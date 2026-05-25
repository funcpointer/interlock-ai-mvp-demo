from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
import mimetypes

from .core.artifacts import read_artifact
from .core.env import DEFAULT_OLD_REPO_ENV
from .core.models import ReviewRequest
from .core.review import run_review
from .core.triage import triage_run


ROOT = Path(__file__).resolve().parents[1]
DEMO_ASSETS = ROOT / "demo_assets/public_aes"
DEFAULT_AUTHORITY = ROOT / "examples/aes_authority.yaml"
DEFAULT_GLOSSARY = ROOT / "examples/aes_glossary.yaml"
PUBLIC_SPEC = DEMO_ASSETS / "somerset_main_power_transformer_spec_sheet.pdf"
PUBLIC_VERSION_REV = DEMO_ASSETS / "somerset_main_power_transformer_spec_sheet_synth_rev.pdf"
PUBLIC_CROSS_DOC = DEMO_ASSETS / "somerset_transformer_protection_study_excerpt_synth.pdf"


def serve(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), InterLockHandler)
    print(f"InterLock MVP UI listening on http://{host}:{port}")
    server.serve_forever()


class InterLockHandler(BaseHTTPRequestHandler):
    server_version = "InterLockMVPUI/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(render_index())
            return
        if parsed.path == "/run":
            params = parse_qs(parsed.query)
            self._html(render_run_page(Path(params.get("dir", [""])[0])))
            return
        if parsed.path == "/artifact":
            self._artifact(parsed.query)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/review":
            self._run_custom_review()
            return
        if parsed.path == "/preset":
            self._run_preset()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _run_custom_review(self) -> None:
        form = self._form()
        try:
            request = _request_from_form(form)
            run_review(request)
            triage_run(request.out_dir, write=True)
            self._redirect(f"/run?dir={quote(str(request.out_dir))}")
        except Exception as exc:
            self._html(render_error(exc), status=HTTPStatus.BAD_REQUEST)

    def _run_preset(self) -> None:
        form = self._form()
        try:
            request = _preset_request(_one(form, "preset"))
            run_review(request)
            triage_run(request.out_dir, write=True)
            self._redirect(f"/run?dir={quote(str(request.out_dir))}")
        except Exception as exc:
            self._html(render_error(exc), status=HTTPStatus.BAD_REQUEST)

    def _form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0"))
        return parse_qs(self.rfile.read(length).decode("utf-8"))

    def _artifact(self, query: str) -> None:
        params = parse_qs(query)
        try:
            artifact = _resolve_artifact_path(Path(unquote(params.get("run", [""])[0])), unquote(params.get("path", [""])[0]))
        except ValueError as exc:
            self.send_error(HTTPStatus.FORBIDDEN, str(exc))
            return
        if not artifact.exists() or not artifact.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = artifact.read_bytes()
        content_type, _encoding = mimetypes.guess_type(str(artifact))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def render_index() -> str:
    return _page(
        "InterLock MVP",
        f"""
        <section class="band">
          <div class="wrap hero">
            <div>
              <h1>InterLock MVP</h1>
              <p class="lede">Cited directional review for two engineering PDFs.</p>
            </div>
            <div class="actions">
              <form method="post" action="/preset">
                <input type="hidden" name="preset" value="public_version">
                <button data-testid="preset-version" type="submit">Run Public Version Demo</button>
              </form>
              <form method="post" action="/preset">
                <input type="hidden" name="preset" value="public_cross_doc">
                <button data-testid="preset-cross" type="submit">Run Public Cross-Doc Demo</button>
              </form>
            </div>
          </div>
        </section>
        <main class="wrap">
          <form class="panel" method="post" action="/review">
            <div class="grid">
              <label>Doc A path<input name="doc_a" value="{escape(str(PUBLIC_SPEC))}"></label>
              <label>Doc B path<input name="doc_b" value="{escape(str(PUBLIC_CROSS_DOC))}"></label>
              <label>Mode
                <select name="mode">
                  <option value="cross_doc" selected>cross_doc</option>
                  <option value="version">version</option>
                </select>
              </label>
              <label>Output directory<input name="out_dir" value="runs/ui-review"></label>
              <label>Doc A type<input name="doc_a_type" value="specification"></label>
              <label>Doc B type<input name="doc_b_type" value="protection_study"></label>
              <label>Authority YAML<input name="authority_config" value="{escape(str(DEFAULT_AUTHORITY))}"></label>
              <label>Glossary YAML<input name="glossary" value="{escape(str(DEFAULT_GLOSSARY))}"></label>
            </div>
            <div class="checks">
              <label><input type="checkbox" name="no_cloud" checked> no cloud</label>
              <label><input type="checkbox" name="no_kuzu" checked> no Kuzu</label>
            </div>
            <button data-testid="run-review" type="submit">Run Review</button>
          </form>
        </main>
        """,
    )


