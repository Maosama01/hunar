import base64

import cv2
import numpy as np
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session, text

from hunar.api import db
from hunar.api.models import AuditEntry


def jpeg(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    img = np.full((240, 320, 3), 200, np.uint8)
    for _ in range(12):
        x, y = rng.integers(0, 300, 2)
        cv2.rectangle(img, (int(x), int(y)), (int(x) + 40, int(y) + 30), [int(v) for v in rng.integers(0, 255, 3)], -1)
    return cv2.imencode(".jpg", img)[1].tobytes()


def new_assessment(client, code="W001", text="I do house wiring, lay conduit and fix switch boards and MCB."):
    w = client.post("/api/workers", json={"code": code}).json()
    return client.post("/api/assessments", json={"worker_id": w["id"], "declaration_text": text}).json()["id"]


def test_mapping_is_a_suggestion(client):
    r = client.post("/api/map", json={"text": "main solar panel aur inverter lagata hoon rooftop pe"}).json()
    assert r["ranking"][0]["nqr_id"] == 11371
    assert "Suggestion only" in r["note"]


def test_full_flow_requires_human_decisions_and_signoff(client):
    aid = new_assessment(client)
    # Picking a pack other than the top suggestion needs a reason.
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 9530, "actor": "A1"}).status_code == 422
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 13772, "actor": "A1"}).status_code == 200

    rub = client.get("/api/rubrics").json()["tasks"]
    for t in rub:
        ticks = {c["id"]: True for c in t["checklist"]}
        assert client.put(f"/api/assessments/{aid}/checklist",
                          json={"task_id": t["task_id"], "ticks": ticks, "actor": "A1"}).status_code == 200
    pre = client.get(f"/api/assessments/{aid}/prescores").json()
    assert all(p["suggested_level"] == 2 for p in pre)
    # No sign off before every criterion has a human decision.
    assert client.post(f"/api/assessments/{aid}/signoff", json={"assessor": "A1", "agrees": True}).status_code == 409

    for i, p in enumerate(pre):
        body = {"task_id": p["task_id"], "criterion_id": p["criterion_id"], "assessor": "A1"}
        if i % 3 == 0:  # some overrides upwards, with reasons
            body |= {"action": "override", "level": 3, "reason": "excellent, explained every step"}
        else:
            body |= {"action": "accept"}
        assert client.post(f"/api/assessments/{aid}/decisions", json=body).status_code == 200
    # Override without a reason is refused.
    bad = {"task_id": pre[0]["task_id"], "criterion_id": pre[0]["criterion_id"], "assessor": "A1",
           "action": "override", "level": 1}
    assert client.post(f"/api/assessments/{aid}/decisions", json=bad).status_code == 422

    prof = client.get(f"/api/assessments/{aid}/profile").json()
    assert prof["requires_assessor_signoff"] and prof["recommendation"] in ("not_yet_competent",
                                                                           "recommend_for_certification")
    r = client.post(f"/api/assessments/{aid}/signoff", json={"assessor": "A1", "agrees": True})
    assert r.status_code == 200 and r.json()["status"] == "signed_off"
    # Signed off assessments are frozen.
    assert client.put(f"/api/assessments/{aid}/checklist",
                      json={"task_id": "t1_safe_isolation", "ticks": {"ppe_gloves": False}, "actor": "A1"}).status_code == 409

    v = client.get("/api/audit/verify").json()
    assert v["ok"] and v["entries"] >= 30
    actions = {e["action"] for e in client.get("/api/audit?limit=500").json()}
    assert {"mapping.suggested", "pack.confirmed", "criterion.accept", "criterion.override",
            "assessment.signed_off"} <= actions


def test_disagreeing_signoff_needs_outcome_and_reason(client):
    aid = new_assessment(client)
    client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 13772, "actor": "A1"})
    for t in client.get("/api/rubrics").json()["tasks"]:
        for c in t["criteria"]:
            client.post(f"/api/assessments/{aid}/decisions",
                        json={"task_id": t["task_id"], "criterion_id": c["id"], "action": "override", "level": 3,
                              "reason": "observed directly", "assessor": "A1"})
    assert client.post(f"/api/assessments/{aid}/signoff", json={"assessor": "A1", "agrees": False}).status_code == 422
    r = client.post(f"/api/assessments/{aid}/signoff", json={"assessor": "A1", "agrees": False,
                                                              "outcome": "not_yet_competent",
                                                              "comment": "needs to repeat t5 under observation"})
    assert r.json()["signoff"]["assessor_outcome"] == "not_yet_competent"
    assert r.json()["signoff"]["tool_recommendation"] == "recommend_for_certification"


