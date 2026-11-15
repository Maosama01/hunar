"""Copy the sound out of the team's raw clip recordings for the speech test (`make clip-audio SRC=folder`).

For every video (or audio) file in SRC, recorded with consent for speech testing (docs/consent_form.md,
video-pilot part), this writes the sound only, as 16 kHz mono WAV, to data/raw/clip_audio/ (gitignored;
no picture, so no faces) and adds a row to data/labels/clip_speech.csv for a person to fill in:

  clip_id     the prompt the recording answers: isolation, capacitor, winding, bearings, regulator,
              fault or run_test
  language    hi, en or hinglish: what the speaker mostly spoke
  speaker     a code such as W07, never a name
  setting     quiet or workshop
  synthetic   1 if the recording is made up (for example text-to-speech), else leave blank
  reference   exactly what was said, written by someone who listened: Hindi words in Devanagari,
              English words in English
  name, function, failure, test
              1 if the speaker explained that aspect, 0 if not; leave blank when the prompt does not
              ask about it (see docs/video_pilot_guide.md)

Rows already in the CSV keep their labels. Nothing is deleted: once the WAV files are checked, delete the
original videos yourself (the consent form promises within 7 days). Then run `make eval-clip-speech`.
"""
from __future__ import annotations

import argparse
import csv
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from hunar.paths import DATA  # noqa: E402

OUT = DATA / "raw" / "clip_audio"
CSV = DATA / "labels" / "clip_speech.csv"
RATE = 16000
MEDIA = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".3gp", ".m4a", ".wav", ".aac", ".ogg", ".mp3"}
FIELDS = ["audio", "source", "seconds", "clip_id", "language", "speaker", "setting", "synthetic", "reference",
          "name", "function", "failure", "test"]


def extract(src: Path, dst: Path) -> float:
    """Write the first sound track of `src` to `dst` as 16 kHz mono 16-bit WAV; returns its length in seconds."""
    import av

    with av.open(str(src)) as c:
        if not c.streams.audio:
            raise ValueError(f"{src.name} has no sound track")
        rs = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        chunks = []
        for frame in c.decode(c.streams.audio[0]):
            chunks += [o.to_ndarray().tobytes() for o in rs.resample(frame)]
        chunks += [o.to_ndarray().tobytes() for o in rs.resample(None)]
    data = b"".join(chunks)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    return len(data) / 2 / RATE


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path, help="folder with the raw recordings")
    a = ap.parse_args(argv)
    if not a.src.is_dir():
        print(f"not a folder: {a.src}")
        return 2
    rows = {r["audio"]: r for r in csv.DictReader(CSV.open())} if CSV.exists() else {}
    added = 0
    for src in sorted(p for p in a.src.iterdir() if p.suffix.lower() in MEDIA):
        name = f"{src.stem}.wav"
        if name in rows:
            continue
        try:
            seconds = extract(src, OUT / name)
        except (ValueError, OSError) as e:
            print(f"skipped {src.name}: {e}")
            continue
        rows[name] = {**dict.fromkeys(FIELDS, ""), "audio": name, "source": src.name, "seconds": f"{seconds:.1f}"}
        added += 1
    CSV.parent.mkdir(parents=True, exist_ok=True)
    with CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows.values())
    shown = CSV.relative_to(DATA.parent) if CSV.is_relative_to(DATA.parent) else CSV
    print(f"{added} new recordings; {len(rows)} rows in {shown}. "
          f"Fill in the empty columns, delete the original videos, then run `make eval-clip-speech`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
