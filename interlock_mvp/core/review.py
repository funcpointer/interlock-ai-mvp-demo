from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import ensure_run_dirs, write_json, write_object
from .authority import classify_doc_type, load_authority_config, resolve_authority, version_order_warning
from .candidates import evidence_lookup, generate_candidates
from .docgraph import build_diff_graph, build_document_graphs
from .evidence import mine_evidence
from .env import load_env_file, load_key_files
from .extraction import extract_pdf
from .graph import build_kuzu_graph
from .logging import JsonlLogger
from .models import ReviewRequest, ReviewResult
from .reasoning import build_reasoning_graph
from .report import render_report
from .search import write_search_index
from .verification import findings_from_reasoning_graph
from .wiki import write_review_wiki


def run_review(request: ReviewRequest) -> ReviewResult:
    started = time.time()
    ensure_run_dirs(request.out_dir)
    logger = JsonlLogger(request.out_dir / "logs.jsonl")
    warnings: list[str] = []
    stage_timings: dict[str, float] = {}
    metrics: dict[str, object] = {
        "mode": request.mode,
        "dry_run": request.dry_run,
        "no_cloud": request.no_cloud,
        "no_kuzu": request.no_kuzu,
        "max_candidates": request.max_candidates,
        "max_vlm_pages": request.max_vlm_pages,
        "max_cost_usd": request.max_cost_usd,
    }
    logger.event("run_started", mode=request.mode, out_dir=str(request.out_dir))
    stage_started = time.time()
    loaded_env_keys = load_env_file(request.env_file_path) + load_key_files()
    if loaded_env_keys:
        metrics["env_keys_loaded"] = sorted(key for key in loaded_env_keys if key.endswith("_API_KEY"))
    _finish_stage(
        logger,
        stage_timings,
        "load_environment",
        stage_started,
        env_keys_loaded=len(metrics.get("env_keys_loaded", [])),
    )

    stage_started = time.time()
    config = load_authority_config(request.authority_config_path)
    sample_a = _sample_text(request.doc_a_path)
    sample_b = _sample_text(request.doc_b_path)
    doc_a_type, doc_a_conf, doc_a_evidence = classify_doc_type(request.doc_a_path, sample_a, request.doc_a_type)
    doc_b_type, doc_b_conf, doc_b_evidence = classify_doc_type(request.doc_b_path, sample_b, request.doc_b_type)
    authority = resolve_authority(
        mode=request.mode,
        config=config,
        doc_a_type=doc_a_type,
        doc_b_type=doc_b_type,
        doc_a_confidence=doc_a_conf,
        doc_b_confidence=doc_b_conf,
    )
    warnings.extend(authority.warnings)
    if request.mode == "version":
        order_warning = version_order_warning(request.doc_a_path, request.doc_b_path)
        if order_warning:
            warnings.append(order_warning)
    _finish_stage(
        logger,
        stage_timings,
        "resolve_authority",
        stage_started,
        doc_a_type=doc_a_type,
        doc_b_type=doc_b_type,
        authoritative_side=authority.authoritative_side,
        authority_confidence=authority.confidence,
        warning_count=len(warnings),
    )

    role_a = "baseline" if request.mode == "version" else "comparison_input"
    role_b = "revised" if request.mode == "version" else "comparison_input"
    stage_started = time.time()
    doc_a, pages_a, regions_a, annotations_a, warnings_a = extract_pdf(
        request.doc_a_path,
        doc_id="A",
        label="Doc A",
        doc_type=doc_a_type,
        mode_role=role_a,
        out_dir=request.out_dir,
    )
    _finish_stage(
        logger,
        stage_timings,
        "extract_doc_a",
        stage_started,
        **_page_region_metrics(pages_a, regions_a, annotations_a),
        warning_count=len(warnings_a),
    )
    stage_started = time.time()
    doc_b, pages_b, regions_b, annotations_b, warnings_b = extract_pdf(
        request.doc_b_path,
        doc_id="B",
        label="Doc B",
        doc_type=doc_b_type,
        mode_role=role_b,
        out_dir=request.out_dir,
    )
    _finish_stage(
        logger,
        stage_timings,
        "extract_doc_b",
        stage_started,
        **_page_region_metrics(pages_b, regions_b, annotations_b),
        warning_count=len(warnings_b),
    )
    warnings.extend(warnings_a)
    warnings.extend(warnings_b)
    documents = [doc_a, doc_b]
    pages = pages_a + pages_b
    regions = regions_a + regions_b
    annotations = annotations_a + annotations_b

    stage_started = time.time()
    evidence = mine_evidence(pages=pages, regions=regions, annotations=annotations)
    evidence_metrics = _evidence_metrics(evidence)
    _finish_stage(logger, stage_timings, "mine_evidence", stage_started, **evidence_metrics)

    stage_started = time.time()
    graph_a, graph_b, evidence = build_document_graphs(regions=regions, evidence=evidence)
    diff_graph = build_diff_graph(graph_a, graph_b)
    diff_graph.edges.extend(_coverage_diff_edges(diff_graph, evidence))
    reasoning_graph = build_reasoning_graph(diff_graph, graph_a, graph_b)
    evidence_metrics = _evidence_metrics(evidence)
    graph_metrics = _graph_metrics(graph_a, graph_b, diff_graph)
    reasoning_metrics = _reasoning_metrics(reasoning_graph)
    _finish_stage(logger, stage_timings, "build_review_graph", stage_started, **graph_metrics, **reasoning_metrics)

    stage_started = time.time()
    candidates = generate_candidates(evidence, max_candidates=request.max_candidates, mode=request.mode)
    candidate_metrics = _candidate_metrics(candidates)
    _finish_stage(logger, stage_timings, "generate_candidates", stage_started, **candidate_metrics)

    stage_started = time.time()
    findings, verifier_warnings, verifier_metrics = findings_from_reasoning_graph(
        reasoning_graph=reasoning_graph,
        diff_edges=diff_graph.edges,
        evidence_by_id=evidence_lookup(evidence),
        authority=authority,
        mode=request.mode,
        no_cloud=request.no_cloud,
        dry_run=request.dry_run,
        max_cost_usd=request.max_cost_usd,
    )
    warnings.extend(verifier_warnings)
    metrics.update(verifier_metrics)
    finding_metrics = _finding_metrics(findings)
    _finish_stage(
        logger,
        stage_timings,
        "verify_findings",
        stage_started,
        **finding_metrics,
        warning_count=len(verifier_warnings),
    )

    stage_started = time.time()
    search_records = write_search_index(
        request.out_dir,
        evidence=evidence,
        doc_graph_a=graph_a,
        doc_graph_b=graph_b,
        diff_graph=diff_graph,
        reasoning_graph=reasoning_graph,
        findings=findings,
    )
    _finish_stage(logger, stage_timings, "write_search_index", stage_started, search_records=search_records)
    metrics["search_records"] = search_records

    if request.no_kuzu:
        graph_message = "skipped by --no-kuzu"
        logger.event("stage_skipped", stage="build_kuzu_graph", reason=graph_message)
    else:
        stage_started = time.time()
        graph_ok, graph_message = build_kuzu_graph(
            run_dir=request.out_dir,
            documents=documents,
            pages=pages,
            regions=regions,
            evidence=evidence,
            findings=findings,
        authority=authority,
        doc_graph_a=graph_a,
        doc_graph_b=graph_b,
        diff_graph=diff_graph,
        reasoning_graph=reasoning_graph,
    )
        if not graph_ok:
            warnings.append(graph_message)
        _finish_stage(logger, stage_timings, "build_kuzu_graph", stage_started, graph_ok=graph_ok, message=graph_message)
    metrics["kuzu_graph"] = graph_message
    metrics["documents"] = len(documents)
    metrics["pages"] = len(pages)
    metrics["regions"] = len(regions)
    metrics["annotations"] = len(annotations)
    metrics["evidence"] = len(evidence)
    metrics.update(evidence_metrics)
    metrics.update(graph_metrics)
    metrics.update(reasoning_metrics)
    metrics.update(candidate_metrics)
    metrics.update(finding_metrics)
    metrics["stage_seconds"] = stage_timings
    metrics["elapsed_seconds"] = round(time.time() - started, 3)

    run_id = datetime.now(UTC).strftime("run_%Y%m%dT%H%M%SZ")
    stage_started = time.time()
    write_object(
        request.out_dir / "manifest.json",
        {
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(),
        "request": request.model_dump(mode="json"),
        },
    )
    write_object(
        request.out_dir / "authority.json",
        {
            "config": config,
            "doc_type_evidence": {"A": doc_a_evidence, "B": doc_b_evidence},
            "decision": authority.model_dump(mode="json"),
        },
    )
    write_json(request.out_dir / "documents.json", records=documents)
    write_json(request.out_dir / "pages.json", records=pages)
    write_json(request.out_dir / "annotations.json", records=annotations)
    write_json(request.out_dir / "regions.json", records=regions)
    write_json(request.out_dir / "evidence.json", records=evidence)
    write_object(request.out_dir / "doc_graph_a.json", graph_a.model_dump(mode="json"))
    write_object(request.out_dir / "doc_graph_b.json", graph_b.model_dump(mode="json"))
    write_object(request.out_dir / "diff_graph.json", diff_graph.model_dump(mode="json"))
    write_object(request.out_dir / "reasoning_graph.json", reasoning_graph.model_dump(mode="json"))
    write_json(request.out_dir / "candidates.json", records=candidates)
    write_json(request.out_dir / "findings.json", records=findings)
    write_object(request.out_dir / "metrics.json", {"metrics": metrics, "warnings": warnings})
    render_report(
        path=request.out_dir / "report.md",
        findings=findings,
        authority=authority,
        metrics=metrics,
        warnings=warnings,
    )
    wiki_pages = write_review_wiki(
        request.out_dir,
        documents=documents,
        doc_graph_a=graph_a,
        doc_graph_b=graph_b,
        diff_graph=diff_graph,
        reasoning_graph=reasoning_graph,
        findings=findings,
        metrics=metrics,
        warnings=warnings,
    )
    metrics["wiki_pages"] = wiki_pages
    write_object(request.out_dir / "metrics.json", {"metrics": metrics, "warnings": warnings})
    _finish_stage(logger, stage_timings, "write_artifacts", stage_started, artifact_count=17, wiki_pages=wiki_pages)
    logger.event("run_finished", findings=len(findings), elapsed_seconds=metrics["elapsed_seconds"])

    return ReviewResult(
        run_id=run_id,
        out_dir=request.out_dir,
        findings_count=len(findings),
        review_required_count=sum(1 for finding in findings if finding.severity == "review_required"),
        coverage_warning_count=sum(1 for finding in findings if finding.finding_type == "coverage_warning"),
        report_path=request.out_dir / "report.md",
        findings_path=request.out_dir / "findings.json",
        metrics_path=request.out_dir / "metrics.json",
        warnings=warnings,
    )


