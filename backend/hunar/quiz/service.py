"""Quiz attempts: start, answer one item at a time, finish with a score and its uncertainty.

The answer key never leaves the server before an answer is given. The result is a self-check for the
worker and context for an assessor; it is never shown to customers and never produces a badge.
"""
from __future__ import annotations

import datetime as dt
import random
import secrets

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from hunar.accounts.models import Account
from hunar.quiz import bank as banks
from hunar.quiz import engine
from hunar.quiz.models import QuizAttempt, QuizResponse

NOTE = ("Self-check score, not a certificate. It shows what you know about the topics in our questions, not "
        "how well you work. Only a practical assessment signed off by an assessor can give you a badge.")
ENOUGH_PER_NOS = 3


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _responses(s: Session, attempt_id: str) -> list[QuizResponse]:
    return list(s.exec(select(QuizResponse).where(QuizResponse.attempt_id == attempt_id)
                       .order_by(QuizResponse.position)))


def _rng(a: QuizAttempt, n: int) -> random.Random:
    return random.Random(a.seed * 1000 + n)


def _next_item(s: Session, a: QuizAttempt) -> str | None:
    bank, par = banks.load(a.trade), banks.params(a.trade)
    asked = {r.item_id for r in _responses(s, a.id)}
    remaining: dict[str, list[tuple[str, float]]] = {n: [] for n in bank.nos}
    for it in bank.items:
        if it.id not in asked:
            remaining[it.nos].append((it.id, par["b"][it.id]))
    counts: dict[str, int] = {}
    for r in _responses(s, a.id):
        counts[r.nos] = counts.get(r.nos, 0) + 1
    targets = {n: float(v.get("weight", 0)) for n, v in bank.nos.items()}
    return engine.choose_item(a.theta, remaining, targets, counts, _rng(a, a.n_answered))


def order(a: QuizAttempt, item_id: str, n: int) -> list[int]:
    """Option order shown in this attempt: shown position i holds original option order[i]. The bank
    lists the right answer first, so options are always shuffled, reproducibly per attempt and item."""
    return random.Random(f"{a.seed}:{item_id}").sample(range(n), n)


def item_out(a: QuizAttempt, item_id: str) -> dict:
    bank = banks.load(a.trade)
    it = bank.item(item_id)
    text = banks.localise(a.trade, it, a.language)
    perm = order(a, it.id, len(it.options))
    return {"id": it.id, "position": a.n_answered + 1, "nos": it.nos, "nos_title": bank.nos[it.nos]["title"],
            "stem": text["stem"], "options": [text["options"][k] for k in perm], "image": it.image,
            "language": text["language"], "translation": text["translation"],
            "max_items": min(engine.DEFAULT_RULES.max_items, len(bank.items))}


def start(s: Session, acc: Account, trade: str, language: str) -> tuple[QuizAttempt, dict]:
    try:
        bank = banks.load(trade)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    a = QuizAttempt(account_id=acc.id, trade=trade, language=language, bank_version=bank.version,
                    params_version=banks.params(trade)["version"], seed=secrets.randbelow(2**31))
    s.add(a)
    s.flush()
    first = _next_item(s, a)
    a.pending_item_id, a.pending_since = first, _now()
    s.add(a)
    s.commit()
    s.refresh(a)
    return a, item_out(a, first)


def answer(s: Session, a: QuizAttempt, item_id: str, choice: int | None, seconds: float | None) -> dict:
    if a.status != "in_progress":
        raise HTTPException(409, "this quiz is finished")
    if item_id != a.pending_item_id:
        raise HTTPException(409, "answer the question on screen")
    bank, par = banks.load(a.trade), banks.params(a.trade)
    it = bank.item(item_id)
    if choice is not None and not 0 <= choice < len(it.options):
        raise HTTPException(422, "no such option")
    original = None if choice is None else order(a, it.id, len(it.options))[choice]
    elapsed = (_now() - _aware(a.pending_since)).total_seconds() if a.pending_since else None
    secs = seconds if seconds is not None and seconds >= 0 else elapsed
    words = len(banks.localise(a.trade, it, a.language)["stem"].split())
    rapid = engine.is_rapid(secs, words)
    s.add(QuizResponse(attempt_id=a.id, item_id=it.id, nos=it.nos, position=a.n_answered, choice=original,
                       correct=original == it.answer, seconds=secs, rapid=rapid, scored=not rapid,
                       difficulty_used=par["b"][it.id]))
    s.flush()
    scored = [(r.difficulty_used, r.correct) for r in _responses(s, a.id) if r.scored]
    a.theta, a.sd = engine.eap(scored)
    a.n_answered += 1
    a.n_scored = len(scored)
    left = len(bank.items) - a.n_answered
    if engine.should_stop(a.n_scored, a.n_answered, a.sd, left):
        a.status, a.finished_at, a.pending_item_id = "finished", _now(), None
        s.add(a)
        s.commit()
        return {"done": True, "result": result(s, a)}
    a.pending_item_id, a.pending_since = _next_item(s, a), _now()
    s.add(a)
    s.commit()
    return {"done": False, "item": item_out(a, a.pending_item_id), "rapid_warning": rapid}


