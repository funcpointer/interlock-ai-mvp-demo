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


def test_eval_enforces_max_findings(tmp_path: Path) -> None:
    write_json(
        tmp_path / "findings.json",
        records=[
            {
                "finding_id": "f1",
                "finding_type": "coverage_warning",
                "severity": "informational",
                "summary": "coverage note",
                "verifier_notes": "ok",
                "evidence_a": None,
                "evidence_b": None,
            }
        ],
    )
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text("expected_findings: []\nmax_findings: 0\n", encoding="utf-8")

    ok, issues = run_eval(tmp_path, eval_path)

    assert not ok
    assert any("exceeds max_findings" in issue for issue in issues)


def test_eval_matches_nested_evidence_contract(tmp_path: Path) -> None:
    write_json(
        tmp_path / "findings.json",
        records=[
            _finding(
                evidence_a={
                    "evidence_id": "ev1",
                    "doc_id": "A",
                    "page": 1,
                    "quote": "Equipment ID: XFMR-001 Rated Power: 1100 kVA",
                    "crop_path": "crops/ev1.png",
                    "value": "1100",
                    "unit": "kVA",
                },
                evidence_b={
                    "evidence_id": "ev2",
                    "doc_id": "B",
                    "page": 3,
                    "quote": "1 1000KVA XFMR 12 x FLA Inrush Point",
                    "crop_path": "crops/ev2.png",
                    "value": "1000",
                    "unit": "KVA",
                },
            )
        ],
    )
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text(
        """
expected_findings:
  - finding_type: value_mismatch
    subject_contains: XFMR
    parameter: rating
    severity_in: [review_required, possible_issue]
    evidence_a:
      page: 1
      value: "1100"
      unit: kVA
      quote_contains: Rated Power
    evidence_b:
      page: 3
      value: "1000"
      unit: KVA
      quote_contains: 1000KVA XFMR
""",
        encoding="utf-8",
    )

    ok, issues = run_eval(tmp_path, eval_path)

    assert ok, issues


def test_eval_rejects_expected_finding_with_wrong_nested_evidence(tmp_path: Path) -> None:
    write_json(
        tmp_path / "findings.json",
        records=[
            _finding(
                evidence_a={
                    "evidence_id": "ev1",
                    "doc_id": "A",
                    "page": 1,
                    "quote": "Equipment ID: XFMR-001 Primary Voltage: 12.47 kV",
                    "crop_path": "crops/ev1.png",
                    "value": "12.47",
                    "unit": "kV",
                },
                evidence_b={
                    "evidence_id": "ev2",
                    "doc_id": "B",
                    "page": 2,
                    "quote": "JCN80E IFLA=42A 5.75% Z 1000KVA delta-Y 480/277V",
                    "crop_path": "crops/ev2.png",
                    "value": "277",
                    "unit": "V",
                },
                parameter="primary_voltage",
            )
        ],
    )
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text(
        """
expected_findings:
  - finding_type: value_mismatch
    subject_contains: XFMR
    parameter: primary_voltage
    evidence_b:
      value: "13.8"
      unit: KV
      quote_contains: 13.8KV
""",
        encoding="utf-8",
    )

    ok, issues = run_eval(tmp_path, eval_path)

    assert not ok
    assert any("missing expected finding" in issue for issue in issues)


def test_eval_forbidden_can_target_nested_evidence(tmp_path: Path) -> None:
    write_json(
        tmp_path / "findings.json",
        records=[
            _finding(
                evidence_a={
                    "evidence_id": "ev1",
                    "doc_id": "A",
                    "page": 1,
                    "quote": "Equipment ID: XFMR-001 Primary Voltage: 12.47 kV",
                    "crop_path": "crops/ev1.png",
                    "value": "12.47",
                    "unit": "kV",
                },
                evidence_b={
                    "evidence_id": "ev2",
                    "doc_id": "B",
                    "page": 2,
                    "quote": "JCN80E IFLA=42A 5.75% Z 1000KVA delta-Y 480/277V",
                    "crop_path": "crops/ev2.png",
                    "value": "277",
                    "unit": "V",
                },
                parameter="primary_voltage",
            )
        ],
    )
    eval_path = tmp_path / "eval.yaml"
    eval_path.write_text(
        """
expected_findings: []
forbidden_findings:
  - finding_type: value_mismatch
    parameter: primary_voltage
    evidence_b:
      value: "277"
      unit: V
""",
        encoding="utf-8",
    )

    ok, issues = run_eval(tmp_path, eval_path)

    assert not ok
    assert any("forbidden finding present" in issue for issue in issues)


def _finding(
    *,
    evidence_a: dict[str, object],
    evidence_b: dict[str, object],
    parameter: str = "rating",
) -> dict[str, object]:
    return {
        "finding_id": "f1",
        "mode": "cross_doc",
        "finding_type": "value_mismatch",
        "severity": "possible_issue",
        "confidence": "medium",
        "subject": "XFMR-001",
        "parameter": parameter,
        "summary": "Possible discrepancy.",
        "authoritative_side": "B",
        "authority_basis": "test",
        "authority_confidence": 0.8,
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "plausibility_notes": [],
        "verifier_notes": "ok",
    }
