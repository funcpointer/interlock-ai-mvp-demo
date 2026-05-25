from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .artifacts import read_artifact
from .verification import authored_language_violations


def run_eval(run_dir: Path, eval_path: Path) -> tuple[bool, list[str]]:
    spec = yaml.safe_load(eval_path.read_text(encoding="utf-8")) or {}
    findings_payload = read_artifact(run_dir / "findings.json")
    findings: list[dict[str, Any]] = findings_payload.get("records", [])
    reasoning = _read_reasoning(run_dir)
    issues: list[str] = []

    for finding in findings:
        if finding.get("finding_type") != "coverage_warning":
            if not _has_citation(finding):
                issues.append(f"finding {finding.get('finding_id')} lacks source citation")
        authored = " ".join(
            str(finding.get(field, ""))
            for field in ("summary", "verifier_notes")
        )
        violations = authored_language_violations(authored)
        if violations:
            issues.append(f"finding {finding.get('finding_id')} has banned authored language: {', '.join(violations)}")

    for expected in spec.get("expected_findings", []):
        if not _matches_any(findings, expected, reasoning):
            issues.append(f"missing expected finding: {expected}")

    for forbidden in spec.get("forbidden_findings", []):
        if _matches_any(findings, forbidden, reasoning):
            issues.append(f"forbidden finding present: {forbidden}")

    coverage_findings = [finding for finding in findings if finding.get("finding_type") == "coverage_warning"]
    for expected in spec.get("expected_coverage_warnings", []):
        if not _matches_any(coverage_findings, expected, reasoning):
            issues.append(f"missing expected coverage warning: {expected}")

    if "max_review_required" in spec:
        count = sum(1 for finding in findings if finding.get("severity") == "review_required")
        if count > int(spec["max_review_required"]):
            issues.append(f"review_required count {count} exceeds max_review_required {spec['max_review_required']}")

    if "max_findings" in spec:
        count = len(findings)
        if count > int(spec["max_findings"]):
            issues.append(f"finding count {count} exceeds max_findings {spec['max_findings']}")

    return not issues, issues


def _has_citation(finding: dict[str, Any]) -> bool:
    for key in ("evidence_a", "evidence_b"):
        citation = finding.get(key)
        if citation and citation.get("page") and citation.get("quote") and citation.get("crop_path"):
            return True
    return False


def _read_reasoning(run_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    path = run_dir / "reasoning_graph.json"
    if not path.exists():
        return {"alignment": {}, "comparison": {}, "absence_search": {}}
    payload = read_artifact(path)
    return {
        "alignment": {item["alignment_id"]: item for item in payload.get("alignments", [])},
        "comparison": {item["comparison_id"]: item for item in payload.get("comparisons", [])},
        "absence_search": {item["absence_id"]: item for item in payload.get("absence_searches", [])},
    }


def _matches_any(findings: list[dict[str, Any]], matcher: dict[str, Any], reasoning: dict[str, dict[str, dict[str, Any]]]) -> bool:
    return any(_matches(finding, matcher, reasoning) for finding in findings)


def _matches(
    finding: dict[str, Any],
    matcher: dict[str, Any],
    reasoning: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> bool:
    for key, expected in matcher.items():
        if key in {"alignment", "comparison", "absence_search"}:
            if not isinstance(expected, dict):
                return False
            decision_id = finding.get(f"{key}_id") if key != "absence_search" else finding.get("absence_id")
            decision = (reasoning or {}).get(key, {}).get(decision_id)
            if not decision or not _matches(decision, expected, reasoning):
                return False
            continue
        if key == "rejected_b_claim_count_max":
            if len(finding.get("rejected_b_claim_ids", [])) > int(expected):
                return False
            continue
        if isinstance(expected, dict):
            actual = finding.get(key)
            if not isinstance(actual, dict):
                return False
            if not _matches(actual, expected, reasoning):
                return False
            continue
        if key.endswith("_contains"):
            actual_key = key.removesuffix("_contains")
            if str(expected).lower() not in str(finding.get(actual_key, "")).lower():
                return False
            continue
        if key.endswith("_in"):
            actual_key = key.removesuffix("_in")
            if finding.get(actual_key) not in expected:
                return False
            continue
        if key == "expected_pages":
            pages = set()
            for citation_key in ("evidence_a", "evidence_b"):
                citation = finding.get(citation_key)
                if citation:
                    pages.add(citation.get("page"))
            if not set(expected).issubset(pages):
                return False
            continue
        if finding.get(key) != expected:
            return False
    return True
