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

Use `--no-kuzu` for fast evaluation/debug loops. Build Kuzu only for graph inspection checkpoints.

Search runs against persisted `search/review_map.jsonl` artifacts using `rg`, not against PDFs directly.
