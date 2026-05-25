from __future__ import annotations

from .models import (
    AlignmentDecision,
    AuthorityDecision,
    DecisionSignal,
    DecisionTrace,
    DiffEdge,
    EvidenceItem,
    Finding,
    ReasoningGraph,
)


def build_decision_traces(
    *,
    findings: list[Finding],
    reasoning_graph: ReasoningGraph,
    diff_edges: list[DiffEdge],
    evidence_by_id: dict[str, EvidenceItem],
    authority: AuthorityDecision,
) -> list[DecisionTrace]:
    diff_by_id = {edge.diff_id: edge for edge in diff_edges}
    alignment_by_id = {alignment.alignment_id: alignment for alignment in reasoning_graph.alignments}
    comparison_by_id = {comparison.comparison_id: comparison for comparison in reasoning_graph.comparisons}
    absence_by_id = {absence.absence_id: absence for absence in reasoning_graph.absence_searches}

    traces: list[DecisionTrace] = []
    for index, finding in enumerate(findings, start=1):
        edge = diff_by_id.get(_diff_id_for_finding(finding))
        signals: list[DecisionSignal] = []
        why: list[str] = []
        downgrade_reasons: list[str] = []
        rejected_alternatives: list[str] = []

        cited_ids = _finding_evidence_ids(finding)
        if cited_ids:
            signals.append(
                DecisionSignal(
                    signal_id=f"sig{index:05d}_citation",
                    source="evidence",
                    signal_type="citation",
                    supports=True,
                    summary=f"Finding cites {len(cited_ids)} evidence item(s): {', '.join(cited_ids)}.",
                    confidence="high",
                    evidence_ids=cited_ids,
                )
            )
            why.append("cited evidence is present")

        signals.append(
            DecisionSignal(
                signal_id=f"sig{index:05d}_authority",
                source="authority",
                signal_type="authority_direction",
                supports=authority.authoritative_side in {"A", "B"},
                summary=f"Authority resolved to `{authority.authoritative_side}` from {authority.basis}.",
                confidence="high" if authority.confidence >= 0.8 else "medium" if authority.confidence >= 0.5 else "low",
            )
        )
        if authority.authoritative_side in {"A", "B"}:
            why.append(f"authority direction is {authority.authoritative_side}")
        else:
            downgrade_reasons.append("authority direction is unknown")

        if edge:
            signals.append(
                DecisionSignal(
                    signal_id=f"sig{index:05d}_diff",
                    source="diff_graph",
                    signal_type=edge.diff_type,
                    supports=edge.deterministic_discrepancy or edge.diff_type == "coverage_warning",
                    summary=edge.rationale,
                    confidence=_confidence_from_identity(edge.identity_strength),
                    evidence_ids=edge.evidence_ids,
                    reasoning_id=edge.diff_id,
                )
            )
            why.append(f"diff edge `{edge.diff_id}` classified `{edge.diff_type}`")
            if edge.identity_strength != "strong":
                downgrade_reasons.append(f"identity strength is {edge.identity_strength}")
            if not edge.deterministic_discrepancy and edge.diff_type != "coverage_warning":
                downgrade_reasons.append("discrepancy is not deterministic")

        if finding.alignment_id:
            alignment = alignment_by_id.get(finding.alignment_id)
            if alignment:
                signals.append(_alignment_signal(index, alignment))
                why.append(
                    f"alignment used subject={alignment.subject_method}, parameter={alignment.parameter_method}, context={alignment.context_method}"
                )
                rejected_alternatives.extend(alignment.rejected_b_claim_ids)

        if finding.comparison_id:
            comparison = comparison_by_id.get(finding.comparison_id)
            if comparison:
                signals.append(
                    DecisionSignal(
                        signal_id=f"sig{index:05d}_comparison",
                        source="reasoning_graph",
                        signal_type="comparison",
                        supports=comparison.deterministic,
                        summary=f"{comparison.comparison_type} via {comparison.unit_method}: {comparison.rationale}",
                        confidence="high" if comparison.deterministic else "medium",
                        reasoning_id=comparison.comparison_id,
                    )
                )
                why.append(f"comparison `{comparison.comparison_id}` used {comparison.unit_method}")
                why.extend(comparison.plausibility_notes)

        if finding.absence_id:
            absence = absence_by_id.get(finding.absence_id)
            if absence:
                signals.append(
                    DecisionSignal(
                        signal_id=f"sig{index:05d}_absence",
                        source="reasoning_graph",
                        signal_type="absence_search",
                        supports=absence.coverage_status == "searched",
                        summary=f"Searched {absence.searched_doc_id} contexts {absence.searched_context_ids}: {absence.rationale}",
                        confidence=absence.confidence,
                        reasoning_id=absence.absence_id,
                    )
                )
                why.append(f"absence search `{absence.absence_id}` status {absence.coverage_status}")
                rejected_alternatives.extend(absence.rejected_candidate_ids)
                if absence.coverage_status != "searched":
                    downgrade_reasons.append(f"absence search coverage status is {absence.coverage_status}")

        if finding.severity != "review_required":
            downgrade_reasons.append(f"severity is {finding.severity}")

        traces.append(
            DecisionTrace(
                finding_id=finding.finding_id,
                decision=finding.severity,
                finding_type=finding.finding_type,
                confidence=finding.confidence,
                why=_dedup(why),
                supporting_signals=signals,
                contradicting_signals=[],
                downgrade_reasons=_dedup(downgrade_reasons),
                rejected_alternatives=_dedup(rejected_alternatives),
            )
        )
    return traces


def _diff_id_for_finding(finding: Finding) -> str:
    return f"diff{finding.finding_id.removeprefix('find_')}"


def _finding_evidence_ids(finding: Finding) -> list[str]:
    ids = []
    if finding.evidence_a:
        ids.append(finding.evidence_a.evidence_id)
    if finding.evidence_b:
        ids.append(finding.evidence_b.evidence_id)
    return ids


def _alignment_signal(index: int, alignment: AlignmentDecision) -> DecisionSignal:
    return DecisionSignal(
        signal_id=f"sig{index:05d}_alignment",
        source="reasoning_graph",
        signal_type="alignment",
        supports=alignment.accepted,
        summary=(
            f"Aligned {alignment.a_claim_id} to {alignment.b_claim_id} "
            f"using subject={alignment.subject_method}, parameter={alignment.parameter_method}, context={alignment.context_method}."
        ),
        confidence=alignment.confidence,
        reasoning_id=alignment.alignment_id,
    )


def _confidence_from_identity(identity_strength: str) -> str:
    if identity_strength == "strong":
        return "high"
    if identity_strength == "medium":
        return "medium"
    return "low"


def _dedup(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
