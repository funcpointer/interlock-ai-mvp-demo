from __future__ import annotations

import json
import os
import re

from .models import AuthorityDecision, CandidateFinding, DiffEdge, EvidenceCitation, EvidenceItem, Finding, ReasoningGraph

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


def verify_candidates(
    *,
    candidates: list[CandidateFinding],
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
    no_cloud: bool,
    dry_run: bool,
    max_cost_usd: float,
) -> tuple[list[Finding], list[str], dict[str, float]]:
    warnings: list[str] = []
    metrics = {"estimated_cloud_cost_usd": 0.0}
    cloud_decisions: dict[str, dict[str, str]] = {}
    if dry_run or no_cloud or not _cloud_key_present():
        warnings.append("cloud verification skipped; deterministic verifier used")
    else:
        try:
            cloud_decisions = _cloud_screen_candidates(candidates, evidence_by_id)
            metrics["cloud_candidates_screened"] = float(len(cloud_decisions))
        except Exception as exc:
            warnings.append(f"cloud verification failed; deterministic verifier used: {exc}")
    # MVP deterministic verifier. Cloud hook intentionally leaves the final gate deterministic.
    findings: list[Finding] = []
    for candidate in candidates:
        decision = cloud_decisions.get(candidate.candidate_id)
        if decision and decision.get("verdict") == "reject":
            continue
        finding = _deterministic_finding(candidate, evidence_by_id, authority, mode)
        if finding:
            if decision:
                verdict = decision.get("verdict", "pass")
                notes = _clean_authored(decision.get("notes", "Cloud verifier reviewed cited evidence."))
                if verdict == "downgrade" and finding.severity == "review_required":
                    finding.severity = "possible_issue"
                    finding.confidence = "medium"
                finding.verifier_notes = notes
            findings.append(finding)
    return findings, warnings, metrics


def findings_from_diff_graph(
    *,
    diff_edges: list[DiffEdge],
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
    no_cloud: bool,
    dry_run: bool,
    max_cost_usd: float,
    reasoning_by_diff_id: dict[str, dict[str, str]] | None = None,
) -> tuple[list[Finding], list[str], dict[str, float]]:
    warnings: list[str] = []
    metrics = {"estimated_cloud_cost_usd": 0.0}
    if dry_run or no_cloud or not _cloud_key_present():
        warnings.append("cloud verification skipped; deterministic verifier used")
    findings: list[Finding] = []
    for edge in diff_edges:
        finding = _diff_edge_to_finding(edge, evidence_by_id, authority, mode, (reasoning_by_diff_id or {}).get(edge.diff_id, {}))
        if finding:
            findings.append(finding)
    return findings, warnings, metrics


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


def _deterministic_finding(
    candidate: CandidateFinding,
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
    mode: str,
) -> Finding | None:
    evidence_a = evidence_by_id.get(candidate.evidence_a_id or "")
    evidence_b = evidence_by_id.get(candidate.evidence_b_id or "")
    if not evidence_a and not evidence_b:
        return None
    cited = (evidence_a is not None and evidence_a.crop_path and evidence_a.raw_text) or (
        evidence_b is not None and evidence_b.crop_path and evidence_b.raw_text
    )
    if not cited:
        return None

    known_authority = authority.authoritative_side in {"A", "B"}
    verifier_passed = True
    strong_identity = candidate.identity_strength == "strong"
    deterministic = candidate.deterministic_discrepancy
    if candidate.finding_type == "coverage_warning":
        severity = "informational"
        confidence = "high"
    elif strong_identity and deterministic and verifier_passed:
        severity = "review_required"
        confidence = "high" if known_authority else "medium"
    else:
        severity = "possible_issue"
        confidence = "medium" if candidate.identity_strength != "weak" else "low"
    if candidate.finding_type == "needs_engineer_review":
        severity = "possible_issue"
        confidence = "medium"

    summary = _summary(candidate, evidence_a, evidence_b, authority)
    notes = "Deterministic verifier confirmed cited evidence and preserved reviewer-assist wording."
    return Finding(
        finding_id=f"find_{candidate.candidate_id[4:]}",
        mode="cross_doc" if mode == "cross_doc" else "version",
        finding_type=candidate.finding_type,
        severity=severity,
        confidence=confidence,
        subject=candidate.subject,
        parameter=candidate.parameter,
        summary=summary,
        authoritative_side=authority.authoritative_side,
        authority_basis=authority.basis,
        authority_confidence=authority.confidence,
        evidence_a=_citation(evidence_a) if evidence_a else None,
        evidence_b=_citation(evidence_b) if evidence_b else None,
        plausibility_notes=candidate.plausibility_notes,
        verifier_notes=notes,
    )


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


