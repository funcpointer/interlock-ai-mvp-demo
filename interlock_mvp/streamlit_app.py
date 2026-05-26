from __future__ import annotations

from datetime import UTC, datetime
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import streamlit as st
from PIL import Image, ImageDraw

from interlock_mvp.core.artifacts import read_artifact, write_json
from interlock_mvp.core.env import DEFAULT_OLD_REPO_ENV
from interlock_mvp.core.models import ReviewRequest
from interlock_mvp.core.review import run_review
from interlock_mvp.core.triage import triage_run


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
    "reviewer_feedback.json",
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
        max_cost_usd = st.number_input(
            "Cloud cost cap (USD)",
            min_value=0.0,
            max_value=5.0,
            value=0.25,
            step=0.05,
            disabled=no_cloud,
            help="Applies only when cloud calls are enabled. External model review is advisory only.",
        )
        no_kuzu = st.checkbox("Skip Kuzu graph", value=True)

    if source == "Upload PDFs":
        _upload_flow(no_cloud=no_cloud, no_kuzu=no_kuzu, max_cost_usd=max_cost_usd)
    else:
        _preset_flow(source, no_cloud=no_cloud, no_kuzu=no_kuzu, max_cost_usd=max_cost_usd)

    last_run_dir = st.session_state.get("last_run_dir")
    if last_run_dir and Path(str(last_run_dir)).exists():
        _render_run(Path(str(last_run_dir)))


def _preset_flow(source: str, *, no_cloud: bool, no_kuzu: bool, max_cost_usd: float) -> None:
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
            max_cost_usd=max_cost_usd,
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
            max_cost_usd=max_cost_usd,
        )
    st.info("Preset demos are controlled, watermarked synthetic cases over public/fixture documents.")
    if st.button("Run review", type="primary"):
        _run_and_render(request)


def _upload_flow(*, no_cloud: bool, no_kuzu: bool, max_cost_usd: float) -> None:
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
                max_cost_usd=max_cost_usd,
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
    st.session_state["last_run_dir"] = str(result.out_dir)


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

    _render_quality_panel(findings=findings, metrics=metrics)

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
        st.markdown(f"### {_finding_title(finding)}")
        st.markdown(f"**Why it is flagged:** {_why_flagged(finding)}")
        st.caption(_finding_caption(finding))
        _render_micro_evidence(finding)
        _render_reviewer_controls(run_dir, finding)
        if _has_explainability(finding):
            _render_explainability(finding)
        if finding.get("model_review_status") == "used":
            _render_model_review(finding)
        col_a, col_b = st.columns(2)
        with col_a:
            _render_citation(run_dir, _citation_label(finding, "A"), finding.get("evidence_a") or {})
        with col_b:
            _render_citation(run_dir, _citation_label(finding, "B"), finding.get("evidence_b") or {})


def _has_explainability(finding: dict[str, Any]) -> bool:
    return bool(
        finding.get("pairing_subject_method")
        or finding.get("comparison_unit_method")
        or finding.get("context_support_summary")
    )


def _render_explainability(finding: dict[str, Any]) -> None:
    confidence = finding.get("pairing_confidence") or finding.get("context_support_confidence") or "unknown"
    with st.expander(f"Explainability: why this finding was made ({confidence})", expanded=False):
        st.graphviz_chart(_finding_graph_dot(finding), use_container_width=False)

        st.markdown("**Why these two citations were compared**")
        for line in _pairing_details(finding):
            st.markdown(f"- {line}")

        st.markdown("**How the value was checked**")
        for line in _comparison_details(finding):
            st.markdown(f"- {line}")

        context_details = _context_support_details(finding)
        if context_details:
            st.markdown("**What surrounding context supported the pairing**")
            for detail in context_details:
                st.markdown(f"- {detail}")

        alternatives = _pairing_alternatives(finding)
        st.markdown("**What else was considered**")
        if alternatives:
            for alternative in alternatives:
                st.markdown(f"- {alternative}")
        else:
            st.markdown("- No same-parameter Doc B alternatives were found outside the accepted pair.")


