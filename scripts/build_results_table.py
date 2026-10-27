"""Build the results tables and M1 figures from experiments/*.json (`make results`).

Writes the tables between the RESULTS markers in README.md and to docs/report/results_tables.md.
Nothing here is typed by hand: a missing experiment file produces "RESULT PENDING".
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
FIG = ROOT / "docs" / "figures"
LANG = {"en": "English", "hi": "Hindi (Devanagari)", "hinglish": "Hinglish"}
METHOD = {"keyword": "Keyword overlap (baseline)", "tfidf": "TF-IDF (baseline)",
          "minilm": "Multilingual MiniLM-L12 (primary)", "labse": "LaBSE",
          "hybrid": "TF-IDF + MiniLM hybrid (exploratory, post hoc)"}


def load(name: str) -> dict | None:
    p = EXP / name
    return json.loads(p.read_text()) if p.exists() else None


def ci(v: list) -> str:
    return f"[{v[0]:.2f}, {v[1]:.2f}]"


def m1_tables(kind: str) -> str:
    d = load(f"m1_mapper_{kind}.json")
    title = {"synthetic": "M1 mapper on the SYNTHETIC declaration set (pipeline check, not real workers)",
             "real": "M1 mapper on the team-written declaration set"}[kind]
    if d is None:
        return f"### {title}\n\nRESULT PENDING: `{EXP.name}/m1_mapper_{kind}.json` does not exist yet.\n"
    out = [f"### {title}\n"]
    if d.get("warning"):
        out.append(f"> **{d['warning']}**\n")
    out.append(f"n = {d['n_items']} declarations ({', '.join(f'{LANG[k]} {v}' for k, v in d['n_by_language'].items())}), "
               f"{len(d['packs'])} qualification packs (chance top-1 = {1 / len(d['packs']):.2f}). "
               f"95% bootstrap CIs in brackets. Source: `experiments/m1_mapper_{kind}.json`.\n")
    out.append("| Method | Top-1 | Top-3 | MRR |\n|---|---|---|---|")
    for m, v in d["methods"].items():
        o = v["overall"]
        out.append(f"| {METHOD.get(m, m)} | {o['top1_acc']:.3f} {ci(o['top1_acc_ci95'])} | "
                   f"{o['top3_acc']:.3f} {ci(o['top3_acc_ci95'])} | {o['mrr']:.3f} {ci(o['mrr_ci95'])} |")
    out.append("\n**By language (fairness analysis): top-1 / top-3 / MRR**\n")
    out.append("| Method | " + " | ".join(LANG.values()) + " |\n|---|" + "---|" * len(LANG))
    for m, v in d["methods"].items():
        cells = [f"{s['top1_acc']:.2f} / {s['top3_acc']:.2f} / {s['mrr']:.2f}" for s in v["by_language"].values()]
        out.append(f"| {METHOD.get(m, m)} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def m1_figures() -> None:
    d = load("m1_mapper_synthetic.json")
    if d is None:
        return
    FIG.mkdir(parents=True, exist_ok=True)
    methods = list(d["methods"])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    w = 0.8 / len(methods)
    for k, m in enumerate(methods):
        vals = [d["methods"][m]["by_language"][lg]["top1_acc"] for lg in LANG]
        cis = [d["methods"][m]["by_language"][lg]["top1_acc_ci95"] for lg in LANG]
        err = [[v - c[0] for v, c in zip(vals, cis, strict=True)], [c[1] - v for v, c in zip(vals, cis, strict=True)]]
        ax.bar(np.arange(3) + (k - (len(methods) - 1) / 2) * w, vals, w, yerr=err, capsize=2, label=m)
    ax.axhline(1 / len(d["packs"]), color="grey", ls="--", lw=1, label="chance")
    ax.set_xticks(range(3), list(LANG.values()))
    ax.set_ylabel("Top-1 accuracy")
    ax.set_ylim(0, 1)
    ax.set_title("M1 mapper top-1 accuracy by language, SYNTHETIC declarations (n=150)", fontsize=10)
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(FIG / "m1_top1_by_language.png", dpi=150)
    plt.close(fig)

    titles = {p["nqr_id"]: p["title"].split(" (")[0] for p in d["packs"]}
    for m in ["minilm", "hybrid"]:
        if m not in d["methods"]:
            continue
        conf = d["methods"][m]["confusion_top1"]
        ids = list(conf)
        M = np.array([[conf[g][p] for p in ids] for g in ids])
        fig, ax = plt.subplots(figsize=(5.6, 4.6))
        ax.imshow(M, cmap="Blues")
        for i in range(len(ids)):
            for j in range(len(ids)):
                ax.text(j, i, M[i, j], ha="center", va="center", color="white" if M[i, j] > M.max() / 2 else "black")
        lab = [titles[int(i)][:22] for i in ids]
        ax.set_xticks(range(len(ids)), lab, rotation=35, ha="right", fontsize=8)
        ax.set_yticks(range(len(ids)), lab, fontsize=8)
        ax.set_xlabel("Predicted top-1 pack")
        ax.set_ylabel("Labelled pack")
        ax.set_title(f"M1 confusion ({m}), SYNTHETIC set", fontsize=10)
        fig.tight_layout()
        fig.savefig(FIG / f"m1_confusion_{m}.png", dpi=150)
        plt.close(fig)


def m2_tables() -> str:
    out = ["### M2 evidence reuse detection (perceptual hashing)\n"]
    d = load("m2_hashing.json")
    if d is None:
        out.append("RESULT PENDING: run `make eval-m2`.\n")
    else:
        dd = d["dedupe"]
        out.append(f"{d['data_note']} The test split had {dd['images_in_split']} images but only "
                   f"{dd['distinct_images']} distinct ones after grouping near-identical frames; {d['n_gallery']} "
                   f"stored ('gallery') photos, {d['n_fresh']} fresh photos, {len(d['transforms'])} reuse "
                   f"transformations. Threshold rule: {d['threshold_rule']}; reported on the held-out half. "
                   "Source: `experiments/m2_hashing.json`.\n")
        out.append("| Hash | Threshold (bits of 64) | Precision | Recall | False flags on fresh photos |\n|---|---|---|---|---|")
        for h, v in d["hashes"].items():
            t = v["test"]
            out.append(f"| {h} | {v['chosen_threshold']} | {t['precision']:.3f} | {t['recall']:.3f} | "
                       f"{t['false_flag_rate_fresh']:.3f} |")
        ph = d["hashes"]["phash"]
        out.append(f"\n**pHash recall by kind of reuse** (threshold {ph['chosen_threshold']}):\n")
        out.append("| " + " | ".join(ph["test_recall_by_transform"]) + " |\n|" + "---|" * len(ph["test_recall_by_transform"]))
        out.append("| " + " | ".join(f"{v:.2f}" for v in ph["test_recall_by_transform"].values()) + " |")
        f1 = ph["test_at_max_f1_threshold"]
        out.append(f"\nFor comparison, the max-F1 threshold ({ph['max_f1_threshold_dev']}) would catch more edited "
                   f"copies (recall {f1['recall']:.2f}) but would also flag {f1['false_flag_rate_fresh']:.0%} of "
                   "fresh, unrelated photos, because many site photos look alike.\n")
    out.append("### M2 PPE / tool presence detector (YOLOv8n)\n")
    det = load("m2_detector.json")
    if det is None:
        out.append("RESULT PENDING: train with `notebooks/m2_train_yolo_colab.ipynb` on Colab and copy "
                   "`m2_detector.json` into `experiments/`.\n")
    else:
        out.append(f"Dataset: {det['dataset']}. Leakage: {det['leakage']['near_duplicate_in_train']} of "
                   f"{det['leakage']['test_images']} test images have a near-duplicate in train.\n")
        out.append("| Test set | mAP50 | mAP50-95 | Precision | Recall |\n|---|---|---|---|---|")
        for k in ["test", "test_clean"]:
            r = det[k]
            out.append(f"| {k} | {r['mAP50']:.3f} | {r['mAP50_95']:.3f} | {r['precision']:.3f} | {r['recall']:.3f} |")
    return "\n".join(out) + "\n"


def m4_table() -> str:
    d = load("m4_consistency.json")
    out = ["### M4 inter-assessor consistency study\n"]
    if d is None or d.get("status") == "RESULT PENDING":
        out.append("RESULT PENDING: no real rater scores yet. Rater mode is built; the study needs 3 to 5 real "
                   "assessors and 20 to 30 consented evidence photos.\n")
        return "\n".join(out)
    out.append(f"{len(d['raters'])} raters, {d['n_ratings']} ratings. Source: `experiments/m4_consistency.json`.\n")
    out.append("| Condition | Items | Fleiss' kappa | Krippendorff's alpha (ordinal) | Pairwise exact | Within one level |\n|---|---|---|---|---|---|")
    for c, r in d["conditions"].items():
        if r.get("status"):
            out.append(f"| {c} | 0 | RESULT PENDING | | | |")
            continue
        f = lambda k: "n/a" if r.get(k) is None else f"{r[k]:.3f} {ci(r['ci95'][k]) if k in r['ci95'] else ''}"  # noqa: E731
        out.append(f"| {c} | {r['n_items']} | {f('fleiss_kappa')} | {f('krippendorff_alpha_ordinal')} | "
                   f"{f('pairwise_exact')} | {f('pairwise_within_one')} |")
    if d.get("difference"):
        x = d["difference"]
        out.append(f"\nAssisted minus unassisted alpha: {x['alpha_assisted_minus_unassisted']:.3f} "
                   f"(95% CI {ci(x['ci95']) if x['ci95'] else 'n/a'}, {x['items_in_both']} items).")
    out.append(f"\n{d['limitations']}\n")
    return "\n".join(out)


def main() -> int:
    m1_figures()
    body = "\n".join([m1_tables("real"), m1_tables("synthetic"), m2_tables(), m4_table()])
    (ROOT / "docs" / "report").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "report" / "results_tables.md").write_text(
        "<!-- generated by scripts/build_results_table.py from experiments/*.json; do not edit -->\n\n" + body)
    readme = ROOT / "README.md"
    text = readme.read_text()
    block = f"<!-- RESULTS:START (generated by `make results`, do not edit) -->\n{body}\n<!-- RESULTS:END -->"
    if "<!-- RESULTS:START" in text:
        text = re.sub(r"<!-- RESULTS:START.*?<!-- RESULTS:END -->", lambda _: block, text, flags=re.S)
        readme.write_text(text)
    print("results tables written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
