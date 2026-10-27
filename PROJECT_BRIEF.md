# Build brief: Hunar, an AI assisted Recognition of Prior Learning tool

Minor project based on Smart India Hackathon 2026 problem statement **SIH26242**, *AI Assisted Skill Assessment Tool for Recognition of Prior Learning (RPL)*, from the Ministry of Skill Development and Entrepreneurship.
Prepared by **Tanishq Khandelwal, B.Tech CSE (AIML)** and team. "Hunar" is a working name; rename it freely.

---

## 1. Your role and how to work

You are the lead engineer on this project. Work like this:

1. Read this whole brief first.
2. Ask me every question in section 12 in **one batch**, then wait for my answers.
3. Propose a plan: final repo layout, the phase breakdown with acceptance criteria, and anything in this brief you think is wrong or too ambitious. Wait for my approval before you write code.
4. Build **one phase at a time**. At the end of each phase: run the tests, tell me what works, what is mocked and what is still missing, commit with a clear message, then stop for my review.
5. In Phase 0, create a `CLAUDE.md` at the repo root that records the conventions and the integrity rules below, so every later session follows them.

Push back when something in this brief is a bad idea. I would rather hear it early.

---

## 2. Integrity rules (non negotiable)

This is an academic project that faculty will examine. These rules override everything else.

1. **Never fabricate results.** Every metric, table and chart in the README, report or slides must come from code in this repo and be reproducible with one command. If there is no result yet, write `RESULT PENDING`, never a plausible number.
2. **Never fabricate sources.** Cite only papers, reports and documents that really exist. If you are not certain a reference exists, write `[CITATION NEEDED]` and let a human find it.
3. **Never invent official content.** Qualification packs, National Occupational Standards and performance criteria must come from the real documents on nqr.gov.in. Record the source URL and download date for each one. For development before the real files arrive, use small stub files clearly marked `STUB, NOT OFFICIAL`.
4. **Label synthetic data everywhere.** Synthetic or placeholder data lives only in `data/synthetic/`, and anything built from it shows a visible "sample data" label in the UI, the notebooks and the report.
5. **AI suggests, the assessor decides.** No code path may certify a worker automatically. Every recommendation needs a human sign off, and every override is logged.
6. **Consent and privacy.** Photos or videos of real people are used only with written consent (generate a simple consent form template in `docs/`). Blur faces by default before anything is stored. Never commit real personal data to git.
7. **State the limits honestly.** The vision model detects whether PPE and tools are present. It does **not** judge workmanship quality. Say so in the UI, the README and the report.

---

## 3. The problem

A large share of India's workforce learned their trade informally, on the job or through family, and has no certificate to show for it. NCVET's Recognition of Prior Learning framework lets such workers be assessed and certified against NSQF levels without repeating training. In practice, RPL assessment depends on manual practical evaluation, which is slow to scale, inconsistent between assessors and locations, and hard to schedule.

The official statement asks for a tool that can:

1. Guide a worker through a structured self declaration of experience, mapped automatically to the closest NSQF qualification pack or packs.
2. Support practical evaluation with guided task checklists and, where feasible, image or video aids that help an assessor score consistently.
3. Standardise scoring rubrics across assessors and locations to reduce variance between evaluators.
4. Generate an NSQF aligned competency profile and certification recommendation for assessor sign off. The tool supports the assessor but never replaces them.
5. Work in low connectivity settings, with offline capture and later sync.

Expected outcomes include a working flow for at least one trade, a qualification pack mapping engine, **evidence of improved inter assessor agreement over unassisted scoring**, an offline capable interface, and a clear statement of where the tool supports versus replaces human judgement.

---

## 4. Our scope

* **One trade: domestic electrician.** Pick the main qualification pack for domestic electrical work from the NQR, plus 3 or 4 neighbouring electrical or electronics packs as distractors for the mapper.
* **Three user roles:** worker (often helped by a facilitator), assessor, admin.
* **Languages:** English and Hindi, plus Hinglish (Hindi written in Roman script) for declarations.
* **Hardware:** everything must run on a normal student laptop on CPU. Model training that needs a GPU goes in a Google Colab notebook.

