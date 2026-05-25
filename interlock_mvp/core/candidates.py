from __future__ import annotations

from collections import defaultdict

from .models import CandidateFinding, EvidenceItem
from .normalization import normalize_key
from .plausibility import values_equivalent
from .subjects import subject_key, subject_similarity


def generate_candidates(
    evidence: list[EvidenceItem],
    *,
    max_candidates: int,
    mode: str = "version",
) -> list[CandidateFinding]:
    by_id = {item.evidence_id: item for item in evidence}
    a_values = [item for item in evidence if item.doc_id == "A" and item.kind == "parameter_value"]
    b_values = [item for item in evidence if item.doc_id == "B" and item.kind == "parameter_value"]
    a_refs = [item for item in evidence if item.doc_id == "A" and item.kind == "reference"]
    b_refs = [item for item in evidence if item.doc_id == "B" and item.kind == "reference"]
    coverage = [item for item in evidence if item.kind == "coverage_warning"]
    a_equipment = [item for item in evidence if item.doc_id == "A" and item.kind == "equipment_id"]
    b_equipment = [item for item in evidence if item.doc_id == "B" and item.kind == "equipment_id"]

    candidates: list[CandidateFinding] = []
    seen: set[str] = set()

    b_by_key: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in b_values:
        b_by_key[subject_key(item.subject, item.parameter)].append(item)

    for item_a in a_values:
        if _is_generic_subject(item_a.subject):
            continue
        key = subject_key(item_a.subject, item_a.parameter)
        matches = _match_values(item_a, b_by_key.get(key, []), b_values, mode=mode)
        if not matches:
            if item_a.parameter not in {"rating", "impedance", "fault_current"}:
                continue
            _add_candidate(
                candidates,
                seen,
                CandidateFinding(
                    candidate_id=f"cand{len(candidates)+1:05d}",
                    candidate_key=_candidate_key("missing_item", item_a, None),
                    finding_type="missing_item",
                    subject=item_a.subject,
                    parameter=item_a.parameter,
                    evidence_a_id=item_a.evidence_id,
                    evidence_b_id=None,
                    generation_method="deterministic_missing_item",
                    deterministic_reason="A evidence has no subject/parameter match in B",
                    identity_strength="strong" if item_a.confidence == "high" else "medium",
                    deterministic_discrepancy=True,
                ),
            )
            continue
        equivalent_match = False
        mismatch_options: list[tuple[EvidenceItem, list[str], str | None]] = []
        for item_b in matches:
            equivalent, notes, forced_type = values_equivalent(
                item_a.value,
                item_a.unit,
                item_b.value,
                item_b.unit,
                a_context=item_a.raw_text,
                b_context=item_b.raw_text,
            )
            if equivalent:
                equivalent_match = True
                break
            mismatch_options.append((item_b, notes, forced_type))
        if equivalent_match or not mismatch_options:
            continue
        item_b, notes, forced_type = _best_mismatch_option(item_a, mismatch_options)
        finding_type = forced_type or "value_mismatch"
        _add_candidate(
            candidates,
            seen,
            CandidateFinding(
                candidate_id=f"cand{len(candidates)+1:05d}",
                candidate_key=_candidate_key(finding_type, item_a, item_b),
                finding_type=finding_type,
                subject=item_a.subject,
                parameter=item_a.parameter,
                evidence_a_id=item_a.evidence_id,
                evidence_b_id=item_b.evidence_id,
                generation_method="deterministic_value_compare",
                deterministic_reason=f"A value {item_a.value} {item_a.unit} differs from B value {item_b.value} {item_b.unit}",
                identity_strength=_identity_strength(item_a, item_b),
                deterministic_discrepancy=True,
                plausibility_notes=notes,
            ),
        )
        if len(candidates) >= max_candidates:
            return candidates

    b_ref_values = {normalize_key(item.value) for item in b_refs}
    for item_a in a_refs:
        if normalize_key(item_a.value) not in b_ref_values:
            _add_candidate(
                candidates,
                seen,
                CandidateFinding(
                    candidate_id=f"cand{len(candidates)+1:05d}",
                    candidate_key=_candidate_key("reference_conflict", item_a, None),
                    finding_type="reference_conflict",
                    subject=item_a.subject,
                    parameter="reference",
                    evidence_a_id=item_a.evidence_id,
                    generation_method="deterministic_reference_compare",
                    deterministic_reason="reference appears in A but not B",
                    identity_strength="medium",
                    deterministic_discrepancy=True,
                ),
            )

    if mode == "version":
        for item_a in a_equipment:
            if not _strong_missing_equipment_subject(item_a.subject):
                continue
            matches = [
                item_b
                for item_b in b_equipment
                if item_b.subject == item_a.subject and item_b.page == item_a.page
            ]
            if matches:
                continue
            _add_candidate(
                candidates,
                seen,
                CandidateFinding(
                    candidate_id=f"cand{len(candidates)+1:05d}",
                    candidate_key=f"missing_item|equipment|{normalize_key(item_a.subject)}|A:p{item_a.page}|B:missing",
                    finding_type="missing_item",
                    subject=item_a.subject,
                    parameter="equipment_presence",
                    evidence_a_id=item_a.evidence_id,
                    evidence_b_id=None,
                    generation_method="deterministic_page_local_equipment_missing",
                    deterministic_reason="strong equipment/device identifier appears in A but not the corresponding B context",
                    identity_strength="strong",
                    deterministic_discrepancy=True,
                ),
            )
            if len(candidates) >= max_candidates:
                return candidates

    for item in coverage:
        _add_candidate(
            candidates,
            seen,
            CandidateFinding(
                candidate_id=f"cand{len(candidates)+1:05d}",
                candidate_key=f"coverage_warning|{item.doc_id}|{item.page}|{item.value}",
                finding_type="coverage_warning",
                subject=item.subject,
                parameter="coverage",
                evidence_a_id=item.evidence_id if item.doc_id == "A" else None,
                evidence_b_id=item.evidence_id if item.doc_id == "B" else None,
                generation_method="deterministic_coverage",
                deterministic_reason=item.raw_text,
                identity_strength="strong",
                deterministic_discrepancy=True,
            ),
        )

    return candidates[:max_candidates]


