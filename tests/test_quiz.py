import json
import random

import numpy as np
import pytest
from conftest import make_account
from sqlmodel import Session, select
from test_accounts import finish_quiz, register
from test_market import bearer, booking, customer, worker_with_profile

from hunar.api import db
from hunar.paths import DATA
from hunar.quiz import bank as banks
from hunar.quiz import engine
from hunar.quiz.models import QuizAttempt

# ---- engine maths -------------------------------------------------------------------------------


def test_eap_without_answers_is_the_prior():
    m, sd = engine.eap([])
    assert m == pytest.approx(0, abs=1e-9) and sd == pytest.approx(1, abs=0.01)


def test_eap_moves_with_answers_and_uncertainty_shrinks():
    up, sd_up = engine.eap([(0.0, True)] * 5)
    down, _ = engine.eap([(0.0, False)] * 5)
    assert up > 0.5 and down == pytest.approx(-up, abs=1e-9)
    _, sd_more = engine.eap([(0.0, True), (0.0, False)] * 10)
    assert sd_more < sd_up < 1


def test_eap_is_finite_for_all_correct():
    m, sd = engine.eap([(b, True) for b in np.linspace(-2, 2, 25)])
    assert np.isfinite(m) and m < 4 and sd > 0


def test_content_balancing_follows_weights():
    remaining = {"A": [(f"a{i}", 0.0) for i in range(10)], "B": [(f"b{i}", 0.0) for i in range(10)]}
    targets, counts, rng = {"A": 80, "B": 20}, {"A": 0, "B": 0}, random.Random(0)
    for _ in range(10):
        item = engine.choose_item(0.0, remaining, targets, counts, rng)
        nos = item[0].upper()
        counts[nos] += 1
        remaining[nos] = [x for x in remaining[nos] if x[0] != item]
    assert counts == {"A": 8, "B": 2}


def test_selection_prefers_items_near_theta():
    remaining = {"A": [("easy", -2.0), ("mid", 0.1), ("hard", 2.0), ("vhard", 3.0)]}
    picks = {engine.choose_item(0.0, remaining, {"A": 1}, {}, random.Random(i), engine.Rules(top_k=1))
             for i in range(20)}
    assert picks == {"mid"}


def test_selection_returns_none_when_bank_empty():
    assert engine.choose_item(0.0, {"A": []}, {"A": 1}, {}, random.Random(0)) is None


def test_stopping_rules():
    r = engine.Rules(min_items=12, max_items=25, se_target=0.5)
    assert not engine.should_stop(11, 11, 0.3, 10, r)  # below the minimum
    assert engine.should_stop(12, 12, 0.49, 10, r)
    assert not engine.should_stop(12, 12, 0.6, 10, r)
    assert engine.should_stop(5, 25, 0.9, 10, r)  # cap reached
    assert engine.should_stop(3, 3, 0.9, 0, r)  # bank exhausted


def test_rapid_flag_scales_with_question_length():
    assert engine.is_rapid(2.5, 10) and not engine.is_rapid(3.5, 10) and engine.is_rapid(3.5, 20)
    assert not engine.is_rapid(None, 10)


@pytest.mark.parametrize("scored, answered, ok", [(0, 0, False), (0, 25, False), (12, 25, False), (13, 25, True),
                                                  (5, 10, True), (4, 10, False), (25, 25, True)])
def test_quiz_counts_only_when_at_least_half_read(scored, answered, ok):
    assert engine.counts(scored, answered) is ok


def test_expected_percent_is_monotonic():
    bs = [-1.0, 0.0, 1.0]
    assert engine.expected_percent(-2, bs) < engine.expected_percent(0, bs) < engine.expected_percent(2, bs)
    s = engine.summary(0.0, 0.5, bs)
    lo, hi = s["expected_percent_interval90"]
    assert lo < s["expected_percent"] < hi


# ---- bank integrity -----------------------------------------------------------------------------


@pytest.mark.parametrize("trade", banks.trades())
def test_bank_is_valid_and_balanced(trade):
    b = banks.load(trade)
    assert len(b.items) >= 20 and b.status.startswith("DRAFT")
    for code in b.nos:
        assert b.nos[code]["title"]["en"] and b.nos[code]["title"]["hi"]
    used = {it.nos for it in b.items}
    assert used == set(b.nos), f"NOS without items: {set(b.nos) - used}"
    for it in b.items:
        assert len({o.en for o in it.options}) == len(it.options), f"{it.id}: duplicate options"


