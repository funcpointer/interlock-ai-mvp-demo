from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from hashlib import blake2b
from pathlib import Path
from typing import Any

from .context_memory import context_memory_search_records
from .domain import DomainDictionary
from .models import SCHEMA_VERSION
from .models import ContextMemory, DiffGraph, DocumentGraph, EvidenceItem, Finding, ReasoningGraph

LANCEDB_VECTOR_DIM = 128
LANCEDB_TABLE = "review_records"
LANCEDB_EMBEDDING = "deterministic_hash_v1"
LANCEDB_MAX_DISTANCE = 1.45


def write_search_index(
    run_dir: Path,
    *,
    evidence: list[EvidenceItem],
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    diff_graph: DiffGraph,
    findings: list[Finding],
    reasoning_graph: ReasoningGraph | None = None,
    context_memory: ContextMemory | None = None,
) -> int:
    search_dir = run_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    records = []
    records.extend(_evidence_records(evidence))
    records.extend(_graph_records(doc_graph_a))
    records.extend(_graph_records(doc_graph_b))
    records.extend(_diff_records(diff_graph))
    if reasoning_graph:
        records.extend(_reasoning_records(reasoning_graph))
    if context_memory:
        records.extend(context_memory_search_records(context_memory))
    records.extend(_finding_records(findings))
    _write_jsonl(search_dir / "review_map.jsonl", records)
    _write_second_brain(search_dir / "second_brain.sqlite", records)
    _write_lancedb(search_dir / "lancedb", records)
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
        for method, record in _retrieval_records(search_dir, term):
            search_id = str(record.get("search_id") or record.get("record_id") or record.get("text"))
            item = scored.setdefault(
                search_id,
                {
                    **record,
                    "score": 0,
                    "matched_terms": [],
                    "retrieval_methods": [],
                },
            )
            score = 10 if idx == 0 else 3
            score += _source_boost(record)
            if method == "sqlite_fts":
                score += 4
            if method == "lancedb":
                score += 3
            if term.lower() == str(record.get("subject", "")).lower():
                score += 5
            if term.lower() in str(record.get("parameter", "")).lower():
                score += 2
            if str(record.get("quote", "")).lower().startswith("footnote"):
                score -= 4
            item["score"] += score
            item["matched_terms"].append(term)
            item["retrieval_methods"].append(method)

    results = sorted(
        scored.values(),
        key=lambda item: (-int(item["score"]), str(item.get("doc_id", "")), int(item.get("page") or 0), str(item.get("search_id", ""))),
    )
    for result in results:
        result["matched_terms"] = _dedup_preserve_order(result["matched_terms"])
        result["retrieval_methods"] = _dedup_preserve_order(result["retrieval_methods"])
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


def _reasoning_records(reasoning_graph: ReasoningGraph) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for alignment in reasoning_graph.alignments:
        records.append(
            {
                "search_id": f"alignment:{alignment.alignment_id}",
                "source": "alignment",
                "record_id": alignment.alignment_id,
                "doc_id": "",
                "page": None,
                "context_id": "",
                "subject": alignment.subject_method,
                "parameter": alignment.parameter_method,
                "value": alignment.confidence,
                "unit": "",
                "quote": alignment.rationale,
                "crop_path": "",
                "text": " ".join(
                    [
                        alignment.alignment_id,
                        alignment.diff_id,
                        alignment.a_claim_id,
                        alignment.b_claim_id,
                        alignment.subject_method,
                        alignment.parameter_method,
                        alignment.context_method,
                        alignment.confidence,
                        alignment.rationale,
                    ]
                ),
            }
        )
    for comparison in reasoning_graph.comparisons:
        records.append(
            {
                "search_id": f"comparison:{comparison.comparison_id}",
                "source": "comparison",
                "record_id": comparison.comparison_id,
                "doc_id": "",
                "page": None,
                "context_id": "",
                "subject": comparison.comparison_type,
                "parameter": comparison.unit_method,
                "value": str(comparison.deterministic),
                "unit": "",
                "quote": comparison.rationale,
                "crop_path": "",
                "text": " ".join(
                    [
                        comparison.comparison_id,
                        comparison.diff_id,
                        comparison.alignment_id or "",
                        comparison.comparison_type,
                        comparison.unit_method,
                        comparison.verifier_status,
                        *comparison.plausibility_notes,
                        comparison.rationale,
                    ]
                ),
            }
        )
    for absence in reasoning_graph.absence_searches:
        records.append(
            {
                "search_id": f"absence:{absence.absence_id}",
                "source": "absence_search",
                "record_id": absence.absence_id,
                "doc_id": absence.searched_doc_id,
                "page": None,
                "context_id": " ".join(absence.searched_context_ids),
                "subject": " ".join(absence.query_terms),
                "parameter": " ".join(absence.searched_parameters),
                "value": absence.coverage_status,
                "unit": "",
                "quote": absence.rationale,
                "crop_path": "",
                "text": " ".join(
                    [
                        absence.absence_id,
                        absence.diff_id,
                        absence.a_subject_id or "",
                        absence.a_claim_id or "",
                        absence.searched_doc_id,
                        absence.coverage_status,
                        absence.confidence,
                        *absence.query_terms,
                        *absence.searched_context_ids,
                        *absence.candidate_ids_considered,
                        absence.rationale,
                    ]
                ),
            }
        )
    return records


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


