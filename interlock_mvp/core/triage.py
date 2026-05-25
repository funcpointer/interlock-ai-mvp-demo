from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import read_artifact, write_object
from .models import RunTriage, TriageIssue

LOW_TEXT_CHARS = 40


def triage_run(run_dir: Path, *, write: bool = True) -> RunTriage:
    """Diagnose accuracy risks from persisted run artifacts.

    This is an inspection layer. It never changes findings and never decides
    whether a run passes; eval YAML remains the acceptance gate.
    """

    metrics = _load_metrics(run_dir)
    pages = _records(run_dir / "pages.json")
    evidence = _records(run_dir / "evidence.json")
    findings = _records(run_dir / "findings.json")
    traces = _records(run_dir / "decision_traces.json")
    reasoning = _load_reasoning(run_dir)
    context_memory = _load_context_memory(run_dir)

    issues: list[TriageIssue] = []
    issues.extend(_weak_extraction_issues(pages, metrics))
    issues.extend(_context_issues(evidence, context_memory, metrics))
    issues.extend(_reasoning_issues(findings, traces, reasoning, metrics))
    issues.extend(_finding_trace_issues(findings, traces, metrics))

    triage = RunTriage(
        run_dir=str(run_dir),
        findings=int(metrics.get("findings") or len(findings)),
        review_required_findings=int(metrics.get("review_required_findings") or 0),
        coverage_warning_findings=int(metrics.get("coverage_warning_findings") or 0),
        issue_count=len(issues),
        issues=issues,
        next_actions=_next_actions(issues),
    )
    if write:
        write_object(run_dir / "triage.json", triage.model_dump(mode="json"))
    return triage


def _weak_extraction_issues(pages: list[dict[str, Any]], metrics: dict[str, Any]) -> list[TriageIssue]:
    weak_pages = [
        page
        for page in pages
        if page.get("extraction_status") != "ok" or int(page.get("text_char_count") or 0) < LOW_TEXT_CHARS
    ]
    if not weak_pages:
        return []
    examples = [
        f"{page.get('doc_id')} p{page.get('page_num')} "
        f"status={page.get('extraction_status')} chars={page.get('text_char_count')}"
        for page in weak_pages[:8]
    ]
    severity = "high" if metrics.get("review_required_findings", 0) == 0 else "medium"
    return [
        TriageIssue(
            issue_id="triage_weak_extraction_pages",
            severity=severity,
            category="extraction",
            title="Weak or empty text-layer pages",
            summary=(
                f"{len(weak_pages)} page(s) have empty, non-ok, or very low text extraction. "
                "Recall on these pages is bounded by OCR/VLM/table extraction, not graph logic."
            ),
            evidence=examples,
            metrics={"weak_pages": len(weak_pages), "pages": len(pages), "low_text_threshold_chars": LOW_TEXT_CHARS},
            suggested_next_step="Add OCR/VLM extraction only for these pages, then compare evidence counts before/after.",
        )
    ]


