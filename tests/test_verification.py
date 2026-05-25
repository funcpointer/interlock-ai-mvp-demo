import interlock_mvp.core.verification as verification_module
from interlock_mvp.core.models import (
    AbsenceSearch,
    AlignmentDecision,
    AuthorityDecision,
    ComparisonDecision,
    ContextSupport,
    DiffEdge,
    EvidenceItem,
    ReasoningGraph,
)
from interlock_mvp.core.verification import ExternalFindingReview, authored_language_violations, findings_from_reasoning_graph


def test_reasoning_graph_finding_requires_cited_evidence() -> None:
    findings, warnings, _metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="missing cited evidence",
                )
            ]
        ),
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
    findings, _warnings, metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            alignments=[
                AlignmentDecision(
                    alignment_id="align00001",
                    diff_id="diff00001",
                    a_claim_id="A:claim:a1",
                    b_claim_id="B:claim:b1",
                    subject_method="exact",
                    parameter_method="exact",
                    context_method="canonicalized",
                    confidence="high",
                    accepted=True,
                    rationale="A differs from B.",
                )
            ],
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ],
        ),
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
    assert metrics["comparison_sourced_findings"] == 1.0
    assert findings[0].severity == "review_required"
    assert findings[0].confidence == "high"
    assert findings[0].evidence_a is not None
    assert findings[0].evidence_b is not None
    assert findings[0].alignment_id == "align00001"
    assert findings[0].comparison_id == "comp00001"


def test_unknown_authority_downgrades_strong_deterministic_diff() -> None:
    findings, _warnings, _metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ]
        ),
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


def test_context_support_can_upgrade_medium_identity_value_mismatch() -> None:
    findings, _warnings, _metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ],
            context_supports=[_context_support("diff00001", supports=True, confidence="high")],
        ),
        diff_edges=[_diff_edge(identity_strength="medium")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="cross_doc",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert findings[0].severity == "review_required"
    assert findings[0].confidence == "high"
    assert findings[0].context_support_id == "ctx00001"
    assert findings[0].context_support_supports is True
    assert findings[0].context_support_confidence == "high"


def test_context_support_does_not_upgrade_weak_identity() -> None:
    findings, _warnings, _metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ],
            context_supports=[_context_support("diff00001", supports=True, confidence="high")],
        ),
        diff_edges=[_diff_edge(identity_strength="weak")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="cross_doc",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert findings[0].severity == "possible_issue"
    assert findings[0].confidence == "low"


def test_context_support_downgrades_possible_equivalent_elsewhere() -> None:
    findings, _warnings, _metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ],
            context_supports=[
                _context_support(
                    "diff00001",
                    supports=False,
                    confidence="medium",
                    signal_types=["possible_equivalent_elsewhere"],
                    downgrade_reasons=["search found possible equivalent evidence elsewhere in the packet"],
                )
            ],
        ),
        diff_edges=[_diff_edge(identity_strength="strong")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="cross_doc",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert findings[0].severity == "possible_issue"
    assert findings[0].confidence == "medium"
    assert findings[0].context_support_supports is False
    assert findings[0].context_support_confidence == "medium"
    assert "possible_equivalent_elsewhere" in findings[0].context_support_signal_types


def test_absence_search_sources_missing_item_finding() -> None:
    findings, _warnings, metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            absence_searches=[
                AbsenceSearch(
                    absence_id="abs00001",
                    diff_id="diff00002",
                    a_subject_id="A:subject:lpn_rk_500sp",
                    searched_doc_id="B",
                    searched_context_ids=["A:tcc3"],
                    searched_parameters=["equipment_presence"],
                    query_terms=["LPN-RK-500SP", "equipment_presence"],
                    coverage_status="searched",
                    confidence="high",
                    rationale="No matching B subject was found.",
                )
            ]
        ),
        diff_edges=[
            DiffEdge(
                diff_id="diff00002",
                diff_type="missing_item",
                a_node_id="A:subject:lpn_rk_500sp",
                alignment_status="unmatched_a",
                subject="LPN-RK-500SP",
                parameter="equipment_presence",
                rationale="No matching B subject was found.",
                evidence_ids=["a1"],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        ],
        evidence_by_id={"a1": _equipment("a1", "A", "LPN-RK-500SP")},
        authority=_authority("B"),
        mode="version",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert len(findings) == 1
    assert metrics["absence_sourced_findings"] == 1.0
    assert findings[0].finding_type == "missing_item"
    assert findings[0].absence_id == "abs00001"
    assert findings[0].comparison_id is None


def test_banned_authored_language_detection_handles_punctuation() -> None:
    violations = authored_language_violations("This is WRONG. That result would be hazardous; not safety language.")

    assert violations == ["hazardous", "safety", "wrong"]


def test_external_model_review_enriches_existing_finding_without_changing_gate(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_review(_finding, *, model: str) -> ExternalFindingReview:
        assert model
        return ExternalFindingReview(
            supports_finding=True,
            reviewer_note="Citations support the stated mismatch.",
            caution_note="Reviewer should confirm engineering significance before action.",
        )

    monkeypatch.setattr(verification_module, "_review_finding_with_openai", fake_review)
    findings, warnings, metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ],
            context_supports=[_context_support("diff00001", supports=True, confidence="high")],
        ),
        diff_edges=[_diff_edge(identity_strength="strong")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="version",
        no_cloud=False,
        dry_run=False,
        max_cost_usd=1.0,
    )

    assert warnings == []
    assert metrics["external_model_reviewed_findings"] == 1.0
    assert metrics["estimated_cloud_cost_usd"] > 0
    assert findings[0].severity == "review_required"
    assert findings[0].model_review_status == "used"
    assert findings[0].model_review_supports is True
    assert findings[0].model_review_cautions == ["Reviewer should confirm engineering significance before action."]


