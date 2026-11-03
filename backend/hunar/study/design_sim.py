"""M4 study design check. SIMULATION OF THE METHOD, NOT A RESULT.

Usage:  python -m hunar.study.design_sim

Question: with the study we can run (3 to 5 raters, 20 to 30 evidence items, the same items in both
conditions), how wide will the confidence intervals from `hunar.study.analyse` be, and how big an
improvement in agreement could the study detect?

It generates artificial ratings from a stated model and runs the same analysis many times:

* each item has a true level 0-3 drawn from ITEM_LEVELS (an assumption);
* rater j scores item i as round(true level + rater bias b_j + noise e_ij), clipped to 0-3, with
  b_j ~ N(0, (BIAS_RATIO * sigma)^2) kept per rater across conditions and e_ij ~ N(0, sigma^2);
* sigma is calibrated so that a very large study has a chosen "population" Krippendorff alpha
  (ordinal): 0.50 without the rubric, and 0.50 / 0.60 / 0.70 / 0.80 with it (assumed scenarios);
* each simulated study gets the paired item bootstrap that analyse.diff_alpha uses (95 %
  percentile CI of alpha assisted minus alpha unassisted). "Detected" means the lower bound > 0.

Nothing here is evidence that the rubric helps. The output is written to
experiments/m4_design_simulation.json with "simulation_of_method": true, kept apart from the real
study (experiments/m4_consistency.json). Not modelled: memory of items between sessions, raters who
change over time, items of uneven difficulty, missing ratings.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import numpy as np

from hunar.paths import EXPERIMENTS, ROOT

ITEM_LEVELS = np.array([0.15, 0.30, 0.35, 0.20])  # assumed share of items whose true level is 0..3
BIAS_RATIO = 0.5
BASELINE_ALPHA = 0.50
SCENARIOS = {"no_effect": 0.50, "plus_010": 0.60, "plus_020": 0.70, "plus_030": 0.80}  # keys: no dots (report paths)
RATERS = (3, 4, 5)
ITEMS = (20, 25, 30)
FIG = ROOT / "docs" / "figures" / "m4_design_power.png"


# ---- fast agreement statistics for complete designs (every rater scores every item) -------------


def category_counts(ratings: np.ndarray, n_cat: int = 4) -> np.ndarray:
    """items x raters integer matrix -> items x categories counts."""
    return np.stack([(ratings == c).sum(axis=1) for c in range(n_cat)], axis=1)


def _ordinal_delta2(marg: np.ndarray) -> np.ndarray:
    """Krippendorff's ordinal metric for each row of marginals (... x C) -> (... x C x C)."""
    c = marg.shape[-1]
    cum = np.cumsum(marg, axis=-1)
    d = np.zeros(marg.shape[:-1] + (c, c))
    for g in range(c):
        for h in range(g, c):
            v = cum[..., h] - (cum[..., g - 1] if g else 0) - (marg[..., g] + marg[..., h]) / 2
            d[..., g, h] = d[..., h, g] = v**2
    return d


