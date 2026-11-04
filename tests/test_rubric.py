import pytest

from hunar.mapper.mapper import load_packs
from hunar.paths import DATA
from hunar.rubric.engine import (
    PASS_RULES,
    DeclarationMatch,
    Detection,
    aggregate,
    get_task,
    load_tasks,
    pass_rules,
    prescore_task,
    tasks_for,
)
from hunar.schemas import QualificationPack

TRADES = ["electrician", "plumber", "carpenter"]


def all_levels(level, tasks=None):
    tasks = tasks or tasks_for("electrician")
    return {(t.task_id, c.id): level for t in tasks for c in t.criteria}


# ---- Rubric files ----------------------------------------------------------------------------


@pytest.mark.parametrize("trade", TRADES)
def test_between_four_and_six_tasks_with_anchored_levels(trade):
    tasks = tasks_for(trade)
    assert 4 <= len(tasks) <= 6
    assert len({t.qualification_nqr_id for t in tasks}) == 1, "one qualification file per trade"
    for t in tasks:
        assert t.title.hi and t.instructions.hi and t.review and t.review.hi
        assert any(c.critical for c in t.criteria), f"{t.task_id} has no safety-critical criterion"
    if trade != "electrician":
        assert all("DRAFT" in t.review.en for t in tasks), "AI-drafted rubrics must say so"


def test_task_ids_are_unique_across_trades():
    ids = [t.task_id for t in load_tasks()]
    assert len(ids) == len(set(ids)) and {t.trade for t in load_tasks()} == set(TRADES)


def test_every_pc_reference_exists_in_the_official_pack():
    packs = {p.nqr_id: p for p in load_packs()}
    for nqr in (12957, 9884):  # the plumber and carpenter files are not M1 packs
        packs[nqr] = QualificationPack.model_validate_json((DATA / "processed" / "qp" / f"{nqr}.json").read_text())
    for t in load_tasks():
        pc_ids = {pc.id for _, pc in packs[t.qualification_nqr_id].criteria()}
        nos_codes = {n.code for n in packs[t.qualification_nqr_id].nos}
        for c in t.criteria:
            assert c.nos in nos_codes, f"{t.task_id}.{c.id}: unknown NOS {c.nos}"
            for ref in c.pc_refs:
                assert ref in pc_ids, f"{t.task_id}.{c.id}: {ref} is not a PC of the official pack"


# ---- Pre scores ------------------------------------------------------------------------------


def test_prescore_levels_from_checklist():
    t = get_task("t2_switchboard_wiring")
    none = {s.criterion_id: s.suggested_level for s in prescore_task(t, checklist={i.id: False for i in t.checklist})}
    allt = {s.criterion_id: s.suggested_level for s in prescore_task(t, checklist={i.id: True for i in t.checklist})}
    assert set(none.values()) == {0}
    assert set(allt.values()) == {2}, "the engine never suggests level 3"
    some = prescore_task(t, checklist={"switch_in_phase": True, "socket_polarity": False, "colour_code": False})
    polarity = next(s for s in some if s.criterion_id == "c3_polarity")
    assert polarity.suggested_level == 1
    assert any("not ticked" in r for r in polarity.reasons)


def test_no_evidence_means_no_suggestion():
    t = get_task("t5_testing_fault_finding")
    for s in prescore_task(t):
        assert s.suggested_level is None and s.confidence == "none"


def test_photo_detection_reason_and_photo_only_suggestion():
    t = get_task("t1_safe_isolation")
    det = [Detection(photo_id="p1", cls="gloves", confidence=0.91),
           Detection(photo_id="p1", cls="safety_shoes", confidence=0.66)]
    ppe = next(s for s in prescore_task(t, detections=det) if s.criterion_id == "c1_ppe")
    assert ppe.suggested_level == 2 and ppe.confidence == "low"
    assert "gloves detected in photo p1, confidence 0.91" in ppe.reasons


def test_low_confidence_detections_are_ignored_and_conflict_flagged():
    t = get_task("t1_safe_isolation")
    det = [Detection(photo_id="p2", cls="gloves", confidence=0.30)]
    ppe = next(s for s in prescore_task(t, checklist={"ppe_gloves": True, "ppe_shoes": True}, detections=det)
               if s.criterion_id == "c1_ppe")
    assert ppe.conflict and ppe.confidence == "low" and ppe.suggested_level == 2


def test_checklist_and_photos_agree_gives_high_confidence():
    t = get_task("t1_safe_isolation")
    det = [Detection(photo_id="p1", cls="gloves", confidence=0.9), Detection(photo_id="p1", cls="safety_shoes", confidence=0.8)]
    ppe = next(s for s in prescore_task(t, checklist={"ppe_gloves": True, "ppe_shoes": True}, detections=det)
               if s.criterion_id == "c1_ppe")
    assert ppe.confidence == "high" and not ppe.conflict


def test_declaration_is_context_only():
    t = get_task("t5_testing_fault_finding")
    decl = {"CON/N0602.PC8": DeclarationMatch(pc_id="CON/N0602.PC8", sentence="I use a megger", similarity=0.8)}
    s = next(p for p in prescore_task(t, declaration_pc_scores=decl) if p.criterion_id == "c3_insulation")
    assert s.suggested_level is None
    assert any("context only" in r for r in s.reasons)


