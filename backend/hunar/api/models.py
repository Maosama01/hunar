"""SQLModel tables. Ids of records that can be created offline are client-generated UUID strings."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Worker(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    code: str = Field(index=True, description="Pseudonymous code such as W001; never a real name")
    preferred_language: str = "hi"
    is_sample: bool = False
    created_at: dt.datetime = Field(default_factory=_now)


class Assessment(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    worker_id: str = Field(foreign_key="worker.id", index=True)
    trade: str = "electrician"  # selects the rubric tasks and the qualification packs that apply
    declaration_text: str = ""
    mapping_json: str | None = None
    confirmed_nqr_id: int | None = None
    status: str = "in_progress"  # in_progress -> signed_off
    is_sample: bool = False
    signoff_json: str | None = None
    created_at: dt.datetime = Field(default_factory=_now)


class ChecklistTick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    task_id: str
    item_id: str
    value: bool
    actor: str
    updated_at: dt.datetime = Field(default_factory=_now)


class EvidenceItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    task_id: str
    photo_id: str
    stored_path: str
    sha256: str
    phash: str
    dhash: str
    faces_blurred: int = 0
    detector_status: str = "unavailable"
    detections_json: str | None = None
    duplicate_of: int | None = None
    duplicate_distance: int | None = None
    consent_confirmed: bool = False
    created_at: dt.datetime = Field(default_factory=_now)


class PhashBand(SQLModel, table=True):
    """One bit band of an evidence photo's pHash (hunar.evidence.hashing.phash_bands), indexed so the
    reuse check reads only photos that share a band."""

    __table_args__ = (Index("ix_phashband_band_value", "band", "value"),)

    evidence_id: int = Field(foreign_key="evidenceitem.id", primary_key=True)
    band: int = Field(primary_key=True)
    value: int


class Decision(SQLModel, table=True):
    """Assessor decision on one criterion. Rows are never updated; the latest row wins."""

    id: int | None = Field(default=None, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    task_id: str
    criterion_id: str
    suggested_level: int | None = None
    final_level: int
    action: str  # accept | override
    reason: str | None = None
    assessor: str
    created_at: dt.datetime = Field(default_factory=_now)


class AuditEntry(SQLModel, table=True):
    seq: int | None = Field(default=None, primary_key=True)
    ts: str
    actor: str
    action: str
    subject: str
    payload_json: str
    prev_hash: str
    hash: str


class AppliedOp(SQLModel, table=True):
    """Offline sync idempotency: an op_id is applied at most once."""

    op_id: str = Field(primary_key=True)
    kind: str
    result_json: str
    applied_at: dt.datetime = Field(default_factory=_now)


class StudyItem(SQLModel, table=True):
    """One evidence photo + criterion that raters score in the M4 consistency study."""

    id: str = Field(primary_key=True)
    image_path: str
    task_id: str
    criterion_id: str
    prescore_json: str | None = None
    is_sample: bool = False


class StudyRating(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    client_id: str | None = Field(default=None, unique=True, description="Client-generated idempotency key")
    rater_id: str = Field(index=True)
    item_id: str = Field(foreign_key="studyitem.id")
    condition: str  # unassisted | assisted
    session: int
    position: int
    level: int
    seconds: float | None = None
    created_at: dt.datetime = Field(default_factory=_now)
