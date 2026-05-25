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

## checkpoint-2026-05-25-decision-sourced-findings

Purpose:

- move the active finding path closer to expert-review flow,
- make `ComparisonDecision` and `AbsenceSearch` the source of non-coverage findings,
- keep `DiffEdge` as compatibility/debug context instead of the primary finding iterator.

Changed:

- added `findings_from_reasoning_graph`,
- `run_review` now verifies findings by iterating `reasoning_graph.comparisons` and `reasoning_graph.absence_searches`,
- coverage warnings remain sourced from coverage diff edges because they are extraction-health findings, not engineering comparisons,
- verifier metrics now include `comparison_sourced_findings`, `absence_sourced_findings`, and `coverage_edge_sourced_findings`,
- integration tests pin decision-sourced finding counts,
- package version bumped to `0.9.0`.

Validation result:

```text
make coverage
  36 passed
  source coverage: 73%

make eval-fast
  unit tests: 36 passed during target run
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

checkpoint-version decision-source metrics:
  comparison_sourced_findings: 3
  absence_sourced_findings: 1
  coverage_edge_sourced_findings: 0
```

Known limit:

- `ComparisonDecision` and `AbsenceSearch` are still derived after `DiffEdge` construction. Next step: capture rejected alternatives during matching/search itself, then make `DiffEdge` a pure projection from decisions.

## checkpoint-2026-05-25-aes-corpus-intake

Purpose:

- make AES/private partner docs a repeatable corpus input instead of ad hoc CLI runs,
- keep private PDFs, notes, and marked-up documents out of git,
- let every partner pair carry mode, authority config, doc type overrides, eval contract, and cost/cloud policy,
- reuse the same `run_review(request)` core path that future API/UI adapters will call.

Changed:

- added `interlock_mvp corpus MANIFEST`,
- added `interlock_mvp/core/corpus.py`,
- added `corpora/aes/manifest.example.yaml` for private partner docs,
- added `corpora/aes/near_real_seed.yaml` as a non-private bridge corpus over existing fixture/public PDFs,
- added `make eval-aes-corpus` and `make eval-aes-seed`,
- gitignored `corpora/aes/local_manifest.yaml`, `corpora/aes/docs/`, and local PDFs,
- package version bumped to `0.10.0`.

Local data inventory:

- no private AES PDF bundle was found by filename under the searched local document roots,
- existing near-real documents were found in the previous InterLock repos and recorded in `corpora/aes/README.md`,
- the private intake path is now explicit: copy `manifest.example.yaml` to `local_manifest.yaml`, add AES paths, run `make eval-aes-corpus`.

Validation result:

```text
tests/test_corpus.py
  3 passed

make coverage
  40 passed
  source coverage: 74%

make eval-aes-seed
  seeded_version_doc_a_60_doc_b_90: eval_passed, 4 findings, 4 review_required
  seeded_negative_same_study: eval_passed, 0 findings, 0 review_required
  seeded_cross_spec_vs_study: eval_passed, 4 findings, 2 review_required
  seeded_real_xfmr_vendor_cross: eval_passed, 3 findings, 1 review_required

make eval-aes-corpus
  skipped cleanly because corpora/aes/local_manifest.yaml does not exist yet

make eval-fast
  unit tests: 39 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed
```

Known limit:

- the seed corpus is not AES-private data. It is a coverage bridge. Real accuracy work now depends on dropping partner PDFs/notes into `corpora/aes/docs/` or referencing absolute paths from `corpora/aes/local_manifest.yaml`.

## checkpoint-2026-05-25-lancedb-search

Purpose:

- bring LanceDB into the MVP as a derived retrieval store,
- keep LanceDB out of finding authority until embeddings/search prove useful on real AES corpora,
- preserve `rg` and SQLite FTS as independent retrieval paths,
- make every search hit carry retrieval-method provenance.

Changed:

- added `lancedb` dependency,
- `write_search_index` now writes:
  - `search/review_map.jsonl`
  - `search/second_brain.sqlite`
  - `search/lancedb/`
  - `search/lancedb_meta.json`
- `search_run` now fuses `sqlite_fts`, `lancedb`, and `rg` hits,
- LanceDB records use `deterministic_hash_v1` local embeddings with `vector_dim=128`,
- CLI `doctor` checks `lancedb`,
- package version bumped to `0.11.0`.

