# Bhashini setup: translations and read-aloud in 22 languages

Hunar shows English and Hindi today. The other 21 scheduled languages fall back to English, and quiz
questions fall back to Hindi, with a "not translated yet" note. With Bhashini, the Government of
India's language platform, one command fills them in, and read-aloud uses Bhashini voices instead of
whatever voices the phone happens to have.

The keys stay on the laptop or server, in a file git ignores. Never paste them into chat, a screenshot,
an issue or a commit.

## 1. Register (team lead, once)

1. Go to https://bhashini.gov.in and register Hunar as an organisation. Colleges and institutes are
   among the groups listed. Use the college's details and describe the project as an academic,
   non-commercial assessment tool.
2. Bhashini may ask you to sign an access agreement and approve it. The terms forbid commercial use
   or redistribution without written approval, and they give no warranty that outputs are correct.
   That is why every translation is labelled "machine-translated, not reviewed".
3. After approval, log in and open **My Profile**. It shows your **User ID** and **ULCA API key**.
4. Find the **pipeline ID** your account may use, from your account or the API's pipeline search. If
   it isn't shown, ask Bhashini support which pipeline ID to use for translation and TTS.

## 2. Put the keys in `.env`

From the repo folder:

```bash
cp .env.example .env
```

Open `.env` and fill in `BHASHINI_USER_ID`, `BHASHINI_API_KEY` and `BHASHINI_PIPELINE_ID`. Save it.
`.env` is gitignored, and the `make` commands load it automatically.

## 3. Check the keys

```bash
make bhashini-check
```

You should see a Hindi translation and "text to speech hi: … bytes, WAV". Then see which languages
your pipeline supports:

```bash
make bhashini-check ARGS=--all
```

It prints a line for every language: `ok` with a sample translation, or `FAIL` with the reason.
Some languages may not be available yet.

## 4. Translate the app and the quiz

```bash
make translate
```

This writes `frontend/src/i18n/locales/<code>.json` (screens) and
`backend/hunar/quiz/banks/i18n/<trade>.<code>.json` (quiz questions). Every file is marked
"machine-translated, not reviewed". To do only the languages that passed the check:

```bash
make translate ARGS="--langs ta te bn mr gu kn ml pa or as ur"
```

Re-running is cheap: only new or changed English text is sent again. A sentence whose placeholder
(such as `{n}`) does not come back is left in English and counted in the output.

## 5. Read-aloud with Bhashini voices

Start the app as usual (`make demo`, or `make api` and `make web`). With the keys in `.env`,
`/api/health` reports `"bhashini": {"configured": true}`, and the app switches read-aloud to Bhashini.
It falls back to the phone's own voices for any language Bhashini cannot speak. Clips are cached in
`data/tts_cache/` (gitignored), so each sentence is fetched only once.

## 6. Review, then commit

1. For each language, ask a native speaker, ideally someone who has worked on a building site, to
   read the app and the quiz in that language. They correct mistakes directly in the JSON files.
   Technical words (MCB, earthing, trap) are often clearest in the form workers already use.
2. When a file has been checked, set `"reviewed": true` in its `_meta` (screens) or `meta` (quiz). The
   "machine-translated" banner then disappears for that language.
3. Rebuild and commit:

```bash
npm --prefix frontend run build
```

```bash
git add frontend/src/i18n/locales backend/hunar/quiz/banks/i18n && git commit -m "Bhashini translations (machine, review status per file)" && ./scripts/push.sh origin main
```

## If something fails

- **`Missing in .env`:** the variable names must match `.env.example` exactly.
- **`HTTP 401` or `403`:** the user ID or API key is wrong, or the account is not yet approved.
- **`HTTP 4xx` naming the pipeline:** check the pipeline ID with Bhashini.
- **A language fails in `--all`:** the pipeline does not offer it. Translate the others and leave that
  one on the English fallback.
- **The client itself:** it follows Bhashini's published API format but had not been run against the
  live service before your credentials. If the format differs, the error will show where.
  `backend/hunar/speech/bhashini.py` is a short file to adjust.
