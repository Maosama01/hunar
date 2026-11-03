"""Bhashini (Government of India language platform) client: machine translation and text to speech.

Configure with the organisation's Bhashini account ("My Profile" on bhashini.gov.in) in the server's
environment, never in the browser or in git:
  BHASHINI_USER_ID, BHASHINI_API_KEY (the ULCA API key), BHASHINI_PIPELINE_ID

Protocol, from the public API documentation (bhashini.gitbook.io/bhashini-apis, read 4 Nov 2026):
1. "pipeline config" call: POST getModelsPipeline with headers userID + ulcaApiKey and the task with
   its languages; the response gives a serviceId per task and pipelineInferenceAPIEndPoint
   {callbackUrl, inferenceApiKey {name, value}}.
2. "pipeline compute" call: POST callbackUrl with header <name>: <value> and pipelineTasks
   [{taskType, config {language, serviceId[, gender]}}] plus inputData.input [{source}]. Translation
   returns pipelineResponse[0].output[i].target; TTS returns pipelineResponse[0].audio[0].audioContent
   (base64 WAV).

NOT YET TESTED against the live service: this project has no credentials. The unit tests check the
payloads against the documented format with a fake transport. Bhashini's terms require an access
agreement and give no warranty that outputs are correct, so every translation is stored as
"machine-translated, not reviewed" until a native speaker checks it.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass, field

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
# App language code -> (Bhashini language code, script code or None). Script codes matter for languages
# written in more than one script; check them against the languages the config call reports.
LANGS: dict[str, tuple[str, str | None]] = {
    "en": ("en", None), "as": ("as", None), "bn": ("bn", None), "brx": ("brx", None), "doi": ("doi", None),
    "gu": ("gu", None), "hi": ("hi", None), "kn": ("kn", None), "ks": ("ks", "Aran"), "gom": ("gom", None),
    "mai": ("mai", None), "ml": ("ml", None), "mni": ("mni", "Mtei"), "mr": ("mr", None), "ne": ("ne", None),
    "or": ("or", None), "pa": ("pa", None), "sa": ("sa", None), "sat": ("sat", "Olck"), "sd": ("sd", "Arab"),
    "ta": ("ta", None), "te": ("te", None), "ur": ("ur", None),
}
BATCH = 16


def _language(src: str, tgt: str | None = None) -> dict:
    s_code, s_script = LANGS[src]
    out = {"sourceLanguage": s_code}
    if s_script:
        out["sourceScriptCode"] = s_script
    if tgt is not None:
        t_code, t_script = LANGS[tgt]
        out["targetLanguage"] = t_code
        if t_script:
            out["targetScriptCode"] = t_script
    return out


def _http_post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


@dataclass
class Bhashini:
    user_id: str
    api_key: str
    pipeline_id: str
    timeout: float = 60.0
    post: object = _http_post  # replaced by a fake in tests
    _configs: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Bhashini | None:
        vals = [os.environ.get(k, "").strip() for k in ("BHASHINI_USER_ID", "BHASHINI_API_KEY", "BHASHINI_PIPELINE_ID")]
        return cls(*vals) if all(vals) else None

    def _config(self, task: str, src: str, tgt: str | None = None) -> tuple[str, str, str, str]:
        key = (task, src, tgt)
        if key not in self._configs:
            body = {"pipelineTasks": [{"taskType": task, "config": {"language": _language(src, tgt)}}],
                    "pipelineRequestConfig": {"pipelineId": self.pipeline_id}}
            r = self.post(CONFIG_URL, {"userID": self.user_id, "ulcaApiKey": self.api_key}, body, self.timeout)
            service = r["pipelineResponseConfig"][0]["config"][0]["serviceId"]
            ep = r["pipelineInferenceAPIEndPoint"]
            self._configs[key] = (service, ep["callbackUrl"], ep["inferenceApiKey"]["name"],
                                  ep["inferenceApiKey"]["value"])
        return self._configs[key]

    def translate(self, texts: list[str], src: str, tgt: str) -> list[str]:
        service, url, key_name, key_value = self._config("translation", src, tgt)
        out: list[str] = []
        for i in range(0, len(texts), BATCH):
            chunk = texts[i:i + BATCH]
            body = {"pipelineTasks": [{"taskType": "translation",
                                       "config": {"language": _language(src, tgt), "serviceId": service}}],
                    "inputData": {"input": [{"source": t} for t in chunk]}}
            r = self.post(url, {key_name: key_value}, body, self.timeout)
            got = [o["target"] for o in r["pipelineResponse"][0]["output"]]
            if len(got) != len(chunk):
                raise ValueError(f"Bhashini returned {len(got)} translations for {len(chunk)} inputs")
            out += got
        return out

    def tts(self, text: str, lang: str, gender: str = "female") -> bytes:
        service, url, key_name, key_value = self._config("tts", lang)
        body = {"pipelineTasks": [{"taskType": "tts", "config": {"language": _language(lang), "serviceId": service,
                                                                 "gender": gender}}],
                "inputData": {"input": [{"source": text}]}}
        r = self.post(url, {key_name: key_value}, body, self.timeout)
        return base64.b64decode(r["pipelineResponse"][0]["audio"][0]["audioContent"])