def test_evidence_needs_consent_and_reuse_is_flagged(client):
    a1, a2 = new_assessment(client, "W001"), new_assessment(client, "W002")
    files = {"file": ("p.jpg", jpeg(1), "image/jpeg")}
    form = {"task_id": "t2_switchboard_wiring", "photo_id": "p1"}
    assert client.post(f"/api/assessments/{a1}/evidence", data=form, files=files).status_code == 422
    r1 = client.post(f"/api/assessments/{a1}/evidence", data=form | {"consent_confirmed": "true"}, files=files).json()
    assert r1["duplicate_of"] is None and r1["detector_status"] in ("ok", "unavailable")
    # The same photo submitted for another worker is flagged for the assessor.
    r2 = client.post(f"/api/assessments/{a2}/evidence", data=form | {"consent_confirmed": "true"},
                     files={"file": ("p.jpg", jpeg(1), "image/jpeg")}).json()
    assert r2["duplicate_of"] == r1["id"]
    r3 = client.post(f"/api/assessments/{a2}/evidence", data=form | {"consent_confirmed": "true"},
                     files={"file": ("q.jpg", jpeg(99), "image/jpeg")}).json()
    assert r3["duplicate_of"] is None
    assert client.get(r1["image_url"]).status_code == 200


def test_offline_sync_applies_in_order_and_is_idempotent(client):
    ops = [
        {"op_id": "op-1", "kind": "worker.create", "payload": {"id": "w-local-1", "code": "W009"}},
        {"op_id": "op-2", "kind": "assessment.create",
         "payload": {"id": "a-local-1", "worker_id": "w-local-1", "declaration_text": "meter badalta hoon smart meter"}},
        {"op_id": "op-3", "kind": "checklist.set",
         "payload": {"assessment_id": "a-local-1", "task_id": "t1_safe_isolation", "ticks": {"ppe_gloves": True},
                     "actor": "F1"}},
        {"op_id": "op-4", "kind": "evidence.add",
         "payload": {"assessment_id": "a-local-1", "task_id": "t1_safe_isolation", "photo_id": "p1",
                     "consent_confirmed": True, "image_b64": base64.b64encode(jpeg(5)).decode()}},
    ]
    first = client.post("/api/sync", json={"ops": ops}).json()["results"]
    assert [r["status"] for r in first] == ["applied"] * 4
    again = client.post("/api/sync", json={"ops": ops}).json()["results"]
    assert [r["status"] for r in again] == ["duplicate"] * 4
    assert len(client.get("/api/workers").json()) == 1
    # A rejected op stops the batch so later dependent ops are not applied out of order.
    bad = [{"op_id": "op-5", "kind": "checklist.set",
            "payload": {"assessment_id": "missing", "task_id": "t1_safe_isolation", "ticks": {}, "actor": "F1"}},
           {"op_id": "op-6", "kind": "worker.create", "payload": {"code": "W010"}}]
    res = client.post("/api/sync", json={"ops": bad}).json()["results"]
    assert [r["status"] for r in res] == ["rejected"]


def test_audit_log_is_tamper_evident_and_append_only(client):
    new_assessment(client)
    with Session(db.engine()) as s:
        assert client.get("/api/audit/verify").json()["ok"]
        with pytest.raises((IntegrityError, OperationalError)):
            s.exec(text("UPDATE auditentry SET actor='mallory' WHERE seq=1"))
            s.commit()
        s.rollback()
        # Simulate an attacker who bypasses the trigger: the hash chain still exposes the edit.
        s.exec(text("DROP TRIGGER audit_no_update"))
        s.exec(text("UPDATE auditentry SET actor='mallory' WHERE seq=1"))
        s.commit()
        assert s.get(AuditEntry, 1).actor == "mallory"
    v = client.get("/api/audit/verify").json()
    assert v == {"ok": False, "entries": 1, "first_bad_seq": 1}


