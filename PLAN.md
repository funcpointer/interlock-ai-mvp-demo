# InterLock MVP Plan: Cited Directional PDF Review Engine

## Target

Build a CLI-first review engine for exactly two engineering PDFs. It produces cited, directional findings for:

- version review: baseline document vs revised document,
- cross-document review: different document classes such as spec vs protection study.

The product claim stays narrow: InterLock helps senior reviewers find verifiable mismatches more systematically. It does not certify engineering correctness.

The CLI is an adapter only. Business logic lives in:

```python
run_review(request: ReviewRequest) -> ReviewResult
```

Future API, UI, batch jobs, and notebooks must call the same function.

## Current Build State

Implemented:

- PyMuPDF extraction for pages, text blocks, annotations, rendered page images, and crops.
- JSON artifact store with one top-level `schema_version` per artifact.
- Authority resolution for version and cross-document mode.
- Evidence mining for equipment IDs, values/units, references, annotations, and coverage warnings.
- Review-map graph artifacts:
  - `doc_graph_a.json`
  - `doc_graph_b.json`
  - `diff_graph.json`
- Deterministic diff graph to findings.
- Pint-backed unit equivalence and custom `%Z` / decimal-slip checks.
- Markdown report.
- Eval runner.
- Optional Kuzu graph build.
- Stage-level JSONL logs and metrics.
- `rg`-backed search over persisted review-map artifacts.

Current validated fixture classes:

- version gold: `doc_a_60pct.pdf` vs `doc_b_90pct.pdf`
- negative pair: `doc_a_60pct.pdf` vs itself
- cross-doc gold: `spec_xfmr_001.pdf` vs `doc_a_60pct.pdf`
- scanned/low-text stress: `doc_a_scanned.pdf` vs itself

## Invariants

- JSON artifacts are source of truth.
- `report.md`, Kuzu, search indexes, and future UI/API payloads are derived from JSON.
- Every finding needs source evidence: page, quote, bbox/crop.
- No citation means no finding.
- Authority direction must appear on every finding.
- Unknown authority routes to review, not overclaim.
- Page number is not identity. Context, subject, claim, and citation form identity.
- Cloud LLM/VLM may propose or verify candidates, but cannot silently publish findings.
- Local SLM/search tools may improve recall, but deterministic/verifier gates still decide findings.
- Logs and metrics are first-class artifacts, not afterthoughts.
- Slow is acceptable when it buys accuracy, precision, recall, citations, or reviewer trust.
- Fast is only a convenience when the skipped work is derived, non-authoritative, or already covered by persisted artifacts.

## Core Commands

Fast deterministic eval path:

```bash
/Users/kc/venv-12/bin/python -m interlock_mvp review A.pdf B.pdf \
  --mode version \
  --out runs/demo \
  --authority-config examples/aes_authority.yaml \
  --no-cloud \
  --no-kuzu

/Users/kc/venv-12/bin/python -m interlock_mvp check runs/demo --eval eval/demo.yaml
```

Full derived-graph path:

```bash
/Users/kc/venv-12/bin/python -m interlock_mvp review A.pdf B.pdf \
  --mode version \
  --out runs/demo-with-graph \
  --authority-config examples/aes_authority.yaml \
  --no-cloud
```

Doctor:

```bash
/Users/kc/venv-12/bin/python -m interlock_mvp doctor
```

## Artifact Contract

Every run writes:

```text
manifest.json
authority.json
documents.json
pages.json
annotations.json
regions.json
evidence.json
doc_graph_a.json
doc_graph_b.json
diff_graph.json
candidates.json
findings.json
metrics.json
logs.jsonl
report.md
crops/
search/review_map.jsonl
graph.kuzu/        # optional, derived, skipped by --no-kuzu
```

The JSON graph artifacts are the MVP's "review map." They are the boring, engineering-grade equivalent of a memory palace:

```text
Document
  -> page / region / annotation
  -> context / table / curve / schedule / spec section
  -> subject / equipment / reference
  -> claim / value / assumption
  -> citation / crop / bbox
  -> diff edge / finding
```

## Telemetry Policy

Every run must answer:

- Did extraction fail?
- Did evidence mining miss the subject?
- Did context assignment degrade to document-level?
- Did graph alignment create too many or too few diff edges?
- Did verification downgrade anything?
- Where did runtime go?

Required metrics:

