"""Quiz design check. SIMULATION OF THE METHOD, NOT A RESULT.

Usage:  python -m hunar.quiz.simulate [--n 1000]

Simulated workers with a known ability (theta ~ N(0, 1)) take each trade's quiz through the same
engine the app uses (hunar.quiz.engine), so we can see how close the estimate gets and how many
questions it takes, before any real worker has answered. Three assumed scenarios:

* calibrated: the true item difficulties equal the bank's estimates;
* cold_start: the true difficulties differ from the AI-drafted estimates by N(0, 0.7^2) logits, which
  is the situation until real answers are used to calibrate (an assumption, not a measurement);
* cold_start_guessing: as cold_start, and a worker who does not know an answer still picks the right
  option with probability 0.2 (a 3PL-style guessing floor the Rasch scorer does not model).

Two policies: the adaptive quiz (engine defaults) and a fixed-length quiz of 20 content-balanced
random items. Reported: bias and RMSE of theta, mean number of questions, the share of 90% intervals
that contain the true theta (coverage), and the bias for low-ability workers under guessing.
Output: experiments/quiz_cat_simulation.json (simulation_of_method: true) and
docs/figures/quiz_cat_simulation.png. It says nothing about real workers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys

import numpy as np

from hunar.paths import EXPERIMENTS, ROOT
from hunar.quiz import bank as banks
from hunar.quiz import engine

SCENARIOS = {"calibrated": (0.0, 0.0), "cold_start": (0.7, 0.0), "cold_start_guessing": (0.7, 0.2)}
FIXED_LENGTH = 20
FIG = ROOT / "docs" / "figures" / "quiz_cat_simulation.png"


def run_test(theta: float, b_used: dict[str, float], b_true: dict[str, float], nos_of: dict[str, str],
             targets: dict[str, float], guess: float, policy: str, rng: random.Random,
             np_rng: np.random.Generator) -> tuple[float, float, int]:
    rules = engine.DEFAULT_RULES
    if policy == "fixed":
        rules = engine.Rules(min_items=FIXED_LENGTH, max_items=FIXED_LENGTH, se_target=0.0,
                             top_k=len(b_used))  # random within the chosen NOS
    remaining: dict[str, list[tuple[str, float]]] = {n: [] for n in targets}
    for item, b in b_used.items():
        remaining[nos_of[item]].append((item, b))
    counts: dict[str, int] = {}
    scored: list[tuple[float, bool]] = []
    est, sd = 0.0, 1.0
    while True:
        item = engine.choose_item(est, remaining, targets, counts, rng, rules)
        if item is None:
            break
        nos = nos_of[item]
        remaining[nos] = [x for x in remaining[nos] if x[0] != item]
        counts[nos] = counts.get(nos, 0) + 1
        p = guess + (1 - guess) * float(engine.p_correct(theta, b_true[item]))
        scored.append((b_used[item], bool(np_rng.random() < p)))
        est, sd = engine.eap(scored)
        left = sum(len(v) for v in remaining.values())
        if engine.should_stop(len(scored), len(scored), sd, left, rules):
            break
    return est, sd, len(scored)


def simulate_trade(trade: str, n: int, seed: int = 0) -> dict:
    bank = banks.load(trade)
    b_prior = {it.id: it.difficulty_prior for it in bank.items}
    nos_of = {it.id: it.nos for it in bank.items}
    targets = {k: float(v.get("weight", 0)) for k, v in bank.nos.items()}
    out = {"n_items": len(bank.items), "scenarios": {}}
    for s_i, (name, (b_err, guess)) in enumerate(SCENARIOS.items()):
        out["scenarios"][name] = {}
        for policy in ("adaptive", "fixed"):
            np_rng = np.random.default_rng(seed * 100 + s_i)
            rng = random.Random(seed * 100 + s_i)
            thetas = np_rng.normal(0, 1, n)
            rows = []
            for th in thetas:
                b_true = {k: v + np_rng.normal(0, b_err) if b_err else v for k, v in b_prior.items()}
                rows.append((th, *run_test(float(th), b_prior, b_true, nos_of, targets, guess,
                                           "fixed" if policy == "fixed" else "adaptive", rng, np_rng)))
            a = np.array(rows)
            err = a[:, 1] - a[:, 0]
            cover = np.abs(err) <= engine.Z90 * a[:, 2]
            low = a[:, 0] < -1
            out["scenarios"][name][policy] = {
                "bias": round(float(err.mean()), 3), "rmse": round(float(np.sqrt((err**2).mean())), 3),
                "mean_items": round(float(a[:, 3].mean()), 1), "coverage90": round(float(cover.mean()), 3),
                "mean_sd": round(float(a[:, 2].mean()), 3),
                "bias_low_ability": round(float(err[low].mean()), 3) if low.any() else None,
                "corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3)}
        print(trade, name, {p: (v["rmse"], v["mean_items"], v["coverage90"]) for p, v in
                            out["scenarios"][name].items()})
    return out


def plot(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    trades = list(res["trades"])
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    width = 0.13
    for k, (scen, colour) in enumerate(zip(SCENARIOS, ["#1b7837", "#e08214", "#b2182b"], strict=True)):
        for j, policy in enumerate(("adaptive", "fixed")):
            x = np.arange(len(trades)) + (k * 2 + j - 2.5) * width
            rm = [res["trades"][t]["scenarios"][scen][policy]["rmse"] for t in trades]
            n = [res["trades"][t]["scenarios"][scen][policy]["mean_items"] for t in trades]
            hatch = None if policy == "adaptive" else "//"
            label = f"{scen}, {policy}"
            axes[0].bar(x, rm, width, color=colour, hatch=hatch, edgecolor="white", label=label)
            axes[1].bar(x, n, width, color=colour, hatch=hatch, edgecolor="white")
    for ax, title in zip(axes, ["RMSE of ability estimate (logits)", "Questions asked (mean)"], strict=True):
        ax.set_xticks(range(len(trades)), trades)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=6.5, ncol=1, loc="upper left")
    fig.suptitle("SIMULATION OF THE METHOD (simulated workers, assumed scenarios): quiz design check", fontsize=9)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=150)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    res = {"experiment": "quiz_cat_simulation", "simulation_of_method": True, "data_kind": "synthetic",
           "warning": ("SIMULATION OF THE METHOD, NOT A RESULT: simulated workers answering under assumed "
                       "scenarios. It checks the quiz design; it says nothing about real workers."),
           "rules": engine.DEFAULT_RULES.__dict__, "fixed_length": FIXED_LENGTH,
           "scenarios": {k: {"difficulty_error_sd": v[0], "guessing": v[1]} for k, v in SCENARIOS.items()},
           "n_simulated_per_cell": a.n, "command": "python -m hunar.quiz.simulate",
           "created": dt.datetime.now().isoformat(timespec="seconds"),
           "trades": {t: simulate_trade(t, a.n) for t in banks.trades()}}
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "quiz_cat_simulation.json").write_text(json.dumps(res, indent=2) + "\n")
    plot(res)
    print("wrote experiments/quiz_cat_simulation.json and", FIG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
