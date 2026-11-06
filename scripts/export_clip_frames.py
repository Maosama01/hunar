"""Export frames from stored guided clips for labelling (`make clip-frames`).

Writes about one frame a second from every stored clip (already face-blurred and silent) to
data/labels/clip_frames/ (gitignored: frames of real people stay off GitHub) and adds a row per
frame to data/labels/clip_frames.csv with two empty columns for a person to fill in:

  part_present  1 if one of the listed parts is visible in the frame, else 0
  hand_on_part  1 if a hand is touching or holding that part, else 0

Rows already in the CSV are kept, with their labels. Then run `make eval-clips`.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlmodel import Session, select  # noqa: E402

from hunar.api.db import engine, init_db  # noqa: E402
from hunar.api.models import Assessment, GuidedClip  # noqa: E402
from hunar.paths import DATA  # noqa: E402
from hunar.rubric.engine import get_task  # noqa: E402

OUT = DATA / "labels" / "clip_frames"
CSV = DATA / "labels" / "clip_frames.csv"
FIELDS = ["image", "clip", "task_id", "clip_id", "labels", "t", "is_sample", "part_present", "hand_on_part"]


def frames(path: Path, every: float = 1.0):
    import av

    with av.open(str(path)) as c:
        nxt = 0.0
        for f in c.decode(c.streams.video[0]):
            t = float(f.time or 0.0)
            if t >= nxt:
                yield t, f.to_ndarray(format="bgr24")
                nxt = t + every


def main(argv: list[str] | None = None) -> int:
    import cv2

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--every", type=float, default=1.0, help="seconds between exported frames")
    a = ap.parse_args(argv)
    init_db()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {r["image"]: r for r in csv.DictReader(CSV.open())} if CSV.exists() else {}
    added = 0
    with Session(engine()) as s:
        for c in s.exec(select(GuidedClip).order_by(GuidedClip.created_at)):
            src = Path(c.stored_path)
            src = src if src.is_absolute() else DATA / src
            if not src.exists():
                continue
            prompt = next((p for p in get_task(c.task_id).clips if p.id == c.clip_id), None)
            a_ = s.get(Assessment, c.assessment_id)
            for t, img in frames(src, a.every):
                name = f"{c.id[:8]}_{c.clip_id}_{t:06.1f}.jpg"
                if f"clip_frames/{name}" in rows:
                    continue
                cv2.imwrite(str(OUT / name), img)
                rows[f"clip_frames/{name}"] = {"image": f"clip_frames/{name}", "clip": c.id, "task_id": c.task_id,
                                               "clip_id": c.clip_id, "labels": "|".join(prompt.detect if prompt else []),
                                               "t": f"{t:.1f}", "is_sample": int(bool(a_ and a_.is_sample)),
                                               "part_present": "", "hand_on_part": ""}
                added += 1
    with CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows.values())
    print(f"{added} new frames; {len(rows)} rows in {CSV.relative_to(DATA.parent)} (fill part_present and hand_on_part)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
