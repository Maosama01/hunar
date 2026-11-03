# Data register

Every dataset used by Hunar: where it comes from, its licence or terms, when it was obtained and
how to get it again. Real personal data is never committed. Synthetic data lives only in
`data/synthetic/` and is labelled as such wherever it is used.

## 1. Official qualification files (M1, M3)

Source: National Qualification Register, NCVET, Government of India (https://www.nqr.gov.in).
Terms: public government documents; content owned by NCVET (see the NQR copyright policy page).
We keep the PDFs out of git and commit only the parsed JSON plus a manifest.

How to get them: `make data` (downloads with `scripts/fetch_qps.py`, then parses with
`hunar.mapper.qp_parser`). URLs, download date and SHA-256 per file:
`data/processed/qp_manifest.json`.

| Role | NQR id | Qualification | NQR code | Sector | NSQF | Valid till (NQR page) |
|---|---|---|---|---|---|---|
| target | 13772 | Assistant Electrician | QG-03-CO-03951-2025-V2-CSDCI | Construction | 3 | 30/04/2028 |
| distractor | 9530 | Industrial Electrician | QG-04-PW-00870-2023-V1-PSSC | Power | 4 | 31/08/2026 |
| distractor | 11371 | Rooftop Solar PV (Installation & Maintenance) | NG-03-PW-02710-2024-V1-DGT | Power | 3 | 24/06/2027 |
| distractor | 14896 | Wireman Control Panel Electronics | QG-03-EH-04474-2025-V2-ESSCI | Electronics & HW | 3 | 07/10/2028 |
| distractor | 9588 | Jr. Technician (Smart Energy Meter) | QG-03-PW-00868-2023-V1-PSSC | Power | 3 | 31/08/2026 |

Why this target: the CSDCI *Assistant Electrician* qualification covers LV single phase wiring in
residential and commercial buildings, which is what an informally trained domestic electrician does.
The four distractors are neighbouring electrical jobs that share vocabulary (wiring, testing,
safety) so the mapper has to discriminate. Two distractors show a "valid till" date that has passed
on the NQR page as of 28 Oct 2026; they are still listed on NQR and are used only as distractors.

Parsing status: parsed automatically from the PDFs (`parse_method: pdf_auto`) and spot-checked
against the PDFs by the AI assistant. **A human check of every performance criterion is still
pending**; after checking, set `parse_method` to `pdf_auto_hand_checked` in the JSON so the parser
never overwrites it.

Known quirks of the official files, handled in the parser: the Assistant Electrician QF prints
one NOS table twice, and repeats one row across a page break; the Industrial Electrician QF prints
`PSS/Q1706` and `PSS/N1337` in the assessment annexure where the module summary says `PSS/N1706`
and `PSS/N1336` (we use the module summary codes).

## 2. Worker declarations for the M1 evaluation

| File | What | Status |
|---|---|---|
| `data/labels/declarations.csv` | Team-written, team-labelled declarations (English, Hindi, Hinglish) | **Empty: to be written by the team** following `docs/labelling_guidelines.md` |
| `data/synthetic/declarations_synthetic.csv` | Declarations written by an AI assistant to exercise the pipeline | **SYNTHETIC.** Not real workers. Used only as a pipeline check. |

### Synthetic speech (voice input check)

`make eval-voice` reads the synthetic declarations aloud with the text-to-speech voices built into
macOS (`say`: Lekha, hi_IN, for Hindi; Rishi, en_IN, for English and Roman-script Hinglish) and
writes the audio to `data/raw/voice_tts/` (gitignored, regenerated on demand). **SYNTHETIC: no
human voices.** Transcripts and metrics go to `experiments/m1_voice_*` with `"data_kind":
"synthetic"`. Real recordings of workers are never stored: the app sends audio once for
transcription and deletes it at once.

## 3. Evidence images (M2)

### Public PPE dataset
* **Name:** Personal Protective Equipment ("PPEs - v7 raw-images_ommittedSuitClasses"), Roboflow
  export of 7 Jul 2022, 11,978 images, COCO format. Classes: glove, goggles, helmet, mask, shoes and
  their `no_*` variants.
* **Licence:** CC BY 4.0 (stated in the dataset's README.roboflow / README.dataset files).
* **Where:** Hugging Face mirror `keremberke/protective-equipment-detection`
  (https://huggingface.co/datasets/keremberke/protective-equipment-detection).
* **Use 1, hashing evaluation:** the test split (1,935 images; `scripts/fetch_ppe_test.py`, downloaded
  28 Oct 2026, zip SHA-256 `16dfeef2e6e14bb188e40d0e856c12c48033e6a61b5b9230eaf53db97d3feb6e`).
  Finding: the split is dominated by near-identical video frames; only 407 images remain distinct
  after grouping (32x32 thumbnail correlation >= 0.95). Reuse is simulated with nine transformations.
* **Use 2, detector training:** all splits (`make ppe-split` downloads them and writes
  `experiments/m2_ppe_split.json`), trained in `notebooks/m2_train_yolo_colab.ipynb` on Colab. Mapped
  to Hunar classes helmet, gloves, safety_shoes, goggles.
  * **Finding: the published splits are class-disjoint.** Train has 0 helmet and 14 safety-shoe boxes;
    test has 0 glove boxes; 136 test images have a near-duplicate (pHash <= 4 bits) in train. Run 1
    (3 Nov 2026) used these splits and is kept only as a diagnostic
    (`experiments/m2_detector_run1_published_splits.json`, `docs/figures/m2_run1_confusion_matrix.png`).
  * **Re-split used from run 2:** pool all 11,978 images, group near-identical frames (pHash <= 4 bits,
    single linkage), assign whole groups with iterative stratification (Sechidis et al., 2011), targets
    70/15/15 per class. Every class is in every split and no test image has a near-duplicate in train.
    The data are mostly video: all safety-shoe boxes come from two videos (one trains, one tests).
    Code: `backend/hunar/evidence/ppe_split.py` (unit-tested, embedded verbatim in the notebook).
  * Detector result (run 2): **RESULT PENDING.**

### Team photos of electrician tools (planned)
About 150 photos of multimeter, tester screwdriver, wire stripper and insulated pliers, taken by the
team **with written consent** and labelled in Label Studio/CVAT/Roboflow. Not collected yet.

### Sample images
`data/synthetic/sample_photos/` holds line drawings generated by `make seed`, stamped
"SAMPLE IMAGE - synthetic drawing". They exist only for the demo.

## 4. Rater study (M4)

| What | Where | Committed? |
|---|---|---|
| Consented study photos and the item list (`items.csv`, template in `docs/study_items_template.csv`) | `data/study/` | No (gitignored) |
| Face-blurred, metadata-free copies loaded by `make study-items` | `data/uploads/study/` | No (gitignored) |
| Rater scores (pseudonymous rater IDs) | app database `data/hunar.db` | No (gitignored) |
| Analysis results | `experiments/m4_consistency.json`, `docs/figures/m4_agreement.png` | Yes |
| Study-size simulation (**SIMULATION OF THE METHOD**, artificial ratings) | `experiments/m4_design_simulation.json` | Yes |

Real rater scores have not been collected yet: **RESULT PENDING**. Procedure:
`docs/m4_study_walkthrough.md`.
