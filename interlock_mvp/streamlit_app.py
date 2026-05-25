from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import streamlit as st

from .core.artifacts import read_artifact
from .core.env import DEFAULT_OLD_REPO_ENV
from .core.models import ReviewRequest
from .core.review import run_review
from .core.triage import triage_run


ROOT = Path(__file__).resolve().parents[1]
DEMO_ASSETS = ROOT / "demo_assets/public_aes"
RUN_ROOT = Path(os.environ.get("INTERLOCK_RUN_ROOT", str(ROOT / "runs")))
DEFAULT_AUTHORITY = ROOT / "examples/aes_authority.yaml"
DEFAULT_GLOSSARY = ROOT / "examples/aes_glossary.yaml"
PUBLIC_SPEC = DEMO_ASSETS / "somerset_main_power_transformer_spec_sheet.pdf"
PUBLIC_VERSION_REV = DEMO_ASSETS / "somerset_main_power_transformer_spec_sheet_synth_rev.pdf"
PUBLIC_CROSS_DOC = DEMO_ASSETS / "somerset_transformer_protection_study_excerpt_synth.pdf"
MAX_UPLOAD_BYTES = int(os.environ.get("INTERLOCK_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
ARTIFACT_DOWNLOADS = [
    "report.md",
    "findings.json",
    "metrics.json",
    "triage.json",
    "reasoning_graph.json",
    "decision_traces.json",
    "wiki/index.md",
    "wiki/review-map.md",
    "wiki/memory-palace.md",
]
WIKI_PREVIEW_FILES = ["wiki/index.md", "wiki/review-map.md", "wiki/memory-palace.md"]


def main() -> None:
    st.set_page_config(page_title="InterLock AI MVP", layout="wide")
    st.title("InterLock AI MVP")
    st.caption("Cited directional review for two engineering PDFs.")

    with st.sidebar:
        st.header("Run")
        options = _input_options()
        source = st.radio("Input", options, index=0)
        no_cloud = st.checkbox("Disable cloud calls", value=True)
        no_kuzu = st.checkbox("Skip Kuzu graph", value=True)

    if source == "Upload PDFs":
        _upload_flow(no_cloud=no_cloud, no_kuzu=no_kuzu)
    else:
        _preset_flow(source, no_cloud=no_cloud, no_kuzu=no_kuzu)


def _preset_flow(source: str, *, no_cloud: bool, no_kuzu: bool) -> None:
    if source == "Public version demo":
        request = ReviewRequest(
            doc_a_path=PUBLIC_SPEC,
            doc_b_path=PUBLIC_VERSION_REV,
            mode="version",
            out_dir=_new_run_dir("streamlit-public-version"),
            authority_config_path=DEFAULT_AUTHORITY,
            domain_glossary_path=DEFAULT_GLOSSARY,
            env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
            doc_a_type="specification",
            doc_b_type="specification",
            no_cloud=no_cloud,
            no_kuzu=no_kuzu,
        )
    else:
        request = ReviewRequest(
            doc_a_path=PUBLIC_SPEC,
            doc_b_path=PUBLIC_CROSS_DOC,
            mode="cross_doc",
            out_dir=_new_run_dir("streamlit-public-cross-doc"),
            authority_config_path=DEFAULT_AUTHORITY,
            domain_glossary_path=DEFAULT_GLOSSARY,
            env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
            doc_a_type="specification",
            doc_b_type="protection_study",
            no_cloud=no_cloud,
            no_kuzu=no_kuzu,
        )
    st.info("Preset demos are controlled, watermarked synthetic cases over public/fixture documents.")
    if st.button("Run review", type="primary"):
        _run_and_render(request)


def _upload_flow(*, no_cloud: bool, no_kuzu: bool) -> None:
    col_a, col_b = st.columns(2)
    with col_a:
        doc_a = st.file_uploader("Doc A PDF", type=["pdf"], key="doc_a")
        doc_a_type = st.selectbox("Doc A type", ["auto", "specification", "protection_study", "drawing", "checklist"], index=0)
    with col_b:
        doc_b = st.file_uploader("Doc B PDF", type=["pdf"], key="doc_b")
        doc_b_type = st.selectbox("Doc B type", ["auto", "specification", "protection_study", "drawing", "checklist"], index=0)
    mode = st.radio("Mode", ["version", "cross_doc"], horizontal=True)
    upload_errors = _upload_errors(doc_a, doc_b)
    for error in upload_errors:
        st.error(error)

    if st.button("Run uploaded review", type="primary", disabled=not (doc_a and doc_b) or bool(upload_errors)):
        with TemporaryDirectory(prefix="interlock-streamlit-") as temp_dir:
            temp_root = Path(temp_dir)
            doc_a_path = temp_root / _safe_upload_name(doc_a.name, fallback="doc_a.pdf")
            doc_b_path = temp_root / _safe_upload_name(doc_b.name, fallback="doc_b.pdf")
            doc_a_path.write_bytes(doc_a.getvalue())
            doc_b_path.write_bytes(doc_b.getvalue())
            out_dir = _new_run_dir("streamlit-upload")
            request = ReviewRequest(
                doc_a_path=doc_a_path,
                doc_b_path=doc_b_path,
                mode=mode,  # type: ignore[arg-type]
                out_dir=out_dir,
                authority_config_path=DEFAULT_AUTHORITY,
                domain_glossary_path=DEFAULT_GLOSSARY,
                env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
                doc_a_type=doc_a_type,
                doc_b_type=doc_b_type,
                no_cloud=no_cloud,
                no_kuzu=no_kuzu,
            )
            _run_and_render(request)


def _run_and_render(request: ReviewRequest) -> None:
    with st.spinner("Reviewing PDFs..."):
        try:
            result = run_review(request)
            triage_run(result.out_dir, write=True)
        except Exception as exc:
            st.error(f"Review failed: {type(exc).__name__}: {exc}")
            return
    _render_run(result.out_dir)


def _render_run(run_dir: Path) -> None:
    findings = _records(run_dir / "findings.json")
    metrics = _metrics(run_dir / "metrics.json")
    triage = _object(run_dir / "triage.json")
    review_findings = [finding for finding in findings if finding.get("finding_type") != "coverage_warning"]
    coverage_findings = [finding for finding in findings if finding.get("finding_type") == "coverage_warning"]

    cols = st.columns(5)
    cols[0].metric("Review findings", len(review_findings))
    cols[1].metric("Review required", metrics.get("review_required_findings", 0))
    cols[2].metric("Coverage warnings", len(coverage_findings))
    cols[3].metric("Comparisons", metrics.get("comparison_decisions", 0))
    cols[4].metric("Absence searches", metrics.get("absence_searches", 0))

    st.subheader("Findings")
    if not review_findings:
        st.write("No review findings.")
    for finding in review_findings:
        _render_finding(run_dir, finding)

    if coverage_findings:
        with st.expander(f"Extraction coverage warnings ({len(coverage_findings)})", expanded=True):
            st.warning(
                "Some pages have empty or weak text layers. The system is refusing to claim review coverage for those pages without OCR/VLM extraction."
            )
            for finding in coverage_findings[:6]:
                citation = finding.get("evidence_a") or finding.get("evidence_b") or {}
                st.caption(citation.get("quote") or finding.get("summary"))
                _render_crop(run_dir, citation)

    with st.expander("Triage", expanded=bool(triage.get("issues"))):
        issues = triage.get("issues", [])
        if not issues:
            st.write("No triage issues.")
        for issue in issues:
            st.write(f"**{issue.get('severity')}** - {issue.get('title')}")
            st.caption(issue.get("summary", ""))

    _render_context_layer(run_dir)

    with st.expander("Artifacts"):
        for name in ARTIFACT_DOWNLOADS:
            path = run_dir / name
            if path.exists():
                st.download_button(name, data=path.read_bytes(), file_name=_download_name(name), mime=_mime_for(name))


def _render_context_layer(run_dir: Path) -> None:
    pages = _wiki_pages(run_dir)
    if not pages:
        return
    entrypoints = [name for name in WIKI_PREVIEW_FILES if name in pages]
    other_pages = [name for name in pages if name not in set(entrypoints)]
    with st.expander("Context layer: graph, search, wiki", expanded=True):
        st.caption(
            "Derived second-brain layer for navigation. JSON findings remain the source of truth."
        )
        if entrypoints:
            tabs = st.tabs([_wiki_tab_label(name) for name in entrypoints])
            for tab, name in zip(tabs, entrypoints, strict=True):
                with tab:
                    _render_wiki_page(run_dir, name, key_prefix="wiki-entry")
        if other_pages:
            st.markdown("**All wiki pages**")
            selected = st.selectbox(
                "Open generated wiki page",
                other_pages,
                format_func=_wiki_page_label,
                key=f"wiki-page-{run_dir.name}",
            )
            _render_wiki_page(run_dir, selected, key_prefix="wiki-page")


def _render_wiki_page(run_dir: Path, name: str, *, key_prefix: str) -> None:
    path = run_dir / name
    st.markdown(_preview_wiki_markdown(path.read_text(encoding="utf-8")))
    st.download_button(
        f"Download {name}",
        data=path.read_bytes(),
        file_name=_download_name(name),
        mime="text/markdown",
        key=f"{key_prefix}-{run_dir.name}-{_download_name(name)}",
    )


def _render_finding(run_dir: Path, finding: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"### {finding.get('finding_id')}: {finding.get('subject')} / {finding.get('parameter')}")
        st.write(finding.get("summary", ""))
        st.caption(
            f"Type: {finding.get('finding_type')} | Severity: {finding.get('severity')} | "
            f"Authority: {finding.get('authoritative_side')} ({finding.get('authority_basis')})"
        )
        col_a, col_b = st.columns(2)
        with col_a:
            _render_citation(run_dir, "Doc A", finding.get("evidence_a") or {})
        with col_b:
            _render_citation(run_dir, "Doc B", finding.get("evidence_b") or {})


def _render_citation(run_dir: Path, label: str, citation: dict[str, Any]) -> None:
    st.markdown(f"**{label}**")
    if not citation:
        st.caption("No citation.")
        return
    st.caption(f"Page {citation.get('page')}: {citation.get('quote')}")
    _render_crop(run_dir, citation)


def _render_crop(run_dir: Path, citation: dict[str, Any]) -> None:
    crop = citation.get("crop_path")
    if not crop:
        return
    path = (run_dir / crop).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError:
        return
    if path.exists():
        st.image(str(path), use_container_width=True)


def _records(path: Path) -> list[dict[str, Any]]:
    return read_artifact(path).get("records", []) if path.exists() else []


def _metrics(path: Path) -> dict[str, Any]:
    return read_artifact(path).get("metrics", {}) if path.exists() else {}


def _object(path: Path) -> dict[str, Any]:
    return read_artifact(path) if path.exists() else {}


def _safe_upload_name(name: str, *, fallback: str) -> str:
    clean = "".join(char for char in name if char.isalnum() or char in {"-", "_", "."}).strip(".")
    if not clean.lower().endswith(".pdf"):
        clean = fallback
    return clean or fallback


def _upload_errors(doc_a: Any, doc_b: Any) -> list[str]:
    errors: list[str] = []
    for label, doc in [("Doc A", doc_a), ("Doc B", doc_b)]:
        if not doc:
            continue
        size = int(getattr(doc, "size", 0) or 0)
        if size > MAX_UPLOAD_BYTES:
            limit_mb = MAX_UPLOAD_BYTES / (1024 * 1024)
            actual_mb = size / (1024 * 1024)
            errors.append(f"{label} is {actual_mb:.1f} MB; max upload size is {limit_mb:.0f} MB for this demo.")
    return errors


def _new_run_dir(prefix: str) -> Path:
    return RUN_ROOT / f"{prefix}-{uuid4().hex[:10]}"


def _mime_for(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".md"):
        return "text/markdown"
    return "application/octet-stream"


def _download_name(name: str) -> str:
    return name.replace("/", "_")


def _wiki_pages(run_dir: Path) -> list[str]:
    wiki_dir = run_dir / "wiki"
    if not wiki_dir.exists():
        return []
    pages = sorted(f"wiki/{path.relative_to(wiki_dir)}" for path in wiki_dir.rglob("*.md"))
    entrypoints = [name for name in WIKI_PREVIEW_FILES if name in pages]
    return entrypoints + [name for name in pages if name not in set(entrypoints)]


def _preview_wiki_markdown(text: str) -> str:
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"**\2** (`\1.md`)", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+\.md)\)", r"**\1** (`\2`)", text)
    return text


def _wiki_tab_label(name: str) -> str:
    return {
        "wiki/index.md": "Index",
        "wiki/review-map.md": "Review Map",
        "wiki/memory-palace.md": "Memory Palace",
    }.get(name, _wiki_page_label(name))


def _wiki_page_label(name: str) -> str:
    return name.removeprefix("wiki/").removesuffix(".md")


def _input_options() -> list[str]:
    options = ["Upload PDFs"]
    if PUBLIC_SPEC.exists() and PUBLIC_CROSS_DOC.exists():
        options.insert(0, "Public cross-doc demo")
    if PUBLIC_SPEC.exists() and PUBLIC_VERSION_REV.exists():
        options.insert(0, "Public version demo")
    return options


if __name__ == "__main__":
    main()
