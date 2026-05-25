from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel

from .models import SCHEMA_VERSION
from .models import AuthorityDecision, ContextSupport, DiffEdge, EvidenceCitation, EvidenceItem, Finding, ReasoningGraph

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
DEFAULT_OPENAI_MODEL = os.environ.get("INTERLOCK_OPENAI_MODEL", "gpt-4o")
ESTIMATED_CLOUD_REVIEW_COST_USD = float(os.environ.get("INTERLOCK_CLOUD_REVIEW_ESTIMATE_USD", "0.01"))


class ExternalFindingReview(BaseModel):
    supports_finding: bool
    reviewer_note: str = ""
    caution_note: str = ""


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
        "external_model_reviewed_findings": 0.0,
        "external_model_review_failures": 0.0,
        "comparison_sourced_findings": 0.0,
        "absence_sourced_findings": 0.0,
        "coverage_edge_sourced_findings": 0.0,
    }
    cloud_enabled = not dry_run and not no_cloud and _openai_key_present()
    if dry_run or no_cloud:
        warnings.append("cloud verification skipped; deterministic verifier used")
    elif not _openai_key_present():
        warnings.append("OpenAI key missing; deterministic verifier used")

    diff_by_id = {edge.diff_id: edge for edge in diff_edges}
    support_by_diff_id = {support.diff_id: support for support in reasoning_graph.context_supports}
    findings: list[Finding] = []

    for comparison in reasoning_graph.comparisons:
        edge = diff_by_id.get(comparison.diff_id)
        if not edge:
            continue
        reasoning_ids = {"comparison_id": comparison.comparison_id}
        if comparison.alignment_id:
            reasoning_ids["alignment_id"] = comparison.alignment_id
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, reasoning_ids, support_by_diff_id.get(edge.diff_id))
        if finding:
            findings.append(finding)
            metrics["comparison_sourced_findings"] += 1.0

    for absence in reasoning_graph.absence_searches:
        edge = diff_by_id.get(absence.diff_id)
        if not edge:
            continue
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, {"absence_id": absence.absence_id}, support_by_diff_id.get(edge.diff_id))
        if finding:
            findings.append(finding)
            metrics["absence_sourced_findings"] += 1.0

    for edge in diff_edges:
        if edge.diff_type != "coverage_warning":
            continue
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, {}, support_by_diff_id.get(edge.diff_id))
        if finding:
            findings.append(finding)
            metrics["coverage_edge_sourced_findings"] += 1.0

    findings.sort(key=_finding_sort_key)
    if cloud_enabled:
        findings, cloud_warnings, cloud_metrics = _apply_external_model_reviews(
            findings=findings,
            max_cost_usd=max_cost_usd,
            model=DEFAULT_OPENAI_MODEL,
        )
        warnings.extend(cloud_warnings)
        metrics.update(cloud_metrics)
    return findings, warnings, metrics


def authored_language_violations(text: str) -> list[str]:
    return sorted(word for word in BANNED_AUTHORED_WORDS if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE))


def _apply_external_model_reviews(
    *,
    findings: list[Finding],
    max_cost_usd: float,
    model: str,
) -> tuple[list[Finding], list[str], dict[str, float]]:
    warnings: list[str] = []
    metrics = {
        "estimated_cloud_cost_usd": 0.0,
        "external_model_reviewed_findings": 0.0,
        "external_model_review_failures": 0.0,
    }
    if max_cost_usd < ESTIMATED_CLOUD_REVIEW_COST_USD:
        warnings.append("external model review skipped; max_cost_usd below per-finding estimate")
        return findings, warnings, metrics
    reviewed: list[Finding] = []
    for finding in findings:
        if finding.finding_type == "coverage_warning":
            reviewed.append(finding)
            continue
        if metrics["estimated_cloud_cost_usd"] + ESTIMATED_CLOUD_REVIEW_COST_USD > max_cost_usd:
            warnings.append("external model review stopped at max_cost_usd")
            reviewed.append(finding)
            continue
        try:
            review = _review_finding_with_openai(finding, model=model)
            reviewer_note = review.reviewer_note.strip()[:600]
            caution_note = review.caution_note.strip()[:400]
            authored_text = " ".join([reviewer_note, caution_note])
            violations = authored_language_violations(authored_text)
            if violations:
                warnings.append(f"external model review rejected for {finding.finding_id}; banned wording: {', '.join(violations)}")
                metrics["external_model_review_failures"] += 1.0
                reviewed.append(finding.model_copy(update={"model_review_status": "rejected_language", "model_review_model": model}))
                continue
            cautions = [caution_note] if caution_note else []
            reviewed.append(
                finding.model_copy(
                    update={
                        "model_review_status": "used",
                        "model_review_model": model,
                        "model_review_supports": review.supports_finding,
                        "model_review_summary": reviewer_note,
                        "model_review_cautions": cautions,
                    }
                )
            )
            metrics["external_model_reviewed_findings"] += 1.0
            metrics["estimated_cloud_cost_usd"] = round(metrics["estimated_cloud_cost_usd"] + ESTIMATED_CLOUD_REVIEW_COST_USD, 4)
        except Exception as exc:
            warnings.append(f"external model review failed for {finding.finding_id}: {type(exc).__name__}")
            metrics["external_model_review_failures"] += 1.0
            reviewed.append(finding.model_copy(update={"model_review_status": "failed", "model_review_model": model}))
    return reviewed, warnings, metrics


