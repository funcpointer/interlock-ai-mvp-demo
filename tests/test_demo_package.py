import json
from pathlib import Path

from interlock_mvp.core.demo_package import DemoCase, write_demo_package


def test_demo_package_writes_static_site_and_copies_crops(tmp_path: Path) -> None:
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
                "evidence_a": {"page": 4, "quote": "84/112/140 MVA", "crop_path": "crops/a.png"},
                "evidence_b": None,
            }
        ],
    )
    _write_json(run_dir / "metrics.json", meta={"metrics": {"findings": 1, "review_required_findings": 1}})
    _write_json(run_dir / "triage.json", meta={"issues": []})
    (run_dir / "report.md").write_text("# Report", encoding="utf-8")

    site_dir = write_demo_package(
        out_dir=tmp_path / "demo",
        cases=[
            DemoCase(
                case_id="case",
                title="Case",
                run_dir=run_dir,
                claim="Claim",
                caveat="Caveat",
            )
        ],
    )

    html = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "InterLock AI MVP Demo" in html
    assert "find_00001" in html
    assert "assets/case/a.png" in html
    assert (site_dir / "assets" / "case" / "a.png").exists()
    assert (site_dir / "artifacts" / "case" / "findings.json").exists()
    assert (tmp_path / "demo" / "summary.md").exists()


def _write_json(path: Path, *, records: list[dict] | None = None, meta: dict | None = None) -> None:
    payload = {"schema_version": "test", "records": records or [], **(meta or {})}
    path.write_text(json.dumps(payload), encoding="utf-8")