def _sample_text(path: Path) -> str:
    try:
        import fitz

        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in list(doc)[:2])
        doc.close()
        return text
    except Exception:
        return ""


def _finish_stage(
    logger: JsonlLogger,
    stage_timings: dict[str, float],
    stage: str,
    started: float,
    **fields: Any,
) -> None:
    elapsed = round(time.time() - started, 3)
    stage_timings[stage] = elapsed
    logger.event("stage_finished", stage=stage, elapsed_seconds=elapsed, **fields)


def _page_region_metrics(pages, regions, annotations) -> dict[str, object]:
    return {
        "pages": len(pages),
        "regions": len(regions),
        "annotations": len(annotations),
        "empty_pages": sum(1 for page in pages if page.extraction_status != "ok"),
        "text_chars": sum(page.text_char_count for page in pages),
    }


def _counter(items, attr: str) -> dict[str, int]:
    return dict(sorted(Counter(str(getattr(item, attr, "")) for item in items).items()))


def _evidence_metrics(evidence) -> dict[str, object]:
    return {
        "evidence_by_kind": _counter(evidence, "kind"),
        "evidence_by_doc": _counter(evidence, "doc_id"),
        "evidence_by_confidence": _counter(evidence, "confidence"),
        "evidence_by_source_method": _counter(evidence, "source_method"),
        "generic_subject_evidence": sum(1 for item in evidence if item.subject in {"GENERAL", "XFMR", "FUSE"}),
        "document_context_evidence": sum(1 for item in evidence if item.context_id.endswith(":document")),
    }


