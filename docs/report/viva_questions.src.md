# Viva preparation: 20 likely questions with answers

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
{{fact:n_nos}} NOS and {{fact:n_pcs}} performance criteria. A test checks that every rubric criterion
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
On the synthetic set TF-IDF top-1 is {{m1_mapper_synthetic:methods.tfidf.overall.top1_acc|.3f}} and MiniLM
{{m1_mapper_synthetic:methods.minilm.overall.top1_acc|.3f}}; the CIs overlap. But TF-IDF falls to near chance on
Hindi in Devanagari (top-1 {{m1_mapper_synthetic:methods.tfidf.by_language.hi.top1_acc|.2f}}, chance 0.20) and MiniLM
does not ({{m1_mapper_synthetic:methods.minilm.by_language.hi.top1_acc|.2f}}). Excluding Hindi-script users would
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
overall top-1 was {{m1_mapper_synthetic:methods.labse.overall.top1_acc|.3f}}.

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
{{m2_hashing:hashes.phash.chosen_threshold}} flags {{m2_hashing:hashes.phash.test.false_flag_rate_fresh|.3f}} of unrelated
photos and catches recompressed and resized copies (recall {{m2_hashing:hashes.phash.test_recall_by_transform.jpeg_q50|.2f}}
and {{m2_hashing:hashes.phash.test_recall_by_transform.resize_50pct|.2f}}), but not crops, rotations, borders or mirroring.
Catching those at a higher threshold would flag many genuinely different site photos.

**17. What is the mAP of your detector?**
RESULT PENDING. The Colab notebook is ready; it maps the public PPE dataset to our classes, checks
train/test leakage from near-duplicate frames and reports mAP on a clean test subset. Even when
trained, it only detects presence of PPE and tools, never quality of work.

**18. What did you find about the public dataset?**
Its test split of 1,935 images contains only 407 distinct images after grouping near-identical frames.
Random train/test splits of such data leak near-duplicates and inflate mAP, which is why the notebook
reports a clean-subset score.

**19. How will you show improved inter-assessor agreement?**
A within-subject study: 3 to 5 real assessors (not the rubric authors) score 20 to 30 consented
evidence items unassisted and, at least a week later, assisted, in a random but reproducible order.
We compare Fleiss' kappa and ordinal Krippendorff's alpha with bootstrap CIs and bootstrap the
assisted-minus-unassisted difference. Result: pending, because we need real assessors.

**20. What would you do with more time?**
Write and cross-label the real declaration set; train the detector; get the rubrics reviewed by a
certified assessor; run the agreement study; add spoken declarations (Whisper) and on-device face
blurring; extend to more trades by parsing more NQR files.