def test_study_order_is_random_but_reproducible(client):
    from hunar.api.models import StudyItem

    with Session(db.engine()) as s:
        for i in range(10):
            s.add(StudyItem(id=f"I{i}", image_path="x.jpg", task_id="t2_switchboard_wiring",
                            criterion_id="c2_termination", is_sample=False))
        s.commit()
    a = [r["item_id"] for r in client.get("/api/study/items", params={"rater_id": "R1", "condition": "unassisted"}).json()]
    b = [r["item_id"] for r in client.get("/api/study/items", params={"rater_id": "R1", "condition": "unassisted"}).json()]
    c = [r["item_id"] for r in client.get("/api/study/items", params={"rater_id": "R2", "condition": "unassisted"}).json()]
    assert a == b and sorted(a) == sorted(c) and a != c
    assisted = client.get("/api/study/items", params={"rater_id": "R1", "condition": "assisted"}).json()
    assert "anchors" in assisted[0] and "anchors" not in client.get(
        "/api/study/items", params={"rater_id": "R1", "condition": "unassisted"}).json()[0]
    ok = client.post("/api/study/ratings", json={"rater_id": "R1", "item_id": "I0", "condition": "unassisted",
                                                 "session": 1, "position": 0, "level": 2})
    assert ok.status_code == 200
    assert "R1,I0,unassisted,1,0,2" in client.get("/api/study/export").text


def test_fixes_from_frontend_integration(client):
    """Regression tests for the gaps the frontend integration found."""
    a1, a2 = new_assessment(client, "W001"), new_assessment(client, "W002")
    form = {"task_id": "t2_switchboard_wiring", "photo_id": "p1", "consent_confirmed": "true"}
    client.post(f"/api/assessments/{a1}/evidence", data=form, files={"file": ("p.jpg", jpeg(1), "image/jpeg")})
    r = client.post(f"/api/assessments/{a2}/evidence", data=form, files={"file": ("p.jpg", jpeg(1), "image/jpeg")}).json()
    assert isinstance(r["duplicate_distance"], int)

    # An unknown task or a missing field is a per-op rejection, not a 500 for the batch.
    ops = [{"op_id": "x1", "kind": "checklist.set",
            "payload": {"assessment_id": a1, "task_id": "no_such_task", "ticks": {}, "actor": "F"}}]
    assert client.post("/api/sync", json={"ops": ops}).json()["results"][0]["status"] == "rejected"
    ops = [{"op_id": "x2", "kind": "decision.add", "payload": {"assessment_id": a1}}]
    assert client.post("/api/sync", json={"ops": ops}).json()["results"][0]["status"] == "rejected"

    # Accept is refused if the suggestion changed since the assessor saw it.
    client.put(f"/api/assessments/{a1}/checklist",
               json={"task_id": "t4_joint_termination", "ticks": {"fully_insulated": True}, "actor": "A"})
    body = {"task_id": "t4_joint_termination", "criterion_id": "c3_insulate", "action": "accept", "assessor": "A"}
    assert client.post(f"/api/assessments/{a1}/decisions", json=body | {"expected_level": 1}).status_code == 409
    assert client.post(f"/api/assessments/{a1}/decisions", json=body | {"expected_level": 2}).status_code == 200

    # Audit paging.
    page1 = client.get("/api/audit", params={"limit": 3}).json()
    page2 = client.get("/api/audit", params={"limit": 3, "before_seq": page1[-1]["seq"]}).json()
    assert [e["seq"] for e in page2] == [page1[-1]["seq"] - k for k in (1, 2, 3)]


def test_rating_retry_is_idempotent(client):
    from hunar.api.models import StudyItem

    with Session(db.engine()) as s:
        s.add(StudyItem(id="I0", image_path="x.jpg", task_id="t2_switchboard_wiring", criterion_id="c2_termination"))
        s.commit()
    body = {"rater_id": "R1", "item_id": "I0", "condition": "assisted", "session": 1, "position": 0, "level": 2,
            "client_id": "c-123"}
    first = client.post("/api/study/ratings", json=body).json()
    again = client.post("/api/study/ratings", json=body).json()
    assert first["id"] == again["id"]
    assert client.get("/api/study/export").text.count("R1,I0") == 1