@pytest.mark.parametrize("trade", banks.trades())
def test_bank_nos_and_pcs_exist_in_official_qualification(trade):
    b = banks.load(trade)
    if b.qualification_nqr_id is None:
        pytest.skip("qualification file not added yet")
    qp = json.loads((DATA / "processed" / "qp" / f"{b.qualification_nqr_id}.json").read_text())
    codes = {n["code"] for n in qp["nos"]}
    pcs = {pc["id"] for n in qp["nos"] for pc in n["performance_criteria"]}
    assert set(b.nos) <= codes
    for it in b.items:
        assert set(it.pc_refs) <= pcs, f"{it.id}: unknown PCs {set(it.pc_refs) - pcs}"


def test_electrician_bank_never_claims_a_5kw_rcd_threshold():
    text = (banks.BANKS / "electrician.yaml").read_text()
    assert "5 kW" not in text and "5kW" not in text  # dropped from the 2023 regulations


# ---- API ----------------------------------------------------------------------------------------


def _take_quiz(client, token, choose):
    r = client.post("/api/quiz/attempts", json={"trade": "electrician", "language": "en"}, headers=bearer(token))
    assert r.status_code == 200, r.text
    aid, item = r.json()["attempt_id"], r.json()["item"]
    seen = []
    for _ in range(60):
        seen.append(item)
        res = client.post(f"/api/quiz/attempts/{aid}/answers", json={"item_id": item["id"], "choice": choose(item),
                                                                   "seconds": 30}, headers=bearer(token)).json()
        if res["done"]:
            return aid, seen, res["result"]
        item = res["item"]
    raise AssertionError("quiz did not stop")


def _right_choice(item):
    it = banks.load("electrician").item(item["id"])
    return item["options"].index(it.options[it.answer].en)


def test_quiz_needs_assessment_consent(client):
    # Required for workers since the quiz became compulsory, so registration refuses to go without it ...
    assert register(client, consents={"account": True, "contact_share": True}).status_code == 422
    # ... and an older worker account without it is sent to give it before the quiz.
    _, tok = make_account(role="worker", phone="9876500002")
    assert client.get("/api/auth/me", headers=bearer(tok)).json()["quiz"]["done"] is False
    r = client.post("/api/quiz/attempts", json={"trade": "electrician"}, headers=bearer(tok))
    assert r.status_code == 409
    assert client.post("/api/auth/consents", json={"purpose": "assessment", "granted": True},
                       headers=bearer(tok)).status_code == 200
    assert client.post("/api/quiz/attempts", json={"trade": "electrician"}, headers=bearer(tok)).status_code == 200


def test_quiz_flow_scoring_and_review(client):
    _, tok = worker_with_profile(client)
    aid, seen, high = _take_quiz(client, tok, _right_choice)
    assert engine.DEFAULT_RULES.min_items <= high["n_answered"] <= engine.DEFAULT_RULES.max_items
    assert "answer" not in json.dumps(seen[0]).lower().replace("answers", "")  # no key sent to the client
    assert len({it["id"] for it in seen}) == len(seen)
    assert {_right_choice(it) for it in seen} != {0}  # options are shuffled
    assert high["expected_percent_interval90"][0] < high["expected_percent"] < high["expected_percent_interval90"][1]
    assert "not a certificate" in high["note"] and high["bank"]["calibrated"] is False
    weights = {n["nos"]: n["answered"] for n in high["by_nos"]}
    assert weights["CON/N0604"] >= weights["CON/N8001"]
    review = client.get(f"/api/quiz/attempts/{aid}/review", headers=bearer(tok)).json()
    assert all(r["correct"] and r["your_choice"] == r["answer"] for r in review) and review[0]["sources"]
    _, _, low = _take_quiz(client, tok, lambda it: None)  # "don't know" to everything
    assert low["theta"] < high["theta"] and low["n_dont_know"] == low["n_answered"]
    assert any(n["nos"] == "CON/N0604" for n in low["revise"])


def test_rapid_answers_are_flagged_not_scored(client):
    _, tok = worker_with_profile(client)
    r = client.post("/api/quiz/attempts", json={"trade": "electrician", "language": "hi"}, headers=bearer(tok)).json()
    item = r["item"]
    assert item["language"] == "hi"
    res = client.post(f"/api/quiz/attempts/{r['attempt_id']}/answers",
                      json={"item_id": item["id"], "choice": 0, "seconds": 0.5}, headers=bearer(tok)).json()
    assert res["rapid_warning"] is True
    state = client.get("/api/quiz/attempts", headers=bearer(tok)).json()[0]
    assert state["n_answered"] == 1


