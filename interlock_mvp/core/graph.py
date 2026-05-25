from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def build_kuzu_graph(
    *,
    run_dir: Path,
    documents: list[Any],
    pages: list[Any],
    regions: list[Any],
    evidence: list[Any],
    findings: list[Any],
    authority: Any,
    doc_graph_a: Any | None = None,
    doc_graph_b: Any | None = None,
    diff_graph: Any | None = None,
    reasoning_graph: Any | None = None,
) -> tuple[bool, str]:
    try:
        import kuzu

        db_path = run_dir / "graph.kuzu"
        if db_path.is_dir():
            shutil.rmtree(db_path)
        elif db_path.exists():
            db_path.unlink()
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)
        _create_schema(conn)
        _insert_nodes(conn, documents, pages, regions, evidence, findings, authority)
        if doc_graph_a and doc_graph_b and diff_graph:
            _insert_review_graph(conn, doc_graph_a, doc_graph_b, diff_graph)
        if reasoning_graph:
            _insert_reasoning_graph(conn, reasoning_graph, findings)
        return True, "graph built"
    except Exception as exc:  # pragma: no cover - Kuzu can fail by platform/runtime
        return False, f"kuzu graph skipped: {exc}"


def _create_schema(conn) -> None:
    statements = [
        "CREATE NODE TABLE IF NOT EXISTS Document(id STRING, label STRING, doc_type STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Page(id STRING, page_num INT64, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Region(id STRING, text STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Evidence(id STRING, kind STRING, subject STRING, parameter STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Finding(id STRING, finding_type STRING, severity STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS AuthorityDecision(id STRING, side STRING, basis STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Context(id STRING, doc_id STRING, label STRING, kind STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Subject(id STRING, doc_id STRING, label STRING, kind STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS Claim(id STRING, doc_id STRING, parameter STRING, value STRING, unit STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS DiffEdge(id STRING, diff_type STRING, status STRING, subject STRING, parameter STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS AlignmentDecision(id STRING, diff_id STRING, subject_method STRING, parameter_method STRING, context_method STRING, confidence STRING, accepted BOOL, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS ComparisonDecision(id STRING, diff_id STRING, comparison_type STRING, unit_method STRING, verifier_status STRING, PRIMARY KEY(id));",
        "CREATE NODE TABLE IF NOT EXISTS AbsenceSearch(id STRING, diff_id STRING, searched_doc_id STRING, coverage_status STRING, confidence STRING, PRIMARY KEY(id));",
        "CREATE REL TABLE IF NOT EXISTS DOCUMENT_HAS_PAGE(FROM Document TO Page);",
        "CREATE REL TABLE IF NOT EXISTS PAGE_HAS_REGION(FROM Page TO Region);",
        "CREATE REL TABLE IF NOT EXISTS REGION_SUPPORTS_EVIDENCE(FROM Region TO Evidence);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_CITES_EVIDENCE(FROM Finding TO Evidence);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_HAS_AUTHORITY(FROM Finding TO AuthorityDecision);",
        "CREATE REL TABLE IF NOT EXISTS CONTEXT_HAS_SUBJECT(FROM Context TO Subject);",
        "CREATE REL TABLE IF NOT EXISTS SUBJECT_HAS_CLAIM(FROM Subject TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS CLAIM_IN_CONTEXT(FROM Claim TO Context);",
        "CREATE REL TABLE IF NOT EXISTS DIFF_CITES_CLAIM(FROM DiffEdge TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS ALIGNMENT_LEFT_CLAIM(FROM AlignmentDecision TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS ALIGNMENT_RIGHT_CLAIM(FROM AlignmentDecision TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS ALIGNMENT_REJECTED_CLAIM(FROM AlignmentDecision TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS COMPARISON_FROM_ALIGNMENT(FROM ComparisonDecision TO AlignmentDecision);",
        "CREATE REL TABLE IF NOT EXISTS ABSENCE_SEARCHED_CONTEXT(FROM AbsenceSearch TO Context);",
        "CREATE REL TABLE IF NOT EXISTS ABSENCE_REJECTED_CLAIM(FROM AbsenceSearch TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS ABSENCE_REJECTED_SUBJECT(FROM AbsenceSearch TO Subject);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_FROM_COMPARISON(FROM Finding TO ComparisonDecision);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_FROM_ABSENCE_SEARCH(FROM Finding TO AbsenceSearch);",
    ]
    for statement in statements:
        conn.execute(statement)


