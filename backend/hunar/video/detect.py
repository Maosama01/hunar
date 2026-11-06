"""Frame check for guided clips: is the named part in the frame, and is a hand on it?

YOLOE (Ultralytics, open vocabulary) is prompted with the part's `detect` labels from the rubric and
with "hand", on about one blurred frame a second. A part counts as seen when a box of one of its
labels reaches the confidence threshold; "hand on part" means a hand box overlaps a part box in the
same frame. This shows presence and handling only, never whether the work was done well, and its
accuracy is not known until it is measured on labelled frames (scripts/eval_clip_detector.py).

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
CONF = float(os.environ.get("HUNAR_CLIP_CONF", "0.25"))  # our choice for a first pilot; to be tuned on labels


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Boxes (x1, y1, x2, y2) share some area."""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def summarise(frames: list[dict]) -> dict:
    """frames: [{"t", "part": [(label, conf, box)], "hands": [box]}] -> the clip's result."""
    seen = [f for f in frames if f["part"]]
    held = [f for f in seen if any(overlaps(h, p[2]) for h in f["hands"] for p in f["part"])]
    return {
        "part_seen": bool(seen),
        "hand_on_part": bool(held),
        "frames": [{"t": round(f["t"], 1), "part": round(max(p[1] for p in f["part"]), 2) if f["part"] else None,
                    "hand_on_part": f in held} for f in frames],
    }


class NoDetector:
    """No detector configured: presence is reported as not checked."""

    name = "none"

    def check(self, samples: list[tuple[float, np.ndarray]], labels: list[str]) -> dict:
        return {"part_seen": None, "hand_on_part": None, "frames": []}


class YoloeDetector:
    name = "yoloe-11s (open vocabulary)"

    def __init__(self, weights: str, pe_file: str, conf: float = CONF):
        import torch
        from ultralytics import YOLOE

        self.model = YOLOE(weights)
        saved = torch.load(pe_file, map_location="cpu")
        self.labels: list[str] = saved["labels"]
        self.embeddings = saved["embeddings"]
        self.conf = conf
        self.lock = threading.Lock()  # set_classes changes the shared model

    def check(self, samples: list[tuple[float, np.ndarray]], labels: list[str]) -> dict:
        use = [lb for lb in labels if lb in self.labels and lb != HAND]
        if not use or HAND not in self.labels or not samples:
            return NoDetector().check(samples, labels)  # labels not prepared: run `make clip-models` again
        names = [*use, HAND]
        idx = [self.labels.index(n) for n in names]
        frames = []
        with self.lock:
            self.model.set_classes(names, self.embeddings[:, idx])
            for t, img in samples:
                r = self.model.predict(img, conf=self.conf, verbose=False)[0]
                part, hands = [], []
                for box, cls, conf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist(),
                                          strict=True):
                    name = names[int(cls)]
                    (hands.append(tuple(box)) if name == HAND else part.append((name, conf, tuple(box))))
                frames.append({"t": t, "part": part, "hands": hands})
        return summarise(frames)


@lru_cache(maxsize=1)
def detector() -> NoDetector | YoloeDetector:
    if os.environ.get("HUNAR_CLIP_DETECTOR", "yoloe") == "none":
        return NoDetector()
    w, pe = DATA / "models" / WEIGHTS, DATA / "models" / PE_FILE
    if not (w.exists() and pe.exists()):
        return NoDetector()
    return YoloeDetector(str(w), str(pe))
