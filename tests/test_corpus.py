import json
from pathlib import Path

import fitz

from interlock_mvp.core.corpus import corpus_success, load_corpus_manifest, run_corpus_manifest


def test_corpus_manifest_runs_pair_and_eval(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    doc_a = docs / "baseline.pdf"
    doc_b = docs / "revised.pdf"
    _write_pdf(doc_a, "Equipment ID: XFMR-001 Rated Power: 1000 kVA")
    _write_pdf(doc_b, "Equipment ID: XFMR-001 Rated Power: 100 kVA")
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text(
        """
expected_findings:
  - finding_type: value_mismatch
    subject_contains: XFMR
    parameter: rating
    evidence_a:
      value: "1000"
      unit: kVA
    evidence_b:
      value: "100"
      unit: kVA
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
schema_version: interlock_mvp.corpus.v1
name: local_test
source_root: docs
pairs:
  - id: xfmr_rating_revision
    mode: version
    doc_a: baseline.pdf
    doc_b: revised.pdf
    eval: eval.yaml
    no_cloud: true
    no_kuzu: true
""",
        encoding="utf-8",
    )

    summaries = run_corpus_manifest(manifest, out_root=tmp_path / "runs")

    assert corpus_success(summaries)
    assert summaries[0].status == "eval_passed"
    assert summaries[0].review_required_count == 1
    assert (tmp_path / "runs" / "xfmr_rating_revision" / "findings.json").exists()
    results = json.loads((tmp_path / "runs" / "corpus_results.json").read_text(encoding="utf-8"))
    assert results["records"][0]["pair_id"] == "xfmr_rating_revision"


def test_corpus_manifest_reports_missing_private_files(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
schema_version: interlock_mvp.corpus.v1
name: missing_private_docs
pairs:
  - id: aes_pair_missing
    mode: cross_doc
    doc_a: docs/missing_a.pdf
    doc_b: docs/missing_b.pdf
""",
        encoding="utf-8",
    )

    summaries = run_corpus_manifest(manifest, out_root=tmp_path / "runs")

    assert not corpus_success(summaries)
    assert summaries[0].status == "missing_files"
    assert "missing_a.pdf" in summaries[0].warnings[0]


def test_load_corpus_manifest_rejects_unknown_schema(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
schema_version: interlock_mvp.corpus.v999
name: bad
pairs: []
""",
        encoding="utf-8",
    )

    try:
        load_corpus_manifest(manifest)
    except ValueError as exc:
        assert "Unsupported corpus schema_version" in str(exc)
    else:
        raise AssertionError("expected schema rejection")


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
