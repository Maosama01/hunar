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

**Trade qualification files (quiz banks, trade rubrics and the video pilot; not candidates for the M1
mapper).** Listed under `trade_packs` in `data/qp_sources.json`, fetched and parsed by the same commands:

| Trade | NQR id | Qualification | NQR code | NSQF | Valid till (NQR page) |
|---|---|---|---|---|---|
| plumber | 12957 | Plumber - General (WMPSC) | QG-04-PL-03441-2024-V2-WMPS | 4 | 17/12/2027 |
| carpenter | 9884 | Assistant Carpenter (FFSC) | QG-04-WC-00828-2023-V2-FFSC | 4 | 31/08/2026 (lapsed) |
| appliance_technician (video pilot) | 14861 | Service Technician – Home Appliances (ESSCI) | QG-04-EH-044772025-V2-ESSCI (as printed on NQR) | 4 | 07/10/2028 |

**Appliance file for the ceiling-fan video pilot (checked 6 Nov 2026).** NQR 14861 is current (NSQC 44,
approved 07/10/2025) and has two trade NOS: ELE/N3101 (engage with customer) and ELE/N3112 (install
and repair appliances); 70 % aggregate pass mark, no NOS-wise mark. Its installation criteria name
refrigerators, air conditioners, washing machines and water purifiers; **no current qualification we
checked names ceiling fans** (not this file, not the five electrical packs). The older Field
Technician – Other Home Appliances (NQR 2270) lapsed on 27/06/2025 and covers mixer-grinders and
microwave ovens, not fans, so it is not used. The fan tasks therefore link to ELE/N3112's general
diagnose-and-repair criteria (PC34–PC43, PC47) and ELE/N3101's customer criteria, and say so.

No worker-level domestic carpentry qualification on NQR was current on 3 Nov 2026, so the lapsed
FFSC file is used as the closest official standard and the app labels it as lapsed. The first parse
had gaps: PSC/N0142 (plumber) came out with one performance criterion, the carpenter NOS titles were
truncated and its Employability Skills NOS lost its code. The parser now handles the layouts behind
them (names and codes wrapped onto extra rows, tables continued on a new page without the name column,
a row printed above a page's table, two criteria in one cell, outcome headings glued onto a criterion),
and `tests/test_qp_parser.py` checks that every NOS has its code and PC1..PCn without gaps. Plumber:
8 NOS, 161 PCs; carpenter: 5 NOS, 103 PCs. The same fixes removed glued-on headings from about 20
criteria in three M1 distractor packs and recovered one missing criterion (ELE/N6322 PC11), so the
five M1 packs now hold 345 PCs; the target pack 13772 did not change, and the M1 evaluation was re-run.

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

### Worker quiz question banks

`backend/hunar/quiz/banks/{electrician,plumber,carpenter}.yaml`: multiple-choice questions written
with AI help from the official sources each item cites (qualification files and their performance
criteria; CEA Safety Regulations 2023; IS 5329, IS 2065, IS 694 and IS 5216 by clause, paraphrased; the
DGT curricula as topic sources). No item is copied from NIMI books or published question banks, which
are not openly licensed. Status **DRAFT** until reviewed by a certified assessor or ITI instructor.
Difficulties are AI estimates until `make quiz-calibrate` has about 100 real attempts per trade.
Machine translations into other languages (`banks/i18n/`) are written by `make translate` (Bhashini)
and marked unreviewed. Real quiz answers live only in the local database (gitignored).

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
