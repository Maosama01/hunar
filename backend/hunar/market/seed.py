"""SAMPLE accounts for the demo (called by `make seed`). Every name starts with "SAMPLE" and every
account is is_sample=True; the app shows a SAMPLE DATA badge on them.

Test logins (local demo only; all use PIN 482913):
  worker      9000000101  SAMPLE Ramesh   electrician, assessment in progress (sample-assessment-1)
  worker      9000000102  SAMPLE Sunita   electrician, sample practical signed off, permit document checked
  worker      9000000103  SAMPLE Imran    plumber
  worker      9000000104  SAMPLE Gurpreet carpenter
  customer    9000000201  SAMPLE Customer
  assessor    9000000301  SAMPLE Assessor
  admin       9000000401  SAMPLE Admin
  facilitator 9000000501  SAMPLE Facilitator

The signed-off assessment for SAMPLE Sunita is made through the normal service functions (assessor
decisions with reasons, then sign-off by the SAMPLE assessor account), on synthetic data, so the
demo can show what a customer sees after a real sign-off.
"""
from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account
from hunar.accounts.notice import purposes_for
from hunar.accounts.routes import record_consent
from hunar.api import services as svc
from hunar.api.models import Worker
from hunar.market.models import WorkerProfile
from hunar.rubric import engine as rubric

SAMPLE_PIN = "482913"
ACCOUNTS = [
    ("worker", "9000000101", "SAMPLE Ramesh", "hi",
     {"trade": "electrician", "years_experience": 7, "pincode": "302017", "district": "Jaipur",
      "languages": "hi,en", "bio": "SAMPLE DATA: house and shop wiring", "permit_status": "self_declared",
      "permit_state": "Rajasthan"}),
    ("worker", "9000000102", "SAMPLE Sunita", "hi",
     {"trade": "electrician", "years_experience": 5, "pincode": "302012", "district": "Jaipur",
      "languages": "hi", "bio": "SAMPLE DATA: wiring, DB and earthing", "permit_status": "self_declared",
      "permit_state": "Rajasthan"}),
    ("worker", "9000000103", "SAMPLE Imran", "ur",
     {"trade": "plumber", "years_experience": 10, "pincode": "302004", "district": "Jaipur",
      "languages": "ur,hi", "bio": "SAMPLE DATA: bathroom fittings and leak repair"}),
    ("worker", "9000000104", "SAMPLE Gurpreet", "pa",
     {"trade": "carpenter", "years_experience": 12, "pincode": "302001", "district": "Jaipur",
      "languages": "pa,hi", "bio": "SAMPLE DATA: doors, windows and furniture repair"}),
    ("customer", "9000000201", "SAMPLE Customer", "en", None),
    ("assessor", "9000000301", "SAMPLE Assessor", "hi", None),
    ("admin", "9000000401", "SAMPLE Admin", "en", None),
    ("facilitator", "9000000501", "SAMPLE Facilitator", "hi", None),
]


def _account(s: Session, role: str, phone: str, name: str, lang: str) -> Account:
    phone = auth.normalise_phone(phone)
    acc = s.exec(select(Account).where(Account.phone == phone)).first()
    if acc:
        return acc
    acc = Account(phone=phone, pin_hash=auth.hash_pin(SAMPLE_PIN), role=role, display_name=name, language=lang,
                  is_sample=True)
    s.add(acc)
    s.flush()
    for purpose in purposes_for(role):
        record_consent(s, acc, purpose, True)
    s.commit()
    s.refresh(acc)
    return acc


def _signed_off_sample(s: Session, assessor: Account) -> str:
    """A SAMPLE worker record with every criterion decided by the SAMPLE assessor and signed off."""
    who = auth.actor(assessor)
    w = svc.create_worker(s, "SAMPLE-W002", "hi", who, id="sample-worker-2", is_sample=True)
    a = svc.create_assessment(s, w.id, "SAMPLE DATA: Main 5 saal se wiring, DB aur earthing ka kaam karti hoon.",
                              who, id="sample-assessment-2", is_sample=True)
    svc.confirm_pack(s, a, 13772, who, "sample data: target pack for the demo")
    k = 0
    for task in rubric.load_tasks():
        for cr in task.criteria:
            level = 3 if k % 2 else 2
            k += 1
            svc.decide(s, a, task.task_id, cr.id, "override", level, "SAMPLE DATA: demo decision", who, None)
    p = svc.profile(s, a)
    svc.signoff(s, a, who, True, None, "SAMPLE DATA: demo sign-off")
    return p.recommendation


def seed_accounts() -> None:
    with Session(svc_engine()) as s:
        made = {name: _account(s, role, phone, name, lang) for role, phone, name, lang, _ in ACCOUNTS}
        admin, assessor = made["SAMPLE Admin"], made["SAMPLE Assessor"]
        for role, _phone, name, _lang, prof in ACCOUNTS:
            if role != "worker" or s.get(WorkerProfile, made[name].id):
                continue
            s.add(WorkerProfile(account_id=made[name].id, visible=True, **prof))
            s.commit()
        ramesh = s.get(WorkerProfile, made["SAMPLE Ramesh"].id)
        if ramesh.worker_id is None and s.get(Worker, "sample-worker-1"):
            ramesh.worker_id = "sample-worker-1"
            s.add(ramesh)
            s.commit()
        sunita = s.get(WorkerProfile, made["SAMPLE Sunita"].id)
        if sunita.worker_id is None:
            outcome = _signed_off_sample(s, assessor)
            sunita = s.get(WorkerProfile, made["SAMPLE Sunita"].id)
            sunita.worker_id = "sample-worker-2"
            sunita.permit_status, sunita.permit_checked_by = "document_checked", admin.id
            sunita.permit_checked_at = dt.datetime.now(dt.UTC)
            s.add(sunita)
            s.commit()
            print(f"sample sign-off for SAMPLE Sunita: {outcome}")
    print(f"sample accounts ready ({len(ACCOUNTS)}; PIN in backend/hunar/market/seed.py)")


def svc_engine():
    from hunar.api.db import engine

    return engine()