End to end flow:

```
Worker self declaration (text or voice)
  -> Qualification pack mapper (M1)
  -> Practical tasks with evidence capture
  -> Evidence checker (M2)
  -> Rubric pre scores with reasons (M3)
  -> Assessor review, override and sign off
  -> Competency profile and recommendation
  -> Offline queue and sync (M5)
Consistency study (M4) measures how much the rubric helps assessors agree.
```

---

## 5. Module M1: qualification pack mapper (NLP)

**Goal:** turn a worker's free text or spoken description of their work into a ranked list of qualification packs, with an explanation of which parts of the description matched which performance criteria.

* **Parsing:** convert each qualification pack into structured JSON: pack, NSQF level, NOS units, performance criteria, knowledge items. Define the schema with Pydantic. Write a PDF parser for the NQR documents, and fall back to a hand checked JSON if parsing is unreliable.
* **Model:** multilingual sentence embeddings with `sentence-transformers`. Start with `paraphrase-multilingual-MiniLM-L12-v2` and compare it with `LaBSE` if time allows. Match at the level of performance criteria, then aggregate up to NOS and pack scores.
* **Baselines:** keyword matching and TF IDF. The report must show the embedding model against both.
* **Voice (optional, later phase):** `faster-whisper` small model for Hindi and English speech to text.
* **Explainability:** for each top pack, show the declaration sentences that matched each performance criterion, with similarity scores, plus the criteria with no match (skill gaps).
* **Labelled evaluation set:** build a tool and guidelines so the team can write and label about 150 declarations: roughly a third each in English, Hindi (Devanagari) and Hinglish, covering the target pack and the distractors. Store them in `data/labels/declarations.csv`, with author and language columns.
* **Metrics:** top 1 accuracy, top 3 accuracy and mean reciprocal rank, each broken down **by language**. That breakdown is our fairness analysis. Include an error analysis notebook.

---

## 6. Module M2: evidence checker (computer vision)

**Goal:** check task photos for required safety gear and tools, and flag reused evidence.

* **Detector:** YOLOv8 nano through `ultralytics`. Fine tune it on a public PPE dataset (for example from Roboflow Universe or Kaggle; record the dataset name, link and licence in `DATA.md`). Add a small custom set of about 150 team labelled images for electrician tools: multimeter, tester screwdriver, wire stripper, insulated pliers. Use Label Studio, CVAT or Roboflow for labelling.
* **Training:** a Colab notebook for training, with CPU inference in the app.
* **Metrics:** mAP50, mAP50 to 95, per class precision and recall, and a confusion matrix.
* **Evidence integrity:** perceptual hashing with `imagehash` to flag a photo or clip reused across workers or batches. Evaluate it on a test set with deliberate duplicates, crops and recompressions, and report precision and recall.
* **Limit:** presence detection only. The UI must never suggest the model judged the quality of the work.

---

## 7. Module M3: rubric engine and explainable pre scores

* **Rubric files:** one YAML file per practical task, listing the criteria with anchored levels 0 to 3 (not performed, partial, competent, proficient), a descriptor for each level, weights, critical safety flags, and the NOS each criterion belongs to.
* **Pre scores:** for each criterion, combine CV detections, the assessor's checklist ticks and the declaration coverage from M1 into a suggested level. Every pre score shows its reasons in plain words, for example "gloves detected in photo 2, confidence 0.91".
* **Assessor control:** the assessor accepts or overrides each pre score. An override requires a short reason. Every action goes into an append only, hash chained audit log.
* **Aggregation:** per NOS and overall weighted scores, a configurable pass mark, and a rule that any failed critical safety criterion blocks a positive recommendation.
* **Output:** a competency profile page with per NOS results, gaps and the recommendation, followed by the assessor sign off step.
* **Tests:** unit tests for all scoring and aggregation maths, including the edge cases.

---

## 8. Module M4: consistency study

This is the deliverable the problem statement cares about most. It must use **real human raters**, even if the sample is small.