def _add_candidate(candidates: list[CandidateFinding], seen: set[str], candidate: CandidateFinding) -> None:
    if candidate.candidate_key in seen:
        return
    seen.add(candidate.candidate_key)
    candidate.candidate_id = f"cand{len(candidates)+1:05d}"
    candidates.append(candidate)


def _candidate_key(kind: str, a: EvidenceItem, b: EvidenceItem | None) -> str:
    b_part = f"{b.doc_id}:{b.normalized_value}" if b else "missing"
    return "|".join(
        [
            kind,
            normalize_key(a.subject),
            normalize_key(a.parameter),
            f"{a.doc_id}:{a.normalized_value}",
            b_part,
        ]
    )


def _fuzzy_matches(item_a: EvidenceItem, b_values: list[EvidenceItem]) -> list[EvidenceItem]:
    matches: list[EvidenceItem] = []
    for item_b in b_values:
        if _is_generic_subject(item_b.subject):
            continue
        if item_a.parameter != item_b.parameter:
            continue
        if subject_similarity(item_a.subject, item_b.subject) >= 92:
            matches.append(item_b)
    return matches


def _match_values(
    item_a: EvidenceItem,
    exact_matches: list[EvidenceItem],
    b_values: list[EvidenceItem],
    *,
    mode: str,
) -> list[EvidenceItem]:
    pool = exact_matches or _fuzzy_matches(item_a, b_values)
    if mode == "version":
        same_page = [item for item in pool if item.page == item_a.page]
        if same_page:
            return same_page
        return []
    if pool:
        return pool
    return _cross_doc_semantic_matches(item_a, b_values)


def _identity_strength(a: EvidenceItem, b: EvidenceItem) -> str:
    if a.subject == b.subject and not _broad_equipment_subject(a.subject):
        return "strong"
    if subject_similarity(a.subject, b.subject) >= 92:
        return "medium"
    return "weak"


def _is_generic_subject(subject: str) -> bool:
    return subject.upper() in {"GENERAL"}


def _strong_missing_equipment_subject(subject: str) -> bool:
    if _is_generic_subject(subject):
        return False
    upper = subject.upper()
    if upper in {"XFMR", "FUSE", "BREAKER", "RELAY"}:
        return False
    return any(char.isdigit() for char in upper)


def _broad_equipment_subject(subject: str) -> bool:
    return subject.upper() in {"XFMR", "FUSE", "BREAKER", "RELAY", "GENERAL"}


def _best_mismatch_option(
    item_a: EvidenceItem,
    options: list[tuple[EvidenceItem, list[str], str | None]],
) -> tuple[EvidenceItem, list[str], str | None]:
    def score(option: tuple[EvidenceItem, list[str], str | None]) -> tuple[int, int, float]:
        item_b, notes, _forced = option
        has_decimal_note = any("decimal" in note or "magnitude" in note for note in notes)
        footnote_penalty = "footnote" in item_b.raw_text.lower()
        vertical_distance = abs(item_a.bbox[1] - item_b.bbox[1])
        return (1 if has_decimal_note else 0, 0 if footnote_penalty else 1, -vertical_distance)

    return sorted(options, key=score, reverse=True)[0]


def _cross_doc_semantic_matches(item_a: EvidenceItem, b_values: list[EvidenceItem]) -> list[EvidenceItem]:
    if "XFMR" not in item_a.subject.upper():
        return []
    matches: list[EvidenceItem] = []
    for item_b in b_values:
        if item_a.parameter == item_b.parameter and _is_transformer_context(item_b):
            matches.append(item_b)
        elif item_a.parameter == "primary_voltage" and item_b.parameter == "voltage" and item_b.unit.lower() == "kv":
            matches.append(item_b)
        elif item_a.parameter == "secondary_voltage" and item_b.parameter == "voltage" and item_b.unit.lower() == "v":
            matches.append(item_b)
        elif item_a.parameter == "rating" and item_b.parameter == "rating" and _is_transformer_context(item_b):
            matches.append(item_b)
        elif item_a.parameter == "impedance" and item_b.parameter == "impedance" and _is_transformer_context(item_b):
            matches.append(item_b)
    return matches


def _is_transformer_context(item: EvidenceItem) -> bool:
    return "XFMR" in item.subject.upper() or "XFMR" in item.raw_text.upper() or "TRANSFORMER" in item.raw_text.upper()


def evidence_lookup(evidence: list[EvidenceItem]) -> dict[str, EvidenceItem]:
    return {item.evidence_id: item for item in evidence}
