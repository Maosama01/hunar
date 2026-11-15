"""Turn a Markdown guide into a printable A4 PDF (`make guide-pdf`).

    python scripts/md_to_pdf.py docs/remaining_tasks_guide.md docs/Hunar_Remaining_Tasks_Guide.pdf

Pandoc makes a standalone HTML page with a print stylesheet, and headless Chrome prints it, the same tools
`make report` uses. Links stay clickable in the PDF. The HTML is written to a temporary folder and removed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium"]
CSS = """
@page { size: A4; margin: 16mm 15mm; }
body { font: 10.5pt/1.5 -apple-system, "Segoe UI", Roboto, "Noto Sans", Arial, sans-serif; color: #161616;
       max-width: 180mm; margin: 0 auto; }
h1 { font-size: 20pt; margin: 0 0 3mm; color: #1b2a6b; }
h2 { font-size: 14pt; margin: 8mm 0 2mm; color: #1b2a6b; border-bottom: 1.5px solid #1b2a6b;
     padding-bottom: 1mm; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 5mm 0 1.5mm; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 6mm; }
li { margin: 0.8mm 0; }
code { font: 9pt/1.4 Menlo, Consolas, monospace; background: #f1f1ee; padding: 0 1mm; border-radius: 2px; }
pre { background: #f1f1ee; padding: 2.5mm 3.5mm; border-left: 3px solid #1b2a6b; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 9.5pt; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm; font-size: 9pt; break-inside: auto; }
col { width: auto !important; }
td code { white-space: nowrap; }
tr { break-inside: avoid; }
th, td { border: 1px solid #b8b8b8; padding: 1.2mm 2mm; text-align: left; vertical-align: top; }
th { background: #e9ebf3; }
a { color: #1b2a6b; }
strong { color: #000; }
header#title-block-header { display: none; }
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    src, out = Path(args[0]), Path(args[1])
    chrome = next((c for c in CHROME if Path(c).exists() or shutil.which(c)), None)
    if chrome is None:
        print("Chrome not found; open the Markdown file and print it instead.")
        return 1
    import pypandoc

    title = next((line[2:].strip() for line in src.read_text(encoding="utf-8").splitlines()
                  if line.startswith("# ")), src.stem)
    with tempfile.TemporaryDirectory() as tmp:
        css, html = Path(tmp) / "print.css", Path(tmp) / "page.html"
        css.write_text(CSS, encoding="utf-8")
        pypandoc.convert_file(str(src), "html", outputfile=str(html),
                              extra_args=["--standalone", "--embed-resources", "--css", str(css),
                                          "--metadata", f"title={title}", "--metadata", "lang=en"])
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out.resolve()}", html.as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
