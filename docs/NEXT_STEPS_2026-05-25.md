# Next Steps - 2026-05-25

Scope: post-audit execution plan for improving MVP accuracy, precision, recall, and reviewer trust.

## Priority Order

### P0: Keep the Authoritative Spine Singular

Current primary path:

```text
PDF -> extraction -> evidence -> document graph -> diff graph -> reasoning graph -> findings
```

This is the right spine for the MVP. Anything else must be explicitly derived or debug-only.

Done in checkpoint `checkpoint-2026-05-25-singular-spine`:

- removed the old candidate-generation module,
- stopped writing `candidates.json`,
- removed `max_candidates` / `--max-candidates` from the active CLI and request model.

Why:

- two finding paths create false confidence and future regressions,
- reasoning decisions carry better explainability than candidate records.

### P1: Domain Dictionary as First-Class Input

Done in this checkpoint:

- `examples/aes_glossary.yaml` expanded into equipment, parameter, context, reference, and search alias sections,
- `DomainDictionary` loader added,
- review/corpus CLI paths accept a glossary,
- extraction, parameter naming, context labeling, and search expansion consume the same dictionary.

Guardrail:

- the dictionary can improve recall, but must not invent identity from weak row text.
- acronym prefixes such as `XFMR` require explicit compact/hyphen/hash tags and do not treat `XFMR 12 x FLA` as equipment `XFMR-12`.

### P1: Decision Trace / Signal Ledger

Done in checkpoint `checkpoint-2026-05-25-singular-spine`: add `decision_traces.json`.

Each finding should show:

- identity signals,
- parameter signals,
- value/unit signals,
- context signals,
- authority signals,
- rejected alternatives,
- downgrade reasons,
- contradictions.

Call this signal corroboration, not majority vote. Majority voting is unsafe when multiple systems share the same bad OCR/text source.

### P1: Real AES Corpus Evaluation

Use `corpora/aes/local_manifest.yaml` with:

- one positive version pair,
- one negative/no-mismatch pair,
- one cross-document pair,
- one scan/annotation-heavy pair.

Every pair needs eval YAML with:

- expected findings,
- forbidden findings,
- max review-required count,
- coverage warning expectations.

### P2: Extraction Upgrade Based on Failures

Do not add broad OCR/VLM/table parsing blindly.

Use telemetry first:

- low-text pages,
- document-context evidence,
- generic subjects,
- missing expected findings,
- context rooms with weak labels.

Then add targeted extraction lanes:

- OCR for low-text pages,
- VLM crop verification for rotated/image-only labels,
- table extraction for schedules/settings,
- annotation/highlight regression fixtures.

### P2: Real Embeddings for LanceDB

Current LanceDB vectors are deterministic hash vectors. They are useful as a local index smoke test, not semantic retrieval.

Next:

- add local Ollama embedding support,
- keep rg and SQLite FTS as deterministic baselines,
- never let LanceDB create findings directly.

## Current Checkpoint Result

Dictionary integration regression caught and fixed:

- first attempt over-admitted `XFMR 12 x FLA` as equipment `XFMR-12`,
- tightened acronym-prefix subject extraction,
- fixture evals returned to baseline.

Validated:

```text
tests/test_domain_dictionary.py tests/test_evidence.py tests/test_search.py tests/test_review_integration.py
  12 passed

make eval-fast
  46 tests passed
  version eval passed
  negative eval passed
  cross-doc eval passed
  scanned eval passed
```
