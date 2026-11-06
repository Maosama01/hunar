"""Measure the guided-clip frame check on hand-labelled frames (`make eval-clips`).

Reads data/labels/clip_frames.csv (from `make clip-frames`, labelled by a person), runs the frame
check on every labelled frame and writes experiments/video_detector.json: precision, recall and
accuracy for "part present" and for "hand on part" at the current cut-offs, with counts and 95 %
bootstrap intervals, plus both checks at a range of cut-offs. The hand check has no cut-off until one
is chosen here (HUNAR_CLIP_HAND_CONF); a cut-off picked and measured on the same frames is optimistic,
so confirm it on frames from new clips.

Frames from SAMPLE assessments are left out unless --include-sample is given (then the file says
data_kind "synthetic"). With no labelled frames or no detector set up, nothing is written and the
README keeps RESULT PENDING.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hunar.paths import DATA, EXPERIMENTS  # noqa: E402
from hunar.video import detect  # noqa: E402

CSV = DATA / "labels" / "clip_frames.csv"


def scores(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs of (truth, predicted)."""
    tp = sum(t and p for t, p in pairs)
    fp = sum(p and not t for t, p in pairs)
    fn = sum(t and not p for t, p in pairs)
    n = len(pairs)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None  # None: no positives and none predicted
    return {"n": n, "positives": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": None if precision is None else round(precision, 4),
            "recall": None if recall is None else round(recall, 4),
            "f1": None if f1 is None else round(f1, 4),
            "accuracy": round(sum(t == p for t, p in pairs) / n, 4) if n else None}


CUTOFFS = [0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]


def sweep(items: list[tuple[bool, bool, list[dict]]], part_conf: float) -> dict:
    """items: (part truth, hand truth, raw frame) per labelled frame -> both checks at every cut-off. The hand
    sweep keeps the part cut-off fixed, since a hand counts only on a part box that passed."""
    part, hand = [], []
    for c in CUTOFFS:
        part.append({"cutoff": c, **scores([(pt, detect.summarise(fr, c, None)["part_seen"]) for pt, _, fr in items])})
        hand.append({"cutoff": c, **scores([(ht, bool(detect.summarise(fr, part_conf, c)["hand_on_part"]))
                                            for _, ht, fr in items])})
    best = {k: max((r for r in rows if r["f1"] is not None), key=lambda r: r["f1"], default=None)
            for k, rows in (("part", part), ("hand", hand))}
    return {"part_by_cutoff": part, "hand_by_cutoff": hand,
            "best_f1_cutoff": {k: (None if r is None else r["cutoff"]) for k, r in best.items()}}


def bootstrap(pairs: list[tuple[bool, bool]], key: str, reps: int = 2000, seed: int = 0) -> list[float] | None:
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        v = scores([rng.choice(pairs) for _ in pairs])[key]
        if v is not None:
            vals.append(v)
    if len(vals) < reps // 2:
        return None
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[int(0.975 * len(vals)) - 1], 4)]


def main(argv: list[str] | None = None) -> int:
    import cv2

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--include-sample", action="store_true", help="also use frames of SAMPLE assessments")
    a = ap.parse_args(argv)
    rows = [r for r in csv.DictReader(CSV.open())] if CSV.exists() else []
    rows = [r for r in rows if r["part_present"].strip() in ("0", "1") and r["hand_on_part"].strip() in ("0", "1")
            and (a.include_sample or r.get("is_sample") != "1")]
    det = detect.detector()
    if not rows:
        print(f"RESULT PENDING: no labelled frames in {CSV.relative_to(ROOT)} (run `make clip-frames`, then label).")
        return 0
    if isinstance(det, detect.NoDetector):
        print("RESULT PENDING: the frame detector is not set up (run `make clip-models`).")
        return 0
    items, part, hand = [], [], []
    for r in rows:
        img = cv2.imread(str(DATA / "labels" / r["image"]))
        if img is None:
            continue
        raw = det.raw([(0.0, img)], r["labels"].split("|"))
        if raw is None:
            continue  # labels not prepared for this part
        now = detect.summarise(raw, det.conf, det.hand_conf)
        pt, ht = r["part_present"] == "1", r["hand_on_part"] == "1"
        items.append((pt, ht, raw))
        part.append((pt, bool(now["part_seen"])))
        if now["hand_on_part"] is not None:
            hand.append((ht, bool(now["hand_on_part"])))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    result = {
        "experiment": "video_detector",
        "data_kind": "synthetic" if a.include_sample else "real",
        "detector": det.name, "confidence_threshold": detect.CONF,
        "n_frames": len(part), "n_clips": len({r["clip"] for r in rows}),
        "part_present": {**scores(part), "precision_ci95": bootstrap(part, "precision"),
                         "recall_ci95": bootstrap(part, "recall")},
        "hand_conf": det.hand_conf,
        "hand_on_part": ({**scores(hand), "precision_ci95": bootstrap(hand, "precision"),
                          "recall_ci95": bootstrap(hand, "recall")} if hand else None),
        **sweep(items, det.conf),
        "cutoff_note": "Cut-offs picked and measured on the same frames are optimistic; confirm on frames from new clips.",
        "note": "Presence and handling only; the detector does not judge workmanship.",
        "command": "python scripts/eval_clip_detector.py" + (" --include-sample" if a.include_sample else ""),
        "git_commit": commit, "created": dt.datetime.now().isoformat(timespec="seconds"),
    }
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "video_detector.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("n_frames", "part_present", "hand_on_part", "best_f1_cutoff")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
