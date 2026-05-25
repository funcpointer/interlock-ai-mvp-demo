from pathlib import Path

import interlock_mvp.streamlit_app as app
from interlock_mvp.streamlit_app import _input_options, _safe_upload_name


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
