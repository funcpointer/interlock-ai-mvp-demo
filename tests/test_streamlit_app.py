from pathlib import Path

import interlock_mvp.streamlit_app as app
from interlock_mvp.streamlit_app import (
    ARTIFACT_DOWNLOADS,
    WIKI_PREVIEW_FILES,
    _citation_label,
    _context_support_details,
    _download_name,
    _pairing_alternatives,
    _pairing_details,
    _comparison_details,
    _finding_title,
    _finding_caption,
    _why_flagged,
    _input_options,
    _mime_for,
    _new_run_dir,
    _preview_wiki_markdown,
    _safe_upload_name,
    _upload_errors,
    _wiki_pages,
    _wiki_page_label,
    _wiki_tab_label,
)


class FakeUpload:
    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self.size = size


def test_safe_upload_name_preserves_pdf_extension() -> None:
    assert _safe_upload_name("AES spec rev A.pdf", fallback="doc.pdf") == "AESspecrevA.pdf"


def test_safe_upload_name_rejects_non_pdf() -> None:
    assert _safe_upload_name("../secret.txt", fallback="doc.pdf") == "doc.pdf"


def test_input_options_fall_back_to_upload_only(monkeypatch) -> None:
    missing = Path("/tmp/interlock-missing.pdf")
    monkeypatch.setattr(app, "PUBLIC_SPEC", missing)
    monkeypatch.setattr(app, "PUBLIC_VERSION_REV", missing)
    monkeypatch.setattr(app, "PUBLIC_CROSS_DOC", missing)

    assert _input_options() == ["Upload PDFs"]


def test_public_demo_assets_are_packaged() -> None:
    assert app.PUBLIC_SPEC.exists()
    assert app.PUBLIC_VERSION_REV.exists()
    assert app.PUBLIC_CROSS_DOC.exists()
    assert _input_options()[0] == "Public version demo"


def test_uploaded_pdf_size_cap_reports_clear_error(monkeypatch) -> None:
    monkeypatch.setattr(app, "MAX_UPLOAD_BYTES", 10)
    errors = _upload_errors(FakeUpload("a.pdf", 11), FakeUpload("b.pdf", 2))

    assert len(errors) == 1
    assert "Doc A" in errors[0]
    assert "max upload size" in errors[0]


def test_streamlit_run_dirs_are_unique() -> None:
    first = _new_run_dir("streamlit-upload")
    second = _new_run_dir("streamlit-upload")

    assert first != second
    assert first.parent == app.RUN_ROOT
    assert first.name.startswith("streamlit-upload-")


def test_download_mime_types_are_specific() -> None:
    assert _mime_for("findings.json") == "application/json"
    assert _mime_for("report.md") == "text/markdown"
    assert _mime_for("crop.png") == "application/octet-stream"


def test_streamlit_exposes_context_layer_wiki_artifacts() -> None:
    assert "wiki/index.md" in ARTIFACT_DOWNLOADS
    assert "wiki/review-map.md" in ARTIFACT_DOWNLOADS
    assert "wiki/memory-palace.md" in ARTIFACT_DOWNLOADS
    assert WIKI_PREVIEW_FILES == ["wiki/index.md", "wiki/review-map.md", "wiki/memory-palace.md"]
    assert _download_name("wiki/index.md") == "wiki_index.md"


