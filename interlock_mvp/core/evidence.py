from __future__ import annotations

import re

from .domain import DomainDictionary
from .models import AnnotationRecord, EvidenceItem, PageRecord, RegionRecord
from .normalization import normalize_key, normalize_text
from .subjects import canonical_parameter, extract_subjects

VALUE_RE = re.compile(
    r"(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>%Z|kVA|MVA|kV|kA|V|A|%|ohm|Ω|uF|μF)(?=\b|[^A-Za-z0-9]|$)",
    flags=re.I,
)
REFERENCE_RE = re.compile(r"\b(?:IEEE|NEC|NFPA|ANSI|IEC|UL|NEMA)\s*[-A-Z0-9. ]{1,30}\b", flags=re.I)


def mine_evidence(
    *,
    pages: list[PageRecord],
    regions: list[RegionRecord],
    annotations: list[AnnotationRecord],
    domain: DomainDictionary | None = None,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    counter = 0

    for page in pages:
        if page.extraction_status != "ok":
            counter += 1
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev{counter:05d}",
                    doc_id=page.doc_id,
                    page=page.page_num,
                    bbox=[0.0, 0.0, page.width, page.height],
                    region_id=page.page_id,
                    kind="coverage_warning",
                    subject=f"{page.doc_id} page {page.page_num}",
                    parameter="coverage",
                    value=page.extraction_status,
                    unit="",
                    raw_text=f"Page text extraction status: {page.extraction_status}",
                    normalized_text=page.extraction_status,
                    normalized_value=page.extraction_status,
                    confidence="high",
                    source_method="pymupdf_page_text_count",
                    crop_path=page.page_image_path,
                )
            )

    for region in regions:
        raw = normalize_text(region.text)
        subjects = extract_subjects(raw, domain=domain)
        for subject in subjects:
            counter += 1
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev{counter:05d}",
                    doc_id=region.doc_id,
                    page=region.page,
                    bbox=region.bbox,
                    region_id=region.region_id,
                    kind="equipment_id",
                    subject=subject,
                    parameter="identity",
                    value=subject,
                    unit="",
                    raw_text=raw,
                    normalized_text=normalize_key(raw),
                    normalized_value=normalize_key(subject),
                    confidence="high",
                    source_method="regex_equipment_id",
                    crop_path=region.crop_path,
                )
            )

        primary_subject = subjects[0] if subjects else _fallback_subject(raw)
        for match in VALUE_RE.finditer(raw):
            unit = match.group("unit")
            value = match.group("value")
            parameter = canonical_parameter(raw, unit, domain=domain)
            counter += 1
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev{counter:05d}",
                    doc_id=region.doc_id,
                    page=region.page,
                    bbox=region.bbox,
                    region_id=region.region_id,
                    kind="parameter_value",
                    subject=primary_subject,
                    parameter=parameter,
                    value=value,
                    unit=unit,
                    raw_text=raw,
                    normalized_text=normalize_key(raw),
                    normalized_value=f"{value.replace(',', '')} {unit.lower()}",
                    confidence="high" if subjects else "medium",
                    source_method="regex_value_unit",
                    crop_path=region.crop_path,
                )
            )

        for match in REFERENCE_RE.finditer(raw):
            ref = normalize_text(match.group(0))
            counter += 1
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev{counter:05d}",
                    doc_id=region.doc_id,
                    page=region.page,
                    bbox=region.bbox,
                    region_id=region.region_id,
                    kind="reference",
                    subject=ref.upper(),
                    parameter="reference",
                    value=ref,
                    unit="",
                    raw_text=raw,
                    normalized_text=normalize_key(raw),
                    normalized_value=normalize_key(ref),
                    confidence="medium",
                    source_method="regex_reference",
                    crop_path=region.crop_path,
                )
            )

    for annotation in annotations:
        if not (annotation.annotation_comment or annotation.highlighted_text):
            continue
        counter += 1
        text = normalize_text(" ".join([annotation.highlighted_text, annotation.annotation_comment]).strip())
        evidence.append(
            EvidenceItem(
                evidence_id=f"ev{counter:05d}",
                doc_id=annotation.doc_id,
                page=annotation.page,
                bbox=annotation.bbox,
                region_id=annotation.annotation_id,
                kind="annotation",
                subject=_fallback_subject(text) or f"{annotation.doc_id} page {annotation.page}",
                parameter="annotation",
                value=annotation.annotation_type,
                unit="",
                raw_text=text,
                normalized_text=normalize_key(text),
                normalized_value=normalize_key(annotation.annotation_type),
                confidence="medium",
                source_method="pymupdf_annotation",
                crop_path="",
            )
        )

    return _attach_neighbor_context(evidence)


def _fallback_subject(text: str) -> str:
    lowered = text.lower()
    if "transformer" in lowered or "xfmr" in lowered:
        return "XFMR"
    if "fuse" in lowered:
        return "FUSE"
    if "breaker" in lowered:
        return "BREAKER"
    if "relay" in lowered:
        return "RELAY"
    return "GENERAL"


def _attach_neighbor_context(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    equipment_by_region = {
        item.region_id: item
        for item in evidence
        if item.subject not in {"GENERAL"} and item.kind in {"equipment_id", "parameter_value"}
    }
    equipment_by_page = [
        item
        for item in evidence
        if item.subject not in {"GENERAL"} and item.kind in {"equipment_id", "parameter_value"}
    ]
    updated: list[EvidenceItem] = []
    for item in evidence:
        if item.kind != "parameter_value" or item.subject != "GENERAL":
            updated.append(item)
            continue
        neighbor = equipment_by_region.get(item.region_id) or _nearest_prior_equipment(item, equipment_by_page)
        if not neighbor:
            updated.append(item)
            continue
        parameter = item.parameter
        if "fault" in neighbor.raw_text.lower() or "fault" in item.raw_text.lower():
            parameter = "fault_current"
        updated.append(
            item.model_copy(
                update={
                    "subject": neighbor.subject,
                    "parameter": parameter,
                    "confidence": "medium",
                    "source_method": f"{item.source_method}+neighbor_context",
                    "raw_text": f"{neighbor.raw_text} {item.raw_text}" if neighbor.region_id != item.region_id else item.raw_text,
                    "normalized_text": normalize_key(f"{neighbor.raw_text} {item.raw_text}"),
                }
            )
        )
    return updated


def _nearest_prior_equipment(item: EvidenceItem, equipment: list[EvidenceItem]) -> EvidenceItem | None:
    candidates = [
        candidate
        for candidate in equipment
        if candidate.doc_id == item.doc_id
        and candidate.page == item.page
        and candidate.bbox[1] <= item.bbox[1] + 8
        and abs(candidate.bbox[1] - item.bbox[1]) <= 140
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: (abs(candidate.bbox[1] - item.bbox[1]), candidate.bbox[0]))[0]
