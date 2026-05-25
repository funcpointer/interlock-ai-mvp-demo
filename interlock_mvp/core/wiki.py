from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .models import ContextMemory, ContextRoom, DiffGraph, DocumentGraph, DocumentRecord, Finding, ReasoningGraph


def write_review_wiki(
    run_dir: Path,
    *,
    documents: list[DocumentRecord],
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    diff_graph: DiffGraph,
    reasoning_graph: ReasoningGraph,
    context_memory: ContextMemory | None = None,
    findings: list[Finding],
    metrics: dict[str, object],
    warnings: list[str],
) -> int:
    wiki_dir = run_dir / "wiki"
    (wiki_dir / "documents").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "subjects").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "context-rooms").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "findings").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "reasoning").mkdir(parents=True, exist_ok=True)

    written = 0
    _write(wiki_dir / "index.md", _index_lines(documents, findings, metrics, warnings))
    written += 1
    _write(wiki_dir / "log.md", _log_lines(documents, findings, metrics, warnings))
    written += 1
    _write(wiki_dir / "review-map.md", _review_map_lines(doc_graph_a, doc_graph_b, diff_graph, reasoning_graph))
    written += 1
    if context_memory:
        _write(wiki_dir / "memory-palace.md", _memory_palace_lines(context_memory))
        written += 1

    for document in documents:
        _write(wiki_dir / "documents" / f"{document.doc_id}.md", _document_lines(document, doc_graph_a, doc_graph_b))
        written += 1
    for finding in findings:
        _write(wiki_dir / "findings" / f"{_slug(finding.finding_id)}.md", _finding_lines(finding))
        written += 1
    for subject_id, lines in _subject_pages(doc_graph_a, doc_graph_b, findings).items():
        _write(wiki_dir / "subjects" / f"{_slug(subject_id)}.md", lines)
        written += 1
    if context_memory:
        for room in context_memory.rooms:
            _write(wiki_dir / "context-rooms" / f"{_slug(room.room_id)}.md", _context_room_lines(room))
            written += 1
    _write(wiki_dir / "reasoning" / "decisions.md", _reasoning_lines(reasoning_graph))
    written += 1
    return written


def _index_lines(
    documents: list[DocumentRecord],
    findings: list[Finding],
    metrics: dict[str, object],
    warnings: list[str],
) -> list[str]:
    lines = [
        "# Review Wiki",
        "",
        "This derived wiki is a compiled memory layer over canonical JSON artifacts. It is for review, navigation, and future LLM context; JSON remains source of truth.",
        "",
        "## Start Here",
        "",
        f"- {_md_link('review-map', 'Review Map')}",
        f"- {_md_link('memory-palace', 'Memory Palace')}",
        f"- {_md_link('log', 'Run Log')}",
        f"- {_md_link('reasoning/decisions', 'Reasoning Decisions')}",
        "- `../findings.json`",
        "- `../reasoning_graph.json`",
        "- `../search/review_map.jsonl`",
        "",
        "## Documents",
        "",
    ]
    for document in documents:
        lines.append(f"- {_md_link(f'documents/{document.doc_id}', f'Doc {document.doc_id}')}: `{document.doc_type}` / `{document.mode_role}`")
    lines.extend(["", "## Findings", ""])
    if findings:
        for finding in findings:
            lines.append(
                f"- {_md_link(f'findings/{_slug(finding.finding_id)}', finding.finding_id)}: `{finding.finding_type}` `{finding.severity}` - {finding.subject} / {finding.parameter}"
            )
    else:
        lines.append("- No findings.")
    lines.extend(["", "## Health", ""])
    for key in [
        "findings",
        "review_required_findings",
        "coverage_warning_findings",
        "alignment_decisions",
        "comparison_decisions",
        "absence_searches",
        "search_records",
    ]:
        if key in metrics:
            lines.append(f"- `{key}`: {metrics[key]}")
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return lines


def _log_lines(
    documents: list[DocumentRecord],
    findings: list[Finding],
    metrics: dict[str, object],
    warnings: list[str],
) -> list[str]:
    stamp = datetime.now(UTC).isoformat()
    return [
        "# Run Log",
        "",
        f"## [{stamp}] review | {documents[0].path if documents else 'A'} vs {documents[1].path if len(documents) > 1 else 'B'}",
        "",
        f"- Findings: {len(findings)}",
        f"- Review required: {sum(1 for finding in findings if finding.severity == 'review_required')}",
        f"- Coverage warnings: {sum(1 for finding in findings if finding.finding_type == 'coverage_warning')}",
        f"- Search records: {metrics.get('search_records', 'unknown')}",
        f"- Warnings: {len(warnings)}",
        "",
    ]


