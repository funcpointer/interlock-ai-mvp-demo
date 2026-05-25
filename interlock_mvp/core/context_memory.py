from __future__ import annotations

from collections import defaultdict

from .models import ContextMemory, ContextRoom, ContextTrail, DocumentGraph, EvidenceItem, Finding
from .normalization import normalize_key


def build_context_memory(
    *,
    doc_graph_a: DocumentGraph,
    doc_graph_b: DocumentGraph,
    evidence: list[EvidenceItem],
    findings: list[Finding],
) -> ContextMemory:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    findings_by_context: dict[str, set[str]] = defaultdict(set)
    evidence_by_context: dict[str, set[str]] = defaultdict(set)
    for item in evidence:
        if item.context_id:
            evidence_by_context[item.context_id].add(item.evidence_id)
    for finding in findings:
        for citation in [finding.evidence_a, finding.evidence_b]:
            if not citation:
                continue
            item = evidence_by_id.get(citation.evidence_id)
            if item and item.context_id:
                findings_by_context[item.context_id].add(finding.finding_id)

    rooms: list[ContextRoom] = []
    for graph in [doc_graph_a, doc_graph_b]:
        subject_ids_by_context: dict[str, set[str]] = defaultdict(set)
        claim_ids_by_context: dict[str, set[str]] = defaultdict(set)
        for subject in graph.subjects:
            for context_id in subject.context_ids:
                subject_ids_by_context[context_id].add(subject.subject_id)
        for claim in graph.claims:
            claim_ids_by_context[claim.context_id].add(claim.claim_id)
        ordered_contexts = sorted(graph.contexts, key=lambda context: (context.page_span[0] if context.page_span else 0, context.canonical_label))
        room_ids = [_room_id(context.context_id) for context in ordered_contexts]
        for idx, context in enumerate(ordered_contexts):
            room_id = room_ids[idx]
            neighbors = []
            if idx > 0:
                neighbors.append(room_ids[idx - 1])
            if idx + 1 < len(room_ids):
                neighbors.append(room_ids[idx + 1])
            room_evidence_ids = sorted(evidence_by_context.get(context.context_id, set()))
            room_finding_ids = sorted(findings_by_context.get(context.context_id, set()))
            room_subject_ids = sorted(subject_ids_by_context.get(context.context_id, set()))
            room_claim_ids = sorted(claim_ids_by_context.get(context.context_id, set()))
            salience = len(room_finding_ids) * 10 + len(room_claim_ids) * 2 + len(room_subject_ids)
            rooms.append(
                ContextRoom(
                    room_id=room_id,
                    doc_id=context.doc_id,
                    context_id=context.context_id,
                    canonical_label=context.canonical_label,
                    kind=context.kind,
                    page_span=context.page_span,
                    region_ids=context.region_ids,
                    subject_ids=room_subject_ids,
                    claim_ids=room_claim_ids,
                    evidence_ids=room_evidence_ids,
                    finding_ids=room_finding_ids,
                    neighboring_room_ids=neighbors,
                    memory_path=f"wiki/context-rooms/{room_id}.md",
                    summary=_room_summary(context.canonical_label, context.kind, context.page_span, room_subject_ids, room_claim_ids, room_finding_ids),
                    salience_score=salience,
                )
            )
    existing_context_ids = {room.context_id for room in rooms}
    for item in sorted(evidence, key=lambda evidence_item: (evidence_item.doc_id, evidence_item.page, evidence_item.evidence_id)):
        if item.kind != "coverage_warning":
            continue
        context_id = f"{item.doc_id}:coverage_p{item.page}"
        if context_id in existing_context_ids:
            continue
        room_id = _room_id(context_id)
        finding_ids = sorted(findings_by_context.get(context_id, set()))
        if not finding_ids:
            finding_ids = sorted(
                finding.finding_id
                for finding in findings
                for citation in [finding.evidence_a, finding.evidence_b]
                if citation and citation.evidence_id == item.evidence_id
            )
        rooms.append(
            ContextRoom(
                room_id=room_id,
                doc_id=item.doc_id,
                context_id=context_id,
                canonical_label=f"coverage_p{item.page}",
                kind="coverage_warning",
                page_span=[item.page],
                region_ids=[item.region_id],
                evidence_ids=[item.evidence_id],
                finding_ids=finding_ids,
                memory_path=f"wiki/context-rooms/{room_id}.md",
                summary=f"coverage_p{item.page} is a coverage-warning room for page {item.page}; extraction status `{item.value}`.",
                salience_score=10 + len(finding_ids) * 10,
            )
        )
        existing_context_ids.add(context_id)

    return ContextMemory(rooms=rooms, trails=_build_trails(rooms, findings))


