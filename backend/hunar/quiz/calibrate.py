"""Re-estimate quiz item difficulties from real answers (`make quiz-calibrate`).

Only finished attempts by real (non-sample) accounts that count (at least half the answers at reading
pace; a low-effort attempt is left out, as in motivation filtering), and only answers that were scored
(not flagged as rapid). Until a trade has MIN_ATTEMPTS finished attempts nothing changes and the result is
written as RESULT PENDING. After that, difficulties are re-estimated by alternating
  1. each attempt's ability by EAP (hunar.quiz.engine.eap) with the current difficulties, and
  2. each item's difficulty by MAP with a N(prior, PRIOR_SD^2) prior around the AI-drafted estimate
     (a few Newton steps on the Rasch log-likelihood),
and only items with at least MIN_PER_ITEM answers are updated; the rest keep their prior. The new
difficulties are written to hunar/quiz/banks/params/<trade>.json with a new version, so attempts in
progress keep the version they started with. A summary goes to experiments/quiz_calibration_<trade>.json.

Rasch difficulties need about 100-150 respondents per item for +/- 0.5 logit (Linacre, RMT 7:4); the
thresholds below are the minimum at which an update is attempted, and the summary reports n per item.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import numpy as np
from sqlmodel import Session, select

from hunar.accounts.models import Account
from hunar.api.db import engine as db_engine
from hunar.api.db import init_db
from hunar.paths import EXPERIMENTS
from hunar.quiz import bank as banks
from hunar.quiz import engine
from hunar.quiz.models import QuizAttempt, QuizResponse
from hunar.quiz.service import counted

MIN_ATTEMPTS = 100
MIN_PER_ITEM = 30
PRIOR_SD = 1.0
CYCLES = 15


def fit_difficulties(responses: list[tuple[str, str, bool]], priors: dict[str, float], min_per_item: int = MIN_PER_ITEM,
                     cycles: int = CYCLES) -> tuple[dict[str, float], dict[str, int]]:
    """MAP difficulties from (person, item, correct) triples; items with too few answers keep the prior."""
    counts: dict[str, int] = {}
    for _, item, _ in responses:
        counts[item] = counts.get(item, 0) + 1
    b = dict(priors)
    persons: dict[str, list[tuple[str, bool]]] = {}
    for p, item, x in responses:
        persons.setdefault(p, []).append((item, x))
    by_item: dict[str, list[tuple[str, bool]]] = {}
    for p, item, x in responses:
        by_item.setdefault(item, []).append((p, x))
    for _ in range(cycles):
        theta = {p: engine.eap([(b[i], x) for i, x in rs])[0] for p, rs in persons.items()}
        for item, rs in by_item.items():
            if counts[item] < min_per_item or item not in priors:
                continue
            th = np.array([theta[p] for p, _ in rs])
            x = np.array([float(v) for _, v in rs])
            bj = b[item]
            for _ in range(5):  # Newton steps on log L(b) + log prior
                p_ = engine.p_correct(th, bj)
                grad = float((p_ - x).sum()) - (bj - priors[item]) / PRIOR_SD**2
                hess = -float((p_ * (1 - p_)).sum()) - 1 / PRIOR_SD**2
                bj = float(np.clip(bj - grad / hess, -4, 4))
            b[item] = bj
    return b, counts


def collect(s: Session, trade: str) -> list[tuple[str, str, bool]]:
    rows = s.exec(select(QuizResponse, QuizAttempt, Account)
                  .where(QuizResponse.attempt_id == QuizAttempt.id, QuizAttempt.account_id == Account.id,
                         QuizAttempt.trade == trade, counted(),
                         Account.is_sample == False, QuizResponse.scored == True))  # noqa: E712
    return [(a.id, r.item_id, r.correct) for r, a, _ in rows]


def calibrate(trade: str, s: Session) -> dict:
    bank = banks.load(trade)
    priors = {it.id: it.difficulty_prior for it in bank.items}
    responses = collect(s, trade)
    n_attempts = len({p for p, _, _ in responses})
    base = {"experiment": f"quiz_calibration_{trade}", "data_kind": "real", "trade": trade,
            "bank_version": bank.version, "n_attempts": n_attempts, "n_responses": len(responses),
            "min_attempts": MIN_ATTEMPTS, "min_per_item": MIN_PER_ITEM, "command": "python -m hunar.quiz.calibrate",
            "created": dt.datetime.now().isoformat(timespec="seconds")}
    if n_attempts < MIN_ATTEMPTS:
        return {**base, "status": "RESULT PENDING",
                "reason": f"{n_attempts} finished real attempts; at least {MIN_ATTEMPTS} are needed"}
    b, counts = fit_difficulties(responses, priors)
    updated = {k: round(v, 3) for k, v in b.items() if counts.get(k, 0) >= MIN_PER_ITEM}
    version = f"cal-{dt.date.today().isoformat()}-n{n_attempts}"
    path = banks.BANKS / "params" / f"{trade}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"version": version, "b": updated, "n_per_item": counts}, indent=1) + "\n")
    shifts = [updated[k] - priors[k] for k in updated]
    return {**base, "status": "calibrated", "params_version": version, "items_updated": len(updated),
            "items_kept_prior": len(priors) - len(updated),
            "mean_abs_shift_from_prior": round(float(np.mean(np.abs(shifts))), 3) if shifts else None,
            "n_per_item": counts}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    init_db()
    EXPERIMENTS.mkdir(exist_ok=True)
    with Session(db_engine()) as s:
        for trade in banks.trades():
            res = calibrate(trade, s)
            (EXPERIMENTS / f"quiz_calibration_{trade}.json").write_text(json.dumps(res, indent=2) + "\n")
            print(trade, res["status"], f"(attempts {res['n_attempts']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
