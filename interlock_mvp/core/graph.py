from __future__ import annotations

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
) -> tuple[bool, str]:
    try:
        import kuzu

        db_path = run_dir / "graph.kuzu"
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)
        _create_schema(conn)
        _insert_nodes(conn, documents, pages, regions, evidence, findings, authority)
        if doc_graph_a and doc_graph_b and diff_graph:
            _insert_review_graph(conn, doc_graph_a, doc_graph_b, diff_graph)
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
        "CREATE REL TABLE IF NOT EXISTS DOCUMENT_HAS_PAGE(FROM Document TO Page);",
        "CREATE REL TABLE IF NOT EXISTS PAGE_HAS_REGION(FROM Page TO Region);",
        "CREATE REL TABLE IF NOT EXISTS REGION_SUPPORTS_EVIDENCE(FROM Region TO Evidence);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_CITES_EVIDENCE(FROM Finding TO Evidence);",
        "CREATE REL TABLE IF NOT EXISTS FINDING_HAS_AUTHORITY(FROM Finding TO AuthorityDecision);",
        "CREATE REL TABLE IF NOT EXISTS CONTEXT_HAS_SUBJECT(FROM Context TO Subject);",
        "CREATE REL TABLE IF NOT EXISTS SUBJECT_HAS_CLAIM(FROM Subject TO Claim);",
        "CREATE REL TABLE IF NOT EXISTS CLAIM_IN_CONTEXT(FROM Claim TO Context);",
        "CREATE REL TABLE IF NOT EXISTS DIFF_CITES_CLAIM(FROM DiffEdge TO Claim);",
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
