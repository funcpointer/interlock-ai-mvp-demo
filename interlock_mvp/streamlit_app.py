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
        st.markdown(f"### {_finding_title(finding)}")
        st.markdown(f"**Why it is flagged:** {_why_flagged(finding)}")
        st.caption(_finding_caption(finding))
        _render_micro_evidence(finding)
        if _has_audit_trail(finding):
            _render_audit_trail(finding)
        if finding.get("model_review_status") == "used":
            _render_model_review(finding)
        col_a, col_b = st.columns(2)
        with col_a:
            _render_citation(run_dir, _citation_label(finding, "A"), finding.get("evidence_a") or {})
        with col_b:
            _render_citation(run_dir, _citation_label(finding, "B"), finding.get("evidence_b") or {})


def _has_audit_trail(finding: dict[str, Any]) -> bool:
    return bool(
        finding.get("pairing_subject_method")
        or finding.get("comparison_unit_method")
        or finding.get("context_support_summary")
    )


def _render_audit_trail(finding: dict[str, Any]) -> None:
    confidence = finding.get("pairing_confidence") or finding.get("context_support_confidence") or "unknown"
    with st.expander(f"Audit trail: pairing and comparison ({confidence})", expanded=False):
        st.markdown("**Pairing decision**")
        for line in _pairing_details(finding):
            st.markdown(f"- {line}")

        st.markdown("**Comparison rule**")
        for line in _comparison_details(finding):
            st.markdown(f"- {line}")

        context_details = _context_support_details(finding)
        if context_details:
            st.markdown("**Context/search support**")
            for detail in context_details:
                st.markdown(f"- {detail}")

        alternatives = _pairing_alternatives(finding)
        st.markdown("**Other candidates considered**")
        if alternatives:
            for alternative in alternatives:
                st.markdown(f"- {alternative}")
        else:
            st.markdown("- No same-parameter Doc B alternatives were found outside the accepted pair.")


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
        details.append(f"Subject identity: {subject}")
    if parameter:
        details.append(f"Parameter identity: {parameter}")
    if context:
        details.append(f"Context bridge: {context}")
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
    with st.expander(f"View source crop - {label}", expanded=False):
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