def counted():
    """SQL condition for a finished attempt that counts (see engine.counts; kept in step with it)."""
    return ((QuizAttempt.status == "finished") & (QuizAttempt.n_answered > 0)
            & (QuizAttempt.n_scored >= engine.DEFAULT_RULES.min_read_share * QuizAttempt.n_answered))


def result(s: Session, a: QuizAttempt) -> dict:
    bank, par = banks.load(a.trade), banks.params(a.trade)
    rs = _responses(s, a.id)
    by_nos = []
    for code, spec in bank.nos.items():
        mine = [r for r in rs if r.nos == code and r.scored]
        if not mine and not any(it.nos == code for it in bank.items):
            continue
        correct = sum(r.correct for r in mine)
        by_nos.append({"nos": code, "title": spec["title"], "answered": len(mine), "correct": correct,
                       "enough": len(mine) >= ENOUGH_PER_NOS})
    revise = [n for n in by_nos if n["answered"] and n["correct"] / n["answered"] < 0.5]
    return {"attempt_id": a.id, "trade": a.trade, "status": a.status, "started_at": a.started_at.isoformat(),
            "finished_at": a.finished_at.isoformat() if a.finished_at else None,
            **engine.summary(a.theta, a.sd, list(par["b"].values())),
            "n_answered": a.n_answered, "n_scored": a.n_scored, "n_rapid": sum(r.rapid for r in rs),
            "n_dont_know": sum(r.choice is None for r in rs), "by_nos": by_nos, "revise": revise,
            "read_share": round(a.n_scored / a.n_answered, 3) if a.n_answered else 0.0,
            "min_read_share": engine.DEFAULT_RULES.min_read_share,
            "counts": a.status == "finished" and engine.counts(a.n_scored, a.n_answered),
            "bank": {"version": a.bank_version, "status": bank.status, "params_version": a.params_version,
                     "calibrated": par["calibrated"]},
            "calibration_note": None if par["calibrated"] else
            "Question difficulties are first estimates, not yet adjusted from real answers.",
            "note": NOTE}


def review(s: Session, a: QuizAttempt) -> list[dict]:
    """After a finished attempt: each question with the right answer and the explanation (for learning)."""
    if a.status != "finished":
        raise HTTPException(409, "finish the quiz first")
    bank = banks.load(a.trade)
    out = []
    for r in _responses(s, a.id):
        it = bank.item(r.item_id)
        text = banks.localise(a.trade, it, a.language)
        perm = order(a, it.id, len(it.options))
        shown = {orig: pos for pos, orig in enumerate(perm)}
        out.append({"position": r.position + 1, "stem": text["stem"], "options": [text["options"][k] for k in perm],
                    "your_choice": None if r.choice is None else shown[r.choice], "answer": shown[it.answer],
                    "correct": r.correct, "rapid": r.rapid,
                    "explanation": text["explanation"], "sources": [bank.sources[k] for k in it.sources],
                    "translation": text["translation"], "language": text["language"]})
    return out


def counted_trades(s: Session, account_id: str) -> set[str]:
    return set(s.exec(select(QuizAttempt.trade).where(QuizAttempt.account_id == account_id, counted())).all())


def gate(s: Session, account_id: str) -> dict:
    """The quiz is compulsory for workers: the first one starts when they register, and until one is
    finished and counts (not rushed) they cannot save a profile, be listed or ask for an assessment. The
    app reads this to send them back to the quiz (to the unfinished one, if any)."""
    done = sorted(counted_trades(s, account_id))
    open_ = s.exec(select(QuizAttempt).where(QuizAttempt.account_id == account_id,
                                             QuizAttempt.status == "in_progress")
                   .order_by(QuizAttempt.started_at.desc())).first()
    return {"done": bool(done), "counted_trades": done,
            "in_progress": {"attempt_id": open_.id, "trade": open_.trade} if open_ else None}


def require_counted(s: Session, account_id: str, trade: str) -> None:
    """A worker works in a trade only after a quiz in that trade that counts (the score does not matter)."""
    if trade not in counted_trades(s, account_id):
        raise HTTPException(409, f"finish the {trade} quiz first, reading each question (a rushed quiz does not count)")


def latest_summary(s: Session, account_id: str, trade: str) -> dict | None:
    """For the assessor: the latest quiz in this trade that counts, and how many did not (rushed)."""
    a = s.exec(select(QuizAttempt).where(QuizAttempt.account_id == account_id, QuizAttempt.trade == trade,
                                         counted())
               .order_by(QuizAttempt.finished_at.desc())).first()
    if a is None:
        return None
    n = len(s.exec(select(QuizAttempt.id).where(QuizAttempt.account_id == account_id,
                                                QuizAttempt.status == "finished")).all())
    ok = len(s.exec(select(QuizAttempt.id).where(QuizAttempt.account_id == account_id, counted())).all())
    return {**result(s, a), "attempts_finished": n, "attempts_not_counted": n - ok}


def erase_quiz_data(s: Session, account_id: str) -> None:
    ids = s.exec(select(QuizAttempt.id).where(QuizAttempt.account_id == account_id)).all()
    if ids:
        s.exec(delete(QuizResponse).where(QuizResponse.attempt_id.in_(ids)))
        s.exec(delete(QuizAttempt).where(QuizAttempt.id.in_(ids)))
    s.flush()
