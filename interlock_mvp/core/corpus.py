from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .artifacts import write_json
from .env import DEFAULT_OLD_REPO_ENV
from .eval import run_eval
from .models import ReviewMode, ReviewRequest
from .review import run_review

CORPUS_SCHEMA_VERSION = "interlock_mvp.corpus.v1"


class CorpusPair(BaseModel):
    id: str
    mode: ReviewMode = "version"
    doc_a: Path
    doc_b: Path
    authority_config: Path | None = None
    domain_glossary: Path | None = None
    eval: Path | None = None
    doc_a_type: str | None = "auto"
    doc_b_type: str | None = "auto"
    no_cloud: bool | None = None
    no_kuzu: bool | None = None
    max_vlm_pages: int | None = None
    max_cost_usd: float | None = None
    notes: str = ""


class CorpusManifest(BaseModel):
    schema_version: str = CORPUS_SCHEMA_VERSION
    name: str
    description: str = ""
    source_root: Path | None = None
    pairs: list[CorpusPair] = Field(default_factory=list)


class CorpusRunSummary(BaseModel):
    pair_id: str
    status: Literal["completed", "eval_passed", "eval_failed", "missing_files", "errored"]
    mode: ReviewMode
    run_dir: str
    doc_a_path: str
    doc_b_path: str
    findings_count: int = 0
    review_required_count: int = 0
    coverage_warning_count: int = 0
    eval_path: str | None = None
    eval_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def load_corpus_manifest(path: Path) -> CorpusManifest:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    manifest = CorpusManifest.model_validate(payload)
    if manifest.schema_version != CORPUS_SCHEMA_VERSION:
        raise ValueError(f"Unsupported corpus schema_version: {manifest.schema_version}")
    return manifest


def run_corpus_manifest(
    manifest_path: Path,
    *,
    out_root: Path,
    default_authority_config: Path | None = None,
    default_domain_glossary: Path | None = None,
    no_cloud: bool = True,
    no_kuzu: bool = True,
    max_vlm_pages: int = 10,
    max_cost_usd: float = 5.0,
) -> list[CorpusRunSummary]:
    manifest = load_corpus_manifest(manifest_path)
    out_root.mkdir(parents=True, exist_ok=True)
    summaries: list[CorpusRunSummary] = []

    for pair in manifest.pairs:
        doc_a = _resolve_doc_path(pair.doc_a, manifest_path=manifest_path, source_root=manifest.source_root)
        doc_b = _resolve_doc_path(pair.doc_b, manifest_path=manifest_path, source_root=manifest.source_root)
        run_dir = out_root / _safe_run_id(pair.id)
        eval_path = _resolve_control_path(pair.eval, manifest_path=manifest_path) if pair.eval else None
        authority_config = _resolve_control_path(pair.authority_config, manifest_path=manifest_path) if pair.authority_config else default_authority_config
        domain_glossary = _resolve_control_path(pair.domain_glossary, manifest_path=manifest_path) if pair.domain_glossary else default_domain_glossary
        missing = [str(path) for path in (doc_a, doc_b) if not path.exists()]
        if eval_path and not eval_path.exists():
            missing.append(str(eval_path))
        if authority_config and not authority_config.exists():
            missing.append(str(authority_config))
        if domain_glossary and not domain_glossary.exists():
            missing.append(str(domain_glossary))
        if missing:
            summaries.append(
                CorpusRunSummary(
                    pair_id=pair.id,
                    status="missing_files",
                    mode=pair.mode,
                    run_dir=str(run_dir),
                    doc_a_path=str(doc_a),
                    doc_b_path=str(doc_b),
                    eval_path=str(eval_path) if eval_path else None,
                    warnings=[f"Missing file: {path}" for path in missing],
                )
            )
            continue

        try:
            result = run_review(
                ReviewRequest(
                    doc_a_path=doc_a,
                    doc_b_path=doc_b,
                    mode=pair.mode,
                    out_dir=run_dir,
                    authority_config_path=authority_config,
                    domain_glossary_path=domain_glossary,
                    env_file_path=DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None,
                    doc_a_type=pair.doc_a_type,
                    doc_b_type=pair.doc_b_type,
                    no_cloud=pair.no_cloud if pair.no_cloud is not None else no_cloud,
                    no_kuzu=pair.no_kuzu if pair.no_kuzu is not None else no_kuzu,
                    max_vlm_pages=pair.max_vlm_pages or max_vlm_pages,
                    max_cost_usd=pair.max_cost_usd or max_cost_usd,
                )
            )
            status: Literal["completed", "eval_passed", "eval_failed"] = "completed"
            eval_issues: list[str] = []
            if eval_path:
                ok, eval_issues = run_eval(run_dir, eval_path)
                status = "eval_passed" if ok else "eval_failed"
            summaries.append(
                CorpusRunSummary(
                    pair_id=pair.id,
                    status=status,
                    mode=pair.mode,
                    run_dir=str(result.out_dir),
                    doc_a_path=str(doc_a),
                    doc_b_path=str(doc_b),
                    findings_count=result.findings_count,
                    review_required_count=result.review_required_count,
                    coverage_warning_count=result.coverage_warning_count,
                    eval_path=str(eval_path) if eval_path else None,
                    eval_issues=eval_issues,
                    warnings=result.warnings,
                )
            )
        except Exception as exc:
            summaries.append(
                CorpusRunSummary(
                    pair_id=pair.id,
                    status="errored",
                    mode=pair.mode,
                    run_dir=str(run_dir),
                    doc_a_path=str(doc_a),
                    doc_b_path=str(doc_b),
                    eval_path=str(eval_path) if eval_path else None,
                    warnings=[f"{type(exc).__name__}: {exc}"],
                )
            )

    write_json(out_root / "corpus_results.json", records=summaries, meta={"manifest": str(manifest_path), "name": manifest.name})
    return summaries


def corpus_success(summaries: list[CorpusRunSummary]) -> bool:
    return all(summary.status in {"completed", "eval_passed"} for summary in summaries)


def _resolve_doc_path(path: Path, *, manifest_path: Path, source_root: Path | None) -> Path:
    if path.is_absolute():
        return path
    if source_root:
        root = source_root if source_root.is_absolute() else manifest_path.parent / source_root
        return (root / path).resolve()
    return (manifest_path.parent / path).resolve()


def _resolve_control_path(path: Path | None, *, manifest_path: Path) -> Path | None:
    if path is None:
        return None
    if path.is_absolute():
        return path
    direct = (manifest_path.parent / path).resolve()
    if direct.exists():
        return direct
    return (Path.cwd() / path).resolve()


def _safe_run_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return safe or "pair"
