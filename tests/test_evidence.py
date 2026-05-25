from interlock_mvp.core.evidence import mine_evidence
from interlock_mvp.core.models import AnnotationRecord, PageRecord, RegionRecord


def test_mine_evidence_extracts_subjects_and_engineering_values() -> None:
    evidence = mine_evidence(
        pages=[_page("A", 1)],
        regions=[
            _region(
                "A",
                1,
                "r1",
                "Equipment ID: XFMR-001 Rated Power: 1100 kVA Rated Impedance: 4.5 %Z",
            )
        ],
        annotations=[],
    )

    assert any(item.kind == "equipment_id" and item.subject == "XFMR-001" for item in evidence)
    assert any(item.kind == "parameter_value" and item.parameter == "rating" and item.value == "1100" for item in evidence)
    assert any(item.kind == "parameter_value" and item.parameter == "impedance" and item.unit == "%Z" for item in evidence)


def test_mine_evidence_emits_coverage_warning_for_low_text_page() -> None:
    evidence = mine_evidence(pages=[_page("A", 3, status="empty")], regions=[], annotations=[])

    assert len(evidence) == 1
    assert evidence[0].kind == "coverage_warning"
    assert evidence[0].page == 3
    assert evidence[0].crop_path == "pages/A_3.png"


def test_neighbor_context_attaches_general_value_to_prior_equipment() -> None:
    evidence = mine_evidence(
        pages=[_page("A", 1)],
        regions=[
            _region("A", 1, "r1", "LOW-PEAK KRP-C-1600SP", y0=10),
            _region("A", 1, "r2", "Fault X1 20,000A RMS Sym", y0=80),
        ],
        annotations=[],
    )

    attached = [
        item
        for item in evidence
        if item.kind == "parameter_value" and item.value == "20,000" and item.unit == "A"
    ][0]
    assert attached.subject == "KRP-C-1600SP"
    assert attached.parameter == "fault_current"
    assert attached.source_method.endswith("+neighbor_context")


def test_annotations_preserve_comment_and_highlight_as_evidence() -> None:
    evidence = mine_evidence(
        pages=[_page("B", 2)],
        regions=[],
        annotations=[
            AnnotationRecord(
                annotation_id="ann1",
                doc_id="B",
                page=2,
                bbox=[1, 2, 30, 40],
                annotation_type="Highlight",
                annotation_comment="Check updated rating",
                highlighted_text="1000 kVA",
            )
        ],
    )

    assert len(evidence) == 1
    assert evidence[0].kind == "annotation"
    assert evidence[0].raw_text == "1000 kVA Check updated rating"
    assert evidence[0].source_method == "pymupdf_annotation"


def _page(doc_id: str, page: int, *, status: str = "ok") -> PageRecord:
    return PageRecord(
        page_id=f"{doc_id}:page:{page}",
        doc_id=doc_id,
        page_num=page,
        width=100,
        height=200,
        text_char_count=120 if status == "ok" else 0,
        extraction_status=status,
        page_image_path=f"pages/{doc_id}_{page}.png",
    )


def _region(doc_id: str, page: int, region_id: str, text: str, *, y0: float = 0) -> RegionRecord:
    return RegionRecord(
        region_id=region_id,
        doc_id=doc_id,
        page=page,
        bbox=[0, y0, 100, y0 + 20],
        text=text,
        kind="text_block",
        crop_path=f"crops/{region_id}.png",
    )
