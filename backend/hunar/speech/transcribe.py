"""Speech to text for spoken declarations (faster-whisper, CPU, int8).

Optional: install with `make voice` (uv extra "voice"). Without it, status() reports "unavailable"
and the app asks the facilitator to type the declaration instead.

The transcript is a draft. The facilitator reads it back to the worker and corrects it before
saving; the mapper only ever sees the text that was saved.

PRIVACY: audio is a recording of a real person. It is written to a temporary file for decoding,
transcribed and deleted at once; only the checked text is stored.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from hunar.mapper.matchers import _usable_hf_home

MODEL = os.environ.get("HUNAR_WHISPER_MODEL", "small")
MAX_BYTES = 20 * 1024 * 1024
AUDIO_SUFFIXES = {".webm", ".ogg", ".oga", ".wav", ".mp3", ".m4a", ".mp4", ".aac", ".aiff", ".flac"}
NOTE = "Draft transcript: read it back to the worker and correct it before saving. Audio is not stored."


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    _usable_hf_home()
    return WhisperModel(MODEL, device="cpu", compute_type="int8")


def status() -> dict:
    """Cheap check for /api/health: never loads or downloads the model."""
    if not available():
        return {"available": False, "reason": "faster-whisper not installed (make voice)", "model": MODEL,
                "note": NOTE}
    return {"available": True, "model": f"faster-whisper-{MODEL}", "note": NOTE}


def transcribe_file(path: str | Path, language: str | None = None) -> dict:
    """Transcript of an audio file. `language` is "hi", "en" or None (auto-detect)."""
    segments, info = _model().transcribe(str(path), language=language, beam_size=5, vad_filter=True,
                                         condition_on_previous_text=False)
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
             "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3)}
            for s in segments]
    return {"text": " ".join(s["text"] for s in segs if s["text"]).strip(), "language": info.language,
            "language_probability": round(float(info.language_probability), 3),
            "duration_s": round(float(info.duration), 2), "segments": segs, "model": f"faster-whisper-{MODEL}",
            "note": NOTE}


def transcribe_bytes(data: bytes, language: str | None = None, filename: str = "") -> dict:
    """Transcribe uploaded audio via a temporary file that is deleted before returning."""
    suffix = Path(filename).suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        suffix = ".webm"  # the decoder probes the content; the suffix is only a hint
    with tempfile.TemporaryDirectory(prefix="hunar-voice-") as d:
        p = Path(d) / f"audio{suffix}"
        p.write_bytes(data)
        return transcribe_file(p, language)
