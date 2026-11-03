# Slide outline (13 slides, about 11 minutes + demo)

Generated from `slides_outline.src.md` by `make report`; numbers come from `experiments/`.

1. **Title.** Hunar: AI-assisted Recognition of Prior Learning for domestic electricians.
   SIH26242 (MSDE). Team, supervisor. Tagline: *AI suggests, the assessor decides.*

2. **The problem.** {{fact:plfs_informal}} of non-agricultural workers are in informal enterprises
   (PLFS 2025 [11]); skills are learnt on the job and stay uncertified. RPL exists (NCVET guidelines
   [4]), but practical assessment is manual, slow and inconsistent between assessors.

3. **What SIH26242 asks for and our scope.** Five requirements (declaration mapping, guided practical
   evaluation, standard rubrics, competency profile with sign-off, offline). One trade: domestic
   electrician. Target: Assistant Electrician (CSDCI, NSQF 3) plus four distractor qualifications from
   the NQR. English, Hindi, Hinglish. Runs on a laptop CPU.

4. **System overview.** Flow diagram: declaration → M1 mapper → practical tasks → M2 evidence →
   M3 pre scores → assessor decisions → profile → sign-off, with the offline queue and audit log.
   One line per module.

5. **Real data, not stubs.** Five official qualification files parsed: {{fact:n_nos}} NOS,
   {{fact:n_pcs}} performance criteria, each with source URL, date and SHA-256. Show one parsed
   PC next to the PDF row. Mention the quirks we found in the official files.

6. **M1 mapper: how it explains itself.** Screenshot: ranked packs, matched sentence → PC with
   similarity, skill gaps. The aggregation rule was fixed before evaluation.

7. **M1 results (SYNTHETIC set, labelled).** Figure `m1_top1_by_language.png`. Message: lexical
   baselines collapse on Devanagari (TF-IDF top-1 {{m1_mapper_synthetic:methods.tfidf.by_language.hi.top1_acc|.2f}},
   chance 0.20); multilingual MiniLM {{m1_mapper_synthetic:methods.minilm.by_language.hi.top1_acc|.2f}}; the exploratory
   hybrid reaches top-3 {{m1_mapper_synthetic:methods.hybrid.overall.top3_acc|.2f}} overall. Caveat on the slide:
   synthetic declarations, wide CIs, real set pending. One line on voice: spoken declarations work, but
   on synthetic speech Hindi word error rate is {{m1_voice_synthetic:by_language.hi.corpus_wer|.2f}}, so the facilitator reads every
   transcript back.

8. **M3 rubric engine.** One rubric criterion on screen: NOS/PC links, four anchored levels, critical
   flag. Pre-score rules in four bullets (checklist drives level, never suggests 3, photos are reasons,
   declaration is context only). Official 70 % pass mark; a failed safety criterion blocks the
   recommendation.

9. **Assessor in control + audit.** Accept / override-with-reason, disagree at sign-off, append-only
   hash-chained log, tamper test. Table: what the tool does vs what the assessor decides.

10. **M2 evidence integrity.** Consent gate, faces blurred before storage. Hashing result: exact
    re-uploads caught (recompression recall {{m2_hashing:hashes.phash.test_recall_by_transform.jpeg_q50|.2f}}) at
    {{m2_hashing:hashes.phash.test.false_flag_rate_fresh|.3f}} false flags; crops/rotations missed. Finding: the
    public PPE dataset is mostly near-duplicate frames, and its published splits are class-disjoint
    (train has {{m2_ppe_split:published_splits.train.boxes.helmet}} helmet boxes), so run 1 is a
    diagnostic and the data were re-split; detector mAP RESULT PENDING (run 2). Presence only, never
    quality.

11. **Offline first.** Outbox → ordered, idempotent replay; client-side UUIDs; demo with network off.

12. **Workers and customers.** Onboarding in 23 languages, phone + PIN login, itemised consent
    (DPDP Act). Worker: compulsory adaptive self-check quiz straight after registering (3 trades,
    built from official sources; no pass mark, but nothing else opens until it is done, and a rushed
    quiz has to be taken again), then profile,
    practical assessment request, bookings. Customer: search, badges that say who checked what, booking
    that respects CEA reg. 31 (permit-only jobs). Simulation (labelled): the quiz needs
    {{quiz_cat_simulation:trades.electrician.scenarios.calibrated.adaptive.mean_items|.1f}} questions instead of 20. Quiz = self-check, never a badge.

13. **Honest status and next steps.** What is real, what is synthetic, what is pending (real
    declarations, detector training, rubric review by a certified assessor, the assessor-agreement
    study). Figure `m4_design_power.png`, labelled SIMULATION OF THE METHOD: 3 raters x 20 items
    catch a large improvement (alpha 0.50 to 0.80) in
    {{m4_design_simulation:scenarios.plus_030.detected_share_by_design.3x20|.0%}} of simulated studies, so
    we aim for 4 to 5 raters and 30 items. Ask the panel for help finding assessors.

**Backup slides:** architecture diagram, data model, metric definitions (top-k, MRR, Fleiss' kappa,
Krippendorff's alpha), the study protocol, limitations list.
