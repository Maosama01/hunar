# Research behind the two-sided Hunar app (workers and customers)

Desk research done on 3–4 November 2026 to design the worker quiz, login, booking and language
support. Every statement below comes from a source that was opened and read. **UNCERTAIN** marks
things that could not be confirmed on a primary page. Numbers here are external facts with their
source. They are not Hunar results.

## 1. What "verified" means today, and why Hunar's badge is different

**Home-services platforms check identity more than skill.**

- *Urban Company*'s IPO offer document (draft red herring prospectus filed with SEBI) describes:
  - a three-step background check by third-party agencies: documents, criminal record and address;
  - in-house training, after which workers "are certified by" NSDC;
  - retraining when ratings fall.

  It reports 48,169 monthly active service professionals (nine months to 31 Dec 2024).
  [UC DRHP](https://www.morganstanley.com/content/dam/msdotcom/en/indiaofferdocuments/pdfs/Urban_company_limited-Draft_Red_Herring_prospectus.pdf)
- *Urban Company* workers have also reported:
  - commission disputes, with rates between 8.5 % and 30 % in 2021 ([DT Next](https://www.dtnext.in/lifestyle/technology/urban-company-slashes-commission-after-workers-protest));
  - IDs blocked when ratings fell below 4.8 ([Business Today](https://businesstoday.in/technology/story/urban-company-punishes-workers-when-users-cancel-services-blocks-ids-for-getting-ratings-below-48-out-of-5-385722-2023-06-15)).
- *Justdial*'s own terms say "JD verified" means only that the vendor's name, address and contact
  details were verified as existing. Justdial "does not examine whether the vendors are good,
  reputable or quality". [Justdial terms](https://www.justdial.com/Terms-of-Use/Listing-Services)
- *Snabbit* and *NoBroker* claim background checks but publish no process. *Housejoy*'s domain is parked.
- None of these platforms tests electricians against a State permit or a national qualification
  standard.

**Government certificates can be checked, but RPL evidence has been weak.**

- PMKVY 4.0 RPL is for ages 18–59 with prior experience in the job role. It uses:
  - pre-screening;
  - an assessment by NCVET-approved bodies, with a 70 % pass mark and core NOS weighted at 70 %;
  - a QR-coded digital certificate in DigiLocker and Skill India Digital.

  [PMKVY 4.0 guidelines](https://www.msde.gov.in/static/uploads/2024/02/PMKVY-4.0-Guidelines_final-copy.pdf)
- Skill India Digital Hub issues "tamper-proof, portable and verifiable certificates", integrated with
  DigiLocker, e-Shram, National Career Service and Bhashini.
  [PIB, 1 Apr 2026](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2247750)
- DGT's e-credential standard puts a URL or offline-verifiable signature data in the QR code.
  Assessors can sign each piece of evidence.
  [DGT 2019](https://www.bharatskills.gov.in/pdf/ESCS/Electronic_Skill_Credential_Standard_v1.0.pdf)
- The CAG audit of PMKVY ([PRS summary](https://prsindia.org/policy/report-summaries/skill-development-under-pm-kaushal-vikas-yojana))
  found:
  - the same photos reused as evidence across trainings;
  - geotagging missing in 84 % of on-spot inspections;
  - unreliable RPL documents.
- CSDCI publishes a list of blacklisted assessors. 12 of the 21 are for Assistant Electrician, Hunar's
  target qualification. [CSDCI](https://www.csdcindia.org/blacklisted-assessors/)

**Design consequence.** Hunar shows a customer only badges that say exactly what was checked:
- "practical skills assessed by an assessor, against Assistant Electrician (NSQF 3), on <date>": only
  after an assessor, logged in with an assessor account, signs off a positive recommendation;
- "State permit document checked by an admin".

Both badges say they are not government certificates. The quiz never produces a badge. Evidence reuse
is caught by perceptual hashing (M2), and every action is in the hash-chained audit log, which
answers the CAG findings.

## 2. The law on who may do electrical work

- **CEA (Measures relating to Safety and Electric Supply) Regulations, 2023** (Gazette, 8 June 2023):
  - **Regulation 31(1)** allows installation work only by a State-licensed electrical contractor,
    under the direct supervision of a certificate-of-competency holder, by a permit holder. This
    covers "additions, alterations, repairs and adjustments".
  - The only exemption is replacing lamps, fans, fuses, switches, domestic appliances up to 250 V and
    fittings "as in no way alters its capacity or character".
  - **31(2):** non-compliant work must not be energised.

  [CEA regulations](https://cea.nic.in/whats-new/file?path=%2Fhome%2Fcea_website%2Freports%2Fgeneral%2Fen%2Fpdf_100_183_English.pdf&mode=view)
- **States issue the permits.** Examples:
  - Tamil Nadu's Electrical Licensing Board: wireman, wireman-helper and supervisor certificates.
  - Kerala's Licensing Board: wireman permits; NTC/NCVT holders get them directly, others take an exam
    after a year as a registered apprentice.
  - Maharashtra: a practical and oral wireman exam.
  - Delhi: a Certificate of Competency Class II after two years' experience.

  Eligibility details differ by State, and Tamil Nadu's are UNCERTAIN.

**Design consequence.**
- Each electrical job in the booking catalogue is marked *needs permit* or *exempt*, following
  reg. 31.
- A customer can book a worker for a *needs permit* job only if an admin has checked the worker's
  permit document.
- The worker's self-declared permit is shown as "self-declared", never as checked.

## 3. Privacy law: DPDP Act 2023 and DPDP Rules 2025

- **Consent:** it must be "free, specific, informed, unconditional and unambiguous", limited to what
  the purpose needs, and withdrawing it must be as easy as giving it (s. 6).
- **Notice:** it must list each item of personal data and the purpose, with links to withdraw and to
  complain (Rule 3).
- **Data handling:**
  - security safeguards (s. 8(5));
  - erasure when consent is withdrawn (s. 8(7));
  - breach notice to the Board within 72 hours (Rule 7).
- **Children:** under 18s need verifiable parental consent (s. 9).
- **Status:** the Rules were notified on 14 Nov 2025 with phased compliance.
  [PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014)
- **Source caveat:** the section wording was read from a third-party mirror (dpdpa.com). It must be
  checked against the official MeitY text, which could not be opened.

**Design consequence.** Hunar asks for consent separately for each purpose: account, assessment,
profile display and contact sharing. Each lists its data items (`backend/hunar/accounts/notice.py`).
- Withdrawing *profile display* hides the profile at once.
- Withdrawing *assessment* erases quiz answers.
- Erasing the account removes the phone number and name, ends sessions, and cancels open bookings.
- Only adults (18+) can register, which matches PMKVY RPL and avoids collecting children's data.
- Audit entries name accounts by id only. Phone numbers are shown to the other party only after a
  booking is accepted.
- PINs are hashed with salt and a server-side pepper.

## 4. Who uses phones, in which languages

- **Phone ownership** (MoSPI Comprehensive Modular Survey: Telecom, Jan–Mar 2025):
  - 85.5 % of households have at least one smartphone;
  - among mobile owners aged 15 and over, smartphone ownership is 79.2 % for rural men and 75.6 % for
    rural women.

  [MoSPI via PIB](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/may/doc2025529560001.pdf)
- **Gig work:** NITI Aayog estimated 77 lakh gig workers in 2020–21 (2.6 % of the non-agricultural
  workforce). [PIB, 27 Jun 2022](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1837277)
- **Languages:** the DPDP Act allows consent notices in English or any Eighth Schedule language, and
  SIDH integrates Bhashini.
- **Low-literacy interfaces:**
  - Text-only interfaces were unusable for first-time low-literacy users; graphical interfaces with
    voice feedback did much better (Medhi, Sagar and Toyama, ICTD 2006, doi:10.1109/ICTD.2006.301841;
    Medhi et al., ACM TOCHI 2011, doi:10.1145/1959022.1959024).
  - Farmers using a voice forum preferred keypad numbers to speech input (Avaaj Otalo,
    doi:10.1145/1753326.1753434).

**Design consequence.**
- Onboarding starts with a language picker that shows all 23 languages in their own scripts.
- Large icon cards, short sentences, and read-aloud on every quiz question.
- Tap answers are the main input; voice is optional.
- The interface works at 360 px.

## 5. Language technology

- **Bhashini** (bhashini.gov.in):
  - An organisation registers once and gets ASR, TTS and translation APIs through a "pipeline config"
    then "pipeline compute" call ([API docs](https://bhashini.gitbook.io/bhashini-apis)).
  - The terms require an access agreement, forbid unauthorised commercial use or redistribution, and
    disclaim any warranty that outputs are correct.
- **Design consequence:**
  - Bhashini keys stay on the server. Text-to-speech goes through `/api/tts` and is cached.
  - Translation is a batch script (`make translate`) that writes files marked "machine-translated, not
    reviewed". The app labels such text and falls back to English or Hindi where a translation is
    missing.
  - The client follows the documented payloads but has **not been tested against the live service**,
    because no credentials exist yet.
- **Open alternatives:** AI4Bharat IndicTrans2 (MIT, all 22 languages) and Indic Parler-TTS
  (Apache-2.0) are open models. Their Hugging Face downloads need a click-through acceptance, so they
  were not used.
- **Whisper's Hindi accuracy:** published word error rate on FLEURS Hindi is 38.4 for Whisper small
  and 21.5 for large-v2 (Radford et al., Table 13). This matches Hunar's own synthetic-speech check:
  Hindi is far worse than English with `small`.

## 6. How the quiz measures knowledge

**What the official assessment looks like**

- *Assistant Electrician* (QG-03-CO-03951-2025-V2-CSDCI) weights the main NOS N0602–N0605 at 20 % each,
  and safety, teamwork, planning and employability at 5 % each.
- Theory to practical is 30:70. The pass mark is 70 % at qualification level.
- Theory is an MCQ or viva "prepared externally and externally marked", taken in a centre with ID
  checks.
- NCVET's assessment-agency guidelines ask for:
  - question banks in local languages;
  - a "proportional mix of easy, medium and hard" questions;
  - randomised test engines.

  [NCVET guidelines](https://www.msde.gov.in/static/uploads/2024/04/Upload-Final-AA-guidelines-28.9.20_0.pdf)

**Model chosen: Rasch (one-parameter item response theory)**

- Rasch needs about 100–150 respondents per item for ±½ logit ([Linacre, RMT 7:4](https://www.rasch.org/rmt/rmt74m.htm)),
  against 500–1,000 per item for the three-parameter model (Thompson and Weiss 2011,
  doi:10.7275/wqzt-9427).
- **Scoring:** expected a posteriori with a N(0, 1) prior (Bock and Mislevy 1982,
  doi:10.1177/014662168200600405). The posterior SD is reported as the uncertainty.
- **Choosing the next question:**
  - content balancing to the qualification's NOS weights (Kingsbury and Zara 1989,
    doi:10.1207/s15324818ame0204_6);
  - then the item closest to the current estimate, picked at random among the top three to spread
    exposure.
- **Stopping:** posterior SD ≤ 0.5 after at least 12 scored items, or 25 items.
- **Cold start:**
  - item difficulties begin as AI-drafted estimates labelled *uncalibrated* (empirical-Bayes priors
    from item features: Mislevy 1988, doi:10.1177/014662168801200306);
  - `make quiz-calibrate` re-estimates them by MAP with that prior once 100 real attempts exist;
  - parameter sets are versioned and never change mid-quiz.
- **Rapid guessing:** answers faster than reading time are recorded and flagged, but not scored (Wise and
  Kong 2005, doi:10.1207/s15324818ame1802_2). A "don't know" option reduces guessing.
- **Simulation check:** a labelled simulation of the method compares the adaptive quiz with a fixed
  20-item quiz (`make quiz-sim`; results in the README). Guessing, which Rasch does not model,
  inflates the scores of weaker workers and weakens the stated uncertainty, which is one reason the
  quiz is never used for a badge.

**What the quiz never claims**
- certification;
- equivalence with the CSDCI theory exam or its 70 % pass mark;
- anything about practical skill or workmanship;
- calibration before real data exists;
- that its items are official CSDCI or NIMI questions.

## 7. Where quiz questions come from

- **CEA Safety Regulations 2023** (official text read in full; cited by regulation number, paraphrased):
  - reg. 17: no switch or fuse in the neutral except a linked switch;
  - reg. 21 and Schedule I Part II: discharge, isolate, earth, positively confirm dead, PPE;
  - reg. 31: who may do the work;
  - reg. 37(2): main switch;
  - reg. 42: insulation test after alterations;
  - reg. 43(viii): three-pin earthed sockets in new or renovated installations;
  - reg. 43(ix)(c): test earthing before energising;
  - reg. 44: RCD of at most 30 mA in domestic installations.
  - The 2023 text has **no** kilowatt threshold for RCDs. The often-quoted "5 kW" rule is from older
    regulations and is not used.
- **The qualification file's performance criteria** (one or more per question), and the **DGT
  Electrician CTS 3.0 curriculum** (Aug 2025) as the source of topics: Ohm's law, cable grading, load
  estimation, earthing, instruments, first aid and rescue.
- **IS 694:2010 cl. 12.1.1** (green-and-yellow protective conductor) and **IS 5216 (Part 1):1982**
  cl. 3 and 5.1 (permit to work; isolate, prove dead, earth).
- **Not copied:** NIMI books and the Bharat Skills question banks are "not to be republished", and
  BIS standards are copyrighted. Hunar cites clause numbers and paraphrases. It never reproduces
  their text or tables, and no item is taken from a published question bank.

All questions are **DRAFT** until a certified assessor or ITI instructor reviews them.

## 8. Open questions for the team

- Check the DPDP section wording against the official MeitY PDF.
- Register Hunar (as a college project) with Bhashini, then run `make translate` and get each
  language reviewed by a native speaker.
- Ask a State licensing board or electrical inspectorate how a platform can verify a permit (a
  register or QR code). Until then an admin checks the document by eye.
- Get the question banks reviewed by an ITI instructor and an RPL assessor, and collect about 100 real
  attempts per trade before calibrating.
