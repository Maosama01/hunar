"""Voice pipeline check on SYNTHETIC speech: text-to-speech -> faster-whisper -> M1 mapper.

Usage:  python -m hunar.speech.evaluate [--limit N]     (macOS only: uses the built-in `say` voices)

Each SYNTHETIC declaration (AI-written text, data/synthetic/) is spoken by a macOS text-to-speech
voice (Hindi: Lekha, hi_IN; English and Roman-script Hinglish: Rishi, en_IN, which reads
Hinglish far more intelligibly than Lekha in a spot check), transcribed with the same settings
the app uses (language = the worker's preferred language: "hi" for Hindi and Hinglish, "en" for
English), and mapped with the primary M1 model. It reports:

* word and character error rates for English and Hindi. Not for Hinglish: its reference is in Roman
  script while Whisper writes Hindi speech in Devanagari, so an error rate would mostly count script.
* M1 top-1 / top-3 / MRR on the transcripts next to the same items typed, and how many top-1
  predictions the transcription changed.
* transcription speed on this laptop's CPU (real-time factor).

Transcripts are cached in data/raw/voice_tts/transcripts.json (gitignored), keyed by item, voice,
model, language and a hash of the text, so a re-run only redoes the mapping; delete the file to
transcribe again. Whisper falls back to sampling when a decode looks degenerate, so a fresh
transcription can differ slightly from a cached one.

LIMITS: clean text-to-speech audio is far easier than a worker speaking on a site with noise and an
accent. These numbers are an optimistic bound that checks the pipeline. They say nothing about how
well the tool understands real workers.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import unicodedata

import numpy as np

from hunar.mapper.evaluate import DATASETS, LANGS, git_commit, load_dataset, summarise, tie_aware
from hunar.mapper.mapper import QPMapper, load_packs
from hunar.mapper.text import split_sentences
from hunar.paths import DATA, EXPERIMENTS
from hunar.speech import transcribe as speech

VOICES = {"en": "Rishi", "hi": "Lekha", "hinglish": "Rishi"}
ASR_LANGUAGE = {"en": "en", "hi": "hi", "hinglish": "hi"}
AUDIO_DIR = DATA / "raw" / "voice_tts"
CACHE = AUDIO_DIR / "transcripts.json"
MAPPER = "minilm"


# ---- error rates --------------------------------------------------------------------------------


def normalise(text: str) -> str:
    """Lower case, punctuation (incl. the danda) to spaces; keeps letters, digits and Devanagari marks."""
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(ch if unicodedata.category(ch)[0] in "LMN" else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(ref: list, hyp: list) -> int:
    """Levenshtein distance (substitutions, insertions, deletions all cost 1)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def _rate(ref: list, hyp: list) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def wer(ref: str, hyp: str) -> float:
    return _rate(normalise(ref).split(), normalise(hyp).split())


def cer(ref: str, hyp: str) -> float:
    return _rate(list(normalise(ref).replace(" ", "")), list(normalise(hyp).replace(" ", "")))


def corpus_wer(pairs: list[tuple[str, str]]) -> float:
    """Total word errors over total reference words (longer items weigh more)."""
    errs = sum(edit_distance(normalise(r).split(), normalise(h).split()) for r, h in pairs)
    return errs / max(1, sum(len(normalise(r).split()) for r, _ in pairs))


def corpus_cer(pairs: list[tuple[str, str]]) -> float:
    def chars(t: str) -> list[str]:
        return list(normalise(t).replace(" ", ""))

    errs = sum(edit_distance(chars(r), chars(h)) for r, h in pairs)
    return errs / max(1, sum(len(chars(r)) for r, _ in pairs))


# ---- pipeline -----------------------------------------------------------------------------------


def synthesise(item: dict) -> str:
    out = AUDIO_DIR / f"{item['id']}_{VOICES[item['language']]}.aiff"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["say", "-v", VOICES[item["language"]], "-o", str(out), item["text"]], check=True)
    return str(out)


def cache_key(item: dict) -> str:
    lang = item["language"]
    digest = hashlib.sha256(item["text"].encode()).hexdigest()[:12]
    return f"{item['id']}|{VOICES[lang]}|{speech.MODEL}|{ASR_LANGUAGE[lang]}|{digest}"


