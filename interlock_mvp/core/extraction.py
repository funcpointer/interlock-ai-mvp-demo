from __future__ import annotations

from pathlib import Path

import fitz

from .artifacts import sha256_file
from .models import AnnotationRecord, DocumentRecord, PageRecord, RegionRecord


def extract_pdf(
    path: Path,
    *,
    doc_id: str,
    label: str,
    doc_type: str,
    mode_role: str,
    out_dir: Path,
) -> tuple[DocumentRecord, list[PageRecord], list[RegionRecord], list[AnnotationRecord], list[str]]:
    warnings: list[str] = []
    pages: list[PageRecord] = []
    regions: list[RegionRecord] = []
    annotations: list[AnnotationRecord] = []

    pdf = fitz.open(path)
    doc_record = DocumentRecord(
        doc_id=doc_id,
        label=label,
        path=str(path),
        sha256=sha256_file(path),
        page_count=pdf.page_count,
        doc_type=doc_type,
        mode_role=mode_role,
    )

    crops_dir = out_dir / "crops"
    for page_index, page in enumerate(pdf, start=1):
        page_id = f"{doc_id}_p{page_index}"
        rect = page.rect
        page_image_rel = f"crops/{page_id}_full.png"
        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(out_dir / page_image_rel)

        text = page.get_text("text") or ""
        text_count = len(text.strip())
        status = "ok" if text_count >= 30 else "low_text" if text_count else "empty"
        if status != "ok":
            warnings.append(f"{doc_id} page {page_index}: extraction status {status}")

        page_annotations = _extract_annotations(page, doc_id=doc_id, page_num=page_index)
        annotations.extend(page_annotations)

        blocks = page.get_text("blocks") or []
        block_num = 0
        for block in blocks:
            if len(block) < 5:
                continue
            x0, y0, x1, y1, block_text = block[:5]
            block_type = block[6] if len(block) > 6 else 0
            if block_type != 0 or not str(block_text).strip():
                continue
            bbox = [float(x0), float(y0), float(x1), float(y1)]
            block_num += 1
            region_id = f"{doc_id}_p{page_index}_r{block_num}"
            crop_rel = f"crops/{region_id}.png"
            _save_crop(page, bbox, crops_dir / f"{region_id}.png")
            region_annotation_ids = [
                annot.annotation_id
                for annot in page_annotations
                if _rects_overlap(bbox, annot.bbox)
            ]
            regions.append(
                RegionRecord(
                    region_id=region_id,
                    doc_id=doc_id,
                    page=page_index,
                    bbox=bbox,
                    text=str(block_text).strip(),
                    kind="text_block",
                    crop_path=crop_rel,
                    annotation_ids=region_annotation_ids,
                )
            )

        pages.append(
            PageRecord(
                page_id=page_id,
                doc_id=doc_id,
                page_num=page_index,
                width=float(rect.width),
                height=float(rect.height),
                text_char_count=text_count,
                extraction_status=status,
                page_image_path=page_image_rel,
            )
        )

    pdf.close()
    return doc_record, pages, regions, annotations, warnings


def _extract_annotations(page: fitz.Page, *, doc_id: str, page_num: int) -> list[AnnotationRecord]:
    records: list[AnnotationRecord] = []
    annot = page.first_annot
    idx = 0
    while annot is not None:
        idx += 1
        rect = annot.rect
        bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        info = dict(annot.info or {})
        annotation_type = annot.type[1] if annot.type else "unknown"
        highlighted_text = (page.get_textbox(rect) or "").strip()
        records.append(
            AnnotationRecord(
                annotation_id=f"{doc_id}_p{page_num}_a{idx}",
                doc_id=doc_id,
                page=page_num,
                bbox=bbox,
                annotation_type=annotation_type,
                annotation_comment=str(info.get("content") or ""),
                highlighted_text=highlighted_text,
                raw=info,
            )
        )
        annot = annot.next
    return records


def _save_crop(page: fitz.Page, bbox: list[float], path: Path) -> None:
    rect = fitz.Rect(*bbox) & page.rect
    if rect.is_empty or rect.width < 1 or rect.height < 1:
        rect = page.rect
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False)
    pix.save(path)


def _rects_overlap(a: list[float], b: list[float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return max(ax0, bx0) < min(ax1, bx1) and max(ay0, by0) < min(ay1, by1)
