from __future__ import annotations

from collections import defaultdict
import re

from .contexts import align_context_label, align_context_label_strict, context_label_for_region
from .domain import DomainDictionary
from .models import ClaimNode, ContextNode, DiffEdge, DiffGraph, DocumentGraph, EvidenceItem, RegionRecord, SubjectNode
from .normalization import normalize_key
from .plausibility import values_equivalent
from .subjects import subject_similarity


def build_document_graphs(
    *,
    regions: list[RegionRecord],
    evidence: list[EvidenceItem],
    domain: DomainDictionary | None = None,
) -> tuple[DocumentGraph, DocumentGraph, list[EvidenceItem]]:
    context_by_region: dict[str, tuple[str, str, str, str]] = {}
    current_by_doc: dict[str, tuple[str, str, str, int]] = {}
    for region in sorted(regions, key=lambda r: (r.doc_id, r.page, r.bbox[1], r.bbox[0])):
        context_by_region[region.region_id] = context_label_for_region(region, current_by_doc, domain=domain)

    updated_evidence: list[EvidenceItem] = []
    for item in evidence:
        context_id, label, _kind, _raw = context_by_region.get(
            item.region_id,
            (f"{item.doc_id}:document", "document", "document", ""),
        )
        confidence = "high" if label != "document" else "low"
        updated_evidence.append(
            item.model_copy(
                update={
                    "context_id": context_id,
                    "context_confidence": confidence,
                    **_contextual_claim_updates(item, label),
                }
            )
        )
    updated_evidence = _attach_main_equipment_subjects(regions, updated_evidence, context_by_region)

    return (
        _build_graph_for_doc("A", regions, updated_evidence, context_by_region),
        _build_graph_for_doc("B", regions, updated_evidence, context_by_region),
        updated_evidence,
    )


def _contextual_claim_updates(item: EvidenceItem, context_label: str) -> dict[str, str]:
    if item.kind != "parameter_value":
        return {}
    aligned = align_context_label(context_label)
    if item.parameter == "percent" and aligned == "impedance_information":
        return {"parameter": "impedance", "source_method": f"{item.source_method}+context_parameter"}
    return {}


def _attach_main_equipment_subjects(
    regions: list[RegionRecord],
    evidence: list[EvidenceItem],
    context_by_region: dict[str, tuple[str, str, str, str]],
) -> list[EvidenceItem]:
    main_subject_by_doc = _main_equipment_subject_by_doc(regions)
    if not main_subject_by_doc:
        return evidence
    updated: list[EvidenceItem] = []
    for item in evidence:
        main_subject = main_subject_by_doc.get(item.doc_id)
        if not main_subject or item.kind != "parameter_value" or item.subject != "GENERAL":
            updated.append(item)
            continue
        _context_id, context_label, context_kind, _raw = context_by_region.get(
            item.region_id,
            (item.context_id, "document", "document", ""),
        )
        if not _is_main_equipment_context(context_label, context_kind):
            updated.append(item)
            continue
        updated.append(
            item.model_copy(
                update={
                    "subject": main_subject,
                    "confidence": "medium",
                    "source_method": f"{item.source_method}+main_equipment_context",
                }
            )
        )
    return updated


def _main_equipment_subject_by_doc(regions: list[RegionRecord]) -> dict[str, str]:
    text_by_doc: dict[str, list[str]] = defaultdict(list)
    for region in sorted(regions, key=lambda r: (r.doc_id, r.page, r.bbox[1], r.bbox[0])):
        if region.page <= 5:
            text_by_doc[region.doc_id].append(region.text)
    result: dict[str, str] = {}
    for doc_id, chunks in text_by_doc.items():
        text = " ".join(chunks).lower()
        if "transformer" not in text:
            continue
        if re.search(r"\b(main\s+power\s+transformer|power\s+transformers?)\b", text) and any(
            marker in text for marker in ("specification sheet", "datasheet", "technical datasheet", "specified data")
        ):
            result[doc_id] = "XFMR"
    return result


def _is_main_equipment_context(context_label: str, context_kind: str) -> bool:
    aligned = align_context_label(context_label)
    return context_kind in {"equipment_data_sheet", "nameplate_table", "rating_table", "impedance_table"} or aligned in {
        "equipment_data_sheet",
        "transformer_electrical_ratings",
        "capacity_ratings",
        "voltage_ratings",
        "impedance_information",
    }


