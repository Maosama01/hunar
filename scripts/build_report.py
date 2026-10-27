"""Assemble the project report from docs/report/report.md (`make report`).

Placeholders are filled only from generated or sourced files, never typed numbers:
  {{<experiment>:<dotted.path>|<format>}}  value from experiments/<experiment>.json (else RESULT PENDING)
  {{fact:<key>}}                           sourced external fact from docs/report/facts.json
  {{fact:n_nos}} / {{fact:n_pcs}}          counted from data/processed/qp/*.json
  {{table:qp}}                             qualification table rows from the parsed packs
  {{include:<file>}}                       a generated file in docs/report/
  {{git:commit}}                           current commit
Outputs docs/report/Hunar_Report.md, .docx (pandoc) and .pdf (headless Chrome, if installed).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "docs" / "report"
EXP = ROOT / "experiments"
QP = ROOT / "data" / "processed" / "qp"
CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium"]


def exp_value(name: str, path: str, fmt: str | None) -> str:
    f = EXP / f"{name}.json"
    if not f.exists():
        return "RESULT PENDING"
    v = json.loads(f.read_text())
    for part in path.split("."):
        if not isinstance(v, dict) or part not in v:
            return "RESULT PENDING"
        v = v[part]
    if v is None:
        return "RESULT PENDING"
    return format(v, fmt) if fmt else str(v)


def packs() -> list[dict]:
    order = [p["nqr_id"] for p in json.loads((ROOT / "data" / "qp_sources.json").read_text())["packs"]]
    return [json.loads((QP / f"{i}.json").read_text()) for i in order]


def qp_table() -> str:
    rows = []
    for p in packs():
        n_pc = sum(len(n["performance_criteria"]) for n in p["nos"])
        rows.append(f"| {p['role']} | {p['title']} ({p['nqr_code']}) | {p['awarding_body']} | {p['nsqf_level']:g} | "
                    f"{len(p['nos'])} | {n_pc} |")
    return "\n".join(rows)


def references() -> str:
    text = (REP / "references.md").read_text()
    entries = re.findall(r"\*\*\[(\d+)\] `([^`]+)`\*\*\s*\n(.+)", text)
    out = "\n".join(f"[{n}] {cite.strip()}\n" for n, _, cite in entries)
    (REP / "references_ieee.md").write_text(out)
    return out


def fill(md: str) -> str:
    facts = json.loads((REP / "facts.json").read_text())
    all_packs = packs()
    counted = {"n_nos": str(sum(len(p["nos"]) for p in all_packs)),
               "n_pcs": str(sum(len(n["performance_criteria"]) for p in all_packs for n in p["nos"]))}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

    def sub(m: re.Match) -> str:
        key, _, rest = m.group(1).partition(":")
        if key == "git":
            return commit or "unknown"
        if key == "fact":
            return counted.get(rest) or facts[rest]["value"]
        if key == "table" and rest == "qp":
            return qp_table()
        if key == "include":
            if rest == "references_ieee.md":
                return references()
            body = (REP / rest).read_text()
            return "\n".join(line for line in body.splitlines() if not line.startswith("<!--"))
        path, _, fmt = rest.partition("|")
        return exp_value(key, path, fmt or None)

    return re.sub(r"\{\{([^}]+)\}\}", sub, md)


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_results_table.py")], check=True)
    md = fill((REP / "report.md").read_text())
    if "{{" in md:
        print("unresolved placeholders remain", file=sys.stderr)
        return 1
    out_md = REP / "Hunar_Report.md"
    out_md.write_text(md)
    import pypandoc

    pypandoc.convert_file(str(out_md), "docx", outputfile=str(REP / "Hunar_Report.docx"),
                          extra_args=["--toc", f"--resource-path={REP}", "--standalone"])
    html = REP / "Hunar_Report.html"
    css = ("body{font-family:Georgia,'Noto Serif',serif;max-width:46em;margin:2em auto;line-height:1.45;"
           "font-size:11pt;color:#111}h1,h2,h3{font-family:Helvetica,Arial,sans-serif}table{border-collapse:collapse;"
           "font-size:9pt;margin:1em 0}td,th{border:1px solid #999;padding:3px 6px}img{max-width:100%}"
           "blockquote{border-left:3px solid #999;margin-left:0;padding-left:1em;color:#333}"
           "pre{font-size:8pt;background:#f5f5f5;padding:.5em;overflow-x:auto}"
           "@page{size:A4;margin:18mm}")
    (REP / "report.css").write_text(css)
    pypandoc.convert_file(str(out_md), "html", outputfile=str(html),
                          extra_args=["--standalone", "--toc", "--embed-resources",
                                      f"--resource-path={REP}", "--css", str(REP / "report.css"),
                                      "--metadata", "lang=en"])
    chrome = next((c for c in CHROME if Path(c).exists() or shutil.which(c)), None)
    if chrome:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={REP / 'Hunar_Report.pdf'}", html.as_uri()],
                       check=False, capture_output=True, timeout=180)
    print("built:", ", ".join(p.name for p in sorted(REP.glob("Hunar_Report.*"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
