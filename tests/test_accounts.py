import json

import pytest
from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.api import db
from hunar.api.models import AuditEntry

WORKER_CONSENTS = {"account": True, "contact_share": True, "assessment": True, "profile_display": True}


def register(client, phone="9876501234", role="worker", pin="482913", **kw):
    body = {"phone": phone, "pin": pin, "role": role, "display_name": "Ramesh", "language": "hi", "is_adult": True,
            "consents": WORKER_CONSENTS if role == "worker" else {"account": True, "contact_share": True},
            **({"trade": "electrician"} if role == "worker" else {}), **kw}
    return client.post("/api/auth/register", json=body, headers={"Authorization": ""})


def finish_quiz(client, token, trade=None, choice=None):
    """Answer a worker's quiz to the end ("don't know" by default): the open one, or a new one in `trade`."""
    h = {"Authorization": f"Bearer {token}"}
    if trade:
        aid = client.post("/api/quiz/attempts", json={"trade": trade}, headers=h).json()["attempt_id"]
    else:
        aid = client.get("/api/auth/me", headers=h).json()["quiz"]["in_progress"]["attempt_id"]
    state = client.get(f"/api/quiz/attempts/{aid}", headers=h).json()
    while not state["done"]:
        state = client.post(f"/api/quiz/attempts/{aid}/answers", headers=h,
                            json={"item_id": state["item"]["id"], "choice": choice, "seconds": 30}).json()
    return state["result"]


@pytest.mark.parametrize("raw, want", [("9876501234", "+919876501234"), ("+91 98765-01234", "+919876501234"),
                                       ("09876501234", "+919876501234"), ("919876501234", "+919876501234")])
def test_phone_normalisation(raw, want):
    assert auth.normalise_phone(raw) == want


@pytest.mark.parametrize("raw", ["12345", "5876501234", "98765012345", "abc"])
def test_bad_phone_numbers(raw):
    with pytest.raises(ValueError):
        auth.normalise_phone(raw)


@pytest.mark.parametrize("pin, ok", [("482913", True), ("4829", True), ("1111", False), ("1234", False),
                                     ("654321", False), ("12a4", False), ("123", False), ("1234567", False)])
def test_pin_rules(pin, ok):
    assert (auth.pin_problem(pin) is None) == ok


def test_pin_may_not_be_end_of_phone():
    assert "phone" in auth.pin_problem("501234", "+919876501234")


def test_register_login_logout(client):
    r = register(client)
    assert r.status_code == 200, r.text
    token, acc = r.json()["token"], r.json()["account"]
    assert acc["role"] == "worker" and acc["phone_masked"].endswith("234") and "98765" not in acc["phone_masked"]
    assert acc["consents"] == WORKER_CONSENTS
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["display_name"] == "Ramesh"
    assert register(client).status_code == 409
    login = client.post("/api/auth/login", json={"phone": "98765 01234", "pin": "482913"})
    assert login.status_code == 200
    t2 = login.json()["token"]
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {t2}"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t2}"}).status_code == 401


def test_register_needs_adult_required_consents_and_good_pin(client):
    assert register(client, is_adult=False).status_code == 422
    assert register(client, consents={"account": True}).status_code == 422  # contact_share is required
    assert register(client, pin="1234").status_code == 422
    assert register(client, role="assessor").status_code == 422  # staff cannot self-register
    assert register(client, consents={**WORKER_CONSENTS, "marketing": True}).status_code == 422


def test_lockout_after_five_wrong_pins(client):
    register(client)
    for _ in range(auth.MAX_FAILED):
        assert client.post("/api/auth/login", json={"phone": "9876501234", "pin": "000999"}).status_code == 401
    assert client.post("/api/auth/login", json={"phone": "9876501234", "pin": "482913"}).status_code == 429


def test_unknown_phone_and_wrong_pin_look_the_same(client):
    register(client)
    a = client.post("/api/auth/login", json={"phone": "9876501234", "pin": "999888"})
    b = client.post("/api/auth/login", json={"phone": "9123456780", "pin": "999888"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_pin_is_hashed_with_salt_and_pepper(client):
    h1, h2 = auth.hash_pin("482913"), auth.hash_pin("482913")
    assert h1 != h2 and "482913" not in h1 and auth.verify_pin("482913", h1) and not auth.verify_pin("482914", h1)


def test_staff_endpoints_need_staff_login(client):
    assert client.get("/api/assessments", headers={"Authorization": ""}).status_code == 401
    token = register(client).json()["token"]
    assert client.get("/api/assessments", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/api/audit", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/api/assessments").status_code == 200  # default client is an assessor


def test_audit_log_holds_no_phone_numbers(client):
    register(client)
    with Session(db.engine()) as s:
        blob = json.dumps([e.model_dump() for e in s.exec(select(AuditEntry))])
    assert "9876501234" not in blob and "Ramesh" not in blob


def test_consent_withdrawal_and_erasure(client):
    token = register(client).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/auth/consents", json={"purpose": "profile_display", "granted": False}, headers=h)
    assert r.status_code == 200 and r.json()["consents"]["profile_display"] is False
    assert client.post("/api/auth/consents", json={"purpose": "account", "granted": False}, headers=h).status_code == 409
    assert client.delete("/api/auth/me", headers=h).json() == {"erased": True}
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"phone": "9876501234", "pin": "482913"}).status_code == 401
    assert register(client).status_code == 200  # the number can register again after erasure


def test_otp_flow_when_provider_configured(client, monkeypatch):
    monkeypatch.setenv("HUNAR_OTP_PROVIDER", "test")
    assert client.get("/api/auth/config").json()["otp_required"] is True
    assert register(client).status_code == 422  # no code
    ch = client.post("/api/auth/otp", json={"phone": "9876501234", "purpose": "register"}).json()
    assert "TEST MODE" in ch["test_note"]
    assert register(client, otp_challenge_id=ch["challenge_id"], otp_code="000000" if ch["test_code"] != "000000"
                    else "111111").status_code == 422
    r = register(client, otp_challenge_id=ch["challenge_id"], otp_code=ch["test_code"])
    assert r.status_code == 200 and r.json()["account"]["phone_verified"] is True
    reset = client.post("/api/auth/otp", json={"phone": "9876501234", "purpose": "reset"}).json()
    assert client.post("/api/auth/reset-pin", json={"phone": "9876501234", "new_pin": "730591", "otp_challenge_id":
                                                    reset["challenge_id"], "otp_code": reset["test_code"]}).status_code == 200
    assert client.post("/api/auth/login", json={"phone": "9876501234", "pin": "730591"}).status_code == 200


def test_reset_without_provider_points_to_admin(client):
    r = client.post("/api/auth/reset-pin", json={"phone": "9876501234", "new_pin": "730591", "otp_challenge_id": "x",
                                                 "otp_code": "1"})
    assert r.status_code == 409 and "admin" in r.json()["detail"]
