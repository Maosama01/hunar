# Hunar web app (PWA)

React + TypeScript progressive web app for Hunar (SIH26242). It talks to the FastAPI backend in
`backend/hunar/api`. Three groups of people use it:

* **Workers** (electrician, plumber, carpenter): an adaptive self-check quiz, a profile that customers
  can see, a request for a practical assessment, bookings, privacy settings.
* **Customers**: search for workers (no login needed to look), book one, rate after the job.
* **Staff** (facilitator, assessor, admin): the assessor screens (declaration, mapping, practical tasks,
  scoring, sign-off, audit log, rater study) with the offline outbox, plus assessment requests and, for
  admins, permit checks.

**AI suggests, the assessor decides.** The app never certifies anyone. It shows a *suggested level*,
a *pre score* and a *recommendation for assessor review*; only an assessor's sign-off produces an
outcome. The quiz is a **self-check**, never a certificate and never shown to customers; a customer
badge appears only after an assessor has signed off a practical assessment, and every badge says what
was checked, by whom and when, and that it is not a government certificate.

## Run it

```bash
# 1. API on :8000 with a throwaway database (never data/hunar.db for demos)
export HUNAR_DB=sqlite:////tmp/hunar-demo.db HUNAR_PIN_PEPPER=dev-pepper HUNAR_MAPPER=tfidf
export HUNAR_OTP_PROVIDER=test        # optional: SMS-code step in TEST MODE (code shown on screen)
uv run python -m hunar.api.seed       # SAMPLE accounts, workers and items (all labelled SAMPLE)
uv run uvicorn hunar.api.main:app --port 8000

# 2. Web app
cd frontend
npm install
npm run dev                  # http://localhost:5173  (proxies /api -> http://localhost:8000)
```

Sample logins (all `is_sample`, shown with a **SAMPLE DATA** badge) are listed at the top of
`backend/hunar/market/seed.py`. Staff cannot self-register: admins create staff accounts with
`python -m hunar.accounts.cli`.

| Command | What it does |
|---|---|
| `npm run typecheck` | `tsc --noEmit` (strict) for the app and `vite.config.ts` |
| `npm run build` | type check, then production build to `dist/` with the service worker |
| `npm run preview` | serve `dist/` on http://localhost:4173 (also proxies `/api`) |

The service worker only exists in the production build, so test offline behaviour with
`npm run build && npm run preview`. Set `HUNAR_API=http://host:port` to proxy to another API, or
`VITE_API_BASE` at build time to call an API on another origin (CORS is open on the backend).
Browsers only enable service workers (and the microphone) on `https://` or `localhost`.

## Screens

Every screen works from 360 px wide; worker and customer screens have a bottom navigation with
icon + short label (tap targets of at least 48 px).

**First run and accounts**

| Route | Screen |
|---|---|
| `/welcome` | Onboarding: (1) language picker with all 23 languages, each in its own script; (2) "I am a worker" / "I want to hire a worker" cards, "I already have an account", small "Staff login"; (3) 2-3 intro cards per role with icons and read-aloud; (4) itemised consent from `GET /api/auth/config` (required purposes need an explicit "I agree" and say why; optional ones are switches, off by default; data used and what withdrawal does; notice version) plus "I am 18 or older"; (5) workers only: their trade, with a note that the quiz in that trade starts as soon as the account exists; (6) register: mobile number, display name ("a first name or nickname is enough"), PIN + confirmation with the PIN rules checked as you type; (7) when `otp_required`, the SMS code step (TEST MODE banner and code when the API returns one). A new worker lands on question 1 of the first quiz. `?step=intro&role=worker&replay=1` replays the intro from Settings. |
| `/login` | Mobile number + PIN (numeric keypad, `autocomplete="off"`, show/hide). Clear messages for a wrong PIN (401) and lockout (429). "Forgot PIN?" leads to the SMS reset when the server has OTP, otherwise says to ask an admin or facilitator. `?staff=1` is the staff login. Shows how many offline changes wait on the device. |
| `/reset-pin` | SMS code (TEST MODE shown) + new PIN twice. |
| `/language` | Change language (also the globe button in the header). |
| `/settings` | Account (name, masked phone, role), language, "How Hunar works", privacy, staff: sync queue and rater mode, log out. |

