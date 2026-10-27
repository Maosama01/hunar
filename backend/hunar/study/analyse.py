"""M4 consistency study: does the rubric + pre score help assessors agree?

Usage:  python -m hunar.study.analyse [--csv data/study/ratings.csv]

Reads real rater scores (from the app database, or a CSV exported from /api/study/export),
drops sample items, and computes for each condition (unassisted / assisted):

* Fleiss' kappa (statsmodels) on items rated by every rater in that condition,
* Krippendorff's alpha, ordinal (krippendorff package; handles missing ratings),
* mean pairwise exact agreement and within-one-level agreement,
* 95 % bootstrap confidence intervals by resampling items,
* the assisted minus unassisted difference in alpha, bootstrapped over items rated in both.

With no real ratings it writes "RESULT PENDING"; it never simulates a study.
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

import krippendorff
import numpy as np
import pandas as pd
from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

from hunar.paths import EXPERIMENTS, ROOT

CONDITIONS = ["unassisted", "assisted"]
FIG = ROOT / "docs" / "figures" / "m4_agreement.png"


def matrix(df: pd.DataFrame) -> pd.DataFrame:
    """items x raters matrix of levels (NaN when a rater did not score an item)."""
    return df.pivot_table(index="item_id", columns="rater_id", values="level", aggfunc="last")


def fleiss(m: pd.DataFrame) -> float | None:
    full = m.dropna()
    if len(full) < 2 or full.shape[1] < 2:
        return None
    table, _ = aggregate_raters(full.to_numpy(dtype=int), n_cat=4)
    return float(fleiss_kappa(table, method="fleiss"))


def alpha(m: pd.DataFrame) -> float | None:
    data = m.T.to_numpy(dtype=float)  # raters x items
    if data.shape[0] < 2 or np.sum(~np.isnan(data)) < 4:
        return None
    if len(np.unique(data[~np.isnan(data)])) < 2:
        return 1.0  # every rating identical: perfect agreement (alpha is undefined, 0/0)
    return float(krippendorff.alpha(reliability_data=data, level_of_measurement="ordinal"))


def pairwise(m: pd.DataFrame) -> tuple[float | None, float | None]:
    exact, within1 = [], []
    for a, b in itertools.combinations(m.columns, 2):
        both = m[[a, b]].dropna()
        if len(both):
            d = (both[a] - both[b]).abs()
            exact.append(float((d == 0).mean()))
            within1.append(float((d <= 1).mean()))
    return (float(np.mean(exact)) if exact else None, float(np.mean(within1)) if within1 else None)


def stats(m: pd.DataFrame) -> dict:
    ex, w1 = pairwise(m)
    return {"fleiss_kappa": fleiss(m), "krippendorff_alpha_ordinal": alpha(m), "pairwise_exact": ex,
            "pairwise_within_one": w1}


def bootstrap(m: pd.DataFrame, n: int = 2000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    items = m.index.to_numpy()
    draws: dict[str, list[float]] = {}
    for _ in range(n):
        s = stats(m.loc[rng.choice(items, size=len(items), replace=True)].reset_index(drop=True))
        for k, v in s.items():
            if v is not None and not np.isnan(v):
                draws.setdefault(k, []).append(v)
    return {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
            for k, v in draws.items()}


def diff_alpha(mu: pd.DataFrame, ma: pd.DataFrame, n: int = 2000, seed: int = 1) -> dict | None:
    common = mu.index.intersection(ma.index)
    if len(common) < 3:
        return None
    rng = np.random.default_rng(seed)
    point = (alpha(ma.loc[common]) or 0) - (alpha(mu.loc[common]) or 0)
    d = []
    for _ in range(n):
        idx = rng.choice(common.to_numpy(), size=len(common), replace=True)
        a1, a0 = alpha(ma.loc[idx].reset_index(drop=True)), alpha(mu.loc[idx].reset_index(drop=True))
        if a1 is not None and a0 is not None and not (np.isnan(a1) or np.isnan(a0)):
            d.append(a1 - a0)
    return {"items_in_both": int(len(common)), "alpha_assisted_minus_unassisted": round(point, 4),
            "ci95": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)] if d else None}


def analyse(df: pd.DataFrame, n_boot: int = 2000) -> dict:
    df = df[~df["is_sample"].astype(str).str.lower().isin(["true", "1"])].copy()
    df["level"] = df["level"].astype(int)
    out = {"experiment": "m4_consistency", "data_kind": "real", "n_ratings": int(len(df)),
           "raters": sorted(df["rater_id"].unique().tolist()), "conditions": {}}
    mats = {}
    for c in CONDITIONS:
        sub = df[df["condition"] == c]
        if sub.empty:
            out["conditions"][c] = {"status": "RESULT PENDING", "n_items": 0, "n_raters": 0}
            continue
        m = matrix(sub)
        mats[c] = m
        out["conditions"][c] = {"n_items": int(m.shape[0]), "n_raters": int(m.shape[1]), **stats(m),
                                "ci95": bootstrap(m, n_boot)}
    out["difference"] = diff_alpha(mats["unassisted"], mats["assisted"], n_boot) if len(mats) == 2 else None
    out["limitations"] = ("Small sample of raters and items; raters saw the same items in both conditions "
                          "(memory effects reduced, not removed, by the gap between sessions and random order).")
    return out


def load(csv_path: Path | None) -> pd.DataFrame:
    if csv_path:
        return pd.read_csv(csv_path)
    from sqlmodel import Session, select

    from hunar.api.db import engine, init_db
    from hunar.api.models import StudyItem, StudyRating

    init_db()
    with Session(engine()) as s:
        rows = [{"rater_id": r.rater_id, "item_id": r.item_id, "condition": r.condition, "level": r.level,
                 "is_sample": s.get(StudyItem, r.item_id).is_sample} for r in s.exec(select(StudyRating))]
    return pd.DataFrame(rows, columns=["rater_id", "item_id", "condition", "level", "is_sample"])


def plot(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = ["fleiss_kappa", "krippendorff_alpha_ordinal", "pairwise_exact"]
    labels = ["Fleiss' kappa", "Krippendorff's alpha\n(ordinal)", "Pairwise exact\nagreement"]
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for k, c in enumerate(CONDITIONS):
        r = res["conditions"][c]
        vals = [r.get(m) or 0 for m in metrics]
        lo = [v - r["ci95"].get(m, [v, v])[0] for m, v in zip(metrics, vals, strict=True)]
        hi = [r["ci95"].get(m, [v, v])[1] - v for m, v in zip(metrics, vals, strict=True)]
        ax.bar(np.arange(3) + (k - 0.5) * 0.38, vals, 0.38, yerr=[lo, hi], capsize=4, label=c)
    ax.set_xticks(range(3), labels)
    ax.set_ylim(min(0, ax.get_ylim()[0]), 1)
    ax.set_title(f"Inter-assessor agreement ({len(res['raters'])} raters, real data)", fontsize=10)
    ax.legend()
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=150)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path)
    a = ap.parse_args(argv)
    df = load(a.csv)
    base = {"command": "python -m hunar.study.analyse", "created": dt.datetime.now().isoformat(timespec="seconds")}
    real = df[~df["is_sample"].astype(str).str.lower().isin(["true", "1"])] if len(df) else df
    if real.empty:
        res = {"experiment": "m4_consistency", "status": "RESULT PENDING",
               "reason": "no real rater scores collected yet (sample items are excluded)", **base}
        print("M4: RESULT PENDING (no real rater data)")
    else:
        res = {**analyse(df), **base}
        if all(res["conditions"][c].get("n_items") for c in CONDITIONS):
            plot(res)
        print(json.dumps(res["conditions"], indent=1))
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "m4_consistency.json").write_text(json.dumps(res, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