def _insert_nodes(conn, documents, pages, regions, evidence, findings, authority) -> None:
    conn.execute("CREATE (:AuthorityDecision {id: 'authority', side: $side, basis: $basis});", {"side": authority.authoritative_side, "basis": authority.basis})
    for doc in documents:
        conn.execute("CREATE (:Document {id: $id, label: $label, doc_type: $doc_type});", {"id": doc.doc_id, "label": doc.label, "doc_type": doc.doc_type})
    for page in pages:
        conn.execute("CREATE (:Page {id: $id, page_num: $page_num});", {"id": page.page_id, "page_num": page.page_num})
        conn.execute("MATCH (d:Document {id: $doc_id}), (p:Page {id: $page_id}) CREATE (d)-[:DOCUMENT_HAS_PAGE]->(p);", {"doc_id": page.doc_id, "page_id": page.page_id})
    for region in regions:
        conn.execute("CREATE (:Region {id: $id, text: $text});", {"id": region.region_id, "text": region.text[:500]})
        conn.execute("MATCH (p:Page {id: $page_id}), (r:Region {id: $region_id}) CREATE (p)-[:PAGE_HAS_REGION]->(r);", {"page_id": f"{region.doc_id}_p{region.page}", "region_id": region.region_id})
    for item in evidence:
        conn.execute("CREATE (:Evidence {id: $id, kind: $kind, subject: $subject, parameter: $parameter});", {"id": item.evidence_id, "kind": item.kind, "subject": item.subject, "parameter": item.parameter})
        conn.execute("MATCH (r:Region {id: $region_id}), (e:Evidence {id: $evidence_id}) CREATE (r)-[:REGION_SUPPORTS_EVIDENCE]->(e);", {"region_id": item.region_id, "evidence_id": item.evidence_id})
    for finding in findings:
        conn.execute("CREATE (:Finding {id: $id, finding_type: $finding_type, severity: $severity});", {"id": finding.finding_id, "finding_type": finding.finding_type, "severity": finding.severity})
        conn.execute("MATCH (f:Finding {id: $id}), (a:AuthorityDecision {id: 'authority'}) CREATE (f)-[:FINDING_HAS_AUTHORITY]->(a);", {"id": finding.finding_id})
        for citation in [finding.evidence_a, finding.evidence_b]:
            if citation:
                conn.execute("MATCH (f:Finding {id: $finding_id}), (e:Evidence {id: $evidence_id}) CREATE (f)-[:FINDING_CITES_EVIDENCE]->(e);", {"finding_id": finding.finding_id, "evidence_id": citation.evidence_id})


def _insert_review_graph(conn, doc_graph_a, doc_graph_b, diff_graph) -> None:
    for graph in [doc_graph_a, doc_graph_b]:
        for context in graph.contexts:
            conn.execute(
                "CREATE (:Context {id: $id, doc_id: $doc_id, label: $label, kind: $kind});",
                {"id": context.context_id, "doc_id": context.doc_id, "label": context.canonical_label, "kind": context.kind},
            )
        for subject in graph.subjects:
            conn.execute(
                "CREATE (:Subject {id: $id, doc_id: $doc_id, label: $label, kind: $kind});",
                {"id": subject.subject_id, "doc_id": subject.doc_id, "label": subject.canonical_label, "kind": subject.kind},
            )
            for context_id in subject.context_ids:
                conn.execute(
                    "MATCH (c:Context {id: $context_id}), (s:Subject {id: $subject_id}) CREATE (c)-[:CONTEXT_HAS_SUBJECT]->(s);",
                    {"context_id": context_id, "subject_id": subject.subject_id},
                )
        for claim in graph.claims:
            conn.execute(
                "CREATE (:Claim {id: $id, doc_id: $doc_id, parameter: $parameter, value: $value, unit: $unit});",
                {"id": claim.claim_id, "doc_id": claim.doc_id, "parameter": claim.parameter, "value": claim.value, "unit": claim.unit},
            )
            conn.execute(
                "MATCH (s:Subject {id: $subject_id}), (cl:Claim {id: $claim_id}) CREATE (s)-[:SUBJECT_HAS_CLAIM]->(cl);",
                {"subject_id": claim.subject_id, "claim_id": claim.claim_id},
            )
            conn.execute(
                "MATCH (c:Context {id: $context_id}), (cl:Claim {id: $claim_id}) CREATE (cl)-[:CLAIM_IN_CONTEXT]->(c);",
                {"context_id": claim.context_id, "claim_id": claim.claim_id},
            )
    for edge in diff_graph.edges:
        conn.execute(
            "CREATE (:DiffEdge {id: $id, diff_type: $diff_type, status: $status, subject: $subject, parameter: $parameter});",
            {
                "id": edge.diff_id,
                "diff_type": edge.diff_type,
                "status": edge.alignment_status,
                "subject": edge.subject,
                "parameter": edge.parameter,
            },
        )
        for node_id in [edge.a_node_id, edge.b_node_id]:
            if node_id and ":claim:" in node_id:
                conn.execute(
                    "MATCH (d:DiffEdge {id: $diff_id}), (c:Claim {id: $claim_id}) CREATE (d)-[:DIFF_CITES_CLAIM]->(c);",
                    {"diff_id": edge.diff_id, "claim_id": node_id},
                )


