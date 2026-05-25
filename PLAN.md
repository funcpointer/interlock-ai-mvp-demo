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
- AES/domain glossary loader used by extraction, parameter naming, context labeling, corpus runs, and search expansion.
- Review-map graph artifacts:
  - `doc_graph_a.json`
  - `doc_graph_b.json`
  - `diff_graph.json`
- Reasoning graph artifact:
  - `reasoning_graph.json`
- Deterministic diff graph to findings.
- Pint-backed unit equivalence and custom `%Z` / decimal-slip checks.
- Markdown report.
- Eval runner.
- Optional Kuzu graph build.
- Stage-level JSONL logs and metrics.
- `rg`-backed search over persisted review-map artifacts.
- Local second-brain SQLite/FTS index over review-map artifacts.
- LanceDB index over review-map artifacts with deterministic local embeddings.
- Corpus manifest runner for AES/private partner document batches.
- Derived Markdown review wiki over each run: index, log, documents, subjects, findings, reasoning decisions.
- Context memory layer: memory-palace rooms/trails derived from contexts and fed into second-brain search.
- Diagnostic triage command that reads persisted artifacts and writes `triage.json`.
- Transformer-spec context extraction: multi-page spec/table section carry,
  main-equipment subject attachment, and context-aware percent/impedance
  classification.

Current validated fixture classes:

- version gold: `doc_a_60pct.pdf` vs `doc_b_90pct.pdf`
- negative pair: `doc_a_60pct.pdf` vs itself
- cross-doc gold: `spec_xfmr_001.pdf` vs `doc_a_60pct.pdf`
- scanned/low-text stress: `doc_a_scanned.pdf` vs itself
- synthetic reference smoke: `synth_equipment_spec_v2.pdf` vs `synth_equipment_spec_v3.pdf`
- real cross-doc smoke: `real_ieee_xfmr_spec_guide.pdf` vs `real_sel_xfmr_protection.pdf`
- AES near-real corpus seed: `corpora/aes/near_real_seed.yaml`
- public AES smoke corpus downloaded locally under gitignored `corpora/aes/docs/public_aes/`
- public AES synthetic revision demo: `make eval-public-demo`

Current accuracy caution:

- The AES glossary is first-class but intentionally bounded. It improves recall
  for partner vocabulary without becoming an authority source. It must not
  invent equipment identity from weak row text; exact citations and reasoning
  gates still decide findings.
- Public AES smoke runs are useful stress tests, but not gold product demos by
  themselves. The best demo needs a paired revision/cross-doc set with explicit
  expected/forbidden findings.
- The first demo-quality public pair now exists. It is a watermarked synthetic
  revision of the public AES Somerset main power transformer specification sheet
  with explicit eval gold.

## Invariants

- JSON artifacts are source of truth.
- `report.md`, Kuzu, search indexes, wiki pages, and future UI/API payloads are derived from JSON.
- Every finding needs source evidence: page, quote, bbox/crop.
- No citation means no finding.
- Authority direction must appear on every finding.
- Unknown authority routes to review, not overclaim.
- Page number is not identity. Context, subject, claim, and citation form identity.
- Cloud LLM/VLM may propose evidence or verify reasoning decisions later, but cannot silently publish findings.
- Local SLM/search tools may improve recall, but deterministic/verifier gates still decide findings.
- Logs and metrics are first-class artifacts, not afterthoughts.
- Slow is acceptable when it buys accuracy, precision, recall, citations, or reviewer trust.
- Fast is only a convenience when the skipped work is derived, non-authoritative, or already covered by persisted artifacts.

## Core Commands

Fast deterministic eval path:

```bash
python -m interlock_mvp review A.pdf B.pdf \
  --mode version \
  --out runs/demo \
  --authority-config examples/aes_authority.yaml \
  --no-cloud \
  --no-kuzu

python -m interlock_mvp check runs/demo --eval eval/demo.yaml
```

Full derived-graph path:

```bash
python -m interlock_mvp review A.pdf B.pdf \
  --mode version \
  --out runs/demo-with-graph \
  --authority-config examples/aes_authority.yaml \
  --no-cloud
```

Doctor:

```bash
python -m interlock_mvp doctor
```

Corpus intake:

