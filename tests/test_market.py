import datetime as dt
import json

from conftest import make_account
from sqlmodel import Session
from test_accounts import finish_quiz, register

from hunar.api import db
from hunar.api.models import Assessment, Worker
from hunar.market.models import WorkerProfile

TOMORROW = (dt.date.today() + dt.timedelta(days=1)).isoformat()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def worker_with_profile(client, phone="9876501234", trade="electrician", pincode="302017", **kw):
    r = register(client, phone=phone, trade=trade, **kw).json()
    finish_quiz(client, r["token"])
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
    finish_quiz(client, hidden["token"])
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


def test_granting_profile_consent_makes_existing_profile_visible(client):
    r = register(client, trade="plumber", consents={"account": True, "contact_share": True, "assessment": True,
                                                    "profile_display": False}).json()
    finish_quiz(client, r["token"])
    client.put("/api/me/profile", json={"trade": "plumber", "years_experience": 3, "pincode": "302017"},
               headers=bearer(r["token"]))
    assert client.get(f"/api/market/workers/{r['account']['id']}").status_code == 404
    client.post("/api/auth/consents", json={"purpose": "profile_display", "granted": True}, headers=bearer(r["token"]))
    assert client.get(f"/api/market/workers/{r['account']['id']}").status_code == 200


def test_update_language_and_name(client):
    tok = register(client).json()["token"]
    me = client.patch("/api/auth/me", json={"language": "ta", "display_name": "Ramu"}, headers=bearer(tok)).json()
    assert me["language"] == "ta" and me["display_name"] == "Ramu"
    assert client.patch("/api/auth/me", json={"language": "xx"}, headers=bearer(tok)).status_code == 422


def test_admin_lists_hidden_profiles_with_masked_phones(client):
    r = register(client, trade="carpenter", consents={"account": True, "contact_share": True, "assessment": True,
                                                      "profile_display": False}).json()
    finish_quiz(client, r["token"])
    client.put("/api/me/profile", json={"trade": "carpenter", "years_experience": 3, "pincode": "302017"},
               headers=bearer(r["token"]))
    _, admin = make_account(role="admin", phone="9000000002")
    rows = client.get("/api/admin/workers", headers=bearer(admin)).json()
    assert rows[0]["visible"] is False and "•" in rows[0]["phone_masked"] and "9876501234" not in json.dumps(rows)
    assert client.get("/api/admin/workers", headers=bearer(r["token"])).status_code == 403


def test_worker_cancels_open_request(client):
    _, wt = worker_with_profile(client)
    rid = client.post("/api/assessment-requests", json={}, headers=bearer(wt)).json()["id"]
    assert client.post(f"/api/assessment-requests/{rid}/cancel", headers=bearer(wt)).json()["status"] == "cancelled"
    assert client.post(f"/api/assessment-requests/{rid}/cancel", headers=bearer(wt)).status_code == 409
    assert client.post("/api/assessment-requests", json={}, headers=bearer(wt)).status_code == 200  # can ask again


def test_phone_hidden_some_time_after_completion(client):
    from hunar.market.models import Booking

    wid, wt = worker_with_profile(client)
    ct = customer(client)
    b = client.post("/api/bookings", json=booking(wid), headers=bearer(ct)).json()
    client.post(f"/api/bookings/{b['id']}/accept", headers=bearer(wt))
    done = client.post(f"/api/bookings/{b['id']}/complete", headers=bearer(ct)).json()
    assert "phone" in done["other_party"]
    with Session(db.engine()) as s:
        row = s.get(Booking, b["id"])
        row.updated_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=15)
        s.add(row)
        s.commit()
    assert "phone" not in client.get("/api/bookings", headers=bearer(ct)).json()[0]["other_party"]


def test_write_endpoints_return_full_rows(client):
    wid, wt = worker_with_profile(client)
    saved = client.put("/api/me/profile", json={"trade": "electrician", "years_experience": 9, "pincode": "302017"},
                       headers=bearer(wt)).json()
    assert saved["trade"] == "electrician" and saved["years_experience"] == 9
    _, admin = make_account(role="admin", phone="9000000002")
    permit = client.post(f"/api/admin/workers/{wid}/permit", json={"status": "document_checked", "state": "RJ"},
                         headers=bearer(admin)).json()
    assert permit["permit_status"] == "document_checked"
    client.post("/api/assessment-requests", json={}, headers=bearer(wt))
    rid = client.get("/api/assessment-requests").json()[0]["id"]
    started = client.post(f"/api/assessment-requests/{rid}/start").json()
    assert started["request"]["status"] == "started"


