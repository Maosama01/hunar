"""Account tables: people who log in (workers, customers, assessors, facilitators, admins).

Personal data kept here is limited to what the consent notice lists (hunar.accounts.notice): phone
number, display name, language and a salted, peppered hash of the PIN. Audit entries refer to
accounts by id only, so erasing an account leaves no phone number or name in the audit log.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Account(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    phone: str = Field(index=True, unique=True, description="+91 and 10 digits; 'erased:<id>' after erasure")
    pin_hash: str
    role: str = Field(index=True)  # worker | customer | facilitator | assessor | admin
    display_name: str
    language: str = "hi"
    phone_verified: bool = False  # True only after an OTP check (when an OTP provider is configured)
    failed_attempts: int = 0
    locked_until: dt.datetime | None = None
    is_sample: bool = False
    erased_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=_now)


class AuthSession(SQLModel, table=True):
    """Login session. Only the SHA-256 of the bearer token is stored."""

    token_hash: str = Field(primary_key=True)
    account_id: str = Field(foreign_key="account.id", index=True)
    created_at: dt.datetime = Field(default_factory=_now)
    expires_at: dt.datetime


class Consent(SQLModel, table=True):
    """Append-only consent record; the latest row per (account, purpose) is in force."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: str = Field(foreign_key="account.id", index=True)
    purpose: str  # see hunar.accounts.notice.PURPOSES
    granted: bool
    notice_version: str
    language: str
    created_at: dt.datetime = Field(default_factory=_now)


class OtpChallenge(SQLModel, table=True):
    """One-time code sent by SMS. Used only when an OTP provider is configured (HUNAR_OTP_PROVIDER)."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    phone: str = Field(index=True)
    purpose: str  # register | reset
    code_hash: str
    attempts: int = 0
    used: bool = False
    expires_at: dt.datetime
    created_at: dt.datetime = Field(default_factory=_now)
