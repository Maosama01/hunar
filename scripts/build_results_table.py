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
        out.append(f"\n**pHash recall by kind of reuse** (threshold {ph['chosen_threshold']}, held-out half):\n")
        out.append("| Reuse transformation | Recall |\n|---|---|")
        out += [f"| {k.replace('_', ' ')} | {v:.2f} |" for k, v in ph["test_recall_by_transform"].items()]
        f1 = ph["test_at_max_f1_threshold"]
        out.append(f"\nFor comparison, the max-F1 threshold ({ph['max_f1_threshold_dev']}) would catch more edited "
                   f"copies (recall {f1['recall']:.2f}) but would also flag {f1['false_flag_rate_fresh']:.0%} of "
                   "fresh, unrelated photos, because many site photos look alike.\n")
    out.append("### M2 PPE / tool presence detector (YOLOv8n)\n")
    det = load("m2_detector.json")
    if det is None:
        out.append("RESULT PENDING: train with `notebooks/m2_train_yolo_colab.ipynb` on Colab, then bring the "
                   "results back with `scripts/import_detector_results.py` (see `docs/m2_colab_walkthrough.md`).\n")
    else:
        out.append(f"Dataset: {det['dataset']}. Leakage: {det['leakage']['near_duplicate_in_train']} of "
                   f"{det['leakage']['test_images']} test images have a near-duplicate in train.\n")
        if det.get("split"):
            out.append(f"Trained and tested on the re-split data ({det['split']['method']}). Boxes per class:\n")
            out += _boxes_table(det["split"]["counts"]) + [""]
        out.append(f"YOLOv8n, {det['epochs']} epochs, image size {det['imgsz']}, ultralytics "
                   f"{det.get('ultralytics_version', '?')}. Source: `experiments/m2_detector.json`. "
                   "**Presence only: the model does not judge workmanship.**\n")
        out.append("| Test set | Images | mAP50 | mAP50-95 | Precision | Recall |\n|---|---|---|---|---|---|")
        names = {"test": "full test split", "test_clean": "clean test (no near-duplicate in train)"}
        for k in ["test", "test_clean"]:
            r = det[k]
            out.append(f"| {names[k]} | {r.get('n_images', '?')} | {r['mAP50']:.3f} | {r['mAP50_95']:.3f} | "
                       f"{r['precision']:.3f} | {r['recall']:.3f} |")
        out.append("\n**Per class, clean test set**\n")
        out.append("| Class | Precision | Recall | mAP50 | mAP50-95 |\n|---|---|---|---|---|")
        for c, v in det["test_clean"]["per_class"].items():
            out.append(f"| {c} | {v['precision']:.3f} | {v['recall']:.3f} | {v['mAP50']:.3f} | {v['mAP50_95']:.3f} |")
    out.append(split_table())
    out.append(run1_diagnostic())
    return "\n".join(out) + "\n"


def _boxes_table(counts: dict) -> list[str]:
    classes = list(next(iter(counts.values()))["boxes"])
    rows = ["| Split | Images | " + " | ".join(classes) + " |", "|---|---|" + "---|" * len(classes)]
    for s in ("train", "valid", "test"):
        c = counts[s]
        rows.append(f"| {s} | {c['images']} | " + " | ".join(str(c["boxes"][k]) for k in classes) + " |")
    return rows


def split_table() -> str:
    d = load("m2_ppe_split.json")
    if d is None:
        return ""
    r = d["resplit"]
    out = ["\n**Training data splits (boxes per class).** The dataset's published splits are class-disjoint, "
           "so a group-aware, class-stratified re-split is used. Source: `experiments/m2_ppe_split.json`.\n",
           "Published splits:\n", *_boxes_table(d["published_splits"]),
           f"\nTest images with a near-duplicate (<= 4 bits) in train, published splits: "
           f"{d['published_test_with_near_duplicate_in_train_4bits']}.\n",
           f"Re-split ({r['method']}; {r['n_groups']} groups, largest {r['largest_group']} images):\n",
           *_boxes_table(r["counts"]),
           f"\nTest images with a near-duplicate (<= 4 bits) in train, re-split: "
           f"{r['test_with_near_duplicate_in_train_4bits']}.\n"]
    return "\n".join(out)


