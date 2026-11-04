# Viva preparation: 23 likely questions with answers

Generated from `viva_questions.src.md` by `make report`. Every number comes from `experiments/` or the
parsed data; if a result is pending, say so plainly.

**1. What problem does Hunar solve, and what does it not do?**
It helps an RPL assessor evaluate informally trained domestic electricians: it maps the worker's
self-declaration to qualification packs, guides practical tasks, suggests rubric levels with reasons,
checks evidence photos for reuse and builds a competency profile. It does not certify anyone, does
not judge workmanship from photos, and does not replace the theory/viva part of NSQF assessment.

**2. Where did the qualification packs come from? Did you make them up?**
From the official qualification files on nqr.gov.in. `scripts/fetch_qps.py` downloads them and records
URL, date and SHA-256 in `data/processed/qp_manifest.json`; `hunar.mapper.qp_parser` extracts
27 NOS and 345 performance criteria. A test checks that every rubric criterion
points to a PC that exists in the parsed official pack.

**3. Why Assistant Electrician (CSDCI, NSQF 3)?**
Its NOS cover low-voltage single-phase wiring in residential and commercial buildings, temporary site
supply and distribution boards, which is what a domestic electrician does; it is current on NQR
(valid till 2028). The distractors are neighbouring electrical jobs that share vocabulary.

**4. How does the mapper work?**
Split the declaration into sentences, compute similarity to every performance criterion, and score a
pack as the mean over sentences of the best match to its core criteria. Explanations show the matched
sentence for each criterion and the unmatched core criteria as gaps. The aggregation was fixed before
evaluation.

**5. Why match at performance-criterion level instead of classifying the whole text?**
It needs no training data (we have none yet), it can explain which part of the declaration supports
which criterion, and it produces a gap list the assessor can probe.

**6. Your embedding model is not better than TF-IDF overall. Why use it?**
On the synthetic set TF-IDF top-1 is 0.543 and MiniLM
0.507; the CIs overlap. But TF-IDF falls to near chance on
Hindi in Devanagari (top-1 0.25, chance 0.20) and MiniLM
does not (0.42). Excluding Hindi-script users would
be unfair. The exploratory hybrid combines both, but it was designed after seeing results and must
be confirmed on real data.

**7. Is your evaluation data real?**
No. The 150 declarations are synthetic, written by an AI model that saw only job titles and summaries,
not the criteria. They are labelled synthetic in the data, tables, figures and report. They test the
pipeline. The team-written set (tool and guidelines ready) will give the real numbers.

**8. How did you avoid the baselines getting free credit?**
Ties are scored as the expected value under random ordering. A baseline that gives every pack a score
of zero on Devanagari text gets chance credit, not credit for whichever pack is listed first; a unit
test covers this.

**9. Why did LaBSE do worse?**
LaBSE is trained for translation retrieval (finding the same sentence in another language), not for
paraphrase similarity between an informal description and a formal criterion. On our data its
overall top-1 was 0.440.

**10. How are pre scores computed? Can the AI give full marks?**
From the assessor's observed checklist: none ticked → 0, some → 1, all → 2. The engine never suggests
3 (proficient). Photo detections become reasons and can flag conflicts; the self-declaration is shown
as context only and never raises a level. With no observed evidence there is no suggestion.

**11. What stops the assessor from just clicking "accept" on everything (automation bias)?**
Suggestions come with reasons and confidence; criteria with no evidence have no suggestion and must
be scored manually; level 3 can only come from the assessor; every accept and override is in the audit
log, so acceptance patterns can be reviewed. Measuring this properly is part of the M4 study.

**12. How is the final recommendation decided?**
Weighted mean of final levels (level/3), per NOS and overall, against the official 70 % aggregate
pass mark from the qualification file; any critical safety criterion below level 2 blocks a positive
recommendation. Then the assessor signs off, agreeing or recording their own outcome with a comment.
Unit tests cover the edge cases.

**13. How is the audit log tamper-evident?**
Each entry stores the SHA-256 of the previous one (hash chain), SQLite triggers block UPDATE and
DELETE, and `/api/audit/verify` recomputes the chain. A test drops the trigger, edits an entry and
shows the verification reports the first broken entry.

**14. How does the offline mode work?**
Every write is an operation in an IndexedDB outbox with a client-generated id. When online, the sync
engine posts operations in order; the server records applied operation ids so replays are ignored, and
stops at the first rejection so later dependent operations are not applied out of order.

**15. How do you protect privacy?**
Written consent is required before a photo is accepted, faces are blurred before anything is stored,
workers are pseudonymous codes, raw data and the database are not in git. Limitation: Haar cascades
miss some faces, and photos taken offline wait unblurred on the device until sync.

**16. How well does duplicate-photo detection work?**
On real public PPE photos with simulated reuse, pHash at threshold
4 flags 0.016 of unrelated
photos and catches recompressed and resized copies (recall 1.00
and 1.00), but not crops, rotations, borders or mirroring.
Catching those at a higher threshold would flag many genuinely different site photos.

