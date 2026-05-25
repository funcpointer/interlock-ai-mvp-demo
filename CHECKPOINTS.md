# InterLock MVP Checkpoints

## checkpoint-2026-05-25-telemetry-fast-eval

Purpose:

- make telemetry the default debugging surface,
- make Kuzu optional for fast loops,
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

- use `eval-fast` after normal code changes,
- use `eval-full` before demo/release or after graph/Kuzu changes.

Known current finding:

- Kuzu build is useful for graph inspection but too slow for inner-loop debugging.
- JSON graph artifacts remain canonical.

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
- make reviewer/debug queries fast without invoking cloud models.

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
