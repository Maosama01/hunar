"""Load one clearly labelled SAMPLE worker for the demo (`make seed`).

Everything created here is marked is_sample=True and shown with a "SAMPLE DATA" badge in the UI.
The photos are synthetic drawings generated below, not pictures of real people or real work.
"""
from __future__ import annotations

import json

import cv2
import numpy as np
from sqlmodel import Session, select

from hunar.api import services as svc
from hunar.api.db import engine, init_db
from hunar.api.models import Worker
from hunar.paths import DATA
from hunar.rubric import engine as rubric

SAMPLE_DIR = DATA / "synthetic" / "sample_photos"
SAMPLE_DECLARATION = (
    "Main 7 saal se ghar aur dukaan ki wiring karta hoon. Pehle chacha ke saath kaam seekha. "
    "Conduit pipe deewar mein daalta hoon, taar kheenchta hoon, switch board aur MCB lagata hoon. "
    "Kaam se pehle main switch band karta hoon aur tester se check karta hoon."
)


def _drawing(title: str, seed: int) -> np.ndarray:
    """A synthetic line drawing of a switch board, stamped SAMPLE IMAGE."""
    rng = np.random.default_rng(seed)
    img = np.full((480, 640, 3), 235, np.uint8)
    cv2.rectangle(img, (170, 90), (470, 390), (60, 60, 60), 3)
    for i in range(3):
        x = 210 + i * 90
        cv2.rectangle(img, (x, 150), (x + 50, 230), (40, 40, 40), 2)
        cv2.line(img, (x + 25, 230), (x + 25 + int(rng.integers(-30, 30)), 390), (0, 0, 200), 2)
    cv2.circle(img, (320, 310), 28, (40, 40, 40), 2)
    cv2.putText(img, "SAMPLE IMAGE - synthetic drawing", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.putText(img, title, (40, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
    return img


def main() -> None:
    init_db()
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    with Session(engine()) as s:
        if s.exec(select(Worker).where(Worker.code == "SAMPLE-W001")).first():
            print("sample worker already present; nothing to do")
            return
        w = svc.create_worker(s, "SAMPLE-W001", "hi", "seed", id="sample-worker-1", is_sample=True)
        a = svc.create_assessment(s, w.id, SAMPLE_DECLARATION, "seed", id="sample-assessment-1", is_sample=True)
        svc.confirm_pack(s, a, 13772, "SAMPLE-assessor", None if json.loads(a.mapping_json)["ranking"][0]["nqr_id"]
                         == 13772 else "sample data: target pack for the demo")
        svc.set_checklist(s, a, "t1_safe_isolation",
                          {"ppe_gloves": True, "ppe_shoes": False, "main_off": True, "tag_lockout": False,
                           "tester_checked": True, "tested_dead": True, "tools_inspected": True}, "SAMPLE-assessor")
        svc.set_checklist(s, a, "t2_switchboard_wiring",
                          {"diagram_followed": True, "no_bare_copper": True, "terminals_tight": True,
                           "switch_in_phase": True, "socket_polarity": True, "earth_connected": True,
                           "colour_code": False, "neat_dressing": True, "works_on_test": True}, "SAMPLE-assessor")
        img = _drawing("Sample worker: finished board (task 2)", 1)
        svc.add_evidence(s, a, "t2_switchboard_wiring", "p1", cv2.imencode(".jpg", img)[1].tobytes(), True, "seed")

        # Sample items so rater mode can be demonstrated. They are excluded from the real study.
        from hunar.api.models import StudyItem

        crit = [("t2_switchboard_wiring", "c2_termination"), ("t2_switchboard_wiring", "c5_workmanship"),
                ("t4_joint_termination", "c3_insulate")]
        for i in range(6):
            task_id, crit_id = crit[i % len(crit)]
            path = SAMPLE_DIR / f"study_sample_{i + 1}.jpg"
            cv2.imwrite(str(path), _drawing(f"Sample study item {i + 1}", 10 + i))
            pre = rubric.prescore_task(rubric.get_task(task_id))
            ps = next(p for p in pre if p.criterion_id == crit_id)
            s.add(StudyItem(id=f"SAMPLE-{i + 1}", image_path=str(path.relative_to(DATA)), task_id=task_id,
                            criterion_id=crit_id, prescore_json=ps.model_dump_json(), is_sample=True))
        s.commit()
    print("seeded SAMPLE-W001 (sample data) with one assessment and 6 sample rater-mode items")


if __name__ == "__main__":
    main()
