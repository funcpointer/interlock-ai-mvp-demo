from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from shutil import copy2, copytree, rmtree
from typing import Any

from .artifacts import read_artifact


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    title: str
    run_dir: Path
    claim: str
    caveat: str


DEFAULT_CASES = [
    DemoCase(
        case_id="version",
        title="Version Review",
        run_dir=Path("runs/public-demo/public_transformer_spec_synthetic_revision"),
        claim="Catches planted value changes between a public AES transformer spec and a watermarked synthetic revision.",
        caveat="Synthetic revision, not a real AES-issued revision.",
    ),
    DemoCase(
        case_id="cross_doc",
        title="Cross-Document Review",
        run_dir=Path("runs/public-cross-doc-demo/public_transformer_spec_vs_synthetic_protection_excerpt"),
        claim="Catches planted mismatches between a public AES transformer spec and a watermarked synthetic protection-study excerpt.",
        caveat="Controlled synthetic cross-doc pair, not proof of arbitrary document-packet robustness.",
    ),
    DemoCase(
        case_id="negative",
        title="Negative Control",
        run_dir=Path("runs/checkpoint-negative"),
        claim="Does not invent findings when the same document is compared to itself.",
        caveat="Fixture control, not a broad false-positive benchmark.",
    ),
    DemoCase(
        case_id="scanned",
        title="Low-Text / Scanned Control",
        run_dir=Path("runs/checkpoint-scanned"),
        claim="Routes unreadable pages to coverage warnings instead of pretending review succeeded.",
        caveat="OCR/VLM recall is still future work.",
    ),
]


def write_demo_package(*, out_dir: Path, cases: list[DemoCase] | None = None) -> Path:
    cases = cases or DEFAULT_CASES
    site_dir = out_dir / "site"
    if site_dir.exists():
        rmtree(site_dir)
    site_dir.mkdir(parents=True)
    (site_dir / "assets").mkdir()
    (site_dir / "artifacts").mkdir()

    rendered_cases = [_render_case(case, site_dir=site_dir) for case in cases]
    (site_dir / "index.html").write_text(_site_html(rendered_cases), encoding="utf-8")
    (out_dir / "summary.md").write_text(_summary_md(rendered_cases), encoding="utf-8")
    return site_dir


def _render_case(case: DemoCase, *, site_dir: Path) -> dict[str, Any]:
    run_dir = case.run_dir.resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"Missing run directory for {case.case_id}: {run_dir}")

    findings = _read_records(run_dir / "findings.json")
    metrics = _read_metrics(run_dir / "metrics.json")
    triage = _read_optional(run_dir / "triage.json")

    artifact_dir = site_dir / "artifacts" / case.case_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name in ["report.md", "findings.json", "metrics.json", "triage.json", "reasoning_graph.json", "decision_traces.json"]:
        source = run_dir / name
        if source.exists():
            copy2(source, artifact_dir / name)
    if (run_dir / "wiki").exists():
        copytree(run_dir / "wiki", artifact_dir / "wiki", dirs_exist_ok=True)

    assets_dir = site_dir / "assets" / case.case_id
    assets_dir.mkdir(parents=True, exist_ok=True)
    for finding in findings:
        for citation_key in ("evidence_a", "evidence_b"):
            citation = finding.get(citation_key) or {}
            crop_path = citation.get("crop_path")
            if not crop_path:
                continue
            source = (run_dir / crop_path).resolve()
            if source.exists() and source.is_file():
                dest = assets_dir / Path(crop_path).name
                copy2(source, dest)
                citation["static_crop_path"] = f"assets/{case.case_id}/{dest.name}"

    return {
        "case": case,
        "run_dir": run_dir,
        "findings": findings,
        "metrics": metrics,
        "triage": triage,
    }


def _site_html(rendered_cases: list[dict[str, Any]]) -> str:
    case_cards = "\n".join(_case_card_html(item) for item in rendered_cases)
    finding_sections = "\n".join(_case_section_html(item) for item in rendered_cases)
    totals = _totals(rendered_cases)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InterLock AI MVP Demo</title>
  <style>{_css()}</style>
