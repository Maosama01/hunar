"""Phone + PIN login, bearer-token sessions and an optional SMS one-time-code step.

* PINs are 4-6 digits, so a PIN hash alone could be brute-forced if the database leaked. Each hash is
  scrypt over HMAC(pepper, PIN) with a per-account salt; the pepper lives outside the database
  (HUNAR_PIN_PEPPER, or data/secret_pepper created on first use with mode 0600, gitignored).
* Five wrong PINs lock the account for 15 minutes.
* Sessions: a random 256-bit bearer token; only its SHA-256 is stored; 30-day expiry.
* OTP-ready: set HUNAR_OTP_PROVIDER to require a one-time code at registration and allow PIN reset by
  SMS. Only the "test" provider exists (it returns the code to the caller and is for development);
  a real SMS gateway is one class implementing OtpProvider.send. Without a provider, PINs are reset
  by an admin (python -m hunar.accounts.cli reset-pin).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
from functools import lru_cache
from typing import Protocol

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from hunar.accounts.models import Account, AuthSession, OtpChallenge
from hunar.api.db import get_session
from hunar.paths import DATA

SESSION_DAYS = 30
MAX_FAILED = 5
LOCK_MINUTES = 15
OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
PUBLIC_ROLES = {"worker", "customer"}
STAFF_ROLES = {"facilitator", "assessor", "admin"}
ROLES = PUBLIC_ROLES | STAFF_ROLES
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(t: dt.datetime) -> dt.datetime:
    """SQLite returns naive datetimes; everything here is stored in UTC."""
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


# ---- phone and PIN rules ------------------------------------------------------------------------


def normalise_phone(raw: str) -> str:
    """Indian mobile number as +91XXXXXXXXXX. Accepts spaces, dashes, +91, 91 or 0 prefixes."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("enter a 10-digit Indian mobile number")
    return "+91" + digits


def pin_problem(pin: str, phone: str | None = None) -> str | None:
    """Why a PIN is not acceptable, or None."""
    if not re.fullmatch(r"\d{4,6}", pin or ""):
        return "PIN must be 4 to 6 digits"
    if len(set(pin)) == 1:
        return "PIN must not repeat one digit"
    steps = {int(b) - int(a) for a, b in zip(pin, pin[1:], strict=False)}
    if steps in ({1}, {-1}):
        return "PIN must not be a sequence such as 1234"
    if phone and phone.endswith(pin):
        return "PIN must not be the end of your phone number"
    return None


# ---- hashing --------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _pepper() -> bytes:
    if env := os.environ.get("HUNAR_PIN_PEPPER"):
        return env.encode()
    path = DATA / "secret_pepper"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(secrets.token_bytes(32))
    return path.read_bytes()


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    keyed = hmac.new(_pepper(), pin.encode(), hashlib.sha256).digest()
    h = hashlib.scrypt(keyed, salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${h.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, want = stored.split("$")
    except ValueError:
        return False
    keyed = hmac.new(_pepper(), pin.encode(), hashlib.sha256).digest()
    got = hashlib.scrypt(keyed, salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(want) // 2)
    return hmac.compare_digest(got.hex(), want)


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- login and sessions ---------------------------------------------------------------------------


def check_login(s: Session, phone: str, pin: str) -> Account:
    """The account for phone + PIN, counting failures and locking after MAX_FAILED."""
    acc = s.exec(select(Account).where(Account.phone == phone)).first()
    if acc is None or acc.erased_at is not None:
        verify_pin(pin, hash_pin("0000"))  # similar timing whether or not the number exists
        raise HTTPException(401, "phone number or PIN is wrong")
    if acc.locked_until and _aware(acc.locked_until) > _now():
        raise HTTPException(429, "too many wrong PINs; try again in 15 minutes or ask an admin to reset it")
    if not verify_pin(pin, acc.pin_hash):
        acc.failed_attempts += 1
        if acc.failed_attempts >= MAX_FAILED:
            acc.locked_until, acc.failed_attempts = _now() + dt.timedelta(minutes=LOCK_MINUTES), 0
        s.add(acc)
        s.commit()
        raise HTTPException(401, "phone number or PIN is wrong")
    acc.failed_attempts, acc.locked_until = 0, None
    s.add(acc)
    return acc


def new_session(s: Session, acc: Account) -> str:
    token = secrets.token_urlsafe(32)
    s.add(AuthSession(token_hash=_sha(token), account_id=acc.id, expires_at=_now() + dt.timedelta(days=SESSION_DAYS)))
    s.commit()
    return token


def end_session(s: Session, token: str) -> None:
    if row := s.get(AuthSession, _sha(token)):
        s.delete(row)
        s.commit()


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def optional_account(authorization: str | None = Header(None), s: Session = Depends(get_session)) -> Account | None:
    token = _bearer(authorization)
    if not token:
        return None
    row = s.get(AuthSession, _sha(token))
    if row is None or _aware(row.expires_at) < _now():
        return None
    acc = s.get(Account, row.account_id)
    return acc if acc and acc.erased_at is None else None


def current_account(acc: Account | None = Depends(optional_account)) -> Account:
    if acc is None:
        raise HTTPException(401, "please log in")
    return acc


def require_roles(*roles: str):
    allowed = set(roles)

    def dep(acc: Account = Depends(current_account)) -> Account:
        if acc.role not in allowed:
            raise HTTPException(403, f"this needs a {' or '.join(sorted(allowed))} account")
        return acc

    return dep


def actor(acc: Account) -> str:
    """How an account appears in the audit log: role and id, never phone or name."""
    return f"{acc.role}:{acc.id}"


# ---- one-time codes (OTP-ready) -------------------------------------------------------------------


class OtpProvider(Protocol):
    name: str
    returns_code: bool  # True only for the development provider

    def send(self, phone: str, code: str) -> None: ...


class TestOtpProvider:
    """Development only: 'sends' nothing and lets the API return the code, marked as a test code."""

    name = "test"
    returns_code = True

    def send(self, phone: str, code: str) -> None:
        return None


def otp_provider() -> OtpProvider | None:
    name = os.environ.get("HUNAR_OTP_PROVIDER", "").strip().lower()
    if name in ("", "none"):
        return None
    if name == "test":
        return TestOtpProvider()
    raise RuntimeError(f"unknown OTP provider {name!r}; implement OtpProvider.send for your SMS gateway")


def start_otp(s: Session, phone: str, purpose: str) -> tuple[OtpChallenge, str]:
    code = f"{secrets.randbelow(10**6):06d}"
    ch = OtpChallenge(phone=phone, purpose=purpose, code_hash=_sha(f"{phone}|{code}"),
                      expires_at=_now() + dt.timedelta(minutes=OTP_MINUTES))
    s.add(ch)
    s.commit()
    return ch, code


def check_otp(s: Session, challenge_id: str | None, code: str | None, phone: str, purpose: str) -> None:
    ch = s.get(OtpChallenge, challenge_id) if challenge_id else None
    if ch is None or ch.phone != phone or ch.purpose != purpose or ch.used:
        raise HTTPException(422, "request a new code")
    if _aware(ch.expires_at) < _now() or ch.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(422, "the code has expired; request a new one")
    ch.attempts += 1
    ok = hmac.compare_digest(ch.code_hash, _sha(f"{phone}|{code or ''}"))
    ch.used = ok
    s.add(ch)
    s.commit()
    if not ok:
        raise HTTPException(422, "the code is wrong")
