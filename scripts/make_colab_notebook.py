"""Generate notebooks/m2_train_yolo_colab.ipynb (`make notebook`).

The re-split code is embedded verbatim from backend/hunar/evidence/ppe_split.py, so Colab runs
exactly the code covered by tests/test_ppe_split.py.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
SPLIT_SRC = (ROOT / "backend" / "hunar" / "evidence" / "ppe_split.py").read_text()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
md("""# Hunar M2: train the PPE / tool presence detector (YOLOv8n) on Google Colab

**Run on Colab with a GPU** (Runtime → Change runtime type → T4/L4/A100). Inference later runs on CPU in the app.

**What this model does and does not do.** It detects whether PPE (helmet, gloves, safety shoes, goggles) and, once the team adds labelled photos, electrician tools are *visible* in a task photo. It does **not** judge the quality of the work. Every number this notebook prints reaches the repo only through the generated `m2_detector.json`, never typed by hand.

**Data.** *Personal Protective Equipment* dataset (Roboflow export v7, 11,978 images, **CC BY 4.0**), mirrored on Hugging Face as `keremberke/protective-equipment-detection`. Attribution is in `docs/DATA.md`.

**Why this notebook re-splits the data (run 2).** The dataset's published splits are class-disjoint: the training split has no helmet boxes and the test split has no glove boxes, so run 1 could not learn helmets or test gloves. Step 2 pools all images, groups near-identical video frames, and makes a class-stratified, group-aware train/valid/test split, so every class is in every split and no scene straddles train and test."""),
code("""!nvidia-smi -L || echo "No GPU: training will be very slow"
%pip -q install "ultralytics==8.3.228" imagehash
import ultralytics; ultralytics.checks()"""),
md("""## 0. Keep the training run safe (recommended)

Colab can disconnect. Saving runs to Google Drive means the weights survive; if it disconnects,
re-run cells 0 to 2 and then the **resume** cell in step 5 instead of starting again."""),
code("""USE_DRIVE = True   # set False to keep everything in the temporary /content disk
if USE_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")
    RUNS = "/content/drive/MyDrive/hunar_runs"
else:
    RUNS = "/content/runs"
RUN_NAME = "hunar_ppe_v2_resplit"   # run 1 (published splits) stays untouched in RUNS/hunar_ppe
print("runs will be saved in", RUNS, "as", RUN_NAME)"""),
md("## 1. Download the dataset (train / valid / test, COCO format)"),
code("""import os, zipfile, urllib.request, json, hashlib, datetime, pathlib, shutil
BASE = "https://huggingface.co/datasets/keremberke/protective-equipment-detection/resolve/main/data/"
ROOT = pathlib.Path("/content/ppe"); ROOT.mkdir(exist_ok=True)
for split in ["train", "valid", "test"]:
    z = ROOT / f"{split}.zip"
    if not z.exists():
        urllib.request.urlretrieve(BASE + f"{split}.zip", z)
    if not (ROOT / split).exists():
        zipfile.ZipFile(z).extractall(ROOT / split)
    print(split, sum(1 for _ in (ROOT / split).glob("*.jpg")), "images")"""),