def _finding_graph_dot(finding: dict[str, Any]) -> str:
    evidence_a = finding.get("evidence_a") or {}
    evidence_b = finding.get("evidence_b") or {}
    context_refs = [item for item in (finding.get("context_support_context_refs") or []) if isinstance(item, dict)]
    context_a = next((item for item in context_refs if item.get("doc_id") == "A"), {})
    context_b = next((item for item in context_refs if item.get("doc_id") == "B"), {})
    subject = str(finding.get("subject") or "subject")
    parameter = str(finding.get("parameter") or "parameter")
    severity = str(finding.get("severity") or "")
    finding_type = str(finding.get("finding_type") or "")
    authority = str(finding.get("authoritative_side") or "unknown")
    pool = int(finding.get("pairing_candidate_pool_count") or 0)
    same_parameter = int(finding.get("pairing_same_parameter_candidate_count") or 0)
    rejected = int(finding.get("pairing_rejected_candidate_count") or 0)

    nodes = [
        _dot_node(
            "evidence",
            _dot_multiline(
                "Cited evidence",
                f"A: {_graph_citation_label(evidence_a)}",
                f"B: {_graph_citation_label(evidence_b)}",
            ),
            fill="#EFF6FF",
        ),
        _dot_node(
            "context",
            _dot_multiline(
                "Context support",
                f"A: {_graph_context_label(context_a)}",
                f"B: {_graph_context_label(context_b)}",
                f"{len(finding.get('context_support_search_ids') or [])} related search hit(s)",
            ),
            fill="#F8FAFC",
            shape="note",
        ),
        _dot_node(
            "pool",
            _dot_multiline(
                "Candidate screening",
                f"{pool} Doc B claim(s)",
                f"{same_parameter} same parameter",
                f"{rejected} rejected alternative(s)",
            ),
            fill="#F1F5F9",
            shape="folder",
        ),
        _dot_node(
            "pair",
            _dot_multiline(
                "Pairing",
                f"subject: {finding.get('pairing_subject_method') or 'n/a'}",
                f"parameter: {finding.get('pairing_parameter_method') or 'n/a'}",
                f"context: {finding.get('pairing_context_method') or 'n/a'}",
            ),
            fill="#FEF3C7",
        ),
        _dot_node(
            "compare",
            _dot_multiline(
                "Value check",
                str(finding.get("comparison_unit_method") or "n/a"),
                "deterministic" if finding.get("comparison_deterministic") else "not deterministic",
            ),
            fill="#ECFDF5",
        ),
        _dot_node(
            "authority",
            _dot_multiline("Authority", authority),
            fill="#F5F3FF",
            shape="component",
        ),
        _dot_node("finding", _dot_multiline("Finding", f"{subject} / {parameter}", finding_type, severity), fill="#FEE2E2"),
    ]
    edges = [
        'evidence -> context [label="located in"]',
        'context -> pool [label="supports search"]',
        'pool -> pair [label="screened"]',
        'pair -> compare [label="paired claims"]',
        'compare -> authority [label="apply direction"]',
        'authority -> finding [label="finding"]',
    ]
    return "\n".join(
        [
            "digraph FindingExplainability {",
            '  graph [rankdir=TB, bgcolor="transparent", pad="0.08", nodesep="0.22", ranksep="0.30"];',
            '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#CBD5E1", fontcolor="#0F172A", margin="0.07,0.05"];',
            '  edge [fontname="Helvetica", fontsize=8, color="#64748B", fontcolor="#475569", arrowsize=0.55];',
            *[f"  {node}" for node in nodes],
            *[f"  {edge};" for edge in edges],
            "}",
        ]
    )


def _dot_node(node_id: str, label: str, *, fill: str, shape: str = "box") -> str:
    return f'{node_id} [label="{_dot_escape(label)}", fillcolor="{fill}", shape="{shape}"];'


def _dot_multiline(*parts: str) -> str:
    return "\n".join(str(part) for part in parts if str(part).strip())


def _dot_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _graph_context_label(ref: dict[str, Any]) -> str:
    if not ref:
        return "not recorded"
    label = str(ref.get("label") or ref.get("context_id") or "").replace("_", " ")
    pages = [int(page) for page in (ref.get("pages") or []) if isinstance(page, int)]
    return f"{_clip_text(label, 28)}{_page_span_text(pages)}".strip()


def _graph_citation_label(citation: dict[str, Any]) -> str:
    if not citation:
        return "not cited"
    page = citation.get("page")
    page_text = f"p{page}" if page else "page unknown"
    value = _citation_value(citation)
    return f"{page_text} | {value}" if value else page_text


