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
        f"### {finding.finding_id}: {finding.subject} / {finding.parameter}",
        "",
        f"- Type: `{finding.finding_type}`",
        f"- Severity: `{finding.severity}`",
        f"- Confidence: `{finding.confidence}`",
        f"- Authority: `{finding.authoritative_side}` ({finding.authority_basis}, confidence {finding.authority_confidence:.2f})",
        f"- Summary: {finding.summary}",
    ]
    if finding.plausibility_notes:
        lines.append(f"- Plausibility notes: {'; '.join(finding.plausibility_notes)}")
    if finding.context_support_summary:
        lines.extend(_context_support_lines(finding))
    lines.append(f"- Verifier notes: {finding.verifier_notes}")
    if finding.evidence_a:
        lines.extend(_citation_lines("Doc A", finding.evidence_a))
    if finding.evidence_b:
        lines.extend(_citation_lines("Doc B", finding.evidence_b))
    return lines


def _context_support_lines(finding: Finding) -> list[str]:
    verdict = "supports this finding" if finding.context_support_supports else "adds caution"
    signals = "; ".join(_context_signal_label(signal) for signal in finding.context_support_signal_types)
    return [
        f"- Context quorum: {verdict} ({finding.context_support_confidence or 'unknown'} confidence).",
        "- Context note: supporting signal only; source citations and deterministic comparison remain required.",
        f"- Context signals: {signals or 'none'}",
        f"- Context summary: {finding.context_support_summary}",
    ]


def _context_signal_label(signal: str) -> str:
    return {
        "context_room": "same kind of document room/table/section",
        "graph_alignment": "graph links both cited claims through document context",
        "search_hit": "search found related packet evidence",
        "missing_context": "evidence is only in generic or missing context",
        "possible_equivalent_elsewhere": "search found possible equivalent evidence elsewhere",
    }.get(signal, signal.replace("_", " "))


def _citation_lines(label: str, citation) -> list[str]:
    return [
        f"- {label} citation: page {citation.page}, evidence `{citation.evidence_id}`",
        f"  - Quote: `{_clip(citation.quote)}`",
        f"  - Crop: `{citation.crop_path}`",
    ]


def _clip(text: str, limit: int = 280) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."
