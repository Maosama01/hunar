# 5-minute demo script (seeded SAMPLE data)

Generated from `demo_script.src.md` by `make report`.

**Before the demo (once):** `make setup && make data`, then `make demo`. This seeds the clearly
labelled sample worker `SAMPLE-W001` and starts the API on :8000 and the web app on :5173. Open
http://localhost:5173 in Chrome and keep http://localhost:8000/docs in a second tab. Practise once with
the network switched off (step 6).

| Time | Screen | What to do | What to say |
|---|---|---|---|
| 0:00 | Home | Point at the banner and the SAMPLE DATA badge | "Hunar supports an RPL assessor. AI suggests, the assessor decides. Everything you see is sample data." |
| 0:20 | Declaration (SAMPLE-W001) | Open the sample assessment's mapping | "The worker described their work in Hinglish. The mapper compares each sentence with the {{fact:n_pcs}} official performance criteria parsed from nqr.gov.in." |
| 0:50 | Mapping detail | Show the matched sentence → criterion pairs and the skill gaps | "Here it ranked *Industrial Electrician* first. That is a known weakness we measured: Hinglish is the weakest language for this model, and big qualifications attract matches. The assessor sees why and corrects it." |
| 1:20 | Assessor: confirm pack | Choose Assistant Electrician; show that a reason is required when it differs from the top suggestion | "The human choice and the reason go into the audit log." |
| 1:40 | Practical tasks | Task 1 (safe isolation): show the checklist with safety shoes and lock/tag not ticked; Task 2: show the sample photo with the faces-blurred count and detector status | "Photos need written consent and faces are blurred before storage. The detector is not trained yet, so the app honestly says photo check unavailable." |
| 2:30 | Scoring | Open Task 1 criteria: suggested level 1 for PPE with the reason "not ticked: Safety shoes worn"; accept one, override another with a reason | "The engine never suggests 'proficient'; the worker's own words are context only. An override without a reason is refused." |
| 3:20 | Profile | Show NOS bars and the critical failure blocking a positive recommendation | "Safety comes first: a failed safety criterion blocks the recommendation whatever the total. The official pass mark from the qualification file is 70 %." |
| 3:50 | Admin | Open the audit log, click Verify chain | "Every action is hash-chained. Editing any past entry breaks the chain; our tests prove it." |
| 4:10 | Offline | Switch Wi-Fi off, add a checklist tick, show the queued-ops counter, switch on, Sync now | "Field sites have poor connectivity. Actions queue on the device and replay in order exactly once." |
| 4:40 | Results slide / README | Show the per-language chart and the RESULT PENDING rows | "Our numbers so far are on synthetic declarations and public photos. The assessor-agreement study needs real assessors, and that is our next phase." |

**If something fails:** the API docs page (http://localhost:8000/docs) can demonstrate
`/api/map`, `/api/assessments/sample-assessment-1/prescores`, `/profile` and `/api/audit/verify`
directly.
