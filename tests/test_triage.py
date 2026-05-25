from pathlib import Path

from interlock_mvp.core.artifacts import write_json, write_object
from interlock_mvp.core.triage import triage_run


def test_triage_flags_weak_extraction_and_context_fallback(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_object(
        run_dir / "metrics.json",
        {
            "metrics": {
                "findings": 18,
                "review_required_findings": 0,
                "coverage_warning_findings": 18,
                "comparison_decisions": 0,
                "alignment_decisions": 0,
            }
        },
    )
    write_json(
        run_dir / "pages.json",
        records=[
            {
                "page_id": "A_p1",
                "doc_id": "A",
                "page_num": 1,
                "text_char_count": 0,
                "extraction_status": "empty",
            }
        ],
    )
    write_json(
        run_dir / "evidence.json",
        records=[
            {
                "evidence_id": "ev1",
                "doc_id": "A",
                "page": 1,
                "kind": "coverage_warning",
                "subject": "DOCUMENT",
                "parameter": "coverage",
                "raw_text": "no text",
                "context_id": "A:document",
                "context_confidence": "low",
            }
        ],
    )
    write_json(run_dir / "findings.json", records=[])
    write_json(run_dir / "decision_traces.json", records=[])

    triage = triage_run(run_dir)

    issue_ids = {issue.issue_id for issue in triage.issues}
    assert "triage_weak_extraction_pages" in issue_ids
    assert "triage_document_level_context" in issue_ids
    assert "triage_generic_subjects" in issue_ids
    assert (run_dir / "triage.json").exists()
    assert any("OCR/VLM" in action for action in triage.next_actions)


def test_triage_flags_absence_only_reasoning(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_object(
        run_dir / "metrics.json",
        {
            "metrics": {
                "findings": 1,
                "review_required_findings": 1,
                "coverage_warning_findings": 0,
                "comparison_decisions": 0,
                "alignment_decisions": 0,
            }
        },
    )
    write_json(run_dir / "pages.json", records=[])
    write_json(run_dir / "evidence.json", records=[])
    write_json(
        run_dir / "findings.json",
        records=[
            {
                "finding_id": "find_00001",
                "finding_type": "missing_item",
                "severity": "review_required",
                "subject": "XFMR-1",
                "parameter": "rating",
                "absence_id": "abs00001",
                "alignment_id": None,
                "comparison_id": None,
            }
        ],
    )
    write_json(
        run_dir / "decision_traces.json",
        records=[
            {
                "finding_id": "find_00001",
                "decision": "review_required",
                "finding_type": "missing_item",
                "confidence": "high",
                "downgrade_reasons": [],
            }
        ],
    )
    write_object(
        run_dir / "reasoning_graph.json",
        {"alignments": [], "comparisons": [], "absence_searches": [{"absence_id": "abs00001"}]},
    )

    triage = triage_run(run_dir)

    issue_ids = {issue.issue_id for issue in triage.issues}
    assert "triage_absence_only_review" in issue_ids
    assert "triage_no_value_comparisons" in issue_ids
    assert any("subject/context alignment" in action for action in triage.next_actions)


def test_triage_flags_missing_decision_trace(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_object(run_dir / "metrics.json", {"metrics": {"findings": 1, "review_required_findings": 1}})
    write_json(
        run_dir / "findings.json",
        records=[{"finding_id": "find_00001", "finding_type": "value_mismatch", "severity": "review_required"}],
    )
    write_json(run_dir / "decision_traces.json", records=[])

    triage = triage_run(run_dir, write=False)

    assert "triage_findings_missing_decision_traces" in {issue.issue_id for issue in triage.issues}
