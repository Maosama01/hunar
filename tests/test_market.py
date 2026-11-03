import datetime as dt
import json

from conftest import make_account
from sqlmodel import Session
from test_accounts import register

from hunar.api import db
from hunar.api.models import Assessment, Worker
from hunar.market.models import WorkerProfile

TOMORROW = (dt.date.today() + dt.timedelta(days=1)).isoformat()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def worker_with_profile(client, phone="9876501234", trade="electrician", pincode="302017", **kw):
    r = register(client, phone=phone, **kw).json()
    profile = {"trade": trade, "years_experience": 8, "pincode": pincode, "district": "Jaipur", "languages": ["hi"],
               "bio": "House wiring", "permit_status": "self_declared", "permit_state": "Rajasthan"}
    assert client.put("/api/me/profile", json=profile, headers=bearer(r["token"])).status_code == 200
    return r["account"]["id"], r["token"]


def customer(client, phone="9988776655"):
    return register(client, phone=phone, role="customer").json()["token"]


def booking(worker_id, job="replace_fitting"):
    return {"worker_id": worker_id, "job_type": job, "description": "Fan not working", "pincode": "302017",
            "preferred_date": TOMORROW, "slot": "morning"}


def test_profile_visible_only_with_consent_and_search(client):
    wid, _ = worker_with_profile(client)
    hidden = register(client, phone="9876500000", consents={"account": True, "contact_share": True,
                                                            "assessment": True, "profile_display": False}).json()
    client.put("/api/me/profile", json={"trade": "electrician", "years_experience": 2, "pincode": "302001"},
               headers=bearer(hidden["token"]))
    found = client.get("/api/market/workers", params={"trade": "electrician", "pincode": "302001"}).json()
    assert [w["account_id"] for w in found] == [wid]
    w = found[0]
    assert w["pincode_area"] == "302xxx" and "phone" not in json.dumps(w) and w["skill_assessed"] is False
    assert client.get("/api/market/workers", params={"pincode": "110001"}).json() == []  # other postal circle
    assert client.get("/api/market/workers", params={"trade": "plumber"}).json() == []


def test_permit_needed_jobs_and_admin_check(client):
    wid, _ = worker_with_profile(client)
    ct = customer(client)
    r = client.post("/api/bookings", json=booking(wid, "wiring"), headers=bearer(ct))
    assert r.status_code == 422 and "reg. 31" in r.json()["detail"]
    assert client.post("/api/bookings", json=booking(wid, "replace_fitting"), headers=bearer(ct)).status_code == 200
    _, admin = make_account(role="admin", phone="9000000002")
    client.post(f"/api/admin/workers/{wid}/permit", json={"status": "document_checked", "state": "Rajasthan"},
                headers=bearer(admin))
    assert client.post("/api/bookings", json=booking(wid, "wiring"), headers=bearer(ct)).status_code == 200
    w = client.get(f"/api/market/workers/{wid}").json()
    assert any(b["kind"] == "permit_checked" for b in w["badges"])


def test_booking_lifecycle_contact_and_rating(client):
    wid, wt = worker_with_profile(client)
    ct = customer(client)
    b = client.post("/api/bookings", json=booking(wid), headers=bearer(ct)).json()
    assert "phone" not in b["other_party"]
    assert client.post(f"/api/bookings/{b['id']}/accept", headers=bearer(ct)).status_code == 403
    acc = client.post(f"/api/bookings/{b['id']}/accept", headers=bearer(wt)).json()
    assert acc["status"] == "accepted" and acc["other_party"]["phone"].startswith("+91")
    assert client.post(f"/api/bookings/{b['id']}/rate", json={"stars": 5}, headers=bearer(ct)).status_code == 409
    client.post(f"/api/bookings/{b['id']}/complete", headers=bearer(wt))
    assert client.post(f"/api/bookings/{b['id']}/rate", json={"stars": 4}, headers=bearer(ct)).status_code == 200
    assert client.post(f"/api/bookings/{b['id']}/rate", json={"stars": 5}, headers=bearer(ct)).status_code == 409
    assert client.get(f"/api/market/workers/{wid}").json()["rating"] == {"average": 4.0, "count": 1}
    assert client.post(f"/api/bookings/{b['id']}/cancel", headers=bearer(ct)).status_code == 409


