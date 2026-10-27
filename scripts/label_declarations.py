"""Team tool for writing and labelling worker declarations for the M1 evaluation.

    uv run python scripts/label_declarations.py --author "Your Name"     # add declarations
    uv run python scripts/label_declarations.py --check                  # validate the CSV

Rows are appended to data/labels/declarations.csv. Follow docs/labelling_guidelines.md.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "labels" / "declarations.csv"
FIELDS = ["id", "text", "language", "label_nqr_id", "author", "data_kind", "difficulty"]
LANGS = {"1": "en", "2": "hi", "3": "hinglish"}
PACKS = json.loads((ROOT / "data" / "qp_sources.json").read_text())["packs"]
PACK_IDS = {str(p["nqr_id"]) for p in PACKS}


def read_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check() -> int:
    rows, problems = read_rows(), []
    seen_ids, seen_text = set(), set()
    for i, r in enumerate(rows, start=2):
        if set(r) != set(FIELDS):
            problems.append(f"line {i}: columns must be {FIELDS}")
            continue
        if r["id"] in seen_ids:
            problems.append(f"line {i}: duplicate id {r['id']}")
        if r["text"].strip().lower() in seen_text:
            problems.append(f"line {i}: duplicate text")
        if r["language"] not in LANGS.values():
            problems.append(f"line {i}: language must be en, hi or hinglish")
        if r["label_nqr_id"] not in PACK_IDS:
            problems.append(f"line {i}: label_nqr_id {r['label_nqr_id']} is not one of {sorted(PACK_IDS)}")
        if r["data_kind"] != "real":
            problems.append(f"line {i}: team-written rows must have data_kind=real")
        if not r["author"].strip():
            problems.append(f"line {i}: author is required")
        seen_ids.add(r["id"])
        seen_text.add(r["text"].strip().lower())
    counts = collections.Counter((r["label_nqr_id"], r["language"]) for r in rows)
    print(f"{len(rows)} declarations in {CSV_PATH.relative_to(ROOT)}")
    print("pack      " + "  ".join(f"{lang:>8s}" for lang in LANGS.values()))
    for p in PACKS:
        print(f"{p['nqr_id']:<9} " + "  ".join(f"{counts[(str(p['nqr_id']), lang)]:>8d}" for lang in LANGS.values())
              + f"   {p['title']}")
    print("by author:", dict(collections.Counter(r["author"] for r in rows)))
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


def add(author: str) -> int:
    rows = read_rows()
    n = len(rows)
    print("Write one declaration at a time. Finish the text with an empty line. Ctrl+C to stop.\n")
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        while True:
            try:
                lang = LANGS.get(input("Language [1=English 2=Hindi(Devanagari) 3=Hinglish]: ").strip())
                if not lang:
                    print("  choose 1, 2 or 3")
                    continue
                print("Declaration text:")
                lines = []
                while (line := input()) != "":
                    lines.append(line)
                text = " ".join(lines).strip()
                if not text:
                    continue
                for i, p in enumerate(PACKS, start=1):
                    print(f"  {i}. {p['title']} (NSQF {p['nsqf_level']})")
                choice = input("Which pack does this describe best? ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(PACKS):
                    print("  skipped: invalid pack number")
                    continue
                hard = input("Hard case (mentions other trades too)? [y/N] ").strip().lower() == "y"
                n += 1
                w.writerow({"id": f"T{n:03d}", "text": text, "language": lang,
                            "label_nqr_id": PACKS[int(choice) - 1]["nqr_id"], "author": author,
                            "data_kind": "real", "difficulty": "hard" if hard else "normal"})
                f.flush()
                print(f"  saved T{n:03d}\n")
            except (KeyboardInterrupt, EOFError):
                print("\nstopped")
                return check()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--author")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check or not a.author:
        sys.exit(check())
    sys.exit(add(a.author))