def context_memory_search_records(context_memory: ContextMemory) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for room in context_memory.rooms:
        records.append(
            {
                "search_id": f"context_room:{room.room_id}",
                "source": "context_room",
                "record_id": room.room_id,
                "doc_id": room.doc_id,
                "page": room.page_span[0] if room.page_span else None,
                "context_id": room.context_id,
                "subject": " ".join(room.subject_ids),
                "parameter": "context_room",
                "value": room.canonical_label,
                "unit": "",
                "quote": room.summary,
                "crop_path": "",
                "text": " ".join(
                    [
                        room.room_id,
                        room.context_id,
                        room.canonical_label,
                        room.kind,
                        room.summary,
                        *room.subject_ids,
                        *room.claim_ids,
                        *room.finding_ids,
                    ]
                ),
            }
        )
    for trail in context_memory.trails:
        records.append(
            {
                "search_id": f"context_trail:{trail.trail_id}",
                "source": "context_trail",
                "record_id": trail.trail_id,
                "doc_id": "",
                "page": None,
                "context_id": " ".join(trail.room_ids),
                "subject": trail.name,
                "parameter": "context_trail",
                "value": trail.name,
                "unit": "",
                "quote": trail.rationale,
                "crop_path": "",
                "text": " ".join([trail.trail_id, trail.name, trail.rationale, *trail.room_ids, *trail.finding_ids, *trail.evidence_ids]),
            }
        )
    return records


def _build_trails(rooms: list[ContextRoom], findings: list[Finding]) -> list[ContextTrail]:
    rooms_by_finding: dict[str, list[ContextRoom]] = defaultdict(list)
    for room in rooms:
        for finding_id in room.finding_ids:
            rooms_by_finding[finding_id].append(room)

    trails: list[ContextTrail] = []
    for finding in findings:
        finding_rooms = sorted(rooms_by_finding.get(finding.finding_id, []), key=lambda room: (room.doc_id, room.page_span[0] if room.page_span else 0))
        room_ids = [room.room_id for room in finding_rooms]
        evidence_ids = []
        if finding.evidence_a:
            evidence_ids.append(finding.evidence_a.evidence_id)
        if finding.evidence_b:
            evidence_ids.append(finding.evidence_b.evidence_id)
        trails.append(
            ContextTrail(
                trail_id=f"trail_{normalize_key(finding.finding_id)}",
                name=f"{finding.subject} / {finding.parameter}",
                room_ids=room_ids,
                finding_ids=[finding.finding_id],
                evidence_ids=evidence_ids,
                rationale=f"Finding {finding.finding_id} connects cited evidence through {len(room_ids)} context room(s).",
            )
        )
    return trails


def _room_id(context_id: str) -> str:
    return f"room_{normalize_key(context_id)}"


def _room_summary(
    label: str,
    kind: str,
    pages: list[int],
    subject_ids: list[str],
    claim_ids: list[str],
    finding_ids: list[str],
) -> str:
    page_text = f"pages {pages}" if pages else "unknown pages"
    return (
        f"{label} is a {kind} context on {page_text}; "
        f"{len(subject_ids)} subject(s), {len(claim_ids)} claim(s), {len(finding_ids)} linked finding(s)."
    )
