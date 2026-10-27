"""Download the official NQR qualification files listed in data/qp_sources.json.

PDFs go to data/raw/qp/ (gitignored). The source URL, download date and SHA-256
of every file are written to data/processed/qp_manifest.json, which is committed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "qp_sources.json"
RAW = ROOT / "data" / "raw" / "qp"
MANIFEST = ROOT / "data" / "processed" / "qp_manifest.json"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    if MANIFEST.exists():
        old = {e["nqr_id"]: e for e in json.loads(MANIFEST.read_text())["files"]}
    entries = []
    for pack in json.loads(SOURCES.read_text())["packs"]:
        dest = RAW / f"{pack['nqr_id']}.pdf"
        if dest.exists() and pack["nqr_id"] in old:
            entries.append(old[pack["nqr_id"]])
            print(f"cached  {dest.name}  {pack['title']}")
            continue
        req = urllib.request.Request(pack["pdf_url"], headers={"User-Agent": "Mozilla/5.0 (Hunar academic project)"})
        data = urllib.request.urlopen(req, timeout=120).read()
        if not data.startswith(b"%PDF"):
            print(f"ERROR   {pack['title']}: response is not a PDF", file=sys.stderr)
            return 1
        dest.write_bytes(data)
        entries.append({
            "nqr_id": pack["nqr_id"],
            "title": pack["title"],
            "source_url": pack["pdf_url"],
            "page_url": pack["page_url"],
            "downloaded_on": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
        print(f"fetched {dest.name}  {pack['title']}  ({len(data)} bytes)")
    MANIFEST.write_text(json.dumps({"files": entries}, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
