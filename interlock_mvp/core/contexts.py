from __future__ import annotations

import re

from .models import RegionRecord
from .normalization import normalize_key

CONTEXT_PATTERNS = [
    (re.compile(r"\b(?:Time Current Curve\s*#?\s*(\d+)|TCC\s*#?\s*(\d+))\b", re.I), "tcc", "time_current_curve"),
    (re.compile(r"\bTransformer\s+Inrush\s+(\d+)\b", re.I), "transformer_inrush", "transformer_inrush"),
    (re.compile(r"\bTransformer\s+Damage\s+Curve\b", re.I), "transformer_damage_curve", "transformer_damage_curve"),
    (re.compile(r"\bSelective Coordination Stud(?:y|ies)\b", re.I), "selective_coordination_studies", "coordination_study"),
    (re.compile(r"\bEquipment Data Sheet\b", re.I), "equipment_data_sheet", "equipment_data_sheet"),
    (re.compile(r"\bNameplate Parameters\b", re.I), "nameplate_parameters", "nameplate_table"),
]
ROW_MARKER_RE = re.compile(r"^\s*(\d{1,3})\s+")


def context_label_for_region(region: RegionRecord, current_by_doc: dict[str, tuple[str, str, str, int]]) -> tuple[str, str, str, str]:
    text = region.text or ""
    row_match = ROW_MARKER_RE.match(text)
    if row_match and region.doc_id in current_by_doc:
        parent_id, parent_label, _parent_kind, _page = current_by_doc[region.doc_id]
        if not parent_label.startswith("document"):
            row_num = row_match.group(1)
            canonical = f"{parent_label}_row_{row_num}"
            return f"{region.doc_id}:{normalize_key(canonical)}", canonical, "table_row", row_match.group(0).strip()
    for pattern, prefix, kind in CONTEXT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        number = next((group for group in match.groups() if group), "")
        canonical = f"{prefix}{number}" if prefix == "tcc" and number else prefix
        if prefix == "transformer_inrush" and number:
            canonical = f"{prefix}_{number}"
        context_id = f"{region.doc_id}:{normalize_key(canonical)}"
        raw = match.group(0)
        current_by_doc[region.doc_id] = (context_id, canonical, kind, region.page)
        return context_id, canonical, kind, raw
    if region.doc_id in current_by_doc:
        context_id, canonical, kind, page = current_by_doc[region.doc_id]
        if page != region.page:
            context_id = f"{region.doc_id}:document_p{region.page}"
            current_by_doc[region.doc_id] = (context_id, f"document_p{region.page}", "document", region.page)
            return context_id, f"document_p{region.page}", "document", ""
        return context_id, canonical, kind, ""
    context_id = f"{region.doc_id}:document"
    current_by_doc[region.doc_id] = (context_id, "document", "document", region.page)
    return context_id, "document", "document", ""


def align_context_label(label: str) -> str:
    norm = normalize_key(label)
    tcc_match = re.search(r"tcc_?(\d+)|time_current_curve_?(\d+)", norm)
    if tcc_match:
        return f"tcc{next(group for group in tcc_match.groups() if group)}"
    if "equipment_data_sheet" in norm or "nameplate" in norm:
        return "equipment_data_sheet"
    if "selective_coordination" in norm:
        return "selective_coordination_studies"
    return norm or "document"


def align_context_label_strict(label: str) -> str:
    norm = normalize_key(label)
    row_match = re.search(r"(tcc_?\d+)_row_(\d+)", norm)
    if row_match:
        return f"{row_match.group(1).replace('_', '')}_row_{row_match.group(2)}"
    return align_context_label(label)
