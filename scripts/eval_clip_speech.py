"""Measure speech-to-text and the explanation check on recorded fan clips (`make eval-clip-speech`).

Reads data/labels/clip_speech.csv (rows from `make clip-audio`, filled in by a person who listened) and the
sound files in data/raw/clip_audio/. Every row with a written reference is transcribed by each speech
engine set up here, the way the app does it, and experiments/video_speech.json gets:

* word and character error rates for Hindi and English clips, overall and by setting (quiet or workshop).
  Not for Hinglish: its reference mixes scripts, so an error rate would mostly count script (as in the
  M1 voice check);
* the explanation check: for each aspect a prompt asks about (name, what it does, how it fails, how it
  is tested), whether the app found its words, against the person's 1/0 label. Measured twice: on the
  written reference (do the term lists match how people really speak?) and on each engine's transcript
  (the whole pipeline). The gap between the two is what speech errors cost.

Made-up recordings (synthetic = 1) are left out unless --include-synthetic is given; the file then says
data_kind "synthetic". With no filled-in rows or no engine, nothing is written and the README keeps
RESULT PENDING.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hunar.paths import DATA, EXPERIMENTS  # noqa: E402
from hunar.rubric.engine import ClipPrompt, tasks_for  # noqa: E402
from hunar.speech.evaluate import cer, corpus_cer, corpus_wer, wer  # noqa: E402
from hunar.video.clips import match_terms  # noqa: E402
from hunar.video.metrics import bootstrap, scores  # noqa: E402

CSV = DATA / "labels" / "clip_speech.csv"
AUDIO = DATA / "raw" / "clip_audio"
ASPECTS = ("name", "function", "failure", "test")
WER_LANGS = ("hi", "en")
Engine = Callable[[Path, str], dict]  # (wav, row language) -> {"text", "words": [{"word", "start"}]}


def prompts() -> dict[str, ClipPrompt]:
    return {c.id: c for t in tasks_for("appliance_technician") for c in t.clips}


def engines() -> dict[str, Engine]:
    """Speech engines usable here. Bhashini or IndicConformer join this list once they are set up."""
    from hunar.speech import transcribe as tr

    out: dict[str, Engine] = {}
    if tr.available():
        # The app sends "hi" for Hindi and Hinglish speakers and "en" for English ones.
        out[f"faster-whisper-{tr.MODEL}"] = lambda path, lang: tr.transcribe_words(
            path, tr.whisper_language("en" if lang == "en" else "hi"))
    return out


def usable(rows: list[dict], include_synthetic: bool) -> list[dict]:
    known = prompts()
    out = []
    for r in rows:
        if not r.get("reference", "").strip() or r.get("clip_id") not in known:
            continue
        if r.get("language") not in ("hi", "en", "hinglish"):
            continue
        if r.get("synthetic", "").strip() == "1" and not include_synthetic:
            continue
        out.append(r)
    return out


def labelled_aspects(row: dict, prompt: ClipPrompt) -> dict[str, bool]:
    """The aspects this prompt asks about that the person labelled 1 or 0."""
    return {a: row[a].strip() == "1" for a in ASPECTS if a in prompt.terms and row.get(a, "").strip() in ("0", "1")}


def as_words(text: str) -> list[dict]:
    return [{"word": w, "start": 0.0} for w in text.split()]


def explanation(pairs: list[tuple[str, bool, bool]]) -> dict:
    """pairs of (aspect, truth, found) -> overall and per-aspect scores."""
    flat = [(t, f) for _, t, f in pairs]
    return {**scores(flat), "precision_ci95": bootstrap(flat, "precision"), "recall_ci95": bootstrap(flat, "recall"),
            "by_aspect": {a: scores([(t, f) for x, t, f in pairs if x == a]) for a in ASPECTS
                          if any(x == a for x, _, _ in pairs)}}


def error_rates(items: list[tuple[str, str, str, str]]) -> dict:
    """items of (language, setting, reference, hypothesis) -> corpus WER/CER by language and by setting."""
    out: dict = {"by_language": {}, "by_setting": {}}
    for lang in WER_LANGS:
        pairs = [(r, h) for lg, _, r, h in items if lg == lang]
        if pairs:
            out["by_language"][lang] = {"n": len(pairs), "wer": round(corpus_wer(pairs), 4),
                                        "cer": round(corpus_cer(pairs), 4)}
    for setting in sorted({s for _, s, _, _ in items if s}):
        pairs = [(r, h) for lg, s, r, h in items if s == setting and lg in WER_LANGS]
        if pairs:
            out["by_setting"][setting] = {"n": len(pairs), "wer": round(corpus_wer(pairs), 4)}
    return out


def evaluate(rows: list[dict], engs: dict[str, Engine], audio_dir: Path) -> dict:
    known = prompts()
    ref_pairs: list[tuple[str, bool, bool]] = []
    for r in rows:
        p = known[r["clip_id"]]
        found = match_terms(as_words(r["reference"]), p.terms)
        ref_pairs += [(a, t, a in found) for a, t in labelled_aspects(r, p).items()]
    result: dict = {"on_reference": explanation(ref_pairs), "engines": {}}
    for name, run in engs.items():
        per_clip, items, pairs = [], [], []
        for r in rows:
            p = known[r["clip_id"]]
            tr = run(audio_dir / r["audio"], r["language"])
            found = match_terms(tr.get("words", []), p.terms)
            labels = labelled_aspects(r, p)
            pairs += [(a, t, a in found) for a, t in labels.items()]
            items.append((r["language"], r.get("setting", "").strip(), r["reference"], tr.get("text", "")))
            rated = r["language"] in WER_LANGS
            per_clip.append({"audio": r["audio"], "clip_id": r["clip_id"], "language": r["language"],
                             "setting": r.get("setting", ""),
                             "wer": round(wer(r["reference"], tr.get("text", "")), 4) if rated else None,
                             "cer": round(cer(r["reference"], tr.get("text", "")), 4) if rated else None,
                             "labelled": labels, "found": sorted(a for a in labels if a in found)})
        result["engines"][name] = {**error_rates(items), "on_transcript": explanation(pairs), "clips": per_clip}
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--include-synthetic", action="store_true", help="also use made-up recordings")
    a = ap.parse_args(argv)
    rows = usable(list(csv.DictReader(CSV.open())) if CSV.exists() else [], a.include_synthetic)
    if not rows:
        shown = CSV.relative_to(ROOT) if CSV.is_relative_to(ROOT) else CSV
        print(f"RESULT PENDING: no filled-in rows in {shown} (run `make clip-audio SRC=...`, then "
              "write the reference and the 1/0 labels).")
        return 0
    engs = engines()
    if not engs:
        print("RESULT PENDING: no speech engine is set up here (run `make voice`).")
        return 0
    res = evaluate(rows, engs, AUDIO)
    synthetic = any(r.get("synthetic", "").strip() == "1" for r in rows)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    out = {
        "experiment": "video_speech",
        "data_kind": "synthetic" if synthetic else "real",
        "n_clips": len(rows),
        "n_speakers": len({r.get("speaker", "") for r in rows if r.get("speaker", "").strip()}),
        "languages": {lg: sum(r["language"] == lg for r in rows) for lg in ("hi", "en", "hinglish")},
        **res,
        "note": ("Error rates only for Hindi and English (Hinglish references mix scripts). The explanation check "
                 "finds words, not understanding: the assessor watches the marked moments and decides."),
        "normalisation": "NFC, lower case, punctuation removed; digits are not spelled out",
        "command": "python scripts/eval_clip_speech.py" + (" --include-synthetic" if a.include_synthetic else ""),
        "git_commit": commit, "created": dt.datetime.now().isoformat(timespec="seconds"),
    }
    EXPERIMENTS.mkdir(exist_ok=True)
    (EXPERIMENTS / "video_speech.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    for name, e in out["engines"].items():
        print(name, json.dumps({k: e[k] for k in ("by_language", "by_setting")}),
              "explanation on transcript:", {k: e["on_transcript"][k] for k in ("precision", "recall")})
    print("explanation on reference:", {k: out["on_reference"][k] for k in ("precision", "recall")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
