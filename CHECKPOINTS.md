# InterLock MVP Checkpoints

## checkpoint-2026-05-25-telemetry-fast-eval

Purpose:

- make telemetry the default debugging surface,
- make Kuzu optional because it is derived, not authoritative,
- codify repeatable fixture evaluation.

Changed:

- `ReviewRequest.no_kuzu`
- CLI `--no-kuzu`
- stage-level `logs.jsonl` events
- richer `metrics.json` counters
- `Makefile` eval targets
- scanned eval contract
- updated `PLAN.md`

Required validation:

```bash
make eval-fast
```

Full graph validation:

```bash
make eval-full
```

Checkpoint rule:

- use `eval-fast` after normal code changes because it preserves the accuracy contracts while skipping only cloud/Kuzu,
- use `eval-full` before demo/release or after graph/Kuzu changes.

Known current finding:

- Kuzu build is useful for graph inspection but does not currently affect findings.
- JSON graph artifacts remain canonical.
- Slow paths are acceptable when they improve extraction, recall, precision, citations, or verification. Skipping Kuzu is not a statement that speed outranks accuracy.

Validation result:

```text
make eval-fast
  unit tests: 9 passed
  version gold: 5 findings, 5 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 7 findings, 4 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-kuzu
  version gold: 5 findings, 5 review_required
  Kuzu graph built
```

Runtime signal:

```text
checkpoint-version --no-kuzu: 1.488s
checkpoint-negative --no-kuzu: 1.451s
checkpoint-cross --no-kuzu: 0.775s
checkpoint-scanned --no-kuzu: 1.251s
checkpoint-kuzu with Kuzu: 27.588s
  build_kuzu_graph: 26.098s
```

## checkpoint-2026-05-25-rg-search

Purpose:

- add a deterministic search/debug layer over persisted review-map artifacts,
- keep search out of final finding authority,
- make reviewer/debug queries available without invoking cloud models,
- keep search as recall/debug support, not finding authority.

Changed:

- `search/review_map.jsonl` emitted on every review run,
- `interlock_mvp search RUN QUERY`,
- `examples/aes_glossary.yaml`,
- `make eval-search`,
- source-aware ranking so findings/diffs beat raw evidence when both match.

Validation result:

```text
make test
  11 passed

make eval-fast
  unit tests: 11 passed
  version gold: 5 findings, 5 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 7 findings, 4 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-search
  query: transformer rating
  top hits: finding -> diff -> claim/evidence
```

Known current finding:

- duplicate XFMR rating findings still exist in the graph output. They are visible in search and should be deduped in a later accuracy pass, not hidden in the search layer.

## checkpoint-2026-05-25-second-brain-search

Purpose:

- add a local persistent memory index for each run,
- support memory-palace/second-brain retrieval without adding finding authority,
- fuse exact `rg` hits with SQLite FTS hits.

Changed:

- `search/second_brain.sqlite` emitted on every run,
- search ranking now records retrieval method provenance,
- CLI search shows which retrieval path found the hit.

Validation result:

```text
make test
  11 passed

make eval-fast
  version gold: 5 findings, 5 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 7 findings, 4 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

  second_brain.sqlite: 514 records, 514 FTS rows

interlock_mvp search runs/checkpoint-version "transformer rating"
  top hits: finding -> diff -> claim/evidence
  retrieval methods: sqlite_fts + rg
```

Latest second-brain index sizes:

```text
checkpoint-version: 514 records
checkpoint-negative: 504 records
checkpoint-cross: 288 records
checkpoint-scanned: 54 records
```

Authority rule:

- The second brain is recall/debug infrastructure only.
- It may propose evidence to inspect later, but it cannot create findings.

## checkpoint-2026-05-25-expanded-examples

Purpose:

- add more real-life and near-real fixture coverage,
- catch reference-as-equipment false positives,
- document extractable vs weak-example classes.

Changed:

- references no longer become graph subjects for missing-equipment findings,
- `eval/synth_reference_smoke.yaml`,
- `eval/real_xfmr_smoke.yaml`,
- `make eval-examples`,
- `examples/REAL_LIFE_EXAMPLES.md`,
- eval supports `max_findings`.

Validation result:

```text
make test
  13 passed

make eval-fast
  version gold: 5 findings, 5 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 5 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-examples
  synth equipment spec v2/v3: 0 findings, eval passed
  real IEEE vs SEL: 17 findings, 1 review_required, eval passed under smoke cap
```

Accuracy finding:

- The real cross-doc example is now less noisy than before the reference fix, but still has repeated possible impedance findings.
- PID/HVAC/relay examples expose weak table/subject extraction and should drive the next table/VLM extraction phase.
- Gold cross-doc got cleaner after the reference fix: 7 findings / 4 review_required became 5 findings / 2 review_required while expected findings still pass.