def run1_diagnostic() -> str:
    d = load("m2_detector_run1_published_splits.json")
    if d is None:
        return ""
    t, c = d["test"], d["test_clean"]
    pc = c["per_class"]
    rows = " | ".join(f"{k} mAP50 {v['mAP50']:.3f}" for k, v in pc.items())
    return ("\n**Diagnostic first run on the published splits (not the detector result).** "
            f"YOLOv8n, {d['epochs']} epochs, ultralytics {d.get('ultralytics_version', '?')}. "
            f"Full test mAP50 {t['mAP50']:.3f}, clean test ({c['n_images']} images) mAP50 {c['mAP50']:.3f}; "
            f"per class on the clean test: {rows}. Helmet scores 0 because the published training split "
            "contains no helmet boxes; gloves cannot be scored because the published test split contains none; "
            "safety shoes had very few training boxes. Only the goggles figure measures what the model learned. "
            "Source: `experiments/m2_detector_run1_published_splits.json`; confusion matrix: "
            "`docs/figures/m2_run1_confusion_matrix.png`.\n")


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
        f = lambda k, r=r: "n/a" if r.get(k) is None else f"{r[k]:.3f} {ci(r['ci95'][k]) if k in r['ci95'] else ''}"  # noqa: E731
        out.append(f"| {c} | {r['n_items']} | {f('fleiss_kappa')} | {f('krippendorff_alpha_ordinal')} | "
                   f"{f('pairwise_exact')} | {f('pairwise_within_one')} |")
    if d.get("difference"):
        x = d["difference"]
        out.append(f"\nAssisted minus unassisted alpha: {x['alpha_assisted_minus_unassisted']:.3f} "
                   f"(95% CI {ci(x['ci95']) if x['ci95'] else 'n/a'}, {x['items_in_both']} items).")
    out.append(f"\n{d['limitations']}\n")
    return "\n".join(out)


def voice_table() -> str:
    d = load("m1_voice_synthetic.json")
    title = "### M1 voice input on SYNTHETIC speech (pipeline check, not real workers)\n"
    if d is None:
        return title + "\nNot run yet: `make voice eval-voice` (macOS).\n"
    sp = d["speed"]
    out = [title, f"> **{d['warning']}**\n",
           f"{d['n_items']} AI-written declarations read by macOS text-to-speech, transcribed with faster-whisper "
           f"{d['asr']['model']} (CPU, int8), then mapped with {METHOD.get(d['mapper'], d['mapper'])}. Transcription took "
           f"{sp['real_time_factor']:.2f} s per second of audio on this laptop ({d['machine']}; not a controlled "
           "benchmark). Error rates count "
           "words or characters wrong per reference word or character; digits are not spelled out. "
           "Source: `experiments/m1_voice_synthetic.json`.\n",
           "| Language | n | Word error rate | Character error rate | Top-1 typed | Top-1 spoken | "
           "Top-1 changed (right to wrong / wrong to right) |\n|---|---|---|---|---|---|---|"]
    for lang, e in d["by_language"].items():
        wer = f"{e['corpus_wer']:.2f}" if "corpus_wer" in e else "n/a (script)"
        cer = f"{e['corpus_cer']:.2f}" if "corpus_cer" in e else "n/a (script)"
        t, sp_ = e["mapping_typed"], e["mapping_spoken"]
        out.append(f"| {LANG[lang]} | {e['n']} | {wer} | {cer} | {t['top1_acc']:.2f} {ci(t['top1_acc_ci95'])} | "
                   f"{sp_['top1_acc']:.2f} {ci(sp_['top1_acc_ci95'])} | {e['top1_changed_by_transcription']} "
                   f"({e['top1_right_to_wrong']} / {e['top1_wrong_to_right']}) |")
    return "\n".join(out) + "\n"


def m4_design_table() -> str:
    d = load("m4_design_simulation.json")
    title = "### M4 study design (SIMULATION OF THE METHOD, not a result)\n"
    if d is None:
        return title + "\nNot run yet: `make design-sim`.\n"
    a = d["assumptions"]
    out = [title, f"> **{d['warning']}**\n",
           f"Share of {d['reps_per_cell']} simulated studies per cell in which the 95% CI of the assisted-minus-"
           f"unassisted Krippendorff alpha excludes 0, assuming alpha {a['population_alpha_unassisted']:.2f} without "
           "the rubric. The no-effect row checks the method: it should stay near 0.025. "
           "Source: `experiments/m4_design_simulation.json`; figure `docs/figures/m4_design_power.png`.\n"]
    scen = list(d["scenarios"].values())
    out.append("| Raters | Items | " + " | ".join(f"with rubric {sc['population_alpha_assisted']:.2f}" for sc in scen)
               + " |\n|---|---|" + "---|" * len(scen))
    for k, c in enumerate(scen[0]["cells"]):
        out.append(f"| {c['raters']} | {c['items']} | " + " | ".join(f"{sc['cells'][k]['detected_share']:.2f}"
                                                               for sc in scen) + " |")
    return "\n".join(out) + "\n"


