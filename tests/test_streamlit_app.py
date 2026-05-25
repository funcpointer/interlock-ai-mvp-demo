from pathlib import Path

import interlock_mvp.streamlit_app as app
from interlock_mvp.streamlit_app import (
    ARTIFACT_DOWNLOADS,
    WIKI_PREVIEW_FILES,
    _context_signal_label,
    _download_name,
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
    assert _context_signal_label("context_room") == "same kind of document room/table/section"
    assert _context_signal_label("graph_alignment") == "graph links both cited claims through document context"
    assert _context_signal_label("possible_equivalent_elsewhere") == "search found possible equivalent evidence elsewhere"
    assert _context_signal_label("custom_signal") == "custom signal"
