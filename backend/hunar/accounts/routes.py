"""/api/auth: register, log in, consents, erasure. Only workers and customers can self-register;
staff accounts (facilitator, assessor, admin) are created with `python -m hunar.accounts.cli`.
A worker chooses a trade when registering, and the first quiz in that trade starts at once."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account, AuthSession, Consent
from hunar.accounts.notice import NOTICE_VERSION, purposes_for
from hunar.api.db import get_session
from hunar.audit import log as audit
from hunar.quiz import bank as quiz_banks
from hunar.quiz import service as quiz

router = APIRouter(prefix="/api/auth", tags=["accounts"])
DB = Depends(get_session)
# Languages the app offers: English and the 22 languages of the Eighth Schedule (ISO 639 codes).
LANGUAGES = ["en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "gom", "mai", "ml", "mni", "mr", "ne", "or",
             "pa", "sa", "sat", "sd", "ta", "te", "ur"]


class RegisterIn(BaseModel):
    phone: str
    pin: str
    role: Literal["worker", "customer"]
    display_name: str = Field(min_length=1, max_length=40)
    language: str = "hi"
    is_adult: bool = Field(description="The person confirms they are 18 or older")
    consents: dict[str, bool] = Field(description="purpose -> granted, for every purpose shown in the notice")
    trade: str | None = Field(default=None, description="Workers only: the trade of the quiz that starts at once")
    otp_challenge_id: str | None = None
    otp_code: str | None = None


class LoginIn(BaseModel):
    phone: str
    pin: str


class OtpIn(BaseModel):
    phone: str
    purpose: Literal["register", "reset"]


class ResetIn(BaseModel):
    phone: str
    new_pin: str
    otp_challenge_id: str
    otp_code: str


class ConsentIn(BaseModel):
    purpose: str
    granted: bool


class MeIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    language: str | None = None


def _phone_or_422(raw: str) -> str:
    try:
        return auth.normalise_phone(raw)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def latest_consents(s: Session, account_id: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for c in s.exec(select(Consent).where(Consent.account_id == account_id).order_by(Consent.id)):
        out[c.purpose] = c.granted
    return out


def has_consent(s: Session, account_id: str, purpose: str) -> bool:
    return latest_consents(s, account_id).get(purpose, False)


def account_out(s: Session, acc: Account) -> dict:
    out = {"id": acc.id, "role": acc.role, "display_name": acc.display_name, "language": acc.language,
           "phone_masked": mask_phone(acc.phone), "phone_verified": acc.phone_verified, "is_sample": acc.is_sample,
           "consents": latest_consents(s, acc.id)}
    if acc.role == "worker":
        out["quiz"] = quiz.gate(s, acc.id)
    return out


def mask_phone(phone: str) -> str:
    return phone[:3] + " ••••• " + phone[-3:] if phone.startswith("+91") else "hidden"


def record_consent(s: Session, acc: Account, purpose: str, granted: bool) -> None:
    s.add(Consent(account_id=acc.id, purpose=purpose, granted=granted, notice_version=NOTICE_VERSION,
                  language=acc.language))
    audit.append(s, auth.actor(acc), "consent.granted" if granted else "consent.withdrawn", acc.id,
                 {"purpose": purpose, "notice_version": NOTICE_VERSION}, commit=False)


@router.get("/config")
def config():
    p = auth.otp_provider()
    return {"otp_required": p is not None, "otp_provider": p.name if p else None, "languages": LANGUAGES,
            "notice_version": NOTICE_VERSION, "purposes": {r: purposes_for(r) for r in sorted(auth.PUBLIC_ROLES)},
            "pin_rules": "4 to 6 digits; not one repeated digit, not a sequence, not the end of your phone number"}


@router.post("/otp")
def request_otp(body: OtpIn, s: Session = DB):
    p = auth.otp_provider()
    if p is None:
        return {"otp_required": False}
    phone = _phone_or_422(body.phone)
    ch, code = auth.start_otp(s, phone, body.purpose)
    p.send(phone, code)
    out = {"otp_required": True, "challenge_id": ch.id, "expires_in_minutes": auth.OTP_MINUTES}
    if p.returns_code:
        out["test_code"] = code
        out["test_note"] = "TEST MODE: no SMS was sent. Never enable the test provider on a real server."
    return out


@router.post("/register")
def register(body: RegisterIn, s: Session = DB):
    phone = _phone_or_422(body.phone)
    if problem := auth.pin_problem(body.pin, phone):
        raise HTTPException(422, problem)
    if not body.is_adult:
        raise HTTPException(422, "Hunar is only for people aged 18 or older")
    if body.language not in LANGUAGES:
        raise HTTPException(422, f"unknown language {body.language!r}")
    needed = purposes_for(body.role)
    missing = [p for p, spec in needed.items() if spec["required"] and not body.consents.get(p)]
    if missing:
        raise HTTPException(422, f"these consents are needed to use Hunar: {', '.join(missing)}")
    if unknown := set(body.consents) - set(needed):
        raise HTTPException(422, f"unknown consent purposes for a {body.role}: {', '.join(sorted(unknown))}")
    if body.role == "worker" and body.trade not in quiz_banks.trades():
        raise HTTPException(422, f"choose your trade: one of {', '.join(quiz_banks.trades())}")
    if body.role != "worker" and body.trade is not None:
        raise HTTPException(422, "only workers choose a trade")
    verified = False
    if auth.otp_provider() is not None:
        auth.check_otp(s, body.otp_challenge_id, body.otp_code, phone, "register")
        verified = True
    if s.exec(select(Account).where(Account.phone == phone)).first():
        raise HTTPException(409, "this phone number already has an account; log in instead")
    acc = Account(phone=phone, pin_hash=auth.hash_pin(body.pin), role=body.role, display_name=body.display_name.strip(),
                  language=body.language, phone_verified=verified)
    s.add(acc)
    s.flush()
    audit.append(s, auth.actor(acc), "account.registered", acc.id, {"role": acc.role}, commit=False)
    for purpose in needed:
        record_consent(s, acc, purpose, bool(body.consents.get(purpose)))
    s.commit()
    s.refresh(acc)
    out = {"token": auth.new_session(s, acc)}
    if acc.role == "worker":  # the quiz is compulsory and comes straight after registering
        attempt, item = quiz.start(s, acc, body.trade, acc.language)
        out["quiz"] = {"attempt_id": attempt.id, "item": item}
    return out | {"account": account_out(s, acc)}


@router.post("/login")
def login(body: LoginIn, s: Session = DB):
    acc = auth.check_login(s, _phone_or_422(body.phone), body.pin)
    return {"token": auth.new_session(s, acc), "account": account_out(s, acc)}


@router.post("/logout")
def logout(authorization: str | None = Header(None), s: Session = DB):
    if token := auth._bearer(authorization):
        auth.end_session(s, token)
    return {"ok": True}


@router.get("/me")
def me(acc: Account = Depends(auth.current_account), s: Session = DB):
    return account_out(s, acc)


@router.post("/reset-pin")
def reset_pin(body: ResetIn, s: Session = DB):
    if auth.otp_provider() is None:
        raise HTTPException(409, "SMS codes are not set up on this server; ask an admin to reset your PIN")
    phone = _phone_or_422(body.phone)
    auth.check_otp(s, body.otp_challenge_id, body.otp_code, phone, "reset")
    acc = s.exec(select(Account).where(Account.phone == phone)).first()
    if acc is None or acc.erased_at is not None:
        raise HTTPException(404, "no account with this phone number")
    if problem := auth.pin_problem(body.new_pin, phone):
        raise HTTPException(422, problem)
    set_pin(s, acc, body.new_pin, auth.actor(acc))
    return {"ok": True}


def set_pin(s: Session, acc: Account, pin: str, by: str) -> None:
    acc.pin_hash, acc.failed_attempts, acc.locked_until = auth.hash_pin(pin), 0, None
    s.add(acc)
    for old in s.exec(select(AuthSession).where(AuthSession.account_id == acc.id)):
        s.delete(old)  # a new PIN logs out every device
    audit.append(s, by, "account.pin_reset", acc.id, {}, commit=False)
    s.commit()


@router.post("/consents")
def change_consent(body: ConsentIn, acc: Account = Depends(auth.current_account), s: Session = DB):
    spec = purposes_for(acc.role).get(body.purpose)
    if spec is None:
        raise HTTPException(422, f"unknown consent purpose {body.purpose!r}")
    if spec["required"] and not body.granted:
        raise HTTPException(409, f"withdrawing '{body.purpose}' erases your account: use DELETE /api/auth/me")
    record_consent(s, acc, body.purpose, body.granted)
    s.commit()
    from hunar.market.service import on_consent_granted, on_consent_withdrawn

    (on_consent_granted if body.granted else on_consent_withdrawn)(s, acc, body.purpose)
    return account_out(s, acc)


@router.patch("/me")
def update_me(body: MeIn, acc: Account = Depends(auth.current_account), s: Session = DB):
    if body.language is not None:
        if body.language not in LANGUAGES:
            raise HTTPException(422, f"unknown language {body.language!r}")
        acc.language = body.language
    if body.display_name is not None:
        acc.display_name = body.display_name.strip()
    s.add(acc)
    audit.append(s, auth.actor(acc), "account.updated", acc.id,
                 {"fields": sorted(k for k, v in body.model_dump().items() if v is not None)}, commit=False)
    s.commit()
    return account_out(s, acc)


@router.delete("/me")
def erase_me(acc: Account = Depends(auth.current_account), s: Session = DB):
    erase_account(s, acc, auth.actor(acc))
    return {"erased": True}


def erase_account(s: Session, acc: Account, by: str) -> None:
    """Right to erasure: remove personal data, end sessions, close open bookings, delete quiz answers."""
    from hunar.market.service import on_account_erased

    on_account_erased(s, acc)
    for old in s.exec(select(AuthSession).where(AuthSession.account_id == acc.id)):
        s.delete(old)
    acc.phone, acc.pin_hash, acc.display_name = f"erased:{acc.id}", "", "Erased account"
    acc.erased_at = dt.datetime.now(dt.UTC)
    s.add(acc)
    audit.append(s, by, "account.erased", acc.id, {}, commit=False)
    s.commit()
