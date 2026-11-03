"""Profiles, badges, search and bookings.

Badge rule (project rule 5): a customer sees "skill assessed" only when an assessor, logged in with an
assessor account, signed off an assessment of this worker with the outcome "recommend for
certification". Quiz results are never shown to customers. Each badge says exactly what was checked,
by whom and when; none of them is a government certificate or licence.

Listing rule: customers find and book only workers who finished the quiz for their trade (the quiz is
compulsory for workers). Whether they did, and how well, is not shown.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import cache

from fastapi import HTTPException
from sqlmodel import Session, select

from hunar.accounts.models import Account
from hunar.api.models import Assessment
from hunar.audit import log as audit
from hunar.market import trades
from hunar.market.models import AssessmentRequest, Booking, WorkerProfile
from hunar.paths import DATA
from hunar.quiz.models import QuizAttempt
from hunar.quiz.service import finished_trades

TRANSITIONS = {  # (status, action) -> (new status, who may do it)
    ("requested", "accept"): ("accepted", "worker"),
    ("requested", "decline"): ("declined", "worker"),
    ("requested", "cancel"): ("cancelled", "either"),
    ("accepted", "cancel"): ("cancelled", "either"),
    ("accepted", "complete"): ("completed", "either"),
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@cache
def qualification_title(nqr_id: int | None) -> dict | None:
    """Title, level and awarding body from the parsed official file (M1 packs and trade packs alike)."""
    if nqr_id is None:
        return None
    f = DATA / "processed" / "qp" / f"{nqr_id}.json"
    if not f.exists():
        return {"nqr_id": nqr_id, "title": f"NQR {nqr_id}", "nsqf_level": None, "awarding_body": None}
    p = json.loads(f.read_text())
    return {"nqr_id": nqr_id, "title": p["title"], "nsqf_level": p.get("nsqf_level"),
            "awarding_body": p.get("awarding_body")}


def badges(s: Session, profile: WorkerProfile) -> list[dict]:
    out = []
    if profile.worker_id:
        rows = s.exec(select(Assessment).where(Assessment.worker_id == profile.worker_id,
                                               Assessment.status == "signed_off"))
        for a in rows:
            so = json.loads(a.signoff_json or "{}")
            if so.get("assessor_outcome") == "recommend_for_certification" and str(so.get("assessor", "")).startswith(
                    "assessor:"):
                out.append({"kind": "skill_assessed", "qualification": qualification_title(a.confirmed_nqr_id),
                            "assessment_id": a.id, "date": a.created_at.date().isoformat(),
                            "note": "Practical assessment signed off by a Hunar assessor. Not a government certificate."})
    if profile.permit_status == "document_checked":
        out.append({"kind": "permit_checked", "state": profile.permit_state,
                    "date": profile.permit_checked_at.date().isoformat() if profile.permit_checked_at else None,
                    "note": "An admin saw the State permit document. Hunar does not issue permits."})
    return out


def rating(s: Session, worker_id: str) -> dict:
    vals = [b.rating for b in s.exec(select(Booking).where(Booking.worker_id == worker_id, Booking.rating != None))]  # noqa: E711
    return {"average": round(sum(vals) / len(vals), 2) if vals else None, "count": len(vals)}


def public_profile(s: Session, acc: Account, p: WorkerProfile) -> dict:
    b = badges(s, p)
    return {"account_id": acc.id, "display_name": acc.display_name, "trade": p.trade,
            "trade_name": trades.TRADES.get(p.trade, {}).get("name"), "years_experience": p.years_experience,
            "district": p.district, "pincode_area": p.pincode[:3] + "xxx", "languages": [x for x in p.languages.split(",") if x],
            "bio": p.bio, "badges": b, "skill_assessed": any(x["kind"] == "skill_assessed" for x in b),
            "permit": {"status": p.permit_status, "state": p.permit_state}, "rating": rating(s, acc.id),
            "is_sample": acc.is_sample}


def listed(s: Session, acc: Account, p: WorkerProfile) -> bool:
    """Customers can see and book this worker: profile shown, account not erased, quiz finished."""
    return p.visible and acc.erased_at is None and p.trade in finished_trades(s, acc.id)


def search(s: Session, trade: str | None, pincode: str | None, assessed_only: bool, permit_only: bool,
           limit: int = 30) -> list[dict]:
    rows = s.exec(select(WorkerProfile, Account).where(WorkerProfile.account_id == Account.id,
                                                       WorkerProfile.visible == True,  # noqa: E712
                                                       Account.erased_at == None))  # noqa: E711
    quizzed = {(a, t) for a, t in s.exec(select(QuizAttempt.account_id, QuizAttempt.trade)
                                         .where(QuizAttempt.status == "finished"))}
    out = []
    for p, acc in rows:
        if (trade and p.trade != trade) or (acc.id, p.trade) not in quizzed:
            continue
        if pincode and p.pincode[:2] != pincode[:2]:
            continue  # different postal circle: too far away
        item = public_profile(s, acc, p)
        if assessed_only and not item["skill_assessed"]:
            continue
        if permit_only and p.permit_status != "document_checked":
            continue
        nearness = 2 if pincode and p.pincode == pincode else 1 if pincode and p.pincode[:3] == pincode[:3] else 0
        item["_key"] = (item["skill_assessed"], nearness, item["rating"]["average"] or 0, p.years_experience)
        out.append(item)
    out.sort(key=lambda x: x.pop("_key"), reverse=True)
    return out[:limit]


# ---- bookings -------------------------------------------------------------------------------------


def create_booking(s: Session, customer: Account, worker_id: str, job_type: str, description: str, pincode: str,
                   preferred_date: dt.date, slot: str) -> Booking:
    worker = s.get(Account, worker_id)
    p = s.get(WorkerProfile, worker_id)
    if worker is None or p is None or not listed(s, worker, p):
        raise HTTPException(404, "this worker is not available")
    if worker.id == customer.id:
        raise HTTPException(422, "you cannot book yourself")
    try:
        spec = trades.job(p.trade, job_type)
    except KeyError as e:
        raise HTTPException(422, str(e)) from e
    if spec["needs_permit"] and p.permit_status != "document_checked":
        raise HTTPException(422, trades.PERMIT_NOTE + " This worker's permit has not been checked.")
    if preferred_date < dt.date.today():
        raise HTTPException(422, "choose today or a later date")
    b = Booking(customer_id=customer.id, worker_id=worker.id, trade=p.trade, job_type=job_type,
                description=description.strip(), pincode=pincode, preferred_date=preferred_date, slot=slot)
    s.add(b)
    s.flush()
    audit.append(s, f"customer:{customer.id}", "booking.requested", b.id,
                 {"worker": worker.id, "trade": p.trade, "job_type": job_type, "needs_permit": spec["needs_permit"]},
                 commit=False)
    s.commit()
    s.refresh(b)
    return b


def booking_out(s: Session, b: Booking, viewer: Account) -> dict:
    d = b.model_dump(mode="json")
    other_id = b.worker_id if viewer.id == b.customer_id else b.customer_id
    other = s.get(Account, other_id)
    d["other_party"] = {"account_id": other_id, "display_name": other.display_name if other else "Unknown",
                        "role": "worker" if other_id == b.worker_id else "customer"}
    if other and other.erased_at is None and contact_visible(b):
        d["other_party"]["phone"] = other.phone  # shared only after acceptance (contact_share consent)
    d["job"] = trades.TRADES.get(b.trade, {}).get("jobs", {}).get(b.job_type)
    d["you_are"] = "customer" if viewer.id == b.customer_id else "worker"
    return d


CONTACT_DAYS_AFTER_COMPLETION = 14


def contact_visible(b: Booking) -> bool:
    """Phones are shared while a booking is accepted and for a short time after it is completed."""
    if b.status == "accepted":
        return True
    if b.status == "completed":
        done = b.updated_at if b.updated_at.tzinfo else b.updated_at.replace(tzinfo=dt.UTC)
        return _now() - done <= dt.timedelta(days=CONTACT_DAYS_AFTER_COMPLETION)
    return False


def act_on_booking(s: Session, b: Booking, viewer: Account, action: str) -> Booking:
    rule = TRANSITIONS.get((b.status, action))
    if rule is None:
        raise HTTPException(409, f"cannot {action} a booking that is {b.status}")
    new, who = rule
    is_worker, is_customer = viewer.id == b.worker_id, viewer.id == b.customer_id
    if not (is_worker or is_customer) or (who == "worker" and not is_worker):
        raise HTTPException(403, f"only the worker can {action} this booking")
    b.status, b.updated_at = new, _now()
    s.add(b)
    audit.append(s, f"{viewer.role}:{viewer.id}", f"booking.{new}", b.id, {}, commit=False)
    s.commit()
    s.refresh(b)
    return b


def rate_booking(s: Session, b: Booking, viewer: Account, stars: int, review: str) -> Booking:
    if viewer.id != b.customer_id:
        raise HTTPException(403, "only the customer can rate this booking")
    if b.status != "completed":
        raise HTTPException(409, "rate a booking after it is completed")
    if b.rating is not None:
        raise HTTPException(409, "this booking is already rated")
    b.rating, b.review, b.updated_at = stars, review.strip(), _now()
    s.add(b)
    audit.append(s, f"customer:{viewer.id}", "booking.rated", b.id, {"stars": stars}, commit=False)
    s.commit()
    s.refresh(b)
    return b


# ---- consent withdrawal and erasure ---------------------------------------------------------------


def on_consent_granted(s: Session, acc: Account, purpose: str) -> None:
    if purpose == "profile_display" and (p := s.get(WorkerProfile, acc.id)):
        p.visible = True
        s.add(p)
        s.commit()


def on_consent_withdrawn(s: Session, acc: Account, purpose: str) -> None:
    if purpose == "profile_display" and (p := s.get(WorkerProfile, acc.id)):
        p.visible = False
        s.add(p)
    if purpose == "assessment":
        from hunar.quiz.service import erase_quiz_data

        erase_quiz_data(s, acc.id)
        for r in s.exec(select(AssessmentRequest).where(AssessmentRequest.account_id == acc.id,
                                                        AssessmentRequest.status == "open")):
            r.status, r.declaration_text = "cancelled", ""
            s.add(r)
    s.commit()


def on_account_erased(s: Session, acc: Account) -> None:
    from hunar.quiz.service import erase_quiz_data

    erase_quiz_data(s, acc.id)
    if p := s.get(WorkerProfile, acc.id):
        s.delete(p)
    for r in s.exec(select(AssessmentRequest).where(AssessmentRequest.account_id == acc.id)):
        r.declaration_text, r.pincode = "", ""
        if r.status == "open":
            r.status = "cancelled"
        s.add(r)
    for b in s.exec(select(Booking).where((Booking.customer_id == acc.id) | (Booking.worker_id == acc.id))):
        if b.status in ("requested", "accepted"):
            b.status = "cancelled"
        b.description, b.review = "", ""
        b.updated_at = _now()
        s.add(b)
    s.flush()
