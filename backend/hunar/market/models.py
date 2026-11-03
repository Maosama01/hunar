"""Marketplace tables: worker profiles, assessment requests and bookings."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class WorkerProfile(SQLModel, table=True):
    """What a worker chooses to show customers. Shown only while 'profile_display' consent is in force."""

    account_id: str = Field(foreign_key="account.id", primary_key=True)
    trade: str = Field(index=True)
    years_experience: int = 0
    pincode: str = Field(index=True)
    district: str = ""
    languages: str = ""  # comma-separated language codes
    bio: str = ""
    visible: bool = False
    # Link to the assessor-side Worker record once an assessor starts an assessment.
    worker_id: str | None = Field(default=None, foreign_key="worker.id")
    permit_status: str = "none"  # none | self_declared | document_checked
    permit_state: str = ""
    permit_checked_by: str | None = None
    permit_checked_at: dt.datetime | None = None
    updated_at: dt.datetime = Field(default_factory=_now)


class AssessmentRequest(SQLModel, table=True):
    """A worker asks for a practical assessment; an assessor picks it up and runs the M1-M3 flow."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    account_id: str = Field(foreign_key="account.id", index=True)
    trade: str
    declaration_text: str = ""
    pincode: str = ""
    preferred_date: dt.date | None = None
    status: str = "open"  # open | started | cancelled
    assessor_account_id: str | None = None
    assessment_id: str | None = Field(default=None, foreign_key="assessment.id")
    created_at: dt.datetime = Field(default_factory=_now)


class Booking(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="account.id", index=True)
    worker_id: str = Field(foreign_key="account.id", index=True)
    trade: str
    job_type: str
    description: str = ""
    pincode: str = ""
    preferred_date: dt.date
    slot: str  # morning | afternoon | evening
    status: str = "requested"  # requested | accepted | declined | cancelled | completed
    rating: int | None = None
    review: str = ""
    created_at: dt.datetime = Field(default_factory=_now)
    updated_at: dt.datetime = Field(default_factory=_now)
