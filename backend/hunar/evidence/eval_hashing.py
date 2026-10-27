"""M2 evidence-integrity evaluation: does perceptual hashing catch reused photos?

Usage:  python -m hunar.evidence.eval_hashing      (needs scripts/fetch_ppe_test.py first)

Setup (mirrors how the app uses hashing):
* Images: test split of the public PPE dataset (real photos of workers, CC BY 4.0). The split
  itself contains near-identical images (video frames, the same photo at several sizes), so
  images are first grouped with an independent similarity measure and one image per group is
  kept; gallery and fresh photos come from different groups.
* Gallery = photos already stored as evidence. Positive queries = each gallery photo after one
  reuse transformation (recompression, resize, crop, brightness, small rotation, flip, border).
  Negative queries = fresh photos never stored before; any flag on them is a false alarm.
* Operating point: the threshold with the highest recall whose false-flag rate on fresh dev photos
  is at most 5 % (a flag interrupts an assessor, so false alarms must be rare). It is chosen on a
  dev half and reported on the held-out test half. The max-F1 threshold is reported for comparison.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import random
import sys
from pathlib import Path

import imagehash
import matplotlib
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from hunar.paths import DATA, EXPERIMENTS, ROOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

IMG_DIR = DATA / "raw" / "ppe" / "test"
FIG_DIR = ROOT / "docs" / "figures"
MAX_FALSE_FLAG = 0.05
HASHES = {"phash": imagehash.phash, "dhash": imagehash.dhash, "ahash": imagehash.average_hash,
          "whash": imagehash.whash}


def _jpeg(img: Image.Image, q: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _crop(img: Image.Image, keep: float) -> Image.Image:
    w, h = img.size
    dw, dh = int(w * (1 - keep) / 2), int(h * (1 - keep) / 2)
    return img.crop((dw, dh, w - dw, h - dh))


TRANSFORMS = {
    "jpeg_q50": lambda im: _jpeg(im, 50),
    "jpeg_q20": lambda im: _jpeg(im, 20),
    "resize_50pct": lambda im: im.resize((im.width // 2, im.height // 2)),
    "crop_90pct": lambda im: _crop(im, 0.90),
    "crop_75pct": lambda im: _crop(im, 0.75),
    "brightness_+30pct": lambda im: ImageEnhance.Brightness(im).enhance(1.3),
    "rotate_5deg": lambda im: im.rotate(5, expand=False, fillcolor=(0, 0, 0)),
    "border_whatsapp_style": lambda im: _jpeg(ImageOps.expand(im, border=(0, im.height // 8), fill="white"), 70),
    "mirror_flip": ImageOps.mirror,
}


def _thumb(p: Path) -> np.ndarray:
    a = np.asarray(Image.open(p).convert("L").resize((32, 32), Image.BILINEAR), dtype=np.float32).ravel()
    return (a - a.mean()) / (a.std() + 1e-6)


def dedupe(paths: list[Path], corr: float = 0.95) -> tuple[list[list[Path]], int]:
    """Group near-identical images with an independent measure (32x32 grey thumbnail correlation),
    so the evaluation does not use perceptual hashes to clean its own test set."""
    X = np.stack([_thumb(p) for p in paths])
    C = (X @ X.T) / X.shape[1]
    parent = list(range(len(paths)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in zip(*np.where(np.triu(C, 1) >= corr), strict=True):
        parent[find(i)] = find(j)
    groups: dict[int, list[Path]] = {}
    for i, p in enumerate(paths):
        groups.setdefault(find(i), []).append(p)
    return list(groups.values()), sum(len(g) - 1 for g in groups.values())


def load_split(seed: int = 0, gallery_share: float = 0.4):
    """One image per near-duplicate group; gallery and fresh photos come from different groups."""
    paths = sorted(p for p in IMG_DIR.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    groups, n_dups = dedupe(paths)
    reps = [sorted(g)[0] for g in groups]
    random.Random(seed).shuffle(reps)
    n_gallery = int(len(reps) * gallery_share)
    gallery, fresh = reps[:n_gallery], reps[n_gallery:]
    stats = {"images_in_split": len(paths), "near_duplicate_groups": sum(len(g) > 1 for g in groups),
             "images_removed_as_near_duplicates": n_dups, "distinct_images": len(reps)}
    return gallery, fresh, stats


def nearest_distances(query_hashes, gallery_hashes) -> np.ndarray:
    g = np.array([h.hash.flatten() for h in gallery_hashes])
    q = np.array([h.hash.flatten() for h in query_hashes])
    return (q[:, None, :] != g[None, :, :]).sum(axis=2)  # [n_query, n_gallery] Hamming distances


def metrics_at(t: int, pos_d: np.ndarray, pos_correct: np.ndarray, neg_d: np.ndarray) -> dict:
    """pos_d / neg_d: distance to the nearest gallery photo; pos_correct: nearest is the true source."""
    tp = int(np.sum((pos_d <= t) & pos_correct))
    wrong = int(np.sum((pos_d <= t) & ~pos_correct))  # flagged, but against the wrong photo
    fp = int(np.sum(neg_d <= t)) + wrong
    fn = len(pos_d) - tp
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / len(pos_d)
    return {"threshold": t, "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
            "false_flag_rate_fresh": round(float(np.mean(neg_d <= t)), 4), "tp": tp, "fp": fp, "fn": fn}


def run(seed: int = 0) -> dict:
    if not IMG_DIR.exists():
        print("missing data/raw/ppe/test: run `uv run python scripts/fetch_ppe_test.py`", file=sys.stderr)
        sys.exit(1)
    gallery, fresh, dedupe_stats = load_split(seed)
    print("dedupe:", dedupe_stats)
    half_g, half_f = len(gallery) // 2, len(fresh) // 2
    splits = {"dev": (gallery[:half_g], fresh[:half_f]), "test": (gallery[half_g:], fresh[half_f:])}
    imgs = {p: Image.open(p).convert("RGB") for p in gallery + fresh}
    result = {
        "experiment": "m2_hashing", "data_kind": "real_images_synthetic_reuse",
        "data_note": ("Real photos from the public PPE dataset (CC BY 4.0, test split); reuse is simulated by "
                      "image transformations. Not photos from our own assessments."),
        "dataset": "keremberke/protective-equipment-detection (Roboflow PPE v7), test split",
        "n_gallery": len(gallery), "n_fresh": len(fresh), "dedupe": dedupe_stats, "transforms": list(TRANSFORMS),
        "command": "python -m hunar.evidence.eval_hashing", "seed": seed,
        "created": dt.datetime.now().isoformat(timespec="seconds"), "hashes": {},
        "threshold_rule": f"max recall s.t. false-flag rate on fresh dev photos <= {MAX_FALSE_FLAG}",
    }
    curves = {}
    for hname, hfn in HASHES.items():
        per_split = {}
        for split, (gal, fr) in splits.items():
            gh = [hfn(imgs[p]) for p in gal]
            pos_q, pos_src, pos_tf = [], [], []
            for i, p in enumerate(gal):
                for tname, tf in TRANSFORMS.items():
                    pos_q.append(hfn(tf(imgs[p])))
                    pos_src.append(i)
                    pos_tf.append(tname)
            D_pos = nearest_distances(pos_q, gh)
            D_neg = nearest_distances([hfn(imgs[p]) for p in fr], gh)
            per_split[split] = {"pos_d": D_pos.min(1), "pos_correct": D_pos.argmin(1) == np.array(pos_src),
                                "pos_tf": np.array(pos_tf), "neg_d": D_neg.min(1)}
        dev, test = per_split["dev"], per_split["test"]
        grid = [metrics_at(t, dev["pos_d"], dev["pos_correct"], dev["neg_d"]) for t in range(0, 33)]
        ok = [m for m in grid if m["false_flag_rate_fresh"] <= MAX_FALSE_FLAG]
        best = max(ok, key=lambda m: (m["recall"], -m["threshold"])) if ok else grid[0]
        t = best["threshold"]
        f1_best = max(grid, key=lambda m: (m["f1"], -m["threshold"]))
        test_m = metrics_at(t, test["pos_d"], test["pos_correct"], test["neg_d"])
        per_tf = {tn: round(float(np.mean((test["pos_d"][test["pos_tf"] == tn] <= t)
                                          & test["pos_correct"][test["pos_tf"] == tn])), 4) for tn in TRANSFORMS}
        curves[hname] = [metrics_at(k, test["pos_d"], test["pos_correct"], test["neg_d"]) for k in range(0, 33)]
        result["hashes"][hname] = {"chosen_threshold": t, "dev_at_threshold": best,
                                   "max_f1_threshold_dev": f1_best["threshold"],
                                   "test_at_max_f1_threshold": metrics_at(f1_best["threshold"], test["pos_d"],
                                                                         test["pos_correct"], test["neg_d"]),
                                   "test": test_m,
                                   "test_recall_by_transform": per_tf}
        print(f"{hname}: t={t:2d}  test P={test_m['precision']:.3f} R={test_m['recall']:.3f} "
              f"F1={test_m['f1']:.3f} false-flag(fresh)={test_m['false_flag_rate_fresh']:.3f}")
    result["chosen_hash"] = "phash"
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "m2_hashing.json").write_text(json.dumps(result, indent=2) + "\n")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for hname, pts in curves.items():
        ax.plot([p["recall"] for p in pts], [p["precision"] for p in pts], marker=".", label=hname)
        c = result["hashes"][hname]["test"]
        ax.scatter([c["recall"]], [c["precision"]], s=60, edgecolor="k", zorder=3)
    ax.set_xlabel("Recall (reused photos flagged)")
    ax.set_ylabel("Precision")
    ax.set_title("Evidence reuse detection, held-out test half\n(real PPE photos, simulated reuse)", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "m2_hashing_pr.png", dpi=150)
    return result


if __name__ == "__main__":
    run()