- `stage_seconds`
- page/region/annotation counts per document
- empty/low-text page counts
- evidence counts by kind/source/confidence/doc
- generic-subject and document-context evidence counts
- context/subject/claim counts per graph
- diff edges by type/alignment/identity strength
- candidates by type/status/identity strength
- findings by type/severity/confidence
- cloud cost estimate
- Kuzu status

Current telemetry finding: Kuzu graph build can dominate runtime. That is acceptable when graph inspection is the goal. Kuzu is optional only because it is a derived mirror of canonical JSON, not because speed outranks accuracy.

## Evaluation Policy

Evaluation is mandatory at checkpoints.

Accuracy checkpoint suite:

- unit tests
- version gold eval
- negative eval
- cross-doc eval
- scanned/low-text review sanity
- all with `--no-cloud --no-kuzu` only because cloud export is gated and Kuzu is derived

Full checkpoint suite:

- accuracy checkpoint suite
- one Kuzu-enabled run
- optional cloud/VLM run only when document export is explicitly allowed

Acceptance now means:

- expected gold findings present,
- forbidden findings absent,
- negative pair has zero `review_required`,
- scanned pair produces coverage warnings and zero `review_required`,
- every non-coverage finding has page/quote/crop,
- no banned verifier-authored language,
- metrics/logs show plausible stage counts.

## Accuracy Roadmap

### Phase A: Inspectable Baseline

Status: mostly done.

- deterministic extraction,
- review-map graph,
- fixture evals,
- telemetry,
- optional Kuzu.

### Phase B: Search-Assisted Debugging

Status: first slice implemented.

Add `search` over persisted JSON/text artifacts. Use `rg --json` as the deterministic primitive.

Search must operate on extracted artifacts, not PDFs directly:

```text
search/evidence.jsonl
search/claims.jsonl
search/contexts.jsonl
search/findings.jsonl
```

Current MVP writes a combined:

```text
search/review_map.jsonl
```

Agentic behavior is limited to:

- query expansion from AES glossary,
- multiple `rg` searches,
- ranking by context/subject/claim proximity,
- returning cited evidence hits,
- proposing candidates marked `proposal_only`.

Search never publishes findings.

### Phase C: Better Document Understanding

Do not keep growing regexes forever. Add richer extraction only where it improves citations and recall:

- `pdfplumber` for table/row debugging on machine-generated PDFs,
- Docling for layout/table structure when PyMuPDF order is weak,
- OCRmyPDF/PaddleOCR for scans,
- VLM extraction for low-text/rotated/visual-only evidence.

PyMuPDF remains the citation/crop geometry layer.

This phase is allowed to be slow. Accuracy, recall, and citation quality are the reason to do it.

### Phase D: Semantic Recall

After graph nodes are stable, add LanceDB or another vector/hybrid index over:

- contexts,
- subjects,
- claims,
- evidence,
- regions.

Use it for recall only. Candidate proposals still require citations and verification.

### Phase E: Local SLM Assistance

Use Ollama/local SLMs for:

- alias suggestions,
- glossary expansion,
- context title canonicalization,
- finding explanation drafts.

Never let local SLMs publish findings without deterministic/verifier gates.

## Checkpoint Policy

Checkpoint after:

- any data-model change,
- any finding-generation change,
- any extraction-context change,
- any verifier/prompt change,
- any evaluation fixture change.

Checkpoint contents:

- code version,
- plan update,
- test/eval command outputs,
- key metrics summary,
- known accuracy limits,
- next risk to attack.

Do not checkpoint after cosmetic-only edits unless they change demo behavior.

## Runtime Policy

Runtime budget is subordinate to review quality.

Accept slow paths for:

- OCR,
- VLM extraction,
- table reconstruction,
- model-proposed candidates,
- semantic/vector recall,
- graph traversal that changes candidates or reviewer-visible evidence,
- extra verification passes that reduce false positives.

Do not accept slow paths for:

- rebuilding a derived mirror that does not alter findings,
- repeated work that can be cached,
- hidden retries without telemetry,
- expensive model calls without cost counters and source citations.

Kuzu is currently in the second category: useful for inspection, not part of finding authority.

## Near-Term Execution Plan

1. Make Kuzu optional because it is derived, not because it is slow.
2. Add Makefile targets for repeatable tests/evals.
3. Run accuracy checkpoint suite.
4. Initialize repo checkpoint if no git repo exists.
5. Add `search` artifacts and `rg`-backed CLI search.
6. Add AES glossary.
7. Re-run accuracy checkpoint suite.
8. Improve search ranking so diff/finding hits beat generic evidence when the query names a discrepancy.
9. Only then consider LanceDB/local SLM integration.
