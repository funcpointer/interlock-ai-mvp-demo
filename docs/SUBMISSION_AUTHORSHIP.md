# Authorship / Build Note

## What I Personally Built

- Fresh InterLock MVP repo and CLI-first review engine.
- Reusable `run_review(ReviewRequest) -> ReviewResult` core.
- PDF ingestion, text/block extraction, annotation extraction, crops, JSON artifacts, metrics, logs, report generation.
- Directional authority model for version and cross-document review.
- Evidence mining, document/reasoning graphs, unit/plausibility checks, cited findings.
- Eval harness, negative/scanned/demo fixtures, triage diagnostics.
- Static Vercel demo package and live Streamlit upload/review app.

## What I Reused

- Public AES transformer specification PDF.
- Existing fixture concepts and selected synthetic/gold expectations from prior InterLock work.
- OSS libraries: PyMuPDF, Pydantic, Typer, Rich, RapidFuzz, Pint, Kuzu, Jinja2, Pillow, Structlog, PyYAML, LanceDB, Streamlit.
- Public/synthetic demo PDFs bundled for repeatable review.

## What Broke

- Early cross-doc attempts over arbitrary public documents produced weak/noisy alignment.
- Scanned/low-text PDFs produced empty-looking results until coverage warnings were surfaced clearly.
- Fixed Streamlit run directories risked artifact reuse across sessions.
- Public repo polish initially included local machine paths in docs/Makefile.
- Broad scan/table/drawing support is not solved yet.

## How I Debugged It

- Added first-class metrics and JSONL stage logs from the start.
- Persisted every intermediate artifact: pages, regions, evidence, document graphs, diff graph, reasoning graph, decision traces, findings.
- Added triage diagnostics for generic subjects, weak contexts, absence-only findings, coverage gaps, and downgrade reasons.
- Added eval YAML for expected/forbidden findings and citation requirements.
- Ran coverage, doctor, public version eval, public cross-doc eval, negative eval, and scanned eval.
- Browser-smoked the live Streamlit deployment and static Vercel demo.