md("""## 2. Re-split: pool, group near-identical frames, stratify by class

The next cell is `backend/hunar/evidence/ppe_split.py` from the repo, copied verbatim (it is unit-tested there). Labels are mapped to Hunar class names: `helmet→helmet`, `glove→gloves`, `shoes→safety_shoes`, `goggles→goggles`; `no_*` and `mask` are dropped. The dataset has no high-visibility vests, so `vest` is not trained."""),
code(SPLIT_SRC.replace("from __future__ import annotations\n", "")),
code("""pool = load_pool(ROOT)
print(len(pool), "images pooled; hashing (a few minutes)...")
hashes = [phash64(r["path"]) for r in pool]
MAX_DIST, SEED = 4, 0
groups = group_near_duplicates(hashes, MAX_DIST)
assignment = stratified_group_split(pool, groups, seed=SEED)
SPLIT = {"method": f"pHash groups (single linkage, <= {MAX_DIST} bits), iterative stratification over groups (rarest class first, targets train/valid/test 0.70/0.15/0.15, ties to test), seed {SEED}",
         "n_groups": int(len(set(groups.tolist()))),
         "counts": class_counts(pool, assignment),
         "published_counts": class_counts(pool, [r["published_split"] for r in pool]),
         "test_with_near_duplicate_in_train_4bits": cross_split_near_duplicates(hashes, assignment, 4)}
for s in ("train", "valid", "test"):
    print(f"{s:5s}", SPLIT["counts"][s])
missing = [(s, c) for s in ("train", "valid", "test") for c in NAMES if SPLIT["counts"][s]["boxes"][c] == 0]
assert not missing, f"a class is missing from a split: {missing}"

YOLO = pathlib.Path("/content/yolo")
shutil.rmtree(YOLO, ignore_errors=True)
for r, s in zip(pool, assignment):
    (YOLO / s / "images").mkdir(parents=True, exist_ok=True)
    (YOLO / s / "labels").mkdir(parents=True, exist_ok=True)
    os.symlink(r["path"], YOLO / s / "images" / r["name"])
    (YOLO / s / "labels" / (pathlib.Path(r["name"]).stem + ".txt")).write_text("\\n".join(r["labels"]))
print("YOLO folders written:", {s: sum(1 for _ in (YOLO / s / "images").iterdir()) for s in ("train", "valid", "test")})"""),
md("""## 3. (Optional, recommended) add the team's electrician-tool photos

Label ~150 photos in Label Studio / CVAT / Roboflow with classes `multimeter`, `tester_screwdriver`, `wire_stripper`, `insulated_pliers`, export in **YOLO format**, zip it as `hunar_tools.zip` with `images/` and `labels/` folders whose class ids follow the order below, and upload it to `/content`. Only photos taken **with written consent** (`docs/consent_form.md`) and with faces blurred. Skip this cell if you have none yet."""),
code("""TOOL_NAMES = ["multimeter", "tester_screwdriver", "wire_stripper", "insulated_pliers"]
tools_zip = pathlib.Path("/content/hunar_tools.zip")
if tools_zip.exists():
    import random
    t = pathlib.Path("/content/tools"); zipfile.ZipFile(tools_zip).extractall(t)
    imgs = sorted((t / "images").glob("*"))
    random.Random(0).shuffle(imgs)
    n = len(imgs); parts = {"train": imgs[: int(.7*n)], "valid": imgs[int(.7*n): int(.85*n)], "test": imgs[int(.85*n):]}
    for split, files in parts.items():
        for f in files:
            shutil.copy(f, YOLO / split / "images" / f.name)
            lab = (t / "labels" / (f.stem + ".txt")).read_text().splitlines()
            # shift tool class ids after the PPE classes
            lab = [f"{int(l.split()[0]) + len(NAMES)} {' '.join(l.split()[1:])}" for l in lab if l.strip()]
            (YOLO / split / "labels" / (f.stem + ".txt")).write_text("\\n".join(lab))
    NAMES = NAMES + TOOL_NAMES
    print("added", n, "team tool photos; classes:", NAMES)
else:
    print("no team tool photos: training PPE classes only")"""),
md("""## 4. Leakage check: near-duplicate frames between train and test

An independent check of step 2: a test image is *leaked* if some training image is within Hamming distance 4. After the group-aware split this should be 0 or close to it. mAP is reported on the full test split and on the clean subset."""),
code("""import imagehash
from PIL import Image
import numpy as np
def phashes(split):
    return {p.name: imagehash.phash(Image.open(p).convert("RGB")) for p in (YOLO / split / "images").iterdir()}
train_h = phashes("train"); test_h = phashes("test")
T = np.array([h.hash.flatten() for h in train_h.values()])
leaked = []
for name, h in test_h.items():
    d = (T != h.hash.flatten()).sum(1).min()
    if d <= 4:
        leaked.append(name)
print(f"{len(leaked)} of {len(test_h)} test images have a near-duplicate in train ({len(leaked)/len(test_h):.1%})")
clean = YOLO / "test_clean"
for sub in ["images", "labels"]:
    (clean / sub).mkdir(parents=True, exist_ok=True)
for p in (YOLO / "test" / "images").iterdir():
    if p.name not in leaked:
        dst = clean / "images" / p.name
        if not dst.exists():
            os.symlink(os.path.realpath(p), dst)
        lab = YOLO / "test" / "labels" / (p.stem + ".txt")
        (clean / "labels" / lab.name).write_text(lab.read_text())
print("clean test images:", sum(1 for _ in (clean / "images").iterdir()))"""),
md("## 5. Train YOLOv8n"),
code("""import yaml
cfg = {"path": str(YOLO), "train": "train/images", "val": "valid/images", "test": "test/images",
       "names": {i: n for i, n in enumerate(NAMES)}}
yaml.safe_dump(cfg, open(YOLO / "data.yaml", "w"))
cfg_clean = dict(cfg, test="test_clean/images"); yaml.safe_dump(cfg_clean, open(YOLO / "data_clean.yaml", "w"))

from ultralytics import YOLO as Y
# Ultralytics prints the time per epoch after the first epoch: multiply by EPOCHS to estimate the total.
# If time is short, lower EPOCHS (e.g. 30) and say so in the report; the value is saved in the results.
EPOCHS = 50
model = Y("yolov8n.pt")
model.train(data=str(YOLO / "data.yaml"), epochs=EPOCHS, imgsz=640, batch=32, seed=0, deterministic=True,
            project=RUNS, name=RUN_NAME, exist_ok=True)"""),
