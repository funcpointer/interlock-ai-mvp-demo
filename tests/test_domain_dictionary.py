from pathlib import Path

from interlock_mvp.core.contexts import align_context_label, context_label_for_region
from interlock_mvp.core.domain import DomainDictionary
from interlock_mvp.core.evidence import mine_evidence
from interlock_mvp.core.models import PageRecord, RegionRecord
from interlock_mvp.core.subjects import canonical_parameter, extract_subjects


def test_domain_dictionary_feeds_subject_extraction_for_aes_equipment_aliases() -> None:
    domain = DomainDictionary.from_yaml(Path("examples/aes_glossary.yaml"))

    subjects = extract_subjects("Switchboard SB-1 available fault current 42 kA", domain=domain)

    assert "SWITCHBOARD SB-1" in subjects


def test_domain_dictionary_feeds_parameter_canonicalization_without_overclaiming_voltage_role() -> None:
    domain = DomainDictionary.from_yaml(Path("examples/aes_glossary.yaml"))

    assert canonical_parameter("BIL 95 kV", "kV", domain=domain) == "bil"
    assert canonical_parameter("12.47 kV", "kV", domain=domain) == "voltage"
    assert canonical_parameter("Primary Voltage 12.47 kV", "kV", domain=domain) == "primary_voltage"


def test_domain_dictionary_feeds_context_aliases() -> None:
    domain = DomainDictionary.from_yaml(Path("examples/aes_glossary.yaml"))
    current = {}

    context_id, canonical, kind, raw = context_label_for_region(
        _region("A", 4, "r1", "Coordination Curve 3"),
        current,
        domain=domain,
    )

    assert context_id == "A:tcc3"
    assert canonical == "tcc3"
    assert kind == "time_current_curve"
    assert raw == "Coordination Curve"
    assert align_context_label(canonical) == "tcc3"


def test_review_evidence_uses_domain_dictionary_for_non_fixture_terms() -> None:
    domain = DomainDictionary.from_yaml(Path("examples/aes_glossary.yaml"))

    evidence = mine_evidence(
        pages=[_page("A", 1)],
        regions=[_region("A", 1, "r1", "Switchboard SB-1 available fault current 42 kA")],
        annotations=[],
        domain=domain,
    )

    assert any(item.kind == "equipment_id" and item.subject == "SWITCHBOARD SB-1" for item in evidence)
    assert any(item.kind == "parameter_value" and item.parameter == "fault_current" and item.value == "42" for item in evidence)


def _page(doc_id: str, page: int) -> PageRecord:
    return PageRecord(
        page_id=f"{doc_id}:page:{page}",
        doc_id=doc_id,
        page_num=page,
        width=100,
        height=200,
        text_char_count=120,
        extraction_status="ok",
        page_image_path=f"pages/{doc_id}_{page}.png",
    )


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