def test_value_mismatch_summary_uses_reviewer_facing_authority_language() -> None:
    findings, _, _ = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ]
        ),
        diff_edges=[_diff_edge(identity_strength="strong")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "140", "MVA"),
            "b1": _evidence("b1", "B", "120", "MVA"),
        },
        authority=_authority("B"),
        mode="version",
        no_cloud=True,
        dry_run=False,
        max_cost_usd=0,
    )

    assert findings[0].summary == "Doc B is authoritative for this review; the cited Doc B value differs from the baseline Doc A value."


def test_external_model_review_rejects_banned_authored_language(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_review(_finding, *, model: str) -> ExternalFindingReview:
        return ExternalFindingReview(
            supports_finding=True,
            reviewer_note="This is wrong.",
            caution_note="",
        )

    monkeypatch.setattr(verification_module, "_review_finding_with_openai", fake_review)
    findings, warnings, metrics = findings_from_reasoning_graph(
        reasoning_graph=ReasoningGraph(
            comparisons=[
                ComparisonDecision(
                    comparison_id="comp00001",
                    diff_id="diff00001",
                    alignment_id="align00001",
                    comparison_type="value_mismatch",
                    unit_method="pint",
                    deterministic=True,
                    verifier_status="not_run",
                    rationale="A differs from B.",
                )
            ]
        ),
        diff_edges=[_diff_edge(identity_strength="strong")],
        evidence_by_id={
            "a1": _evidence("a1", "A", "1000", "KVA"),
            "b1": _evidence("b1", "B", "100", "KVA"),
        },
        authority=_authority("B"),
        mode="version",
        no_cloud=False,
        dry_run=False,
        max_cost_usd=1.0,
    )

    assert metrics["external_model_review_failures"] == 1.0
    assert "banned wording" in warnings[0]
    assert findings[0].model_review_status == "rejected_language"
    assert findings[0].model_review_summary == ""


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


def _diff_edge(*, identity_strength: str) -> DiffEdge:
    return DiffEdge(
        diff_id="diff00001",
        diff_type="value_mismatch",
        alignment_status="conflict",
        subject="XFMR",
        parameter="rating",
        rationale="A differs from B.",
        evidence_ids=["a1", "b1"],
        identity_strength=identity_strength,  # type: ignore[arg-type]
        deterministic_discrepancy=True,
    )


def _context_support(
    diff_id: str,
    *,
    supports: bool,
    confidence: str,
    signal_types: list[str] | None = None,
    downgrade_reasons: list[str] | None = None,
) -> ContextSupport:
    return ContextSupport(
        support_id="ctx00001",
        diff_id=diff_id,
        supports=supports,
        confidence=confidence,  # type: ignore[arg-type]
        signal_types=signal_types or ["context_room", "search_hit", "graph_alignment"],
        context_ids=["A:ctx:ratings", "B:ctx:ratings"],
        search_ids=["claim:b1"],
        summary="Aligned cited context.",
        downgrade_reasons=downgrade_reasons or [],
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


def _equipment(evidence_id: str, doc_id: str, subject: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        doc_id=doc_id,
        page=1,
        bbox=[1, 2, 3, 4],
        region_id=f"r{evidence_id}",
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
        crop_path=f"crops/{evidence_id}.png",
    )