md("""**Only if Colab disconnected during training:** re-run cells 0 to 2 (mount, download, re-split) and
step 4 (leakage), then run this cell instead of the one above. It continues from the last saved epoch."""),
code("""# from ultralytics import YOLO as Y
# model = Y(f"{RUNS}/{RUN_NAME}/weights/last.pt")
# model.train(resume=True)"""),
md("## 6. Evaluate on the test split and on the clean test split; write `m2_detector.json`"),
code("""best = f"{RUNS}/{RUN_NAME}/weights/best.pt"
m = Y(best)
def evaluate(data_yaml, name):
    r = m.val(data=data_yaml, split="test", imgsz=640, batch=32, plots=True, project=RUNS,
              name=f"{RUN_NAME}_{name}", exist_ok=True)
    per_class = {}
    for i, c in enumerate(r.box.ap_class_index):
        p, rc, ap50, ap = r.box.class_result(i)
        per_class[NAMES[int(c)]] = {"precision": round(float(p), 4), "recall": round(float(rc), 4),
                                    "mAP50": round(float(ap50), 4), "mAP50_95": round(float(ap), 4)}
    try:
        cm = r.confusion_matrix.matrix.astype(int).tolist()
    except AttributeError:
        cm = None
    n_imgs = len(list((YOLO / ("test" if name == "eval_test" else "test_clean") / "images").iterdir()))
    return {"n_images": n_imgs, "mAP50": round(float(r.box.map50), 4), "mAP50_95": round(float(r.box.map), 4),
            "precision": round(float(r.box.mp), 4), "recall": round(float(r.box.mr), 4), "per_class": per_class,
            "confusion_matrix": cm}

result = {
    "experiment": "m2_detector", "data_kind": "real_public_dataset", "run": RUN_NAME,
    "dataset": "keremberke/protective-equipment-detection (Roboflow PPE v7, CC BY 4.0), re-split" +
               (" + team tool photos" if tools_zip.exists() else ""),
    "classes": NAMES, "model": "yolov8n", "epochs": EPOCHS, "imgsz": 640, "seed": 0,
    "ultralytics_version": ultralytics.__version__,
    "command": "notebooks/m2_train_yolo_colab.ipynb on Google Colab", "created": datetime.datetime.now().isoformat(timespec="seconds"),
    "split": SPLIT,
    "leakage": {"test_images": len(test_h), "near_duplicate_in_train": len(leaked)},
    "test": evaluate(str(YOLO / "data.yaml"), "eval_test"),
    "test_clean": evaluate(str(YOLO / "data_clean.yaml"), "eval_test_clean"),
    "note": "Presence detection only; the model does not judge workmanship quality.",
}
json.dump(result, open("/content/m2_detector_v2.json", "w"), indent=2)
json.dump(result, open(f"{RUNS}/m2_detector_v2.json", "w"), indent=2)  # second copy next to the weights
print(json.dumps({k: result[k] for k in ["leakage"]}, indent=1))
print("test     mAP50 %.3f  mAP50-95 %.3f" % (result["test"]["mAP50"], result["test"]["mAP50_95"]))
print("clean    mAP50 %.3f  mAP50-95 %.3f" % (result["test_clean"]["mAP50"], result["test_clean"]["mAP50_95"]))
for c, v in result["test_clean"]["per_class"].items():
    print(f"  {c:13s} mAP50 {v['mAP50']:.3f}  recall {v['recall']:.3f}")"""),
md("""## 7. Bring the results back to the repo

The next cell downloads `m2_detector_v2.json`, `best.pt` and the clean-test confusion matrix. On the laptop, from the repo folder:

```
make vision
make import-detector
```

`make import-detector` takes the newest `m2_detector*.json`, `best*.pt` and `confusion_matrix*.png` in `~/Downloads`, checks them, copies them into place and rebuilds the README and report. See `docs/m2_colab_walkthrough.md`."""),
code("""from google.colab import files
files.download("/content/m2_detector_v2.json")
files.download(f"{RUNS}/{RUN_NAME}/weights/best.pt")
files.download(f"{RUNS}/{RUN_NAME}_eval_test_clean/confusion_matrix.png")"""),
]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["accelerator"] = "GPU"
nb.metadata["colab"] = {"provenance": [], "gpuType": "T4"}
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3"}
nbf.write(nb, ROOT / "notebooks" / "m2_train_yolo_colab.ipynb")
print("written notebooks/m2_train_yolo_colab.ipynb")
