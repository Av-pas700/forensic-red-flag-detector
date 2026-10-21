"""Render reports/memo.md to reports/memo.pdf with headless Chrome/Chromium (skipped if none is installed).

The memo must fit on two A4 pages; the script fails if it does not.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

from redflag import config

CSS = """
@page { size: A4; margin: 13mm 15mm; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; font-size: 10.2pt; line-height: 1.4; color: #1f2328; }
h1 { font-size: 15pt; margin: 0 0 4px; } h2 { font-size: 11pt; margin: 9px 0 3px; border-bottom: 1px solid #d0d7de; padding-bottom: 1px; }
p { margin: 3px 0; } ul, ol { margin: 3px 0; padding-left: 18px; } li { margin: 1px 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 5px 0; }
th, td { border: 1px solid #d0d7de; padding: 2px 5px; text-align: left; } th { background: #f6f8fa; }
em { color: #57606a; }
"""

CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def find_chrome() -> str | None:
    for c in CANDIDATES:
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    return None


def main() -> int:
    chrome = find_chrome()
    if chrome is None:
        print("no Chrome/Chromium found; skipping memo.pdf (memo.md is the source of truth)")
        return 0
    src = config.REPORTS / "memo.md"
    html = markdown.markdown(src.read_text(), extensions=["tables"])
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Memo</title><style>{CSS}</style></head><body>{html}</body></html>"
    out = config.REPORTS / "memo.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "memo.html"
        page.write_text(doc)
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    from pypdf import PdfReader

    pages = len(PdfReader(str(out)).pages)
    print(f"wrote {out.relative_to(config.ROOT)} ({pages} pages)")
    if pages > 2:
        print("ERROR: memo exceeds two pages")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
