"""Blur faces before an evidence photo is stored (integrity rule 6).

Uses OpenCV's Haar cascade face detector (Viola-Jones), which runs on CPU with no download.
It misses some faces (profile views, small or occluded faces), so the UI also lets the
facilitator retake a photo, and a full-image blur fallback is available.
"""
from __future__ import annotations

import cv2
import numpy as np

_CASCADES = [cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
             cv2.data.haarcascades + "haarcascade_profileface.xml"]
_detectors = [cv2.CascadeClassifier(p) for p in _CASCADES]


def detect_faces(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    min_side = max(24, min(img.shape[:2]) // 20)
    boxes: list[tuple[int, int, int, int]] = []
    for det in _detectors:
        for (x, y, w, h) in det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_side, min_side)):
            boxes.append((int(x), int(y), int(w), int(h)))
    return boxes


def blur_faces(img: np.ndarray, pad: float = 0.25) -> tuple[np.ndarray, int]:
    """Return a copy with every detected face strongly blurred, and the number of faces."""
    out = img.copy()
    boxes = detect_faces(img)
    H, W = img.shape[:2]
    for (x, y, w, h) in boxes:
        px, py = int(w * pad), int(h * pad)
        x0, y0, x1, y1 = max(0, x - px), max(0, y - py), min(W, x + w + px), min(H, y + h + py)
        roi = out[y0:y1, x0:x1]
        k = max(31, (min(roi.shape[:2]) // 2) | 1)
        out[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(cv2.resize(roi, (8, 8)), roi.shape[1::-1],
                                                        interpolation=cv2.INTER_NEAREST), (k, k), 0)
    return out, len(boxes)


def decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a readable image")
    return img


def encode_jpeg(img: np.ndarray, quality: int = 88) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()
