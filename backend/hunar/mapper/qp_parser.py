"""Parse NCVET qualification files (QF PDFs from nqr.gov.in) into `QualificationPack` JSON.

The QF template has two tables we need:

* Section 2 "Module Summary": one row per NOS with its name, code, core flag, level and hours.
* "Annexure: Detailed Assessment Criteria": NOS name in the first column and one
  performance criterion (PC1., PC2., ...) per row, with wrapped lines continuing on later rows.

Layouts seen in the official files and handled here: a NOS name or code that wraps onto extra rows of
the module table (FFSC); a criteria table that continues on the next page without its name column,
so PCs and outcome headings move into the first column (WMPSC, FFSC); outcome headings ("Install
sanitary fixtures ...") that carry their own marks and must not be glued onto the criterion above (they
are kept only as a hint for naming a block whose NOS name is not printed); two criteria printed in
one cell ("PC19. ... PC20. ..."); and the first row of a table continued on a new page, which
pdfplumber sometimes leaves out of the table, so criteria printed above a page's table are read from
the page text.

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


def _summary_records(table: list[list[str | None]]) -> list[list[str]]:
    """Numbered rows of a module table, with names and codes that wrap onto the following unnumbered
    rows joined back (column by column). Rows with marks or totals never count as a continuation."""
    records: list[list[str]] = []
    for row in table:
        raw = [_clean(c) for c in row]
        cells = [c for c in raw if c]
        if not cells:
            continue
        if re.fullmatch(r"\d+\.?", cells[0]):
            records.append(raw)
        elif records and not raw[0] and not any(re.search(r"\d", c) and NUM_RE.fullmatch(c) for c in cells) \
                and not any("total" in c.lower() for c in cells):
            rec = records[-1]
            for k, c in enumerate(raw[: len(rec)]):
                if c:
                    rec[k] = f"{rec[k]} {c}".strip()
    return records


def parse_module_summary(pdf: pdfplumber.PDF) -> list[dict]:
    """Rows of the Section 2 NOS table: name, code, core, level, hours."""
    texts = [p.extract_text() or "" for p in pdf.pages]
    start = next(i for i, t in enumerate(texts) if "Mandatory NOS" in t and "Table of Contents" not in t)
    end = next((i for i in range(start, len(texts)) if "Section 3" in texts[i]), start + 3)
    rows = []
    for pi in range(start, end + 1):
        for table in pdf.pages[pi].extract_tables():
            for rec in _summary_records(table):
                cells = [c for c in rec if c]
                if len(cells) < 4:
                    continue
                name, code_raw = cells[1], cells[2]
                if not CODE_RE.search(code_raw):  # bridge modules and on-the-job training have no NOS code
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


def _pc_events(text: str) -> list[tuple]:
    """('pc', n, text) for each criterion in a cell; one cell sometimes holds two ("PC19. ... PC20. ...")."""
    out = []
    for part in re.split(r"\s(?=PC\s*\d+\s*[.:)]\s)", text):
        m = PC_RE.match(part)
        out.append(("pc", int(m.group(1)), m.group(2)))
    return out


MARKS_TAIL = re.compile(r"(?:\s+(?:-|\d+(?:\.\d+)?)){1,4}\s*$")  # up to four mark columns at a line's end


def _orphan_rows(page, tables) -> list[tuple]:
    """Criteria printed above the first table on a page (a row continuing the previous page's table
    that table detection missed), with their wrapped lines; outcome headings and page headers skipped."""
    top = min(t.bbox[1] for t in tables)
    if top < 5:
        return []
    pcs = [w for w in page.crop((0, 0, page.width, top)).extract_words() if re.match(r"PC\s*\d", w["text"])]
    if not pcs:
        return []
    # Read from the criteria column: NOS name fragments to its left share the same text lines.
    left = min(w["x0"] for w in pcs) - 1
    events: list[tuple] = []
    started = False
    for line in (page.crop((left, 0, page.width, top)).extract_text() or "").splitlines():
        line = _clean(line)
        if NUM_RE.fullmatch(line):  # the marks of a wrapped criterion, printed on a line of their own
            continue
        body = MARKS_TAIL.sub("", line)
        if PC_RE.match(body):
            events.extend(_pc_events(body))
            started = True
        elif started and body:
            if re.search(r"\d", line[len(body):]):  # a heading with its own marks ends the criterion
                started = False
            else:
                events.append(("text", body, False, False))
    return events


def _is_header_row(cells: list[str]) -> bool:
    if any(c.startswith(("NOS/Module Name", "Assessment Criteria", "Assessment outcomes", "S. No")) for c in cells):
        return True
    return all(c.lower() in HEADER_CELLS for c in cells)


def _events(pdf: pdfplumber.PDF, start: int, end: int) -> list[tuple]:
    """Flatten the annexure tables into ('name'|'pc'|'text'|'total', ...) events in reading order."""
    events: list[tuple] = []
    for pi in range(start, end):
        page = pdf.pages[pi]
        found = page.find_tables()
        if found:
            events.extend(_orphan_rows(page, found))
        for table in (t.extract() for t in found):
            for row in table:
                if not row:
                    continue
                first = _clean(row[0])
                rest = [_clean(c) for c in row[1:] if c not in (None, "")]
                if _is_header_row([first, *rest]):
                    continue
                has_total = any(TOTAL_RE.match(c) for c in [first, *rest])
                marks = [c for c in rest if NUM_RE.fullmatch(c)]
                has_marks, digit_marks = bool(marks), any(re.search(r"\d", c) for c in marks)
                texts = [c for c in rest if not (TOTAL_RE.match(c) or NUM_RE.fullmatch(c))]
                if first and not TOTAL_RE.match(first):
                    if PC_RE.match(first):  # table continued on a new page without its name column
                        events.extend(_pc_events(first))
                    elif not texts and digit_marks:  # ... so an outcome heading moved into the first column
                        events.append(("heading", first))
                    else:
                        events.append(("name", re.sub(r"^\d+\.\s*", "", first)))
                for c in texts:
                    events.extend(_pc_events(c) if PC_RE.match(c) else [("text", c, has_marks, digit_marks)])
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
    cur = {"names": [], "pcs": [], "hints": []}
    for e in events:
        if e[0] == "total":
            if cur["pcs"]:
                blocks.append(cur)
            cur = {"names": [], "pcs": [], "hints": []}
        elif e[0] == "name":
            cur["names"].append((e[1], len(cur["pcs"])))
        elif e[0] == "pc":
            if e[1] == 1 and cur["pcs"]:
                # PC numbering restarted without a total row: names seen after the last PC
                # are the heading of the new block.
                n = len(cur["pcs"])
                carry = [x for x in cur["names"] if x[1] == n]
                hints = [x for x in cur["hints"] if x[1] == n]
                cur["names"] = [x for x in cur["names"] if x[1] != n]
                cur["hints"] = [x for x in cur["hints"] if x[1] != n]
                blocks.append(cur)
                cur = {"names": [(t, 0) for t, _ in carry], "pcs": [], "hints": [(t, 0) for t, _ in hints]}
            cur["pcs"].append({"code": f"PC{e[1]}", "text": e[2]})
        elif e[0] == "heading" or (pc_mode and e[3]):
            # An outcome heading with its own marks, not part of a criterion; kept only as a naming hint.
            cur["hints"].append((e[1], len(cur["pcs"])))
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
        b["hint"] = " ".join(t for t, _ in b.pop("hints"))
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
        # Some files print no NOS name for a block: fall back to its outcome headings and criteria.
        name = b["title"] or " ".join([b.get("hint", ""), *(p["text"] for p in b["pcs"])])
        bt = _tokens(name)
        flat = re.sub(r"\s+", "", name)
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
    src = json.loads((DATA / "qp_sources.json").read_text())
    sources = src["packs"] + src.get("trade_packs", [])  # trade packs: quiz banks only, not M1
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