def test_wrong_item_and_foreign_attempt_are_refused(client):
    _, tok = worker_with_profile(client)
    r = client.post("/api/quiz/attempts", json={"trade": "electrician"}, headers=bearer(tok)).json()
    bad = client.post(f"/api/quiz/attempts/{r['attempt_id']}/answers", json={"item_id": "el-999", "choice": 0},
                      headers=bearer(tok))
    assert bad.status_code == 409
    _, other = worker_with_profile(client, phone="9876500001")
    assert client.get(f"/api/quiz/attempts/{r['attempt_id']}", headers=bearer(other)).status_code == 404


def test_machine_translation_falls_back_and_is_labelled(client):
    _, tok = worker_with_profile(client)
    item = client.post("/api/quiz/attempts", json={"trade": "electrician", "language": "sat"},
                       headers=bearer(tok)).json()["item"]
    assert item["translation"] in ("machine", "reviewed", "missing")
    if item["translation"] == "missing":
        assert item["language"] == "hi"


def test_quiz_results_go_to_assessors_not_customers(client):
    wid, tok = worker_with_profile(client)
    _take_quiz(client, tok, _right_choice)
    assert "theta" not in json.dumps(client.get(f"/api/market/workers/{wid}").json())
    client.post("/api/assessment-requests", json={}, headers=bearer(tok))
    req = client.get("/api/assessment-requests").json()[0]  # assessor view
    assert req["quiz"]["attempts_finished"] == 2  # the one taken at registration, then this one
    # The quiz is part of every worker account: stopping it means erasing the account, which deletes the answers.
    assert client.post("/api/auth/consents", json={"purpose": "assessment", "granted": False},
                       headers=bearer(tok)).status_code == 409
    client.delete("/api/auth/me", headers=bearer(tok))
    with Session(db.engine()) as s:
        assert s.exec(select(QuizAttempt).where(QuizAttempt.account_id == wid)).all() == []


# ---- the quiz is compulsory for workers and comes straight after registering --------------------


def test_worker_registration_needs_a_trade_and_starts_the_quiz(client):
    assert register(client, trade=None).status_code == 422
    assert register(client, trade="welder").status_code == 422
    assert register(client, phone="9988776655", role="customer", trade="plumber").status_code == 422
    config = client.get("/api/auth/config").json()
    assert config["purposes"]["worker"]["assessment"]["required"] is True
    r = register(client, trade="plumber").json()
    first = r["quiz"]
    assert first["item"]["position"] == 1 and first["item"]["language"] == "hi"
    assert r["account"]["quiz"] == {"done": False, "counted_trades": [],
                                    "in_progress": {"attempt_id": first["attempt_id"], "trade": "plumber"}}
    login = client.post("/api/auth/login", json={"phone": "9876501234", "pin": "482913"}).json()
    assert login["account"]["quiz"]["in_progress"]["attempt_id"] == first["attempt_id"]  # comes back to it
    assert "quiz" not in customer_account(client)


def customer_account(client):
    tok = customer(client)
    return client.get("/api/auth/me", headers=bearer(tok)).json()


def test_nothing_else_until_the_quiz_is_finished(client):
    tok = register(client).json()["token"]
    profile = {"trade": "electrician", "years_experience": 4, "pincode": "302017"}
    r = client.put("/api/me/profile", json=profile, headers=bearer(tok))
    assert r.status_code == 409 and "quiz" in r.json()["detail"]
    assert client.post("/api/assessment-requests", json={}, headers=bearer(tok)).status_code == 409
    finish_quiz(client, tok)  # "don't know" throughout: the result does not matter, finishing does
    gate = client.get("/api/auth/me", headers=bearer(tok)).json()["quiz"]
    assert gate == {"done": True, "counted_trades": ["electrician"], "in_progress": None}
    assert client.put("/api/me/profile", json=profile, headers=bearer(tok)).status_code == 200
    assert client.post("/api/assessment-requests", json={}, headers=bearer(tok)).status_code == 200
    # A new trade needs that trade's quiz first.
    assert client.put("/api/me/profile", json={**profile, "trade": "plumber"}, headers=bearer(tok)).status_code == 409
    finish_quiz(client, tok, trade="plumber")
    assert client.put("/api/me/profile", json={**profile, "trade": "plumber"}, headers=bearer(tok)).status_code == 200


