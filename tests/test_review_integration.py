import json
from pathlib import Path

import fitz

from interlock_mvp.core.models import ReviewRequest
from interlock_mvp.core.review import run_review


def test_run_review_writes_artifacts_and_cited_finding(tmp_path: Path) -> None:
    doc_a = tmp_path / "doc_a.pdf"
    doc_b = tmp_path / "doc_b.pdf"
    _write_pdf(doc_a, "Equipment Data Sheet\nEquipment ID: XFMR-001 Rated Power: 1000 kVA")
    _write_pdf(doc_b, "Equipment Data Sheet\nEquipment ID: XFMR-001 Rated Power: 100 kVA")

    out_dir = tmp_path / "run"
    result = run_review(
        ReviewRequest(
            doc_a_path=doc_a,
            doc_b_path=doc_b,
            mode="version",
            out_dir=out_dir,
            no_cloud=True,
            no_kuzu=True,
            max_candidates=10,
        )
    )

    assert result.findings_count == 1
    assert result.review_required_count == 1
    for name in [
        "manifest.json",
        "authority.json",
        "documents.json",
        "pages.json",
        "regions.json",
        "evidence.json",
        "doc_graph_a.json",
        "doc_graph_b.json",
        "diff_graph.json",
        "reasoning_graph.json",
        "candidates.json",
        "findings.json",
        "metrics.json",
        "logs.jsonl",
        "report.md",
        "search/review_map.jsonl",
        "search/second_brain.sqlite",
    ]:
        assert (out_dir / name).exists(), name

    findings = json.loads((out_dir / "findings.json").read_text(encoding="utf-8"))["records"]
    finding = findings[0]
    assert finding["parameter"] == "rating"
    assert finding["evidence_a"]["quote"]
    assert finding["evidence_a"]["crop_path"]
    assert finding["evidence_b"]["quote"]
    assert finding["evidence_b"]["crop_path"]
    assert finding["alignment_id"]
    assert finding["comparison_id"]
    assert finding["absence_id"] is None

    reasoning = json.loads((out_dir / "reasoning_graph.json").read_text(encoding="utf-8"))
    assert reasoning["comparisons"][0]["comparison_id"] == finding["comparison_id"]
    assert reasoning["alignments"][0]["alignment_id"] == finding["alignment_id"]

    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    assert metrics["alignment_decisions"] == 1
    assert metrics["comparison_decisions"] == 1
    assert metrics["comparison_sourced_findings"] == 1.0
    assert metrics["absence_sourced_findings"] == 0.0
    assert "Review Reasoning Health" in (out_dir / "report.md").read_text(encoding="utf-8")

    logs = (out_dir / "logs.jsonl").read_text(encoding="utf-8")
    assert "extract_doc_a" in logs
    assert "verify_findings" in logs


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