def _review_map_lines(
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    diff_graph: DiffGraph,
    reasoning_graph: ReasoningGraph,
) -> list[str]:
    lines = [
        "# Review Map",
        "",
        "## Graph Counts",
        "",
        f"- Doc A contexts: {len(doc_graph_a.contexts)}",
        f"- Doc A subjects: {len(doc_graph_a.subjects)}",
        f"- Doc A claims: {len(doc_graph_a.claims)}",
        f"- Doc B contexts: {len(doc_graph_b.contexts)}",
        f"- Doc B subjects: {len(doc_graph_b.subjects)}",
        f"- Doc B claims: {len(doc_graph_b.claims)}",
        f"- Diff edges: {len(diff_graph.edges)}",
        f"- Alignment decisions: {len(reasoning_graph.alignments)}",
        f"- Comparison decisions: {len(reasoning_graph.comparisons)}",
        f"- Absence searches: {len(reasoning_graph.absence_searches)}",
        f"- Context supports: {len(reasoning_graph.context_supports)}",
        "",
        "## Diff Edges",
        "",
    ]
    for edge in diff_graph.edges[:100]:
        lines.append(f"- `{edge.diff_id}` `{edge.diff_type}` `{edge.alignment_status}`: {edge.subject} / {edge.parameter} - {edge.rationale}")
    if len(diff_graph.edges) > 100:
        lines.append(f"- ... {len(diff_graph.edges) - 100} more in `../diff_graph.json`")
    lines.append("")
    return lines


def _memory_palace_lines(context_memory: ContextMemory) -> list[str]:
    lines = [
        "# Memory Palace",
        "",
        "Each room is a document context: a table, curve, spec section, page-level fallback, or other review location. Trails connect rooms through findings.",
        "",
        "## High-Salience Rooms",
        "",
    ]
    for room in sorted(context_memory.rooms, key=lambda item: (-item.salience_score, item.doc_id, item.page_span[0] if item.page_span else 0))[:80]:
        lines.append(
            f"- {_md_link(f'context-rooms/{_slug(room.room_id)}', room.canonical_label)} `{room.doc_id}` `{room.kind}` salience={room.salience_score}: {room.summary}"
        )
    lines.extend(["", "## Trails", ""])
    if context_memory.trails:
        for trail in context_memory.trails:
            rooms = ", ".join(_md_link(f"context-rooms/{_slug(room_id)}", room_id) for room_id in trail.room_ids)
            lines.append(f"- `{trail.trail_id}` {trail.name}: {rooms or 'no linked rooms'}")
    else:
        lines.append("- No trails.")
    lines.append("")
    return lines


def _document_lines(document: DocumentRecord, doc_graph_a: DocumentGraph, doc_graph_b: DocumentGraph) -> list[str]:
    graph = doc_graph_a if document.doc_id == doc_graph_a.doc_id else doc_graph_b
    lines = [
        f"# Document {document.doc_id}",
        "",
        f"- Path: `{document.path}`",
        f"- SHA256: `{document.sha256}`",
        f"- Page count: {document.page_count}",
        f"- Doc type: `{document.doc_type}`",
        f"- Mode role: `{document.mode_role}`",
        "",
        "## Contexts",
        "",
    ]
    for context in graph.contexts[:80]:
        lines.append(f"- `{context.context_id}` `{context.kind}` pages {context.page_span}: {context.canonical_label}")
    if len(graph.contexts) > 80:
        lines.append(f"- ... {len(graph.contexts) - 80} more in `../doc_graph_{document.doc_id.lower()}.json`")
    lines.extend(["", "## Subjects", ""])
    for subject in graph.subjects[:120]:
        lines.append(f"- {_md_link(f'../subjects/{_slug(subject.subject_id)}', subject.canonical_label)} `{subject.kind}` `{subject.confidence}`")
    if len(graph.subjects) > 120:
        lines.append(f"- ... {len(graph.subjects) - 120} more in `../doc_graph_{document.doc_id.lower()}.json`")
    lines.append("")
    return lines