def alpha_ordinal_weighted(counts: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Krippendorff's ordinal alpha for item multisets.

    counts: items x C category counts (each item rated by the same number m >= 2 of raters).
    weights: B x items, how often each item appears in each (bootstrap) sample.
    Returns B alphas. Uses the coincidence-matrix definition (Krippendorff 2011).
    """
    m = counts.sum(axis=1)
    per_item = (counts[:, :, None] * counts[:, None, :] - np.einsum("ic,cd->icd", counts, np.eye(counts.shape[1])))
    per_item = per_item / (m - 1)[:, None, None]
    o = np.einsum("bi,icd->bcd", weights, per_item)
    marg = o.sum(axis=2)
    n = marg.sum(axis=1)
    d2 = _ordinal_delta2(marg)
    d_o = np.einsum("bcd,bcd->b", o, d2)
    d_e = np.einsum("bc,bd,bcd->b", marg, marg, d2) / (n - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(d_e > 0, 1 - d_o / d_e, 1.0)


def alpha_ordinal(ratings: np.ndarray) -> float:
    counts = category_counts(ratings)
    return float(alpha_ordinal_weighted(counts, np.ones((1, len(counts))))[0])


def fleiss_kappa_counts(counts: np.ndarray) -> float:
    m = counts.sum(axis=1)[0]
    p_i = ((counts**2).sum(axis=1) - m) / (m * (m - 1))
    p_c = counts.sum(axis=0) / counts.sum()
    pe = float((p_c**2).sum())
    return float((p_i.mean() - pe) / (1 - pe))


# ---- generative model ---------------------------------------------------------------------------


def simulate(rng: np.random.Generator, truth: np.ndarray, bias: np.ndarray, sigma: float) -> np.ndarray:
    noise = rng.normal(0, sigma, (len(truth), len(bias)))
    return np.clip(np.rint(truth[:, None] + bias[None, :] * sigma + noise), 0, 3).astype(int)


def population_alpha(sigma: float, n_items: int = 20000, n_raters: int = 5, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    truth = rng.choice(4, n_items, p=ITEM_LEVELS)
    bias = rng.normal(0, BIAS_RATIO, n_raters)
    return alpha_ordinal(simulate(rng, truth, bias, sigma))


def calibrate(target: float, lo: float = 0.01, hi: float = 5.0, iters: int = 40) -> float:
    """sigma whose population alpha equals target (alpha falls as sigma grows)."""
    for _ in range(iters):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if population_alpha(mid) > target else (lo, mid)
    return round((lo + hi) / 2, 4)


def run_cell(n_raters: int, n_items: int, s_un: float, s_as: float, reps: int, n_boot: int,
             rng: np.random.Generator) -> dict:
    detected, widths, half_un, diffs = 0, [], [], []
    for _ in range(reps):
        truth = rng.choice(4, n_items, p=ITEM_LEVELS)
        bias = rng.normal(0, BIAS_RATIO, n_raters)  # same raters in both conditions
        c_un = category_counts(simulate(rng, truth, bias, s_un))
        c_as = category_counts(simulate(rng, truth, bias, s_as))
        w = rng.multinomial(n_items, np.full(n_items, 1 / n_items), size=n_boot)  # same items resampled
        a_un, a_as = alpha_ordinal_weighted(c_un, w), alpha_ordinal_weighted(c_as, w)
        d = a_as - a_un
        lo, hi = np.percentile(d, [2.5, 97.5])
        detected += lo > 0
        widths.append(hi - lo)
        u_lo, u_hi = np.percentile(a_un, [2.5, 97.5])
        half_un.append((u_hi - u_lo) / 2)
        ones = np.ones((1, n_items))
        diffs.append(float(alpha_ordinal_weighted(c_as, ones)[0] - alpha_ordinal_weighted(c_un, ones)[0]))
    return {"raters": n_raters, "items": n_items, "detected_share": round(detected / reps, 3),
            "median_diff_ci_width": round(float(np.median(widths)), 3),
            "median_alpha_ci_halfwidth_unassisted": round(float(np.median(half_un)), 3),
            "mean_estimated_diff": round(float(np.mean(diffs)), 3)}


def run(reps: int, n_boot: int, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    sig = {name: calibrate(a) for name, a in {"baseline": BASELINE_ALPHA, **SCENARIOS}.items()}
    out = {}
    for name, target in SCENARIOS.items():
        cells = [run_cell(r, n, sig["baseline"], sig[name], reps, n_boot, rng) for r in RATERS for n in ITEMS]
        out[name] = {"population_alpha_unassisted": BASELINE_ALPHA, "population_alpha_assisted": target,
                     "sigma_unassisted": sig["baseline"], "sigma_assisted": sig[name], "cells": cells,
                     "detected_share_by_design": {f"{c['raters']}x{c['items']}": c["detected_share"] for c in cells}}
        print(f"{name:10s} " + "  ".join(f"{c['raters']}x{c['items']}:{c['detected_share']:.2f}" for c in cells))
    return out


def plot(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [n for n in SCENARIOS if n != "no_effect"]
    fig, axes = plt.subplots(1, len(names), figsize=(9, 3.2), sharey=True)
    for ax, name in zip(axes, names, strict=True):
        cells = res["scenarios"][name]["cells"]
        for r, style in zip(RATERS, ["o-", "s--", "^-."], strict=True):
            pts = [c for c in cells if c["raters"] == r]
            ax.plot([c["items"] for c in pts], [c["detected_share"] for c in pts], style, label=f"{r} raters")
        a = res["scenarios"][name]
        ax.set_title(f"alpha {a['population_alpha_unassisted']:.2f} -> {a['population_alpha_assisted']:.2f}",
                     fontsize=9)
        ax.set_xticks(ITEMS)
        ax.set_xlabel("evidence items")
        ax.set_ylim(0, 1)
        ax.axhline(0.8, color="grey", lw=0.6, ls=":")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("share of simulated studies\nwhose 95% CI excludes 0")
    axes[0].legend(fontsize=8)
    fig.suptitle("SIMULATION OF THE METHOD (assumed scenarios, not a result): power of the M4 design", fontsize=9)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=150)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args(argv)
    res = {
        "experiment": "m4_design_simulation",
        "simulation_of_method": True,
        "data_kind": "synthetic",
        "warning": ("SIMULATION OF THE METHOD, NOT A RESULT: artificial ratings from an assumed model, used to "
                    "size the study. Says nothing about whether the rubric helps real assessors."),
        "assumptions": {"item_true_level_shares": ITEM_LEVELS.tolist(), "rater_bias_sd_over_noise_sd": BIAS_RATIO,
                        "population_alpha_unassisted": BASELINE_ALPHA,
                        "scenarios_population_alpha_assisted": SCENARIOS,
                        "calibration": "sigma set so a 20,000-item, 5-rater simulated study has the stated alpha"},
        "method": ("paired item bootstrap of Krippendorff's ordinal alpha (assisted minus unassisted), 95% "
                   "percentile CI; detected = lower bound > 0, as in hunar.study.analyse.diff_alpha"),
        "reps_per_cell": a.reps,
        "bootstrap_resamples": a.boot,
        "not_modelled": ["memory of items between sessions", "rater drift", "uneven item difficulty",
                         "missing ratings"],
        "command": "python -m hunar.study.design_sim",
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "scenarios": run(a.reps, a.boot),
    }
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "m4_design_simulation.json").write_text(json.dumps(res, indent=2) + "\n")
    plot(res)
    print("wrote experiments/m4_design_simulation.json and", FIG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