def _graph_metrics(graph_a, graph_b, diff_graph) -> dict[str, object]:
    return {
        "contexts_a": len(graph_a.contexts),
        "contexts_b": len(graph_b.contexts),
        "claims_a": len(graph_a.claims),
        "claims_b": len(graph_b.claims),
        "subjects_a": len(graph_a.subjects),
        "subjects_b": len(graph_b.subjects),
        "diff_edges": len(diff_graph.edges),
        "diff_edges_by_type": _counter(diff_graph.edges, "diff_type"),
        "diff_edges_by_alignment": _counter(diff_graph.edges, "alignment_status"),
        "diff_edges_by_identity_strength": _counter(diff_graph.edges, "identity_strength"),
    }


def _reasoning_metrics(reasoning_graph) -> dict[str, object]:
    return {
        "alignment_decisions": len(reasoning_graph.alignments),
        "comparison_decisions": len(reasoning_graph.comparisons),
        "absence_searches": len(reasoning_graph.absence_searches),
        "alignment_decisions_by_subject_method": _counter(reasoning_graph.alignments, "subject_method"),
        "alignment_decisions_by_context_method": _counter(reasoning_graph.alignments, "context_method"),
        "comparison_decisions_by_type": _counter(reasoning_graph.comparisons, "comparison_type"),
        "comparison_decisions_by_unit_method": _counter(reasoning_graph.comparisons, "unit_method"),
        "absence_searches_by_coverage_status": _counter(reasoning_graph.absence_searches, "coverage_status"),
    }