def run(items: list[dict]) -> dict:
    packs = load_packs()
    ids = [p.nqr_id for p in packs]
    mapper = QPMapper(MAPPER, packs=packs)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    rows = []
    for k, item in enumerate(items, 1):
        key = cache_key(item)
        if key not in cache:
            audio = synthesise(item)
            t0 = time.perf_counter()
            out = speech.transcribe_file(audio, ASR_LANGUAGE[item["language"]])
            cache[key] = {"text": out["text"], "duration_s": out["duration_s"],
                          "asr_s": round(time.perf_counter() - t0, 2)}
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        tr, secs = cache[key], cache[key]["asr_s"]
        gold = ids.index(int(item["label_nqr_id"]))
        typed, _ = mapper.pack_scores(split_sentences(item["text"]))
        spoken, _ = mapper.pack_scores(split_sentences(tr["text"])) if tr["text"] else (np.zeros(len(ids)), None)
        rows.append({"id": item["id"], "language": item["language"], "gold": ids[gold], "voice": VOICES[item["language"]],
                     "audio_s": tr["duration_s"], "asr_s": round(secs, 2),
                     "wer": round(wer(item["text"], tr["text"]), 4), "cer": round(cer(item["text"], tr["text"]), 4),
                     "typed": tie_aware(typed, gold), "spoken": tie_aware(spoken, gold),
                     "top1_typed": ids[int(np.argmax(typed))], "top1_spoken": ids[int(np.argmax(spoken))],
                     "text": item["text"], "transcript": tr["text"]})
        print(f"{k:3d}/{len(items)} {item['id']} {item['language']:8s} wer={rows[-1]['wer']:.2f} "
              f"{secs:.1f}s for {tr['duration_s']:.1f}s audio", flush=True)
    return {"rows": rows, "ids": ids}


def report(rows: list[dict], items_path: str) -> dict:
    by_lang = {}
    for lang in LANGS:
        sub = [r for r in rows if r["language"] == lang]
        if not sub:
            continue
        pairs = [(r["text"], r["transcript"]) for r in sub]
        entry = {"n": len(sub), "voice": VOICES[lang], "asr_language": ASR_LANGUAGE[lang],
                 "mapping_typed": summarise([r["typed"] for r in sub]),
                 "mapping_spoken": summarise([r["spoken"] for r in sub]),
                 "top1_changed_by_transcription": sum(r["top1_typed"] != r["top1_spoken"] for r in sub),
                 "top1_right_to_wrong": sum(r["top1_typed"] == r["gold"] != r["top1_spoken"] for r in sub),
                 "top1_wrong_to_right": sum(r["top1_typed"] != r["gold"] == r["top1_spoken"] for r in sub)}
        if lang != "hinglish":
            entry["corpus_wer"] = round(corpus_wer(pairs), 4)
            entry["corpus_cer"] = round(corpus_cer(pairs), 4)
        else:
            entry["error_rate_note"] = "not computed: Roman-script reference vs Devanagari transcript"
        by_lang[lang] = entry
    audio = sum(r["audio_s"] for r in rows)
    asr = sum(r["asr_s"] for r in rows)
    return {
        "experiment": "m1_voice",
        "data_kind": "synthetic",
        "warning": ("SYNTHETIC SPEECH: AI-written declarations read aloud by macOS text-to-speech voices, not "
                    "recordings of workers. Clean synthetic audio is an optimistic bound; this checks the pipeline."),
        "dataset": items_path,
        "n_items": len(rows),
        "asr": {"engine": "faster-whisper", "version": importlib.metadata.version("faster-whisper"),
                "model": speech.MODEL, "device": "cpu", "compute_type": "int8", "beam_size": 5, "vad_filter": True},
        "tts": {"engine": "macOS say", "voices": VOICES, "macos": platform.mac_ver()[0]},
        "mapper": MAPPER,
        "machine": platform.machine(),
        "speed": {"audio_seconds": round(audio, 1), "transcription_seconds": round(asr, 1),
                  "real_time_factor": round(asr / audio, 3) if audio else None,
                  "note": "includes the one-off model load; not a controlled benchmark (other programs may share the CPU)"},
        "by_language": by_lang,
        "transcripts": "cached in data/raw/voice_tts/transcripts.json; speed figures are from the run that made them",
        "normalisation": "NFC, lower case, punctuation removed; digits are not spelled out (\"8\" vs \"eight\" counts as an error)",
        "command": "python -m hunar.speech.evaluate",
        "git_commit": git_commit(),
        "created": dt.datetime.now().isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="first N items only (smoke run, not saved)")
    args = ap.parse_args(argv)
    if shutil.which("say") is None or not speech.available():
        print("needs macOS `say` and faster-whisper (make voice)")
        return 1
    items = load_dataset(DATASETS["synthetic"])
    if args.limit:
        items = items[: args.limit]
    out = run(items)
    res = report(out["rows"], str(DATASETS["synthetic"].relative_to(DATA.parent)))
    for lang, e in res["by_language"].items():
        print(f"{lang:8s} n={e['n']} wer={e.get('corpus_wer', '-')} top1 typed={e['mapping_typed']['top1_acc']:.3f} "
              f"spoken={e['mapping_spoken']['top1_acc']:.3f} changed={e['top1_changed_by_transcription']}")
    if args.limit:
        print("smoke run: not saved")
        return 0
    (EXPERIMENTS / "m1_voice_synthetic.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    with (EXPERIMENTS / "m1_voice_predictions_synthetic.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["id", "language", "gold", "top1_typed", "top1_spoken", "wer", "cer", "audio_s", "asr_s", "text",
                "transcript"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_for_csv(out["rows"]))
    print("wrote experiments/m1_voice_synthetic.json")
    return 0


def rows_for_csv(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k not in ("typed", "spoken")} for r in rows]


if __name__ == "__main__":
    sys.exit(main())
