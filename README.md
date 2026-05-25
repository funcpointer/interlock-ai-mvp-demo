# InterLock MVP

CLI-first evidence review engine for comparing two engineering PDFs.

## Submission Materials

- Submission packet: `docs/SUBMISSION_PACKET.md`
- PRD: `docs/SUBMISSION_PRD.md`
- TDD: `docs/SUBMISSION_TDD.md`
- Authorship/build note: `docs/SUBMISSION_AUTHORSHIP.md`
- Demo video script: `docs/DEMO_VIDEO_SCRIPT.md`
- Live Streamlit app: `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`
- Static read-only demo: `https://interlock-ai-mvp-demo.vercel.app`

```bash
python -m interlock_mvp doctor
python -m interlock_mvp review A.pdf B.pdf --mode version --out runs/demo --no-cloud --no-kuzu
python -m interlock_mvp check runs/demo --eval eval/demo.yaml
python -m interlock_mvp triage runs/demo
python -m interlock_mvp search runs/demo "transformer rating"
python -m interlock_mvp corpus corpora/aes/local_manifest.yaml --out-root runs/aes-corpus --no-cloud --no-kuzu
make eval-public-demo
make eval-public-cross-doc-demo
make eval-demo-package
make ui
make streamlit
```

Local development with a specific interpreter:

```bash
make PY=/path/to/python test
python -m interlock_mvp review A.pdf B.pdf --env-file .env.local --no-kuzu
```

The CLI is only an adapter. The reusable entrypoint is:

```python
from interlock_mvp.core.review import run_review
from interlock_mvp.core.models import ReviewRequest

result = run_review(ReviewRequest(...))
```

Canonical outputs are JSON artifacts. `report.md`, `graph.kuzu/`, and search indexes are derived.

The local browser UI is also only an adapter over the same core:

```bash
make ui
```

Open `http://127.0.0.1:8765` and run either the public version demo, the public
cross-doc demo, or a custom two-PDF review by local file path.

For a URL you can safely share externally, generate the static demo package:

```bash
make eval-demo-package
```

Deploy `runs/demo-package/site/` as a static site. This is the recommended VC
sharing surface because it has no run button, no local path inputs, no server
execution, and no access to files outside the exported artifacts.

Current deployed VC demo:

```text
https://interlock-ai-mvp-demo.vercel.app
```

For a dynamic upload/review app, use Streamlit:

```bash
make streamlit
```

The Streamlit app supports preset demos and two-PDF uploads. It is the right
surface for a live interactive demo. The static Vercel site remains the
lowest-risk read-only VC URL.

Details:

- `docs/STREAMLIT_DYNAMIC_APP_2026-05-25.md`
- `docs/STREAMLIT_CLOUD_DEPLOYMENT_2026-05-25.md`

Streamlit Cloud deployment settings:

- branch: `main`
- main file path: `streamlit_app.py`
- Python: `3.12`
- secrets: none required for the default no-cloud demo

The AES/domain glossary is loaded from `examples/aes_glossary.yaml` by default.
It now feeds extraction, parameter naming, context labeling, corpus runs, and
search expansion. It is still an MVP glossary, not a complete AES ontology.

Important review-map artifacts:

- `doc_graph_a.json` / `doc_graph_b.json`: contexts, subjects, claims.
- `diff_graph.json`: compatibility/debug view of mismatches and missing items.
- `reasoning_graph.json`: alignment, comparison, and absence-search decisions explaining why findings were created.
- `decision_traces.json`: finding-level signal ledger: citations, authority, alignment, comparison/absence logic, rejected alternatives, and downgrade reasons.
- `triage.json`: optional diagnostic artifact written by `interlock_mvp triage`; flags extraction, context, subject-resolution, reasoning, and explainability risks.
- `context_memory.json`: memory-palace rooms/trails derived from contexts, claims, evidence, and findings.
- `findings.json`: reviewer-facing cited findings emitted from reasoning decisions, with decision IDs back into the reasoning graph.
- `wiki/`: derived Markdown review wiki with index, log, memory palace, document pages, context-room pages, subject pages, finding pages, and reasoning-decision pages.

Use `--no-kuzu` when Kuzu is not part of the question being tested. Kuzu is derived from JSON today; skipping it does not skip finding logic.

Search runs against persisted `search/review_map.jsonl`, `search/second_brain.sqlite`, and `search/lancedb/` artifacts, not against PDFs directly. Context rooms and trails are indexed there too. LanceDB is currently fed by deterministic local hash embeddings so it is a retrieval/debug aid, not finding authority.

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

For the funding-demo-oriented public AES synthetic revision, run:

```bash
make eval-public-demo
```

That target regenerates a watermarked synthetic revision of the public AES
Somerset main power transformer specification sheet, runs the version review,
checks `eval/public_transformer_spec_synth.yaml`, and writes triage diagnostics.
The planted changes are `140 MVA -> 120 MVA` and `10% impedance -> 8%`.

For the funding-demo-oriented public AES synthetic cross-document pair, run:

```bash
make eval-public-cross-doc-demo
```

That target compares the same real public AES transformer specification sheet
against a watermarked synthetic protection-study excerpt. The planted
cross-document discrepancies are the same rating and impedance changes, but
expressed in a different document type.

Demo and cross-document status notes:

- `docs/DEMO_WALKTHROUGH_2026-05-25.md`
- `docs/CROSS_DOC_STATUS_2026-05-25.md`

Corpus runs write one child run directory per pair and a summary artifact at
`runs/<corpus>/corpus_results.json`.

Public AES smoke data can be placed under `corpora/aes/docs/public_aes/`. This
folder is gitignored. The current local smoke set uses public AES Indiana DER /
Goldbook documents and AES Clean Energy Somerset transformer/drawing documents
only to stress extraction and triage. It is not a substitute for private AES
project review packets with gold expectations.