## checkpoint-2026-05-25-precision-dedup

Purpose:

- improve precision without losing labeled recall,
- remove duplicate same-value mismatch findings,
- stop prose/tap/loss percentages from being classified as impedance unless `%Z` or explicit impedance context is present.

Changed:

- `docgraph` diff admission now filters impedance claims with weak `%` context,
- repeated same-value `rating`/`impedance`/`fault_current` diffs collapse,
- regression tests for percent-context admission and duplicate diff collapse.

Validation result:

```text
make test
  15 passed

make eval-fast
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 5 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-examples
  synth equipment spec v2/v3: 0 findings, eval passed
  real IEEE vs SEL: 3 findings, 1 review_required, eval passed under smoke cap
```

Accuracy result:

- Version gold kept all expected findings but removed the duplicate XFMR rating finding.
- Real IEEE/SEL smoke dropped from 17 findings to 3 findings by eliminating prose-percent noise.
- Remaining real IEEE/SEL findings still need review; two are possible impedance missing-items and one is equipment presence.

## checkpoint-2026-05-25-test-coverage-contracts

Purpose:

- strengthen tests around the accuracy contracts that can break a funding demo,
- make eval YAML assert cited evidence values/units/pages/quotes, not just top-level finding labels,
- prevent cross-document transformer specs from pairing to unrelated low-voltage or KVA-only lines,
- add an executable coverage gate.

Changed:

- eval matchers now support nested evidence assertions and `_in` matchers,
- cross-doc semantic fallback no longer treats every B-side claim as compatible with A-side `XFMR`,
- `primary_voltage` no longer aligns to generic `voltage`,
- transformer cross-doc fallback requires B evidence to be transformer-specific, not just KVA-bearing,
- verifier authored-language guard now catches banned terms followed by punctuation,
- added evidence-mining, verification, and end-to-end `run_review` tests,
- `make coverage` runs source coverage with `--fail-under=70`,
- package version bumped to `0.7.0`.

Validation result:

```text
make coverage
  30 passed
  source coverage: 73%

make eval-fast
  unit tests: 30 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-examples
  synth equipment spec v2/v3: 0 findings, eval passed
  real IEEE vs SEL: 3 findings, 1 review_required, eval passed

make eval-search
  query: transformer rating
  top hit: finding

make eval-kuzu
  version gold: 4 findings, 4 review_required
  Kuzu graph built without warning
```

Accuracy finding:

- The old cross-doc primary-voltage expectation was too weak and allowed A `12.47 kV` to pair with B `277 V`.
- The tightened contract forbids that citation class instead of pretending it is a valid high-confidence mismatch.
- Correct primary-voltage recall now requires better extraction/subject attribution, not a looser graph matcher.

## checkpoint-2026-05-25-reasoning-graph-slice

Purpose:

- start working the graph-modeling critique directly,
- stop treating every important review relation as a thin edge,
- add explicit reasoning decisions while preserving current `diff_graph.json` compatibility,
- make findings traceable to alignment/comparison/absence-search decisions.

Changed:

- added `AlignmentDecision`, `ComparisonDecision`, `AbsenceSearch`, and `ReasoningGraph` models,
- added `interlock_mvp/core/reasoning.py`,
- every current value mismatch / engineer-review finding now carries `alignment_id` and `comparison_id`,
- every current missing-item finding now carries `absence_id`,
- new canonical artifact: `reasoning_graph.json`,
- eval YAML can assert alignment/comparison/absence-search details,
- Kuzu mirrors reasoning decision nodes and finding-to-decision relations,
- search index includes alignment/comparison/absence-search records,
- `metrics.json` includes reasoning-health counters,
- `report.md` includes a compact "Review Reasoning Health" section,
- package version bumped to `0.8.0`.

Validation result:

```text
make coverage
  35 passed
  source coverage: 73%

make eval-fast
  unit tests: 35 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-examples
  synth equipment spec v2/v3: 0 findings, eval passed
  real IEEE vs SEL: 3 findings, 1 review_required, eval passed

make eval-search
  query: transformer rating
  top hit: finding

make eval-kuzu
  version gold: 4 findings, 4 review_required
  Kuzu graph built without warning

Kuzu decision-node sanity:
  AlignmentDecision: 3
  ComparisonDecision: 3
  AbsenceSearch: 1
```

Known limit:

- This is a compatibility-layer slice. Reasoning decisions are currently derived from `DiffEdge`; the next hardening step is to generate findings directly from `ComparisonDecision` and `AbsenceSearch`, then make rejected alternatives first-class at match time rather than reconstructed after the fact.
