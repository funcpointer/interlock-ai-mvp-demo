from interlock_mvp.core.docgraph import build_diff_graph, build_document_graphs
from interlock_mvp.core.models import ClaimNode, ContextNode, DiffEdge, DiffGraph, DocumentGraph, EvidenceItem, RegionRecord
from interlock_mvp.core.reasoning import build_reasoning_graph, reasoning_lookup


def test_value_mismatch_has_alignment_and_comparison_decisions() -> None:
    regions = [
        _region("A", 1, "ra1", "TCC3"),
        _region("A", 1, "ra2", "1000KVA XFMR"),
        _region("B", 1, "rb1", "TCC3"),
        _region("B", 1, "rb2", "100KVA XFMR"),
    ]
    evidence = [
        _claim("A", 1, "ra2", "ev1", "XFMR", "rating", "1000", "KVA", "1000KVA XFMR"),
        _claim("B", 1, "rb2", "ev2", "XFMR", "rating", "100", "KVA", "100KVA XFMR"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    reasoning = build_reasoning_graph(diff, graph_a, graph_b)

    assert len(reasoning.alignments) == 1
    assert len(reasoning.comparisons) == 1
    assert reasoning.absence_searches == []
    alignment = reasoning.alignments[0]
    comparison = reasoning.comparisons[0]
    assert alignment.accepted is True
    assert alignment.subject_method == "exact"
    assert alignment.parameter_method == "exact"
    assert comparison.alignment_id == alignment.alignment_id
    assert comparison.comparison_type == "value_mismatch"
    assert comparison.unit_method == "pint"


def test_missing_item_has_absence_search_decision() -> None:
    regions = [
        _region("A", 7, "ra1", "Time Current Curve #3 (TCC3)"),
        _region("A", 7, "ra2", "LPN-RK-500SP Class RK1 Fuse"),
        _region("B", 7, "rb1", "TCC3"),
    ]
    evidence = [_equipment("A", 7, "ra2", "ev1", "LPN-RK-500SP")]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    reasoning = build_reasoning_graph(diff, graph_a, graph_b)

    assert reasoning.alignments == []
    assert reasoning.comparisons == []
    assert len(reasoning.absence_searches) == 1
    absence = reasoning.absence_searches[0]
    assert absence.a_subject_id == "A:subject:lpn_rk_500sp"
    assert absence.searched_doc_id == "B"
    assert absence.searched_parameters == ["equipment_presence"]
    assert absence.coverage_status == "searched"
    assert "LPN-RK-500SP" in absence.query_terms


def test_reasoning_lookup_maps_diff_to_decision_ids() -> None:
    regions = [
        _region("A", 1, "ra1", "TCC3"),
        _region("A", 1, "ra2", "1000KVA XFMR"),
        _region("B", 1, "rb1", "TCC3"),
        _region("B", 1, "rb2", "100KVA XFMR"),
    ]
    evidence = [
        _claim("A", 1, "ra2", "ev1", "XFMR", "rating", "1000", "KVA", "1000KVA XFMR"),
        _claim("B", 1, "rb2", "ev2", "XFMR", "rating", "100", "KVA", "100KVA XFMR"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    reasoning = build_reasoning_graph(diff, graph_a, graph_b)

    lookup = reasoning_lookup(reasoning)

    edge = diff.edges[0]
    assert lookup[edge.diff_id]["alignment_id"] == reasoning.alignments[0].alignment_id
    assert lookup[edge.diff_id]["comparison_id"] == reasoning.comparisons[0].comparison_id


def test_alignment_records_rejected_same_parameter_candidate_summaries() -> None:
    graph_a = DocumentGraph(
        doc_id="A",
        contexts=[_context("A:context:capacity", "capacity ratings")],
        claims=[_claim_node("A:claim:rating", "A", "A:context:capacity", "A:subject:xfmr", "rating", "140", "MVA", "84/112/140 MVA")],
    )
    graph_b = DocumentGraph(
        doc_id="B",
        contexts=[
            _context("B:context:capacity", "capacity ratings"),
            _context("B:context:spares", "spare equipment"),
        ],
        claims=[
            _claim_node("B:claim:accepted", "B", "B:context:capacity", "B:subject:xfmr", "rating", "120", "MVA", "84/112/120 MVA"),
            _claim_node("B:claim:rejected", "B", "B:context:spares", "B:subject:spare", "rating", "75", "MVA", "Spare transformer 75 MVA"),
        ],
    )
    diff = DiffGraph(
        edges=[
            DiffEdge(
                diff_id="diff00001",
                diff_type="value_mismatch",
                a_node_id="A:claim:rating",
                b_node_id="B:claim:accepted",
                alignment_status="conflict",
                subject="XFMR",
                parameter="rating",
                rationale="accepted claim differs",
                evidence_ids=[],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        ]
    )

    reasoning = build_reasoning_graph(diff, graph_a, graph_b)

    alignment = reasoning.alignments[0]
    assert alignment.candidate_b_claim_count == 2
    assert alignment.same_parameter_b_claim_count == 2
    assert alignment.rejected_b_claim_ids == ["B:claim:rejected"]
    assert alignment.rejected_b_claim_summaries == [
        'Doc B / spare equipment: rating 75 MVA - "Spare transformer 75 MVA"'
    ]


def _region(doc_id: str, page: int, region_id: str, text: str) -> RegionRecord:
    return RegionRecord(
        region_id=region_id,
        doc_id=doc_id,
        page=page,
        bbox=[0, 0, 100, 20],
        text=text,
        kind="text_block",
        crop_path=f"crops/{region_id}.png",
    )


def _context(context_id: str, label: str) -> ContextNode:
    return ContextNode(
        context_id=context_id,
        doc_id=context_id.split(":", 1)[0],
        canonical_label=label,
        raw_labels=[label],
        kind="section",
        page_span=[1],
        confidence="high",
    )


def _claim_node(
    claim_id: str,
    doc_id: str,
    context_id: str,
    subject_id: str,
    parameter: str,
    value: str,
    unit: str,
    raw_text: str,
) -> ClaimNode:
    return ClaimNode(
        claim_id=claim_id,
        doc_id=doc_id,
        context_id=context_id,
        subject_id=subject_id,
        parameter=parameter,
        value=value,
        unit=unit,
        raw_text=raw_text,
        evidence_ids=[],
        confidence="high",
    )


def _equipment(doc_id: str, page: int, region_id: str, evidence_id: str, subject: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=page,
        bbox=[0, 0, 100, 20],
        region_id=region_id,
        kind="equipment_id",
        subject=subject,
        parameter="identity",
        value=subject,
        unit="",
        raw_text=subject,
        normalized_text=subject.lower(),
        normalized_value=subject.lower(),
        confidence="high",
        source_method="test",
        crop_path=f"crops/{region_id}.png",
    )


def _claim(
    doc_id: str,
    page: int,
    region_id: str,
    evidence_id: str,
    subject: str,
    parameter: str,
    value: str,
    unit: str,
    raw_text: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=page,
        bbox=[0, 0, 100, 20],
        region_id=region_id,
        kind="parameter_value",
        subject=subject,
        parameter=parameter,
        value=value,
        unit=unit,
        raw_text=raw_text,
        normalized_text=raw_text.lower(),
        normalized_value=f"{value} {unit}".lower(),
        confidence="high",
        source_method="test",
        crop_path=f"crops/{region_id}.png",
    )
