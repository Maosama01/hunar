"""Quiz attempts and answers. Deleted when the worker withdraws 'assessment' consent or is erased."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class QuizAttempt(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    account_id: str = Field(foreign_key="account.id", index=True)
    trade: str
    language: str
    bank_version: str
    params_version: str
    seed: int
    status: str = "in_progress"  # in_progress | finished
    pending_item_id: str | None = None
    pending_since: dt.datetime | None = None
    theta: float = 0.0
    sd: float = 1.0
    n_answered: int = 0
    n_scored: int = 0
    started_at: dt.datetime = Field(default_factory=_now)
    finished_at: dt.datetime | None = None


class QuizResponse(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    attempt_id: str = Field(foreign_key="quizattempt.id", index=True)
    item_id: str
    nos: str
    position: int
    choice: int | None = None  # None = "don't know"
    correct: bool
    seconds: float | None = None
    rapid: bool = False
    scored: bool = True
    difficulty_used: float
    created_at: dt.datetime = Field(default_factory=_now)
