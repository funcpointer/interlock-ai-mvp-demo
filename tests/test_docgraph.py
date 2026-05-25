from interlock_mvp.core.docgraph import build_diff_graph, build_document_graphs
from interlock_mvp.core.models import EvidenceItem, RegionRecord


def test_context_alignment_ignores_page_movement() -> None:
    regions = [
        _region("A", 7, "ra1", "Time Current Curve #3 (TCC3)"),
        _region("A", 7, "ra2", "LPN-RK-500SP Class RK1 Fuse"),
        _region("B", 8, "rb1", "TCC3"),
        _region("B", 8, "rb2", "LPN-RK-500SP Class RK1 Fuse"),
    ]
    evidence = [
        _equipment("A", 7, "ra2", "ev1", "LPN-RK-500SP"),
        _equipment("B", 8, "rb2", "ev2", "LPN-RK-500SP"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    assert not [edge for edge in diff.edges if edge.diff_type == "missing_item"]


def test_missing_subject_in_aligned_context_surfaces() -> None:
    regions = [
        _region("A", 7, "ra1", "Time Current Curve #3 (TCC3)"),
        _region("A", 7, "ra2", "LPN-RK-500SP Class RK1 Fuse"),
        _region("B", 8, "rb1", "TCC3"),
    ]
    evidence = [_equipment("A", 7, "ra2", "ev1", "LPN-RK-500SP")]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    assert any(edge.diff_type == "missing_item" and edge.subject == "LPN-RK-500SP" for edge in diff.edges)


def test_equivalent_unit_claim_does_not_diff() -> None:
    regions = [
        _region("A", 7, "ra1", "TCC3"),
        _region("A", 7, "ra2", "150 KVA XFMR"),
        _region("B", 8, "rb1", "Time Current Curve #3"),
        _region("B", 8, "rb2", "0.15 MVA XFMR"),
    ]
    evidence = [
        _claim("A", 7, "ra2", "ev1", "XFMR", "rating", "150", "KVA", "150 KVA XFMR"),
        _claim("B", 8, "rb2", "ev2", "XFMR", "rating", "0.15", "MVA", "0.15 MVA XFMR"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)
    assert not [edge for edge in diff.edges if edge.diff_type == "value_mismatch"]


def test_reference_subjects_do_not_become_missing_equipment() -> None:
    regions = [
        _region("A", 1, "ra1", "Equipment Data Sheet"),
        _region("A", 1, "ra2", "Standards compliance: NEMA MG 1-2016, IEC 60034-1"),
        _region("B", 1, "rb1", "Equipment Data Sheet"),
        _region("B", 1, "rb2", "Standards compliance: NEMA MG 1-2016"),
    ]
    evidence = [
        _reference("A", 1, "ra2", "ev1", "IEC 60034-1"),
        _reference("B", 1, "rb2", "ev2", "NEMA MG 1-2016"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)

    assert not [edge for edge in diff.edges if edge.subject in {"IEC 60034-1", "NEMA MG 1-2016"}]


def test_percent_values_without_impedance_context_do_not_diff_as_impedance() -> None:
    regions = [
        _region("A", 17, "ra1", "TAPS (range, locations etc.)"),
        _region("A", 17, "ra2", "Transformer taps 2.5%"),
        _region("B", 17, "rb1", "TAPS (range, locations etc.)"),
    ]
    evidence = [
        _claim("A", 17, "ra2", "ev1", "XFMR", "impedance", "2.5", "%", "Transformer taps 2.5%"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)

    assert not [edge for edge in diff.edges if edge.parameter == "impedance"]


def test_duplicate_same_value_edges_collapse() -> None:
    regions = [
        _region("A", 7, "ra1", "TCC3"),
        _region("A", 7, "ra2", "1000KVA XFMR"),
        _region("A", 7, "ra3", "1000KVA XFMR"),
        _region("B", 7, "rb1", "TCC3"),
        _region("B", 7, "rb2", "100KVA XFMR"),
    ]
    evidence = [
        _claim("A", 7, "ra2", "ev1", "XFMR", "rating", "1000", "KVA", "1000KVA XFMR"),
        _claim("A", 7, "ra3", "ev2", "XFMR", "rating", "1000", "KVA", "1000KVA XFMR"),
        _claim("B", 7, "rb2", "ev3", "XFMR", "rating", "100", "KVA", "100KVA XFMR"),
    ]
    graph_a, graph_b, _updated = build_document_graphs(regions=regions, evidence=evidence)
    diff = build_diff_graph(graph_a, graph_b)

    rating_edges = [edge for edge in diff.edges if edge.parameter == "rating"]
    assert len(rating_edges) == 1


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


def _reference(doc_id: str, page: int, region_id: str, evidence_id: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=page,
        bbox=[0, 0, 100, 20],
        region_id=region_id,
        kind="reference",
        subject=value,
        parameter="reference",
        value=value,
        unit="",
        raw_text=value,
        normalized_text=value.lower(),
        normalized_value=value.lower(),
        confidence="medium",
        source_method="test",
        crop_path=f"crops/{region_id}.png",
    )
