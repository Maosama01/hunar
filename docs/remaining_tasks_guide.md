# What is left, and how to do it

For the whole Hunar team. The software is built. What is left needs people: experts who check what the
AI drafted, workers who take the quiz, and team members who write, record and label. This guide covers
the three jobs that did not have a guide yet (parts A, B and C) and points to the guides for the rest.

Every number in the README, report and slides must come from a command in this repository. Until a
command has produced it, the place says **RESULT PENDING**. Nobody types a result by hand.

## The whole list

Write a name in the last column so that every job has one owner.

| # | Job | Who does it | Guide | Command that turns it into a result | Owner |
|---|---|---|---|---|---|
| 1 | Expert review of the quiz questions (electrician, plumber, carpenter) | One certified assessor or ITI instructor per trade | Part A below | `make review-summary` | |
| 2 | Expert review of the practical tasks (the same three trades and the fan pilot) | The same experts; an appliance technician for the fan | Part A below | `make review-summary` | |
| 3 | Hindi review (app text, quiz, tasks) | A native Hindi speaker who did not write the Hindi | Part A below | `make review-summary` | |
| 4 | Quiz with real workers, at least 100 people per trade | Team members run sessions | Part B below | `make quiz-calibrate DB=quiz_pilot` | |
| 5 | About 150 work stories for the mapper test | Several team members | Part C below and [labelling_guidelines.md](labelling_guidelines.md) | `make eval-m1` | |
| 6 | Bhashini keys, then machine translations | One team member | [bhashini_setup.md](bhashini_setup.md) | `make bhashini-check`, `make translate` | |
| 7 | Detector run 2 on Colab | One team member with Colab | [m2_colab_walkthrough.md](m2_colab_walkthrough.md) | `make import-detector` | |
| 8 | Fan video pilot: 20 clips and 2 full runs | Two or more team members | [video_pilot_guide.md](video_pilot_guide.md) | `make eval-clip-speech`, `make eval-clips` | |
| 9 | Assessor agreement study (M4) | 3 to 5 outside assessors | [m4_study_walkthrough.md](m4_study_walkthrough.md) | `make study` | |
| 10 | Paperwork | Whole team | "Paperwork" below | `make report` | |

After any of these, run `make results` (README tables) and `make report` (report), then commit.

## What must come first

Some jobs change what other jobs use, so the order matters:

* **Quiz review (1) and Hindi review (3) before the quiz with workers (4).** The calibration only uses
  answers given to the current version of a question bank. If an expert changes questions after workers
  have answered them, those answers are left out and the sessions have to be repeated.
* **Task review (2) for the electrician before the M4 study (9).** The assessors in the study score
  photos against the criteria; changing the criteria afterwards makes the study measure an old version.
* **Task review (2) for the fan before recording the fan clips (8).** The expert may change a prompt or
  the words the app listens for.
* **Bhashini keys (6) before any machine translation.** Each translated language then needs its own
  native-speaker check (end of part A).
* **Work stories (5) and detector run 2 (7) depend on nothing.** Start them now.

## A. Expert reviews

The quiz banks and the practical tasks were written with AI help from the official qualification files.
The app says so: the quiz shows "DRAFT, not yet reviewed by an expert assessor or ITI instructor". A
person who knows the trade has to check them before the project can say they are fit for real workers.

### Who

* **Quiz and tasks:** for each of electrician, plumber and carpenter, a certified RPL assessor or an ITI
  instructor of that trade. For the fan tasks, an appliance repair technician or an ITI instructor who
  teaches fan repair. Two experts per quiz bank is better than one: where they disagree, ask them both.
* **Hindi:** a native Hindi speaker who talks with workers every day, and who did not write or check the
  Hindi before.
* Not team members. Preferably not the people who will later be assessors in the M4 study: someone who
  helped shape the criteria knows them better than a typical assessor does.
* Give each expert a code: `E1`, `E2`, ... for trade experts, `H1`, ... for Hindi reviewers. Keep the
  list of names and codes on paper, outside the repository. Ask each expert whether they would like to be
  thanked by name in the report, and write their answer on that list.

