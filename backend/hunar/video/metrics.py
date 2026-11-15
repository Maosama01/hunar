"""Yes/no check metrics shared by the video-pilot evaluations (frame check, explanation check)."""
from __future__ import annotations

import random


def scores(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs of (truth, predicted) -> counts, precision, recall, F1 and accuracy (None when undefined)."""
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


def bootstrap(pairs: list[tuple[bool, bool]], key: str, reps: int = 2000, seed: int = 0) -> list[float] | None:
    """95 % percentile interval of scores()[key] over resampled pairs; None when it is mostly undefined."""
    if not pairs:
        return None
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
