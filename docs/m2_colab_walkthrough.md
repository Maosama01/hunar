# Walkthrough: train the PPE detector on Colab and bring the results back

This fills the **RESULT PENDING** detector rows in the README and report. You need a Google account
with Colab Pro and the laptop with this repo. Every number comes from the notebook's own output
file, `m2_detector.json`; nothing is typed by hand.

The notebook's code was smoke-tested on the laptop (1 epoch on 40 images, CPU) with the same pinned
ultralytics version (8.3.228). That checks the code runs; it says nothing about accuracy.

## Part A: on Colab

1. **Open the notebook.** Go to https://colab.research.google.com → *File → Upload notebook* → pick
   `notebooks/m2_train_yolo_colab.ipynb` from this repo. (Or use the *GitHub* tab and authorise access
   to the private `Maosama01/hunar` repo.)
2. **Choose a GPU.** *Runtime → Change runtime type → Hardware accelerator: GPU* (T4 works; L4 or A100
   are faster if Colab Pro offers them). Save.
3. **Run the cells in order** (*Runtime → Run all*, or Shift+Enter cell by cell):

   | Cell | What happens | What you should see |
   |---|---|---|
   | Setup | Installs ultralytics 8.3.228 | `nvidia-smi` lists a GPU; ultralytics prints a check summary |
   | 0. Drive | Asks to connect Google Drive (approve the pop-up) | `runs will be saved in /content/drive/MyDrive/hunar_runs` |
   | 1. Download | Downloads the PPE dataset (about 2.3 GB) | train / valid / test image counts |
   | 2. Convert | COCO → YOLO labels with Hunar class names | image and box counts per split |
   | 3. Tools (optional) | Adds the team's own tool photos if `hunar_tools.zip` is uploaded | otherwise "training PPE classes only" |
   | 4. Leakage check | Finds test images with a near-duplicate in train | "N of M test images have a near-duplicate in train" |
   | 5. Train | YOLOv8n, 50 epochs | one progress block per epoch |
   | 6. Evaluate | mAP on the full test split and the clean subset | two lines: `test mAP50 …` and `clean mAP50 …` |
   | 7. Download | Downloads `m2_detector.json`, `best.pt`, `confusion_matrix.png` | allow multiple downloads if the browser asks |

4. **How long training takes.** After the first epoch ultralytics prints the time per epoch; multiply
   by 50. If that is too long, stop, set `EPOCHS = 30` in the train cell and run it again. The epoch
   count is saved in the results file and shown in the report, so a shorter run is fine as long as
   it is reported.
5. **Keep the tab open** and the laptop awake while it trains.
6. **If Colab disconnects:** reconnect, run Setup, cells 0, 1, 2 and 4 again, then run the
   *resume* cell under step 5 (remove the `#` signs) instead of the train cell. Your weights are safe
   in Google Drive (`MyDrive/hunar_runs`), and `m2_detector.json` is also saved there.

## Part B: on the laptop

From the repo folder (`/Users/tanishqkhandelwal/Hunar`), with the three files in `~/Downloads`:

```bash
make vision
```

```bash
make import-detector
```

If the files are somewhere else: `make import-detector DL=/path/to/folder`.

The import script checks the files before copying anything. It refuses smoke-test files, runs with
fewer than 100 test images, runs under 10 epochs (unless you pass `--allow-short-run`), and weights
whose class names do not match the results file. Then it:

* copies `best.pt` to `data/models/hunar_ppe_tools_yolov8n.pt` (gitignored, never committed),
* copies `m2_detector.json` to `experiments/` and the confusion matrix to `docs/figures/`,
* rebuilds the README results table and the report.

## Part C: check and commit

1. Open `README.md` → *M2 PPE / tool presence detector*: the RESULT PENDING line is replaced by a
   table for the full and clean test sets plus per-class rows.
2. `make api`, then open http://localhost:8000/api/health: `"detector": {"available": true, …}`.
   Upload a task photo in the app: the evidence card now lists detections, with the "presence only"
   note.
3. Commit and push:

```bash
git add experiments/m2_detector.json docs README.md && git commit -m "M2: detector results from Colab run" && ./scripts/push.sh origin main
```

## What to say about the numbers

* Quote the **clean test** mAP as the headline; the full-split number is inflated by near-duplicate
  frames shared with the training set (the leakage line says how many).
* Report the number of epochs and the GPU type.
* The detector checks whether PPE is **visible**; it does not judge whether the work is done well.
* Tool classes (multimeter, tester screwdriver, wire stripper, insulated pliers) appear only if the
  team uploads its own consented, labelled photos in step 3.