def _finding_lines(finding: Finding) -> list[str]:
    lines = [
        f"# {_finding_title(finding)}",
        "",
        f"- Finding id: `{finding.finding_id}`",
        f"- Type: `{finding.finding_type}`",
        f"- Severity: `{finding.severity}`",
        f"- Confidence: `{finding.confidence}`",
        f"- Authority: `{finding.authoritative_side}` ({finding.authority_basis}, confidence {finding.authority_confidence:.2f})",
        f"- Summary: {finding.summary}",
        f"- Verifier notes: {finding.verifier_notes}",
        f"- Alignment decision: `{finding.alignment_id or ''}`",
        f"- Comparison decision: `{finding.comparison_id or ''}`",
        f"- Absence search: `{finding.absence_id or ''}`",
        "",
    ]
    if finding.context_support_summary:
        lines.extend(_finding_context_support_lines(finding))
        lines.append("")
    if finding.model_review_status == "used":
        lines.extend(_finding_model_review_lines(finding))
        lines.append("")
    lines.extend(["## Citations", ""])
    if finding.evidence_a:
        lines.extend(_citation_lines("Doc A", finding.evidence_a))
    if finding.evidence_b:
        lines.extend(_citation_lines("Doc B", finding.evidence_b))
    if finding.plausibility_notes:
        lines.extend(["", "## Plausibility", ""])
        lines.extend(f"- {note}" for note in finding.plausibility_notes)
    lines.append("")
    return lines


def _finding_context_support_lines(finding: Finding) -> list[str]:
    verdict = "strong alignment" if finding.context_support_supports else "context caution"
    signals = "; ".join(_context_signal_label(signal) for signal in finding.context_support_signal_types)
    return [
        "## Citation Pairing Context",
        "",
        f"- Support id: `{finding.context_support_id or ''}`",
        f"- Verdict: {verdict}",
        f"- Confidence: `{finding.context_support_confidence or 'unknown'}`",
        "- Note: this explains why the cited evidence was compared; it is not proof by itself.",
        f"- Signals: {signals or 'none'}",
        f"- Summary: {finding.context_support_summary}",
    ]


def _context_signal_label(signal: str) -> str:
    return {
        "context_room": "same section/table type",
        "graph_alignment": "document graph aligned the claims",
        "search_hit": "related evidence found in packet search",
        "missing_context": "generic or missing context",
        "possible_equivalent_elsewhere": "possible equivalent evidence elsewhere",
    }.get(signal, signal.replace("_", " "))


def _finding_model_review_lines(finding: Finding) -> list[str]:
    verdict = "supports the cited finding" if finding.model_review_supports else "adds caution for reviewer inspection"
    lines = [
        "## External Model Advisory Review",
        "",
        f"- Model: `{finding.model_review_model}`",
        f"- Verdict: {verdict}",
        "- Note: advisory only; source citations and deterministic comparison remain required.",
        f"- Summary: {finding.model_review_summary}",
    ]
    if finding.model_review_cautions:
        lines.append(f"- Cautions: {'; '.join(finding.model_review_cautions)}")
    return lines


def _context_room_lines(room: ContextRoom) -> list[str]:
    lines = [
        f"# {room.canonical_label}",
        "",
        f"- Room id: `{room.room_id}`",
        f"- Context id: `{room.context_id}`",
        f"- Doc: `{room.doc_id}`",
        f"- Kind: `{room.kind}`",
        f"- Pages: `{room.page_span}`",
        f"- Salience: {room.salience_score}",
        f"- Summary: {room.summary}",
        "",
        "## Neighbor Rooms",
        "",
    ]
    if room.neighboring_room_ids:
        lines.extend(f"- {_md_link(_slug(room_id), room_id)}" for room_id in room.neighboring_room_ids)
    else:
        lines.append("- No neighboring rooms.")
    lines.extend(["", "## Subjects", ""])
    lines.extend(f"- `{subject_id}`" for subject_id in room.subject_ids) if room.subject_ids else lines.append("- No subjects.")
    lines.extend(["", "## Claims", ""])
    lines.extend(f"- `{claim_id}`" for claim_id in room.claim_ids) if room.claim_ids else lines.append("- No claims.")
    lines.extend(["", "## Findings", ""])
    lines.extend(f"- {_md_link(f'../findings/{_slug(finding_id)}', finding_id)}" for finding_id in room.finding_ids) if room.finding_ids else lines.append("- No linked findings.")
    lines.extend(["", "## Evidence", ""])
    lines.extend(f"- `{evidence_id}`" for evidence_id in room.evidence_ids[:120]) if room.evidence_ids else lines.append("- No evidence.")
    if len(room.evidence_ids) > 120:
        lines.append(f"- ... {len(room.evidence_ids) - 120} more evidence records in `../evidence.json`")
    lines.append("")
    return lines