Validation result:

```text
tests/test_search.py tests/test_review_integration.py
  3 passed

make coverage
  40 passed
  source coverage: 74%

make eval-fast
  unit tests: 40 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-search
  top transformer-rating hits include retrieval_methods:
    sqlite_fts + lancedb + rg

make eval-aes-seed
  4/4 corpus pairs eval_passed with LanceDB artifacts written
```

Known limit:

- `deterministic_hash_v1` is only a local lexical-vector bootstrap. It proves the LanceDB artifact path and fusion logic. It is not a substitute for real embeddings from a local SLM/Ollama model or cloud model.

## checkpoint-2026-05-25-review-wiki

Purpose:

- align the MVP memory architecture with the Karpathy LLM Wiki pattern without making the wiki authoritative,
- give future reviewers and model calls a stable Markdown synthesis layer before they search JSON, crops, or source PDFs,
- keep raw PDFs and JSON artifacts as source of truth while adding a browsable compiled-memory layer.

Research note:

- Karpathy's LLM Wiki pattern separates immutable raw sources, an LLM-maintained interlinked Markdown wiki, and a schema/workflow file.
- Our system already had raw PDFs, canonical JSON, Kuzu, SQLite FTS, LanceDB, and `rg`.
- Missing piece: a Markdown wiki layer that compiles the review map into pages with links, summaries, and reasoning traces.

Changed:

- added `interlock_mvp/core/wiki.py`,
- every review now writes:
  - `wiki/index.md`
  - `wiki/log.md`
  - `wiki/review-map.md`
  - `wiki/documents/*.md`
  - `wiki/subjects/*.md`
  - `wiki/findings/*.md`
  - `wiki/reasoning/decisions.md`
- `metrics.json` now includes `wiki_pages`,
- integration test pins wiki artifact contract and finding decision links,
- package version bumped to `0.12.0`.

Validation result:

```text
tests/test_review_integration.py
  1 passed

make coverage
  40 passed
  source coverage: 75%

make eval-fast
  unit tests: 40 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed
```

Known limit:

- the wiki is deterministic and derived today. It does not yet perform LLM-maintained synthesis across multiple runs or update persistent AES domain pages. That should come after real AES corpus intake, because the wiki schema should be shaped by partner documents, not by synthetic fixtures.

## checkpoint-2026-05-25-context-memory

Purpose:

- move memory-palace and second-brain concepts into the context layer itself,
- stop treating context as only a pairing label,
- make review locations navigable as rooms and finding paths navigable as trails,
- feed context rooms/trails into the existing second-brain search stack.

Changed:

- added `ContextRoom`, `ContextTrail`, and `ContextMemory` models,
- added `interlock_mvp/core/context_memory.py`,
- every review now writes `context_memory.json`,
- every review now emits wiki context-room pages under `wiki/context-rooms/`,
- every review now emits `wiki/memory-palace.md`,
- `write_search_index` now indexes `context_room` and `context_trail` records into:
  - `search/review_map.jsonl`,
  - `search/second_brain.sqlite`,
  - `search/lancedb/`,
  - `rg`-searchable JSONL,
- metrics now include context rooms/trails/salience counters,
- package version bumped to `0.13.0`.

Current shape:

- **Room:** one document context such as TCC, table row, spec section, or page-level fallback.
- **Neighbor:** previous/next room in document order.
- **Trail:** a finding-centered path connecting cited evidence through rooms.
- **Second-brain record:** searchable room/trail record fused with existing evidence/claim/finding records.

Validation result:

```text
tests/test_context_memory.py tests/test_review_integration.py tests/test_search.py
  5 passed

make coverage
  41 passed
  source coverage: 76%

make eval-fast
  unit tests: 41 passed during target run
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make eval-search
  passed; context_room records are searchable through sqlite_fts + lancedb + rg

make eval-aes-seed
  4/4 corpus pairs eval_passed
```

Checkpoint-version context-memory signal:

```text
rooms: 85
trails: 4
rooms with findings: 6
top rooms:
  room_a_selective_coordination_studies salience=73
  room_b_selective_coordination_studies salience=63
  room_b_tcc3 salience=47
```

Known limit:

- rooms are currently derived from existing context segmentation. If context segmentation is weak, the memory palace mirrors that weakness. Next accuracy step is better context extraction from real AES documents, not more retrieval infrastructure.