### Steps

1. **Make the packs.** On the project laptop:

   ```bash
   make review-packs
   ```

   This writes to `data/review/` (not committed; it is rebuilt from the YAML files each time):

   | File | What it is |
   |---|---|
   | `quiz_<trade>.html` | Every question in English and Hindi, the answer marked correct, the sources, and the official performance criteria it is linked to, with boxes to tick |
   | `rubric_<trade>.html` | Every practical task: instructions, checklist, criteria with their official criteria, weights, critical flags and levels 0 to 3; for the fan, the clip prompts and the words the app listens for |
   | `quiz_<trade>.csv`, `rubric_<trade>.csv` | One row per question, task, checklist item, criterion or clip, with empty columns for the expert's verdict |
   | `ui_hindi.csv` | Every text of the app, English next to Hindi, for the Hindi reviewer |

   The packs do not show the AI's guess of how hard each question is, so that the expert's own judgement
   is not steered.

2. **Print.** Open the `.html` file in Chrome and print it (or "Save as PDF" and send that). Experts who
   prefer a screen can fill in the `.csv` file directly in Excel or Google Sheets.
3. **Hand over.** Tell the expert: the content was drafted with AI help from the official files; we want
   honest criticism; "Remove" is a fine answer; it is not a test of them. Ask them to tick **OK**, **Fix**
   (and write the fix) or **Remove** for each question, task part and Hindi text, and to note anything
   missing on the last page. Fill in their code, role and years in the trade at the top, never their name.
4. **Type the verdicts in.** If the expert marked paper, a team member copies the marks into the matching
   `.csv` file. Use only these words in the verdict columns:

   | Column | Values |
   |---|---|
   | `verdict` | `ok`, `fix` or `remove` |
   | `hindi` | `ok` or `fix` |
   | `difficulty` (quiz only) | `easy`, `medium` or `hard` |
   | `correction`, `comment`, `better_hindi` | the expert's own words |

5. **Keep the returned sheet.** Save it as `docs/review/<sheet>_<code>.csv`, for example
   `docs/review/quiz_electrician_E1.csv` or `docs/review/ui_hindi_H1.csv`, and commit it. It is the record
   of the review. Scan the paper pages and keep them with the consent forms, offline.
6. **Apply the fixes.** Change only what the expert asked for.
   * Quiz questions: `backend/hunar/quiz/banks/<trade>.yaml`. A wording fix keeps the question's `id`. A
     completely different question gets a new `id`, a source in `sources` and its NOS and performance
     criterion, like the others. "Remove" means delete the question.
   * Practical tasks: `backend/hunar/rubric/tasks/*.yaml`. For the fan clips, new words go in the `terms`
     lists.
   * Hindi in the app: `frontend/src/i18n/locales/hi.json`. Keep every `{placeholder}` such as `{n}`
     exactly as it is.
   * Where you cannot apply a fix (two experts disagree, or it needs a new source), write it in the
     sheet's `comment` column and raise it in the team.
7. **Change the status, only after a full review.** When an expert has reviewed the whole bank and the
   fixes are in:
   * in the quiz bank, set `version:` to the date of the change, and rewrite `status:` so that it does not
     start with "DRAFT" any more, for example: *"Reviewed on 2 December 2026 by an ITI electrician
     instructor (E1); fixes applied. Difficulties are AI estimates, not yet calibrated from real answers."*
     The app stops showing "DRAFT" once the status no longer starts with it;
   * in each reviewed task file, rewrite `review:` in English and Hindi the same way.

   If only part was reviewed, say exactly which part, and keep "DRAFT" at the start.
8. **Check and commit.**

   ```bash
   make test
   make review-summary
   ```

   `make test` checks that every bank and task file is still valid and that every NOS and performance
   criterion a question cites exists in the official file. After a Hindi fix, also run
   `npm --prefix frontend run build`: it stops if a text is missing from `hi.json`. `make review-summary` counts the verdicts in `docs/review/` into
   `experiments/expert_review.json`; quote numbers such as "4 of 40 questions changed" only from there.
   Commit with a message such as *"Review: electrician quiz bank by E1 (ITI instructor), 4 fixed, 1
   removed"*.

