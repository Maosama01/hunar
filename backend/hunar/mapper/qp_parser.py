"""Parse NCVET qualification files (QF PDFs from nqr.gov.in) into `QualificationPack` JSON.

The QF template has two tables we need:

* Section 2 "Module Summary": one row per NOS with its name, code, core flag, level and hours.
* "Annexure: Detailed Assessment Criteria": NOS name in the first column and one
  performance criterion (PC1., PC2., ...) per row, with wrapped lines continuing on later rows.

Usage:  python -m hunar.mapper.qp_parser            (parses every pack in data/qp_sources.json)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

from hunar.paths import DATA
from hunar.schemas import NOS, PerformanceCriterion, QualificationPack, Source

PC_RE = re.compile(r"^\s*PC\s*(\d+)\s*[.:)]?\s*(.*)$", re.S)
CODE_RE = re.compile(r"([A-Z]{2,5}\s*/\s*[A-Z]{1,4}\s*/?\s*[A-Z]?\s*\d[\d\s]*)")
HEADER_WORDS = ("NOS/Module Name", "Assessment Criteria", "Outcomes", "Total Marks", "Marks")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower())


def _fix_code(raw: str) -> str:
    """'PSS/N170 6' -> 'PSS/N1706', 'CON/N0602 & v 5.0' -> 'CON/N0602'."""
    raw = raw.split("&")[0]
    raw = re.split(r"\s[Vv]\s?\d", raw)[0]
    m = CODE_RE.search(raw.replace("\n", " "))
    return re.sub(r"\s+", "", m.group(1)) if m else re.sub(r"\s+", "", raw)


def _num(s: str) -> float | None:
    try:
        return float(_clean(s))
    except ValueError:
        return None


def parse_module_summary(pdf: pdfplumber.PDF) -> list[dict]:
    """Rows of the Section 2 NOS table: name, code, core, level, hours."""
    texts = [p.extract_text() or "" for p in pdf.pages]
    start = next(i for i, t in enumerate(texts) if "Mandatory NOS" in t and "Table of Contents" not in t)
    end = next((i for i in range(start, len(texts)) if "Section 3" in texts[i]), start + 3)
    rows = []
    for pi in range(start, end + 1):
        for table in pdf.pages[pi].extract_tables():
            for row in table:
                cells = [c for c in row if c not in (None, "")]
                if len(cells) < 4 or not re.fullmatch(r"\d+\.?", _clean(cells[0])):
                    continue
                name, code_raw = _clean(cells[1]), cells[2]
                if not re.search(r"\d", code_raw or ""):
                    continue
                rest = [_clean(c) for c in cells[3:]]
                core = None
                if rest and rest[0]:
                    core = not rest[0].lower().replace(" ", "").startswith("non")
                level = _num(rest[1]) if len(rest) > 1 else None
                rows.append({"title": name, "code": _fix_code(code_raw), "core": core, "nsqf_level": level})
    return rows


NUM_RE = re.compile(r"[\d\s.\-%/]+")
TOTAL_RE = re.compile(r"^(nos\s+|grand\s+)?total\b", re.I)
HEADER_CELLS = {"", "marks", "marks (%)", "outcomes", "theory", "practical", "project", "viva", "viva marks"}


def _is_header_row(cells: list[str]) -> bool:
    if any(c.startswith(("NOS/Module Name", "Assessment Criteria", "Assessment outcomes", "S. No")) for c in cells):
        return True
    return all(c.lower() in HEADER_CELLS for c in cells)


def _events(pdf: pdfplumber.PDF, start: int, end: int) -> list[tuple]:
    """Flatten the annexure tables into ('name'|'pc'|'text'|'total', ...) events in reading order."""
    events: list[tuple] = []
    for pi in range(start, end):
        for table in pdf.pages[pi].extract_tables():
            for row in table:
                if not row:
                    continue
                first = _clean(row[0])
                rest = [_clean(c) for c in row[1:] if c not in (None, "")]
                if _is_header_row([first, *rest]):
                    continue
                has_total = any(TOTAL_RE.match(c) for c in [first, *rest])
                if first and not TOTAL_RE.match(first):
                    events.append(("name", re.sub(r"^\d+\.\s*", "", first)))
                has_marks = any(NUM_RE.fullmatch(c) for c in rest)
                for c in rest:
                    if TOTAL_RE.match(c) or NUM_RE.fullmatch(c):
                        continue
                    m = PC_RE.match(c)
                    events.append(("pc", int(m.group(1)), m.group(2)) if m else ("text", c, has_marks))
                if has_total:
                    events.append(("total",))
    return events


def parse_assessment_criteria(pdf: pdfplumber.PDF) -> list[dict]:
    """NOS blocks with their criteria from the Detailed Assessment Criteria annexure.

    Each NOS block ends with a "Total Marks" row. The NOS name sits in a vertically
    centred merged cell, so its text can appear anywhere inside the block (even on the
    next page); we therefore collect name fragments per block and match them to the
    module summary later.
    """
    texts = [p.extract_text() or "" for p in pdf.pages]
    hits = [i for i, t in enumerate(texts) if "Annexure: Detailed Assessment Criteria" in t and "...." not in t]
    start = hits[-1]
    end = next((i for i in range(start + 1, len(texts)) if "Annexure: Assessment Strategy" in texts[i]), len(texts))
    events = _events(pdf, start, end)
    pc_mode = any(e[0] == "pc" for e in events)
    blocks: list[dict] = []
    cur = {"names": [], "pcs": []}
    for e in events:
        if e[0] == "total":
            if cur["pcs"]:
                blocks.append(cur)
            cur = {"names": [], "pcs": []}
        elif e[0] == "name":
            cur["names"].append((e[1], len(cur["pcs"])))
        elif e[0] == "pc":
            if e[1] == 1 and cur["pcs"]:
                # PC numbering restarted without a total row: names seen after the last PC
                # are the heading of the new block.
                n = len(cur["pcs"])
                carry = [x for x in cur["names"] if x[1] == n]
                cur["names"] = [x for x in cur["names"] if x[1] != n]
                blocks.append(cur)
                cur = {"names": [(t, 0) for t, _ in carry], "pcs": []}
            cur["pcs"].append({"code": f"PC{e[1]}", "text": e[2]})
        elif pc_mode or not e[2]:  # continuation of the previous criterion
            if cur["pcs"]:
                cur["pcs"][-1]["text"] = f"{cur['pcs'][-1]['text']} {e[1]}"
        else:  # criterion rows without PC numbers (some DGT files): one marked row = one criterion
            cur["pcs"].append({"code": f"PC{len(cur['pcs']) + 1}", "text": e[1]})
    if cur["pcs"]:
        blocks.append(cur)
    # Drop exact duplicate blocks (some official files repeat a NOS table verbatim).
    unique, seen = [], set()
    for b in blocks:
        b["title"] = " ".join(t for t, _ in b.pop("names"))
        # A row split across a page break is sometimes printed on both pages.
        b["pcs"] = [p for i, p in enumerate(b["pcs"]) if i == 0 or p != b["pcs"][i - 1]]
        key = tuple(_norm(p["text"]) for p in b["pcs"])
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


def _tokens(s: str) -> set[str]:
    stop = {"and", "of", "the", "to", "at", "in", "for", "as", "per", "with", "a", "nos"}
    return {w for w in _norm(s).split() if w not in stop and len(w) > 1}


def _assign_titles(blocks: list[dict], summary: list[dict]) -> list[dict | None]:
    """Match each block to a module-summary row (by NOS code if printed, else by title tokens)."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    if not summary:
        return [None] * len(blocks)
    score = np.zeros((len(blocks), len(summary)))
    for i, b in enumerate(blocks):
        bt = _tokens(b["title"])
        flat = re.sub(r"\s+", "", b["title"])
        for j, row in enumerate(summary):
            if "/" in (row["code"] or "") and row["code"] in flat:
                score[i, j] = 2.0
                continue
            rt = _tokens(row["title"])
            score[i, j] = len(bt & rt) / max(len(rt), 1)
    rows, cols = linear_sum_assignment(-score)
    out: list[dict | None] = [None] * len(blocks)
    for i, j in zip(rows, cols, strict=True):
        if score[i, j] >= 0.5:
            out[i] = summary[j]
    return out


