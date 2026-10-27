"""Perceptual hashes to flag evidence photos reused across workers or batches.

pHash (DCT based) and dHash (gradient based) are 64-bit hashes that change little under
re-compression, resizing and mild crops. Two photos are flagged as the same evidence when the
Hamming distance of their pHash is at or below the threshold chosen in `eval_hashing.py`
(stored in experiments/m2_hashing.json). Flags are for the assessor to review; nothing is
rejected automatically.
"""
from __future__ import annotations

from dataclasses import dataclass

import imagehash
import numpy as np
from PIL import Image

# Chosen by `make eval-m2` (experiments/m2_hashing.json, hashes.phash.chosen_threshold).
DEFAULT_PHASH_THRESHOLD = 4  # max recall with <= 5% false flags on fresh photos (dev half)


@dataclass(frozen=True)
class Hashes:
    phash: str
    dhash: str


def hashes_for(img: Image.Image) -> Hashes:
    img = img.convert("RGB")
    return Hashes(phash=str(imagehash.phash(img)), dhash=str(imagehash.dhash(img)))


def hashes_from_bgr(arr: np.ndarray) -> Hashes:
    return hashes_for(Image.fromarray(arr[:, :, ::-1]))


def distance(a: str, b: str) -> int:
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)


def find_duplicate(phash: str, existing: list[tuple[int, str]], threshold: int = DEFAULT_PHASH_THRESHOLD
                   ) -> tuple[int, int] | None:
    """Closest (id, distance) among `existing` (id, phash) pairs within the threshold, else None."""
    best = None
    for eid, other in existing:
        d = distance(phash, other)
        if d <= threshold and (best is None or d < best[1]):
            best = (eid, d)
    return best