def render_run_page(run_dir: Path) -> str:
    if not str(run_dir):
        return render_error(ValueError("Missing run directory."))
    run_dir = run_dir.resolve()
    findings_payload = _read_optional(run_dir / "findings.json")
    metrics_payload = _read_optional(run_dir / "metrics.json")
    triage_payload = _read_optional(run_dir / "triage.json")
    findings = findings_payload.get("records", [])
    metrics = metrics_payload.get("metrics", {})
    triage_issues = triage_payload.get("issues", [])
    findings_html = "\n".join(_finding_html(run_dir, finding) for finding in findings) or "<p>No findings.</p>"
    triage_html = "\n".join(
        f"<li><strong>{escape(issue.get('severity', ''))}</strong> {escape(issue.get('title', ''))}: {escape(issue.get('summary', ''))}</li>"
        for issue in triage_issues
    ) or "<li>No triage issues.</li>"
    return _page(
        "InterLock Review Results",
        f"""
        <section class="band">
          <div class="wrap hero">
            <div>
              <h1>Review Results</h1>
              <p class="lede">{escape(str(run_dir))}</p>
            </div>
            <a class="button-link" href="/">New Review</a>
          </div>
        </section>
        <main class="wrap">
          <section class="metrics">
            <div><strong>{escape(str(metrics.get('findings', len(findings))))}</strong><span>Findings</span></div>
            <div><strong>{escape(str(metrics.get('review_required_findings', _count_severity(findings, 'review_required'))))}</strong><span>Review Required</span></div>
            <div><strong>{escape(str(metrics.get('coverage_warning_findings', _count_type(findings, 'coverage_warning'))))}</strong><span>Coverage Warnings</span></div>
            <div><strong>{escape(str(metrics.get('comparison_decisions', 0)))}</strong><span>Comparisons</span></div>
            <div><strong>{escape(str(metrics.get('absence_searches', 0)))}</strong><span>Absence Searches</span></div>
          </section>
          <section><h2>Findings</h2>{findings_html}</section>
          <section><h2>Triage</h2><ul class="triage">{triage_html}</ul></section>
          <section><h2>Artifacts</h2><div class="artifact-links">{_artifact_links(run_dir)}</div></section>
        </main>
        """,
    )


def render_error(exc: Exception) -> str:
    return _page("InterLock Error", f"<main class='wrap'><h1>Run failed</h1><pre class='error'>{escape(type(exc).__name__)}: {escape(str(exc))}</pre><a class='button-link' href='/'>Back</a></main>")


def _finding_html(run_dir: Path, finding: dict[str, Any]) -> str:
    evidence_a = finding.get("evidence_a") or {}
    evidence_b = finding.get("evidence_b") or {}
    return f"""
    <article class="finding {escape(str(finding.get('severity', '')))}">
      <div class="finding-head">
        <div>
          <h3>{escape(str(finding.get('finding_id', '')))}: {escape(str(finding.get('subject', '')))} / {escape(str(finding.get('parameter', '')))}</h3>
          <p>{escape(str(finding.get('summary', '')))}</p>
        </div>
        <div class="badge">{escape(str(finding.get('severity', '')))}</div>
      </div>
      <dl>
        <dt>Type</dt><dd>{escape(str(finding.get('finding_type', '')))}</dd>
        <dt>Authority</dt><dd>{escape(str(finding.get('authoritative_side', '')))} - {escape(str(finding.get('authority_basis', '')))}</dd>
        <dt>Confidence</dt><dd>{escape(str(finding.get('confidence', '')))}</dd>
      </dl>
      <div class="citations">{_citation_html(run_dir, "Doc A", evidence_a)}{_citation_html(run_dir, "Doc B", evidence_b)}</div>
    </article>
    """


