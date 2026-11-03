"""Worker profiles, search, bookings and assessment requests."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account
from hunar.accounts.routes import LANGUAGES, has_consent
from hunar.api import services as svc
from hunar.api.db import get_session
from hunar.audit import log as audit
from hunar.market import service, trades
from hunar.market.models import AssessmentRequest, Booking, WorkerProfile
from hunar.quiz import service as quiz

router = APIRouter(tags=["marketplace"])
DB = Depends(get_session)
WORKER = Depends(auth.require_roles("worker"))
CUSTOMER = Depends(auth.require_roles("customer"))
ASSESSOR = Depends(auth.require_roles("assessor", "admin"))
ADMIN = Depends(auth.require_roles("admin"))
PINCODE = r"^[1-9]\d{5}$"


class ProfileIn(BaseModel):
    trade: Literal["electrician", "plumber", "carpenter"]
    years_experience: int = Field(ge=0, le=60)
    pincode: str = Field(pattern=PINCODE)
    district: str = Field(default="", max_length=60)
    languages: list[str] = Field(default_factory=list)
    bio: str = Field(default="", max_length=300)
    permit_status: Literal["none", "self_declared"] = "none"
    permit_state: str = Field(default="", max_length=40)


class BookingIn(BaseModel):
    worker_id: str
    job_type: str
    description: str = Field(default="", max_length=500)
    pincode: str = Field(pattern=PINCODE)
    preferred_date: dt.date
    slot: Literal["morning", "afternoon", "evening"]


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    review: str = Field(default="", max_length=300)


class RequestIn(BaseModel):
    declaration_text: str = Field(default="", max_length=3000)
    preferred_date: dt.date | None = None


class PermitIn(BaseModel):
    status: Literal["none", "self_declared", "document_checked"]
    state: str = Field(default="", max_length=40)


@router.get("/api/trades")
def list_trades():
    return {k: {"name": v["name"], "qualification": service.qualification_title(v["qualification_nqr_id"]),
                "jobs": v["jobs"]} for k, v in trades.TRADES.items()} | {"_permit_note": trades.PERMIT_NOTE}


# ---- worker's own profile -------------------------------------------------------------------------


@router.get("/api/me/profile")
def my_profile(acc: Account = WORKER, s: Session = DB):
    p = s.get(WorkerProfile, acc.id)
    if p is None:
        return None
    return {**p.model_dump(mode="json", exclude={"permit_checked_by"}), "public": service.public_profile(s, acc, p),
            "visible_reason": None if p.visible else "profile_display consent not given"}


@router.put("/api/me/profile")
def save_profile(body: ProfileIn, acc: Account = WORKER, s: Session = DB):
    if bad := [x for x in body.languages if x not in LANGUAGES]:
        raise HTTPException(422, f"unknown languages: {', '.join(bad)}")
    quiz.require_counted(s, acc.id, body.trade)  # the quiz comes first, and again for a new trade
    p = s.get(WorkerProfile, acc.id) or WorkerProfile(account_id=acc.id, trade=body.trade, pincode=body.pincode)
    if p.permit_status == "document_checked" and (body.trade != p.trade):
        p.permit_status, p.permit_checked_by, p.permit_checked_at = "self_declared", None, None
    for k in ("trade", "years_experience", "pincode", "district", "bio", "permit_state"):
        setattr(p, k, getattr(body, k))
    p.languages = ",".join(body.languages)
    if p.permit_status != "document_checked":
        p.permit_status = body.permit_status
    p.visible = has_consent(s, acc.id, "profile_display")
    p.updated_at = dt.datetime.now(dt.UTC)
    s.add(p)
    audit.append(s, auth.actor(acc), "profile.saved", acc.id, {"trade": p.trade, "visible": p.visible}, commit=False)
    s.commit()
    return my_profile(acc, s)


# ---- customers: search and bookings ---------------------------------------------------------------


@router.get("/api/market/workers")
def search_workers(trade: str | None = None, pincode: str | None = None, assessed_only: bool = False,
                   permit_only: bool = False, s: Session = DB):
    """Open to anyone, so customers can look before they register. No contact details are shown."""
    return service.search(s, trade, pincode, assessed_only, permit_only)


@router.get("/api/market/workers/{account_id}")
def worker_public(account_id: str, s: Session = DB):
    acc, p = s.get(Account, account_id), s.get(WorkerProfile, account_id)
    if acc is None or p is None or not service.listed(s, acc, p):
        raise HTTPException(404, "worker not found")
    return service.public_profile(s, acc, p)


@router.post("/api/bookings")
def create_booking(body: BookingIn, acc: Account = CUSTOMER, s: Session = DB):
    b = service.create_booking(s, acc, body.worker_id, body.job_type, body.description, body.pincode,
                               body.preferred_date, body.slot)
    return service.booking_out(s, b, acc)


@router.get("/api/bookings")
def my_bookings(acc: Account = Depends(auth.current_account), s: Session = DB):
    rows = s.exec(select(Booking).where((Booking.customer_id == acc.id) | (Booking.worker_id == acc.id))
                  .order_by(Booking.created_at.desc()))
    return [service.booking_out(s, b, acc) for b in rows]


@router.post("/api/bookings/{bid}/rate")  # before the {action} route, which would otherwise match "rate"
def rate(bid: str, body: RateIn, acc: Account = CUSTOMER, s: Session = DB):
    b = s.get(Booking, bid)
    if b is None or acc.id != b.customer_id:
        raise HTTPException(404, "booking not found")
    return service.booking_out(s, service.rate_booking(s, b, acc, body.stars, body.review), acc)


@router.post("/api/bookings/{bid}/{action}")
def booking_action(bid: str, action: Literal["accept", "decline", "cancel", "complete"],
                   acc: Account = Depends(auth.current_account), s: Session = DB):
    b = s.get(Booking, bid)
    if b is None or acc.id not in (b.customer_id, b.worker_id):
        raise HTTPException(404, "booking not found")
    return service.booking_out(s, service.act_on_booking(s, b, acc, action), acc)


# ---- assessment requests: worker asks, assessor starts the practical assessment --------------------


def _request_out(s: Session, r: AssessmentRequest, for_assessor: bool) -> dict:
    d = r.model_dump(mode="json")
    if for_assessor:
        from hunar.quiz.service import latest_summary

        acc = s.get(Account, r.account_id)
        d["worker_display_name"] = acc.display_name if acc else None
        d["quiz"] = latest_summary(s, r.account_id, r.trade) if has_consent(s, r.account_id, "assessment") else None
    return d


@router.post("/api/assessment-requests")
def request_assessment(body: RequestIn, acc: Account = WORKER, s: Session = DB):
    if not has_consent(s, acc.id, "assessment"):
        raise HTTPException(409, "give the 'assessment' consent first")
    p = s.get(WorkerProfile, acc.id)
    if p is None:
        raise HTTPException(409, "fill in your profile (trade and PIN code) first")
    quiz.require_counted(s, acc.id, p.trade)
    if s.exec(select(AssessmentRequest).where(AssessmentRequest.account_id == acc.id,
                                              AssessmentRequest.status == "open")).first():
        raise HTTPException(409, "you already have an open request")
    r = AssessmentRequest(account_id=acc.id, trade=p.trade, declaration_text=body.declaration_text.strip(),
                          pincode=p.pincode, preferred_date=body.preferred_date)
    s.add(r)
    audit.append(s, auth.actor(acc), "assessment.requested", r.id, {"trade": p.trade}, commit=False)
    s.commit()
    s.refresh(r)
    return _request_out(s, r, False)


@router.get("/api/assessment-requests")
def list_requests(acc: Account = Depends(auth.current_account), s: Session = DB):
    if acc.role in ("assessor", "admin"):
        rows = s.exec(select(AssessmentRequest).where(AssessmentRequest.status == "open")
                      .order_by(AssessmentRequest.created_at))
        return [_request_out(s, r, True) for r in rows]
    if acc.role == "worker":
        rows = s.exec(select(AssessmentRequest).where(AssessmentRequest.account_id == acc.id)
                      .order_by(AssessmentRequest.created_at.desc()))
        return [_request_out(s, r, False) for r in rows]
    raise HTTPException(403, "only workers and assessors have assessment requests")


@router.post("/api/assessment-requests/{rid}/start")
def start_assessment(rid: str, acc: Account = ASSESSOR, s: Session = DB):
    """Creates the pseudonymous Worker + Assessment for the existing assessor flow and links the profile."""
    r = s.get(AssessmentRequest, rid)
    if r is None or r.status != "open":
        raise HTTPException(404, "open request not found")
    p = s.get(WorkerProfile, r.account_id)
    worker_acc = s.get(Account, r.account_id)
    if p is None or worker_acc is None or worker_acc.erased_at is not None:
        raise HTTPException(409, "the worker's profile no longer exists")
    if p.worker_id is None:
        w = svc.create_worker(s, f"W-{uuid.uuid4().hex[:6].upper()}", worker_acc.language, auth.actor(acc))
        p.worker_id = w.id
        s.add(p)
        s.commit()
    a = svc.create_assessment(s, p.worker_id, r.declaration_text, auth.actor(acc))
    r.status, r.assessor_account_id, r.assessment_id = "started", acc.id, a.id
    s.add(r)
    audit.append(s, auth.actor(acc), "assessment.request_started", r.id, {"assessment_id": a.id}, commit=False)
    s.commit()
    s.refresh(r)
    return {"request": _request_out(s, r, True), "assessment_id": a.id}


@router.post("/api/assessment-requests/{rid}/cancel")
def cancel_request(rid: str, acc: Account = WORKER, s: Session = DB):
    r = s.get(AssessmentRequest, rid)
    if r is None or r.account_id != acc.id:
        raise HTTPException(404, "request not found")
    if r.status != "open":
        raise HTTPException(409, f"cannot cancel a request that is {r.status}")
    r.status = "cancelled"
    s.add(r)
    audit.append(s, auth.actor(acc), "assessment.request_cancelled", r.id, {}, commit=False)
    s.commit()
    s.refresh(r)
    return _request_out(s, r, False)


@router.get("/api/admin/workers")
def admin_workers(trade: str | None = None, q: str = "", acc: Account = ADMIN, s: Session = DB):
    """All worker profiles, hidden ones included, for permit checks. Phone numbers stay masked."""
    from hunar.accounts.routes import mask_phone

    rows = s.exec(select(WorkerProfile, Account).where(WorkerProfile.account_id == Account.id,
                                                       Account.erased_at == None))  # noqa: E711
    out = []
    for p, a in rows:
        if (trade and p.trade != trade) or (q and q.lower() not in a.display_name.lower()):
            continue
        out.append({**service.public_profile(s, a, p), "visible": p.visible, "phone_masked": mask_phone(a.phone),
                    "permit_state": p.permit_state})
    return out


@router.post("/api/admin/workers/{account_id}/permit")
def set_permit(account_id: str, body: PermitIn, acc: Account = ADMIN, s: Session = DB):
    """An admin records that they saw the worker's State permit document (or clears it)."""
    p = s.get(WorkerProfile, account_id)
    if p is None:
        raise HTTPException(404, "profile not found")
    p.permit_status, p.permit_state = body.status, body.state or p.permit_state
    checked = body.status == "document_checked"
    p.permit_checked_by = acc.id if checked else None
    p.permit_checked_at = dt.datetime.now(dt.UTC) if checked else None
    s.add(p)
    audit.append(s, auth.actor(acc), "permit.status_set", account_id, {"status": body.status, "state": p.permit_state},
                 commit=False)
    s.commit()
    s.refresh(p)
    return p.model_dump(mode="json")