def _pairing_details(finding: dict[str, Any]) -> list[str]:
    details: list[str] = []
    pool = int(finding.get("pairing_candidate_pool_count") or 0)
    same_parameter = int(finding.get("pairing_same_parameter_candidate_count") or 0)
    if pool:
        details.append(f"Candidate pool: {pool} Doc B claim(s); {same_parameter} matched the parameter before value comparison")
    subject = _pairing_method_label("subject", str(finding.get("pairing_subject_method") or ""))
    parameter = _pairing_method_label("parameter", str(finding.get("pairing_parameter_method") or ""))
    context = _pairing_method_label("context", str(finding.get("pairing_context_method") or ""))
    if subject:
        details.append(f"Subject match: {subject}")
    if parameter:
        details.append(f"Parameter match: {parameter}")
    if context:
        details.append(f"Context match: {context}")
    rationale = str(finding.get("pairing_rationale") or "").strip()
    if rationale:
        details.append(f"Accepted pair rationale: {rationale}")
    return details or ["No pairing decision was recorded for this finding."]


def _comparison_details(finding: dict[str, Any]) -> list[str]:
    details: list[str] = []
    unit_method = _unit_method_label(str(finding.get("comparison_unit_method") or ""))
    if unit_method:
        details.append(f"Unit/value check: {unit_method}")
    deterministic = finding.get("comparison_deterministic")
    if deterministic is not None:
        details.append("Deterministic discrepancy: yes" if deterministic else "Deterministic discrepancy: no")
    for note in finding.get("plausibility_notes") or []:
        details.append(f"Check note: {_plausibility_note_label(str(note))}")
    rationale = str(finding.get("comparison_rationale") or "").strip()
    if rationale:
        details.append(f"Comparison rationale: {rationale}")
    return details or ["No comparison decision was recorded for this finding."]


def _pairing_alternatives(finding: dict[str, Any]) -> list[str]:
    count = int(finding.get("pairing_rejected_candidate_count") or 0)
    same_parameter = int(finding.get("pairing_same_parameter_candidate_count") or 0)
    summaries = [str(item) for item in (finding.get("pairing_rejected_candidate_summaries") or []) if str(item).strip()]
    if not count:
        if same_parameter:
            return [f"Only one Doc B claim matched this parameter; no same-parameter alternatives were rejected."]
        return []
    lines = [f"Rejected {count} same-parameter Doc B candidate(s) after subject/context checks."]
    lines.extend(summaries[:3])
    if count > len(summaries[:3]):
        lines.append(f"{count - len(summaries[:3])} more candidate(s) omitted from this card; see reasoning_graph.json.")
    return lines


def _pairing_method_label(axis: str, method: str) -> str:
    labels = {
        "subject": {
            "exact": "exact subject/tag match",
            "alias": "known equipment alias match",
            "context_bridge": "same equipment inferred from nearby context",
            "semantic": "weak semantic candidate only",
        },
        "parameter": {
            "exact": "exact normalized parameter match",
            "normalized": "normalized parameter alias match",
        },
        "context": {
            "exact": "same context id",
            "canonicalized": "same normalized section/table label",
            "cross_doc_bridge": "different labels, but compatible review contexts",
            "missing": "generic or missing context",
        },
    }
    return labels.get(axis, {}).get(method, method.replace("_", " ") if method else "")


def _unit_method_label(method: str) -> str:
    return {
        "pint": "Pint unit equivalence first, then mismatch if values remain different",
        "custom_percent_impedance": "custom percent-impedance check; base/context matters",
        "dimension_mismatch": "unit dimensions are incompatible",
        "exact": "exact normalized value/unit comparison",
    }.get(method, method.replace("_", " ") if method else "")


def _plausibility_note_label(note: str) -> str:
    return {
        "pint_equivalence": "unit-normalized numeric comparison was available",
        "quantity_parse_failed": "unit parser could not normalize the value",
        "custom_quantity_required": "custom engineering quantity logic was required",
        "dimension_mismatch": "units have incompatible dimensions",
    }.get(note, note.replace("_", " "))


def _context_support_details(finding: dict[str, Any]) -> list[str]:
    details: list[str] = []
    context_refs = [item for item in (finding.get("context_support_context_refs") or []) if isinstance(item, dict)]
    if context_refs:
        details.append("Compared sections: " + "; ".join(_human_context_ref(item) for item in context_refs[:4]))
    search_ids = [str(item) for item in (finding.get("context_support_search_ids") or [])]
    if search_ids:
        subject = str(finding.get("subject") or "subject")
        parameter = str(finding.get("parameter") or "parameter")
        details.append(f"Related packet evidence: {len(search_ids)} search hit(s) for {subject} / {parameter}")
    if "possible_equivalent_elsewhere" in (finding.get("context_support_signal_types") or []):
        details.append("Caution: search found a possible equivalent value elsewhere")
    return details


