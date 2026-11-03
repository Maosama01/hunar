"""Staff accounts and PIN resets (run on the server, not exposed over HTTP).

  python -m hunar.accounts.cli create --role assessor --phone 98xxxxxxxx --name "Assessor A" [--pin 482913]
  python -m hunar.accounts.cli reset-pin --phone 98xxxxxxxx [--pin 482913]

Without --pin a random 6-digit PIN is generated and printed once; give it to the person in private.
"""
from __future__ import annotations

import argparse
import secrets
import sys

from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account
from hunar.accounts.routes import record_consent, set_pin
from hunar.api.db import engine, init_db
from hunar.audit import log as audit


def _pin(given: str | None, phone: str) -> str:
    pin = given or f"{secrets.randbelow(10**6):06d}"
    while not given and auth.pin_problem(pin, phone):
        pin = f"{secrets.randbelow(10**6):06d}"
    if problem := auth.pin_problem(pin, phone):
        raise SystemExit(problem)
    return pin


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--role", choices=sorted(auth.STAFF_ROLES), required=True)
    c.add_argument("--phone", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--pin")
    c.add_argument("--language", default="hi")
    r = sub.add_parser("reset-pin")
    r.add_argument("--phone", required=True)
    r.add_argument("--pin")
    a = ap.parse_args(argv)
    init_db()
    phone = auth.normalise_phone(a.phone)
    pin = _pin(a.pin, phone)
    with Session(engine()) as s:
        acc = s.exec(select(Account).where(Account.phone == phone)).first()
        if a.cmd == "create":
            if acc:
                raise SystemExit("this phone number already has an account")
            acc = Account(phone=phone, pin_hash=auth.hash_pin(pin), role=a.role, display_name=a.name,
                          language=a.language)
            s.add(acc)
            s.flush()
            audit.append(s, "admin:cli", "account.created", acc.id, {"role": a.role}, commit=False)
            record_consent(s, acc, "account", True)
            s.commit()
            print(f"created {a.role} account {acc.id}")
        else:
            if acc is None or acc.erased_at is not None:
                raise SystemExit("no account with this phone number")
            set_pin(s, acc, pin, "admin:cli")
            print(f"PIN reset for account {acc.id}")
    if not a.pin:
        print(f"PIN (shown once): {pin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
