"""Print-ready review packs for the experts who check our AI-drafted content (`make review-packs`).

For every quiz bank and every trade's practical rubrics this writes, to data/review/ (gitignored, rebuilt
from the YAML files each time):

  quiz_<trade>.html     every question in English and Hindi with the marked answer, the cited sources and
                        the official performance criteria it is linked to, and boxes to tick. Open it in a
                        browser and print it, or read it on screen.
  quiz_<trade>.csv      one row per question, for the expert's verdicts: verdict (ok / fix / remove),
                        hindi (ok / fix), difficulty (easy / medium / hard for a typical worker),
                        correction, comment.
  rubric_<trade>.html   every task: what the worker is asked to do, the checklist, each criterion with its
                        NOS, the official criterion text, weight, critical flag and levels 0 to 3, and for the
                        video pilot the clip prompts with the words the app listens for.
  rubric_<trade>.csv    one row per task, checklist item, criterion and clip, for verdicts.
  ui_hindi.csv          every English text of the app next to its Hindi version, for a native speaker:
                        verdict (ok / fix), better_hindi, comment.

The AI's own difficulty guesses are left out on purpose, so the expert's judgement is independent.
docs/remaining_tasks_guide.md says who reviews what and what the team does with the returned sheets, which
are saved as docs/review/<sheet>_<reviewer code>.csv. `make review-summary` (--summary) counts their verdicts
into experiments/expert_review.json, so the report never quotes a hand-counted number.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hunar.paths import DATA, EXPERIMENTS  # noqa: E402
from hunar.quiz import bank as banks  # noqa: E402
from hunar.rubric.engine import load_tasks  # noqa: E402

OUT = DATA / "review"
RETURNED = ROOT / "docs" / "review"  # the experts' filled-in sheets, named <sheet>_<reviewer code>.csv
LOCALES = ROOT / "frontend" / "src" / "i18n" / "locales"
QUIZ_FIELDS = ["item_id", "nos", "question_en", "marked_answer_en", "verdict", "hindi", "difficulty", "correction",
               "comment"]
RUBRIC_FIELDS = ["task_id", "kind", "id", "text_en", "verdict", "hindi", "correction", "comment"]
UI_FIELDS = ["key", "english", "hindi", "verdict", "better_hindi", "comment"]
TRADE_NAMES = {"electrician": "Electrician", "plumber": "Plumber", "carpenter": "Carpenter",
               "appliance_technician": "Appliance technician (ceiling-fan video pilot)"}

CSS = """
@page { size: A4; margin: 14mm 13mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.45 -apple-system, "Segoe UI", Roboto, "Noto Sans", "Noto Sans Devanagari",
       "Kohinoor Devanagari", Mangal, sans-serif; color: #1b1b1b; background: #fff; margin: 0 auto;
       max-width: 190mm; padding: 8mm 0; }
