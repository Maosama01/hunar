"""Load real, consented evidence photos into M4 rater mode.

Usage:  python -m hunar.study.items data/study/items.csv [--replace] [--actor NAME]     (`make study-items`)

items.csv columns (template: docs/study_items_template.csv):

  item_id       short code such as E01 (never a person's name; "SAMPLE" prefixes are reserved)
  photo         path to the photo, relative to the CSV file
  task_id       rubric task, for example t1_safe_isolation
  criterion_id  criterion of that task, for example c1_ppe
  consent_ref   number of the signed consent form (docs/consent_form.md); rows without it are refused
  ticked        checklist items the observer saw done, separated by ";". "none" = observed, nothing
                done. Empty = no checklist recorded (the pre score then uses the photo only).

Every row is checked before anything is written; one bad row stops the whole import. Each photo is
decoded, faces are blurred, and it is re-encoded as JPEG (which drops EXIF data such as GPS) into
data/uploads/study/ (gitignored). The pre score shown in the assisted condition is computed now with
the same rubric engine the app uses. Each added item is written to the audit log.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from hunar.api import services
from hunar.api.db import engine as db_engine
from hunar.api.db import init_db
from hunar.api.models import StudyItem, StudyRating
from hunar.audit import log as audit
from hunar.evidence import detector, privacy
from hunar.paths import DATA
from hunar.rubric import engine

COLUMNS = ["item_id", "photo", "task_id", "criterion_id", "consent_ref", "ticked"]
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
TARGET_ITEMS = (20, 30)


@dataclass
class Row:
    item_id: str
    photo: Path
    task: engine.Task
    criterion: engine.Criterion
    consent_ref: str
    checklist: dict[str, bool] | None


def parse(csv_path: Path) -> tuple[list[Row], list[str]]:
    """Validated rows and a list of problems (empty when every row is fine)."""
    problems: list[str] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [], [f"missing columns: {', '.join(missing)}"]
        raw = list(reader)
    rows, seen = [], set()
    for n, r in enumerate(raw, start=2):  # line 1 is the header
        r = {k: (v or "").strip() for k, v in r.items() if k}
        where = f"line {n}"
        item_id = r["item_id"]
        if not ID_RE.match(item_id) or item_id.upper().startswith("SAMPLE"):
            problems.append(f"{where}: item_id {item_id!r} must be 1-32 letters, digits, - or _ and not start "
                            "with SAMPLE")
            continue
        if item_id in seen:
            problems.append(f"{where}: duplicate item_id {item_id}")
            continue
        seen.add(item_id)
        if not r["consent_ref"]:
            problems.append(f"{where}: {item_id} has no consent_ref; only photos with signed consent may be used")
            continue
        photo = (csv_path.parent / r["photo"]).resolve()
        if not r["photo"] or not photo.is_file():
            problems.append(f"{where}: photo not found: {r['photo']!r}")
            continue
        try:
            task = engine.get_task(r["task_id"])
        except KeyError:
            problems.append(f"{where}: unknown task_id {r['task_id']!r}")
            continue
        cr = next((c for c in task.criteria if c.id == r["criterion_id"]), None)
        if cr is None:
            problems.append(f"{where}: {r['criterion_id']!r} is not a criterion of {task.task_id}")
            continue
        checklist = None
        if r["ticked"]:
            ticked = set() if r["ticked"].lower() == "none" else {t.strip() for t in r["ticked"].split(";") if t.strip()}
            known = {c.id for c in task.checklist}
            if unknown := ticked - known:
                problems.append(f"{where}: unknown checklist items {sorted(unknown)} for {task.task_id}")
                continue
            checklist = {c: c in ticked for c in known}
        rows.append(Row(item_id, photo, task, cr, r["consent_ref"], checklist))
    if not raw:
        problems.append("the CSV has no rows")
    return rows, problems


def prescore(row: Row, img) -> engine.PreScore:
    dets = detector.detect(img, "study")
    detections = [engine.Detection(**d) for d in dets] if dets is not None else None
    return engine.prescore_criterion(row.task, row.criterion, row.checklist, detections, [])


def add_items(rows: list[Row], actor: str, replace: bool = False) -> list[StudyItem]:
    init_db()
    folder = services.UPLOADS / "study"
    added = []
    with Session(db_engine()) as s:
        for row in rows:
            old = s.get(StudyItem, row.item_id)
            if old and not replace:
                print(f"  {row.item_id}: already loaded, skipped (use --replace to update it)")
                continue
            if old and s.exec(select(StudyRating).where(StudyRating.item_id == row.item_id)).first():
                raise SystemExit(f"{row.item_id} already has ratings; replacing it would invalidate them")
            img = privacy.decode(row.photo.read_bytes())
            blurred, n_faces = privacy.blur_faces(img)  # blur before anything is written
            jpeg = privacy.encode_jpeg(blurred)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{row.item_id}.jpg"
            path.write_bytes(jpeg)
            ps = prescore(row, blurred)
            item = old or StudyItem(id=row.item_id, image_path="", task_id="", criterion_id="")
            item.image_path = str(path.relative_to(DATA))
            item.task_id, item.criterion_id = row.task.task_id, row.criterion.id
            item.prescore_json, item.is_sample = ps.model_dump_json(), False
            s.add(item)
            audit.append(s, actor, "study.item_added", row.item_id,
                         {"task_id": row.task.task_id, "criterion_id": row.criterion.id, "consent_ref": row.consent_ref,
                          "sha256": hashlib.sha256(jpeg).hexdigest(), "faces_blurred": n_faces,
                          "suggested_level": ps.suggested_level, "replaced": bool(old)}, commit=False)
            added.append(item)
            print(f"  {row.item_id}: {row.task.task_id}.{row.criterion.id}  faces blurred {n_faces}  "
                  f"pre score {ps.suggested_level if ps.suggested_level is not None else '-'} ({ps.confidence})")
        s.commit()
        for it in added:
            s.refresh(it)
        total = len(s.exec(select(StudyItem).where(StudyItem.is_sample == False)).all())  # noqa: E712
    lo, hi = TARGET_ITEMS
    print(f"{len(added)} item(s) added; {total} real study item(s) in the database (plan: {lo} to {hi}).")
    if total < lo:
        print(f"  note: fewer than {lo} items; agreement estimates will be very imprecise "
              "(see experiments/m4_design_simulation.json).")
    return added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", type=Path)
    ap.add_argument("--replace", action="store_true", help="update items already loaded (only if not yet rated)")
    ap.add_argument("--actor", default="study-coordinator")
    a = ap.parse_args(argv)
    if not a.csv.is_file():
        print(f"{a.csv}: not found. Copy docs/study_items_template.csv to data/study/items.csv and fill it in.")
        return 1
    rows, problems = parse(a.csv)
    if problems:
        print("Nothing was imported. Fix these rows first:")
        for p in problems:
            print("  " + p)
        return 1
    add_items(rows, a.actor, a.replace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