def _summary(candidate: CandidateFinding, a: EvidenceItem | None, b: EvidenceItem | None, authority: AuthorityDecision) -> str:
    direction = _direction_phrase(authority)
    if candidate.finding_type == "value_mismatch" and a and b:
        return f"{direction} Possible discrepancy for {candidate.subject} {candidate.parameter}: A cites {a.value} {a.unit}; B cites {b.value} {b.unit}."
    if candidate.finding_type == "needs_engineer_review" and a and b:
        return f"{direction} {candidate.subject} {candidate.parameter} requires reviewer comparison because impedance base information is incomplete or different."
    if candidate.finding_type == "missing_item" and a:
        return f"{direction} {candidate.subject} {candidate.parameter} appears in A but no matching cited item was found in B."
    if candidate.finding_type == "reference_conflict" and a:
        return f"{direction} Reference {a.value} appears in A but no matching reference was found in B."
    if candidate.finding_type == "coverage_warning":
        ev = a or b
        return f"Coverage warning for {ev.doc_id} page {ev.page}: {ev.value}." if ev else "Coverage warning."
    return f"{direction} Possible discrepancy for {candidate.subject}."


def _direction_phrase(authority: AuthorityDecision) -> str:
    if authority.authoritative_side == "B":
        return "Revised/authoritative B evidence differs from A."
    if authority.authoritative_side == "A":
        return "Authoritative A evidence differs from B."
    return "Documents disagree; authoritative source not determined."


def _cloud_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _cloud_screen_candidates(
    candidates: list[CandidateFinding],
    evidence_by_id: dict[str, EvidenceItem],
) -> dict[str, dict[str, str]]:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic_screen(candidates, evidence_by_id)
    if os.environ.get("OPENAI_API_KEY"):
        return _openai_screen(candidates, evidence_by_id)
    return {}


def _candidate_payload(candidates: list[CandidateFinding], evidence_by_id: dict[str, EvidenceItem]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for candidate in candidates[:20]:
        a = evidence_by_id.get(candidate.evidence_a_id or "")
        b = evidence_by_id.get(candidate.evidence_b_id or "")
        payload.append(
            {
                "candidate_id": candidate.candidate_id,
                "finding_type": candidate.finding_type,
                "subject": candidate.subject,
                "parameter": candidate.parameter,
                "reason": candidate.deterministic_reason,
                "evidence_a": _evidence_prompt(a),
                "evidence_b": _evidence_prompt(b),
            }
        )
    return payload


def _evidence_prompt(evidence: EvidenceItem | None) -> dict[str, object] | None:
    if not evidence:
        return None
    return {
        "doc_id": evidence.doc_id,
        "page": evidence.page,
        "quote": evidence.raw_text[:900],
        "value": evidence.value,
        "unit": evidence.unit,
        "crop_path": evidence.crop_path,
    }


def _screen_prompt(candidates: list[CandidateFinding], evidence_by_id: dict[str, EvidenceItem]) -> str:
    payload = _candidate_payload(candidates, evidence_by_id)
    return (
        "You are checking candidate engineering document discrepancies. "
        "Try to disprove each candidate using only the cited snippets. "
        "Do not create new findings. Return strict JSON only: "
        "{\"decisions\":[{\"candidate_id\":\"cand00001\",\"verdict\":\"pass|downgrade|reject\",\"notes\":\"short reviewer-assist note\"}]}. "
        "Avoid these words in notes unless they are source quotes: wrong, error, incorrect, mistake, unsafe, dangerous, hazardous, defective.\n\n"
        f"Candidates:\n{json.dumps(payload, indent=2)}"
    )


def _anthropic_screen(candidates: list[CandidateFinding], evidence_by_id: dict[str, EvidenceItem]) -> dict[str, dict[str, str]]:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("INTERLOCK_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    response = client.messages.create(
        model=model,
        max_tokens=1800,
        temperature=0,
        messages=[{"role": "user", "content": _screen_prompt(candidates, evidence_by_id)}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    return _parse_decisions(text)


def _openai_screen(candidates: list[CandidateFinding], evidence_by_id: dict[str, EvidenceItem]) -> dict[str, dict[str, str]]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("INTERLOCK_OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[{"role": "user", "content": _screen_prompt(candidates, evidence_by_id)}],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content or "{}"
    return _parse_decisions(text)


def _parse_decisions(text: str) -> dict[str, dict[str, str]]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    parsed = json.loads(text[start : end + 1])
    decisions: dict[str, dict[str, str]] = {}
    for item in parsed.get("decisions", []):
        candidate_id = str(item.get("candidate_id", ""))
        verdict = str(item.get("verdict", "pass"))
        if candidate_id and verdict in {"pass", "downgrade", "reject"}:
            decisions[candidate_id] = {
                "verdict": verdict,
                "notes": _clean_authored(str(item.get("notes", ""))),
            }
    return decisions


def _clean_authored(text: str) -> str:
    cleaned = text or "Verifier reviewed cited evidence."
    for word in BANNED_AUTHORED_WORDS:
        cleaned = cleaned.replace(word, "issue").replace(word.capitalize(), "Issue")
    return cleaned
