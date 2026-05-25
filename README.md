# InterLock MVP

Fresh CLI-only evidence review engine for comparing two engineering PDFs.

```bash
/Users/kc/venv-12/bin/python -m interlock_mvp doctor
/Users/kc/venv-12/bin/python -m interlock_mvp review A.pdf B.pdf --mode version --out runs/demo --no-cloud --no-kuzu
/Users/kc/venv-12/bin/python -m interlock_mvp check runs/demo --eval eval/demo.yaml
/Users/kc/venv-12/bin/python -m interlock_mvp search runs/demo "transformer rating"
```

The CLI is only an adapter. The reusable entrypoint is:

```python
from interlock_mvp.core.review import run_review
from interlock_mvp.core.models import ReviewRequest

result = run_review(ReviewRequest(...))
```

Canonical outputs are JSON artifacts. `report.md` and `graph.kuzu/` are derived.

Important review-map artifacts:

- `doc_graph_a.json` / `doc_graph_b.json`: contexts, subjects, claims.
- `diff_graph.json`: compatibility view of mismatches and missing items.
- `reasoning_graph.json`: alignment, comparison, and absence-search decisions explaining why findings were created.
- `findings.json`: reviewer-facing cited findings with decision IDs back into the reasoning graph.

Use `--no-kuzu` when Kuzu is not part of the question being tested. Kuzu is derived from JSON today; skipping it does not skip finding logic.

Search runs against persisted `search/review_map.jsonl` and `search/second_brain.sqlite` artifacts, not against PDFs directly.