```bash
python -m interlock_mvp corpus corpora/aes/local_manifest.yaml \
  --out-root runs/aes-corpus \
  --authority-config examples/aes_authority.yaml \
  --no-cloud \
  --no-kuzu
```

Run triage on any completed run:

```bash
python -m interlock_mvp triage runs/demo
```

Private AES PDFs are not committed. They are referenced by
`corpora/aes/local_manifest.yaml`, which is gitignored. The committed
`corpora/aes/near_real_seed.yaml` is only a bridge over existing fixture and
public/vendor PDFs.

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
reasoning_graph.json
decision_traces.json
context_memory.json
findings.json
metrics.json
logs.jsonl
report.md
crops/
search/review_map.jsonl
search/second_brain.sqlite
search/lancedb/
search/lancedb_meta.json
wiki/
graph.kuzu/        # optional, derived, skipped by --no-kuzu
```

`triage.json` is written by the explicit `interlock_mvp triage RUN_DIR` command.
It is diagnostic, not authoritative. It reports extraction, context, subject
resolution, reasoning, verification, and explainability risks found in the
already-written artifacts.

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

The Markdown wiki is the LLM-readable synthesis layer. It is intentionally
derived from JSON, not authoritative. It gives the next reviewer or model a
stable starting map before falling back to search, JSON, crops, or source PDFs.

The context memory layer turns context from a flat label into navigation:

- **rooms**: tables, curves, spec sections, document-page fallback contexts,
- **neighbors**: adjacent rooms in document order,
- **trails**: finding-centered paths through rooms and cited evidence,
- **second-brain records**: room/trail records indexed in JSONL, SQLite FTS,
  LanceDB, and `rg`.

Rooms and trails help recall and reviewer navigation. They do not create
findings.

## Telemetry Policy

Every run must answer:

- Did extraction fail?
- Did evidence mining miss the subject?
- Did context assignment degrade to document-level?
- Did graph alignment create too many or too few diff edges?
- Did verification downgrade anything?
- Where did runtime go?
- Does triage say the run is absence-only, document-context-heavy, or missing
  decision traces?

Required metrics:

- domain dictionary term counts
- `stage_seconds`
- page/region/annotation counts per document
- empty/low-text page counts
- evidence counts by kind/source/confidence/doc
- generic-subject and document-context evidence counts
- context/subject/claim counts per graph
- context-memory rooms/trails/rooms-with-findings
- diff edges by type/alignment/identity strength
- decision traces and traces with downgrade reasons
- triage issue counts by category/severity when `triage` has been run
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
- triage over checkpoint runs
- all with `--no-cloud --no-kuzu` only because cloud export is gated and Kuzu is derived

Full checkpoint suite:

- accuracy checkpoint suite
- expanded example suite
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

Smoke examples are allowed to have loose caps instead of exact expected findings. They exist to catch regressions and expose gaps, not to claim gold precision/recall.

## Accuracy Roadmap

### Phase A: Inspectable Baseline

Status: mostly done.

- deterministic extraction,
- review-map graph,
- fixture evals,
- telemetry,
- optional Kuzu.

### Phase B: Search-Assisted Debugging

Status: second slice implemented.

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
search/second_brain.sqlite
```

Agentic behavior is limited to:

- query expansion from AES glossary,
- multiple `rg` and SQLite FTS searches,
- ranking by context/subject/claim proximity,
- fusing exact and full-text results,
- returning cited evidence hits.

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

### Phase F: Reasoning Graph Hardening

Status: first slice implemented.

The original graph was useful but too artifact-shaped. It traced where evidence came from, but did not model enough of the reviewer reasoning:

- why claim A aligned to claim B,
- which alternatives were rejected,
- why a missing item is true absence versus extraction failure,
- which comparisons were deterministic versus verifier-assisted,
- which relation had low confidence.

First-principles rule:

- a **node** is a durable review object a reviewer may inspect independently,
- a **relation** is a simple asserted connection between objects,
- when a connection has confidence, method, rejected alternatives, rationale, or audit value, promote it to a node.

Current acceptable nodes:

- `Document`
- `Page`
- `Region`
- `Evidence`
- `Context`
- `Subject`
- `Claim`
- `DiffEdge`
- `Finding`
- `AuthorityDecision`

Current relations are mostly provenance:

- `DOCUMENT_HAS_PAGE`
- `PAGE_HAS_REGION`
- `REGION_SUPPORTS_EVIDENCE`
- `CONTEXT_HAS_SUBJECT`
- `SUBJECT_HAS_CLAIM`
- `CLAIM_IN_CONTEXT`
- `FINDING_CITES_EVIDENCE`
- `FINDING_HAS_AUTHORITY`
- `DIFF_CITES_CLAIM`

That is enough for traceability, not enough for engineering-grade review reasoning.

#### F1: Add Reasoning Decision Models

Add explicit internal models:

```python
AlignmentDecision
ComparisonDecision
AbsenceSearch
```

`AlignmentDecision` records:

- `alignment_id`
- `a_claim_id`
- `b_claim_id`
- `subject_method`: exact / alias / context_bridge / semantic / model_proposed
- `parameter_method`: exact / normalized / rejected
- `context_method`: exact / canonicalized / cross_doc_bridge / missing
- `confidence`
- `accepted`
- `rationale`
- `rejected_b_claim_ids`

`ComparisonDecision` records:

- `comparison_id`
- `alignment_id`
- `comparison_type`: equivalent / value_mismatch / needs_engineer_review
- `unit_method`: exact / pint / custom_percent_impedance / dimension_mismatch
- `plausibility_notes`
- `deterministic`
- `verifier_status`: not_run / passed / downgraded / rejected
- `rationale`

`AbsenceSearch` records:

- `absence_id`
- `a_subject_id` or `a_claim_id`
- `searched_doc_id`
- `searched_context_ids`
- `searched_parameters`
- `query_terms`
- `candidate_ids_considered`
- `rejected_candidate_ids`
- `coverage_status`: searched / low_text / no_aligned_context / extractor_gap
- `confidence`
- `rationale`

Acceptance:

- all three models serialize into JSON artifacts, **implemented**,
- every `missing_item` finding references an `AbsenceSearch`, **implemented for current graph findings**,
- every `value_mismatch` or `needs_engineer_review` finding references a `ComparisonDecision`, **implemented for current graph findings**,
- tests prove findings can be traced back to decision nodes and cited evidence, **implemented**.

#### F2: Replace Thin `DiffEdge` Semantics Incrementally

Do not delete `DiffEdge` immediately. First make it a compatibility projection derived from decisions.

Order:

1. Keep `diff_graph.json` shape stable.
2. Add `reasoning_graph.json` with decisions. **Implemented.**
3. Generate findings from `ComparisonDecision` and `AbsenceSearch`. **Implemented for non-coverage findings.**
4. Keep old diff graph in artifacts for search/debug compatibility.
5. Once evals pass, decide whether `DiffEdge` stays as a derived view or disappears.

Acceptance:

- existing `make eval-fast` passes,
- `findings.json` count and gold expectations stay stable unless a stricter contract exposes a real false positive,
- search still returns finding/diff/evidence hits,
- `reasoning_graph.json` explains the path from evidence to finding, **implemented**,
- metrics report `comparison_sourced_findings`, `absence_sourced_findings`, and `coverage_edge_sourced_findings`, **implemented**.

#### F3: Make Kuzu Mirror the Reasoning Graph

Kuzu should mirror the canonical JSON, not invent structure.

Add node tables:

- `AlignmentDecision`
- `ComparisonDecision`
- `AbsenceSearch`

Add relation tables:

- `ALIGNMENT_LEFT_CLAIM`
- `ALIGNMENT_RIGHT_CLAIM`
- `ALIGNMENT_REJECTED_CLAIM`
- `COMPARISON_FROM_ALIGNMENT`
- `ABSENCE_SEARCHED_CONTEXT`
- `ABSENCE_REJECTED_CANDIDATE`
- `FINDING_FROM_COMPARISON`
- `FINDING_FROM_ABSENCE_SEARCH`

Acceptance:

- `make eval-kuzu` builds without warnings, **implemented**,
- a Kuzu query can answer: "why was this finding created?", **partially implemented through decision nodes**,
- a Kuzu query can answer: "what did we reject before calling this missing?"

#### F4: Strengthen Eval Around Reasoning, Not Just Output

Status: first slice implemented.

Extend eval YAML matchers with:

```yaml
expected_findings:
  - finding_type: value_mismatch
    parameter: rating
    evidence_a:
      value: "1000"
    evidence_b:
      value: "100"
    comparison:
      comparison_type: value_mismatch
      unit_method: pint
    alignment:
      subject_method_in: [exact, context_bridge]
      rejected_b_claim_count_max: 2
```

For missing items:

```yaml
expected_findings:
  - finding_type: missing_item
    subject_contains: LPN-RK-500SP
    absence_search:
      coverage_status: searched
      searched_context_contains: tcc3
```

Acceptance:

- eval fails if a finding has the right label but wrong evidence, **implemented**,
- eval fails if a missing item has no absence-search trace, **implemented for expected findings that declare `absence_search`**,
- eval fails if an alignment used an explicitly forbidden method, **implemented through nested reasoning matchers**.

#### F5: Instrument Reasoning Quality Metrics

Add metrics:

- alignment decisions by method/confidence/accepted,
- rejected candidate count per accepted alignment,
- comparison decisions by type/unit method/verifier status,
- absence searches by coverage status/confidence,
- findings by decision source,
- document-context fallback rate,
- generic-subject rate.

Acceptance:

- metrics reveal whether a run is relying too much on weak context bridges,
- metrics reveal missing-item risk caused by low-text or unsearched contexts,
- report includes a compact "review reasoning health" section, **implemented**.

#### F6: Do Not Overbuild

Out of scope for this phase:

- LanceDB,
- local SLM publishing decisions,
- UI,
- new workflow/orchestration framework,
- replacing PyMuPDF,
- graph algorithms that do not change findings or auditability.

Those only become useful after decision nodes exist.

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
- model-proposed evidence/claim suggestions,
- semantic/vector recall,
- graph traversal that changes reviewer-visible evidence,
- extra verification passes that reduce false positives.

Do not accept slow paths for:

- rebuilding a derived mirror that does not alter findings,
- repeated work that can be cached,
- hidden retries without telemetry,
- expensive model calls without cost counters and source citations.

Kuzu is currently in the second category: useful for inspection, not part of finding authority.

The second-brain SQLite index is also derived, but cheap enough to build every run and useful enough for debugging that it stays on by default.

## Near-Term Execution Plan

Completed:

1. Make Kuzu optional because it is derived, not because it is slow.
2. Add Makefile targets for repeatable tests/evals.
3. Run accuracy checkpoint suite.
4. Add `search` artifacts and `rg`-backed CLI search.
5. Add AES glossary.
6. Improve search ranking so diff/finding hits beat generic evidence when the query names a discrepancy.
7. Tighten eval contracts around cited evidence.
8. Add reasoning decision models, `reasoning_graph.json`, finding decision IDs, reasoning metrics, report reasoning health, search records, Kuzu decision nodes, and eval assertions over reasoning decisions.
9. Generate non-coverage findings by iterating `ComparisonDecision` and `AbsenceSearch`; keep `DiffEdge` as lookup/debug context.
10. Remove the stale candidate-generation path and add `decision_traces.json` as the finding-level signal ledger.
11. Add `triage` command and use it on fixture/public-AES runs to expose extraction/context/reasoning failures.
12. Add transformer-spec context carry, main-equipment subject attachment, and fix `%` misclassification caused by matching the `z` in `size`.
13. Add `make eval-public-demo`: generate a watermarked synthetic revision of a
    public AES transformer spec and validate two cited directional findings.

Next:

1. Polish the public-demo report/walkthrough for a 2-5 minute screen recording.
2. Improve subject/context alignment for cross-document review using true paired AES packet data when available.
3. Add OCR/VLM extraction for pages that triage marks weak/low-text.
4. Add table-aware extraction for schedules, settings, and drawing/spec tables beyond the current section-header carry.
5. Add real local embeddings for LanceDB after extraction/context failures are measured.
6. Add Kuzu smoke queries for finding-to-decision-trace traceability.

Validation after each step:

```bash
make coverage
make eval-fast
$(PY) -m interlock_mvp triage runs/checkpoint-version
$(PY) -m interlock_mvp triage runs/checkpoint-cross
$(PY) -m interlock_mvp triage runs/checkpoint-scanned
make eval-examples
make eval-search
make eval-kuzu
```