**Worker** (`/w/...`)

| Route | Screen |
|---|---|
| `/w/quiz` | Choose a trade (only trades with a question bank; others "Questions coming soon"), start, history of results. Needs the *assessment* consent (required for workers; older accounts get an "I agree" button). The quiz is compulsory: until one is finished and counts (at least half the answers at reading pace; a rushed quiz shows "This quiz does not count" and a "Take the quiz again" button), `/w/profile`, `/w/assess` and `/w/bookings` redirect to the quiz (`RequireQuiz` in `App.tsx`, using `account.quiz` from the API), and the bottom bar shows only the quiz and privacy. |
| `/w/quiz/:id` | One question per screen: option cards, a separate "Don't know" button, read-aloud of question and options, "Question n of up to N", seconds per question measured and sent, no going back, gentle "please read each question fully" after a rapid answer, label for machine-translated or not-yet-translated questions (shown in Hindi). When done: the result. |
| result | "You would likely answer about X–Y% of our questions correctly" with a range bar (90 % interval, middle marked), counts, per-NOS bars ("Not enough answers to say" when `enough` is false), topics to revise, the result note, "Request a practical assessment", "See answers and explanations", and in small print the DRAFT bank and "uncalibrated" labels. |
| `/w/quiz/:id/review` | Each question with the right answer, the worker's answer, the explanation and the sources. |
| `/w/profile` | Edit trade, years, PIN code, district, languages (23 endonyms), short bio, self-declared electrical permit. Shows exactly what customers will see (the same card and badge text) and whether it is visible (depends on the *profile display* consent). |
| `/w/assess` | Request a practical assessment: declaration typed or spoken (`VoiceInput`, "I read the text and corrected the mistakes" tick after speech), optional preferred date, request status. Explains that the quiz is only context for the assessor. For a trade without practical tasks (`practical_assessment: false` in `/api/trades`; all three trades have tasks now) it says assessments are not available yet, and the quiz result offers no "Request a practical assessment" button. Assessor screens show only the assessment's own trade's tasks (`tradeTasks` in `data.ts`), the trade as a badge, and for plumbers and carpenters the trade's own qualification file in the pack step instead of M1 suggestions; each task shows its review note (DRAFT for plumber and carpenter). |
| `/w/bookings` | Accept / decline new requests, mark as done, cancel; the customer's phone appears only after accepting. |
| `/w/privacy` | Every consent purpose with its data and what withdrawal does; optional ones as switches (turning off asks first); erase the account with a typed confirmation word. |

**Customer** (`/c/...`)

| Route | Screen |
|---|---|
| `/c/find` | Trade chips with icons, PIN code, filters "Skills checked by an assessor" and "Permit document checked". Worker cards with SAMPLE DATA badge, rating, languages and badges. Open to everyone. |
| `/c/worker/:id` | The card, then "What was checked" in plain words, e.g. "Practical skills checked by an assessor on 3 Nov 2026 against Assistant Electrician (NSQF 3). Not a government certificate." Booking form (customers only): jobs from `/api/trades`; jobs that need a State permit are disabled with the permit note when the worker's permit is not checked; date from today; morning / afternoon / evening. |
| `/c/bookings` | Cancel, mark as done, rate (1-5 stars and a few words) after completion; the worker's phone appears after acceptance. |
| `/c/privacy` | As for workers. |

**Staff** (assessor-side screens unchanged apart from the login)

