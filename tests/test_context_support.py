from interlock_mvp.core.context_support import build_context_supports
from interlock_mvp.core.models import ContextNode, DiffEdge, DocumentGraph, EvidenceItem


def test_high_context_support_when_both_sides_have_context_and_search_hit() -> None:
    support = build_context_supports(
        diff_edges=[_edge("diff00001", ["a1", "b1"])],
        evidence_by_id={
            "a1": _evidence("a1", "A", "A:ctx:ratings", "1000"),
            "b1": _evidence("b1", "B", "B:ctx:ratings", "100"),
        },
        doc_graph_a=_graph("A", "A:ctx:ratings", "capacity_ratings"),
        doc_graph_b=_graph("B", "B:ctx:ratings", "capacity_ratings"),
        search_records=[_search("claim:b1", "claim", "B", "XFMR", "rating", "100")],
    )[0]

    assert support.supports is True
    assert support.confidence == "high"
    assert "context_room" in support.signal_types
    assert "graph_alignment" in support.signal_types
    assert "search_hit" in support.signal_types


def test_low_context_support_when_context_is_generic_document() -> None:
    support = build_context_supports(
        diff_edges=[_edge("diff00001", ["a1", "b1"])],
        evidence_by_id={
            "a1": _evidence("a1", "A", "A:document", "1000"),
            "b1": _evidence("b1", "B", "B:document", "100"),
        },
        doc_graph_a=_graph("A", "A:document", "document", confidence="low"),
        doc_graph_b=_graph("B", "B:document", "document", confidence="low"),
        search_records=[_search("claim:b1", "claim", "B", "XFMR", "rating", "100")],
    )[0]

    assert support.supports is False
    assert support.confidence == "low"
    assert "missing_context" in support.signal_types
    assert support.downgrade_reasons


def test_search_hit_can_support_single_sided_context_at_medium_confidence() -> None:
    support = build_context_supports(
        diff_edges=[_edge("diff00001", ["a1"])],
        evidence_by_id={"a1": _evidence("a1", "A", "A:ctx:ratings", "1000")},
        doc_graph_a=_graph("A", "A:ctx:ratings", "capacity_ratings"),
        doc_graph_b=_graph("B", "B:ctx:document", "document"),
        search_records=[_search("context:ratings", "context_room", "A", "XFMR", "rating", "capacity ratings")],
    )[0]

    assert support.supports is True
    assert support.confidence == "medium"
    assert "search_hit" in support.signal_types


def test_search_hit_does_not_count_the_diff_record_itself() -> None:
    support = build_context_supports(
        diff_edges=[_edge("diff00001", ["a1"])],
        evidence_by_id={"a1": _evidence("a1", "A", "A:ctx:ratings", "1000")},
        doc_graph_a=_graph("A", "A:ctx:ratings", "capacity_ratings"),
        doc_graph_b=_graph("B", "B:ctx:document", "document"),
        search_records=[_search("diff:diff00001", "diff", "", "XFMR", "rating", "value_mismatch")],
    )[0]

    assert support.supports is False
    assert "search_hit" not in support.signal_types


def test_possible_equivalent_elsewhere_is_a_downgrade_signal() -> None:
    support = build_context_supports(
        diff_edges=[_edge("diff00001", ["a1", "b1"])],
        evidence_by_id={
            "a1": _evidence("a1", "A", "A:ctx:ratings", "1000"),
            "b1": _evidence("b1", "B", "B:ctx:ratings", "100"),
        },
        doc_graph_a=_graph("A", "A:ctx:ratings", "capacity_ratings"),
        doc_graph_b=_graph("B", "B:ctx:ratings", "capacity_ratings"),
        search_records=[
            _search("evidence:b2", "evidence", "B", "XFMR", "rating", "1000", record_id="b2"),
        ],
    )[0]

    assert support.supports is False
    assert support.confidence == "medium"
    assert "possible_equivalent_elsewhere" in support.signal_types
    assert support.search_ids == ["evidence:b2"]
    assert support.downgrade_reasons


def _edge(diff_id: str, evidence_ids: list[str]) -> DiffEdge:
    return DiffEdge(
        diff_id=diff_id,
        diff_type="value_mismatch",
        alignment_status="conflict",
        subject="XFMR",
        parameter="rating",
        rationale="A differs from B.",
        evidence_ids=evidence_ids,
        identity_strength="medium",
        deterministic_discrepancy=True,
    )


def _evidence(evidence_id: str, doc_id: str, context_id: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=1,
        bbox=[1, 2, 3, 4],
        region_id=f"r{evidence_id}",
        kind="parameter_value",
        subject="XFMR",
        parameter="rating",
        value=value,
        unit="KVA",
        raw_text=f"{value} KVA XFMR",
        normalized_text=f"{value} kva xfmr",
        normalized_value=f"{value} KVA",
        confidence="high",
        source_method="test",
        crop_path=f"crops/{evidence_id}.png",
        context_id=context_id,
        context_confidence="high" if "document" not in context_id else "low",
    )


def _graph(doc_id: str, context_id: str, label: str, *, confidence: str = "high") -> DocumentGraph:
    return DocumentGraph(
        doc_id=doc_id,
        contexts=[
            ContextNode(
                context_id=context_id,
                doc_id=doc_id,
                canonical_label=label,
                kind=label,
                page_span=[1],
                confidence=confidence,  # type: ignore[arg-type]
            )
        ],
    )


def _search(
    search_id: str,
    source: str,
    doc_id: str,
    subject: str,
    parameter: str,
    value: str,
    *,
    record_id: str | None = None,
) -> dict[str, object]:
    return {
        "search_id": search_id,
        "source": source,
        "record_id": record_id or search_id,
        "doc_id": doc_id,
        "subject": subject,
        "parameter": parameter,
        "value": value,
        "text": f"{subject} {parameter} {value}",
    }