def test_practical_assessment_needs_rubric_tasks_for_the_trade(client, monkeypatch):
    listed = client.get("/api/trades").json()
    assert all(listed[k]["practical_assessment"] for k in ("electrician", "plumber", "carpenter"))
    _, pt = worker_with_profile(client, phone="9876500011", trade="plumber")
    from hunar.rubric import engine

    real = engine.tasks_for
    monkeypatch.setattr(engine, "tasks_for", lambda trade: () if trade == "plumber" else real(trade))
    r = client.post("/api/assessment-requests", json={"declaration_text": "Das saal se plumbing"}, headers=bearer(pt))
    assert r.status_code == 409 and "not available for this trade" in r.json()["detail"]
    with Session(db.engine()) as s:  # a request made while the trade still had tasks is not started either
        from hunar.market.models import AssessmentRequest

        acc_id = client.get("/api/auth/me", headers=bearer(pt)).json()["id"]
        s.add(AssessmentRequest(id="old-plumber-request", account_id=acc_id, trade="plumber", pincode="302017"))
        s.commit()
    assert client.post("/api/assessment-requests/old-plumber-request/start").status_code == 409


def test_plumber_assessment_uses_plumber_tasks_and_qualification(client):
    wid, pt = worker_with_profile(client, phone="9876500012", trade="plumber")
    client.post("/api/assessment-requests", json={"declaration_text": "Main 10 saal se nal aur pipe ka kaam karta hoon"},
                headers=bearer(pt))
    rid = client.get("/api/assessment-requests").json()[0]["id"]
    aid = client.post(f"/api/assessment-requests/{rid}/start").json()["assessment_id"]
    detail = client.get(f"/api/assessments/{aid}").json()
    assert detail["assessment"]["trade"] == "plumber" and detail["mapping"] is None  # M1 packs are electrical
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 13772, "actor": "A"}).status_code == 400
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 12957, "actor": "A"}).status_code == 200
    assert client.put(f"/api/assessments/{aid}/checklist",
                      json={"task_id": "t1_safe_isolation", "ticks": {"main_off": True}, "actor": "A"}).status_code == 422
    assert client.put(f"/api/assessments/{aid}/checklist",
                      json={"task_id": "p1_safe_preparation", "ticks": {"water_off": True}, "actor": "A"}).status_code == 200
    pre = client.get(f"/api/assessments/{aid}/prescores").json()
    assert pre and {p["task_id"][:2] for p in pre} == {"p1", "p2", "p3", "p4"}
    tasks = [t for t in client.get("/api/rubrics").json()["tasks"] if t["trade"] == "plumber"]
    for t in tasks:
        for c in t["criteria"]:
            r = client.post(f"/api/assessments/{aid}/decisions", json={
                "task_id": t["task_id"], "criterion_id": c["id"], "action": "override", "level": 3,
                "reason": "observed on the practice frame", "assessor": "A"})
            assert r.status_code == 200, r.text
    prof = client.get(f"/api/assessments/{aid}/profile").json()
    assert prof["recommendation"] == "recommend_for_certification" and prof["pass_mark"] == 0.7
    assert {n["nos"] for n in prof["nos"]} <= {"PSC/N0130", "PSC/N0131", "PSC/N0132", "PSC/N0133", "PSC/N0136",
                                                "PSC/N0142"}
    r = client.post(f"/api/assessments/{aid}/signoff", json={"agrees": True, "comment": "", "assessor": "A"})
    assert r.status_code == 200, r.text
    badge = client.get(f"/api/market/workers/{wid}").json()["badges"][0]
    assert badge["kind"] == "skill_assessed" and badge["qualification"]["title"] == "Plumber - General"
    packs = {p["nqr_id"]: p["trade"] for p in client.get("/api/packs").json()}
    assert packs[12957] == "plumber" and packs[9884] == "carpenter" and packs[13772] == "electrician"


def test_carpenter_profile_uses_the_nos_wise_pass_mark(client):
    _, ct = worker_with_profile(client, phone="9876500013", trade="carpenter")
    client.post("/api/assessment-requests", json={}, headers=bearer(ct))
    rid = client.get("/api/assessment-requests").json()[0]["id"]
    aid = client.post(f"/api/assessment-requests/{rid}/start").json()["assessment_id"]
    prof = client.get(f"/api/assessments/{aid}/profile").json()
    assert prof["nos_pass_mark"] == 0.7 and prof["recommendation"] == "incomplete"


def test_init_db_adds_the_trade_column_to_an_older_database(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'old.db'}"
    with create_engine(url).begin() as c:  # the assessment table as it was before trades
        c.execute(text("CREATE TABLE assessment (id VARCHAR PRIMARY KEY, worker_id VARCHAR, declaration_text VARCHAR, "
                       "mapping_json VARCHAR, confirmed_nqr_id INTEGER, status VARCHAR, is_sample BOOLEAN, "
                       "signoff_json VARCHAR, created_at DATETIME)"))
        c.execute(text("INSERT INTO assessment (id, worker_id, status, is_sample) VALUES ('old', 'w', 'in_progress', 0)"))
    monkeypatch.setenv("HUNAR_DB", url)
    db.reset_engine()
    try:
        db.init_db()
        db.init_db()  # running it again changes nothing
        with Session(db.engine()) as s:
            assert s.exec(text("SELECT trade FROM assessment WHERE id = 'old'")).one()[0] == "electrician"
    finally:
        db.reset_engine()
