# Walkthrough: run the M4 assessor-agreement study

This is the study the problem statement cares about most: **do assessors agree more with each other
when they use our rubric and pre scores than when they score on their own?** It needs real people.
The tool, the rater mode and the analysis are ready. Until the team runs the study, the README and
report say **RESULT PENDING** for M4.

Everything below runs on the laptop with this repo. Every number in the README and report comes
from `make study`; nothing is typed by hand.

## 0. How big should the study be?

Run `make design-sim` (or look at `docs/figures/m4_design_power.png` and the *M4 study design*
table in the README). It is a **simulation of the method under assumed scenarios, not a result**.
It shows the share of simulated studies of each size (3 to 5 raters, 20 to 30 items) in which
the confidence interval of the improvement excludes zero.

The rule of thumb from it: **more raters and more items help a lot.** Aim for 4 or 5 raters and
30 items. With 3 raters and 20 items, only a large improvement is likely to show up, and a small
one cannot be confirmed by a study of this size at all. Report the interval either way.

## 1. Recruit raters (1 to 2 weeks before)

* 3 to 5 people who assess or teach electrical work: certified RPL assessors, ITI electrician
  instructors, or experienced licensed electricians. **Not** team members who wrote the rubrics.
* Give each a pseudonymous ID (`R1` … `R5`). Keep the list of names and IDs on paper, outside
  the repo.
* Explain the study and get each rater's written agreement to take part and to have their
  anonymised scores used in the project report.
* Book two sessions per rater, **at least one week apart**. Each takes about 30 to 45 minutes.

## 2. Collect 20 to 30 evidence items

An item is **one photo plus one rubric criterion** to score it on, for example a photo of a
switchboard termination scored on *t2_switchboard_wiring / c2_termination*.

* Photograph real electrical practical tasks, done by workers or trainees who have signed the
  consent form (`docs/consent_form.md`). Number each form (`CF-001`, …). Faces are blurred
  automatically, but avoid faces, name tags and house numbers anyway.
* **Mix the quality on purpose:** some clearly well done, some partly done, some with steps
  missing (for example gloves not worn). If every item is "competent", there is nothing to
  disagree about and agreement statistics are meaningless.
* Spread items over the six tasks (`backend/hunar/rubric/tasks/*.yaml`) and their criteria.
  Choose criteria that a photo can show. A photo cannot show a test result that was never
  written down.
* The person who watched the task notes which **checklist items** they saw done (the ids are
  in the task's YAML file, under `checklist:`). This is what the tool would know in a real
  assessment, and it drives the pre score shown in the assisted condition.

## 3. Load the items

1. Put the photos in `data/study/photos/`. The folder is gitignored and is never committed.
2. Copy `docs/study_items_template.csv` to `data/study/items.csv` and fill in one row per item:

   | column | example | meaning |
   |---|---|---|
   | `item_id` | `E07` | short code, never a name |
   | `photo` | `photos/E07.jpg` | path relative to the CSV |
   | `task_id` | `t1_safe_isolation` | rubric task |
   | `criterion_id` | `c1_ppe` | criterion of that task |
   | `consent_ref` | `CF-007` | number of the signed consent form (required) |
   | `ticked` | `ppe_gloves` | checklist items seen done, separated by `;`; `none` if none; empty if not recorded |

3. Run:

```bash
make study-items
```

   The import checks every row first and imports nothing if any row is wrong (missing consent,
   unknown task or criterion, missing photo, a name used as an ID). It blurs faces, removes the
   photo's metadata (including GPS), stores a copy in `data/uploads/study/`, computes the pre score
   and writes each item to the audit log. Re-running it skips items already loaded.
   `--replace` updates an item only if nobody has rated it yet.

## 4. Session 1: unassisted (everyone first)

```bash
make demo
```

* Open http://localhost:5173 → **Rater mode** (on the laptop, or on a phone on the same Wi-Fi
  with `npx vite --host`; see `frontend/README.md`).
* Each rater enters their ID, chooses **Unassisted** and session **1**, then presses Start.
  Leave *Include sample items* **unticked**.
* Raters work **alone and in silence**: no discussion, no looking at each other's screens. Each
  sees the items in their own random order, and ratings cannot be changed afterwards.
* Ratings are saved on the device first and upload by themselves, so a dropped connection loses
  nothing.

Unassisted always comes first. A rater who had already seen the anchored descriptors would not
be judging "unassisted" any more.

## 5. Wait at least a week

This reduces memory of the items. Don't show the raters the rubric files in between.

## 6. Session 2: assisted

Same as session 1, but choose **Assisted** and session **2**. Raters now see the level
descriptors and the tool's pre score with its reasons. They are free to disagree with it.

## 7. Analyse and commit

```bash
make study
```

```bash
make results report
```

This writes `experiments/m4_consistency.json` (Fleiss' kappa, Krippendorff's ordinal alpha,
pairwise agreement, bootstrap intervals, and the assisted-minus-unassisted difference) and
`docs/figures/m4_agreement.png`, then refills the README and report. Sample items are excluded
automatically. To keep a copy of the raw ratings, open http://localhost:8000/api/study/export and
save the CSV **outside** the repo.

```bash
git add experiments/m4_consistency.json docs/figures/m4_agreement.png README.md docs/report && git commit -m "M4: agreement study results" && ./scripts/push.sh origin main
```

## What to say about the result

* State the number of raters and items, and give the intervals, not just the point values.
* If the interval of the difference includes zero, write that **this study could not show a
  difference**. That is not the same as "the rubric does not help".
* Say who the raters were (their role, not their names), that each rater saw the same items in
  both conditions, and that the week's gap reduces memory effects but does not remove them.
* The pre score is based on the observer's checklist and, if the detector was installed, on PPE
  being *visible* in the photo. It never judges workmanship quality.
