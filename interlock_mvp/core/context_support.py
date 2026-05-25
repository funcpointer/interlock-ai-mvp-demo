from __future__ import annotations

from .contexts import align_context_label
from .models import ContextSupport, DiffEdge, DocumentGraph, EvidenceItem
from .normalization import normalize_key


def build_context_supports(
    *,
    diff_edges: list[DiffEdge],
    evidence_by_id: dict[str, EvidenceItem],
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    search_records: list[dict[str, object]],
) -> list[ContextSupport]:
    contexts = {context.context_id: context for context in [*doc_graph_a.contexts, *doc_graph_b.contexts]}
    support_records: list[ContextSupport] = []
    for index, edge in enumerate(diff_edges, start=1):
        cited = [evidence_by_id[eid] for eid in edge.evidence_ids if eid in evidence_by_id]
        context_ids = _dedup([item.context_id for item in cited if item.context_id])
        signal_types: list[str] = []
        downgrade_reasons: list[str] = []

        missing_context = not context_ids or any(_is_generic_context(contexts.get(context_id)) for context_id in context_ids)
        if missing_context:
            signal_types.append("missing_context")
            downgrade_reasons.append("cited evidence is in generic or missing document context")
        else:
            signal_types.append("context_room")

        if len(_non_generic_contexts_by_doc(cited, contexts)) >= 2:
            signal_types.append("graph_alignment")

        search_hits = _supporting_search_hits(edge, search_records)
        if search_hits:
            signal_types.append("search_hit")

        possible_equivalents = _possible_equivalent_hits(edge, cited, search_records)
        if possible_equivalents:
            signal_types.append("possible_equivalent_elsewhere")
            downgrade_reasons.append("search found possible equivalent evidence elsewhere in the packet")

        if possible_equivalents:
            supports_diff = False
            confidence = "medium"
        elif missing_context:
            supports_diff = False
            confidence = "low"
        elif "graph_alignment" in signal_types and "search_hit" in signal_types:
            supports_diff = True
            confidence = "high"
        elif "graph_alignment" in signal_types or "search_hit" in signal_types:
            supports_diff = True
            confidence = "medium"
        else:
            supports_diff = False
            confidence = "low"

        supports_obj = ContextSupport(
            support_id=f"ctx{index:05d}",
            diff_id=edge.diff_id,
            supports=supports_diff,
            confidence=confidence,
            signal_types=_dedup(signal_types),
            context_ids=context_ids,
            search_ids=_dedup([*search_hits, *possible_equivalents])[:12],
            summary=_summary(supports_diff, confidence, signal_types, context_ids, search_hits, possible_equivalents),
            downgrade_reasons=_dedup(downgrade_reasons),
        )
        support_records.append(supports_obj)
    return support_records


def _is_generic_context(context: object | None) -> bool:
    if not context:
        return True
    label = align_context_label(str(getattr(context, "canonical_label", "document")))
    return label == "document" or str(getattr(context, "confidence", "low")) == "low"


def _non_generic_contexts_by_doc(cited: list[EvidenceItem], contexts: dict[str, object]) -> set[str]:
    return {item.doc_id for item in cited if item.context_id and not _is_generic_context(contexts.get(item.context_id))}


def _supporting_search_hits(edge: DiffEdge, search_records: list[dict[str, object]]) -> list[str]:
    subject = normalize_key(edge.subject)
    parameter = normalize_key(edge.parameter)
    hits = []
    for record in search_records:
        if record.get("source") not in {"evidence", "claim", "context", "context_room", "subject"}:
            continue
        record_subject = normalize_key(str(record.get("subject", "")))
        record_parameter = normalize_key(str(record.get("parameter", "")))
        record_text = normalize_key(str(record.get("text", "")))
        if parameter and parameter not in {record_parameter, ""} and parameter not in record_text:
            continue
        if subject and subject not in record_subject and subject not in record_text:
            continue
        search_id = str(record.get("search_id", ""))
        if search_id:
            hits.append(search_id)
    return hits[:8]


def _possible_equivalent_hits(edge: DiffEdge, cited: list[EvidenceItem], search_records: list[dict[str, object]]) -> list[str]:
    if edge.diff_type != "value_mismatch" or len(cited) < 2:
        return []
    cited_ids = {item.evidence_id for item in cited}
    values_by_doc = {item.doc_id: (_value_key(item.value), normalize_key(item.parameter), normalize_key(item.subject)) for item in cited}
    hits = []
    for record in search_records:
        if record.get("source") != "evidence":
            continue
        record_id = str(record.get("record_id", ""))
        if record_id in cited_ids:
            continue
        doc_id = str(record.get("doc_id", ""))
        opposite = "A" if doc_id == "B" else "B" if doc_id == "A" else ""
        if opposite not in values_by_doc:
            continue
        expected_value, expected_parameter, expected_subject = values_by_doc[opposite]
        if _value_key(str(record.get("value", ""))) != expected_value:
            continue
        if normalize_key(str(record.get("parameter", ""))) != expected_parameter:
            continue
        record_subject = normalize_key(str(record.get("subject", "")))
        if expected_subject and expected_subject not in record_subject and record_subject not in expected_subject:
            continue
        search_id = str(record.get("search_id", ""))
        if search_id:
            hits.append(search_id)
    return hits[:4]


def _value_key(value: str) -> str:
    return normalize_key(value).replace("-", "")


def _summary(
    supports: bool,
    confidence: str,
    signal_types: list[str],
    context_ids: list[str],
    search_hits: list[str],
    possible_equivalents: list[str],
) -> str:
    verdict = "supports" if supports else "does not independently support"
    parts = [
        f"Context quorum {verdict} this diff with {confidence} confidence.",
        f"Signals: {', '.join(_dedup(signal_types)) or 'none'}.",
    ]
    if context_ids:
        parts.append(f"Contexts: {', '.join(context_ids[:4])}.")
    if search_hits:
        parts.append(f"Search hits: {len(search_hits)}.")
    if possible_equivalents:
        parts.append(f"Possible equivalent elsewhere: {len(possible_equivalents)}.")
    return " ".join(parts)


def _dedup(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
