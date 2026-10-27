# Guidelines: writing and labelling worker declarations (M1)

The mapper is only as credible as its test set. These declarations are the ground truth for
top-1 / top-3 accuracy and MRR per language, so write them carefully and honestly.

## Target

About **150 declarations**: 30 for each of the 5 qualification packs, and for each pack 10 in
English, 10 in Hindi (Devanagari) and 10 in Hinglish (Hindi typed in Roman script). Several team
members should write, so that no single writing style dominates. The `author` column records who
wrote each row; the per-author breakdown goes into the report.

## How to write one

1. **Think of a real person.** Best: interview an electrician, wireman, solar installer or meter
   technician you know (with their permission, without recording their name) and write down what
   they say about their work. Otherwise imagine one concretely: age, where they learnt, where they
   work.
2. **First person, plain words.** "I have been doing house wiring for 8 years with my uncle", not
   "Performs LV electrical installation as per standards".
3. **Do not open the qualification PDFs or the JSON in `data/processed/` while writing.** Copying
   the official wording makes the task artificially easy for keyword baselines.
4. **Vary length:** some one-liners, some 3 to 6 sentences.
5. **Include natural noise:** years of experience, family, places, tools, the way people really mix
   English words into Hindi.
6. **About 15% hard cases:** the person mentions tasks from other trades too (a house electrician who
   once helped on a solar job). Mark them `hard`.
7. **No personal data.** No real names, phone numbers, Aadhaar numbers or addresses.

## How to label

Choose the **one** pack that best describes the person's main work. If two packs fit equally well,
do not include the declaration (we only evaluate unambiguous items for now; note such cases in
`docs/report/` as examples of genuine ambiguity).

| Pack (NQR id) | Main work |
|---|---|
| Assistant Electrician (13772) | Wiring in houses, shops, offices; conduits, switch boards, lights, MCB/DB; temporary supply at construction sites |
| Industrial Electrician (9530) | Three-phase industrial wiring, earthing pits, switchgear, motor starters, transformers, DG sets |
| Rooftop Solar PV (11371) | Rooftop solar panels, mounting structures, charge controllers, batteries, inverters |
| Wireman Control Panel Electronics (14896) | Wiring inside control panels in a factory from drawings: ferrules, lugs, DIN rails, relays, PLC panels |
| Jr. Technician (Smart Energy Meter) (9588) | Replacing and installing consumer energy meters and smart meters for the electricity board |

## Tool

```bash
uv run python scripts/label_declarations.py --author "Your Name"
uv run python scripts/label_declarations.py --check
make eval-m1
```

## Quality check

* A second team member re-labels a random 20% without seeing the first label; report the agreement
  (Cohen's kappa) in the report. Disagreements are discussed and either fixed or removed.
* Never edit a label after looking at the model's prediction for that row.
