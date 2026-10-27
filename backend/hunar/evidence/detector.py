"""PPE and tool presence detector (YOLOv8n, CPU inference).

The model is trained in notebooks/m2_train_yolo_colab.ipynb and its weights are copied to
data/models/hunar_ppe_tools_yolov8n.pt (gitignored). Until then the detector reports
status "unavailable" and returns no detections; the rubric engine then treats photos as
"not analysed" rather than "nothing detected".

LIMIT: the detector says whether PPE or a tool is visible. It does not judge the quality of
the work, and the UI must never suggest that it does.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from hunar.paths import DATA

WEIGHTS = Path(os.environ.get("HUNAR_YOLO_WEIGHTS", DATA / "models" / "hunar_ppe_tools_yolov8n.pt"))
# Class names the rubric files refer to. Training data labels are mapped onto these names.
CLASSES = ["helmet", "gloves", "vest", "safety_shoes", "goggles",
           "multimeter", "tester_screwdriver", "wire_stripper", "insulated_pliers"]
LIMIT_NOTE = "Presence only: the detector does not judge workmanship quality."


@lru_cache(maxsize=1)
def _model():
    if not WEIGHTS.exists():
        return None
    try:
        from ultralytics import YOLO
    except ImportError:
        return None
    return YOLO(str(WEIGHTS))


def status() -> dict:
    if _model() is None:
        why = "weights not found" if not WEIGHTS.exists() else "ultralytics not installed (uv sync --extra vision)"
        return {"available": False, "reason": why, "weights": str(WEIGHTS), "note": LIMIT_NOTE}
    return {"available": True, "weights": str(WEIGHTS), "classes": CLASSES, "note": LIMIT_NOTE}


def detect(img_bgr: np.ndarray, photo_id: str, conf: float = 0.25) -> list[dict] | None:
    """Detections as [{photo_id, cls, confidence, box}] or None when the detector is unavailable."""
    model = _model()
    if model is None:
        return None
    res = model.predict(img_bgr, conf=conf, device="cpu", verbose=False)[0]
    out = []
    for box in res.boxes:
        name = res.names[int(box.cls)]
        if name in CLASSES:
            out.append({"photo_id": photo_id, "cls": name, "confidence": round(float(box.conf), 3),
                        "box": [round(float(v), 1) for v in box.xyxy[0].tolist()]})
    return out
