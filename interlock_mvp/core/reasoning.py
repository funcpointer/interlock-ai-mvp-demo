from __future__ import annotations

from .contexts import align_context_label
from .models import (
    AbsenceSearch,
    AlignmentDecision,
    ClaimNode,
    ComparisonDecision,
    DiffEdge,
    DiffGraph,
    DocumentGraph,
    ReasoningGraph,
    SubjectNode,
)
from .normalization import normalize_key


def build_reasoning_graph(diff_graph: DiffGraph, graph_a: DocumentGraph, graph_b: DocumentGraph) -> ReasoningGraph:
    claim_by_id = {claim.claim_id: claim for claim in [*graph_a.claims, *graph_b.claims]}
    subject_by_id = {subject.subject_id: subject for subject in [*graph_a.subjects, *graph_b.subjects]}
    context_by_id = {context.context_id: context for context in [*graph_a.contexts, *graph_b.contexts]}

    alignments: list[AlignmentDecision] = []
    comparisons: list[ComparisonDecision] = []
    absence_searches: list[AbsenceSearch] = []

    for edge in diff_graph.edges:
        if edge.diff_type in {"value_mismatch", "needs_engineer_review"} and edge.a_node_id and edge.b_node_id:
            claim_a = claim_by_id.get(edge.a_node_id)
            claim_b = claim_by_id.get(edge.b_node_id)
            if not claim_a or not claim_b:
                continue
            alignment = _alignment_decision(
                edge=edge,
                claim_a=claim_a,
                claim_b=claim_b,
                graph_b=graph_b,
                context_by_id=context_by_id,
                index=len(alignments) + 1,
            )
            alignments.append(alignment)
            comparisons.append(_comparison_decision(edge=edge, alignment_id=alignment.alignment_id, index=len(comparisons) + 1))
            continue

        if edge.diff_type == "missing_item":
            absence_searches.append(
                _absence_search(
                    edge=edge,
                    claim_by_id=claim_by_id,
                    subject_by_id=subject_by_id,
                    graph_b=graph_b,
                    index=len(absence_searches) + 1,
                )
            )

    return ReasoningGraph(alignments=alignments, comparisons=comparisons, absence_searches=absence_searches)


def _alignment_decision(
    *,
    edge: DiffEdge,
    claim_a: ClaimNode,
    claim_b: ClaimNode,
    graph_b: DocumentGraph,
    context_by_id: dict[str, object],
    index: int,
) -> AlignmentDecision:
    rejected = [
        claim.claim_id
        for claim in graph_b.claims
        if claim.claim_id != claim_b.claim_id and claim.parameter == claim_a.parameter
    ]
    return AlignmentDecision(
        alignment_id=f"align{index:05d}",
        diff_id=edge.diff_id,
        a_claim_id=claim_a.claim_id,
        b_claim_id=claim_b.claim_id,
        subject_method=_subject_method(claim_a.subject_id, claim_b.subject_id, edge.identity_strength),
        parameter_method="exact" if claim_a.parameter == claim_b.parameter else "normalized",
        context_method=_context_method(claim_a.context_id, claim_b.context_id, context_by_id),
        confidence=_confidence(edge.identity_strength),
        accepted=True,
        rationale=edge.rationale,
        rejected_b_claim_ids=rejected,
    )


def _comparison_decision(*, edge: DiffEdge, alignment_id: str, index: int) -> ComparisonDecision:
    return ComparisonDecision(
        comparison_id=f"comp{index:05d}",
        diff_id=edge.diff_id,
        alignment_id=alignment_id,
        comparison_type=edge.diff_type,
        unit_method=_unit_method(edge),
        plausibility_notes=edge.plausibility_notes,
        deterministic=edge.deterministic_discrepancy,
        verifier_status="not_run",
        rationale=edge.rationale,
    )