### Other languages

After the Bhashini keys arrive, `make translate` writes machine translations of the app and the quiz for
the other 21 languages. The app labels them "Machine-translated, not yet checked by a native speaker". For
each language, a native speaker reads the file (`frontend/src/i18n/locales/<lang>.json` and
`backend/hunar/quiz/banks/i18n/<trade>.<lang>.json`), the team applies the fixes, and only then sets
`"reviewed": true` in that file's `_meta` (app) or `meta` (quiz) section. Do this for the languages your workers actually speak.

## B. The quiz with real workers

**Goal:** at least **100 people per trade** (electrician, plumber, carpenter), each taking the quiz once.
`make quiz-calibrate` then turns their answers into measured question difficulties; until then the app
uses the AI's first estimates and says so.

**Before you start:** the quiz bank of that trade and the Hindi are reviewed (part A), and `make test`
passes.

### Who takes it

* People who do the work: working electricians, plumbers and carpenters. Final-year ITI trainees are also
  fine; write down which group each session was, because difficulties measured on trainees may differ.
* Adults only (the app asks).
* **Not** team members, and not the experts who reviewed the questions: they have seen the answers.
* Each person takes the quiz **once per trade**. After a quiz the app shows the right answers, so the
  calibration uses only each person's **first** finished quiz in a trade. A second try is not used, and
  neither is a quiz on an older version of the bank.

### Consent

Each person signs the quiz-pilot part of [the consent form](consent_form.md) and agrees on screen in the
app. Keep the signed forms offline; never commit them. The person's mobile number and name stay only in
the pilot's database on the laptop (below).

### Set up the laptop (once per session)

All sessions use **one laptop** and **one database**, kept apart from test data. In the app's normal
database there are already test accounts from development, and they must not be counted.

1. Open two terminal windows in the project folder. In the first:

   ```bash
   make api DB=quiz_pilot
   ```

   `DB=quiz_pilot` keeps the pilot's accounts in their own file, `data/quiz_pilot.db` (never committed).
   Use the same `DB=quiz_pilot` every time, on every command in this part.
2. In the second:

   ```bash
   make web LAN=1
   ```

   It prints a line such as `Network: http://192.168.1.8:5173/`. That is the address the phones open.
3. Connect the laptop and the phones to the **same Wi-Fi**. College Wi-Fi may block phones from
   reaching a laptop; if so, turn on a hotspot on one phone and connect the laptop and the other phones to
   it. If the Mac asks whether to allow incoming connections, choose Allow.
4. Test with a team member's phone first: open the address, check that the app appears, then go back
   without creating an account. The address starts with `http://`, so the app cannot be installed on the
   phone from it and does not work offline. That is fine for a session.
5. Never take the quiz yourself on this database. To try the app, stop the first command (Ctrl+C), run
   `make api DB=try_out` instead, and afterwards delete `data/try_out.db` and start `make api
   DB=quiz_pilot` again.
6. If `make api` says the address is already in use, another program is using port 8000 on this laptop.
   Close that program first.

### Run a session

