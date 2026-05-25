import json
from pathlib import Path

import pytest

from interlock_mvp.ui import _resolve_artifact_path, render_run_page


def test_render_run_page_shows_findings_and_crop_links(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    crops = run_dir / "crops"
    crops.mkdir(parents=True)
    (crops / "a.png").write_bytes(b"fake")
    _write_json(
        run_dir / "findings.json",
        records=[
            {
                "finding_id": "find_00001",
                "finding_type": "value_mismatch",
                "severity": "review_required",
                "confidence": "high",
                "subject": "XFMR",
                "parameter": "rating",
                "summary": "A cites 140 MVA; B cites 120 MVA.",
                "authoritative_side": "B",
                "authority_basis": "revised document supersedes baseline",
                "evidence_a": {
                    "page": 4,
                    "quote": "Primary to Secondary Winding: 84/112/140 MVA",
                    "crop_path": "crops/a.png",
                },
                "evidence_b": None,
            }
        ],
    )
    _write_json(run_dir / "metrics.json", meta={"metrics": {"findings": 1, "review_required_findings": 1}})
    _write_json(run_dir / "triage.json", meta={"issues": []})

    html = render_run_page(run_dir)

    assert "find_00001" in html
    assert "XFMR / rating" in html
    assert "Primary to Secondary Winding" in html
    assert "/artifact?run=" in html
    assert "No triage issues" in html


def test_artifact_path_rejects_traversal(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(ValueError):
        _resolve_artifact_path(run_dir, "../secret.txt")


def _write_json(path: Path, *, records: list[dict] | None = None, meta: dict | None = None) -> None:
    payload = {"schema_version": "test", "records": records or [], **(meta or {})}
    path.write_text(json.dumps(payload), encoding="utf-8")
