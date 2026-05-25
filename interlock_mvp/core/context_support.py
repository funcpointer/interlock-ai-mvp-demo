from __future__ import annotations

from .contexts import align_context_label
from .models import ContextReference, ContextSupport, DiffEdge, DocumentGraph, EvidenceItem, SearchReference
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

        search_hit_records = _supporting_search_records(edge, search_records)
        search_hits = [str(record.get("search_id", "")) for record in search_hit_records if record.get("search_id")]
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
            context_refs=_context_refs(context_ids, contexts),
            search_refs=_search_refs([*search_hit_records, *_records_by_search_id(possible_equivalents, search_records)], edge),
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


def _supporting_search_records(edge: DiffEdge, search_records: list[dict[str, object]]) -> list[dict[str, object]]:
    subject = normalize_key(edge.subject)
    parameter = normalize_key(edge.parameter)
    hits: list[dict[str, object]] = []
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
        if record.get("search_id"):
            hits.append(record)
    return hits[:8]


def _records_by_search_id(search_ids: list[str], search_records: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id = {str(record.get("search_id", "")): record for record in search_records}
    return [by_id[search_id] for search_id in search_ids if search_id in by_id]


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
    verdict = "Aligned cited context" if supports else "Weak cited context"
    parts = [
        f"{verdict} ({confidence} confidence).",
    ]
    if context_ids:
        parts.append(f"Sections: {', '.join(context_ids[:4])}.")
    if search_hits:
        parts.append(f"Related hits: {len(search_hits)}.")
    if possible_equivalents:
        parts.append(f"Possible equivalent elsewhere: {len(possible_equivalents)}.")
    return " ".join(parts)


def _context_refs(context_ids: list[str], contexts: dict[str, object]) -> list[ContextReference]:
    refs: list[ContextReference] = []
    for context_id in context_ids[:4]:
        context = contexts.get(context_id)
        refs.append(
            ContextReference(
                context_id=context_id,
                doc_id=str(getattr(context, "doc_id", context_id.split(":", 1)[0] if ":" in context_id else "")),
                label=str(getattr(context, "canonical_label", context_id.split(":", 1)[-1])).replace("_", " "),
                kind=str(getattr(context, "kind", "")),
                pages=list(getattr(context, "page_span", []) or []),
            )
        )
    return refs


def _search_refs(records: list[dict[str, object]], edge: DiffEdge) -> list[SearchReference]:
    refs: list[SearchReference] = []
    seen = set()
    seen_content = set()
    for record in sorted(records, key=_search_ref_rank):
        search_id = str(record.get("search_id", ""))
        if not search_id or search_id in seen:
            continue
        source = str(record.get("source", ""))
        if source not in {"evidence", "claim"}:
            continue
        if normalize_key(str(record.get("parameter", ""))) != normalize_key(edge.parameter):
            continue
        content_key = (
            str(record.get("doc_id", "")),
            normalize_key(str(record.get("quote", ""))),
            normalize_key(str(record.get("value", ""))),
            normalize_key(str(record.get("unit", ""))),
        )
        if content_key in seen_content:
            continue
        seen.add(search_id)
        seen_content.add(content_key)
        refs.append(
            SearchReference(
                search_id=search_id,
                source=source,
                doc_id=str(record.get("doc_id", "") or ""),
                page=int(record["page"]) if record.get("page") is not None else None,
                context_id=str(record.get("context_id", "") or ""),
                subject=str(record.get("subject", "") or ""),
                parameter=str(record.get("parameter", "") or ""),
                value=str(record.get("value", "") or ""),
                unit=str(record.get("unit", "") or ""),
                quote=str(record.get("quote", "") or ""),
            )
        )
        if len(refs) >= 4:
            break
    return refs


def _search_ref_rank(record: dict[str, object]) -> tuple[int, str, int, str]:
    source_rank = {"evidence": 0, "claim": 1, "context": 2, "context_room": 3, "subject": 4}
    return (
        source_rank.get(str(record.get("source", "")), 9),
        str(record.get("doc_id", "")),
        int(record.get("page") or 0),
        str(record.get("search_id", "")),
    )


def _dedup(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
