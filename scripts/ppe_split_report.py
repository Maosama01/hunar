"""Class balance of the PPE dataset's published splits vs the Hunar re-split (`make ppe-split`).

Needs all three splits locally: `uv run python scripts/fetch_ppe_test.py train valid test`.
Writes experiments/m2_ppe_split.json. The Colab notebook runs the same re-split code
(hunar.evidence.ppe_split, embedded verbatim) and records its own counts in m2_detector.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from hunar.evidence.ppe_split import (  # noqa: E402
    class_counts,
    cross_split_near_duplicates,
    group_near_duplicates,
    load_pool,
    phash64,
    stratified_group_split,
)

PPE = ROOT / "data" / "raw" / "ppe"
CACHE = PPE / "phash_cache.json"
MAX_DIST = 4  # grouping threshold (bits of 64); 8 chained whole videos into one group (see report)
SEED = 0


def main() -> int:
    if not all((PPE / s / "_annotations.coco.json").exists() for s in ("train", "valid", "test")):
        print("run: uv run python scripts/fetch_ppe_test.py train valid test", file=sys.stderr)
        return 1
    pool = load_pool(PPE)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    hashes = []
    for i, r in enumerate(pool):
        if r["name"] not in cache:
            cache[r["name"]] = phash64(r["path"])
        hashes.append(cache[r["name"]])
        if i % 2000 == 0:
            print(f"hashed {i}/{len(pool)}")
    CACHE.write_text(json.dumps(cache))
    published = class_counts(pool, [r["published_split"] for r in pool])
    groups = group_near_duplicates(hashes, MAX_DIST)
    sizes = collections.Counter(groups.tolist())
    assignment = stratified_group_split(pool, groups, seed=SEED)
    new = class_counts(pool, assignment)
    res = {
        "experiment": "m2_ppe_split", "data_kind": "real_public_dataset",
        "dataset": "keremberke/protective-equipment-detection (Roboflow PPE v7, CC BY 4.0)",
        "command": "python scripts/ppe_split_report.py", "created": dt.datetime.now().isoformat(timespec="seconds"),
        "n_images": len(pool),
        "published_splits": published,
        "published_test_with_near_duplicate_in_train_4bits": cross_split_near_duplicates(
            hashes, [r["published_split"] for r in pool], 4),
        "resplit": {
            "method": f"pHash groups (single linkage, <= {MAX_DIST} bits), iterative stratification over groups (rarest class first, targets train/valid/test 0.70/0.15/0.15, ties to test), seed {SEED}",
            "n_groups": len(sizes), "largest_group": max(sizes.values()),
            "groups_with_more_than_one_image": sum(v > 1 for v in sizes.values()),
            "counts": new,
            "test_with_near_duplicate_in_train_4bits": cross_split_near_duplicates(hashes, assignment, 4),
        },
    }
    (ROOT / "experiments" / "m2_ppe_split.json").write_text(json.dumps(res, indent=2) + "\n")
    for title, c in [("published", published), ("re-split", new)]:
        print(f"\n{title}:")
        for s in ("train", "valid", "test"):
            print(f"  {s:5s} {c[s]['images']:5d} images  boxes {c[s]['boxes']}")
    print("\ngroups:", res["resplit"]["n_groups"], "largest:", res["resplit"]["largest_group"],
          "| leaked test images (published, re-split):", res["published_test_with_near_duplicate_in_train_4bits"],
          res["resplit"]["test_with_near_duplicate_in_train_4bits"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
