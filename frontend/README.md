# Hunar web app (PWA)

React + TypeScript progressive web app for Hunar, the AI-assisted Recognition of Prior Learning
tool for domestic electricians (SIH26242). It talks to the FastAPI backend in `backend/hunar/api`.

**AI suggests, the assessor decides.** The app never certifies anyone. It shows a *suggested level*,
a *pre score* and a *recommendation for assessor review*; only an assessor's sign-off produces an
outcome, and every accept, override and sign-off is written to the backend's hash-chained audit log.

## Run it

```bash
# 1. API on :8000 (from the repo root)
make api                     # or: uv run uvicorn hunar.api.main:app --port 8000
make seed                    # optional: one clearly labelled SAMPLE worker + 6 sample rater items

# 2. Web app
cd frontend
npm install
npm run dev                  # http://localhost:5173  (proxies /api -> http://localhost:8000)
```

Other scripts:

| Command | What it does |
|---|---|
| `npm run typecheck` | `tsc --noEmit` (strict) for the app and `vite.config.ts` |
| `npm run build` | type check, then production build to `dist/` with the service worker |
| `npm run preview` | serve `dist/` on http://localhost:4173 (also proxies `/api`) |

The service worker only exists in the production build, so test offline behaviour with
`npm run build && npm run preview`. Set `HUNAR_API=http://host:port` to proxy to another API, or
`VITE_API_BASE` at build time to call an API on another origin (CORS is open on the backend).

To try it on a phone on the same Wi-Fi, run `npx vite --host` (or `npx vite preview --host`).
Note that browsers only enable service workers on `https://` or `localhost`, so offline start-up
from the home screen needs HTTPS in a real deployment; the IndexedDB queue works either way.

## Screens

| Route | Screen |
|---|---|
| `/` | Choose a role (Worker/Facilitator, Assessor, Admin, Rater) and enter your name or ID (stored on the device, used as `actor` / `assessor`). List of assessments with **SAMPLE DATA** badges. |
| `/declare` | New worker with a pseudonymous code (warns against real names), preferred language, declaration text. Voice input is shown as *planned* (disabled). |
| `/a/:id/mapping` | The declaration and the top 3 qualification packs: score bars, matched performance criteria with the worker's sentences and similarity, NOS coverage, and skill gaps (core criteria with no match). Labelled "Suggestion only — the assessor confirms the pack". |
| `/a/:id/tasks` | The 6 practical tasks from `/api/rubrics`: instructions, checklist items as large Yes/No toggles, photo slots with a written-consent checkbox, evidence thumbnails, faces-blurred count, duplicate warning, detector status. |
| `/a/:id/score` | Step 1: confirm the pack (top suggestion by default; another pack needs a reason). Step 2: per criterion, the text, four anchored level descriptors, the suggested level with confidence and every reason, conflicts highlighted, critical (safety) criteria marked. Accept, or override with a level and a reason (5+ characters). Latest decision per criterion. |
| `/a/:id/profile` | Overall score vs the pass mark (70 %, from the official qualification file), per-NOS bars, gaps, critical failures, unscored count, the recommendation for assessor review, then the sign-off form (online only). After sign-off the assessment is shown as signed off and editing is frozen. |
| `/admin` | Audit log table (seq, time, actor, action, subject, collapsible payload), subject filter, "Verify chain". |
| `/rater` | Consistency study: rater ID, condition, session number, "include sample items (demo only)". One item at a time, no going back, seconds per item recorded, progress bar, thank-you screen. Assisted condition also shows the level descriptors and the pre score reasons. |
| `/queue` | The sync queue (what is waiting, in order). |

English and Hindi UI strings live in `src/i18n/en.ts` and `src/i18n/hi.ts`; TypeScript enforces the
same keys in both. The header toggle switches language (remembered in `localStorage`). Rubric
content comes from the API with `{en, hi}` fields; level descriptors and pre score reasons are
English-only in the backend and are shown as such.

## Offline design

```
user action ──> Dexie (IndexedDB) ──> outbox (ordered by seq) ──> POST /api/sync ──> server
                    │                                                   │
                    └── screens render from: server snapshot + queued ops overlay
```

* **Every write goes through a durable outbox** (`src/db.ts`, table `outbox`):
  `{op_id (uuid), seq (auto-increment), kind, payload, created_at, status, error, attempts,
  assessment_id}`. Kinds match `POST /api/sync`: `worker.create`, `assessment.create`,
  `pack.confirm`, `checklist.set`, `evidence.add`, `decision.add`.
* **Client-generated UUIDs** for workers and assessments, so later ops (ticks, photos, decisions)
  can reference a record before the server has seen it.