def parse_pack(pdf_path: Path, meta: dict, manifest_entry: dict | None) -> QualificationPack:
    with pdfplumber.open(pdf_path) as pdf:
        summary = parse_module_summary(pdf)
        blocks = parse_assessment_criteria(pdf)
    nos_list = []
    for b, row in zip(blocks, _assign_titles(blocks, summary), strict=True):
        row = row or {}
        code = row.get("code") or f"{meta['nqr_id']}/NOS{len(nos_list) + 1}"
        pcs = [
            PerformanceCriterion(id=f"{code}.{p['code']}", code=p["code"], text=_clean(p["text"]))
            for p in b["pcs"]
            if _clean(p["text"])
        ]
        nos_list.append(
            NOS(code=code, title=row.get("title") or b["title"], core=row.get("core"),
                nsqf_level=row.get("nsqf_level"), performance_criteria=pcs)
        )
    m = manifest_entry or {}
    return QualificationPack(
        nqr_id=meta["nqr_id"], nqr_code=meta.get("nqr_code"), title=meta["title"], sector=meta.get("sector"),
        nsqf_level=meta.get("nsqf_level"), awarding_body=meta.get("awarding_body"), role=meta["role"],
        parse_method="pdf_auto",
        verification_note="Parsed automatically from the official PDF. Spot-checked against the PDF by the "
        "AI assistant; HUMAN CHECK PENDING.",
        source=Source(pdf_url=m.get("source_url"), page_url=m.get("page_url"),
                      downloaded_on=m.get("downloaded_on"), sha256=m.get("sha256")),
        nos=nos_list,
    )


def main() -> int:
    sources = json.loads((DATA / "qp_sources.json").read_text())["packs"]
    manifest = {e["nqr_id"]: e for e in json.loads((DATA / "processed" / "qp_manifest.json").read_text())["files"]}
    out_dir = DATA / "processed" / "qp"
    out_dir.mkdir(parents=True, exist_ok=True)
    for meta in sources:
        pdf_path = DATA / "raw" / "qp" / f"{meta['nqr_id']}.pdf"
        if not pdf_path.exists():
            print(f"missing {pdf_path}; run `make data` first", file=sys.stderr)
            return 1
        out = out_dir / f"{meta['nqr_id']}.json"
        if out.exists() and json.loads(out.read_text()).get("parse_method") == "pdf_auto_hand_checked":
            print(f"keep    {out.name} (hand checked, not overwritten)")
            continue
        qp = parse_pack(pdf_path, meta, manifest.get(meta["nqr_id"]))
        out.write_text(qp.model_dump_json(indent=2) + "\n")
        n_pc = sum(len(n.performance_criteria) for n in qp.nos)
        print(f"parsed  {out.name}  {qp.title}: {len(qp.nos)} NOS, {n_pc} PCs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
