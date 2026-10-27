"""M1 evaluation: top-1 / top-3 accuracy and MRR, overall and per language, with bootstrap CIs.

Usage:  python -m hunar.mapper.evaluate [--methods keyword tfidf minilm labse]

Datasets:
* data/labels/declarations.csv            team-written declarations ("real" data kind)
* data/synthetic/declarations_synthetic.csv  AI-written declarations ("synthetic" data kind)

Each dataset is evaluated separately and written to experiments/m1_mapper_<kind>.json plus a
per-item predictions CSV for the error analysis notebook. Ties are scored as a uniformly random
order among the tied packs (expected value), so an all-zero score vector earns chance credit only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from hunar.mapper.mapper import QPMapper, load_packs
from hunar.mapper.text import split_sentences
from hunar.paths import DATA, EXPERIMENTS, ROOT

DATASETS = {
    "real": DATA / "labels" / "declarations.csv",
    "synthetic": DATA / "synthetic" / "declarations_synthetic.csv",
}
LANGS = ["en", "hi", "hinglish"]


def tie_aware(scores: np.ndarray, gold: int) -> dict:
    """Expected top-1, top-3 and reciprocal rank when tied packs are ordered at random."""
    g = scores[gold]
    better = int(np.sum(scores > g + 1e-9))
    tied = int(np.sum(np.isclose(scores, g, atol=1e-9)))
    ranks = np.arange(better + 1, better + tied + 1)
    return {
        "top1": float(np.mean(ranks <= 1)),
        "top3": float(np.mean(ranks <= 3)),
        "rr": float(np.mean(1.0 / ranks)),
        "rank": float(np.mean(ranks)),
    }


def bootstrap_ci(values: np.ndarray, n: int = 2000, seed: int = 0) -> list[float]:
    if len(values) == 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def summarise(rows: list[dict]) -> dict:
    out = {"n": len(rows)}
    for k, name in [("top1", "top1_acc"), ("top3", "top3_acc"), ("rr", "mrr")]:
        vals = np.array([r[k] for r in rows])
        out[name] = round(float(vals.mean()), 4) if len(vals) else None
        out[name + "_ci95"] = bootstrap_ci(vals)
    return out


def load_dataset(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("text", "").strip()]


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def evaluate(kind: str, items: list[dict], methods: list[str]) -> dict:
    packs = load_packs()
    ids = [p.nqr_id for p in packs]
    result = {
        "experiment": "m1_mapper",
        "data_kind": kind,
        "dataset": str(DATASETS[kind].relative_to(ROOT)),
        "n_items": len(items),
        "n_by_language": {lang: sum(r["language"] == lang for r in items) for lang in LANGS},
        "packs": [{"nqr_id": p.nqr_id, "title": p.title, "role": p.role} for p in packs],
        "aggregation": "pack score = mean over declaration units of max similarity to the pack's core PCs",
        "tie_handling": "expected value under random order of tied packs",
        "command": "python -m hunar.mapper.evaluate",
        "git_commit": git_commit(),
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "methods": {},
        "exploratory_methods": {"hybrid": "designed after seeing the first synthetic results; not a confirmed result"},
    }
    if kind == "synthetic":
        result["warning"] = ("SYNTHETIC DATA: declarations written by an AI model, not by workers. "
                             "These numbers check the pipeline; they are not evidence about real workers.")
    pred_rows = []
    for method in methods:
        mapper = QPMapper(method, packs=packs)
        per_item = []
        confusion = {str(g): {str(p): 0 for p in ids} for g in ids}
        for r in items:
            gold = ids.index(int(r["label_nqr_id"]))
            scores, _ = mapper.pack_scores(split_sentences(r["text"]))
            m = tie_aware(scores, gold)
            top = ids[int(np.argmax(scores))] if scores.max() > 0 else None
            if top is not None:
                confusion[str(ids[gold])][str(top)] += 1
            per_item.append({**m, "language": r["language"]})
            pred_rows.append({"id": r["id"], "method": method, "language": r["language"],
                              "gold": ids[gold], "pred_top1": top if top is not None else "",
                              "expected_rank": round(m["rank"], 2), "rr": round(m["rr"], 4),
                              "scores": json.dumps({str(i): round(float(s), 4) for i, s in zip(ids, scores, strict=True)}),
                              "text": r["text"]})
        result["methods"][method] = {
            "overall": summarise(per_item),
            "by_language": {lang: summarise([p for p in per_item if p["language"] == lang]) for lang in LANGS},
            "confusion_top1": confusion,
        }
        o = result["methods"][method]["overall"]
        print(f"[{kind}] {method:8s} top1={o['top1_acc']:.3f} top3={o['top3_acc']:.3f} mrr={o['mrr']:.3f} (n={o['n']})")
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / f"m1_mapper_{kind}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    with (EXPERIMENTS / f"m1_predictions_{kind}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(pred_rows[0].keys()))
        w.writeheader()
        w.writerows(pred_rows)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=["keyword", "tfidf", "minilm", "labse", "hybrid"])
    args = ap.parse_args(argv)
    ran = False
    for kind, path in DATASETS.items():
        items = load_dataset(path)
        if not items:
            print(f"[{kind}] {path.relative_to(ROOT)}: no labelled items yet -> RESULT PENDING")
            continue
        evaluate(kind, items, args.methods)
        ran = True
    return 0 if ran else 1


if __name__ == "__main__":
    sys.exit(main())