# ---- Aggregation -----------------------------------------------------------------------------


def test_all_competent_recommends_for_assessor_review():
    p = aggregate(all_levels(2))
    assert p.overall == pytest.approx(2 / 3, abs=1e-4)
    assert p.recommendation == "not_yet_competent", "2/3 = 66.7% is below the official 70% pass mark"
    p3 = aggregate(all_levels(3))
    assert p3.overall == 1.0 and p3.recommendation == "recommend_for_certification"
    assert p3.requires_assessor_signoff


def test_all_zero():
    p = aggregate(all_levels(0))
    assert p.overall == 0.0 and p.recommendation == "not_yet_competent"
    assert len(p.critical_failures) == sum(c.critical for t in tasks_for("electrician") for c in t.criteria)


def test_exactly_at_pass_mark_passes():
    t = get_task("t4_joint_termination")
    # weights 1,1,2,1 -> levels 3,3,2,1 give (1 + 1 + 2*2/3 + 1/3) / 5 = 0.7333
    levels = {("t4_joint_termination", "c1_strip"): 3, ("t4_joint_termination", "c2_joint"): 3,
              ("t4_joint_termination", "c3_insulate"): 2, ("t4_joint_termination", "c4_tools"): 1}
    p = aggregate(levels, tasks=[t], pass_mark=0.7333)
    assert p.overall == pytest.approx(0.7333)
    assert p.recommendation == "recommend_for_certification"
    assert aggregate(levels, tasks=[t], pass_mark=0.74).recommendation == "not_yet_competent"


def test_critical_failure_blocks_positive_recommendation():
    levels = all_levels(3)
    levels[("t1_safe_isolation", "c3_test_dead")] = 1
    p = aggregate(levels)
    assert p.overall > 0.9
    assert p.recommendation == "not_yet_competent"
    assert [g.criterion_id for g in p.critical_failures] == ["c3_test_dead"]


def test_unscored_criteria_make_profile_incomplete():
    levels = all_levels(3)
    levels[("t2_switchboard_wiring", "c5_workmanship")] = None
    p = aggregate(levels)
    assert p.recommendation == "incomplete" and p.unscored == ["t2_switchboard_wiring.c5_workmanship"]


def test_weights_and_nos_scores():
    t = get_task("t4_joint_termination")
    levels = {("t4_joint_termination", c.id): 0 for c in t.criteria}
    levels[("t4_joint_termination", "c3_insulate")] = 3  # weight 2, NOS CON/N0603
    p = aggregate(levels, tasks=[t])
    assert p.overall == pytest.approx(2 / 5, abs=1e-4)
    nos = {n.nos: n.score for n in p.nos}
    assert nos["CON/N0603"] == pytest.approx(2 / 3, abs=1e-4)  # c2 (w1, level 0) + c3 (w2, level 3)
    assert nos["CON/N0602"] == 0.0


@pytest.mark.parametrize("bad", [-1, 4, 2.5])
def test_invalid_level_rejected(bad):
    with pytest.raises(ValueError):
        aggregate({("t4_joint_termination", "c1_strip"): bad})


@pytest.mark.parametrize("pm", [0, -0.1, 1.5])
def test_invalid_pass_mark_rejected(pm):
    with pytest.raises(ValueError):
        aggregate(all_levels(2), pass_mark=pm)


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        aggregate({})


# ---- Pass rules from each qualification file ------------------------------------------------------


def test_pass_rules_come_from_the_qualification_files():
    assert pass_rules(13772) == (0.70, None) and pass_rules(12957) == (0.70, None)
    assert pass_rules(9884) == (0.70, 0.70)  # the carpenter file also sets 70 % per NOS
    assert set(PASS_RULES) == {t.qualification_nqr_id for t in load_tasks()}


def _carpenter_levels(level, nos=None, nos_level=None):
    tasks = tasks_for("carpenter")
    return tasks, {(t.task_id, c.id): (nos_level if c.nos == nos else level) for t in tasks for c in t.criteria}


def test_nos_pass_mark_blocks_when_one_nos_is_low():
    tasks, levels = _carpenter_levels(3)
    # Drop every criterion of the bench-setup NOS to level 2 (66.7 %): overall stays well above 70 %.
    tasks, levels = _carpenter_levels(3, nos="FFS/N2206", nos_level=2)
    p = aggregate(levels, tasks=list(tasks), pass_mark=0.70, nos_pass_mark=0.70)
    assert p.overall > 0.9 and p.recommendation == "not_yet_competent"
    assert "FFS/N2206" in p.explanation and p.nos_pass_mark == 0.70
    assert aggregate(levels, tasks=list(tasks), pass_mark=0.70).recommendation == "recommend_for_certification"


def test_nos_pass_mark_met_everywhere_recommends():
    tasks, levels = _carpenter_levels(3)
    p = aggregate(levels, tasks=list(tasks), pass_mark=0.70, nos_pass_mark=0.70)
    assert p.recommendation == "recommend_for_certification" and "every NOS" in p.explanation


@pytest.mark.parametrize("bad", [0.0, 1.2, -0.1])
def test_invalid_nos_pass_mark_rejected(bad):
    with pytest.raises(ValueError):
        aggregate(all_levels(2), nos_pass_mark=bad)
