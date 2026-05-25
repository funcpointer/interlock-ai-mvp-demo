from __future__ import annotations

from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "corpora/aes/docs/public_aes/somerset_main_power_transformer_spec_sheet.pdf"
OUT = ROOT / "corpora/aes/docs/public_aes/somerset_main_power_transformer_spec_sheet_synth_rev.pdf"

REPLACEMENTS = [
    ("84/112/140 MVA", "84/112/120 MVA"),
    ("10% (+/- allowed tolerance)", "8% (+/- allowed tolerance)"),
]


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source PDF: {SRC}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(SRC)
    try:
        for needle, replacement in REPLACEMENTS:
            hits = _replace_all(doc, needle, replacement)
            if hits != 1:
                raise SystemExit(f"Expected exactly one hit for {needle!r}; found {hits}")
        _watermark(doc)
        doc.save(OUT, garbage=4, deflate=True)
    finally:
        doc.close()
    print(OUT)


def _replace_all(doc: fitz.Document, needle: str, replacement: str) -> int:
    hits = 0
    for page in doc:
        rects = page.search_for(needle)
        for rect in rects:
            hits += 1
            padded = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 18, rect.y1 + 3)
            page.add_redact_annot(padded, fill=(1, 1, 1))
            page.apply_redactions()
            page.insert_textbox(
                padded,
                replacement,
                fontsize=7.8,
                fontname="helv",
                color=(0, 0, 0),
                align=fitz.TEXT_ALIGN_LEFT,
            )
    return hits


def _watermark(doc: fitz.Document) -> None:
    text = "SYNTHETIC REVISION FOR INTERLOCK MVP DEMO - PLANTED VALUE CHANGES"
    for page_number in (0, 3, 4):
        if page_number >= doc.page_count:
            continue
        page = doc[page_number]
        rect = fitz.Rect(54, 24, page.rect.width - 54, 42)
        page.insert_textbox(
            rect,
            text,
            fontsize=7,
            fontname="helv",
            color=(0.65, 0, 0),
            align=fitz.TEXT_ALIGN_CENTER,
        )


if __name__ == "__main__":
    main()