def _write_second_brain(path: Path, records: list[dict[str, Any]]) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE records (
              search_id TEXT PRIMARY KEY,
              source TEXT,
              doc_id TEXT,
              page INTEGER,
              context_id TEXT,
              subject TEXT,
              parameter TEXT,
              value TEXT,
              quote TEXT,
              crop_path TEXT,
              text TEXT,
              payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE records_fts USING fts5(
              search_id UNINDEXED,
              source,
              doc_id,
              context_id,
              subject,
              parameter,
              value,
              quote,
              text
            )
            """
        )
        for record in records:
            row = (
                str(record.get("search_id", "")),
                str(record.get("source", "")),
                str(record.get("doc_id", "")),
                record.get("page"),
                str(record.get("context_id", "")),
                str(record.get("subject", "")),
                str(record.get("parameter", "")),
                str(record.get("value", "")),
                str(record.get("quote", "")),
                str(record.get("crop_path", "")),
                str(record.get("text", "")),
                json.dumps(record, sort_keys=True),
            )
            conn.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            conn.execute(
                "INSERT INTO records_fts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row[0], row[1], row[2], row[4], row[5], row[6], row[7], row[8], row[10]),
            )
        conn.commit()
    finally:
        conn.close()


def _write_lancedb(path: Path, records: list[dict[str, Any]]) -> None:
    meta_path = path.parent / "lancedb_meta.json"
    if path.exists():
        shutil.rmtree(path)
    rows = [
        {
            "search_id": str(record.get("search_id", "")),
            "source": str(record.get("source", "")),
            "doc_id": str(record.get("doc_id", "")),
            "page": int(record["page"]) if record.get("page") is not None else -1,
            "subject": str(record.get("subject", "")),
            "parameter": str(record.get("parameter", "")),
            "text": str(record.get("text", "")),
            "payload": json.dumps(record, sort_keys=True),
            "vector": _text_vector(_record_embedding_text(record)),
        }
        for record in records
        if str(record.get("search_id", ""))
    ]
    if not rows:
        _write_lancedb_meta(meta_path, ok=False, records=0, message="no records")
        return
    try:
        import lancedb

        db = lancedb.connect(str(path))
        with _suppress_stderr_fd():
            db.create_table(LANCEDB_TABLE, data=rows, mode="overwrite")
        _write_lancedb_meta(meta_path, ok=True, records=len(rows), message="created")
    except Exception as exc:
        _write_lancedb_meta(meta_path, ok=False, records=0, message=f"{type(exc).__name__}: {exc}")


def _write_lancedb_meta(path: Path, *, ok: bool, records: int, message: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": ok,
                "records": records,
                "message": message,
                "table": LANCEDB_TABLE,
                "embedding": LANCEDB_EMBEDDING,
                "max_distance": LANCEDB_MAX_DISTANCE,
                "vector_dim": LANCEDB_VECTOR_DIM,
                "authority": "derived_search_only",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_aliases(glossary_path: Path | None) -> dict[str, list[str]]:
    if not glossary_path or not glossary_path.exists():
        return {}
    domain = DomainDictionary.from_yaml(glossary_path)
    return {key: [str(value) for value in values] for key, values in domain.search_aliases().items()}


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
                try:
                    records.append(json.loads(text))
                except json.JSONDecodeError:
                    continue
        return records
    return _python_search_records(search_dir, term)


def _retrieval_records(search_dir: Path, term: str) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    records.extend(("sqlite_fts", record) for record in _sqlite_records(search_dir / "second_brain.sqlite", term))
    records.extend(("lancedb", record) for record in _lancedb_records(search_dir / "lancedb", term))
    records.extend(("rg", record) for record in _rg_records(search_dir, term))
    return records


def _sqlite_records(path: Path, term: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    query = _fts_query(term)
    if not query:
        return []
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT records.payload
            FROM records_fts
            JOIN records ON records_fts.search_id = records.search_id
            WHERE records_fts MATCH ?
            ORDER BY bm25(records_fts)
            LIMIT 100
            """,
            (query,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _lancedb_records(path: Path, term: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import lancedb

        db = lancedb.connect(str(path))
        table = db.open_table(LANCEDB_TABLE)
        rows = table.search(_text_vector(term)).limit(100).to_list()
    except Exception:
        return []
    records: list[dict[str, Any]] = []
    for row in rows:
        distance = row.get("_distance")
        if distance is not None and float(distance) > LANCEDB_MAX_DISTANCE:
            continue
        try:
            record = json.loads(str(row.get("payload", "{}")))
        except json.JSONDecodeError:
            continue
        record["lancedb_distance"] = distance
        records.append(record)
    return records


def _fts_query(term: str) -> str:
    tokens = [token for token in term.replace("-", " ").replace("_", " ").split() if token]
    cleaned = [token.replace('"', "").replace("'", "") for token in tokens]
    cleaned = [token for token in cleaned if token]
    return " OR ".join(f'"{token}"' for token in cleaned)


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
    if source == "context_trail":
        return 6
    if source == "context_room":
        return 5
    if source == "claim":
        return 3
    return 0


def _record_embedding_text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key, ""))
        for key in ["source", "subject", "parameter", "value", "unit", "quote", "text", "context_id"]
    )


def _text_vector(text: str) -> list[float]:
    vector = [0.0] * LANCEDB_VECTOR_DIM
    features = _text_features(text)
    if not features:
        return vector
    for feature in features:
        digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % LANCEDB_VECTOR_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def _text_features(text: str) -> list[str]:
    normalized = text.lower().replace("%z", " impedance percent ")
    tokens = [token for token in normalized.replace("-", " ").replace("_", " ").split() if token]
    cleaned = ["".join(ch for ch in token if ch.isalnum() or ch in {"%", "."}).strip(".") for token in tokens]
    cleaned = [token for token in cleaned if token]
    features = cleaned[:]
    features.extend(f"{a} {b}" for a, b in zip(cleaned, cleaned[1:]))
    return features


def _dedup_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


@contextmanager
def _suppress_stderr_fd():
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)
