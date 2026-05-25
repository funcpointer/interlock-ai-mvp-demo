from pathlib import Path

import interlock_mvp.streamlit_app as app
from interlock_mvp.streamlit_app import _input_options, _mime_for, _new_run_dir, _safe_upload_name, _upload_errors


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