def _human_context_ref(ref: dict[str, Any]) -> str:
    doc_id = str(ref.get("doc_id") or "")
    label = str(ref.get("label") or ref.get("context_id") or "").replace("_", " ")
    pages = [int(page) for page in (ref.get("pages") or []) if isinstance(page, int)]
    page_text = _page_span_text(pages)
    prefix = f"Doc {doc_id} - " if doc_id in {"A", "B"} else ""
    return f"{prefix}{label}{page_text}"


def _page_span_text(pages: list[int]) -> str:
    if not pages:
        return ""
    unique = sorted(set(pages))
    if len(unique) == 1:
        return f" (p{unique[0]})"
    return f" (p{unique[0]}-{unique[-1]})"


def _clip_text(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _render_model_review(finding: dict[str, Any]) -> None:
    supports = finding.get("model_review_supports")
    model = finding.get("model_review_model") or "external model"
    title = "supports citations" if supports else "adds caution"
    with st.expander(f"External model check: {title}", expanded=False):
        st.caption(f"Model: {model}. Advisory only; it cannot create findings or bypass citations.")
        summary = str(finding.get("model_review_summary") or "").strip()
        if summary:
            st.markdown(summary)
        cautions = finding.get("model_review_cautions") or []
        if cautions:
            st.caption("Cautions: " + "; ".join(str(item) for item in cautions))


def _render_citation(run_dir: Path, label: str, citation: dict[str, Any]) -> None:
    st.markdown(f"**{label}**")
    if not citation:
        st.caption("No citation.")
        return
    st.caption(f"Page {citation.get('page')}")
    st.markdown(f"> {citation.get('quote')}")
    with st.expander(f"View page highlight - {label}", expanded=False):
        _render_page_highlight(run_dir, citation)
    with st.expander(f"View source crop - {label}", expanded=False):
        _render_crop(run_dir, citation)


def _render_page_highlight(run_dir: Path, citation: dict[str, Any]) -> None:
    overlay = _highlighted_page_image(run_dir, citation)
    if overlay is None:
        st.caption("Page overlay unavailable for this citation.")
        return
    st.image(overlay, use_container_width=True)


def _highlighted_page_image(run_dir: Path, citation: dict[str, Any]) -> Image.Image | None:
    page_record = _page_record_for_citation(run_dir, citation)
    if not page_record:
        return None
    image_rel = str(page_record.get("page_image_path") or "")
    if not image_rel:
        return None
    image_path = (run_dir / image_rel).resolve()
    try:
        image_path.relative_to(run_dir.resolve())
    except ValueError:
        return None
    if not image_path.exists():
        return None

    image = Image.open(image_path).convert("RGB")
    bbox = citation.get("bbox") or []
    if not isinstance(bbox, list) or len(bbox) != 4:
        return image
    page_width = float(page_record.get("width") or 0)
    page_height = float(page_record.get("height") or 0)
    if page_width <= 0 or page_height <= 0:
        return image
    sx = image.width / page_width
    sy = image.height / page_height
    x0, y0, x1, y1 = [float(value) for value in bbox]
    pad = 8
    rect = [
        max(0, int(x0 * sx) - pad),
        max(0, int(y0 * sy) - pad),
        min(image.width, int(x1 * sx) + pad),
        min(image.height, int(y1 * sy) + pad),
    ]
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle(rect, outline=(220, 38, 38, 255), width=5)
    draw.rectangle(rect, fill=(220, 38, 38, 35))
    label = f"p{citation.get('page', '')} cited evidence"
    label_box = [rect[0], max(0, rect[1] - 26), min(image.width, rect[0] + 170), rect[1]]
    draw.rectangle(label_box, fill=(220, 38, 38, 230))
    draw.text((label_box[0] + 6, label_box[1] + 6), label, fill=(255, 255, 255, 255))
    return image


def _page_record_for_citation(run_dir: Path, citation: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = citation.get("doc_id")
    page = citation.get("page")
    for record in _records(run_dir / "pages.json"):
        if record.get("doc_id") == doc_id and record.get("page_num") == page:
            return record
    return None


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


def _finding_title(finding: dict[str, Any]) -> str:
    if finding.get("finding_type") == "value_mismatch" and finding.get("evidence_a") and finding.get("evidence_b"):
        return (
            f"{finding.get('subject')} {finding.get('parameter')}: "
            f"{_citation_value(finding['evidence_a'])} -> {_citation_value(finding['evidence_b'])}"
        )
    if finding.get("finding_type") == "missing_item":
        return f"{finding.get('subject')}: missing aligned evidence"
    return f"{finding.get('subject')} {finding.get('parameter')}"


def _why_flagged(finding: dict[str, Any]) -> str:
    if finding.get("finding_type") == "value_mismatch" and finding.get("evidence_a") and finding.get("evidence_b"):
        authority = finding.get("authoritative_side")
        if authority == "B":
            return "Doc B is treated as controlling, and its cited value does not match Doc A."
        if authority == "A":
            return "Doc A is treated as controlling, and its cited value does not match Doc B."
        return "Both documents cite different values for the same subject and parameter."
    return str(finding.get("summary") or "")


def _finding_caption(finding: dict[str, Any]) -> str:
    kind = str(finding.get("finding_type") or "").replace("_", " ")
    severity = str(finding.get("severity") or "").replace("_", " ")
    authority = str(finding.get("authoritative_side") or "unknown")
    basis = str(finding.get("authority_basis") or "").strip()
    basis_text = f" - {basis}" if basis else ""
    return f"{severity} | {kind} | authority {authority}{basis_text}"


def _render_micro_evidence(finding: dict[str, Any]) -> None:
    evidence_a = finding.get("evidence_a") or {}
    evidence_b = finding.get("evidence_b") or {}
    if not evidence_a and not evidence_b:
        return
    cols = st.columns(2)
    with cols[0]:
        if evidence_a:
            st.metric(_citation_label(finding, "A"), _citation_value(evidence_a))
    with cols[1]:
        if evidence_b:
            st.metric(_citation_label(finding, "B"), _citation_value(evidence_b))


def _citation_value(citation: dict[str, Any]) -> str:
    return " ".join(str(part) for part in [citation.get("value"), citation.get("unit")] if part).strip() or str(citation.get("quote") or "")


def _citation_label(finding: dict[str, Any], side: str) -> str:
    if finding.get("mode") == "version":
        return "Baseline (Doc A)" if side == "A" else "Revised (Doc B)"
    return f"Doc {side}"


def _render_quality_panel(*, findings: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    review_findings = [finding for finding in findings if finding.get("finding_type") != "coverage_warning"]
    cited_findings = sum(1 for finding in review_findings if _finding_has_citations(finding))
    high_context = sum(1 for finding in review_findings if finding.get("context_support_confidence") == "high")
    with st.expander("Review quality signals", expanded=True):
        st.caption(
            "Findings require direct citations and deterministic review logic. Graph/search/context are supporting signals, not proof by themselves."
        )
        cols = st.columns(4)
        cols[0].metric("Cited findings", f"{cited_findings}/{len(review_findings)}")
        cols[1].metric("High context support", high_context)
        cols[2].metric("Evidence items", metrics.get("evidence", 0))
        cols[3].metric("Decision traces", metrics.get("decision_traces", 0))


def _finding_has_citations(finding: dict[str, Any]) -> bool:
    citations = [finding.get("evidence_a"), finding.get("evidence_b")]
    present = [citation for citation in citations if isinstance(citation, dict)]
    return bool(present) and all(citation.get("page") and citation.get("quote") and citation.get("crop_path") for citation in present)


def _render_reviewer_controls(run_dir: Path, finding: dict[str, Any]) -> None:
    finding_id = str(finding.get("finding_id") or "")
    if not finding_id:
        return
    current = _feedback_by_finding(run_dir).get(finding_id)
    if current:
        st.caption(f"Reviewer mark: {current.get('action', '').replace('_', ' ')}")
    cols = st.columns([1, 1, 1, 4])
    for column, label, action in [
        (cols[0], "Accept", "accepted"),
        (cols[1], "Needs review", "needs_review"),
        (cols[2], "Dismiss", "dismissed"),
    ]:
        if column.button(label, key=f"feedback-{run_dir.name}-{finding_id}-{action}"):
            _record_feedback(run_dir, finding_id=finding_id, action=action)
            st.toast(f"Marked {finding_id} as {action.replace('_', ' ')}")
            st.rerun()


def _record_feedback(run_dir: Path, *, finding_id: str, action: str) -> None:
    records = [
        record
        for record in _feedback_records(run_dir)
        if record.get("finding_id") != finding_id
    ]
    records.append(
        {
            "finding_id": finding_id,
            "action": action,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    write_json(run_dir / "reviewer_feedback.json", records=records)


def _feedback_by_finding(run_dir: Path) -> dict[str, dict[str, Any]]:
    return {str(record.get("finding_id")): record for record in _feedback_records(run_dir)}


def _feedback_records(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "reviewer_feedback.json"
    if not path.exists():
        return []
    return read_artifact(path).get("records", [])


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