def test_wiki_pages_prioritize_entrypoints(tmp_path: Path) -> None:
    for name in ["wiki/context-rooms/room_a.md", "wiki/index.md", "wiki/memory-palace.md", "wiki/review-map.md"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# page\n", encoding="utf-8")

    assert _wiki_pages(tmp_path)[:3] == ["wiki/index.md", "wiki/review-map.md", "wiki/memory-palace.md"]
    assert "wiki/context-rooms/room_a.md" in _wiki_pages(tmp_path)


def test_wiki_preview_rewrites_internal_links_to_non_broken_labels() -> None:
    rendered = _preview_wiki_markdown("- [Review Map](review-map.md)\n- [[memory-palace|Memory Palace]]")

    assert "[Review Map]" not in rendered
    assert "**Review Map** (`review-map.md`)" in rendered
    assert "**Memory Palace** (`memory-palace.md`)" in rendered


def test_wiki_labels_are_human_readable() -> None:
    assert _wiki_tab_label("wiki/index.md") == "Index"
    assert _wiki_tab_label("wiki/review-map.md") == "Review Map"
    assert _wiki_tab_label("wiki/memory-palace.md") == "Memory Palace"
    assert _wiki_page_label("wiki/context-rooms/room_a.md") == "context-rooms/room_a"


def test_finding_title_uses_review_values_not_internal_ids() -> None:
    finding = {
        "finding_id": "find_00001",
        "finding_type": "value_mismatch",
        "subject": "XFMR",
        "parameter": "rating",
        "evidence_a": {"value": "140", "unit": "MVA"},
        "evidence_b": {"value": "120", "unit": "MVA"},
    }

    assert _finding_title(finding) == "XFMR rating: 140 MVA -> 120 MVA"


def test_version_citation_labels_are_reviewer_facing() -> None:
    finding = {"mode": "version"}

    assert _citation_label(finding, "A") == "Baseline (Doc A)"
    assert _citation_label(finding, "B") == "Revised (Doc B)"


def test_finding_card_copy_is_reviewer_native() -> None:
    finding = {
        "finding_type": "value_mismatch",
        "severity": "review_required",
        "authoritative_side": "B",
        "authority_basis": "protection_study ranks higher in configured AES precedence",
        "evidence_a": {"value": "1100", "unit": "kVA"},
        "evidence_b": {"value": "1000", "unit": "KVA"},
    }

    assert _why_flagged(finding) == "Doc B is treated as controlling, and its cited value does not match Doc A."
    assert _finding_caption(finding) == "review required | value mismatch | authority B - protection_study ranks higher in configured AES precedence"


def test_context_support_details_show_concrete_trace_without_signal_dump() -> None:
    finding = {
        "context_support_context_refs": [
            {"doc_id": "A", "label": "capacity ratings", "pages": [4]},
            {"doc_id": "B", "label": "capacity ratings", "pages": [3]},
        ],
        "context_support_search_ids": ["s1", "s2", "s3"],
        "context_support_signal_types": ["context_room", "graph_alignment", "search_hit"],
        "subject": "XFMR",
        "parameter": "rating",
    }

    assert _context_support_details(finding) == [
        "Compared sections: Doc A - capacity ratings (p4); Doc B - capacity ratings (p3)",
        "Related packet evidence: 3 search hit(s) for XFMR / rating",
    ]


def test_audit_trail_explains_pairing_without_repeating_citations() -> None:
    finding = {
        "pairing_subject_method": "exact",
        "pairing_parameter_method": "exact",
        "pairing_context_method": "cross_doc_bridge",
        "pairing_rationale": "A differs from B.",
        "pairing_candidate_pool_count": 4,
        "pairing_same_parameter_candidate_count": 3,
        "comparison_unit_method": "pint",
        "comparison_deterministic": True,
        "comparison_rationale": "A differs from B.",
        "plausibility_notes": ["decimal shift candidate"],
        "pairing_rejected_candidate_count": 2,
        "pairing_rejected_candidate_summaries": [
            'Doc B / other table: rating 900 kVA - "XFMR spare 900 kVA"',
        ],
    }

    assert _pairing_details(finding) == [
        "Candidate pool: 4 Doc B claim(s); 3 matched the parameter before value comparison",
        "Subject match: exact subject/tag match",
        "Parameter match: exact normalized parameter match",
        "Context match: different labels, but compatible review contexts",
        "Accepted pair rationale: A differs from B.",
    ]
    assert _comparison_details(finding) == [
        "Unit/value check: Pint unit equivalence first, then mismatch if values remain different",
        "Deterministic discrepancy: yes",
        "Check note: decimal shift candidate",
        "Comparison rationale: A differs from B.",
    ]
    assert _pairing_alternatives(finding) == [
        "Rejected 2 same-parameter Doc B candidate(s) after subject/context checks.",
        'Doc B / other table: rating 900 kVA - "XFMR spare 900 kVA"',
        "1 more candidate(s) omitted from this card; see reasoning_graph.json.",
    ]


def test_pairing_alternatives_states_when_pool_had_no_rejections() -> None:
    finding = {
        "pairing_same_parameter_candidate_count": 1,
        "pairing_rejected_candidate_count": 0,
        "pairing_rejected_candidate_summaries": [],
    }

    assert _pairing_alternatives(finding) == [
        "Only one Doc B claim matched this parameter; no same-parameter alternatives were rejected."
    ]