* **Rater mode in the app:** show a rater a set of 20 to 30 evidence items (photos or short clips of electrical tasks, taken with consent) in random order and collect their scores. Run two conditions: unassisted (rater's own judgement) and assisted (our rubric plus pre scores). Use a gap between sessions and randomise the order to reduce memory effects. Target 3 to 5 raters.
* **Analysis:** Fleiss' kappa (`statsmodels`), Krippendorff's alpha for ordinal data (`krippendorff`), mean pairwise agreement, and bootstrap confidence intervals. Show both conditions side by side.
* **Honesty:** state the sample size and the limitations plainly. A small real study is the goal. Do not generate a simulated study unless it is clearly labelled as a simulation of the method, kept separate from real results.

---

## 9. Module M5: application

* **Backend:** Python 3.11, FastAPI, SQLite through SQLModel, with the ML modules behind clean service interfaces.
* **Frontend:** React with Vite as a progressive web app. Offline capture through IndexedDB (Dexie) with a durable sync queue that replays in order when the connection returns. English and Hindi UI.
* **Screens:** worker or facilitator declaration flow, practical task checklist with evidence capture, assessor dashboard and scoring screen, competency profile, admin view of the audit log, and rater mode for M4.
* **Demo data:** a seed command that loads a clearly labelled sample worker, so the demo runs in one step.

---

## 10. Repo layout (adjust in your plan if you have a better one)

```
hunar/
  backend/
    app/            FastAPI routes, models, services
    ml/mapper/      M1
    ml/evidence/    M2
    rubric/         M3 engine and YAML rubrics
    audit/          hash chained log
  frontend/         React PWA
  data/
    raw/            official downloads (gitignored)
    processed/      parsed qualification packs
    labels/         team labelled declarations and images
    synthetic/      sample data, always labelled
  notebooks/        evaluation, error analysis, figures
  experiments/      configs and results as JSON
  docs/
    DATA.md         every dataset: source, licence, date, how to get it
    architecture.md with Mermaid diagrams
    consent_form.md
    report/         report draft
  tests/
  Makefile          setup, test, demo, eval targets
  CLAUDE.md
  README.md
```

---

## 11. Phases

| Phase | Goal | Done when |
|---|---|---|
| 0 | Setup and plan | Repo, environment, `CLAUDE.md`, `DATA.md`, schemas, stub packs, `make setup` and `make test` work |
| 1 | M1 mapper | Parser, embeddings, baselines, labelling tool, evaluation script produces metrics from the labelled set |
| 2 | M3 rubric engine and backend API | Rubric YAMLs for 4 to 6 electrician tasks, scoring with tests, audit log, API endpoints |
| 3 | M2 evidence checker | Colab training notebook, CPU inference, hashing, metrics written to `experiments/` |
| 4 | Frontend and offline sync | Full flow works in the browser, including with the network switched off |
| 5 | M4 study | Rater mode, analysis notebook, figures generated from real rater data |
| 6 | Report and viva prep | Report draft, slides outline, demo script, viva questions |

---

## 12. Questions to ask me before you start

1. Team member names and roles for the README. The default author line is "Tanishq Khandelwal, B.Tech CSE (AIML)".
2. Our laptops: OS, RAM, and whether anyone has a GPU. Do we have Google Colab?
3. Semester timeline: review dates and final submission date.
4. Our faculty's required report format (college template, IEEE style, page limits).
5. Should voice input be in the first version or a later phase?
6. Do we already have any qualification pack files, photos or labelled data?
7. Any technology our faculty requires or forbids.

---

## 13. Final deliverables for faculty

* `README.md` with a project summary, an architecture diagram, one command setup (`make setup`, `make demo`) and a results table filled automatically from `experiments/`.
* Report draft in `docs/report/`: abstract, introduction, literature review (real sources only), problem definition, methodology, system design, experiments, results, limitations, ethics and consent, future work.
* A 10 to 12 slide outline for the presentation.
* A 5 minute demo script using the seeded demo data.
* Viva preparation: 20 likely examiner questions with answers grounded in our actual code and results.

Start with section 12 now.
