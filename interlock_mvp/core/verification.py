from __future__ import annotations

import os
import re

from .models import AuthorityDecision, DiffEdge, EvidenceCitation, EvidenceItem, Finding, ReasoningGraph

BANNED_AUTHORED_WORDS = {
    "wrong",
    "error",
    "incorrect",
    "mistake",
    "unsafe",
    "dangerous",
    "hazardous",
    "defective",
}


def findings_from_reasoning_graph(
    *,
    reasoning_graph: ReasoningGraph,
    diff_edges: list[DiffEdge],
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
    no_cloud: bool,
    dry_run: bool,
    max_cost_usd: float,
) -> tuple[list[Finding], list[str], dict[str, float]]:
    warnings: list[str] = []
    metrics = {
        "estimated_cloud_cost_usd": 0.0,
        "comparison_sourced_findings": 0.0,
        "absence_sourced_findings": 0.0,
        "coverage_edge_sourced_findings": 0.0,
    }
    if dry_run or no_cloud or not _cloud_key_present():
        warnings.append("cloud verification skipped; deterministic verifier used")
    else:
        warnings.append("cloud reasoning verifier not implemented; deterministic verifier used")

    diff_by_id = {edge.diff_id: edge for edge in diff_edges}
    findings: list[Finding] = []

    for comparison in reasoning_graph.comparisons:
        edge = diff_by_id.get(comparison.diff_id)
        if not edge:
            continue
        reasoning_ids = {"comparison_id": comparison.comparison_id}
        if comparison.alignment_id:
            reasoning_ids["alignment_id"] = comparison.alignment_id
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, reasoning_ids)
        if finding:
            findings.append(finding)
            metrics["comparison_sourced_findings"] += 1.0

    for absence in reasoning_graph.absence_searches:
        edge = diff_by_id.get(absence.diff_id)
        if not edge:
            continue
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, {"absence_id": absence.absence_id})
        if finding:
            findings.append(finding)
            metrics["absence_sourced_findings"] += 1.0

    for edge in diff_edges:
        if edge.diff_type != "coverage_warning":
            continue
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, {})
        if finding:
            findings.append(finding)
            metrics["coverage_edge_sourced_findings"] += 1.0

    findings.sort(key=_finding_sort_key)
    return findings, warnings, metrics


def authored_language_violations(text: str) -> list[str]:
    return sorted(word for word in BANNED_AUTHORED_WORDS if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE))


def _diff_edge_to_finding(
    edge: DiffEdge,
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
    reasoning_ids: dict[str, str] | None = None,
) -> Finding | None:
    cited_evidence = [evidence_by_id[eid] for eid in edge.evidence_ids if eid in evidence_by_id]
    if not cited_evidence:
        return None
    evidence_a = next((item for item in cited_evidence if item.doc_id == "A"), None)
    evidence_b = next((item for item in cited_evidence if item.doc_id == "B"), None)
    if not evidence_a and not evidence_b:
        return None

    known_authority = authority.authoritative_side in {"A", "B"}
    if edge.diff_type == "coverage_warning":
        severity = "informational"
        confidence = "high"
    elif edge.identity_strength == "strong" and edge.deterministic_discrepancy and known_authority:
        severity = "review_required"
        confidence = "high"
    elif edge.identity_strength == "strong" and edge.deterministic_discrepancy:
        severity = "possible_issue"
        confidence = "medium"
    else:
        severity = "possible_issue"
        confidence = "medium" if edge.identity_strength != "weak" else "low"
    if edge.diff_type == "needs_engineer_review":
        severity = "possible_issue"
        confidence = "medium"

    return Finding(
        finding_id=f"find_{edge.diff_id[4:]}",
        mode="cross_doc" if mode == "cross_doc" else "version",
        finding_type=edge.diff_type,
        severity=severity,
        confidence=confidence,
        subject=edge.subject,
        parameter=edge.parameter,
        summary=_diff_summary(edge, evidence_a, evidence_b, authority),
        authoritative_side=authority.authoritative_side,
        authority_basis=authority.basis,
        authority_confidence=authority.confidence,
        evidence_a=_citation(evidence_a) if evidence_a else None,
        evidence_b=_citation(evidence_b) if evidence_b else None,
        plausibility_notes=edge.plausibility_notes,
        verifier_notes="Deterministic graph verifier confirmed cited evidence and preserved reviewer-assist wording.",
        alignment_id=(reasoning_ids or {}).get("alignment_id"),
        comparison_id=(reasoning_ids or {}).get("comparison_id"),
        absence_id=(reasoning_ids or {}).get("absence_id"),
    )


def _finding_sort_key(finding: Finding) -> tuple[int, str]:
    type_rank = {
        "value_mismatch": 0,
        "needs_engineer_review": 1,
        "missing_item": 2,
        "reference_conflict": 3,
        "coverage_warning": 4,
    }
    return (type_rank.get(finding.finding_type, 9), finding.finding_id)


def _diff_summary(edge: DiffEdge, a: EvidenceItem | None, b: EvidenceItem | None, authority: AuthorityDecision) -> str:
    direction = _direction_phrase(authority)
    if edge.diff_type == "value_mismatch" and a and b:
        return f"{direction} Possible discrepancy for {edge.subject} {edge.parameter}: A cites {a.value} {a.unit}; B cites {b.value} {b.unit}."
    if edge.diff_type == "needs_engineer_review" and a and b:
        return f"{direction} {edge.subject} {edge.parameter} requires reviewer comparison because base or identity context is incomplete."
    if edge.diff_type == "missing_item" and a:
        return f"{direction} {edge.subject} {edge.parameter} appears in A's aligned context but no matching B evidence was found."
    return f"{direction} Possible discrepancy for {edge.subject} {edge.parameter}."


def _citation(evidence: EvidenceItem) -> EvidenceCitation:
    return EvidenceCitation(
        evidence_id=evidence.evidence_id,
        doc_id=evidence.doc_id,
        page=evidence.page,
        bbox=evidence.bbox,
        quote=evidence.raw_text,
        crop_path=evidence.crop_path,
        value=evidence.value,
        unit=evidence.unit,
    )


def _direction_phrase(authority: AuthorityDecision) -> str:
    if authority.authoritative_side == "B":
        return "Revised/authoritative B evidence differs from A."
    if authority.authoritative_side == "A":
        return "Authoritative A evidence differs from B."
    return "Documents disagree; authoritative source not determined."


def _cloud_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
