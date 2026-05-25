from __future__ import annotations

from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "corpora/aes/docs/public_aes/somerset_main_power_transformer_spec_sheet.pdf"
OUT = ROOT / "corpora/aes/docs/public_aes/somerset_transformer_protection_study_excerpt_synth.pdf"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source PDF used as demo anchor: {SRC}")
    OUT.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    try:
        page = doc.new_page(width=612, height=792)
        _write_page(page)
        doc.save(OUT, garbage=4, deflate=True)
    finally:
        doc.close()
    print(OUT)


def _write_page(page: fitz.Page) -> None:
    y = 54
    page.insert_text(
        (72, y),
        "SYNTHETIC PROTECTION STUDY EXCERPT FOR INTERLOCK MVP DEMO",
        fontsize=10,
        fontname="helv",
        color=(0.65, 0, 0),
    )
    y += 34
    page.insert_text((72, y), "Selective Coordination Studies", fontsize=14, fontname="helv")
    y += 26
    page.insert_text((72, y), "Transformer Source Equipment", fontsize=12, fontname="helv")
    y += 24
    page.insert_text(
        (90, y),
        "Main Power Transformer Rating: 120 MVA",
        fontsize=11,
        fontname="helv",
    )
    y += 20
    page.insert_text(
        (90, y),
        "Main Power Transformer Impedance: 8%",
        fontsize=11,
        fontname="helv",
    )
    y += 32
    page.insert_text(
        (72, y),
        "Study note: values are synthetic and intentionally conflict with the public AES specification sheet.",
        fontsize=9,
        fontname="helv",
        color=(0.25, 0.25, 0.25),
    )
    y += 18
    page.insert_text(
        (72, y),
        "Source basis: public AES Somerset transformer specification sheet; this excerpt is not a real AES study.",
        fontsize=9,
        fontname="helv",
        color=(0.25, 0.25, 0.25),
    )


if __name__ == "__main__":
    main()