def build_diff_graph(graph_a: DocumentGraph, graph_b: DocumentGraph) -> DiffGraph:
    edges: list[DiffEdge] = []
    b_claims = graph_b.claims
    b_context_labels = {context.context_id: align_context_label(context.canonical_label) for context in graph_b.contexts}

    for claim_a in graph_a.claims:
        if _is_generic_subject_id(claim_a.subject_id):
            continue
        if not _claim_admissible_for_diff(claim_a):
            continue
        context_a = align_context_label(_context_label(graph_a, claim_a.context_id))
        matches = [
            claim_b
            for claim_b in b_claims
            if _parameters_align(claim_a.parameter, claim_b.parameter)
            and _subjects_align(claim_a.subject_id, claim_b.subject_id, mode="strict")
            and b_context_labels.get(claim_b.context_id, "document") == context_a
        ]
        if not matches and context_a != "document":
            matches = [
                claim_b
                for claim_b in b_claims
                if _parameters_align(claim_a.parameter, claim_b.parameter)
                and _subjects_align(claim_a.subject_id, claim_b.subject_id, mode="semantic")
                and b_context_labels.get(claim_b.context_id, "document") == context_a
            ]
        if not matches and _is_spec_context(context_a):
            matches = [
                claim_b
                for claim_b in b_claims
                if _parameters_align(claim_a.parameter, claim_b.parameter, cross_doc_spec=True)
                and _cross_doc_spec_subjects_compatible(claim_a, claim_b)
            ]
        if not matches:
            if claim_a.parameter in {"rating", "impedance", "fault_current"}:
                edges.append(
                    DiffEdge(
                        diff_id=f"diff{len(edges)+1:05d}",
                        diff_type="missing_item",
                        a_node_id=claim_a.claim_id,
                        alignment_status="unmatched_a",
                        subject=_subject_label(claim_a.subject_id),
                        parameter=claim_a.parameter,
                        rationale="A claim has no aligned B claim in the same canonical context.",
                        evidence_ids=claim_a.evidence_ids,
                        identity_strength="medium",
                        deterministic_discrepancy=True,
                    )
                )
            continue
        equivalent, notes, forced_type, best_b = _compare_against_matches(claim_a, matches)
        if equivalent:
            continue
        edges.append(
            DiffEdge(
                diff_id=f"diff{len(edges)+1:05d}",
                diff_type=forced_type or "value_mismatch",
                a_node_id=claim_a.claim_id,
                b_node_id=best_b.claim_id,
                alignment_status="conflict" if not forced_type else "needs_review",
                subject=_subject_label(claim_a.subject_id),
                parameter=claim_a.parameter,
                rationale=f"A claim {claim_a.value} {claim_a.unit} differs from B claim {best_b.value} {best_b.unit}.",
                evidence_ids=claim_a.evidence_ids + best_b.evidence_ids,
                plausibility_notes=notes,
                identity_strength="strong" if _subjects_align(claim_a.subject_id, best_b.subject_id, mode="strict") else "medium",
                deterministic_discrepancy=True,
            )
        )

    for subject_a in graph_a.subjects:
        if not _strong_missing_subject(subject_a.canonical_label):
            continue
        for context_id in subject_a.context_ids:
            context_label = align_context_label_strict(_context_label(graph_a, context_id))
            if context_label == "document":
                continue
            has_b = any(
                _subjects_align(subject_a.subject_id, subject_b.subject_id, mode="strict")
                and any(_contexts_align(context_label, align_context_label_strict(_context_label(graph_b, ctx))) for ctx in subject_b.context_ids)
                for subject_b in graph_b.subjects
            )
            if not has_b:
                edges.append(
                    DiffEdge(
                        diff_id=f"diff{len(edges)+1:05d}",
                        diff_type="missing_item",
                        a_node_id=subject_a.subject_id,
                        alignment_status="unmatched_a",
                        subject=subject_a.canonical_label,
                        parameter="equipment_presence",
                        rationale="A subject appears in an aligned context and no matching B subject was found in that context.",
                        evidence_ids=subject_a.evidence_ids,
                        identity_strength="strong",
                        deterministic_discrepancy=True,
                    )
                )
    return DiffGraph(edges=_dedup_edges(edges))