* **Sync engine** (`src/sync.ts`) replays the outbox **in order** in small batches (≤ 10 ops,
  ≤ ~2.5 MB) on app start, on the `online` event, every 20 s, when the tab becomes visible, right
  after each new write, and on "Sync now". A Web Lock makes sure only one tab syncs.
  * `applied` / `duplicate` → the op is removed (the server dedupes by `op_id`, so resending after
    a lost response is safe).
  * `rejected` → the op stays, marked refused; the queue stops (later ops may depend on it) and a
    banner shows the server's error with **Retry** and **Discard this change**.
  * Server down (network error, timeout, 502–504, or the dev proxy's empty 500) → ops stay
    pending; the header shows "Server not reachable". A real server error (5xx with a body) on a
    single op is retried and only marked refused after 3 attempts.
  * Consecutive checklist taps on the same task are merged into the newest queued op, but only if
    that op has never been sent, so order and idempotency are kept.
* **Local copies** so screens work offline: workers and assessments created on the device, the
  latest server snapshot of each assessment (detail, pre scores, profile), photo thumbnails, and the
  cached `/api/packs` and `/api/rubrics`. A screen shows *snapshot + queued ops*, so a tick made
  offline appears immediately and does not flicker back when an older snapshot arrives.
* **The mapper needs the server.** A declaration saved offline shows: "Your declaration is saved and
  will be matched to qualification packs when the device is online."
* **Photos**: `<input type="file" accept="image/*" capture="environment">`, downscaled on the device
  to at most 1280 px JPEG (quality 0.85) with a canvas, saved only after the "written consent
  obtained" box is ticked, and queued as `evidence.add` with `image_b64`. Faces are blurred by the
  server before storage. Until it syncs the photo exists only on this device (the UI says so);
  once its op is applied, the full image is deleted with the op and the raw preview is replaced by a
  thumbnail of the server's blurred copy.
* **Pre scores and accept**: pre scores are computed by the server. While checklist or photo changes
  for an assessment are still queued, *Accept suggestion* is disabled (the server would accept its
  own, newer suggestion); *Override* stays available because it carries an explicit level.
* **Sign-off is online only** and requires an empty queue for that assessment, a confirmed pack and
  all criteria scored.
* **Rater ratings** are not part of `/api/sync`: posted directly when online, otherwise stored in the
  `ratings` table and uploaded later. Session progress is stored, so a reload resumes the session
  instead of restarting it; images are prefetched when a session starts.
* **App shell**: `vite-plugin-pwa` (Workbox) precaches the built app, so it opens offline after the
  first visit. Evidence and study images are cached at runtime (cache-first).

## Honesty rules in the UI

* Wording: "suggested level", "pre score", "recommendation for assessor review". No "certified",
  "passed" or "approved" before an assessor signs off.
* A persistent footer: "AI suggests, the assessor decides" / "AI सुझाव देता है, निर्णय मूल्यांकनकर्ता का है".
* Wherever photo checks appear: the model only checks whether PPE and tools are visible and does
  **not** judge the quality of the work. With no trained model: "Photo check not available yet
  (model not trained)".
* Anything with `is_sample = true` (workers, assessments, audit subjects, study items) shows a
  **SAMPLE DATA** badge.

## Known limitations

* Mapping, pre scores and the competency profile are computed only on the server; offline the app
  shows the last copy it saw and says when it may be out of date.
* An *accept* decision does not carry the level the assessor saw (the API recomputes it), which is
  why Accept is disabled while prescore-affecting changes are queued.
* Rating uploads have no idempotency key in the API: if a rating reaches the server but the reply is
  lost, a later retry stores it twice.
* No authentication: the role and name are chosen on the device, as the project brief allows.
* Voice input is a placeholder (disabled button).
* On-device face blurring (MediaPipe) was not implemented; blurring happens on the server only.
* The audit view shows at most 1000 entries (the API has `limit` but no paging).
* Service workers need `https://` or `localhost`; over plain HTTP on a LAN the app works online
  and keeps its IndexedDB queue, but cannot start without a connection.

## Code map

| File | Purpose |
|---|---|
| `src/api.ts` | Typed API client and response types |
| `src/db.ts` | Dexie schema: outbox, workers, assessments, snapshots, photos, cache, ratings, study progress |
| `src/sync.ts` | Outbox writes and the ordered sync engine |
| `src/actions.ts` | User actions (each one writes locally and queues an op) |
| `src/data.ts` | Refresh from the API and build screen views (snapshot + queued ops) |
| `src/photo.ts` | Downscaling and thumbnails |
| `src/i18n/` | English and Hindi strings, language context |
| `src/screens/`, `src/components/` | Screens and shared components |