def quiz_tables() -> str:
    d = load("quiz_cat_simulation.json")
    out = ["### Worker quiz: design check (SIMULATION OF THE METHOD, not a result)\n"]
    if d is None:
        out.append("Not run yet: `make quiz-sim`.\n")
    else:
        r = d["rules"]
        out += [f"> **{d['warning']}**\n",
                f"{d['n_simulated_per_cell']} simulated workers per cell, ability ~ N(0, 1). Adaptive quiz: Rasch model, "
                f"EAP scoring, stop at posterior SD <= {r['se_target']} after {r['min_items']} items or at "
                f"{r['max_items']} items; compared with a fixed {d['fixed_length']}-item quiz. Scenarios: difficulties "
                "as estimated (*calibrated*), off by N(0, 0.7²) logits (*cold start*), and cold start with a 0.2 "
                "guessing floor. Coverage = share of 90% intervals containing the true ability. "
                "Source: `experiments/quiz_cat_simulation.json`; figure `docs/figures/quiz_cat_simulation.png`.\n",
                "| Trade | Scenario | Questions (adaptive / fixed) | RMSE (adaptive / fixed) | 90% coverage (adaptive / fixed) |"
                "\n|---|---|---|---|---|"]
        for t, td in d["trades"].items():
            for sc, v in td["scenarios"].items():
                a, f = v["adaptive"], v["fixed"]
                out.append(f"| {t} | {sc.replace('_', ' ')} | {a['mean_items']:.1f} / {f['mean_items']:.0f} | "
                           f"{a['rmse']:.2f} / {f['rmse']:.2f} | {a['coverage90']:.2f} / {f['coverage90']:.2f} |")
        out.append("")
    cal = []
    for f in sorted(EXP.glob("quiz_calibration_*.json")):
        c = json.loads(f.read_text())
        state = (f"RESULT PENDING ({c['n_attempts']} finished real attempts; {c['min_attempts']} needed)"
                 if c["status"] == "RESULT PENDING" else
                 f"calibrated from {c['n_attempts']} attempts, {c['items_updated']} items updated "
                 f"(version {c['params_version']})")
        cal.append(f"| {c['trade']} | {state} |")
    out.append("### Worker quiz: calibration from real answers\n")
    out.append("| Trade | Status |\n|---|---|\n" + "\n".join(cal) + "\n" if cal else
               "RESULT PENDING: `make quiz-calibrate` has not been run.\n")
    return "\n".join(out)


def video_table() -> str:
    d = load("video_detector.json")
    title = "### Video pilot: frame check on hand-labelled frames\n"
    if d is None:
        return (title + "\nRESULT PENDING: no labelled frames yet. Record guided clips, run `make clip-frames`, "
                "label `data/labels/clip_frames.csv`, then `make eval-clips`.\n")
    out = [title]
    if d["data_kind"] != "real":
        out.append("> **Pipeline check on SAMPLE / synthetic frames, not evidence about real workers.**\n")
    out += [f"{d['n_frames']} frames from {d['n_clips']} clips, {d['detector']} at confidence {d['confidence_threshold']}. "
            f"{d['note']} Source: `experiments/video_detector.json`.\n",
            "| Check | n | Positives | Precision | Recall | Accuracy |\n|---|---|---|---|---|---|"]
    for key, name in (("part_present", "Part present"), ("hand_on_part", "Hand on the part")):
        e = d[key]
        fmt = lambda v, c: "n/a" if v is None else f"{v:.2f} {ci(c) if c else ''}".strip()  # noqa: E731
        out.append(f"| {name} | {e['n']} | {e['positives']} | {fmt(e['precision'], e['precision_ci95'])} | "
                   f"{fmt(e['recall'], e['recall_ci95'])} | {fmt(e['accuracy'], None)} |")
    return "\n".join(out) + "\n"


def main() -> int:
    m1_figures()
    body = "\n".join([m1_tables("real"), m1_tables("synthetic"), voice_table(), m2_tables(), video_table(), m4_table(),
                      m4_design_table(), quiz_tables()])
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
