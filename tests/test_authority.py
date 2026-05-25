from pathlib import Path

from interlock_mvp.core.authority import classify_doc_type, resolve_authority


def test_cli_doc_type_override_has_full_confidence() -> None:
    doc_type, confidence, evidence = classify_doc_type(Path("x.pdf"), "", "drawing")
    assert doc_type == "drawing"
    assert confidence == 1.0
    assert evidence["method"] == "cli_override"


def test_cross_doc_precedence_selects_authoritative_side() -> None:
    decision = resolve_authority(
        mode="cross_doc",
        config={"cross_doc": {"precedence": ["protection_study", "drawing"], "fallback": "unknown_direction"}},
        doc_a_type="drawing",
        doc_b_type="protection_study",
        doc_a_confidence=1.0,
        doc_b_confidence=1.0,
    )
    assert decision.authoritative_side == "B"
    assert decision.confidence == 1.0
