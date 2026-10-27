# Architecture

## Components

```mermaid
flowchart TB
  subgraph Device["Facilitator / assessor device (PWA, works offline)"]
    UI[React screens<br/>EN / HI] --> OB[(Dexie outbox<br/>IndexedDB)]
    UI --> LC[(Local cache:<br/>packs, rubrics, own records)]
    OB --> SY[Sync engine<br/>ordered replay]
  end
  SY -->|POST /api/sync| API
  UI -->|GET when online| API
  subgraph Server["FastAPI backend (CPU laptop)"]
    API[REST API] --> SVC[Services]
    SVC --> M1[M1 mapper<br/>sentence-transformers]
    SVC --> M2[M2 evidence<br/>face blur, pHash, YOLOv8n]
    SVC --> M3[M3 rubric engine<br/>YAML rubrics]
    SVC --> AU[Audit log<br/>SHA-256 chain]
    SVC --> DB[(SQLite)]
    AU --> DB
    M2 --> FS[(Blurred photos<br/>data/uploads)]
  end
  QP[(Official QP JSON<br/>parsed from nqr.gov.in)] --> M1
  QP --> M3
  COLAB[[Colab notebook<br/>YOLOv8n training]] -. weights .-> M2
```

## Assessment sequence

```mermaid
sequenceDiagram
  actor F as Facilitator
  actor A as Assessor
  participant App as PWA
  participant S as API
  F->>App: worker code + declaration (any language)
  App->>S: assessment.create (queued if offline)
  S->>S: M1 ranks packs, stores evidence + gaps
  S-->>App: suggestion only
  A->>App: confirm pack (reason if not the top one)
  F->>App: checklist ticks, consented photos per task
  App->>S: checklist.set / evidence.add
  S->>S: blur faces → store → pHash reuse check → detector (presence only)
  A->>App: open scoring screen
  App->>S: GET prescores
  S-->>App: suggested level + confidence + reasons per criterion
  A->>App: accept, or override with reason
  App->>S: decision.add (audit logged)
  A->>App: review competency profile
  App->>S: sign off (agree, or own outcome + comment)
  S->>S: freeze assessment, audit log entry
```

## Key design decisions

| Decision | Why |
|---|---|
| Match at performance-criterion level, aggregate up to packs | Gives the explanation the brief asks for (which sentence matched which PC) and the gap list. |
| Pack score = mean over declaration sentences of best match to the pack's core PCs | A declaration is partial; we measure how well a pack explains what was said. Fixed **before** evaluation. |
| Self-declaration never raises a rubric level | Saying you can do something is not evidence that you did it; it is shown as context only. |
| Engine never suggests level 3 | Proficiency is a judgement the assessor makes. |
| Photo detections are reasons, not scores | The detector can only show presence; disagreements with the checklist are flagged as conflicts. |
| Critical safety criterion below 2 blocks a positive recommendation | Matches assessor practice: unsafe work cannot be offset by other marks. |
| Append-only audit log with a hash chain + DB triggers | Overrides and sign-offs must be traceable; tampering with any past entry is detectable. |
| Client-generated UUIDs + an ordered, idempotent outbox | Lets a facilitator create a worker, assessment and evidence offline, and replay safely. |
| Face blur on the server before anything is written to disk | Privacy by default. Limitation: offline photos wait unblurred in the device queue until sync. |
| pHash threshold chosen for ≤5 % false flags | A flag interrupts an assessor; false alarms must be rare even if edited reuse is missed. |

## Data model (SQLite)

`Worker` (pseudonymous code) → `Assessment` (declaration, mapping JSON, confirmed pack, status,
sign-off) → `ChecklistTick`, `EvidenceItem` (sha256, pHash, dHash, faces blurred, detections,
duplicate_of), `Decision` (append-only; latest per criterion wins). `AuditEntry` (seq, ts, actor,
action, subject, payload, prev_hash, hash). `AppliedOp` (offline idempotency). `StudyItem`,
`StudyRating` (M4).
