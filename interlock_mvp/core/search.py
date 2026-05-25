from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .models import DiffGraph, DocumentGraph, EvidenceItem, Finding


def write_search_index(
    run_dir: Path,
    *,
    evidence: list[EvidenceItem],
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    diff_graph: DiffGraph,
    findings: list[Finding],
) -> int:
    search_dir = run_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    records = []
    records.extend(_evidence_records(evidence))
    records.extend(_graph_records(doc_graph_a))
    records.extend(_graph_records(doc_graph_b))
    records.extend(_diff_records(diff_graph))
    records.extend(_finding_records(findings))
    _write_jsonl(search_dir / "review_map.jsonl", records)
    return len(records)


def expand_query(query: str, glossary_path: Path | None = None) -> list[str]:
    query = " ".join(query.split())
    if not query:
        return []
    terms = [query]
    aliases = _load_aliases(glossary_path)
    lowered = query.lower()
    tokens = set(lowered.replace("-", " ").replace("_", " ").split())
    for canonical, values in aliases.items():
        alias_set = {canonical.lower(), *(value.lower() for value in values)}
        if canonical.lower() in lowered or tokens.intersection(alias_set) or any(alias in lowered for alias in alias_set if " " in alias):
            terms.extend([canonical, *values])
    return _dedup_preserve_order(terms)