def _context_issues(
    evidence: list[dict[str, Any]], context_memory: dict[str, Any], metrics: dict[str, Any]
) -> list[TriageIssue]:
    issues: list[TriageIssue] = []
    document_context = [
        item
        for item in evidence
        if str(item.get("context_id") or "").endswith(":document") or item.get("context_confidence") == "low"
    ]
    generic_subjects = [
        item
        for item in evidence
        if str(item.get("subject") or "").strip().upper() in {"", "DOCUMENT", "UNKNOWN", "GENERAL"}
    ]
    if document_context:
        examples = [
            f"{item.get('evidence_id')} {item.get('doc_id')} p{item.get('page')} "
            f"context={item.get('context_id') or '<blank>'} subject={item.get('subject') or '<blank>'}"
            for item in document_context[:8]
        ]
        issues.append(
            TriageIssue(
                issue_id="triage_document_level_context",
                severity="medium",
                category="context",
                title="Evidence fell back to document-level or low-confidence context",
                summary=(
                    f"{len(document_context)} evidence item(s) lack a strong table, curve, section, or drawing context. "
                    "Cross-document alignment will over-rely on subject strings."
                ),
                evidence=examples,
                metrics={"document_context_evidence": len(document_context), "evidence": len(evidence)},
                suggested_next_step="Improve section/table/curve segmentation before loosening match rules.",
            )
        )
    if generic_subjects:
        examples = [
            f"{item.get('evidence_id')} {item.get('doc_id')} p{item.get('page')} "
            f"kind={item.get('kind')} parameter={item.get('parameter')} quote={_clip(item.get('raw_text') or '')}"
            for item in generic_subjects[:8]
        ]
        issues.append(
            TriageIssue(
                issue_id="triage_generic_subjects",
                severity="medium",
                category="subject_resolution",
                title="Evidence has generic or missing subjects",
                summary=(
                    f"{len(generic_subjects)} evidence item(s) have no useful equipment/reference subject. "
                    "This is usually an extraction/context problem, not a matcher problem."
                ),
                evidence=examples,
                metrics={"generic_subject_evidence": len(generic_subjects), "evidence": len(evidence)},
                suggested_next_step="Use context rooms and nearby labels to attach claims to a stable subject, then rerun eval.",
            )
        )
    rooms = context_memory.get("rooms", [])
    trails = context_memory.get("trails", [])
    if metrics.get("findings", 0) and not trails:
        issues.append(
            TriageIssue(
                issue_id="triage_findings_without_memory_trails",
                severity="low",
                category="context_memory",
                title="Findings are not represented as memory trails",
                summary="The run has findings but no memory trails, weakening reviewer navigation.",
                metrics={"context_rooms": len(rooms), "context_trails": len(trails)},
                suggested_next_step="Inspect context_memory.json generation and preserve finding-to-room links.",
            )
        )
    return issues


def _reasoning_issues(
    findings: list[dict[str, Any]], traces: list[dict[str, Any]], reasoning: dict[str, Any], metrics: dict[str, Any]
) -> list[TriageIssue]:
    issues: list[TriageIssue] = []
    non_coverage_findings = [item for item in findings if item.get("finding_type") != "coverage_warning"]
    absence_only = [
        item
        for item in non_coverage_findings
        if item.get("absence_id") and not item.get("alignment_id") and not item.get("comparison_id")
    ]
    if non_coverage_findings and len(absence_only) == len(non_coverage_findings):
        examples = [
            f"{item.get('finding_id')} subject={item.get('subject')} parameter={item.get('parameter')} "
            f"absence={item.get('absence_id')}"
            for item in absence_only[:8]
        ]
        issues.append(
            TriageIssue(
                issue_id="triage_absence_only_review",
                severity="high",
                category="reasoning",
                title="Review produced only absence-search findings",
                summary=(
                    "All non-coverage findings came from absence search, with no accepted alignments or comparisons. "
                    "This is weak for cross-document review because it cannot prove value-level disagreement."
                ),
                evidence=examples,
                metrics={
                    "non_coverage_findings": len(non_coverage_findings),
                    "absence_only_findings": len(absence_only),
                    "alignment_decisions": len(reasoning.get("alignments", [])),
                    "comparison_decisions": len(reasoning.get("comparisons", [])),
                },
                suggested_next_step="Improve subject aliases/context extraction until at least key expected claims align across docs.",
            )
        )
    elif absence_only:
        issues.append(
            TriageIssue(
                issue_id="triage_some_absence_only_findings",
                severity="medium",
                category="reasoning",
                title="Some findings are absence-search only",
                summary=(
                    f"{len(absence_only)} non-coverage finding(s) lack alignment/comparison support. "
                    "They may still be valid missing-item findings, but they deserve reviewer attention."
                ),
                evidence=[
                    f"{item.get('finding_id')} subject={item.get('subject')} parameter={item.get('parameter')}"
                    for item in absence_only[:8]
                ],
                metrics={"absence_only_findings": len(absence_only), "non_coverage_findings": len(non_coverage_findings)},
                suggested_next_step="Check whether these are true checklist gaps or missed aliases/context matches.",
            )
        )
    if non_coverage_findings and metrics.get("comparison_decisions", 0) == 0:
        issues.append(
            TriageIssue(
                issue_id="triage_no_value_comparisons",
                severity="high",
                category="reasoning",
                title="No value comparison decisions were made",
                summary=(
                    "The run found non-coverage issues but performed zero value comparisons. "
                    "Version review and cross-document review both need comparison coverage for accuracy."
                ),
                metrics={
                    "findings": metrics.get("findings", len(findings)),
                    "comparison_decisions": metrics.get("comparison_decisions", 0),
                    "alignment_decisions": metrics.get("alignment_decisions", 0),
                },
                suggested_next_step="Triage why claims did not align: subject aliases, parameter names, context labels, or missing extraction.",
            )
        )
    downgraded = [trace for trace in traces if trace.get("downgrade_reasons")]
    if downgraded:
        issues.append(
            TriageIssue(
                issue_id="triage_downgraded_decisions",
                severity="medium",
                category="verification",
                title="Decision traces include downgrades",
                summary=f"{len(downgraded)} finding trace(s) were downgraded or caveated by the verifier ledger.",
                evidence=[
                    f"{trace.get('finding_id')}: {'; '.join(trace.get('downgrade_reasons') or [])}"
                    for trace in downgraded[:8]
                ],
                metrics={"decision_traces_with_downgrades": len(downgraded), "decision_traces": len(traces)},
                suggested_next_step="Inspect downgrade reasons before treating these as high-confidence engineering discrepancies.",
            )
        )
    return issues


