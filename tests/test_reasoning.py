from interlock_mvp.core.docgraph import build_diff_graph, build_document_graphs
from interlock_mvp.core.models import EvidenceItem, RegionRecord
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