def _citation_lines(label: str, citation) -> list[str]:
    return [
        f"### {label}",
        "",
        f"- Evidence: `{citation.evidence_id}`",
        f"- Page: {citation.page}",
        f"- BBox: `{citation.bbox}`",
        f"- Crop: `{citation.crop_path}`",
        f"- Value: `{citation.value}` `{citation.unit}`",
        f"- Quote: `{_clip(citation.quote)}`",
        "",
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


def _subject_pages(doc_graph_a: DocumentGraph, doc_graph_b: DocumentGraph, findings: list[Finding]) -> dict[str, list[str]]:
    pages: dict[str, list[str]] = {}
    for graph in [doc_graph_a, doc_graph_b]:
        claims_by_subject: dict[str, list[str]] = {}
        for claim in graph.claims:
            claims_by_subject.setdefault(claim.subject_id, []).append(
                f"- `{claim.claim_id}` {claim.parameter}: `{claim.value}` `{claim.unit}` from evidence {', '.join(claim.evidence_ids)}"
            )
        for subject in graph.subjects:
            linked_findings = [
                finding
                for finding in findings
                if finding.subject.lower() in subject.canonical_label.lower() or subject.canonical_label.lower() in finding.subject.lower()
            ]
            lines = [
                f"# {subject.canonical_label}",
                "",
                f"- Subject id: `{subject.subject_id}`",
                f"- Doc: `{subject.doc_id}`",
                f"- Kind: `{subject.kind}`",
                f"- Confidence: `{subject.confidence}`",
                f"- Contexts: `{', '.join(subject.context_ids)}`",
                f"- Raw labels: `{', '.join(subject.raw_labels)}`",
                "",
                "## Claims",
                "",
                *(claims_by_subject.get(subject.subject_id) or ["- No claims."]),
                "",
                "## Findings",
                "",
            ]
            if linked_findings:
                lines.extend(f"- {_md_link(f'../findings/{_slug(finding.finding_id)}', finding.finding_id)} {finding.parameter}" for finding in linked_findings)
            else:
                lines.append("- No linked findings.")
            lines.append("")
            pages[subject.subject_id] = lines
    return pages


def _reasoning_lines(reasoning_graph: ReasoningGraph) -> list[str]:
    lines = ["# Reasoning Decisions", "", "## Alignments", ""]
    for alignment in reasoning_graph.alignments[:120]:
        lines.append(
            f"- `{alignment.alignment_id}` accepted={alignment.accepted} confidence=`{alignment.confidence}` subject=`{alignment.subject_method}` parameter=`{alignment.parameter_method}` context=`{alignment.context_method}`"
        )
    lines.extend(["", "## Comparisons", ""])
    for comparison in reasoning_graph.comparisons[:120]:
        lines.append(
            f"- `{comparison.comparison_id}` type=`{comparison.comparison_type}` unit=`{comparison.unit_method}` deterministic={comparison.deterministic}: {comparison.rationale}"
        )
    lines.extend(["", "## Absence Searches", ""])
    for absence in reasoning_graph.absence_searches[:120]:
        lines.append(
            f"- `{absence.absence_id}` searched_doc=`{absence.searched_doc_id}` coverage=`{absence.coverage_status}` confidence=`{absence.confidence}` terms=`{', '.join(absence.query_terms)}`"
        )
    lines.extend(["", "## Context Support", ""])
    for support in reasoning_graph.context_supports[:120]:
        lines.append(
            f"- `{support.support_id}` diff=`{support.diff_id}` supports={support.supports} confidence=`{support.confidence}` signals=`{', '.join(support.signal_types)}`: {support.summary}"
        )
    lines.append("")
    return lines


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "item"


def _md_link(target: str, label: str) -> str:
    path = target if target.endswith(".md") else f"{target}.md"
    return f"[{label}]({path})"


def _clip(text: str, limit: int = 320) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."
