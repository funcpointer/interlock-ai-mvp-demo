from pathlib import Path

from interlock_mvp.core.artifacts import write_json
from interlock_mvp.core.eval import run_eval


def test_eval_fails_uncited_finding(tmp_path: Path) -> None:
    write_json(
        tmp_path / "findings.json",
        records=[
            {
                "finding_id": "f1",
                "finding_type": "value_mismatch",
                "summary": "Possible discrepancy.",
                "verifier_notes": "ok",
                "evidence_a": None,
                "evidence_b": None,
            }
        ],
    )
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text("expected_findings: []\n", encoding="utf-8")
    ok, issues = run_eval(tmp_path, eval_path)
    assert not ok
    assert any("lacks source citation" in issue for issue in issues)
