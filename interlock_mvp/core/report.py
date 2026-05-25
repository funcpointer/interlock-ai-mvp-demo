from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import AuthorityDecision, Finding


def render_report(
    *,
    path: Path,
    findings: list[Finding],
    authority: AuthorityDecision,
    metrics: dict,
    warnings: list[str],
) -> None:
    sections = _route_findings(findings)
    lines: list[str] = [
        "# InterLock MVP Review Report",
        "",
        "This report is a reviewer-assist artifact. It does not certify engineering correctness.",
        "",
        "## Executive Summary",
        "",
        f"- Findings: {len(findings)}",
        f"- Review required: {sum(1 for f in findings if f.severity == 'review_required')}",
        f"- Coverage warnings: {sum(1 for f in findings if f.finding_type == 'coverage_warning')}",
        f"- Authority: {authority.authoritative_side} ({authority.basis}, confidence {authority.confidence:.2f})",
        "",
    ]
    if warnings:
        lines.extend(["### Run Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    lines.extend(_reasoning_health_lines(metrics))

    for title, key in [
        ("Directional High-Confidence Findings", "directional"),
        ("Possible Discrepancies", "possible"),
        ("Missing / Removed Items", "missing"),
        ("Reference Conflicts", "reference"),
        ("Needs Engineer Review", "engineer"),
        ("Coverage Warnings", "coverage"),
    ]:
        lines.extend([f"## {title}", ""])
        routed = sections.get(key, [])
        if not routed:
            lines.extend(["No findings in this section.", ""])
            continue
        for finding in routed:
            lines.extend(_finding_lines(finding))
            lines.append("")

    lines.extend(["## Run Metrics", ""])
    for key, value in sorted(metrics.items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _reasoning_health_lines(metrics: dict) -> list[str]:
    keys = [
        "alignment_decisions",
        "comparison_decisions",
        "absence_searches",
        "context_supports",
        "context_supports_by_confidence",
        "alignment_decisions_by_subject_method",
        "alignment_decisions_by_context_method",
        "comparison_decisions_by_unit_method",
        "absence_searches_by_coverage_status",
    ]
    if not any(key in metrics for key in keys):
        return []
    lines = ["## Review Reasoning Health", ""]
    for key in keys:
        if key in metrics:
            lines.append(f"- `{key}`: {metrics[key]}")
    lines.append("")
    return lines


def _route_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    routed: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        known_authority = finding.authoritative_side in {"A", "B"}
        if finding.finding_type == "coverage_warning":
            routed["coverage"].append(finding)
        elif finding.finding_type == "missing_item":
            routed["missing"].append(finding)
        elif finding.finding_type == "reference_conflict":
            routed["reference"].append(finding)
        elif finding.finding_type == "needs_engineer_review" or (
            finding.severity == "review_required" and not known_authority
        ):
            routed["engineer"].append(finding)
        elif finding.severity == "review_required" and known_authority:
            routed["directional"].append(finding)
        else:
            routed["possible"].append(finding)
    return routed


def _finding_lines(finding: Finding) -> list[str]:
    lines = [
        f"### {_finding_title(finding)}",
        "",
        f"- Why flagged: {finding.summary}",
        f"- Severity: `{finding.severity}`",
        f"- Type: `{finding.finding_type}`",
        f"- Confidence: `{finding.confidence}`",
        f"- Authority: `{finding.authoritative_side}` ({finding.authority_basis}, confidence {finding.authority_confidence:.2f})",
        f"- Finding ID: `{finding.finding_id}`",
    ]
    if finding.plausibility_notes:
        lines.append(f"- Plausibility notes: {'; '.join(finding.plausibility_notes)}")
    if finding.alignment_id or finding.comparison_id:
        lines.extend(_audit_trail_lines(finding))
    if finding.context_support_summary:
        lines.extend(_context_support_lines(finding))
    if finding.model_review_status == "used":
        lines.extend(_model_review_lines(finding))
    lines.append(f"- Verifier notes: {finding.verifier_notes}")
    if finding.evidence_a:
        lines.extend(_citation_lines("Doc A", finding.evidence_a))
    if finding.evidence_b:
        lines.extend(_citation_lines("Doc B", finding.evidence_b))
    return lines


def _context_support_lines(finding: Finding) -> list[str]:
    verdict = "aligned context" if finding.context_support_supports else "context caution"
    lines = [
        f"- Audit trail context: {verdict}; {finding.context_support_confidence or 'unknown'} confidence.",
    ]
    if finding.context_support_context_refs:
        sections = "; ".join(_human_context_ref(item) for item in finding.context_support_context_refs[:4])
        lines.append(f"- Compared sections: {sections}")
    if finding.context_support_search_ids:
        lines.append(f"- Related packet evidence: {len(finding.context_support_search_ids)} supporting search hit(s)")
    return lines


def _audit_trail_lines(finding: Finding) -> list[str]:
    lines = [
        f"- Candidate pool: {finding.pairing_candidate_pool_count} Doc B claim(s); "
        f"{finding.pairing_same_parameter_candidate_count} same-parameter candidate(s).",
        f"- Pairing: subject `{finding.pairing_subject_method or 'n/a'}`, "
        f"parameter `{finding.pairing_parameter_method or 'n/a'}`, "
        f"context `{finding.pairing_context_method or 'n/a'}`.",
    ]
    if finding.pairing_rejected_candidate_count:
        lines.append(f"- Other candidates considered: {finding.pairing_rejected_candidate_count} same-parameter Doc B candidate(s).")
        for summary in finding.pairing_rejected_candidate_summaries[:3]:
            lines.append(f"- Rejected candidate: {summary}")
    if finding.comparison_unit_method:
        deterministic = "deterministic" if finding.comparison_deterministic else "not deterministic"
        lines.append(f"- Comparison rule: `{finding.comparison_unit_method}` ({deterministic}).")
    return lines


def _human_context_ref(ref) -> str:
    page_text = _page_span_text(ref.pages)
    prefix = f"Doc {ref.doc_id} - " if ref.doc_id in {"A", "B"} else ""
    return f"{prefix}{ref.label}{page_text}"


def _page_span_text(pages: list[int]) -> str:
    if not pages:
        return ""
    unique = sorted(set(pages))
    if len(unique) == 1:
        return f" (p{unique[0]})"
    return f" (p{unique[0]}-{unique[-1]})"


def _model_review_lines(finding: Finding) -> list[str]:
    verdict = "supports citations" if finding.model_review_supports else "adds caution"
    lines = [
        f"- External model check: {verdict} (`{finding.model_review_model}`). Advisory only.",
        f"- External model summary: {finding.model_review_summary}",
    ]
    if finding.model_review_cautions:
        lines.append(f"- External model cautions: {'; '.join(finding.model_review_cautions)}")
    return lines


def _citation_lines(label: str, citation) -> list[str]:
    return [
        f"- {label}: page {citation.page}, evidence `{citation.evidence_id}`",
        f"  - Quote: `{_clip(citation.quote)}`",
        f"  - Crop: `{citation.crop_path}`",
    ]


def _finding_title(finding: Finding) -> str:
    if finding.finding_type == "value_mismatch" and finding.evidence_a and finding.evidence_b:
        return (
            f"{finding.subject} {finding.parameter}: "
            f"{_display_citation_value(finding.evidence_a)} -> {_display_citation_value(finding.evidence_b)}"
        )
    if finding.finding_type == "missing_item":
        return f"{finding.subject}: missing aligned evidence"
    return f"{finding.subject} {finding.parameter}"


def _display_citation_value(citation) -> str:
    return " ".join(part for part in [citation.value, citation.unit] if part).strip() or _clip(citation.quote, 80)


def _clip(text: str, limit: int = 280) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."
