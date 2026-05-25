from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .core.eval import run_eval
from .core.env import DEFAULT_OLD_REPO_ENV, load_env_file, load_key_files
from .core.models import ReviewRequest
from .core.review import run_review
from .core.search import search_run

app = typer.Typer(help="InterLock MVP cited directional PDF review CLI.")
console = Console()


@app.command()
def review(
    doc_a: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    doc_b: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    mode: Annotated[str, typer.Option(help="version or cross-doc")] = "version",
    out: Annotated[Path, typer.Option(help="Output run directory")] = Path("runs/demo"),
    authority_config: Annotated[Path | None, typer.Option(help="Authority YAML path")] = None,
    env_file: Annotated[Path | None, typer.Option(help="Optional .env file. Defaults to old repo .env when present.")] = None,
    doc_a_type: Annotated[str | None, typer.Option(help="Doc A type or auto")] = "auto",
    doc_b_type: Annotated[str | None, typer.Option(help="Doc B type or auto")] = "auto",
    dry_run: Annotated[bool, typer.Option(help="No cloud calls; deterministic only")] = False,
    no_cloud: Annotated[bool, typer.Option(help="Disable cloud verifier/proposer")] = False,
    no_kuzu: Annotated[bool, typer.Option(help="Skip derived Kuzu graph build for fast eval/debug runs")] = False,
    max_candidates: Annotated[int, typer.Option()] = 50,
    max_vlm_pages: Annotated[int, typer.Option()] = 10,
    max_cost_usd: Annotated[float, typer.Option()] = 5.0,
) -> None:
    normalized_mode = _normalize_mode(mode)
    request = ReviewRequest(
        doc_a_path=doc_a,
        doc_b_path=doc_b,
        mode=normalized_mode,
        out_dir=out,
        authority_config_path=authority_config,
        env_file_path=env_file or (DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None),
        doc_a_type=doc_a_type,
        doc_b_type=doc_b_type,
        dry_run=dry_run,
        no_cloud=no_cloud,
        no_kuzu=no_kuzu,
        max_candidates=max_candidates,
        max_vlm_pages=max_vlm_pages,
        max_cost_usd=max_cost_usd,
    )
    result = run_review(request)
    table = Table(title="InterLock MVP Review")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Run", result.run_id)
    table.add_row("Findings", str(result.findings_count))
    table.add_row("Review required", str(result.review_required_count))
    table.add_row("Coverage warnings", str(result.coverage_warning_count))
    table.add_row("Report", str(result.report_path))
    table.add_row("Findings JSON", str(result.findings_path))
    console.print(table)
    if result.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"- {warning}")


@app.command()
def check(
    run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    eval: Annotated[Path, typer.Option("--eval", exists=True, dir_okay=False, readable=True)],
) -> None:
    ok, issues = run_eval(run_dir, eval)
    if ok:
        console.print("[green]Eval passed.[/green]")
        raise typer.Exit(0)
    console.print("[red]Eval failed.[/red]")
    for issue in issues:
        console.print(f"- {issue}")
    raise typer.Exit(1)


@app.command()
def inspect(
    run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    finding: Annotated[str | None, typer.Option(help="Finding id to print")] = None,
) -> None:
    import json

    findings_path = run_dir / "findings.json"
    if not findings_path.exists():
        console.print(f"[red]Missing {findings_path}[/red]")
        raise typer.Exit(1)
    payload = json.loads(findings_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if finding:
        records = [record for record in records if record.get("finding_id") == finding]
    console.print_json(data=records)


@app.command()
def search(
    run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    query: Annotated[str, typer.Argument(help="Search query")],
    glossary: Annotated[Path | None, typer.Option(help="Optional AES glossary YAML")] = Path("examples/aes_glossary.yaml"),
    limit: Annotated[int, typer.Option(help="Maximum hits")] = 20,
) -> None:
    try:
        hits = search_run(run_dir, query, glossary_path=glossary, limit=limit)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    table = Table(title=f"InterLock Search: {query}")
    table.add_column("Score", justify="right")
    table.add_column("Source")
    table.add_column("Doc")
    table.add_column("Page")
    table.add_column("Subject")
    table.add_column("Parameter")
    table.add_column("Via")
    table.add_column("Quote")
    for hit in hits:
        table.add_row(
            str(hit.get("score", "")),
            str(hit.get("source", "")),
            str(hit.get("doc_id", "")),
            "" if hit.get("page") is None else str(hit.get("page")),
            str(hit.get("subject", ""))[:28],
            str(hit.get("parameter", ""))[:24],
            ",".join(str(item) for item in hit.get("retrieval_methods", [])),
            _clip(str(hit.get("quote") or hit.get("text") or ""), 90),
        )
    console.print(table)


@app.command()
def doctor() -> None:
    load_env_file(DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None)
    load_key_files()
    checks = []
    for module in ["fitz", "pydantic", "typer", "rich", "rapidfuzz", "pint", "kuzu", "jinja2", "PIL", "structlog", "yaml", "anthropic"]:
        checks.append((module, _import_ok(module)))
    checks.append(("cloud_key", bool(__import__("os").environ.get("OPENAI_API_KEY") or __import__("os").environ.get("ANTHROPIC_API_KEY"))))
    checks.append(("kuzu_temp_write", _kuzu_temp_ok()))
    checks.append(("output_tmp_write", _tmp_write_ok()))

    table = Table(title="InterLock MVP Doctor")
    table.add_column("Check")
    table.add_column("Status")
    for name, ok in checks:
        table.add_row(name, "[green]ok[/green]" if ok else "[red]missing/fail[/red]")
    console.print(table)
    if not all(ok for name, ok in checks if name != "cloud_key"):
        raise typer.Exit(1)


def _normalize_mode(mode: str):
    normalized = mode.replace("-", "_")
    if normalized not in {"version", "cross_doc"}:
        raise typer.BadParameter("mode must be version or cross-doc")
    return normalized


def _import_ok(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def _kuzu_temp_ok() -> bool:
    temp_dir = Path(tempfile.mkdtemp(prefix="interlock-kuzu-"))
    try:
        import kuzu

        db = kuzu.Database(str(temp_dir / "graph.kuzu"))
        conn = kuzu.Connection(db)
        conn.execute("CREATE NODE TABLE T(id STRING, PRIMARY KEY(id));")
        conn.execute("CREATE (:T {id: 'ok'});")
        return True
    except Exception:
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _tmp_write_ok() -> bool:
    try:
        with tempfile.TemporaryDirectory(prefix="interlock-write-") as directory:
            path = Path(directory) / "ok.txt"
            path.write_text("ok", encoding="utf-8")
            return path.read_text(encoding="utf-8") == "ok"
    except Exception:
        return False


def _clip(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


if __name__ == "__main__":
    app()