def _insert_reasoning_graph(conn, reasoning_graph, findings) -> None:
    for alignment in reasoning_graph.alignments:
        conn.execute(
            "CREATE (:AlignmentDecision {id: $id, diff_id: $diff_id, subject_method: $subject_method, parameter_method: $parameter_method, context_method: $context_method, confidence: $confidence, accepted: $accepted});",
            {
                "id": alignment.alignment_id,
                "diff_id": alignment.diff_id,
                "subject_method": alignment.subject_method,
                "parameter_method": alignment.parameter_method,
                "context_method": alignment.context_method,
                "confidence": alignment.confidence,
                "accepted": alignment.accepted,
            },
        )
        conn.execute(
            "MATCH (a:AlignmentDecision {id: $alignment_id}), (c:Claim {id: $claim_id}) CREATE (a)-[:ALIGNMENT_LEFT_CLAIM]->(c);",
            {"alignment_id": alignment.alignment_id, "claim_id": alignment.a_claim_id},
        )
        conn.execute(
            "MATCH (a:AlignmentDecision {id: $alignment_id}), (c:Claim {id: $claim_id}) CREATE (a)-[:ALIGNMENT_RIGHT_CLAIM]->(c);",
            {"alignment_id": alignment.alignment_id, "claim_id": alignment.b_claim_id},
        )
        for claim_id in alignment.rejected_b_claim_ids:
            conn.execute(
                "MATCH (a:AlignmentDecision {id: $alignment_id}), (c:Claim {id: $claim_id}) CREATE (a)-[:ALIGNMENT_REJECTED_CLAIM]->(c);",
                {"alignment_id": alignment.alignment_id, "claim_id": claim_id},
            )

    for comparison in reasoning_graph.comparisons:
        conn.execute(
            "CREATE (:ComparisonDecision {id: $id, diff_id: $diff_id, comparison_type: $comparison_type, unit_method: $unit_method, verifier_status: $verifier_status});",
            {
                "id": comparison.comparison_id,
                "diff_id": comparison.diff_id,
                "comparison_type": comparison.comparison_type,
                "unit_method": comparison.unit_method,
                "verifier_status": comparison.verifier_status,
            },
        )
        if comparison.alignment_id:
            conn.execute(
                "MATCH (c:ComparisonDecision {id: $comparison_id}), (a:AlignmentDecision {id: $alignment_id}) CREATE (c)-[:COMPARISON_FROM_ALIGNMENT]->(a);",
                {"comparison_id": comparison.comparison_id, "alignment_id": comparison.alignment_id},
            )

    for absence in reasoning_graph.absence_searches:
        conn.execute(
            "CREATE (:AbsenceSearch {id: $id, diff_id: $diff_id, searched_doc_id: $searched_doc_id, coverage_status: $coverage_status, confidence: $confidence});",
            {
                "id": absence.absence_id,
                "diff_id": absence.diff_id,
                "searched_doc_id": absence.searched_doc_id,
                "coverage_status": absence.coverage_status,
                "confidence": absence.confidence,
            },
        )
        for context_id in absence.searched_context_ids:
            conn.execute(
                "MATCH (a:AbsenceSearch {id: $absence_id}), (c:Context {id: $context_id}) CREATE (a)-[:ABSENCE_SEARCHED_CONTEXT]->(c);",
                {"absence_id": absence.absence_id, "context_id": context_id},
            )
        for candidate_id in absence.rejected_candidate_ids:
            if ":claim:" in candidate_id:
                conn.execute(
                    "MATCH (a:AbsenceSearch {id: $absence_id}), (c:Claim {id: $candidate_id}) CREATE (a)-[:ABSENCE_REJECTED_CLAIM]->(c);",
                    {"absence_id": absence.absence_id, "candidate_id": candidate_id},
                )
            elif ":subject:" in candidate_id:
                conn.execute(
                    "MATCH (a:AbsenceSearch {id: $absence_id}), (s:Subject {id: $candidate_id}) CREATE (a)-[:ABSENCE_REJECTED_SUBJECT]->(s);",
                    {"absence_id": absence.absence_id, "candidate_id": candidate_id},
                )

    comparison_ids = {comparison.comparison_id for comparison in reasoning_graph.comparisons}
    absence_ids = {absence.absence_id for absence in reasoning_graph.absence_searches}
    for finding in findings:
        if finding.comparison_id in comparison_ids:
            conn.execute(
                "MATCH (f:Finding {id: $finding_id}), (c:ComparisonDecision {id: $comparison_id}) CREATE (f)-[:FINDING_FROM_COMPARISON]->(c);",
                {"finding_id": finding.finding_id, "comparison_id": finding.comparison_id},
            )
        if finding.absence_id in absence_ids:
            conn.execute(
                "MATCH (f:Finding {id: $finding_id}), (a:AbsenceSearch {id: $absence_id}) CREATE (f)-[:FINDING_FROM_ABSENCE_SEARCH]->(a);",
                {"finding_id": finding.finding_id, "absence_id": finding.absence_id},
            )