def _citation_html(run_dir: Path, label: str, citation: dict[str, Any]) -> str:
    if not citation:
        return f"<div class='citation'><h4>{escape(label)}</h4><p>No citation.</p></div>"
    crop_path = citation.get("crop_path") or ""
    image = ""
    if crop_path:
        src = f"/artifact?run={quote(str(run_dir))}&path={quote(str(crop_path))}"
        image = f"<img src='{src}' alt='{escape(label)} citation crop'>"
    return f"<div class='citation'><h4>{escape(label)} page {escape(str(citation.get('page', '')))}</h4><blockquote>{escape(str(citation.get('quote', '')))}</blockquote>{image}</div>"


def _artifact_links(run_dir: Path) -> str:
    names = ["report.md", "findings.json", "metrics.json", "triage.json", "reasoning_graph.json", "decision_traces.json", "wiki/index.md"]
    links = []
    for name in names:
        if (run_dir / name).exists():
            href = f"/artifact?run={quote(str(run_dir))}&path={quote(name)}"
            links.append(f"<a href='{href}'>{escape(name)}</a>")
    return "\n".join(links) or "<p>No artifact links.</p>"


def _request_from_form(form: dict[str, list[str]]) -> ReviewRequest:
    return ReviewRequest(
        doc_a_path=Path(_one(form, "doc_a")),
        doc_b_path=Path(_one(form, "doc_b")),
        mode=_one(form, "mode").replace("-", "_"),  # type: ignore[arg-type]
        out_dir=Path(_one(form, "out_dir")),
        authority_config_path=_path_or_none(_one(form, "authority_config")),
        domain_glossary_path=_path_or_none(_one(form, "glossary")),
        env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
        doc_a_type=_one(form, "doc_a_type") or "auto",
        doc_b_type=_one(form, "doc_b_type") or "auto",
        no_cloud="no_cloud" in form,
        no_kuzu="no_kuzu" in form,
    )


def _preset_request(preset: str) -> ReviewRequest:
    if preset == "public_version":
        return ReviewRequest(
            doc_a_path=PUBLIC_SPEC,
            doc_b_path=PUBLIC_VERSION_REV,
            mode="version",
            out_dir=ROOT / "runs/ui-public-version",
            authority_config_path=DEFAULT_AUTHORITY,
            domain_glossary_path=DEFAULT_GLOSSARY,
            env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
            doc_a_type="specification",
            doc_b_type="specification",
            no_cloud=True,
            no_kuzu=True,
        )
    if preset == "public_cross_doc":
        return ReviewRequest(
            doc_a_path=PUBLIC_SPEC,
            doc_b_path=PUBLIC_CROSS_DOC,
            mode="cross_doc",
            out_dir=ROOT / "runs/ui-public-cross-doc",
            authority_config_path=DEFAULT_AUTHORITY,
            domain_glossary_path=DEFAULT_GLOSSARY,
            env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
            doc_a_type="specification",
            doc_b_type="protection_study",
            no_cloud=True,
            no_kuzu=True,
        )
    raise ValueError(f"Unknown preset: {preset}")


def _resolve_artifact_path(run_dir: Path, rel_path: str) -> Path:
    run_root = run_dir.resolve()
    artifact = (run_root / rel_path).resolve()
    if not artifact.is_relative_to(run_root):
        raise ValueError("Artifact path escapes run directory")
    return artifact


def _read_optional(path: Path) -> dict[str, Any]:
    return read_artifact(path) if path.exists() else {}