def _candidate_metrics(candidates) -> dict[str, object]:
    return {
        "candidates": len(candidates),
        "candidates_by_type": _counter(candidates, "finding_type"),
        "candidates_by_status": _counter(candidates, "status"),
        "candidates_by_identity_strength": _counter(candidates, "identity_strength"),
    }


def _finding_metrics(findings) -> dict[str, object]:
    return {
        "findings": len(findings),
        "findings_by_type": _counter(findings, "finding_type"),
        "findings_by_severity": _counter(findings, "severity"),
        "findings_by_confidence": _counter(findings, "confidence"),
        "review_required_findings": sum(1 for finding in findings if finding.severity == "review_required"),
        "coverage_warning_findings": sum(1 for finding in findings if finding.finding_type == "coverage_warning"),
    }


def _coverage_diff_edges(diff_graph, evidence):
    from .models import DiffEdge

    edges = []
    for item in evidence:
        if item.kind != "coverage_warning":
            continue
        edges.append(
            DiffEdge(
                diff_id=f"diff{len(diff_graph.edges)+len(edges)+1:05d}",
                diff_type="coverage_warning",
                a_node_id=None,
                b_node_id=None,
                alignment_status="needs_review",
                subject=item.subject,
                parameter="coverage",
                rationale=item.raw_text,
                evidence_ids=[item.evidence_id],
                identity_strength="strong",
                deterministic_discrepancy=True,
            )
        )
    return edges
