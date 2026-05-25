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
