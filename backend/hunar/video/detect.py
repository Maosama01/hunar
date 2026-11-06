"""Frame check for guided clips: is the named part in the frame, and is a hand on it?

YOLOE (Ultralytics, open vocabulary) is prompted with the part's `detect` labels from the rubric and
with "hand", on about one blurred frame a second. A part counts as seen when a box of one of its
labels reaches the part cut-off (HUNAR_CLIP_CONF, 0.25 by our choice). "Hand on part" means a hand box
overlaps a part box in the same frame and reaches the hand cut-off (HUNAR_CLIP_HAND_CONF).

The hand check is OFF until that cut-off is set. In a first look at sample photos YOLOE put its "hand"
box on a clearly visible hand but scored it far below the part cut-off, so any value we picked now
would be a guess. Until then every clip says "hand not checked"; each frame still records the best
hand score so that `make eval-clips` can choose the cut-off from labelled frames.

This shows presence and handling only, never whether the work was done well, and its accuracy is not
known until it is measured on labelled frames (scripts/eval_clip_detector.py).

Setup: `make clip-models` downloads the weights and prepares the text prompts in data/models/. Without
them, or with HUNAR_CLIP_DETECTOR=none, the check reports "not checked". MediaPipe was considered
for hands but would install a second OpenCV that replaces the cv2 build the face blur relies on.
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache

import numpy as np

from hunar.paths import DATA

WEIGHTS = "yoloe-11s-seg.pt"
PE_FILE = "yoloe_text_pe.pt"
HAND = "hand"
CONF = float(os.environ.get("HUNAR_CLIP_CONF", "0.25"))  # parts: our choice for a first pilot; to be tuned on labels
_hand = os.environ.get("HUNAR_CLIP_HAND_CONF", "").strip()
HAND_CONF: float | None = float(_hand) if _hand else None  # None: hand check off until labelled frames set it
FLOOR = 0.01  # boxes kept below the cut-offs, for the record and for choosing cut-offs on labelled frames


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Boxes (x1, y1, x2, y2) share some area."""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def frame_result(f: dict, part_conf: float, hand_conf: float | None) -> dict:
    """One frame {"t", "part": [(label, conf, box)], "hands": [(conf, box)]} at the given cut-offs.
    "hand" is the best score of a hand box on a part box that passed; "hand_on_part" is None while the
    hand check has no cut-off."""
    parts = [p for p in f["part"] if p[1] >= part_conf]
    hand = max((c for c, box in f["hands"] if any(overlaps(box, p[2]) for p in parts)), default=None)
    return {"t": round(f["t"], 1),
            "part": round(max(p[1] for p in parts), 2) if parts else None,
            "hand": None if hand is None else round(hand, 3),
            "hand_on_part": None if hand_conf is None else (hand is not None and hand >= hand_conf)}


def summarise(frames: list[dict], part_conf: float, hand_conf: float | None) -> dict:
    """The clip's result from its frames (see frame_result)."""
    rows = [frame_result(f, part_conf, hand_conf) for f in frames]
    return {
        "part_seen": any(r["part"] is not None for r in rows),
        "hand_on_part": None if hand_conf is None else any(r["hand_on_part"] for r in rows),
        "frames": rows,
    }


class NoDetector:
    """No detector configured: presence is reported as not checked."""

    name = "none"

    def check(self, samples: list[tuple[float, np.ndarray]], labels: list[str]) -> dict:
        return {"part_seen": None, "hand_on_part": None, "frames": []}


class YoloeDetector:
    name = "yoloe-11s (open vocabulary)"

    def __init__(self, weights: str, pe_file: str, conf: float = CONF, hand_conf: float | None = HAND_CONF):
        import torch
        from ultralytics import YOLOE

        self.model = YOLOE(weights)
        saved = torch.load(pe_file, map_location="cpu")
        self.labels: list[str] = saved["labels"]
        self.embeddings = saved["embeddings"]
        self.conf = conf
        self.hand_conf = hand_conf
        self.lock = threading.Lock()  # set_classes changes the shared model

    def raw(self, samples: list[tuple[float, np.ndarray]], labels: list[str]) -> list[dict] | None:
        """Every part and hand box down to FLOOR, per frame; None when no label was prepared."""
        use = [lb for lb in labels if lb in self.labels and lb != HAND]
        if not use or HAND not in self.labels or not samples:
            return None  # labels not prepared: run `make clip-models` again
        names = [*use, HAND]
        idx = [self.labels.index(n) for n in names]
        floor = min(FLOOR, self.conf, self.hand_conf if self.hand_conf is not None else FLOOR)
        frames = []
        with self.lock:
            self.model.set_classes(names, self.embeddings[:, idx])
            for t, img in samples:
                r = self.model.predict(img, conf=floor, verbose=False)[0]
                part, hands = [], []
                for box, cls, conf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist(),
                                          strict=True):
                    name = names[int(cls)]
                    (hands.append((conf, tuple(box))) if name == HAND else part.append((name, conf, tuple(box))))
                frames.append({"t": t, "part": part, "hands": hands})
        return frames

    def check(self, samples: list[tuple[float, np.ndarray]], labels: list[str]) -> dict:
        frames = self.raw(samples, labels)
        if frames is None:
            return NoDetector().check(samples, labels)
        return summarise(frames, self.conf, self.hand_conf)


@lru_cache(maxsize=1)
def detector() -> NoDetector | YoloeDetector:
    if os.environ.get("HUNAR_CLIP_DETECTOR", "yoloe") == "none":
        return NoDetector()
    w, pe = DATA / "models" / WEIGHTS, DATA / "models" / PE_FILE
    if not (w.exists() and pe.exists()):
        return NoDetector()
    return YoloeDetector(str(w), str(pe))