def _finding_trace_issues(
    findings: list[dict[str, Any]], traces: list[dict[str, Any]], metrics: dict[str, Any]
) -> list[TriageIssue]:
    finding_ids = {item.get("finding_id") for item in findings}
    trace_ids = {item.get("finding_id") for item in traces}
    missing_traces = sorted(str(item) for item in finding_ids - trace_ids if item)
    if not missing_traces:
        return []
    return [
        TriageIssue(
            issue_id="triage_findings_missing_decision_traces",
            severity="high",
            category="explainability",
            title="Findings are missing decision traces",
            summary="Every published finding should have a traceable signal ledger.",
            evidence=missing_traces[:12],
            metrics={"findings": metrics.get("findings", len(findings)), "decision_traces": len(traces)},
            suggested_next_step="Fix decision trace generation before using the run for demo or evaluation.",
        )
    ]


def _next_actions(issues: list[TriageIssue]) -> list[str]:
    if not issues:
        return ["No structural triage issues found. Add real-corpus eval cases or inspect report.md for reviewer wording."]
    actions: list[str] = []
    by_id = {issue.issue_id for issue in issues}
    if "triage_weak_extraction_pages" in by_id:
        actions.append("Prioritize OCR/VLM extraction for listed weak pages; compare evidence counts and coverage warnings.")
    if "triage_absence_only_review" in by_id or "triage_no_value_comparisons" in by_id:
        actions.append("Prioritize subject/context alignment before adding more finding types.")
    if "triage_document_level_context" in by_id or "triage_generic_subjects" in by_id:
        actions.append("Improve context segmentation and subject attachment using tables, section headers, and nearby labels.")
    if "triage_downgraded_decisions" in by_id:
        actions.append("Inspect downgraded traces and decide whether eval should expect possible_issue instead of review_required.")
    if "triage_findings_missing_decision_traces" in by_id:
        actions.append("Repair trace generation before demo; explainability is part of the MVP contract.")
    return actions


def _load_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return read_artifact(path).get("metrics", {})


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = read_artifact(path)
    records = payload.get("records")
    return records if isinstance(records, list) else []


def _load_reasoning(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    path = run_dir / "reasoning_graph.json"
    if not path.exists():
        return {"alignments": [], "comparisons": [], "absence_searches": []}
    payload = read_artifact(path)
    return {
        "alignments": payload.get("alignments", []),
        "comparisons": payload.get("comparisons", []),
        "absence_searches": payload.get("absence_searches", []),
    }


def _load_context_memory(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    path = run_dir / "context_memory.json"
    if not path.exists():
        return {"rooms": [], "trails": []}
    payload = read_artifact(path)
    return {"rooms": payload.get("rooms", []), "trails": payload.get("trails", [])}


def _clip(text: str, limit: int = 90) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."