def _build_graph_for_doc(
    doc_id: str,
    regions: list[RegionRecord],
    evidence: list[EvidenceItem],
    context_by_region: dict[str, tuple[str, str, str, str]],
) -> DocumentGraph:
    doc_regions = [region for region in regions if region.doc_id == doc_id]
    doc_evidence = [item for item in evidence if item.doc_id == doc_id]
    contexts_by_id: dict[str, ContextNode] = {}
    region_ids_by_context: dict[str, list[str]] = defaultdict(list)
    pages_by_context: dict[str, set[int]] = defaultdict(set)
    raw_by_context: dict[str, set[str]] = defaultdict(set)

    for region in doc_regions:
        context_id, label, kind, raw = context_by_region.get(region.region_id, (f"{doc_id}:document", "document", "document", ""))
        region_ids_by_context[context_id].append(region.region_id)
        pages_by_context[context_id].add(region.page)
        if raw:
            raw_by_context[context_id].add(raw)
        contexts_by_id[context_id] = ContextNode(
            context_id=context_id,
            doc_id=doc_id,
            canonical_label=label,
            raw_labels=sorted(raw_by_context[context_id]),
            kind=kind,
            page_span=sorted(pages_by_context[context_id]),
            region_ids=region_ids_by_context[context_id],
            confidence="high" if label != "document" else "low",
        )

    subject_evidence: dict[str, list[EvidenceItem]] = defaultdict(list)
    subject_contexts: dict[str, set[str]] = defaultdict(set)
    claims: list[ClaimNode] = []
    for item in doc_evidence:
        if item.kind not in {"equipment_id", "parameter_value"}:
            continue
        subject_label = item.subject
        subject_id = f"{doc_id}:subject:{normalize_key(subject_label)}"
        subject_evidence[subject_id].append(item)
        subject_contexts[subject_id].add(item.context_id or f"{doc_id}:document")
        if item.kind == "parameter_value":
            claims.append(
                ClaimNode(
                    claim_id=f"{doc_id}:claim:{item.evidence_id}",
                    doc_id=doc_id,
                    context_id=item.context_id or f"{doc_id}:document",
                    subject_id=subject_id,
                    parameter=item.parameter,
                    value=item.value,
                    unit=item.unit,
                    raw_text=item.raw_text,
                    evidence_ids=[item.evidence_id],
                    confidence=item.confidence,
                )
            )

    subjects = [
        SubjectNode(
            subject_id=subject_id,
            doc_id=doc_id,
            canonical_label=items[0].subject,
            raw_labels=sorted({item.subject for item in items}),
            kind=_subject_kind(items[0].subject),
            context_ids=sorted(subject_contexts[subject_id]),
            evidence_ids=[item.evidence_id for item in items],
            confidence="high" if items[0].subject not in {"GENERAL", "XFMR"} else "medium",
        )
        for subject_id, items in sorted(subject_evidence.items())
    ]
    return DocumentGraph(doc_id=doc_id, contexts=list(contexts_by_id.values()), subjects=subjects, claims=claims)


def _compare_against_matches(claim_a: ClaimNode, matches: list[ClaimNode]) -> tuple[bool, list[str], str | None, ClaimNode]:
    mismatch_options: list[tuple[ClaimNode, list[str], str | None]] = []
    for claim_b in matches:
        equivalent, notes, forced_type = values_equivalent(
            claim_a.value,
            claim_a.unit,
            claim_b.value,
            claim_b.unit,
            a_context=claim_a.raw_text,
            b_context=claim_b.raw_text,
        )
        if equivalent:
            return True, notes, None, claim_b
        mismatch_options.append((claim_b, notes, forced_type))
    best = sorted(
        mismatch_options,
        key=lambda option: (
            any("decimal" in note or "magnitude" in note for note in option[1]),
            "footnote" not in option[0].raw_text.lower(),
        ),
        reverse=True,
    )[0]
    return False, best[1], best[2], best[0]


def _context_label(graph: DocumentGraph, context_id: str) -> str:
    for context in graph.contexts:
        if context.context_id == context_id:
            return context.canonical_label
    return "document"