**17. What is the mAP of your detector?**
The headline number is RESULT PENDING: it needs the second Colab run on the re-split data. The first
run, on the dataset's published splits, scored 0 for helmets because that training split has
0 helmet boxes, and could not score gloves because
that test split has 0. Only goggles were measurable
(clean-test mAP50 0.795). We
report that run as a diagnostic, not as the result. Even when trained properly, the model only detects
presence of PPE and tools, never quality of work.

**18. What did you find about the public dataset?**
Two things. Its published splits are class-disjoint (no helmets in train, no gloves in test), and it
is mostly video frames: the 1,935-image test split has only 407 distinct images, and all safety-shoe
boxes come from two videos. We pool the 11978 images, group near-identical frames
and re-split with iterative stratification (Sechidis et al. [63]), so every class is in every split and
0 test images have a near-duplicate in
training (the published split had 136).

**19. How will you show improved inter-assessor agreement?**
A within-subject study: 3 to 5 real assessors (not the rubric authors) score 20 to 30 consented
evidence items unassisted and, at least a week later, assisted, in a random but reproducible order.
We compare Fleiss' kappa and ordinal Krippendorff's alpha with bootstrap CIs and bootstrap the
assisted-minus-unassisted difference. Result: pending, because we need real assessors.
*Is that enough people?* Only for a large effect. We simulated our own analysis under stated
assumptions (a simulation of the method, not a result): if the rubric raised alpha from 0.50 to 0.80,
3 raters on 20 items would show it in
71% of simulated studies, and 5
raters on 30 items in 99.6%; a rise
to 0.60 would mostly go unseen
(27% even with 5 x 30). So we aim
for 4 to 5 raters and 30 items, and we will report the interval, not just "better" or "worse". With
no real effect the simulated studies wrongly "found" one in about
2% of cases, close to the
nominal 2.5 %, which checks the method itself.

**20. What would you do with more time?**
Write and cross-label the real declaration set; train the detector; get the rubrics reviewed by a
certified assessor; run the agreement study; test voice input with real workers' speech; add
on-device face blurring; extend to more trades by parsing more NQR files.

**21. Can a worker speak instead of type? How good is it?**
Yes, optionally (`make voice`). The facilitator records the worker; faster-whisper `small` transcribes
on the laptop CPU; the audio is deleted at once; the text is only a draft, and the declaration cannot
be saved until the facilitator ticks that they read it back to the worker. We have only tested it on
**synthetic** speech (macOS text-to-speech reading our synthetic declarations): word error rate
0.05 in English but 0.43 in Hindi, and top-1 mapping fell in every
language (Hindi 0.42 → 0.28) while top-3 barely
moved. Even English, with almost no word errors, lost top-1 accuracy: punctuation, capitals and
number format changed the sentence units and tokens the model sees, which told us the mapper's top-1
margins are thin.
Real workers on a noisy site will do worse; testing with consenting workers is a next step.

**22. How does the worker quiz work, and can a worker cheat it?**
It is adaptive: a Rasch model scores answers with EAP, the next question balances the qualification's
NOS weights and targets the current estimate, and it stops when the uncertainty is small enough
(posterior SD 0.5 after 12 answers) or at 25 questions. In our labelled simulation it needed
15.4 questions instead of 20 for a similar error. It can be cheated: it is
unsupervised and someone else could answer. That is exactly why it never produces a badge; it is a
self-check for the worker and context for the assessor. We still reduce noise: options are shuffled,
the answer key never reaches the phone, answers faster than reading time are flagged and not scored,
and "don't know" discourages guessing. The questions are drafts from official sources (qualification
files, CEA regulations, Indian Standards) and need review by an ITI instructor; difficulties are
uncalibrated until about 100 real attempts exist.

**23. What does a customer's "verified" badge mean? What stops a fake assessor?**
The badge says "practical skills assessed by an assessor against Assistant Electrician (NSQF 3) on
<date>, not a government certificate". It appears only when an assessor account, created by an admin
on the server, signs off a positive recommendation; every decision and the sign-off are in the
hash-chained audit log under that account. Assessor accounts cannot self-register. A second badge,
"permit document checked", is set by an admin after seeing the State permit; electrical jobs that
need a permit under CEA regulation 31 cannot be booked without it. We do not claim identity
verification: there is no Aadhaar or permit-register check yet.


**24. Why must every worker take the quiz right after registering, if it is not a test?**
Because it is the one step that tells us, and the worker, what they know before anyone else is
involved. A worker chooses a trade while registering and the first quiz starts with the account; until
one is finished the app shows only the quiz and privacy settings, and the server refuses a profile, a
listing, a booking or an assessment request. Finishing is what counts: there is no pass mark, and
"don't know" is always allowed, so nobody is shut out for a low score. The assessor sees the result as
context. Because the quiz processes the worker's answers, consent to it is required for workers, and
withdrawing it means erasing the account. A compulsory quiz invites tapping through, so a quiz counts
only if at least half of its answers came slower than reading time (its response-time effort, Wise and
Kong 2005); otherwise the worker is asked to take it again. The one-half line is our choice and has to
be checked on real attempts.