def _one(form: dict[str, list[str]], key: str) -> str:
    return (form.get(key) or [""])[0].strip()


def _path_or_none(value: str) -> Path | None:
    return Path(value) if value else None


def _count_severity(findings: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for finding in findings if finding.get("severity") == severity)


def _count_type(findings: list[dict[str, Any]], finding_type: str) -> int:
    return sum(1 for finding in findings if finding.get("finding_type") == finding_type)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title><style>{_css()}</style></head><body>{body}</body></html>"""


def _css() -> str:
    return """
    :root { color-scheme: light; --ink:#172026; --muted:#5a6872; --line:#d7dde2; --band:#eef3f6; --accent:#006f8f; --warn:#8a5a00; --ok:#0f6b45; --bad:#9d2f2f; }
    * { box-sizing:border-box; } body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#fbfcfd; letter-spacing:0; }
    .wrap { max-width:1180px; margin:0 auto; padding:24px; } .band { background:var(--band); border-bottom:1px solid var(--line); }
    .hero { display:flex; justify-content:space-between; gap:24px; align-items:center; } h1 { margin:0; font-size:34px; line-height:1.1; } h2 { margin:28px 0 12px; font-size:22px; } h3 { margin:0 0 8px; font-size:18px; } h4 { margin:0 0 8px; font-size:14px; color:var(--muted); }
    .lede { color:var(--muted); margin:8px 0 0; } .actions { display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
    button, .button-link { display:inline-block; border:1px solid var(--accent); background:var(--accent); color:white; padding:10px 14px; border-radius:6px; font-size:14px; text-decoration:none; cursor:pointer; }
    button:hover, .button-link:hover { background:#005b76; } .panel { border:1px solid var(--line); border-radius:8px; padding:18px; background:white; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; } label { display:flex; flex-direction:column; gap:6px; font-size:13px; color:var(--muted); }
    input, select { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px 10px; font-size:14px; color:var(--ink); background:white; }
    .checks { display:flex; gap:18px; margin:16px 0; } .checks label { flex-direction:row; align-items:center; }
    .metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin:20px 0; } .metrics div { border-top:3px solid var(--accent); background:white; padding:14px; border-radius:6px; border-left:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
    .metrics strong { display:block; font-size:26px; } .metrics span { color:var(--muted); font-size:13px; }
    .finding { border:1px solid var(--line); border-radius:8px; padding:16px; background:white; margin:14px 0; } .finding.review_required { border-left:5px solid var(--bad); } .finding.possible_issue { border-left:5px solid var(--warn); } .finding.informational { border-left:5px solid var(--ok); }
    .finding-head { display:flex; justify-content:space-between; gap:18px; } .finding p { margin:0 0 10px; color:var(--muted); } .badge { height:max-content; border:1px solid var(--line); border-radius:999px; padding:4px 9px; font-size:12px; color:var(--muted); white-space:nowrap; }
    dl { display:grid; grid-template-columns:120px 1fr; gap:6px 12px; margin:10px 0; } dt { color:var(--muted); } dd { margin:0; }
    .citations { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; } .citation { border-top:1px solid var(--line); padding-top:12px; } blockquote { margin:0 0 10px; padding:8px 10px; background:#f4f7f9; border-left:3px solid var(--accent); } img { max-width:100%; border:1px solid var(--line); background:white; }
    .triage { background:white; border:1px solid var(--line); border-radius:8px; padding:16px 16px 16px 34px; } .artifact-links { display:flex; flex-wrap:wrap; gap:10px; } .artifact-links a { color:var(--accent); border:1px solid var(--line); padding:8px 10px; border-radius:6px; background:white; text-decoration:none; }
    .error { background:#fff4f4; border:1px solid #efb9b9; border-radius:8px; padding:16px; white-space:pre-wrap; }
    @media (max-width: 760px) { .hero, .finding-head { flex-direction:column; align-items:flex-start; } .grid, .metrics, .citations { grid-template-columns:1fr; } .actions { justify-content:flex-start; } }
    """


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)
