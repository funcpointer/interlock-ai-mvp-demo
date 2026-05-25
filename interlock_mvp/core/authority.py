from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import AuthorityDecision

DOC_TYPE_PATTERNS = {
    "protection_study": re.compile(r"\b(protection|coordination|relay|fault|short.?circuit|study|sel)\b", re.I),
    "drawing": re.compile(r"\b(drawing|one.?line|single.?line|schematic|p&id|pid|plan|civil)\b", re.I),
    "specification": re.compile(r"\b(spec|specification|datasheet|guide|standard)\b", re.I),
    "checklist": re.compile(r"\b(checklist|review.?list|qa|qc)\b", re.I),
}


def load_authority_config(path: Path | None) -> dict[str, Any]:
    if path and path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "version": {"authoritative_side": "B", "basis": "revised document supersedes baseline"},
        "cross_doc": {
            "precedence": ["protection_study", "drawing", "specification", "checklist"],
            "fallback": "unknown_direction",
        },
    }


def classify_doc_type(path: Path, text_sample: str, override: str | None) -> tuple[str, float, dict[str, str]]:
    if override and override != "auto":
        return override, 1.0, {"method": "cli_override", "value": override}
    filename = path.name.replace("_", " ").replace("-", " ")
    filename_type = _match_type(filename)
    content_type = _match_type(text_sample[:4000])
    if filename_type and content_type and filename_type == content_type:
        return filename_type, 0.9, {"method": "filename_and_content", "filename": filename_type, "content": content_type}
    if content_type:
        return content_type, 0.7, {"method": "content", "content": content_type}
    if filename_type:
        return filename_type, 0.6, {"method": "filename", "filename": filename_type}
    return "unknown", 0.3, {"method": "unknown"}


def resolve_authority(
    *,
    mode: str,
    config: dict[str, Any],
    doc_a_type: str,
    doc_b_type: str,
    doc_a_confidence: float,
    doc_b_confidence: float,
) -> AuthorityDecision:
    warnings: list[str] = []
    if mode == "version":
        version_cfg = config.get("version", {})
        authoritative_side = version_cfg.get("authoritative_side", "B")
        basis = version_cfg.get("basis", "revised document supersedes baseline")
        confidence = 1.0 if authoritative_side in {"A", "B"} else 0.3
        return AuthorityDecision(
            authoritative_side=authoritative_side,
            basis=basis,
            confidence=confidence,
            doc_a_type=doc_a_type,
            doc_b_type=doc_b_type,
            doc_a_type_confidence=doc_a_confidence,
            doc_b_type_confidence=doc_b_confidence,
            warnings=warnings,
        )

    precedence = config.get("cross_doc", {}).get("precedence", [])
    fallback = config.get("cross_doc", {}).get("fallback", "unknown_direction")
    side = "unknown"
    basis = "Documents disagree; authoritative source not determined."
    confidence = 0.3
    if doc_a_type in precedence and doc_b_type in precedence and doc_a_type != doc_b_type:
        side = "A" if precedence.index(doc_a_type) < precedence.index(doc_b_type) else "B"
        basis = f"{doc_a_type if side == 'A' else doc_b_type} ranks higher in configured AES precedence"
        confidence = min(doc_a_confidence, doc_b_confidence)
    elif doc_a_type == doc_b_type and doc_a_type != "unknown":
        warnings.append("documents have same authority class")
        side = fallback
    else:
        warnings.append("unknown authority direction")
        side = fallback
    return AuthorityDecision(
        authoritative_side=side,
        basis=basis,
        confidence=confidence,
        doc_a_type=doc_a_type,
        doc_b_type=doc_b_type,
        doc_a_type_confidence=doc_a_confidence,
        doc_b_type_confidence=doc_b_confidence,
        warnings=warnings,
    )


def version_order_warning(path_a: Path, path_b: Path) -> str | None:
    rev_a = _revision_marker(path_a.name)
    rev_b = _revision_marker(path_b.name)
    if rev_a is not None and rev_b is not None and rev_b < rev_a:
        return f"version mode received B that appears older than A: A={rev_a}, B={rev_b}"
    return None


def _match_type(text: str) -> str | None:
    for doc_type, pattern in DOC_TYPE_PATTERNS.items():
        if pattern.search(text or ""):
            return doc_type
    return None


def _revision_marker(name: str) -> float | None:
    matches = re.findall(r"\b(?:rev|v|r)?\s*(\d+(?:\.\d+)?)\b", name, flags=re.I)
    return float(matches[-1]) if matches else None
