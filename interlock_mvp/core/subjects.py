from __future__ import annotations

import re

from rapidfuzz import fuzz

from .domain import DomainDictionary
from .normalization import normalize_subject

EQUIPMENT_PATTERNS = [
    re.compile(r"\b(?:XFMR|TX)\s*[-#]\s*\d+[A-Z]?\b", re.I),
    re.compile(r"\bT\s*-?\s*\d+[A-Z]?\b", re.I),
    re.compile(r"\bTRANSFORMER\s*#?\s*\d+[A-Z]?\b", re.I),
    re.compile(r"\b(?:LPN|LPS|KRP|JCN|FRN|LPJ)[-A-Z0-9]*\d+[A-Z]*\b", re.I),
    re.compile(r"\b[A-Z]{2,6}-[A-Z]{1,4}-\d{2,5}[A-Z]*\b"),
    re.compile(r"\b(?:RELAY|BREAKER|FUSE|FEEDER|BUS|MCC|SWBD|PANEL)\s*[-# ]?\s*[A-Z0-9]+\b", re.I),
]


def extract_subjects(text: str, domain: DomainDictionary | None = None) -> list[str]:
    found: list[str] = []
    patterns = [*EQUIPMENT_PATTERNS, *(domain.subject_patterns() if domain else [])]
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            subject = normalize_subject(match.group(0))
            if subject and subject not in found:
                found.append(subject)
    return found


def canonical_parameter(text: str, unit: str, domain: DomainDictionary | None = None) -> str:
    lower = text.lower()
    unit_lower = unit.lower()
    if domain:
        domain_parameter = domain.parameter_for(text, unit)
        if domain_parameter:
            return domain_parameter
    if "bil" in lower:
        return "bil"
    if "primary voltage" in lower:
        return "primary_voltage"
    if "secondary voltage" in lower:
        return "secondary_voltage"
    if unit_lower in {"kva", "mva"}:
        return "rating"
    if unit_lower in {"kv", "v"}:
        return "voltage"
    if "fault" in lower and unit_lower in {"a", "ka"}:
        return "fault_current"
    if "short circuit" in lower and unit_lower in {"a", "ka"}:
        return "fault_current"
    if unit_lower in {"ka", "a"}:
        return "current"
    if unit_lower in {"%", "%z"}:
        return "impedance" if "z" in lower or "impedance" in lower else "percent"
    return "parameter"


def subject_similarity(a: str, b: str) -> int:
    return int(fuzz.token_set_ratio(normalize_subject(a), normalize_subject(b)))


def subject_key(subject: str, parameter: str) -> str:
    subject_norm = normalize_subject(subject)
    return f"{subject_norm}|{parameter}".lower()
