"""Group-aware, class-stratified re-split of the public PPE dataset for detector training.

Why: the dataset's published splits are class-disjoint (the train split has no helmet boxes and the
test split has no glove boxes), and they share near-identical video frames. A model trained on them
cannot learn helmets and cannot be tested on gloves (see experiments/m2_ppe_split.json).

How:
1. Pool the images of all published splits and map COCO labels to Hunar class names.
2. pHash every image; union images whose hashes are within `max_dist` bits, so frames of the same
   scene form one group and can never end up on both sides of a split.
3. Iterative stratification over groups: rarest class first, each of its groups goes to the split
   that still needs most boxes of that class (targets 70/15/15). The dataset is mostly long videos
   (all safety-shoe boxes come from two of them), so a 4-bit threshold is used: it removes every
   cross-split near-duplicate at 4 bits while keeping all classes in all splits.

This file has no project imports: notebooks/m2_train_yolo_colab.ipynb embeds its source verbatim,
so Colab runs exactly the code tested here.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

CLASS_MAP = {"helmet": "helmet", "glove": "gloves", "shoes": "safety_shoes", "goggles": "goggles"}
NAMES = ["helmet", "gloves", "safety_shoes", "goggles"]
_LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def load_pool(root: Path, splits: tuple[str, ...] = ("train", "valid", "test")) -> list[dict]:
    """One record per image: path, published split, YOLO label lines and Hunar classes present."""
    pool = []
    for split in splits:
        src = Path(root) / split
        coco = json.load(open(src / "_annotations.coco.json"))
        cats = {c["id"]: c["name"] for c in coco["categories"]}
        boxes = collections.defaultdict(list)
        for a in coco["annotations"]:
            name = CLASS_MAP.get(cats.get(a["category_id"], ""))
            if name is not None:
                boxes[a["image_id"]].append((NAMES.index(name), a["bbox"]))
        for im in coco["images"]:
            lines, classes = [], set()
            for k, (x, y, w, h) in boxes[im["id"]]:
                W, H = im["width"], im["height"]
                lines.append(f"{k} {(x + w / 2) / W:.6f} {(y + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}")
                classes.add(NAMES[k])
            pool.append({"path": str(src / im["file_name"]), "published_split": split, "labels": lines,
                         "classes": sorted(classes), "name": f"{split}_{im['file_name']}"})
    return pool


def phash64(path: str) -> int:
    bits = imagehash.phash(Image.open(path).convert("RGB")).hash.flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def _popcount(x: np.ndarray) -> np.ndarray:
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(x)
    return _LUT[x.view(np.uint8).reshape(*x.shape, 8)].sum(-1)


def group_near_duplicates(hashes: list[int], max_dist: int, chunk: int = 512) -> np.ndarray:
    """Group ids such that any two images within `max_dist` bits share a group (single linkage)."""
    h = np.array(hashes, dtype=np.uint64)
    parent = np.arange(len(h))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for s in range(0, len(h), chunk):
        d = _popcount(h[s:s + chunk, None] ^ h[None, :])
        for i, j in zip(*np.nonzero(d <= max_dist), strict=True):
            a, b = find(s + int(i)), find(int(j))
            if a != b:
                parent[a] = b
    return np.array([find(i) for i in range(len(h))])


SPLITS = ("test", "valid", "train")  # tie-break order: fill test first, it matters most


def stratified_group_split(pool: list[dict], groups: np.ndarray, seed: int = 0,
                           fractions: dict[str, float] | None = None) -> list[str]:
    """'train' / 'valid' / 'test' per image, keeping every group in one split.

    Iterative stratification over groups (after Sechidis et al., 2011): repeatedly take the class with
    the fewest unassigned boxes and give each of its groups (largest first) to the split that still
    needs the most boxes of that class. Groups without Hunar labels then fill the image targets.
    `seed` only breaks ties between equally sized groups.
    """
    fractions = fractions or {"train": 0.70, "valid": 0.15, "test": 0.15}
    rng = np.random.default_rng(seed)
    members: dict[int, list[int]] = collections.defaultdict(list)
    for i, g in enumerate(groups.tolist()):
        members[g].append(i)
    boxes = {g: collections.Counter(NAMES[int(line.split()[0])] for i in idx for line in pool[i]["labels"])
             for g, idx in members.items()}
    total = collections.Counter()
    for c in boxes.values():
        total.update(c)
    need = {s: {c: fractions[s] * total[c] for c in total} for s in SPLITS}
    need_img = {s: fractions[s] * len(pool) for s in SPLITS}
    tiebreak = {g: rng.random() for g in members}
    where: dict[int, str] = {}

    def assign(g: int, s: str) -> None:
        where[g] = s
        need_img[s] -= len(members[g])
        for c, n in boxes[g].items():
            need[s][c] -= n

    while True:
        left = collections.Counter()
        for g, c in boxes.items():
            if g not in where:
                left.update(c)
        if not left:
            break
        cls = min(left, key=lambda c: (left[c], c))
        todo = sorted((g for g in boxes if g not in where and boxes[g][cls]),
                      key=lambda g: (-boxes[g][cls], tiebreak[g]))
        for g in todo:
            assign(g, max(SPLITS, key=lambda s: (need[s][cls], need_img[s])))
    for g in sorted((g for g in members if g not in where), key=lambda g: (-len(members[g]), tiebreak[g])):
        assign(g, max(SPLITS, key=lambda s: need_img[s]))
    return [where[g] for g in groups.tolist()]


def class_counts(pool: list[dict], assignment: list[str]) -> dict:
    """Images and boxes per class for each split."""
    res: dict = {}
    for r, s in zip(pool, assignment, strict=True):
        d = res.setdefault(s, {"images": 0, "boxes": dict.fromkeys(NAMES, 0)})
        d["images"] += 1
        for line in r["labels"]:
            d["boxes"][NAMES[int(line.split()[0])]] += 1
    return res


def cross_split_near_duplicates(hashes: list[int], assignment: list[str], max_dist: int) -> int:
    """Test images that have a near-duplicate (within max_dist) in train. 0 by construction."""
    h = np.array(hashes, dtype=np.uint64)
    a = np.array(assignment)
    tr, te = h[a == "train"], h[a == "test"]
    if len(tr) == 0 or len(te) == 0:
        return 0
    return int(sum(_popcount(te[i:i + 256, None] ^ tr[None, :]).min(1).__le__(max_dist).sum()
                   for i in range(0, len(te), 256)))
