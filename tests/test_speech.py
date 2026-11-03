import shutil
import subprocess
from pathlib import Path

import pytest

from hunar.speech import evaluate as ev
from hunar.speech import transcribe as speech


def test_health_reports_speech(client):
    s = client.get("/api/health").json()["speech"]
    assert set(s) >= {"available", "note"} and "not stored" in s["note"]


def test_transcribe_unavailable_is_503(client, monkeypatch):
    monkeypatch.setattr(speech, "available", lambda: False)
    r = client.post("/api/transcribe", files={"file": ("a.webm", b"xx", "audio/webm")})
    assert r.status_code == 503 and "type instead" in r.json()["detail"]


def test_transcribe_passes_language_and_rejects_bad_input(client, monkeypatch):
    seen = {}

    def fake(data, language, filename):
        seen.update(data=data, language=language, filename=filename)
        return {"text": "मैं वायरिंग करता हूँ", "language": language, "note": speech.NOTE}

    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe_bytes", fake)
    r = client.post("/api/transcribe", data={"language": "hi"}, files={"file": ("rec.webm", b"abc", "audio/webm")})
    assert r.status_code == 200 and r.json()["text"] == "मैं वायरिंग करता हूँ"
    assert seen == {"data": b"abc", "language": "hi", "filename": "rec.webm"}

    assert client.post("/api/transcribe", files={"file": ("rec.webm", b"", "audio/webm")}).status_code == 422
    client.post("/api/transcribe", data={"language": "sat"}, files={"file": ("rec.webm", b"abc", "audio/webm")})
    assert seen["language"] is None  # no Whisper token for Santali: auto-detect
    client.post("/api/transcribe", data={"language": "ta"}, files={"file": ("rec.webm", b"abc", "audio/webm")})
    assert seen["language"] == "ta"
    monkeypatch.setattr(speech, "MAX_BYTES", 2)
    assert client.post("/api/transcribe", files={"file": ("rec.webm", b"abc", "audio/webm")}).status_code == 413


def test_transcribe_decoder_failure_is_422(client, monkeypatch):
    def boom(*_a):
        raise ValueError("bad audio")

    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe_bytes", boom)
    r = client.post("/api/transcribe", files={"file": ("rec.webm", b"abc", "audio/webm")})
    assert r.status_code == 422 and "ValueError" in r.json()["detail"]


def test_audio_temp_file_is_deleted(monkeypatch):
    seen = {}

    def fake(path, language=None):
        seen["path"], seen["suffix"] = Path(path), Path(path).suffix
        assert Path(path).read_bytes() == b"abc"
        return {"text": "ok"}

    monkeypatch.setattr(speech, "transcribe_file", fake)
    assert speech.transcribe_bytes(b"abc", "en", "../../etc/x.exe") == {"text": "ok"}
    assert seen["suffix"] == ".webm" and not seen["path"].exists()
    speech.transcribe_bytes(b"abc", "en", "clip.WAV")
    assert seen["suffix"] == ".wav" and not seen["path"].exists()


# ---- error-rate maths ---------------------------------------------------------------------------


def test_edit_distance_and_error_rates():
    assert ev.edit_distance([], []) == 0
    assert ev.edit_distance(list("abc"), []) == 3
    assert ev.edit_distance([], list("ab")) == 2
    assert ev.edit_distance(list("kitten"), list("sitting")) == 3
    assert ev.wer("I fix the MCB.", "i fix the mcb") == 0.0
    assert ev.wer("a b c d", "a x c") == 0.5  # one substitution + one deletion over 4 reference words
    assert ev.cer("abcd", "abcd") == 0.0
    assert ev.wer("", "") == 0.0 and ev.wer("", "extra words") == 1.0


def test_normalise_keeps_devanagari_marks():
    assert ev.normalise("मैं  वायरिंग, करता हूँ।") == "मैं वायरिंग करता हूँ"
    assert ev.normalise("Switch-board's OK!") == "switch board s ok"


def test_corpus_rates_weight_by_length():
    pairs = [("a b c d", "a b c d"), ("x y", "p q")]
    assert ev.corpus_wer(pairs) == pytest.approx(2 / 6)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("say") is None or not speech.available(), reason="needs macOS say + make voice")
def test_real_transcription_of_tts_clip(tmp_path):
    wav = tmp_path / "en.aiff"
    subprocess.run(["say", "-v", "Rishi", "-o", str(wav), "I fix switch boards."], check=True)
    out = speech.transcribe_file(wav, "en")
    assert out["language"] == "en" and "switch" in out["text"].lower()