| Route | Screen |
|---|---|
| `/staff` | What this role can do, and the list of assessments with **SAMPLE DATA** badges. |
| `/staff/requests` | Assessor/admin: open assessment requests with the worker's declaration and latest quiz summary, labelled "Self-check quiz (context only)". *Start practical assessment* creates the assessment and opens its mapping screen. |
| `/staff/permits` | Admin: mark "Permit document checked" (with the State, after ticking "I have seen the original permit document") or remove the check. |
| `/declare`, `/a/:id/mapping`, `/a/:id/tasks`, `/a/:id/score`, `/a/:id/profile` | Declaration (now with the trade being assessed, including the appliance-technician fan pilot), pack suggestions, practical tasks with photos, scoring, competency profile and sign-off. Tasks with guided clips (video pilot) show a recorder per part (`GuidedClips.tsx`: prompt with read-aloud, consent tick, meter fields, upload; online only) and, once processed, the blurred silent video, the words found per aspect as timestamp buttons that seek the video, when the frame check saw the part and a hand on it (also seek buttons, only when `make clip-models` has been run; the hand line says "not checked" until `HUNAR_CLIP_HAND_CONF` is set), the meter check and the draft transcript. |
| `/admin` | Audit log and chain check (assessor or admin). |
| `/rater` | Consistency study (rater mode); open without a login. |
| `/queue` | The sync queue. |

## Accounts and auth

* `src/session.ts` keeps the bearer token and the account in `localStorage` (so a staff device can
  reload offline) and exposes `useSession()`. `src/api.ts` adds `Authorization: Bearer <token>` to
  every request; a 401 on any request that carried the token ends the session and the route guards
  open `/login` (queued offline changes are kept).
* Route guards (`RequireRole` in `src/App.tsx`): `/w/*` workers, `/c/bookings` and `/c/privacy`
  customers, staff screens facilitator/assessor/admin, requests and audit assessor/admin, permits admin.
* The role and name are no longer picked on the device: `src/settings.tsx` now reads them from the
  logged-in account (the server ignores names in request bodies).

## Languages

* UI strings live in `src/i18n/locales/en.json` (the source of keys; `Key` is derived from it) and
  `hi.json`, which must have every key (checked at compile time).
* Any other language is an optional file `src/i18n/locales/<code>.json`, loaded only when chosen
  (`import.meta.glob`). Format: a flat object `key -> string`, plus an optional
  `"_meta": {"provider": "...", "reviewed": false, "generated": "2026-11-03"}`. `{name}` placeholders
  must be kept. Missing keys fall back to English.
* When the chosen language's file is missing or incomplete, a small banner says "Not all text is
  translated into <endonym> yet"; when `_meta.reviewed` is false it also says "Machine-translated, not
  yet checked by a native speaker". The language picker marks languages without a file
  ("mostly English for now").
* `<html lang>` follows the language (with script subtags for `mni-Mtei`, `sat-Olck`, `ks-Arab`,
  `sd-Arab`) and `dir="rtl"` is set for Urdu, Kashmiri and Sindhi. The CSS uses logical properties
  (`inset-inline-start`, `margin-inline-*`, `border-inline-start`, `text-align: start`); in RTL, text
  elements use `unicode-bidi: plaintext` so English fallback strings keep their punctuation in place.
  Quiz content that arrives in another script (e.g. the Hindi fallback) gets its own `lang` and `dir`.
* Fonts: system fonts, plus Noto Sans Ol Chiki and Noto Sans Meetei Mayek from Google Fonts, loaded
  only when Santali or Manipuri is chosen (the picker loads just the glyphs of the two names). A
  Workbox runtime-caching rule keeps those fonts available offline after first use.
* Consent texts: the English text of each purpose comes from the server (the legal source). A
  translated text is used only when the locale's `consent.translatedNotice` equals the server's
  `notice_version`; otherwise the English server text is shown.
* Rubric/qualification content: the API's `{en, hi}` fields; for other languages the app shows Hindi
  to readers of Devanagari-script languages and English to everyone else. Quiz items come from the API
  in the chosen language when a translation exists (labelled machine-translated or reviewed), otherwise
  in Hindi with a label.
* The Hindi strings were written during development and have **not yet been checked by a native
  speaker**; the other 21 languages are to be generated by a separate Bhashini script.

## Read-aloud

