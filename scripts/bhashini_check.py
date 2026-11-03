"""Check the Bhashini credentials in .env before running `make translate` (`make bhashini-check`).

  python scripts/bhashini_check.py [--all]

Translates one short sentence (English to Hindi) and speaks one Hindi sentence. With --all it tries the
sentence in every target language and lists which ones the configured pipeline supports. Keys are
never printed.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from hunar.speech.bhashini import LANGS, Bhashini  # noqa: E402

SENTENCE = "Switch off the supply before you touch the wire."
VARS = ("BHASHINI_USER_ID", "BHASHINI_API_KEY", "BHASHINI_PIPELINE_ID")


def _why(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        body = e.read().decode(errors="replace")[:200].replace("\n", " ")
        return f"HTTP {e.code}: {body}"
    return f"{type(e).__name__}: {e}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="try every target language")
    a = ap.parse_args(argv)
    missing = [v for v in VARS if not os.environ.get(v, "").strip()]
    if missing:
        print(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill them in.")
        return 1
    client = Bhashini.from_env()
    ok = True
    try:
        print("translation en -> hi:", client.translate([SENTENCE], "en", "hi")[0])
    except Exception as e:  # report and continue so the TTS check still runs
        ok = False
        print("translation FAILED:", _why(e))
    try:
        wav = client.tts("काम शुरू करने से पहले सप्लाई बंद करें।", "hi")
        print(f"text to speech hi: {len(wav)} bytes, {'WAV' if wav[:4] == b'RIFF' else 'not WAV?'}")
    except Exception as e:
        ok = False
        print("text to speech FAILED:", _why(e))
    if a.all:
        supported = []
        for lang in [c for c in LANGS if c not in ("en", "hi")]:
            try:
                out = client.translate([SENTENCE], "en", lang)[0]
                supported.append(lang)
                print(f"  {lang:4s} ok   {out}")
            except Exception as e:
                print(f"  {lang:4s} FAIL {_why(e)}")
        print(f"{len(supported)} of {len(LANGS) - 2} target languages work: {' '.join(supported)}")
        print("Run `make translate` for all, or `python scripts/translate.py --langs <codes>` for the ones that work.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
