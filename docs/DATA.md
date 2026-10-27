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

## 3. Evidence images (M2)

| Dataset | Use | Licence | Status |
|---|---|---|---|
| Public PPE dataset | Fine-tune YOLOv8n for helmet/gloves/vest/shoes presence | see notebook | RESULT PENDING: chosen and trained in `notebooks/m2_train_yolo_colab.ipynb` |
| Team photos of electrician tools (~150) | Fine-tune tool classes | Team-owned, with consent | Not collected yet |
| Hashing test set | Evaluate duplicate/reuse detection | see `experiments/m2_hashing.json` | Built by `make eval-m2` from public-domain sample images |

## 4. Rater study (M4)

Real rater scores are stored in `data/study/` (created by the app's rater mode). Not collected yet:
**RESULT PENDING**.