1. **Before anyone starts, say this** (in the group's language):
   * "This is a self-check about your trade. It is not an exam and gives no certificate. Customers never
     see it."
   * "Read each question fully. If you do not know, press **Don't know**. Do not guess."
   * "If you answer too fast without reading, the quiz does not count."
   * "Please do it alone, without talking about the answers."
2. **Each person, on the phone:** choose the language → **I am a worker** → read the short intro or
   **Skip** → choose the trade → on "Your data, your choice", tick **I agree** for the three required
   items and **I am 18 years or older** (showing the profile to customers is optional: they can leave it
   off) → **Next** → enter their mobile number, a first name or nickname, and a PIN twice → **Create
   account and start the quiz** → answer the questions (12 to 25; the app decides when it has enough).
3. **If someone has no smartphone,** lend them one. After their quiz, open **Settings** (the button at
   the top right), choose **Log out**, and hand the phone to the next person.
4. **If someone reads with difficulty,** they can press **Read aloud**. You may also read the question
   and options aloud exactly as written. Never explain, hint or react to an answer.
5. **Note the session on paper:** date, place, group (working or ITI trainees), how many people per trade,
   how many needed reading help. No names.

### Watch the count

At any time:

```bash
make quiz-calibrate DB=quiz_pilot
```

It prints, per trade, `RESULT PENDING (attempts N)` until 100 people have a counted first quiz. Nothing
changes in the app before that.

### At 100 people

```bash
make quiz-calibrate DB=quiz_pilot
make results
make test
```

This writes the new difficulties to `backend/hunar/quiz/banks/params/<trade>.json` and a summary to
`experiments/quiz_calibration_<trade>.json`, including how many answers each question got. Commit both.
New quizzes then use the measured difficulties.

100 people is the minimum at which the calibration runs, not plenty: a question needs at least 30
answers before its difficulty is updated, and about 100 to 150 answers per question for a precise
estimate. Report the number per question from the summary file, and keep collecting if you can.

### Afterwards

* The database holds real mobile numbers. Never copy `data/quiz_pilot.db` to a pen drive, cloud folder or
  chat. Keep the laptop locked when you leave it.
* Anyone can erase their account in the app (**Privacy**, then **Erase my account now**), or ask you to.
* By the deletion date on the consent form, and after the final `make quiz-calibrate`, delete
  `data/quiz_pilot.db`. The calibration files keep no names or numbers.

## C. Work stories for the mapper test

The mapper suggests which qualification fits what a worker says about their work. To test it, we need
about **150 short work stories** written by the team, each labelled with the one qualification that fits.
The full rules are in [labelling_guidelines.md](labelling_guidelines.md); in short:

1. **Spread:** 30 per qualification (Assistant Electrician, Industrial Electrician, Rooftop Solar PV,
   Wireman Control Panel, Smart Energy Meter technician), and for each 10 in English, 10 in Hindi
   (Devanagari) and 10 in Hinglish (Hindi typed in English letters). Several team members write, so that
   no single style dominates.
2. **Best source: a real conversation.** Talk with an electrician, solar installer or meter technician
   you know. They sign the work-story part of [the consent form](consent_form.md). Record nothing; take
   notes, and write the story the same day in your own words, in the first person: "I have done house
   wiring for 8 years with my uncle." No names, phone numbers, employers or exact places.
3. If you cannot talk with someone, imagine one concrete person (age, where they learnt, where they
   work), as the guidelines describe.
4. **Do not look at the qualification files while writing.** Copying their words makes the test too easy.
5. **Add the stories:**

   ```bash
   make declarations AUTHOR=AB
   ```

   Use your initials or team code for `AB`. The tool asks for the language, the text (finish it with an
   empty line), the qualification it fits best and whether it is a hard case, and adds a row to
   `data/labels/declarations.csv`. Run `make declarations` on its own to check the file.
6. **Second labeller:** another team member labels a random fifth of the stories without seeing the
   first labels. Discuss the disagreements and fix or remove them. Never change a label after seeing
   what the mapper predicted.
7. **Measure:**

   ```bash
   make eval-m1
   make results
   ```

## Paperwork

* Report page 1 (`docs/report/report.md`, the lines marked in square brackets): team names and SAP IDs,
  faculty supervisor, department and institute. Then `make report`.
* [The consent form](consent_form.md): fill in the team contact and the faculty supervisor at the top,
  and the deletion date in point 6.
* The hackathon deck: its "Where we are" slide is out of date; update it from the README status table.

## Rules that always apply

* AI suggests, the assessor decides. Nothing in this work certifies anyone.
* No result is typed by hand; until a command produces it, write RESULT PENDING.
* Made-up or sample data stays labelled as such and is never counted as real.
* Signed forms, names and phone numbers never go into the repository.
