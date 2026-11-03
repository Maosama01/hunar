"""Question banks: one YAML file per trade in hunar/quiz/banks/, with English and Hindi text.

Every item names the NOS it tests, the sources that support its answer (keys into the bank's
`sources`), and an AI-drafted difficulty estimate in logits. Banks carry status DRAFT until a certified
assessor or ITI instructor has reviewed them; the app shows that status.

Other languages come from banks/i18n/<trade>.<lang>.json, written by scripts/translate.py (Bhashini
or another machine-translation provider) and marked unreviewed until a native speaker checks them.
Calibrated difficulties, once enough real answers exist, come from banks/params/<trade>.json
(hunar.quiz.calibrate); otherwise the AI-drafted estimates are used and labelled "uncalibrated".
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

BANKS = Path(__file__).parent / "banks"


class Text(BaseModel):
    en: str
    hi: str


class Item(BaseModel):
    id: str
    nos: str
    pc_refs: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)
    difficulty_prior: float = Field(ge=-3, le=3)
    stem: Text
    options: list[Text] = Field(min_length=3, max_length=4)
    answer: int
    explanation: Text
    image: str | None = None

    @model_validator(mode="after")
    def _answer_in_range(self):
        if not 0 <= self.answer < len(self.options):
            raise ValueError(f"{self.id}: answer index out of range")
        return self


class Bank(BaseModel):
    trade: str
    version: str
    status: str
    qualification_nqr_id: int | None = None
    nos: dict[str, dict] = Field(description="NOS code -> {title: {en, hi}, weight}")
    sources: dict[str, str]
    items: list[Item]

    @model_validator(mode="after")
    def _consistent(self):
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.trade}: duplicate item ids")
        for it in self.items:
            if it.nos not in self.nos:
                raise ValueError(f"{it.id}: NOS {it.nos} is not listed in the bank")
            if missing := [k for k in it.sources if k not in self.sources]:
                raise ValueError(f"{it.id}: unknown sources {missing}")
        return self

    def item(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)


@cache
def load(trade: str) -> Bank:
    path = BANKS / f"{trade}.yaml"
    if not path.exists():
        raise KeyError(f"no question bank for {trade!r}")
    return Bank.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def trades() -> list[str]:
    return sorted(p.stem for p in BANKS.glob("*.yaml"))


@cache
def params(trade: str) -> dict:
    """{version, calibrated: bool, b: {item_id: difficulty}}; falls back to the AI-drafted priors."""
    bank = load(trade)
    path = BANKS / "params" / f"{trade}.json"
    prior = {it.id: it.difficulty_prior for it in bank.items}
    if path.exists():
        p = json.loads(path.read_text())
        return {"version": p["version"], "calibrated": True, "b": {**prior, **p["b"]}}
    return {"version": f"prior-{bank.version}", "calibrated": False, "b": prior}


@cache
def translations(trade: str, lang: str) -> dict:
    path = BANKS / "i18n" / f"{trade}.{lang}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def localise(trade: str, item: Item, lang: str) -> dict:
    """Item text in `lang`, falling back to Hindi then English, with a status the UI shows."""
    if lang in ("en", "hi"):
        pick = lang
        return {"stem": getattr(item.stem, pick), "options": [getattr(o, pick) for o in item.options],
                "explanation": getattr(item.explanation, pick), "language": pick, "translation": "original"}
    tr = translations(trade, lang)
    t = tr.get("items", {}).get(item.id)
    if t and len(t.get("options", [])) == len(item.options):
        meta = tr.get("meta", {})
        status = "reviewed" if meta.get("reviewed") else "machine"
        return {"stem": t["stem"], "options": t["options"], "explanation": t.get("explanation", item.explanation.en),
                "language": lang, "translation": status, "provider": meta.get("provider")}
    return {"stem": item.stem.hi, "options": [o.hi for o in item.options], "explanation": item.explanation.hi,
            "language": "hi", "translation": "missing"}