def _parameters_align(a: str, b: str, *, cross_doc_spec: bool = False) -> bool:
    if a == b:
        return True
    if cross_doc_spec and a == "primary_voltage" and b == "rating":
        return False
    return False


def _contexts_align(a: str, b: str) -> bool:
    if a == b:
        return True
    if "_row_" in a or "_row_" in b:
        return False
    return False


def _subjects_align(a_id: str, b_id: str, *, mode: str) -> bool:
    a = _subject_label(a_id)
    b = _subject_label(b_id)
    if a == b:
        return True
    if mode == "semantic" and "XFMR" in a.upper() and ("XFMR" in b.upper() or "TRANSFORMER" in b.upper()):
        return True
    return subject_similarity(a, b) >= (95 if mode == "strict" else 88)


def _cross_doc_spec_subjects_compatible(claim_a: ClaimNode, claim_b: ClaimNode) -> bool:
    if _subjects_align(claim_a.subject_id, claim_b.subject_id, mode="semantic"):
        return True
    return _is_transformer_subject(claim_a.subject_id) and _is_transformer_claim(claim_b)


def _subject_label(subject_id: str) -> str:
    return subject_id.split(":subject:", 1)[-1].replace("_", "-").upper()


def _is_generic_subject_id(subject_id: str) -> bool:
    return _subject_label(subject_id) == "GENERAL"


def _is_spec_context(context_label: str) -> bool:
    return context_label in {"equipment_data_sheet", "nameplate_parameters"}


def _is_transformer_claim(claim: ClaimNode) -> bool:
    label = _subject_label(claim.subject_id)
    raw = claim.raw_text.upper()
    return (
        "XFMR" in label
        or "XFMR" in raw
        or "TRANSFORMER" in raw
        or "%Z" in raw
        or "IMPEDANCE" in raw
        or "∆-Y" in raw
        or "DELTA" in raw
    )


def _is_transformer_subject(subject_id: str) -> bool:
    label = _subject_label(subject_id)
    return "XFMR" in label or "TRANSFORMER" in label


def _claim_admissible_for_diff(claim: ClaimNode) -> bool:
    raw = claim.raw_text.lower()
    if claim.parameter == "impedance":
        if "impedance" in claim.context_id.lower():
            return True
        if claim.unit.lower() == "%z":
            return True
        return any(token in raw for token in ("%z", "impedance", "z%"))
    if claim.parameter == "rating":
        return claim.unit.lower() in {"kva", "mva"}
    if claim.parameter == "fault_current":
        return "fault" in raw or "short circuit" in raw
    return True


def _strong_missing_subject(subject: str) -> bool:
    upper = subject.upper()
    if upper in {"GENERAL", "XFMR", "FUSE", "BREAKER", "RELAY"}:
        return False
    return any(char.isdigit() for char in upper)


def _subject_kind(subject: str) -> str:
    upper = subject.upper()
    if "XFMR" in upper:
        return "transformer"
    if any(token in upper for token in ("LPN", "LPS", "KRP", "FUSE")):
        return "protective_device"
    if "BREAKER" in upper:
        return "breaker"
    return "equipment"


def _dedup_edges(edges: list[DiffEdge]) -> list[DiffEdge]:
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    result: list[DiffEdge] = []
    for edge in edges:
        key = _edge_dedup_key(edge)
        if key in seen:
            continue
        seen.add(key)
        edge.diff_id = f"diff{len(result)+1:05d}"
        result.append(edge)
    return result


def _edge_dedup_key(edge: DiffEdge) -> tuple[str, str, str, str | None, str | None]:
    if edge.diff_type == "value_mismatch" and edge.parameter in {"rating", "impedance", "fault_current"}:
        return (edge.diff_type, edge.subject, edge.parameter, _value_rationale_key(edge.rationale), None)
    if edge.diff_type == "missing_item" and edge.parameter in {"rating", "impedance", "fault_current"}:
        return (edge.diff_type, edge.subject, edge.parameter, edge.rationale, None)
    return (edge.diff_type, edge.subject, edge.parameter, edge.a_node_id, edge.b_node_id)


def _value_rationale_key(rationale: str) -> str:
    return " ".join(rationale.lower().split())