def _review_finding_with_openai(finding: Finding, *, model: str) -> ExternalFindingReview:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc
    client = OpenAI()
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are an advisory evidence reviewer for engineering PDFs. Review only whether the supplied citations support the "
                    "existing finding. Do not judge engineering acceptability, design adequacy, operational significance, safety, or "
                    "code compliance. Try to disprove the finding using only the supplied JSON. "
                    "Set supports_finding=true when the citations contain the stated subject, parameter, values, and authority/context "
                    "needed for the existing finding, even if a human engineer must decide significance. Set supports_finding=false only "
                    "when there is a citation, identity, authority, unit-equivalence, or context gap. Do not create new findings. "
                    "Return concise reviewer-facing JSON. Avoid these authored words: wrong, error, incorrect, mistake, unsafe, dangerous, hazardous, defective."
                ),
            },
            {
                "role": "user",
                "content": _external_review_payload(finding),
            },
        ],
        text_format=ExternalFindingReview,
    )
    parsed = response.output_parsed
    if not isinstance(parsed, ExternalFindingReview):
        raise RuntimeError("OpenAI response did not parse as ExternalFindingReview")
    return parsed


def _external_review_payload(finding: Finding) -> str:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "instruction": "Review this existing cited finding as advisory support only. Do not create or remove findings.",
        "finding": finding.model_dump(
            mode="json",
            include={
                "finding_id",
                "finding_type",
                "severity",
                "confidence",
                "subject",
                "parameter",
                "summary",
                "authoritative_side",
                "authority_basis",
                "evidence_a",
                "evidence_b",
                "plausibility_notes",
                "context_support_supports",
                "context_support_confidence",
                "context_support_summary",
                "context_support_signal_types",
            },
        ),
    }
    import json

    return json.dumps(payload, sort_keys=True)


def _diff_edge_to_finding(
    edge: DiffEdge,
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
    reasoning_ids: dict[str, str] | None = None,
    context_support: ContextSupport | None = None,
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
    severity, confidence = _apply_context_support_policy(
        edge=edge,
        severity=severity,
        confidence=confidence,
        context_support=context_support,
        known_authority=known_authority,
        has_both_citations=bool(evidence_a and evidence_b),
    )

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
        context_support_id=context_support.support_id if context_support else None,
        context_support_supports=context_support.supports if context_support else None,
        context_support_confidence=context_support.confidence if context_support else None,
        context_support_summary=context_support.summary if context_support else "",
        context_support_signal_types=context_support.signal_types if context_support else [],
    )


def _apply_context_support_policy(
    *,
    edge: DiffEdge,
    severity: str,
    confidence: str,
    context_support: ContextSupport | None,
    known_authority: bool,
    has_both_citations: bool,
) -> tuple[str, str]:
    if not context_support or edge.diff_type == "coverage_warning":
        return severity, confidence
    contradicts = "possible_equivalent_elsewhere" in context_support.signal_types
    weak_context_for_non_strong_identity = not context_support.supports and edge.identity_strength != "strong"
    if severity == "review_required" and (contradicts or weak_context_for_non_strong_identity):
        return "possible_issue", "medium"
    can_upgrade = (
        severity != "review_required"
        and edge.diff_type == "value_mismatch"
        and edge.identity_strength == "medium"
        and edge.deterministic_discrepancy
        and known_authority
        and has_both_citations
        and context_support.supports
        and context_support.confidence == "high"
    )
    if can_upgrade:
        return "review_required", "high"
    return severity, confidence


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
    if edge.diff_type == "value_mismatch" and a and b:
        return _value_mismatch_summary(edge, a, b, authority)
    if edge.diff_type == "needs_engineer_review" and a and b:
        return f"{edge.subject} {edge.parameter} needs engineering review because base or identity context is incomplete."
    if edge.diff_type == "missing_item" and a:
        return f"{edge.subject} {edge.parameter} appears in Doc A, but no matching Doc B evidence was found in the aligned context."
    return f"{edge.subject} {edge.parameter} needs reviewer inspection."


def _value_mismatch_summary(edge: DiffEdge, a: EvidenceItem, b: EvidenceItem, authority: AuthorityDecision) -> str:
    value_a = _display_value(a)
    value_b = _display_value(b)
    if authority.authoritative_side == "B":
        return f"{edge.subject} {edge.parameter}: authoritative Doc B cites {value_b}; baseline Doc A cites {value_a}."
    if authority.authoritative_side == "A":
        return f"{edge.subject} {edge.parameter}: authoritative Doc A cites {value_a}; Doc B cites {value_b}."
    return f"{edge.subject} {edge.parameter}: Doc A cites {value_a}; Doc B cites {value_b}. Authority is unresolved."


def _display_value(evidence: EvidenceItem) -> str:
    return " ".join(part for part in [evidence.value, evidence.unit] if part).strip()


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


def _openai_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))
