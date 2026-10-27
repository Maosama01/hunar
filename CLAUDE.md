# Hunar: working rules for every session

Hunar is an AI assisted Recognition of Prior Learning (RPL) tool for domestic electricians,
built as a B.Tech minor project on SIH26242. The full brief is in `PROJECT_BRIEF.md`.

## Integrity rules (override everything else)

1. **Never fabricate results.** Every number in the README, report or slides comes from code in
   this repo and is reproducible with one command (`make eval`, `make study`). If there is no
   result yet, write `RESULT PENDING`. Results tables are generated from `experiments/*.json`,
   never typed by hand.
2. **Never fabricate sources.** Cite only references that are listed and verified in
   `docs/report/references.md`. Unsure → `[CITATION NEEDED]`.
3. **Never invent official content.** Qualification packs, NOS and performance criteria come from
   the official PDFs on nqr.gov.in (`data/qp_sources.json`, `make data`). The source URL, download
   date and SHA-256 are in `data/processed/qp_manifest.json`. Test fixtures that imitate a QP are
   marked `STUB, NOT OFFICIAL`.
4. **Label synthetic data everywhere.** Synthetic or placeholder data lives only in
   `data/synthetic/`. Anything derived from it (metrics, figures, UI screens, report sections)
   carries a visible "SAMPLE DATA" / "synthetic" label. Metrics computed on synthetic data are
   stored with `"data_kind": "synthetic"` and must be presented as a pipeline check, not as
   evidence about real workers.
5. **AI suggests, the assessor decides.** No code path certifies a worker automatically. A
   recommendation exists only after an assessor signs off; every accept, override and sign off
   is written to the hash chained audit log, and an override needs a reason.
6. **Consent and privacy.** Photos/videos of real people only with written consent
   (`docs/consent_form.md`). Faces are blurred before an image is stored. Never commit real
   personal data; `data/raw/`, `data/uploads/` and `*.db` are gitignored.
7. **State the limits honestly.** The vision model detects whether PPE and tools are *present*.
   It does not judge workmanship quality. The UI, README and report say so.

## Conventions

* Python 3.11 managed with `uv`; the package lives in `backend/hunar/`. Run things with
  `uv run ...` or the `make` targets. FastAPI app: `hunar.api.main:app`.
* Frontend: React + Vite PWA in `frontend/`, Dexie (IndexedDB) for the offline sync queue,
  English and Hindi strings in `frontend/src/i18n/`.
* Schemas are Pydantic models in `backend/hunar/schemas.py`; DB tables are SQLModel in
  `backend/hunar/api/models.py`.
* Rubrics are YAML files in `backend/hunar/rubric/tasks/`, one per practical task, each criterion
  linked to an official NOS code.
* Experiments write JSON to `experiments/<module>_<name>.json` with the command that produced it,
  the data kind (`real` / `synthetic`), the dataset size and a timestamp. `make results` rebuilds
  the README results table from those files.
* Tests live in `tests/`; `make test` must pass before every commit. Scoring and aggregation maths
  need unit tests for edge cases.
* Commit at the end of each phase with a clear message; say what works, what is mocked and what is
  missing.
* Keep the UI wording neutral: "suggested level", "pre score", "recommendation for assessor review".
  Never "certified", "passed" or "approved" until an assessor has signed off.
