from interlock_mvp.core.models import AuthorityDecision, DiffEdge, EvidenceItem
from interlock_mvp.core.verification import authored_language_violations, findings_from_diff_graph


def test_diff_graph_finding_requires_cited_evidence() -> None:
    findings, warnings, _metrics = findings_from_diff_graph(
        diff_edges=[
            DiffEdge(
                diff_id="diff00001",
                diff_type="value_mismatch",
                alignment_status="conflict",
                subject="XFMR",
                parameter="rating",
                rationale="missing cited evidence",
                evidence_ids=["missing"],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        ],
        evidence_by_id={},
        authority=_authority("B"),
        mode="version",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert findings == []
    assert warnings == ["cloud verification skipped; deterministic verifier used"]


def test_known_authority_strong_deterministic_diff_is_review_required() -> None:
    findings, _warnings, _metrics = findings_from_diff_graph(
        diff_edges=[
            DiffEdge(
                diff_id="diff00001",
                diff_type="value_mismatch",
                alignment_status="conflict",
                subject="XFMR",
                parameter="rating",
                rationale="A differs from B.",
                evidence_ids=["a1", "b1"],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        ],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="version",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert len(findings) == 1
    assert findings[0].severity == "review_required"
    assert findings[0].confidence == "high"
    assert findings[0].evidence_a is not None
    assert findings[0].evidence_b is not None


def test_unknown_authority_downgrades_strong_deterministic_diff() -> None:
    findings, _warnings, _metrics = findings_from_diff_graph(
        diff_edges=[
            DiffEdge(
                diff_id="diff00001",
                diff_type="value_mismatch",
                alignment_status="conflict",
                subject="XFMR",
                parameter="rating",
                rationale="A differs from B.",
                evidence_ids=["a1", "b1"],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        ],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("unknown_direction"),
        mode="cross_doc",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert len(findings) == 1
    assert findings[0].severity == "possible_issue"
    assert findings[0].confidence == "medium"
    assert findings[0].authoritative_side == "unknown_direction"


def test_banned_authored_language_detection_handles_punctuation() -> None:
    violations = authored_language_violations("This is WRONG. That result would be hazardous; not quoted.")

    assert violations == ["hazardous", "wrong"]


def _authority(side: str) -> AuthorityDecision:
    return AuthorityDecision(
        authoritative_side=side,
        basis="test",
        confidence=0.9 if side in {"A", "B"} else 0.3,
        doc_a_type="specification",
        doc_b_type="protection_study",
        doc_a_type_confidence=1.0,
        doc_b_type_confidence=1.0,
    )


def _evidence(evidence_id: str, doc_id: str, value: str, unit: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=1 if doc_id == "A" else 2,
        bbox=[1, 2, 3, 4],
        region_id=f"r{evidence_id}",
        kind="parameter_value",
        subject="XFMR",
        parameter="rating",
        value=value,
        unit=unit,
        raw_text=f"{value}{unit} XFMR",
        normalized_text=f"{value}{unit} xfmr",
        normalized_value=f"{value} {unit}",
        confidence="high",
        source_method="test",
        crop_path=f"crops/{evidence_id}.png",
    )