## checkpoint-2026-05-25-mvp-audit

Purpose:

- iterate through every source file, top-level function family, CLI path, and runtime artifact from a funding-demo MVP perspective,
- run the near-real validation suite again after the context-memory/search/wiki/LanceDB additions,
- document what is right for the MVP, what is merely derived infrastructure, and what still limits accuracy,
- patch any correctness issue found during the audit before checkpointing.

Changed:

- added `docs/MVP_AUDIT_2026-05-25.md`,
- patched `build_context_memory` so scanned/low-text coverage warnings get page-specific rooms instead of collapsing into one document room,
- added a regression test proving coverage-warning rooms link back to their findings and trails,
- package version bumped to `0.14.0`.

Validation result:

```text
make eval-full
  unit tests passed
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 4 findings, 2 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed
  search/examples/Kuzu paths passed

make coverage
  42 passed
  source coverage: 76%

make eval-fast
  version / negative / cross-doc / scanned evals passed

make eval-aes-seed
  4/4 corpus pairs eval_passed
```

Audit verdict:

- the architecture is coherent enough to keep building,
- `run_review(ReviewRequest) -> ReviewResult`, JSON-as-truth, directional authority, cited findings, deterministic verification, eval YAML, and derived search/wiki/graph/memory are the correct MVP boundaries,
- the main accuracy risk is extraction and context segmentation, not graph/search/storage,
- no P0 issues remain in the current MVP contracts.

P1 next work:

- add OCR/VLM/table extraction against real AES documents where PyMuPDF text extraction fails,
- improve context segmentation from real page/table/section structure,
- keep candidate generation auxiliary until decision-sourced matching is fully primary.

## checkpoint-2026-05-25-domain-dictionary

Purpose:

- prioritize the next MVP work after the audit,
- move AES glossary/dictionary data from search-only support into the extraction/reasoning input path,
- improve recall for partner vocabulary without turning glossary aliases into an authority source,
- document the next ordered work queue.

Changed:

- added `interlock_mvp/core/domain.py`,
- expanded `examples/aes_glossary.yaml` into:
  - equipment terms,
  - parameter terms,
  - context terms,
  - standards/reference terms,
  - legacy search aliases,
- added `ReviewRequest.domain_glossary_path`,
- added CLI/corpus `--glossary` support,
- wired `DomainDictionary` into:
  - subject extraction,
  - parameter canonicalization,
  - context labeling,
  - corpus manifests,
  - search query expansion,
- added `tests/test_domain_dictionary.py`,
- added `docs/NEXT_STEPS_2026-05-25.md`,
- package version bumped to `0.15.0`.

Important regression caught:

- first dictionary implementation over-admitted `XFMR 12 x FLA` as a concrete equipment tag `XFMR-12`,
- this inflated version-review findings from 4 to 8/10 and broke gold alignments,
- fix: acronym prefixes such as `XFMR` require compact/hyphen/hash-style IDs and do not treat plain row text as equipment identity,
- natural prefixes such as `Switchboard SB-1` remain supported.

Validation result:

```text
tests/test_domain_dictionary.py tests/test_evidence.py tests/test_search.py tests/test_review_integration.py
  12 passed

make eval-fast
  46 tests passed
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 6 findings, 4 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make coverage
  46 passed
  source coverage: 77%

make eval-aes-seed
  4/4 corpus pairs eval_passed

make eval-search
  passed
```

Priority queue after this checkpoint:

1. keep the authoritative review spine singular by demoting/removing stale candidate-verifier surfaces,
2. add `decision_traces.json` / signal corroboration for explainability,
3. run real AES corpus manifests and add eval YAML for each pair,
4. add OCR/VLM/table extraction only where telemetry proves deterministic extraction failed,
5. replace LanceDB hash vectors with local Ollama/SLM embeddings only after real corpus recall demands it.

## checkpoint-2026-05-25-singular-spine

Purpose:

- remove the stale candidate-generation path,
- make the reasoning graph the single authoritative source for findings,
- add finding-level signal corroboration and explainability,
- reduce misleading cloud/LLM surface until a real reasoning-level verifier exists.

Changed:

- deleted `interlock_mvp/core/candidates.py`,
- removed `CandidateFinding`,
- stopped generating `candidates.json`,
- removed `max_candidates` / `--max-candidates` from active commands and Makefile targets,
- removed unused candidate-verifier and diff-graph-verifier paths from `verification.py`,
- added `DecisionSignal` and `DecisionTrace` models,
- added `interlock_mvp/core/decision_traces.py`,
- every review now writes `decision_traces.json`,
- metrics now include:
  - `decision_traces`,
  - `decision_traces_with_downgrades`,
- `cloud reasoning verifier not implemented; deterministic verifier used` is now explicit when a key exists but no cloud reasoning verifier is wired,
- removed `anthropic` from required dependencies/doctor checks until cloud verification is implemented,
- package version bumped to `0.16.0`.

Current authoritative spine:

```text
PDF
  -> extraction
  -> evidence
  -> document graph
  -> diff graph
  -> reasoning graph
  -> findings
  -> decision traces
```

Decision trace contents:

- citation signal,
- authority signal,
- diff-edge signal,
- alignment signal,
- comparison or absence-search signal,
- rejected alternatives,
- downgrade reasons.

Validation result:

```text
tests/test_review_integration.py tests/test_verification.py tests/test_corpus.py
  9 passed

make eval-fast
  46 tests passed
  version gold: 4 findings, 4 review_required, eval passed
  negative: 0 findings, 0 review_required, eval passed
  cross-doc: 6 findings, 4 review_required, eval passed
  scanned: 18 coverage warnings, 0 review_required, eval passed

make coverage
  46 passed
  source coverage: 82%

make eval-aes-seed
  4/4 corpus pairs eval_passed
```

Known limits:

- decision traces are deterministic ledger records, not independent model verification,
- `contradicting_signals` is present but currently empty until OCR/VLM/table channels create real cross-system contradictions,
- Kuzu/wiki/search do not yet mirror `decision_traces.json`; JSON remains canonical.

Next:

1. run real AES corpus manifests and inspect decision traces on misses/noise,
2. add OCR/VLM/table extraction where telemetry proves recall gaps,
3. add real local embeddings only after search recall needs it.

## checkpoint-2026-05-25-triage-public-aes

Purpose:

- turn run metrics and decision traces into an executable diagnostic surface,
- use public AES/AES Indiana PDFs as a local, non-private stress corpus,
- make the next accuracy work evidence-driven instead of infrastructure-driven.

Changed:

- added `TriageIssue` and `RunTriage` models,
- added `interlock_mvp/core/triage.py`,
- added `interlock_mvp triage RUN_DIR`,
- `triage` writes `triage.json` into the run directory,
- added tests for:
  - weak/empty text-layer pages,
  - document-level context fallback,
  - generic subjects,
  - absence-only reviews,
  - zero comparison decisions,
  - missing decision traces,
- added `make eval-triage`,
- documented public AES smoke PDFs in `corpora/aes/README.md`,
- package version bumped to `0.17.0`.

Public AES files downloaded locally under gitignored `corpora/aes/docs/public_aes/`:

- AES Indiana DER interconnection standard,
- AES Indiana Goldbook complete service and meter manual,
- AES Clean Energy Somerset main power transformer specification sheet,
- AES Clean Energy Somerset electrical design drawings part 1.

Validation result:

```text
tests/test_triage.py
  3 passed

make test
  49 passed

checkpoint triage:
  checkpoint-version: generic subjects + one absence-only finding
  checkpoint-cross: generic subjects + absence-only findings + downgraded decisions
  checkpoint-scanned: weak extraction pages + document context + downgraded coverage warnings
  example-real-xfmr-cross: absence-only review, zero comparisons

make eval-aes-corpus
  public_aes_der_standard_vs_goldbook: completed, 33 findings, 0 review_required, 30 coverage warnings
  public_aes_der_standard_vs_transformer_spec_sheet: completed, 19 findings, 0 review_required, 16 coverage warnings
```

Accuracy finding:

- Public AES runs confirm the same wall as the public/vendor cross-doc smoke:
  extraction finds many values, but subject/context attachment is weak enough
  that the reasoning graph creates absence-search findings rather than accepted
  alignments and value comparisons.
- The next accuracy work is not another storage/search layer. It is table/section
  context extraction, subject attachment, and targeted OCR/VLM for weak pages.

Operational finding:

- The full Somerset drawing package can dominate runtime. Keep it available for
  targeted extraction tests, but do not put it in the default local smoke
  manifest until a bounded page-range/intake mode exists.

## checkpoint-2026-05-25-transformer-spec-context

Purpose:

- improve real spec-sheet extraction without adding another infrastructure layer,
- attach table values to the main equipment when the document is clearly a
  transformer datasheet/specification sheet,
- make section context classify ambiguous percent rows correctly.

Changed:

- added public-spec context patterns:
  - `Main Power Transformer Specification Sheet`,
  - `Project Specific Information`,
  - `Transformer Electrical Ratings`,
  - `Capacity Ratings`,
  - `Voltage Ratings`,
  - `Impedance Information`,
  - `On-Load Tap Changer`,
  - `Bushings`,
- added cautious cross-page context carry for equipment/spec tables only,
- added main-equipment subject attachment for generic parameter values inside
  transformer spec contexts,
- added context-aware parameter correction: percent rows under
  `Impedance Information` become `impedance`,
- fixed the old `%` classifier bug where any `z` in text made a percent row
  look like impedance (`Step Size: 0.625%` now stays `percent`),
- package version bumped to `0.18.0`.

Validation result:

```text
tests/test_docgraph.py tests/test_evidence.py
  16 passed

make eval-aes-corpus
  public_aes_der_standard_vs_goldbook: completed
  public_aes_der_standard_vs_transformer_spec_sheet: completed

make eval-triage
  52 tests passed
  version/cross/negative/scanned evals passed

make coverage
  52 passed
  source coverage: 82%
```

Public AES artifact improvement:

```text
Before:
  B transformer-spec values on pages 4/5 were mostly subject=GENERAL.
  "Step Size: 0.625%" was misclassified as impedance because "size" contains "z".

After:
  ev00100 "Primary - Secondary (ONAF): 10%" =>
    subject=XFMR
    parameter=impedance
    context=B:impedance_information

  ev00109 "Step Size: 0.625%" =>
    subject=GENERAL
    parameter=percent
    context=B:tap_changer
```

Accuracy finding:

- This improves the document graph for real transformer specification sheets.
- It does not yet make the public DER-standard-vs-transformer-spec pair produce
  value comparisons, because that pair is not a true paired revision/cross-doc
  project set. The next demo-quality data step is a real paired transformer
  spec/drawing/study pair or a bounded synthetic mutation of a public AES spec
  sheet with explicit gold.

## checkpoint-2026-05-25-public-demo-synth

Purpose:

- create a demo-quality paired case over a real public AES PDF,
- keep the mutation explicitly synthetic and watermarked,
- prove the MVP can emit cited directional version-review findings with eval and
  triage around the same artifact.

Changed:

- added `scripts/make_synthetic_transformer_revision.py`,
- added `corpora/aes/public_demo_manifest.yaml`,
- added `eval/public_transformer_spec_synth.yaml`,
- added `make eval-public-demo`,
- fixed impedance diff admission so `%` rows under an
  `impedance_information` context do not need the word `impedance` repeated in
  the row text,
- made primary/secondary/high/low winding voltage rows directional parameters,
- synthetic demo now plants two changes:
  - `84/112/140 MVA` -> `84/112/120 MVA`,
  - `10% (+/- allowed tolerance)` -> `8% (+/- allowed tolerance)`,
- package version bumped to `0.19.0`.

Validation result:

```text
make eval-public-demo
  public_transformer_spec_synthetic_revision: eval_passed
  findings: 2
  review_required: 2
  coverage warnings: 0

demo run metrics:
  alignment_decisions: 2
  comparison_decisions: 2
  absence_searches: 0
  decision_traces_with_downgrades: 0
```

Expected findings:

- rating mismatch: A cites `84/112/140 MVA`; B cites `84/112/120 MVA`,
- impedance mismatch: A cites `Primary - Secondary (ONAF): 10%`; B cites
  `8% (+/- allowed tolerance)`.

Forbidden findings:

- voltage mismatch,
- missing item,
- coverage warning,
- tap step size / `0.625%` as a finding.

Demo note:

- This is not claimed as a real AES revision. It is a real public AES source PDF
  plus a generated, watermarked synthetic revision that creates controlled,
  auditable mismatches for the funding demo.
