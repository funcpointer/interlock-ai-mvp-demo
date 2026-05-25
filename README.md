# InterLock MVP

Fresh CLI-only evidence review engine for comparing two engineering PDFs.

```bash
/Users/kc/venv-12/bin/python -m interlock_mvp doctor
/Users/kc/venv-12/bin/python -m interlock_mvp review A.pdf B.pdf --mode version --out runs/demo --no-cloud --no-kuzu
/Users/kc/venv-12/bin/python -m interlock_mvp check runs/demo --eval eval/demo.yaml
/Users/kc/venv-12/bin/python -m interlock_mvp search runs/demo "transformer rating"
/Users/kc/venv-12/bin/python -m interlock_mvp corpus corpora/aes/local_manifest.yaml --out-root runs/aes-corpus --no-cloud --no-kuzu
```

The CLI is only an adapter. The reusable entrypoint is:

```python
from interlock_mvp.core.review import run_review
from interlock_mvp.core.models import ReviewRequest

result = run_review(ReviewRequest(...))
```

Canonical outputs are JSON artifacts. `report.md`, `graph.kuzu/`, and search indexes are derived.

Important review-map artifacts:

- `doc_graph_a.json` / `doc_graph_b.json`: contexts, subjects, claims.
- `diff_graph.json`: compatibility/debug view of mismatches and missing items.
- `reasoning_graph.json`: alignment, comparison, and absence-search decisions explaining why findings were created.
- `findings.json`: reviewer-facing cited findings emitted from reasoning decisions, with decision IDs back into the reasoning graph.
- `wiki/`: derived Markdown review wiki with index, log, document pages, subject pages, finding pages, and reasoning-decision pages.

Use `--no-kuzu` when Kuzu is not part of the question being tested. Kuzu is derived from JSON today; skipping it does not skip finding logic.

Search runs against persisted `search/review_map.jsonl`, `search/second_brain.sqlite`, and `search/lancedb/` artifacts, not against PDFs directly. LanceDB is currently fed by deterministic local hash embeddings so it is a retrieval/debug aid, not finding authority.

## AES Corpus Intake

Private partner docs are loaded through `corpora/aes/local_manifest.yaml`, which is
gitignored. Copy `corpora/aes/manifest.example.yaml`, point it at AES PDFs or
notes, then run:

```bash
make eval-aes-corpus
```

For a non-private bridge corpus assembled from existing fixtures and public/vendor
PDFs, run:

```bash
make eval-aes-seed
```

Corpus runs write one child run directory per pair and a summary artifact at
`runs/<corpus>/corpus_results.json`.
