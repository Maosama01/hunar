"""Guided clips for the video-assessment pilot: one short clip per part, asked for by the app.

For each upload:
1. the upload goes to a private temporary folder: it holds the worker's voice and unblurred faces;
2. speech is transcribed with word timings (hunar.speech.transcribe; an Indian-language engine such
   as Bhashini ASR or IndicConformer can replace it once measured on real clips);
3. every frame is decoded, faces are blurred, and the clip is re-encoded as H.264 WITHOUT audio, at
   most MAX_WIDTH wide and MAX_FPS frames a second: only this blurred, silent copy is stored;
4. about one frame a second is kept for the frame check (part and hand present), which runs only
   when a detector is configured; without one the result says "not checked";
5. each aspect's terms are searched in the transcript, and a meter reading typed by the worker is
   compared with the value printed on the part (the tolerance printed on it, or 10 % when none).
The temporary folder is deleted before returning. Nothing here judges workmanship: the results are
reasons for a suggested level that the assessor accepts or overrides.
"""
from __future__ import annotations

import re
import tempfile
import unicodedata
from fractions import Fraction
from pathlib import Path

import numpy as np

from hunar.evidence import privacy
from hunar.rubric.engine import ClipPrompt

MAX_BYTES = 80 * 1024 * 1024
MAX_SECONDS = 180
MAX_WIDTH = 640
MAX_FPS = 15
DEFAULT_TOLERANCE_PCT = 10.0
NOTE = ("Faces blurred in every frame and the sound removed before storage. The transcript is a draft; "
        "the words found are reasons for a suggestion, not a score.")
_SPLIT = re.compile(r"[\s,.!?;:\"'()\[\]{}।॥-]+")


def normalise(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _tokens(words: list[dict]) -> list[tuple[str, float]]:
    out = []
    for w in words:
        for tok in _SPLIT.split(normalise(w.get("word", ""))):
            if tok:
                out.append((tok, float(w.get("start", 0.0))))
    return out


def match_terms(words: list[dict], terms: dict[str, list[str]], per_aspect: int = 3) -> dict[str, list[tuple[str, float]]]:
    """aspect -> [(term, seconds)] for terms said in the clip. A single word matches a whole token, or the
    start of a token when the term has 4 or more letters (capacitors, bearings); a phrase matches
    consecutive tokens."""
    toks = _tokens(words)
    found: dict[str, list[tuple[str, float]]] = {}
    for aspect, items in terms.items():
        hits: list[tuple[str, float]] = []
        for term in items:
            parts = [p for p in _SPLIT.split(normalise(term)) if p]
            if not parts:
                continue
            for i in range(len(toks) - len(parts) + 1):
                window = toks[i:i + len(parts)]
                if len(parts) == 1:
                    tok = window[0][0]
                    ok = tok == parts[0] or (len(parts[0]) >= 4 and tok.startswith(parts[0]))
                else:
                    ok = [w for w, _ in window] == parts
                if ok:
                    hits.append((term, window[0][1]))
                    break
        if hits:
            found[aspect] = sorted(hits, key=lambda h: h[1])[:per_aspect]
    return found


def meter_in_range(reading: float | None, printed: float | None, tolerance_pct: float | None) -> bool | None:
    """Whether a reading is within the value printed on the part; None when either is missing."""
    if reading is None or printed is None or printed <= 0:
        return None
    tol = DEFAULT_TOLERANCE_PCT if tolerance_pct is None else tolerance_pct
    return abs(reading - printed) / printed * 100 <= tol + 1e-9


def blur_and_encode(src: Path, dst: Path) -> dict:
    """Decode `src`, blur faces in every kept frame and write a silent H.264 mp4 to `dst`. Returns frame
    counts and about one frame a second (already blurred) for the frame check."""
    import av

    with av.open(str(src)) as inp:
        if not inp.streams.video:
            raise ValueError("the clip has no video")
        vin = inp.streams.video[0]
        rate = float(vin.average_rate or vin.base_rate or 25)
        keep_every = max(1, round(rate / MAX_FPS))
        out_rate = max(1, round(rate / keep_every))
        out = av.open(str(dst), mode="w")
        vout = None
        kept = with_faces = 0
        samples: list[np.ndarray] = []
        next_sample = 0.0
        last_t = 0.0
        try:
            for i, frame in enumerate(inp.decode(vin)):
                if i % keep_every:
                    continue
                img = frame.to_ndarray(format="bgr24")
                h, w = img.shape[:2]
                if w > MAX_WIDTH:
                    import cv2

                    img = cv2.resize(img, (MAX_WIDTH, round(h * MAX_WIDTH / w / 2) * 2))
                h, w = img.shape[:2]
                img = img[: h - h % 2, : w - w % 2]
                blurred, n = privacy.blur_faces(img)  # blur BEFORE anything is written to disk
                with_faces += n > 0
                if vout is None:
                    vout = out.add_stream("libx264", rate=out_rate)
                    vout.width, vout.height = blurred.shape[1], blurred.shape[0]
                    vout.pix_fmt = "yuv420p"
                    vout.time_base = Fraction(1, out_rate)
                vf = av.VideoFrame.from_ndarray(blurred, format="bgr24")
                vf.pts = kept
                vf.time_base = Fraction(1, out_rate)
                for pkt in vout.encode(vf):
                    out.mux(pkt)
                kept += 1
                t = float(frame.time) if frame.time is not None else kept / out_rate
                last_t = t
                if t >= next_sample:
                    samples.append(blurred)
                    next_sample = t + 1.0
                if t > MAX_SECONDS:
                    raise ValueError(f"the clip is longer than {MAX_SECONDS} seconds")
            if vout is None:
                raise ValueError("the clip has no frames")
            for pkt in vout.encode():
                out.mux(pkt)
        finally:
            out.close()
    return {"frames": kept, "frames_with_faces": with_faces, "duration_s": round(last_t, 2), "samples": samples}


class NoDetector:
    """Default frame check: none configured, so presence is reported as not checked."""

    name = "none"

    def check(self, frames: list[np.ndarray], labels: list[str]) -> tuple[bool | None, bool | None]:
        return None, None


DETECTOR = NoDetector()


def process_clip(data: bytes, prompt: ClipPrompt, out_path: Path, language: str | None = None,
                 reading: float | None = None, printed: float | None = None,
                 tolerance_pct: float | None = None) -> dict:
    """Run the whole pipeline on one upload; only the blurred, silent copy at `out_path` remains."""
    from hunar.speech import transcribe as tr

    if len(data) > MAX_BYTES:
        raise ValueError(f"the clip is larger than {MAX_BYTES // (1024 * 1024)} MB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hunar-clip-") as d:
        src = Path(d) / "upload.bin"
        src.write_bytes(data)
        if tr.available():
            transcript = tr.transcribe_words(src, tr.whisper_language(language))
        else:
            transcript = {"text": "", "words": [], "unavailable": "speech to text is not installed (make voice)"}
        video = blur_and_encode(src, out_path)
    part_seen, hand_on_part = DETECTOR.check(video.pop("samples"), prompt.detect)
    return {
        **video,
        "transcript": transcript,
        "found": match_terms(transcript.get("words", []), prompt.terms),
        "part_seen": part_seen,
        "hand_on_part": hand_on_part,
        "detector": DETECTOR.name,
        "meter_in_range": meter_in_range(reading, printed, tolerance_pct) if prompt.meter else None,
        "note": NOTE,
    }
