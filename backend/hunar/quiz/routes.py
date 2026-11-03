"""/api/quiz: the adaptive self-check quiz for workers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account
from hunar.accounts.routes import LANGUAGES, has_consent
from hunar.api.db import get_session
from hunar.quiz import bank as banks
from hunar.quiz import engine, service
from hunar.quiz.models import QuizAttempt

router = APIRouter(prefix="/api/quiz", tags=["quiz"])
DB = Depends(get_session)
WORKER = Depends(auth.require_roles("worker"))


class StartIn(BaseModel):
    trade: str
    language: str = "hi"


class AnswerIn(BaseModel):
    item_id: str
    choice: int | None = None  # None = "don't know"
    seconds: float | None = None


def _mine(s: Session, aid: str, acc: Account) -> QuizAttempt:
    a = s.get(QuizAttempt, aid)
    if a is None or a.account_id != acc.id:
        raise HTTPException(404, "quiz not found")
    return a


@router.get("/banks")
def list_banks():
    out = {}
    for t in banks.trades():
        b, p = banks.load(t), banks.params(t)
        translated = sorted(f.name.split(".")[1] for f in (banks.BANKS / "i18n").glob(f"{t}.*.json"))
        out[t] = {"version": b.version, "status": b.status, "n_items": len(b.items),
                  "qualification_nqr_id": b.qualification_nqr_id, "calibrated": p["calibrated"],
                  "nos": {k: {"title": v["title"], "weight": v.get("weight", 0)} for k, v in b.nos.items()},
                  "languages": {"original": ["en", "hi"], "machine_translated": translated},
                  "rules": engine.DEFAULT_RULES.__dict__}
    return out


@router.post("/attempts")
def start(body: StartIn, acc: Account = WORKER, s: Session = DB):
    if not has_consent(s, acc.id, "assessment"):
        raise HTTPException(409, "give the 'assessment' consent to take the quiz")
    if body.language not in LANGUAGES:
        raise HTTPException(422, f"unknown language {body.language!r}")
    a, item = service.start(s, acc, body.trade, body.language)
    return {"attempt_id": a.id, "item": item}


@router.post("/attempts/{aid}/answers")
def answer(aid: str, body: AnswerIn, acc: Account = WORKER, s: Session = DB):
    return service.answer(s, _mine(s, aid, acc), body.item_id, body.choice, body.seconds)


@router.get("/attempts")
def my_attempts(acc: Account = WORKER, s: Session = DB):
    rows = s.exec(select(QuizAttempt).where(QuizAttempt.account_id == acc.id).order_by(QuizAttempt.started_at.desc()))
    return [service.result(s, a) if a.status == "finished" else
            {"attempt_id": a.id, "trade": a.trade, "status": a.status, "n_answered": a.n_answered} for a in rows]


@router.get("/attempts/{aid}")
def get_attempt(aid: str, acc: Account = WORKER, s: Session = DB):
    a = _mine(s, aid, acc)
    if a.status == "finished":
        return {"done": True, "result": service.result(s, a)}
    return {"done": False, "item": service.item_out(a, a.pending_item_id)}


@router.get("/attempts/{aid}/review")
def review(aid: str, acc: Account = WORKER, s: Session = DB):
    return service.review(s, _mine(s, aid, acc))
