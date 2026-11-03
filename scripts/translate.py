"""Machine-translate the app's UI strings and quiz questions into the 22 scheduled languages (Bhashini).

  python scripts/translate.py [--langs ta te ...] [--what ui quiz] [--force] [--dry-run]

Needs BHASHINI_USER_ID, BHASHINI_API_KEY and BHASHINI_PIPELINE_ID (see hunar/speech/bhashini.py).
Sources: frontend/src/i18n/locales/en.json (UI) and the English text of hunar/quiz/banks/*.yaml.
Outputs, all marked "machine-translated, not reviewed":
  frontend/src/i18n/locales/<lang>.json            {"_meta": {...}, key: text}
  backend/hunar/quiz/banks/i18n/<trade>.<lang>.json {"meta": {...}, "items": {id: {stem, options, explanation}}}

Placeholders such as {n} are swapped for numbered markers before translation; a string whose markers
do not all come back is left out (the app then falls back to English) and counted in the summary.
Strings already translated from the same English text are kept, so re-runs only send what changed.
A native speaker should review each file and set "reviewed": true.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hunar.speech.bhashini import LANGS, Bhashini  # noqa: E402

UI_DIR = ROOT / "frontend" / "src" / "i18n" / "locales"
BANK_DIR = ROOT / "backend" / "hunar" / "quiz" / "banks"
TARGETS = [code for code in LANGS if code not in ("en", "hi")]  # Hindi is written by people
PLACEHOLDER = re.compile(r"\{\w+\}")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:10]


def protect(text: str) -> tuple[str, list[str]]:
    found = PLACEHOLDER.findall(text)
    for i, ph in enumerate(found):
        text = text.replace(ph, f"[[{i}]]", 1)
    return text, found


def restore(text: str, found: list[str]) -> str | None:
    for i, ph in enumerate(found):
        marker = f"[[{i}]]"
        if marker not in text:
            return None
        text = text.replace(marker, ph, 1)
    return text


def translate_map(client, source: dict[str, str], old: dict[str, str], old_hashes: dict[str, str], lang: str,
                  force: bool) -> tuple[dict[str, str], dict[str, str], int]:
    """Translate the values of `source`, reusing old translations whose English text is unchanged."""
    out, hashes, todo = {}, {}, []
    for k, en in source.items():
        if not force and k in old and old_hashes.get(k) == _hash(en):
            out[k], hashes[k] = old[k], old_hashes[k]
        else:
            todo.append(k)
    protected = [protect(source[k]) for k in todo]
    results = client.translate([p[0] for p in protected], "en", lang) if todo else []
    lost = 0
    for k, (_, found), got in zip(todo, protected, results, strict=True):
        text = restore(got, found)
        if text is None:
            lost += 1
            continue
        out[k], hashes[k] = text, _hash(source[k])
    return out, hashes, lost


def meta(lang: str) -> dict:
    return {"provider": "bhashini", "reviewed": False, "language": lang,
            "generated": dt.date.today().isoformat(), "note": "Machine-translated, not yet checked by a native speaker."}


def do_ui(client, lang: str, force: bool) -> str:
    en = json.loads((UI_DIR / "en.json").read_text(encoding="utf-8"))
    source = {k: v for k, v in en.items() if not k.startswith("_")}
    path = UI_DIR / f"{lang}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old_hashes = old.get("_meta", {}).get("source_hashes", {})
    out, hashes, lost = translate_map(client, source, old, old_hashes, lang, force)
    path.write_text(json.dumps({"_meta": {**meta(lang), "source_hashes": hashes}, **out}, ensure_ascii=False,
                               indent=1) + "\n", encoding="utf-8")
    return f"ui {lang}: {len(out)}/{len(source)} strings ({lost} dropped: placeholders lost)"


def do_quiz(client, lang: str, force: bool) -> list[str]:
    lines = []
    for bank_file in sorted(BANK_DIR.glob("*.yaml")):
        bank = yaml.safe_load(bank_file.read_text(encoding="utf-8"))
        source = {}
        for it in bank["items"]:
            source[f"{it['id']}|stem"] = it["stem"]["en"]
            source[f"{it['id']}|explanation"] = it["explanation"]["en"]
            for j, o in enumerate(it["options"]):
                source[f"{it['id']}|option{j}"] = o["en"]
        path = BANK_DIR / "i18n" / f"{bank['trade']}.{lang}.json"
        old_doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        old_flat = old_doc.get("flat", {})
        out, hashes, lost = translate_map(client, source, old_flat, old_doc.get("meta", {}).get("source_hashes", {}),
                                          lang, force)
        items = {}
        for it in bank["items"]:
            keys = [f"{it['id']}|stem", f"{it['id']}|explanation"] + [f"{it['id']}|option{j}"
                                                                        for j in range(len(it["options"]))]
            if all(k in out for k in keys):  # only complete items are used; others fall back to Hindi
                items[it["id"]] = {"stem": out[keys[0]], "explanation": out[keys[1]],
                                   "options": [out[k] for k in keys[2:]]}
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"meta": {**meta(lang), "source_hashes": hashes}, "items": items, "flat": out},
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        lines.append(f"quiz {bank['trade']} {lang}: {len(items)}/{len(bank['items'])} items ({lost} strings dropped)")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--langs", nargs="+", default=TARGETS, choices=TARGETS)
    ap.add_argument("--what", nargs="+", default=["ui", "quiz"], choices=["ui", "quiz"])
    ap.add_argument("--force", action="store_true", help="re-translate everything")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if "ui" in a.what and not (UI_DIR / "en.json").exists():
        print(f"{UI_DIR / 'en.json'} not found")
        return 1
    if a.dry_run:
        print(f"would translate {a.what} into {len(a.langs)} languages: {' '.join(a.langs)}")
        return 0
    client = Bhashini.from_env()
    if client is None:
        print("Set BHASHINI_USER_ID, BHASHINI_API_KEY and BHASHINI_PIPELINE_ID (from your Bhashini account) first.")
        return 1
    for lang in a.langs:
        try:
            if "ui" in a.what:
                print(do_ui(client, lang, a.force))
            if "quiz" in a.what:
                print("\n".join(do_quiz(client, lang, a.force)))
        except Exception as e:  # one language failing (unsupported pair, quota) should not stop the rest
            print(f"{lang}: FAILED ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