</head>
<body>
  <section class="band">
    <div class="wrap hero">
      <div>
        <h1>InterLock AI MVP Demo</h1>
        <p class="lede">Cited directional review for engineering PDFs.</p>
      </div>
      <div class="stamp">Static investor demo</div>
    </div>
  </section>
  <main class="wrap">
    <section class="summary">
      <div><strong>{totals['cases']}</strong><span>Demo Cases</span></div>
      <div><strong>{totals['review_findings']}</strong><span>Review Findings</span></div>
      <div><strong>{totals['review_required']}</strong><span>Review Required</span></div>
      <div><strong>{totals['coverage']}</strong><span>Coverage Warnings</span></div>
    </section>
    <section class="note">
      <h2>What This Proves</h2>
      <p>The engine produces repeatable, cited, directional review findings over public/synthetic engineering PDFs. It also shows honest failure handling: no findings on a negative control and coverage warnings for low-text scans.</p>
      <h2>What This Does Not Prove</h2>
      <p>This is not broad arbitrary document understanding. The version and cross-document examples are controlled, watermarked synthetic mutations over public or fixture documents.</p>
    </section>
    <section class="cards">{case_cards}</section>
    {finding_sections}
  </main>
</body>
</html>"""


def _case_card_html(item: dict[str, Any]) -> str:
    case: DemoCase = item["case"]
    metrics = item["metrics"]
    return f"""
    <article class="card">
      <h3><a href="#{escape(case.case_id)}">{escape(case.title)}</a></h3>
      <p>{escape(case.claim)}</p>
      <dl>
        <dt>Review Findings</dt><dd>{escape(str(_review_findings_count(item)))}</dd>
        <dt>Review Required</dt><dd>{escape(str(metrics.get('review_required_findings', _count(item['findings'], 'severity', 'review_required'))))}</dd>
        <dt>Coverage Warnings</dt><dd>{escape(str(metrics.get('coverage_warning_findings', _count(item['findings'], 'finding_type', 'coverage_warning'))))}</dd>
      </dl>
    </article>"""


def _case_section_html(item: dict[str, Any]) -> str:
    case: DemoCase = item["case"]
    findings = item["findings"]
    metrics = item["metrics"]
    finding_html = "\n".join(_finding_html(case.case_id, finding) for finding in findings) or "<p class='empty'>No findings.</p>"
    triage_html = _triage_html(item["triage"])
    return f"""
    <section class="case" id="{escape(case.case_id)}">
      <div class="case-head">
        <div>
          <h2>{escape(case.title)}</h2>
          <p>{escape(case.claim)}</p>
          <p class="caveat">{escape(case.caveat)}</p>
        </div>
        <a class="artifact" href="artifacts/{escape(case.case_id)}/report.md">Open report.md</a>
      </div>
      <div class="mini-metrics">
        <span>{escape(str(metrics.get('alignment_decisions', 0)))} alignments</span>
        <span>{escape(str(metrics.get('comparison_decisions', 0)))} comparisons</span>
        <span>{escape(str(metrics.get('absence_searches', 0)))} absence searches</span>
        <span>{escape(str(metrics.get('decision_traces_with_downgrades', 0)))} downgraded traces</span>
      </div>
      {finding_html}
      <details>
        <summary>Triage</summary>
        {triage_html}
      </details>
      <p class="artifact-row">
        <a href="artifacts/{escape(case.case_id)}/findings.json">findings.json</a>
        <a href="artifacts/{escape(case.case_id)}/metrics.json">metrics.json</a>
        <a href="artifacts/{escape(case.case_id)}/reasoning_graph.json">reasoning_graph.json</a>
        <a href="artifacts/{escape(case.case_id)}/decision_traces.json">decision_traces.json</a>
      </p>
    </section>"""


def _finding_html(case_id: str, finding: dict[str, Any]) -> str:
    evidence_a = finding.get("evidence_a") or {}
    evidence_b = finding.get("evidence_b") or {}
    return f"""
    <article class="finding {escape(str(finding.get('severity', '')))}">
      <div class="finding-head">
        <div>
          <h3>{escape(str(finding.get('finding_id', '')))}: {escape(str(finding.get('subject', '')))} / {escape(str(finding.get('parameter', '')))}</h3>
          <p>{escape(str(finding.get('summary', '')))}</p>
        </div>
        <span>{escape(str(finding.get('severity', '')))}</span>
      </div>
      <dl>
        <dt>Type</dt><dd>{escape(str(finding.get('finding_type', '')))}</dd>
        <dt>Authority</dt><dd>{escape(str(finding.get('authoritative_side', '')))} - {escape(str(finding.get('authority_basis', '')))}</dd>
        <dt>Confidence</dt><dd>{escape(str(finding.get('confidence', '')))}</dd>
      </dl>
      <div class="citations">
        {_citation_html(case_id, "Doc A", evidence_a)}
        {_citation_html(case_id, "Doc B", evidence_b)}
      </div>
    </article>"""


def _citation_html(case_id: str, label: str, citation: dict[str, Any]) -> str:
    if not citation:
        return f"<div class='citation'><h4>{escape(label)}</h4><p>No citation.</p></div>"
    crop_path = citation.get("static_crop_path") or ""
    image = f"<img src='{escape(crop_path)}' alt='{escape(case_id)} {escape(label)} crop'>" if crop_path else ""
    return f"""
    <div class="citation">
      <h4>{escape(label)} page {escape(str(citation.get('page', '')))}</h4>
      <blockquote>{escape(str(citation.get('quote', '')))}</blockquote>
      {image}
    </div>"""


def _triage_html(payload: dict[str, Any]) -> str:
    issues = payload.get("issues", [])
    if not issues:
        return "<p>No triage issues.</p>"
    return "<ul>" + "\n".join(
        f"<li><strong>{escape(issue.get('severity', ''))}</strong> {escape(issue.get('title', ''))}: {escape(issue.get('summary', ''))}</li>"
        for issue in issues
    ) + "</ul>"


def _summary_md(rendered_cases: list[dict[str, Any]]) -> str:
    lines = ["# InterLock AI MVP Demo Package", ""]
    totals = _totals(rendered_cases)
    lines.extend([
        f"- Cases: {totals['cases']}",
        f"- Review findings: {totals['review_findings']}",
        f"- Review required: {totals['review_required']}",
        f"- Coverage warnings: {totals['coverage']}",
        "",
        "Open `site/index.html` locally or deploy the `site/` directory as a static website.",
        "",
        "## Cases",
        "",
    ])
    for item in rendered_cases:
        case: DemoCase = item["case"]
        metrics = item["metrics"]
        lines.extend([
            f"### {case.title}",
            "",
            f"- Run: `{item['run_dir']}`",
            f"- Review findings: {_review_findings_count(item)}",
            f"- Review required: {metrics.get('review_required_findings', _count(item['findings'], 'severity', 'review_required'))}",
            f"- Coverage warnings: {metrics.get('coverage_warning_findings', _count(item['findings'], 'finding_type', 'coverage_warning'))}",
            f"- Caveat: {case.caveat}",
            "",
        ])
    return "\n".join(lines)


def _totals(rendered_cases: list[dict[str, Any]]) -> dict[str, int]:
    review_findings = sum(_review_findings_count(item) for item in rendered_cases)
    review_required = sum(int(item["metrics"].get("review_required_findings", _count(item["findings"], "severity", "review_required"))) for item in rendered_cases)
    coverage = sum(int(item["metrics"].get("coverage_warning_findings", _count(item["findings"], "finding_type", "coverage_warning"))) for item in rendered_cases)
    return {"cases": len(rendered_cases), "review_findings": review_findings, "review_required": review_required, "coverage": coverage}


def _review_findings_count(item: dict[str, Any]) -> int:
    metrics = item["metrics"]
    findings_total = int(metrics.get("findings", len(item["findings"])))
    coverage = int(metrics.get("coverage_warning_findings", _count(item["findings"], "finding_type", "coverage_warning")))
    return max(0, findings_total - coverage)


def _read_records(path: Path) -> list[dict[str, Any]]:
    return read_artifact(path).get("records", [])


def _read_metrics(path: Path) -> dict[str, Any]:
    return read_artifact(path).get("metrics", {}) if path.exists() else {}


def _read_optional(path: Path) -> dict[str, Any]:
    return read_artifact(path) if path.exists() else {}


def _count(records: list[dict[str, Any]], key: str, value: str) -> int:
    return sum(1 for record in records if record.get(key) == value)


def _css() -> str:
    return """
    :root { color-scheme: light; --ink:#172026; --muted:#5a6872; --line:#d7dde2; --band:#eef3f6; --accent:#006f8f; --warn:#8a5a00; --ok:#0f6b45; --bad:#9d2f2f; }
    * { box-sizing:border-box; } body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#fbfcfd; letter-spacing:0; }
    .wrap { max-width:1180px; margin:0 auto; padding:24px; } .band { background:var(--band); border-bottom:1px solid var(--line); } .hero { display:flex; justify-content:space-between; gap:24px; align-items:center; } h1 { margin:0; font-size:36px; line-height:1.1; } h2 { margin:30px 0 10px; font-size:24px; } h3 { margin:0 0 8px; font-size:18px; } h4 { margin:0 0 8px; font-size:14px; color:var(--muted); } .lede, .caveat { color:var(--muted); } .stamp { border:1px solid var(--accent); color:var(--accent); border-radius:999px; padding:7px 11px; font-size:13px; }
    .summary, .cards, .mini-metrics { display:grid; gap:12px; } .summary { grid-template-columns:repeat(4,minmax(0,1fr)); margin:20px 0; } .summary div, .card, .note, .finding { background:white; border:1px solid var(--line); border-radius:8px; } .summary div { border-top:3px solid var(--accent); padding:14px; } .summary strong { display:block; font-size:28px; } .summary span, dt { color:var(--muted); font-size:13px; } .note { padding:18px; }
    .cards { grid-template-columns:repeat(4,minmax(0,1fr)); margin:18px 0; } .card { padding:14px; } .card a, .artifact, .artifact-row a { color:var(--accent); } .card p { color:var(--muted); } dl { display:grid; grid-template-columns:130px 1fr; gap:6px 12px; margin:10px 0; } dd { margin:0; }
    .case { margin-top:28px; } .case-head { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; } .artifact { white-space:nowrap; border:1px solid var(--line); border-radius:6px; padding:8px 10px; text-decoration:none; background:white; } .mini-metrics { grid-template-columns:repeat(4,minmax(0,1fr)); margin:12px 0; } .mini-metrics span { background:#f4f7f9; padding:8px 10px; border-radius:6px; color:var(--muted); }
    .finding { padding:16px; margin:14px 0; } .finding.review_required { border-left:5px solid var(--bad); } .finding.possible_issue { border-left:5px solid var(--warn); } .finding.informational { border-left:5px solid var(--ok); } .finding-head { display:flex; justify-content:space-between; gap:18px; } .finding-head span { height:max-content; border:1px solid var(--line); border-radius:999px; padding:4px 9px; font-size:12px; color:var(--muted); white-space:nowrap; } .finding p { margin:0 0 10px; color:var(--muted); }
    .citations { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; } .citation { border-top:1px solid var(--line); padding-top:12px; } blockquote { margin:0 0 10px; padding:8px 10px; background:#f4f7f9; border-left:3px solid var(--accent); } img { max-width:100%; border:1px solid var(--line); background:white; } details { margin:14px 0; } .artifact-row { display:flex; flex-wrap:wrap; gap:10px; } .artifact-row a { border:1px solid var(--line); padding:8px 10px; border-radius:6px; background:white; text-decoration:none; }
    @media (max-width: 860px) { .hero, .case-head, .finding-head { flex-direction:column; align-items:flex-start; } .summary, .cards, .mini-metrics, .citations { grid-template-columns:1fr; } }
    """