def search_run(run_dir: Path, query: str, *, glossary_path: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    search_dir = run_dir / "search"
    if not search_dir.exists():
        raise FileNotFoundError(f"missing search index: {search_dir}")
    terms = expand_query(query, glossary_path)
    if not terms:
        return []

    scored: dict[str, dict[str, Any]] = {}
    for idx, term in enumerate(terms):
        for record in _rg_records(search_dir, term):
            search_id = str(record.get("search_id") or record.get("record_id") or record.get("text"))
            item = scored.setdefault(
                search_id,
                {
                    **record,
                    "score": 0,
                    "matched_terms": [],
                },
            )
            score = 10 if idx == 0 else 3
            score += _source_boost(record)
            if term.lower() == str(record.get("subject", "")).lower():
                score += 5
            if term.lower() in str(record.get("parameter", "")).lower():
                score += 2
            if str(record.get("quote", "")).lower().startswith("footnote"):
                score -= 4
            item["score"] += score
            item["matched_terms"].append(term)

    results = sorted(
        scored.values(),
        key=lambda item: (-int(item["score"]), str(item.get("doc_id", "")), int(item.get("page") or 0), str(item.get("search_id", ""))),
    )
    for result in results:
        result["matched_terms"] = _dedup_preserve_order(result["matched_terms"])
    return results[:limit]


def _evidence_records(evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
    return [
        {
            "search_id": f"evidence:{item.evidence_id}",
            "source": "evidence",
            "record_id": item.evidence_id,
            "doc_id": item.doc_id,
            "page": item.page,
            "region_id": item.region_id,
            "context_id": item.context_id,
            "subject": item.subject,
            "parameter": item.parameter,
            "value": item.value,
            "unit": item.unit,
            "quote": item.raw_text,
            "crop_path": item.crop_path,
            "text": " ".join([item.subject, item.parameter, item.value, item.unit, item.raw_text]),
        }
        for item in evidence
    ]


def _graph_records(graph: DocumentGraph) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for context in graph.contexts:
        records.append(
            {
                "search_id": f"context:{context.context_id}",
                "source": "context",
                "record_id": context.context_id,
                "doc_id": context.doc_id,
                "page": context.page_span[0] if context.page_span else None,
                "context_id": context.context_id,
                "subject": "",
                "parameter": "context",
                "value": context.canonical_label,
                "unit": "",
                "quote": " ".join(context.raw_labels),
                "crop_path": "",
                "text": " ".join([context.canonical_label, context.kind, *context.raw_labels]),
            }
        )
    for subject in graph.subjects:
        records.append(
            {
                "search_id": f"subject:{subject.subject_id}",
                "source": "subject",
                "record_id": subject.subject_id,
                "doc_id": subject.doc_id,
                "page": None,
                "context_id": " ".join(subject.context_ids),
                "subject": subject.canonical_label,
                "parameter": "identity",
                "value": subject.canonical_label,
                "unit": "",
                "quote": " ".join(subject.raw_labels),
                "crop_path": "",
                "text": " ".join([subject.canonical_label, subject.kind, *subject.raw_labels, *subject.context_ids]),
            }
        )
    for claim in graph.claims:
        records.append(
            {
                "search_id": f"claim:{claim.claim_id}",
                "source": "claim",
                "record_id": claim.claim_id,
                "doc_id": claim.doc_id,
                "page": None,
                "context_id": claim.context_id,
                "subject": claim.subject_id,
                "parameter": claim.parameter,
                "value": claim.value,
                "unit": claim.unit,
                "quote": claim.raw_text,
                "crop_path": "",
                "text": " ".join([claim.subject_id, claim.parameter, claim.value, claim.unit, claim.raw_text, claim.context_id]),
            }
        )
    return records


def _diff_records(diff_graph: DiffGraph) -> list[dict[str, Any]]:
    return [
        {
            "search_id": f"diff:{edge.diff_id}",
            "source": "diff",
            "record_id": edge.diff_id,
            "doc_id": "",
            "page": None,
            "context_id": "",
            "subject": edge.subject,
            "parameter": edge.parameter,
            "value": edge.diff_type,
            "unit": "",
            "quote": edge.rationale,
            "crop_path": "",
            "text": " ".join([edge.subject, edge.parameter, edge.diff_type, edge.alignment_status, edge.rationale]),
        }
        for edge in diff_graph.edges
    ]


def _finding_records(findings: list[Finding]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for finding in findings:
        citation = finding.evidence_a or finding.evidence_b
        records.append(
            {
                "search_id": f"finding:{finding.finding_id}",
                "source": "finding",
                "record_id": finding.finding_id,
                "doc_id": citation.doc_id if citation else "",
                "page": citation.page if citation else None,
                "context_id": "",
                "subject": finding.subject,
                "parameter": finding.parameter,
                "value": finding.finding_type,
                "unit": "",
                "quote": finding.summary,
                "crop_path": citation.crop_path if citation else "",
                "text": " ".join([finding.subject, finding.parameter, finding.finding_type, finding.summary, finding.verifier_notes]),
            }
        )
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def _load_aliases(glossary_path: Path | None) -> dict[str, list[str]]:
    if not glossary_path or not glossary_path.exists():
        return {}
    payload = yaml.safe_load(glossary_path.read_text(encoding="utf-8")) or {}
    aliases = payload.get("aliases", {})
    return {str(key): [str(value) for value in values or []] for key, values in aliases.items()}


def _rg_records(search_dir: Path, term: str) -> list[dict[str, Any]]:
    if shutil.which("rg"):
        completed = subprocess.run(
            ["rg", "--json", "-i", "--fixed-strings", term, str(search_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode not in {0, 1}:
            return []
        records = []
        for line in completed.stdout.splitlines():
            event = json.loads(line)
            if event.get("type") != "match":
                continue
            text = event.get("data", {}).get("lines", {}).get("text", "").strip()
            if text:
                records.append(json.loads(text))
        return records
    return _python_search_records(search_dir, term)


def _python_search_records(search_dir: Path, term: str) -> list[dict[str, Any]]:
    needle = term.lower()
    records = []
    for path in search_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if needle in line.lower():
                records.append(json.loads(line))
    return records


def _source_boost(record: dict[str, Any]) -> int:
    source = record.get("source")
    if source == "finding":
        return 10
    if source == "diff":
        return 8
    if source == "claim":
        return 3
    return 0


def _dedup_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
