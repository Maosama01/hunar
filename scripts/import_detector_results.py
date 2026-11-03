"""Bring the Colab detector results into the repo (step 7 of notebooks/m2_train_yolo_colab.ipynb).

    uv run python scripts/import_detector_results.py \\
        --json ~/Downloads/m2_detector.json --weights ~/Downloads/best.pt \\
        [--confusion ~/Downloads/confusion_matrix.png]

Checks the files, copies them to experiments/, data/models/ (gitignored) and docs/figures/, then
rebuilds the README results table and the report. Nothing is edited by hand.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from hunar.evidence.detector import CLASSES, WEIGHTS  # noqa: E402

REQUIRED = {"experiment", "dataset", "classes", "epochs", "imgsz", "leakage", "test", "test_clean", "split"}


def fail(msg: str) -> int:
    print("ERROR:", msg, file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, required=True)
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--confusion", type=Path)
    ap.add_argument("--allow-short-run", action="store_true",
                    help="accept a run with fewer than 10 epochs (it is still recorded with its epoch count)")
    a = ap.parse_args()
    for p in [a.json, a.weights] + ([a.confusion] if a.confusion else []):
        if not p.expanduser().exists():
            return fail(f"{p} not found")
    res = json.loads(a.json.expanduser().read_text())
    if "split" not in res and "test" in res:
        return fail("this run used the dataset's published splits, which are class-disjoint (no helmets in "
                    "train, no gloves in test). It is kept as a diagnostic run, not imported as the result. "
                    "Re-run the current notebook, which re-splits the data.")
    if missing := REQUIRED - set(res):
        return fail(f"{a.json} is missing {sorted(missing)}; is this the m2_detector*.json from the notebook?")
    if res["experiment"] != "m2_detector":
        return fail("not an m2_detector result")
    # Guard against importing a test or partial run as if it were the real result.
    if "smoke" in a.json.name.lower() or "smoke" in json.dumps(res).lower():
        return fail("this looks like a smoke-test file, not a real training run")
    n_test = res["test"].get("n_images") or res["leakage"].get("test_images", 0)
    if n_test < 100:
        return fail(f"only {n_test} test images: the full PPE test split has about 1,900. Not a full run.")
    if res["epochs"] < 10 and not a.allow_short_run:
        return fail(f"only {res['epochs']} epochs; pass --allow-short-run if this was deliberate")
    if unknown := set(res["classes"]) - set(CLASSES):
        return fail(f"classes {sorted(unknown)} are not known to the app (hunar.evidence.detector.CLASSES)")
    try:
        from ultralytics import YOLO
    except ImportError:
        return fail("ultralytics is not installed: run `uv sync --extra vision` first")
    names = set(YOLO(str(a.weights.expanduser())).names.values())
    if names != set(res["classes"]):
        return fail(f"weights classes {sorted(names)} do not match the JSON classes {sorted(res['classes'])}")
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(a.weights.expanduser(), WEIGHTS)
    if missing_cls := [c for s in ("train", "test") for c, n in res["split"]["counts"][s]["boxes"].items() if n == 0]:
        return fail(f"a class has no boxes in train or test: {missing_cls}")
    shutil.copy(a.json.expanduser(), ROOT / "experiments" / "m2_detector.json")
    if a.confusion:
        shutil.copy(a.confusion.expanduser(), ROOT / "docs" / "figures" / "m2_confusion_matrix.png")
    print(f"weights  -> {WEIGHTS.relative_to(ROOT)} (gitignored)")
    print("results  -> experiments/m2_detector.json")
    t = res["test_clean"]
    print(f"clean test: mAP50 {t['mAP50']:.3f}, mAP50-95 {t['mAP50_95']:.3f} "
          f"({res['leakage']['near_duplicate_in_train']} of {res['leakage']['test_images']} test images leaked)")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report.py")], check=True)
    print("README results table and report rebuilt. Review, then commit: git add experiments docs README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
