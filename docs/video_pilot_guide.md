# Video pilot: how to record, write down and label the fan clips

For the team members running the ceiling-fan pilot. Recording takes an afternoon. Writing down what was
said and labelling frames takes a few more hours. At the end, two commands turn your work into the
pilot's first real results.

What the pilot needs: **20 short part clips** and **2 full runs**, each with signed consent.

## 0. Before anything

1. Print [the consent form](consent_form.md) and fill in its video-pilot part. Everyone who appears or
   speaks signs it, ticking only the purposes they agree to. Keep the signed copies offline and never
   commit them.
2. Give each speaker a code (`W01`, `W02`, ...). **Nobody says a name in a clip**, theirs or anyone
   else's: the app keeps everything that is said.
3. If someone did not tick "keep the sound for testing", their clips can go into the app, but leave
   them out of step 5.

## 1. Kit

* A ceiling fan taken down and **not connected to the mains**, on a table.
* Its capacitor (with the value printed on it, e.g. 2.5 µF), winding, bearings and regulator.
* A multimeter with a capacitance range, and a voltage tester.
* For the "supply and tester" clip: an MCB and a switch on a training board, **switched off**.
* For the run test: only on a proper test board with an MCB and an RCD, with a qualified electrician
  present. If you cannot do that safely, skip the run-test clip; the pilot works without it.
* One planted fault for the fault clip (for example a weak capacitor or a loose regulator wire), set up
  by someone other than the speaker.
* A phone, good light, a quiet room, and a second place with normal workshop noise.

## 2. Phone settings

* Use the phone's own **camera app**, not the in-app recorder: the speech test needs the original
  sound, and the app removes it from its copy.
* Set video to **1080p at 30 fps**. A one-minute clip then stays under the app's 80 MB limit.
* Point the camera at your hands and the part. **Keep faces out of the picture.** The app blurs any face
  it finds, but out of the picture is safer.
* Upright or sideways both work: the app turns phone videos the right way up.
* Keep every clip **under one minute**. Speak clearly at your normal speed.

## 3. What to record

Each clip answers one prompt from the app. The four part prompts ask the same four things: **what it
is called, what it does, how it fails, and how you test it**.

### A. 20 short part clips

Five recordings for each of the four parts (capacitor, winding, bearings, regulator). Use at least two
different speakers across the 20.

| For each part | Language | Where | What to say |
|---|---|---|---|
| Clip 1 | Hindi | quiet room | all four things |
| Clip 2 | Hinglish | quiet room | all four things |
| Clip 3 | English | quiet room | all four things |
| Clip 4 | Hindi or Hinglish | workshop noise | all four things |
| Clip 5 | any | quiet room | **leave one thing out on purpose** (for example, do not say how it fails) and note which |

Clip 5 matters: the check must also be tried on clips where something is missing. Otherwise we cannot
tell whether it "finds" an explanation that was never given.

For the capacitor clips, also measure the capacitor and type the reading and the printed value when
you upload.

### B. 2 full runs

All seven clips in order: supply and tester, capacitor, winding, bearings, regulator, the faulty part,
run test. Each run is its own assessment in the app.

* **Run 1:** done properly, everything explained.
* **Run 2:** skip one part completely (no clip at all), and in one other clip show the part but **say
  nothing**.

## 4. Upload in the app

1. Sign in as an assessor and start a **New worker declaration**. Choose the trade **Appliance
   technician (fan pilot)** and write one line about the worker (no name).
2. Open **Tasks**. Each part has its own card with the prompt.
3. On the card, tap **Choose a video already recorded** and pick the clip. For the capacitor and the
   faulty part, type the meter reading and the printed value.
4. Tick **The worker has given written consent to be recorded**, then **Upload clip**. Processing can take
   a minute.
5. After the **first** clip, check it: the video shows the right way up, faces (if any) are blurred, and
   the transcript under "Transcript (draft)" looks roughly like what was said.

The app keeps only a blurred, silent copy, the transcript and the words it found.

## 5. The speech test: write down what was said

1. Copy the original videos from the phone to a folder on the laptop **outside the project**, for
   example `~/hunar_raw_clips`.
2. Copy the sound out:

   ```bash
   make clip-audio SRC=~/hunar_raw_clips
   ```

   This writes sound-only files to `data/raw/clip_audio/` and one row per recording to
   `data/labels/clip_speech.csv`. Both stay off GitHub.
3. **Delete the original videos** from the phone and the laptop. The consent form promises this within 7
   days.
4. Fill in the empty columns of `data/labels/clip_speech.csv` (a spreadsheet app is fine; save as CSV):

   | Column | What to write |
   |---|---|
   | `clip_id` | `capacitor`, `winding`, `bearings`, `regulator`, `isolation` (supply and tester), `fault` or `run_test` |
   | `language` | `hi`, `en` or `hinglish`: what the speaker mostly spoke |
   | `speaker` | the code, e.g. `W01` |
   | `setting` | `quiet` or `workshop` |
   | `synthetic` | leave blank (only for made-up test recordings) |
   | `reference` | exactly what was said (rules below) |
   | `name`, `function`, `failure`, `test` | `1` if the speaker really explained that thing, `0` if not; leave blank if the prompt does not ask about it |

   **Rules for `reference`:** someone other than the speaker writes it, listening at least twice. Write
   every word that was said, in the order said, including repeats. Hindi words in Devanagari, English
   words in English letters (for Hinglish too). Write numbers the way they were said ("do point paanch",
   or "2.5" if the speaker read out digits). Punctuation does not matter.

   **Rules for the 1/0 labels:** judge the meaning, not the words. "How it fails" is 1 if the speaker said
   a real way the part fails, in any words. Which aspects each prompt asks about: the four part clips ask
   all four; `fault` asks `failure` and `test`; `isolation` and `run_test` ask only `test`.
5. Run the test:

   ```bash
   make eval-clip-speech
   make results
   ```

   It reports how many words the speech-to-text got wrong (Hindi and English) and how often the
   explanation check agrees with your labels, both on your written text and on the app's transcript.

## 6. The picture check: label frames

1. Export about one frame a second from the stored (blurred, silent) clips:

   ```bash
   make clip-frames
   ```

2. Open `data/labels/clip_frames.csv` and look at each image in `data/labels/clip_frames/`. Fill in:
   * `part_present`: `1` if one of the parts listed in `labels` is clearly visible (at least half of
     it), else `0`;
   * `hand_on_part`: `1` if a hand is touching or holding that part, else `0`.
3. Label 100 to 200 frames. When unsure, ask a second person.
4. Run the test:

   ```bash
   make eval-clips
   make results
   ```

   It reports how often the picture check is right, at a range of cut-offs, and suggests a cut-off for
   the hand check. Put it in `.env` as `HUNAR_CLIP_HAND_CONF=...` to switch the hand check on. That
   cut-off was chosen on the same frames it was measured on, so confirm it on frames from new clips.

## 7. Deleting

* Original videos: within 7 days of copying the sound out (step 5).
* Everything else, by the date on the consent form, or within 7 days if someone asks:
  `data/raw/clip_audio/` (sound), `data/labels/clip_speech.csv` (what was said),
  `data/labels/clip_frames/` (frames) and the stored clips under `data/uploads/<assessment id>/`.

## What the results can and cannot show

Twenty clips from team members are a small, friendly sample: real workers in real workshops will be
harder. The results show whether the pipeline is worth trying with real workers, not how well it works
for them. The checks find words and objects; they never judge workmanship, and the assessor decides.
