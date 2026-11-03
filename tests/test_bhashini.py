"""Bhashini client and translation script, checked against the documented payloads with a fake
transport (no network, no credentials)."""
import base64
import importlib.util
import json
from pathlib import Path

from hunar.speech import bhashini

ROOT = Path(__file__).resolve().parents[1]


class FakeBhashini:
    def __init__(self, translate=lambda s, tgt: f"<{tgt}>{s}"):
        self.calls, self.fn = [], translate

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body))
        if url == bhashini.CONFIG_URL:
            task = body["pipelineTasks"][0]["taskType"]
            return {"pipelineResponseConfig": [{"taskType": task, "config": [{"serviceId": f"svc-{task}"}]}],
                    "pipelineInferenceAPIEndPoint": {"callbackUrl": "https://compute.example/pipeline",
                                                     "inferenceApiKey": {"name": "Authorization", "value": "k"}}}
        task = body["pipelineTasks"][0]
        if task["taskType"] == "tts":
            return {"pipelineResponse": [{"audio": [{"audioContent": base64.b64encode(b"RIFFwav").decode()}]}]}
        tgt = task["config"]["language"]["targetLanguage"]
        return {"pipelineResponse": [{"output": [{"source": x["source"], "target": self.fn(x["source"], tgt)}
                                                 for x in body["inputData"]["input"]]}]}


def client(fake):
    return bhashini.Bhashini("user", "ulca-key", "pipe-1", post=fake)


def test_config_then_compute_with_documented_fields():
    fake = FakeBhashini()
    c = client(fake)
    assert c.translate(["Switch off the supply"] * 20, "en", "sat")[0] == "<sat>Switch off the supply"
    url, headers, body = fake.calls[0]
    assert url == bhashini.CONFIG_URL and headers == {"userID": "user", "ulcaApiKey": "ulca-key"}
    assert body["pipelineRequestConfig"] == {"pipelineId": "pipe-1"}
    assert body["pipelineTasks"][0]["config"]["language"] == {"sourceLanguage": "en", "targetLanguage": "sat",
                                                               "targetScriptCode": "Olck"}
    url, headers, body = fake.calls[1]
    assert url == "https://compute.example/pipeline" and headers == {"Authorization": "k"}
    assert body["pipelineTasks"][0]["config"]["serviceId"] == "svc-translation"
    assert len(body["inputData"]["input"]) == bhashini.BATCH and len(fake.calls) == 3  # 20 texts -> 2 batches
    c.translate(["again"], "en", "sat")
    assert len(fake.calls) == 4  # config is cached per task and language pair


def test_tts_returns_wav_bytes():
    fake = FakeBhashini()
    assert client(fake).tts("नमस्ते", "hi") == b"RIFFwav"
    assert fake.calls[1][2]["pipelineTasks"][0]["config"]["gender"] == "female"


def test_from_env_needs_all_three(monkeypatch):
    for k in ("BHASHINI_USER_ID", "BHASHINI_API_KEY", "BHASHINI_PIPELINE_ID"):
        monkeypatch.delenv(k, raising=False)
    assert bhashini.Bhashini.from_env() is None
    monkeypatch.setenv("BHASHINI_USER_ID", "u")
    monkeypatch.setenv("BHASHINI_API_KEY", "k")
    assert bhashini.Bhashini.from_env() is None
    monkeypatch.setenv("BHASHINI_PIPELINE_ID", "p")
    assert bhashini.Bhashini.from_env().pipeline_id == "p"


def test_tts_endpoint_without_credentials(client, monkeypatch):
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    r = client.post("/api/tts", json={"text": "नमस्ते", "language": "hi"})
    assert r.status_code == 503 and "not set up" in r.json()["detail"]
    assert client.post("/api/tts", json={"text": "x", "language": "xx"}).status_code == 422


def _script():
    spec = importlib.util.spec_from_file_location("translate_script", ROOT / "scripts" / "translate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_placeholders_survive_or_string_is_dropped():
    t = _script()
    fake_ok = client(FakeBhashini())
    out, hashes, lost = t.translate_map(fake_ok, {"a": "{n} items", "b": "Hello"}, {}, {}, "ta", False)
    assert out == {"a": "<ta>{n} items", "b": "<ta>Hello"} and lost == 0
    eats = client(FakeBhashini(lambda s, tgt: s.replace("[[0]]", "")))
    out, _, lost = t.translate_map(eats, {"a": "{n} items", "b": "Hello"}, {}, {}, "ta", False)
    assert "a" not in out and lost == 1
    fake = FakeBhashini()
    out2, _, _ = t.translate_map(client(fake), {"a": "{n} items", "b": "Hello"}, out, hashes, "ta", False)
    assert out2["b"] == out["b"] and out2["a"] == "<ta>{n} items" and len(fake.calls) == 2  # only "a" re-sent


def test_quiz_translation_files_are_complete_items_only(tmp_path, monkeypatch):
    t = _script()
    monkeypatch.setattr(t, "BANK_DIR", tmp_path)
    (tmp_path / "x.yaml").write_text(json.dumps({"trade": "x", "items": [
        {"id": "x-1", "stem": {"en": "Q?"}, "explanation": {"en": "E"}, "options": [{"en": "A"}, {"en": "B"}]}]}))
    lines = t.do_quiz(client(FakeBhashini()), "bn", False)
    doc = json.loads((tmp_path / "i18n" / "x.bn.json").read_text())
    assert doc["meta"]["reviewed"] is False and doc["items"]["x-1"]["options"] == ["<bn>A", "<bn>B"]
    assert "1/1 items" in lines[0]
