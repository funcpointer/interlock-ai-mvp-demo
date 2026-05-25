from pathlib import Path

from interlock_mvp.core.models import DiffGraph, DocumentGraph, EvidenceItem
from interlock_mvp.core.search import expand_query, search_run, write_search_index


def test_expand_query_uses_glossary_aliases() -> None:
    terms = expand_query("transformer rating", Path("examples/aes_glossary.yaml"))

    assert "transformer rating" in terms
    assert "xfmr" in terms
    assert "kva" in terms


def test_search_run_returns_cited_artifact_hits(tmp_path: Path) -> None:
    evidence = [
        EvidenceItem(
            evidence_id="ev1",
            doc_id="A",
            page=7,
            bbox=[1, 2, 3, 4],
            region_id="r1",
            kind="parameter_value",
            subject="XFMR",
            parameter="rating",
            value="1000",
            unit="kVA",
            raw_text="1000KVA XFMR",
            normalized_text="1000kva xfmr",
            normalized_value="1000 kva",
            confidence="high",
            source_method="test",
            crop_path="crops/A_p7_r1.png",
            context_id="A:tcc3",
        )
    ]
    count = write_search_index(
        tmp_path,
        evidence=evidence,
        doc_graph_a=DocumentGraph(doc_id="A"),
        doc_graph_b=DocumentGraph(doc_id="B"),
        diff_graph=DiffGraph(),
        findings=[],
    )

    hits = search_run(tmp_path, "transformer rating", glossary_path=Path("examples/aes_glossary.yaml"))

    assert count == 1
    assert (tmp_path / "search" / "second_brain.sqlite").exists()
    assert hits
    assert hits[0]["record_id"] == "ev1"
    assert hits[0]["doc_id"] == "A"
    assert hits[0]["page"] == 7
    assert "sqlite_fts" in hits[0]["retrieval_methods"]