`src/tts.ts` defines a `TtsProvider` interface (`canSpeak`, `speak`, `stop`, `subscribe`) and a
`WebSpeechTts` implementation that picks a device voice by BCP-47 tag (`hi-IN`, `ta-IN`, `bn-IN`, ...).
`<SpeakButton>` hides itself when no voice exists for that language. A server-side Bhashini TTS proxy
can be plugged in with `setTtsProvider()`; Bhashini is never called from the browser (keys stay on the
server). Untranslated strings are read with an English voice.

## Offline design (staff screens)

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
* **Auth and the outbox**: every request, including sync replay, sends `Authorization: Bearer <token>`.
  Ops are only sent while a staff account is logged in; the server records the logged-in account as
  the actor (names in payloads are ignored). A 401 (expired session, PIN reset, logged out elsewhere)
  or 403 on `/api/sync` puts the batch back to *pending* (never *refused*), ends the session on this
  device and opens the login screen, which shows how many changes are waiting. The next staff login
  sends them. Logging out keeps the queue too (Settings warns how many changes are not sent yet).
* **Evidence images** need the staff token, which an `<img src>` cannot send, so they are fetched with
  the token and shown as blob URLs (the service worker still caches them for offline use).

## Honesty rules in the UI

* Wording: "suggested level", "pre score", "recommendation for assessor review", "self-check". No
  "certified", "passed" or "approved" before an assessor signs off.
* A persistent line above the bottom navigation: "AI suggests, the assessor decides" (and the English
  text when the line is translated).
* The quiz says on every screen that it is a self-check; the result shows its uncertainty (a range,
  not one number), the DRAFT status of the question bank and that difficulties are uncalibrated.
  Assessors see the quiz only as "context only".
* Badges explain what was checked, by whom and when, and "Not a government certificate" / "Hunar does
  not issue permits". A self-declared permit is shown as "Says they have a permit".
* Wherever photo checks appear: the model only checks whether PPE and tools are visible and does
  **not** judge the quality of the work.
* Anything with `is_sample = true` (accounts, workers, assessments, audit subjects, study items) shows
  a **SAMPLE DATA** badge.

## Known limitations

* Worker and customer screens need the network (a friendly offline message is shown); only the staff
  screens have the offline outbox.
* Changing the language in the app does not change the account's language on the server (there is no
  endpoint for it); the quiz is started in the app's current language.
* Logging out removes the token but keeps the device's cached assessments and queued changes (by
  design, so offline work is not lost); a shared device should be cleared by an admin.
* Server messages that the app cannot map to a translated string (some validation errors) are shown in
  English.
* Read-aloud depends on the voices installed on the device; many Indian languages have none on
  desktop browsers, so the button is hidden there.
* Hindi strings are not yet reviewed by a native speaker; no other language files exist yet.
* Mapping, pre scores and the competency profile are computed only on the server; offline the app
  shows the last copy it saw. Sign-off is online only. Voice input needs the server (`make voice`).
* On-device face blurring was not implemented; blurring happens on the server only.
* The audit view shows at most 1000 entries.

## Code map

| File | Purpose |
|---|---|
| `src/api.ts` | Typed API client (adds the bearer token; 401 ends the session) and response types |
| `src/session.ts` | Token + account store, `useSession()`, role home paths |
| `src/i18n/index.tsx`, `languages.ts`, `locales/*.json` | Strings, lazy locales, coverage banner data, the 23 languages (endonyms, BCP-47, RTL, fonts) |
| `src/tts.ts` | Read-aloud (`TtsProvider`, Web Speech implementation) |
| `src/consent.ts` | Consent purpose texts (server English or matching translation) |
| `src/trades.ts` | Cached `/api/trades` |
| `src/db.ts`, `src/sync.ts`, `src/actions.ts`, `src/data.ts`, `src/photo.ts` | Staff offline outbox, sync engine, local views, photos |
| `src/components/` | Layout (headers, translation banner, bottom nav), auth inputs, worker card and badges, icons, shared UI |
| `src/screens/` | Onboarding, login, reset PIN, settings, privacy, bookings; `worker/`, `customer/`, `staff/` and the existing assessor screens |
