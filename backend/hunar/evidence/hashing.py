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
    """Hamming distance of two hex hashes: the same value as imagehash's `-`, without building arrays."""
    if len(a) != len(b):
        raise ValueError("hashes differ in length")
    return (int(a, 16) ^ int(b, 16)).bit_count()


# Pigeonhole: two hashes within t bits of each other agree exactly on at least one of t + 1 disjoint
# bit bands. The database indexes each photo's bands, so a reuse check only compares the photos that
# share a band instead of every stored photo (multi-index hashing). Changing the threshold or the
# band layout changes the bands; hunar.api.services.index_phashes rebuilds them at start-up.
BANDS = DEFAULT_PHASH_THRESHOLD + 1


def phash_bands(phash: str, n: int = BANDS) -> list[int]:
    """`phash` cut into n disjoint bit bands, as integers. Band i holds bits i, i + n, i + 2n, ...

    Interleaving spreads the correlated low-frequency DCT bits over all bands, so the bands of real
    photos vary more than runs of adjacent bits would, and a lookup reads fewer candidates."""
    v, bits = int(phash, 16), 4 * len(phash)
    out = []
    for i in range(n):
        band = 0
        for j, b in enumerate(range(i, bits, n)):
            band |= ((v >> b) & 1) << j
        out.append(band)
    return out


def find_duplicate(phash: str, existing: list[tuple[int, str]], threshold: int = DEFAULT_PHASH_THRESHOLD
                   ) -> tuple[int, int] | None:
    """Closest (id, distance) among `existing` (id, phash) pairs within the threshold, else None.

    Ties keep the first pair in `existing`."""
    best = None
    for eid, other in existing:
        d = distance(phash, other)
        if d <= threshold and (best is None or d < best[1]):
            best = (eid, d)
    return best