def test_a_rushed_quiz_does_not_count(client):
    tok = register(client).json()["token"]
    rushed = finish_quiz(client, tok, seconds=0.5)  # every answer faster than reading time
    assert rushed["status"] == "finished" and rushed["counts"] is False and rushed["read_share"] == 0
    assert rushed["n_answered"] == engine.DEFAULT_RULES.max_items and rushed["n_scored"] == 0
    gate = client.get("/api/auth/me", headers=bearer(tok)).json()["quiz"]
    assert gate == {"done": False, "counted_trades": [], "in_progress": None}
    profile = {"trade": "electrician", "years_experience": 4, "pincode": "302017"}
    r = client.put("/api/me/profile", json=profile, headers=bearer(tok))
    assert r.status_code == 409 and "rushed" in r.json()["detail"]
    again = finish_quiz(client, tok, trade="electrician")  # taken again at reading pace
    assert again["counts"] is True and again["read_share"] == 1
    assert client.get("/api/auth/me", headers=bearer(tok)).json()["quiz"]["done"] is True
    assert client.put("/api/me/profile", json=profile, headers=bearer(tok)).status_code == 200
    client.post("/api/assessment-requests", json={}, headers=bearer(tok))
    summary = client.get("/api/assessment-requests").json()[0]["quiz"]  # assessor view
    assert summary["attempt_id"] == again["attempt_id"] and summary["attempts_not_counted"] == 1


@pytest.mark.parametrize("how", ["unfinished", "rushed"])
def test_workers_without_a_counted_quiz_are_not_listed_or_bookable(client, how):
    wid, _ = worker_with_profile(client)
    ct = customer(client)
    assert [w["account_id"] for w in client.get("/api/market/workers").json()] == [wid]
    with Session(db.engine()) as s:  # e.g. an older profile saved before the quiz was compulsory
        for a in s.exec(select(QuizAttempt).where(QuizAttempt.account_id == wid)):
            if how == "unfinished":
                a.status = "in_progress"
            else:
                a.n_scored = a.n_answered // 2 - 1
            s.add(a)
        s.commit()
    assert client.get("/api/market/workers").json() == []
    assert client.get(f"/api/market/workers/{wid}").status_code == 404
    assert client.post("/api/bookings", json=booking(wid), headers=bearer(ct)).status_code == 404


# ---- calibration (simulated responses, tests only) --------------------------------------------


def test_calibration_recovers_difficulties_from_simulated_answers():
    from hunar.quiz.calibrate import fit_difficulties

    rng = np.random.default_rng(0)
    true_b = {f"i{k}": float(b) for k, b in enumerate(np.linspace(-1.5, 1.5, 8))}
    priors = dict.fromkeys(true_b, 0.0)  # deliberately uninformative starting point
    responses = []
    for p in range(400):
        th = rng.normal()
        for item, b in true_b.items():
            responses.append((f"p{p}", item, bool(rng.random() < engine.p_correct(th, b))))
    fitted, counts = fit_difficulties(responses, priors)
    err = np.array([fitted[k] - true_b[k] for k in true_b])
    # Priors and EAP both shrink extremes towards the middle, so the hardest item is recovered least well.
    assert np.abs(err).mean() < 0.2 and np.abs(err).max() < 0.5 and counts["i0"] == 400
    order_true = sorted(true_b, key=true_b.get)
    assert sorted(fitted, key=fitted.get) == order_true


def test_calibration_keeps_prior_for_items_with_few_answers():
    from hunar.quiz.calibrate import fit_difficulties

    fitted, _ = fit_difficulties([("p1", "a", True), ("p2", "a", False)], {"a": 1.2, "b": -0.4})
    assert fitted == {"a": 1.2, "b": -0.4}


def test_calibration_is_pending_without_real_data(client):
    from sqlmodel import Session

    from hunar.api import db
    from hunar.quiz.calibrate import calibrate

    with Session(db.engine()) as s:
        res = calibrate("electrician", s)
    assert res["status"] == "RESULT PENDING" and res["n_attempts"] == 0 and res["data_kind"] == "real"


def test_calibration_leaves_out_rushed_quizzes(client):
    from hunar.quiz.calibrate import calibrate

    finish_quiz(client, register(client).json()["token"])
    finish_quiz(client, register(client, phone="9876500003").json()["token"], seconds=0.5)
    with Session(db.engine()) as s:
        assert calibrate("electrician", s)["n_attempts"] == 1