h1 { font-size: 17pt; margin: 0 0 2mm; }
h2 { font-size: 13pt; margin: 7mm 0 2mm; border-bottom: 1.5px solid #333; padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 3mm 0 1mm; }
.meta { color: #444; margin: 0 0 3mm; }
.howto { border: 1px solid #999; background: #f6f6f2; padding: 3mm 4mm; margin: 3mm 0 5mm; }
.howto ol, .howto ul { margin: 1mm 0 1mm 5mm; padding: 0; }
.fill { display: flex; gap: 8mm; flex-wrap: wrap; margin: 2mm 0 4mm; }
.fill span { border-bottom: 1px solid #333; min-width: 45mm; display: inline-block; }
.card { border: 1px solid #888; padding: 3mm 4mm; margin: 0 0 4mm; break-inside: avoid; page-break-inside: avoid; }
.card .id { font-weight: 700; }
.small { font-size: 9pt; color: #444; }
.hi { color: #222; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.pair > div { min-width: 0; }
ol.opts { margin: 1mm 0; padding-left: 6mm; }
ol.opts li { margin: 0.5mm 0; }
.marked { font-weight: 700; }
.marked::after { content: "\\2713 marked correct"; margin-left: 2mm; font-weight: 400; font-size: 9pt; color: #444; }
.boxes { margin-top: 2mm; display: flex; flex-wrap: wrap; gap: 2mm 6mm; font-size: 9.5pt; }
.notes { border-bottom: 1px dotted #777; height: 7mm; margin-top: 1mm; }
table { border-collapse: collapse; width: 100%; margin: 1mm 0; font-size: 9.5pt; }
td, th { border: 1px solid #aaa; padding: 1mm 2mm; vertical-align: top; text-align: left; }
th { background: #eee; }
.crit { font-size: 8.5pt; border: 1px solid #333; padding: 0 1.5mm; margin-left: 2mm; }
@media (max-width: 700px) { .pair { grid-template-columns: 1fr; } body { padding: 4mm; } }
"""


def esc(s: object) -> str:
    return html.escape(str(s))


def boxes(*groups: tuple[str, list[str]]) -> str:
    parts = [f"<span><b>{esc(label)}:</b> " + " &nbsp; ".join(f"&#9744; {esc(o)}" for o in opts) + "</span>"
             for label, opts in groups]
    return f'<div class="boxes">{"".join(parts)}</div><div class="notes"></div>'


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>'
            f"<style>{CSS}</style></head><body>{body}</body></html>\n")


def reviewer_fields() -> str:
    return ('<div class="fill"><div>Reviewer code: <span></span></div><div>Role and years in the trade: '
            '<span></span></div><div>Date: <span></span></div></div>')


def official(nqr_id: int | None) -> tuple[str, dict[str, str], dict[str, str]]:
    """(qualification title, NOS code -> title, PC id -> text) from the parsed official file, if downloaded."""
    path = DATA / "processed" / "qp" / f"{nqr_id}.json"
    if nqr_id is None or not path.exists():
        return "", {}, {}
    qp = json.loads(path.read_text(encoding="utf-8"))
    nos = {n["code"]: n["title"] for n in qp["nos"]}
    pcs = {pc["id"]: pc["text"] for n in qp["nos"] for pc in n["performance_criteria"]}
    return qp.get("title", ""), nos, pcs


def pc_lines(refs: list[str], pcs: dict[str, str]) -> str:
    if not refs:
        return ""
    rows = "".join(f"<li><b>{esc(r)}</b>: {esc(pcs.get(r, '(official text not downloaded: run make data)'))}</li>"
                   for r in refs)
    return f'<div class="small">Linked official performance criteria:<ul>{rows}</ul></div>'


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    # utf-8-sig so that Excel shows Hindi correctly; Google Sheets and LibreOffice read it as well.
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)


def quiz_pack(trade: str, out: Path) -> int:
    b = banks.load(trade)
    title, nos_official, pcs = official(b.qualification_nqr_id)
    name = TRADE_NAMES.get(trade, trade)
    head = (f"<h1>Quiz question review: {esc(name)}</h1>"
            f'<p class="meta">Qualification: {esc(title or "not downloaded")} (NQR {esc(b.qualification_nqr_id)}). '
            f"Question bank version {esc(b.version)}, {len(b.items)} questions. "
            f"Printed {dt.date.today().isoformat()}.</p>"
            f'<p class="meta"><b>Status:</b> {esc(b.status)}</p>'
            '<div class="howto"><b>What we ask you to check, for each question</b><ol>'
            "<li>Is the answer marked correct really correct, by current rules and good practice?</li>"
            "<li>Is exactly one option right, and is each of the others clearly wrong?</li>"
            "<li>Would a working worker of this trade understand the question the first time?</li>"
            "<li>Does it test something the job really needs, under the topic (NOS) shown?</li>"
            "<li>Hindi: does it mean the same as the English, in words workers really use?</li>"
            "<li>How hard is it for a typical working worker of this trade: easy, medium or hard?</li></ol>"
            "Tick <b>OK</b>, <b>Fix</b> (write the fix on the line) or <b>Remove</b>. "
            "Write any missing topic or a better question on the last page. The app shuffles the options for "
            "every worker; here the marked answer is simply listed first. Thank you.</div>"
            + reviewer_fields())
    sections, rows = [], []
    for code, spec in b.nos.items():
        items = [it for it in b.items if it.nos == code]
        if not items:
            continue
        cards = []
        for n, it in enumerate(items, 1):
            opts_en = "".join(f'<li class="{"marked" if k == it.answer else ""}">{esc(o.en)}</li>'
                              for k, o in enumerate(it.options))
            opts_hi = "".join(f'<li class="{"marked" if k == it.answer else ""}">{esc(o.hi)}</li>'
                              for k, o in enumerate(it.options))
            src = "; ".join(b.sources[s] for s in it.sources)
            cards.append(
                f'<div class="card"><div><span class="id">{esc(it.id)}</span> '
                f'<span class="small">({n} of {len(items)} in this topic)</span></div>'
                f'<div class="pair"><div><p>{esc(it.stem.en)}</p><ol class="opts" type="A">{opts_en}</ol>'
                f'<p class="small">Why: {esc(it.explanation.en)}</p></div>'
                f'<div class="hi" lang="hi"><p>{esc(it.stem.hi)}</p><ol class="opts" type="A">{opts_hi}</ol>'
                f'<p class="small">{esc(it.explanation.hi)}</p></div></div>'
                f'<p class="small">Sources: {esc(src)}</p>{pc_lines(it.pc_refs, pcs)}'
                + boxes(("Question", ["OK", "Fix", "Remove"]), ("Hindi", ["OK", "Fix"]),
                        ("Difficulty", ["Easy", "Medium", "Hard"])) + "</div>")
            rows.append({"item_id": it.id, "nos": it.nos, "question_en": it.stem.en,
                         "marked_answer_en": it.options[it.answer].en})
        official_title = nos_official.get(code, "")
        sections.append(f"<h2>{esc(code)}: {esc(spec['title']['en'])}</h2>"
                        + (f'<p class="small">Official NOS title: {esc(official_title)}</p>' if official_title else "")
                        + "".join(cards))
    tail = ('<h2>Anything missing?</h2><p>Topics a worker of this trade must know that no question covers, or a '
            'better question you would ask:</p>' + '<div class="notes"></div>' * 10)
    (out / f"quiz_{trade}.html").write_text(page(f"Quiz review: {name}", head + "".join(sections) + tail),
                                           encoding="utf-8")
    write_csv(out / f"quiz_{trade}.csv", QUIZ_FIELDS, rows)
    return len(rows)


def rubric_pack(trade: str, tasks: list, out: Path) -> int:
    name = TRADE_NAMES.get(trade, trade)
    title, _, pcs = official(tasks[0].qualification_nqr_id)
    head = (f"<h1>Practical task review: {esc(name)}</h1>"
            f'<p class="meta">Qualification: {esc(title or "not downloaded")} (NQR {esc(tasks[0].qualification_nqr_id)}). '
            f"{len(tasks)} tasks. Printed {dt.date.today().isoformat()}.</p>"
            f'<p class="meta"><b>Status:</b> {esc(tasks[0].review.en if tasks[0].review else "not stated")}</p>'
            '<div class="howto"><b>What we ask you to check</b><ul>'
            "<li>Is each task a fair, safe practical test for this trade? Is a step missing?</li>"
            "<li>Checklist: can an assessor see or check each item on site?</li>"
            "<li>Criteria: is each linked to the right official criterion (shown under it)? Are the weights "
            "sensible? Should a failure on it alone mean <i>not yet competent</i> (marked CRITICAL)?</li>"
            "<li>Levels 0 to 3: in the right order, clearly different, and each one something an assessor can "
            "observe? (Levels are in English only for now.)</li>"
            "<li>Video clips (fan pilot only): would a worker understand the prompt, and are the listed words the "
            "words workers really use for each point?</li>"
            "<li>Hindi: same meaning as the English, in words workers use?</li></ul>"
            "Tick <b>OK</b>, <b>Fix</b> (write the fix) or <b>Remove</b>. The app only suggests levels; the assessor "
            "always decides.</div>" + reviewer_fields())
    sections, rows = [], []
    for t in tasks:
        rows.append({"task_id": t.task_id, "kind": "task", "id": t.task_id, "text_en": t.title.en})
        photo_list = "".join(f"<li>{esc(p.en)}</li>" for p in t.photos)
        check_rows = ""
        for c in t.checklist:
            rows.append({"task_id": t.task_id, "kind": "checklist", "id": c.id, "text_en": c.en})
            check_rows += (f"<tr><td>{esc(c.id)}</td><td>{esc(c.en)}</td><td lang='hi'>{esc(c.hi)}</td>"
                           "<td>&#9744; OK &#9744; Fix &#9744; Remove</td></tr>")
        crit_cards = ""
        for cr in t.criteria:
            rows.append({"task_id": t.task_id, "kind": "criterion", "id": cr.id, "text_en": cr.text.en})
            levels = "".join(f"<tr><td>{k}</td><td>{esc(v)}</td></tr>" for k, v in sorted(cr.levels.items()))
            uses = ", ".join(cr.checklist) or "none"
            crit_cards += (
                f'<div class="card"><div><span class="id">{esc(cr.id)}</span> '
                f'<span class="small">NOS {esc(cr.nos)}, weight {cr.weight:g}</span>'
                + ('<span class="crit">CRITICAL</span>' if cr.critical else "")
                + f'</div><div class="pair"><div>{esc(cr.text.en)}</div><div lang="hi">{esc(cr.text.hi)}</div></div>'
                f"{pc_lines(cr.pc_refs, pcs)}"
                f'<table><tr><th style="width:12mm">Level</th><th>What the assessor sees</th></tr>{levels}</table>'
                f'<p class="small">Checklist items it uses: {esc(uses)}</p>'
                + boxes(("Criterion", ["OK", "Fix", "Remove"]), ("Levels", ["OK", "Fix"]),
                        ("Critical flag", ["Right", "Wrong"])) + "</div>")
        clip_cards = ""
        for cl in t.clips:
            rows.append({"task_id": t.task_id, "kind": "clip", "id": cl.id, "text_en": cl.prompt.en})
            terms = "".join(f"<tr><td>{esc(a)}</td><td>{esc(', '.join(ws))}</td></tr>" for a, ws in cl.terms.items())
            clip_cards += (
                f'<div class="card"><div><span class="id">Clip: {esc(cl.part.en)}</span></div>'
                f'<div class="pair"><div>{esc(cl.prompt.en)}</div><div lang="hi">{esc(cl.prompt.hi)}</div></div>'
                f'<table><tr><th style="width:22mm">Point</th><th>Words the app listens for</th></tr>{terms}</table>'
                + boxes(("Prompt", ["OK", "Fix"]), ("Word lists", ["OK", "Add words"])) + "</div>")
        sections.append(
            f"<h2>{esc(t.task_id)}: {esc(t.title.en)}</h2>"
            f'<div class="pair"><div><p>{esc(t.instructions.en)}</p></div>'
            f'<div lang="hi"><p class="small">{esc(t.title.hi)}</p><p>{esc(t.instructions.hi)}</p></div></div>'
            + (f'<p class="small">Photos the app asks for:</p><ul class="small">{photo_list}</ul>' if photo_list else "")
            + boxes(("Task as a whole", ["OK", "Fix", "Remove"]))
            + (f"<h3>Checklist</h3><table><tr><th>id</th><th>English</th><th>Hindi</th><th>Verdict</th></tr>"
               f"{check_rows}</table>" if check_rows else "")
            + "<h3>Criteria</h3>" + crit_cards
            + (f"<h3>Video clips</h3>{clip_cards}" if clip_cards else ""))
    tail = ('<h2>Anything missing?</h2><p>Practical tasks or safety steps this trade needs that are not here:</p>'
            + '<div class="notes"></div>' * 8)
    (out / f"rubric_{trade}.html").write_text(page(f"Task review: {name}", head + "".join(sections) + tail),
                                             encoding="utf-8")
    write_csv(out / f"rubric_{trade}.csv", RUBRIC_FIELDS, rows)
    return len(tasks)


def ui_sheet(out: Path) -> int:
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    hi = json.loads((LOCALES / "hi.json").read_text(encoding="utf-8"))
    rows = [{"key": k, "english": v, "hindi": hi.get(k, "")} for k, v in en.items()]
    write_csv(out / "ui_hindi.csv", UI_FIELDS, rows)
    return len(rows)


def tally(rows: list[dict], column: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = (r.get(column) or "").strip().lower() or "not marked"
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def summary(returned: Path, out: Path) -> int:
    """Count the verdicts in the returned sheets (docs/review/<sheet>_<reviewer code>.csv) for the report."""
    sheets = []
    for path in sorted(returned.glob("*.csv")):
        sheet, _, code = path.stem.rpartition("_")
        if not sheet:
            continue
        with path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        entry: dict = {"file": path.name, "sheet": sheet, "reviewer": code, "rows": len(rows),
                       "verdict": tally(rows, "verdict")}
        for col in ("hindi", "difficulty"):
            if rows and col in rows[0]:
                entry[col] = tally(rows, col)
        sheets.append(entry)
    if not sheets:
        shown = returned.relative_to(ROOT) if returned.is_relative_to(ROOT) else returned
        print(f"RESULT PENDING: no returned review sheets in {shown}/ (see docs/remaining_tasks_guide.md).")
        return 0
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    res = {"experiment": "expert_review", "data_kind": "real", "n_sheets": len(sheets),
           "n_reviewers": len({s["reviewer"] for s in sheets}), "sheets": sheets,
           "note": "Counts of the experts' own verdicts as typed into the returned sheets; not a measure of quality.",
           "command": "python scripts/make_review_packs.py --summary", "git_commit": commit,
           "created": dt.datetime.now().isoformat(timespec="seconds")}
    out.mkdir(exist_ok=True)
    (out / "expert_review.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for s in sheets:
        print(s["file"], s["verdict"])
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT, help="folder for the packs (default data/review/)")
    ap.add_argument("--summary", action="store_true",
                    help="instead, count the verdicts in docs/review/*.csv -> experiments/expert_review.json")
    a = ap.parse_args(argv)
    if a.summary:
        return summary(RETURNED, EXPERIMENTS)
    a.out.mkdir(parents=True, exist_ok=True)
    for trade in banks.trades():
        print(f"quiz_{trade}: {quiz_pack(trade, a.out)} questions")
    by_trade: dict[str, list] = {}
    for t in load_tasks():
        by_trade.setdefault(t.trade, []).append(t)
    for trade, tasks in sorted(by_trade.items()):
        print(f"rubric_{trade}: {rubric_pack(trade, tasks, a.out)} tasks")
    print(f"ui_hindi: {ui_sheet(a.out)} texts")
    shown = a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out
    print(f"Written to {shown}/. Open the .html files in a browser to print; verdicts go in the .csv files "
          "(see docs/remaining_tasks_guide.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
