"""One-shot extractor for Nick's game database HTML exports.

Reads every HTML file in the downloaded database directory, parses the
embedded Google Sheets table, and writes a clean TSV alongside each sheet
into data/raw/nick_db/.
"""
import os
import sys
from html.parser import HTMLParser
from pathlib import Path


class TableExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._cur: list[str] = []
        self._txt: list[str] = []
        self._in_td = False
        self._in_tr = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._in_tr = True
            self._cur = []
        elif tag in ("td", "th") and self._in_tr:
            self._in_td = True
            self._txt = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_td:
            self._cur.append(" ".join("".join(self._txt).split()))
            self._in_td = False
        elif tag == "tr" and self._in_tr:
            if self._cur:
                self.rows.append(self._cur)
            self._in_tr = False

    def handle_data(self, data):
        if self._in_td:
            self._txt.append(data)


def extract(src_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for fn in sorted(src_dir.iterdir()):
        if fn.suffix.lower() != ".html":
            continue
        t = TableExtractor()
        t.feed(fn.read_text(encoding="utf-8", errors="ignore"))
        out_name = fn.stem.replace(" ", "_").replace("+", "_") + ".tsv"
        out_path = out_dir / out_name
        with out_path.open("w", encoding="utf-8", newline="") as w:
            for row in t.rows:
                # strip leading row-number cell from Google Sheets export
                cells = row[1:] if len(row) > 1 and row[0].strip().isdigit() else row
                # drop trailing empty cells
                while cells and not cells[-1].strip():
                    cells.pop()
                if cells:
                    w.write("\t".join(cells) + "\n")
        print(f"  {fn.name} -> {out_path.name} ({len(t.rows)} rows)")


def main():
    src = Path(r"C:\Users\bekru\Downloads\Copy of Don't Die AI Game Database - Updated April 13th")
    out = Path(r"C:\dev\dontDieAi\data\raw\nick_db")
    print(f"source: {src}")
    print(f"out:    {out}")
    extract(src, out)


if __name__ == "__main__":
    main()
