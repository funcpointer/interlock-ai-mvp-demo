from pathlib import Path

from interlock_mvp.core.context_memory import build_context_memory, context_memory_search_records
from interlock_mvp.core.search import search_run, write_search_index
from interlock_mvp.core.models import (
    ClaimNode,
    ContextNode,
    DiffGraph,
    DocumentGraph,
    EvidenceCitation,
    EvidenceItem,
    Finding,
    SubjectNode,
)


def test_context_memory_builds_rooms_trails_and_search_records(tmp_path: Path) -> None:
    evidence_a = EvidenceItem(
        evidence_id="evA",
        doc_id="A",
        page=2,
        bbox=[1, 2, 3, 4],
        region_id="rA",
        kind="parameter_value",
        subject="XFMR-1",
        parameter="rating",
        value="1000",
        unit="kVA",
        raw_text="XFMR-1 Rated Power: 1000 kVA",
        normalized_text="xfmr 1 rated power 1000 kva",
        normalized_value="1000 kva",
        confidence="high",
        source_method="test",
        crop_path="crops/a.png",
        context_id="A:tcc1",
    )
    evidence_b = evidence_a.model_copy(update={"evidence_id": "evB", "doc_id": "B", "region_id": "rB", "value": "100", "context_id": "B:tcc1"})
    graph_a = DocumentGraph(
        doc_id="A",
        contexts=[_context("A:tcc1", "A")],
        subjects=[_subject("A:subject:xfmr_1", "A", "A:tcc1")],
        claims=[_claim("A:claim:evA", "A", "A:tcc1", "A:subject:xfmr_1", "evA", "1000")],
    )
    graph_b = DocumentGraph(
        doc_id="B",
        contexts=[_context("B:tcc1", "B")],
        subjects=[_subject("B:subject:xfmr_1", "B", "B:tcc1")],
        claims=[_claim("B:claim:evB", "B", "B:tcc1", "B:subject:xfmr_1", "evB", "100")],
    )
    finding = Finding(
        finding_id="find_00001",
        mode="version",
        finding_type="value_mismatch",
        severity="review_required",
        confidence="high",
        subject="XFMR-1",
        parameter="rating",
        summary="Possible discrepancy for XFMR-1 rating.",
        authoritative_side="B",
        authority_basis="revised document supersedes baseline",
        authority_confidence=1.0,
        evidence_a=EvidenceCitation(evidence_id="evA", doc_id="A", page=2, bbox=[1, 2, 3, 4], quote="1000 kVA", crop_path="crops/a.png", value="1000", unit="kVA"),
        evidence_b=EvidenceCitation(evidence_id="evB", doc_id="B", page=2, bbox=[1, 2, 3, 4], quote="100 kVA", crop_path="crops/b.png", value="100", unit="kVA"),
        verifier_notes="Deterministic graph verifier confirmed cited evidence.",
    )

    memory = build_context_memory(doc_graph_a=graph_a, doc_graph_b=graph_b, evidence=[evidence_a, evidence_b], findings=[finding])
    records = context_memory_search_records(memory)

    assert len(memory.rooms) == 2
    assert len(memory.trails) == 1
    assert memory.trails[0].room_ids == ["room_a_tcc1", "room_b_tcc1"]
    assert all(room.finding_ids == ["find_00001"] for room in memory.rooms)
    assert any(record["source"] == "context_room" for record in records)
    assert any(record["source"] == "context_trail" and "find_00001" in record["text"] for record in records)

    write_search_index(
        tmp_path,
        evidence=[evidence_a, evidence_b],
        doc_graph_a=graph_a,
        doc_graph_b=graph_b,
        diff_graph=DiffGraph(),
        findings=[finding],
        context_memory=memory,
    )
    hits = search_run(tmp_path, "context_room XFMR-1", glossary_path=None, limit=5)
    assert any(hit["source"] == "context_room" for hit in hits)


def _context(context_id: str, doc_id: str) -> ContextNode:
    return ContextNode(
        context_id=context_id,
        doc_id=doc_id,
        canonical_label="tcc1",
        raw_labels=["TCC 1"],
        kind="time_current_curve",
        page_span=[2],
        region_ids=[f"{doc_id}:r1"],
        confidence="high",
    )


def _subject(subject_id: str, doc_id: str, context_id: str) -> SubjectNode:
    return SubjectNode(
        subject_id=subject_id,
        doc_id=doc_id,
        canonical_label="XFMR-1",
        raw_labels=["XFMR-1"],
        kind="transformer",
        context_ids=[context_id],
        evidence_ids=[],
        confidence="high",
    )


def _claim(claim_id: str, doc_id: str, context_id: str, subject_id: str, evidence_id: str, value: str) -> ClaimNode:
    return ClaimNode(
        claim_id=claim_id,
        doc_id=doc_id,
        context_id=context_id,
        subject_id=subject_id,
        parameter="rating",
        value=value,
        unit="kVA",
        raw_text=f"{value} kVA",
        evidence_ids=[evidence_id],
        confidence="high",
    )
