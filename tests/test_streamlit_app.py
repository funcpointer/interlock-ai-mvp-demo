from pathlib import Path

import interlock_mvp.streamlit_app as app
from interlock_mvp.streamlit_app import (
    ARTIFACT_DOWNLOADS,
    WIKI_PREVIEW_FILES,
    _citation_label,
    _context_signal_label,
    _download_name,
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


def test_context_signal_labels_are_reviewer_facing() -> None:
    assert _context_signal_label("context_room") == "same section/table type"
    assert _context_signal_label("graph_alignment") == "document graph aligned the claims"
    assert _context_signal_label("possible_equivalent_elsewhere") == "possible equivalent evidence elsewhere"
    assert _context_signal_label("custom_signal") == "custom signal"


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
