"""Adaptive knowledge quiz: Rasch model, EAP ability estimate, content-balanced item selection.

Model (Rasch / 1PL): P(correct | theta, b) = 1 / (1 + exp(-(theta - b))). Theta is the worker's
knowledge on a logit scale, b an item's difficulty. Rasch is chosen over 2PL/3PL because it needs far
fewer respondents to calibrate (about 100-150 per item for +/- 0.5 logit, against 500-1,000 for 3PL;
Linacre, RMT 7:4; Thompson & Weiss 2011).

* Ability: expected a posteriori (EAP) on a grid with a N(0, 1) prior (Bock & Mislevy 1982). The
  posterior SD is the score's uncertainty and is always reported with it.
* Item selection: first the NOS that is furthest below its share of the qualification's weightage
  (content balancing), then, within it, a random choice among the TOP_K items whose difficulty is
  closest to the current estimate (for Rasch the most informative; "randomesque" exposure control).
* Stopping: posterior SD <= SE_TARGET once MIN_ITEMS answers are scored, or MAX_ITEMS answered, or
  no items left. The defaults are checked by a labelled simulation (hunar.quiz.simulate).
* Rapid answers (faster than a person could read the question) are recorded and flagged for the
  assessor but not scored (Wise & Kong 2005). "Don't know" is scored as wrong; it is offered so that
  people do not have to guess.
* A finished quiz counts (opens the app for a worker, goes to the assessor, feeds calibration) only if
  at least MIN_READ_SHARE of its answers were given at reading pace. This share is the quiz's
  response-time effort (Wise & Kong 2005); the threshold of one half is our choice, not a standard.

Before real answers exist, item difficulties are AI-drafted estimates (bank field difficulty_prior),
labelled "uncalibrated". hunar.quiz.calibrate re-estimates them once enough real answers exist.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

GRID = np.linspace(-4.0, 4.0, 161)
_PRIOR = np.exp(-0.5 * GRID**2)
Z90 = 1.6449


@dataclass(frozen=True)
class Rules:
    min_items: int = 12
    max_items: int = 25
    se_target: float = 0.5
    top_k: int = 3
    rapid_base_s: float = 2.0
    rapid_per_word_s: float = 0.1
    min_read_share: float = 0.5


DEFAULT_RULES = Rules()


def p_correct(theta, b):
    return 1.0 / (1.0 + np.exp(-(np.asarray(theta) - np.asarray(b))))


def eap(scored: list[tuple[float, bool]]) -> tuple[float, float]:
    """Posterior mean and SD of theta given (difficulty, correct) pairs."""
    log_post = np.log(_PRIOR)
    for b, x in scored:
        p = p_correct(GRID, b)
        log_post = log_post + (np.log(p) if x else np.log1p(-p))
    w = np.exp(log_post - log_post.max())
    w /= w.sum()
    mean = float((w * GRID).sum())
    return mean, float(math.sqrt(max((w * (GRID - mean) ** 2).sum(), 0.0)))


def is_rapid(seconds: float | None, words: int, rules: Rules = DEFAULT_RULES) -> bool:
    return seconds is not None and seconds < rules.rapid_base_s + rules.rapid_per_word_s * words


def counts(n_scored: int, n_answered: int, rules: Rules = DEFAULT_RULES) -> bool:
    """Whether a finished quiz counts: enough of its answers were given at reading pace (not rapid)."""
    return n_answered > 0 and n_scored >= rules.min_read_share * n_answered


def choose_item(theta: float, remaining: dict[str, list[tuple[str, float]]], targets: dict[str, float],
                counts: dict[str, int], rng: random.Random, rules: Rules = DEFAULT_RULES) -> str | None:
    """Next item id. remaining: NOS -> [(item_id, difficulty)] not yet asked; targets: NOS -> weight."""
    open_nos = [n for n, items in remaining.items() if items]
    if not open_nos:
        return None
    total_w = sum(targets.get(n, 0.0) for n in remaining) or 1.0
    asked = sum(counts.values()) + 1

    def deficit(n: str) -> float:
        return targets.get(n, 0.0) / total_w * asked - counts.get(n, 0)

    best = max(deficit(n) for n in open_nos)
    nos = rng.choice(sorted(n for n in open_nos if math.isclose(deficit(n), best) or deficit(n) == best))
    ranked = sorted(remaining[nos], key=lambda it: (abs(it[1] - theta), it[0]))
    return rng.choice(ranked[: rules.top_k])[0]


def should_stop(n_scored: int, n_answered: int, sd: float, items_left: int, rules: Rules = DEFAULT_RULES) -> bool:
    if items_left == 0 or n_answered >= rules.max_items:
        return True
    return n_scored >= rules.min_items and sd <= rules.se_target


def expected_percent(theta: float, difficulties: list[float]) -> float:
    """Expected share of the whole bank answered correctly at this theta (0-100)."""
    return float(100 * p_correct(theta, np.array(difficulties)).mean()) if difficulties else float("nan")


def summary(theta: float, sd: float, difficulties: list[float]) -> dict:
    lo, hi = theta - Z90 * sd, theta + Z90 * sd
    return {"theta": round(theta, 3), "sd": round(sd, 3), "theta_interval90": [round(lo, 3), round(hi, 3)],
            "expected_percent": round(expected_percent(theta, difficulties), 1),
            "expected_percent_interval90": [round(expected_percent(lo, difficulties), 1),
                                            round(expected_percent(hi, difficulties), 1)]}