def test_booking_rules(client):
    wid, wt = worker_with_profile(client)
    ct = customer(client)
    past = {**booking(wid), "preferred_date": (dt.date.today() - dt.timedelta(days=1)).isoformat()}
    assert client.post("/api/bookings", json=past, headers=bearer(ct)).status_code == 422
    assert client.post("/api/bookings", json=booking(wid, "no_such_job"), headers=bearer(ct)).status_code == 422
    assert client.post("/api/bookings", json=booking(wid), headers=bearer(wt)).status_code == 403  # workers don't book
    assert client.post("/api/bookings", json=booking("missing"), headers=bearer(ct)).status_code == 404


def _signed_off(worker_id: str, assessor: str, outcome: str) -> None:
    with Session(db.engine()) as s:
        s.add(Assessment(worker_id=worker_id, status="signed_off", confirmed_nqr_id=13772,
                         signoff_json=json.dumps({"assessor": assessor, "assessor_outcome": outcome})))
        s.commit()


def test_badge_only_from_assessor_signoff(client):
    wid, _ = worker_with_profile(client)
    with Session(db.engine()) as s:
        w = Worker(code="W-TEST")
        s.add(w)
        p = s.get(WorkerProfile, wid)
        p.worker_id = w.id
        s.add(p)
        s.commit()
        worker_id = w.id
    _signed_off(worker_id, "facilitator", "recommend_for_certification")  # not an assessor account
    _signed_off(worker_id, "assessor:abc", "not_yet_competent")
    assert client.get(f"/api/market/workers/{wid}").json()["skill_assessed"] is False
    _signed_off(worker_id, "assessor:abc", "recommend_for_certification")
    w = client.get(f"/api/market/workers/{wid}").json()
    badge = next(b for b in w["badges"] if b["kind"] == "skill_assessed")
    assert w["skill_assessed"] and badge["qualification"]["nqr_id"] == 13772 and "Not a government" in badge["note"]
    assert client.get("/api/market/workers", params={"assessed_only": True}).json()[0]["account_id"] == wid


def test_assessment_request_flow(client):
    wid, wt = worker_with_profile(client)
    r = client.post("/api/assessment-requests", json={"declaration_text": "Main 8 saal se house wiring karta hoon"},
                    headers=bearer(wt))
    assert r.status_code == 200
    assert client.post("/api/assessment-requests", json={}, headers=bearer(wt)).status_code == 409  # one open
    open_ = client.get("/api/assessment-requests").json()  # default client is an assessor
    assert len(open_) == 1 and open_[0]["worker_display_name"] == "Ramesh"
    started = client.post(f"/api/assessment-requests/{open_[0]['id']}/start").json()
    a = client.get(f"/api/assessments/{started['assessment_id']}").json()
    assert a["assessment"]["declaration_text"].startswith("Main 8 saal") and a["mapping"] is not None
    with Session(db.engine()) as s:
        assert s.get(WorkerProfile, wid).worker_id == a["worker"]["id"]
    assert client.get("/api/assessment-requests").json() == []


def test_erasure_cancels_bookings(client):
    wid, wt = worker_with_profile(client)
    ct = customer(client)
    b = client.post("/api/bookings", json=booking(wid), headers=bearer(ct)).json()
    client.delete("/api/auth/me", headers=bearer(wt))
    mine = client.get("/api/bookings", headers=bearer(ct)).json()
    assert mine[0]["id"] == b["id"] and mine[0]["status"] == "cancelled" and mine[0]["description"] == ""
    assert client.get(f"/api/market/workers/{wid}").status_code == 404