def _absence_search(
    *,
    edge: DiffEdge,
    claim_by_id: dict[str, ClaimNode],
    subject_by_id: dict[str, SubjectNode],
    graph_b: DocumentGraph,
    index: int,
) -> AbsenceSearch:
    a_claim = claim_by_id.get(edge.a_node_id or "")
    a_subject = subject_by_id.get(edge.a_node_id or "")
    searched_context_ids = [a_claim.context_id] if a_claim else list(a_subject.context_ids if a_subject else [])
    candidates = _absence_candidates(edge, graph_b)
    return AbsenceSearch(
        absence_id=f"abs{index:05d}",
        diff_id=edge.diff_id,
        a_subject_id=a_subject.subject_id if a_subject else (a_claim.subject_id if a_claim else None),
        a_claim_id=a_claim.claim_id if a_claim else None,
        searched_doc_id="B",
        searched_context_ids=searched_context_ids,
        searched_parameters=[edge.parameter],
        query_terms=_query_terms(edge),
        candidate_ids_considered=candidates,
        rejected_candidate_ids=candidates,
        coverage_status="searched" if searched_context_ids else "no_aligned_context",
        confidence=_confidence(edge.identity_strength),
        rationale=edge.rationale,
    )


def reasoning_lookup(reasoning_graph: ReasoningGraph) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for alignment in reasoning_graph.alignments:
        lookup.setdefault(alignment.diff_id, {})["alignment_id"] = alignment.alignment_id
    for comparison in reasoning_graph.comparisons:
        record = lookup.setdefault(comparison.diff_id, {})
        record["comparison_id"] = comparison.comparison_id
        if comparison.alignment_id:
            record["alignment_id"] = comparison.alignment_id
    for absence in reasoning_graph.absence_searches:
        lookup.setdefault(absence.diff_id, {})["absence_id"] = absence.absence_id
    return lookup


def _absence_candidates(edge: DiffEdge, graph_b: DocumentGraph) -> list[str]:
    if edge.parameter == "equipment_presence":
        edge_key = normalize_key(edge.subject)
        return [
            subject.subject_id
            for subject in graph_b.subjects
            if subject.canonical_label not in {"GENERAL", "XFMR", "FUSE"} and normalize_key(subject.canonical_label) != edge_key
        ]
    return [claim.claim_id for claim in graph_b.claims if claim.parameter == edge.parameter]


def _query_terms(edge: DiffEdge) -> list[str]:
    return [term for term in [edge.subject, edge.parameter] if term]


def _subject_method(a_subject_id: str, b_subject_id: str, identity_strength: str) -> str:
    a = a_subject_id.split(":subject:", 1)[-1]
    b = b_subject_id.split(":subject:", 1)[-1]
    if a == b:
        return "exact"
    if identity_strength == "strong":
        return "alias"
    if identity_strength == "medium":
        return "context_bridge"
    return "semantic"


def _context_method(a_context_id: str, b_context_id: str, context_by_id: dict[str, object]) -> str:
    if a_context_id == b_context_id:
        return "exact"
    a_label = _context_label(a_context_id, context_by_id)
    b_label = _context_label(b_context_id, context_by_id)
    if "document" in {a_label, b_label}:
        return "missing"
    if align_context_label(a_label) == align_context_label(b_label):
        return "canonicalized"
    return "cross_doc_bridge"


def _context_label(context_id: str, context_by_id: dict[str, object]) -> str:
    context = context_by_id.get(context_id)
    if not context:
        return "document"
    return str(getattr(context, "canonical_label", "document"))


def _unit_method(edge: DiffEdge) -> str:
    notes = " ".join(edge.plausibility_notes).lower()
    if "dimension" in notes:
        return "dimension_mismatch"
    if edge.parameter == "impedance" or "%z" in notes or "impedance base" in notes:
        return "custom_percent_impedance"
    if "pint" in notes:
        return "pint"
    return "exact"


def _confidence(identity_strength: str) -> str:
    if identity_strength == "strong":
        return "high"
    if identity_strength == "medium":
        return "medium"
    return "low"
