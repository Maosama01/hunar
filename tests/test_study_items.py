import json

import cv2
import numpy as np
import pytest
from sqlmodel import Session, select

from hunar.api import db, services
from hunar.api.models import AuditEntry, StudyItem, StudyRating
from hunar.audit import log as audit
from hunar.study import items


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("HUNAR_DB", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(services, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(items, "DATA", tmp_path)
    db.reset_engine()
    (tmp_path / "photos").mkdir()
    for k in range(3):
        img = np.full((120, 160, 3), 60 * k, np.uint8)
        cv2.imwrite(str(tmp_path / "photos" / f"E0{k + 1}.jpg"), img)
    yield tmp_path
    db.reset_engine()


def write_csv(folder, rows):
    p = folder / "items.csv"
    p.write_text("item_id,photo,task_id,criterion_id,consent_ref,ticked\n" + "\n".join(rows) + "\n")
    return p


def test_import_stores_blurred_copy_prescore_and_audit(env):
    csv_path = write_csv(env, ["E01,photos/E01.jpg,t1_safe_isolation,c1_ppe,CF-001,ppe_gloves;ppe_shoes",
                               "E02,photos/E02.jpg,t1_safe_isolation,c1_ppe,CF-002,ppe_gloves",
                               "E03,photos/E03.jpg,t1_safe_isolation,c1_ppe,CF-003,"])
    assert items.main([str(csv_path)]) == 0
    with Session(db.engine()) as s:
        got = {i.id: i for i in s.exec(select(StudyItem))}
        assert set(got) == {"E01", "E02", "E03"} and not any(i.is_sample for i in got.values())
        levels = {k: json.loads(v.prescore_json)["suggested_level"] for k, v in got.items()}
        assert levels["E01"] == 2 and levels["E02"] == 1  # checklist drives the level, never 3
        assert levels["E03"] is None  # no checklist and no detector: the rater sees "not enough evidence"
        assert (env / got["E01"].image_path).is_file() and got["E01"].image_path.startswith("uploads/study/")
        log = s.exec(select(AuditEntry).where(AuditEntry.action == "study.item_added")).all()
        assert len(log) == 3 and json.loads(log[0].payload_json)["consent_ref"] == "CF-001"
        assert audit.verify(s)["ok"]


@pytest.mark.parametrize("row, msg", [
    ("E01,photos/E01.jpg,t1_safe_isolation,c1_ppe,,", "consent_ref"),
    ("E01,photos/missing.jpg,t1_safe_isolation,c1_ppe,CF-1,", "photo not found"),
    ("E01,photos/E01.jpg,t9_nope,c1_ppe,CF-1,", "unknown task_id"),
    ("E01,photos/E01.jpg,t1_safe_isolation,c9_nope,CF-1,", "not a criterion"),
    ("E01,photos/E01.jpg,t1_safe_isolation,c1_ppe,CF-1,gloves_typo", "unknown checklist"),
    ("SAMPLE-9,photos/E01.jpg,t1_safe_isolation,c1_ppe,CF-1,", "SAMPLE"),
    ("Ram Kumar,photos/E01.jpg,t1_safe_isolation,c1_ppe,CF-1,", "item_id"),
])
def test_bad_rows_stop_the_whole_import(env, row, msg):
    good = "E02,photos/E02.jpg,t1_safe_isolation,c1_ppe,CF-2,none"
    rows, problems = items.parse(write_csv(env, [good, row]))
    assert len(problems) == 1 and msg in problems[0]
    assert items.main([str(write_csv(env, [good, row]))]) == 1
    db.init_db()
    with Session(db.engine()) as s:
        assert s.exec(select(StudyItem)).first() is None


def test_rated_items_cannot_be_replaced(env):
    csv_path = write_csv(env, ["E01,photos/E01.jpg,t1_safe_isolation,c1_ppe,CF-001,none"])
    assert items.main([str(csv_path)]) == 0
    assert items.main([str(csv_path)]) == 0  # second run skips the existing item
    with Session(db.engine()) as s:
        s.add(StudyRating(rater_id="R1", item_id="E01", condition="unassisted", session=1, position=0, level=2))
        s.commit()
    with pytest.raises(SystemExit, match="already has ratings"):
        items.main([str(csv_path), "--replace"])
