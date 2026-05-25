# Authorship / Build Note

## What I Personally Built

- Fresh InterLock MVP repo and CLI-first review engine.
- Shared `run_review(ReviewRequest) -> ReviewResult` core used by CLI and Streamlit.
- PDF ingestion, block extraction, annotations, crops, evidence mining, document graphs, reasoning graph, findings, metrics, logs, and reports.
- Directional authority for version and cross-document review.
- Unit/plausibility checks, citation-gated findings, explainability graph, eval harness, triage diagnostics, and live Streamlit demo.

## What I Reused

- Public AES transformer specification PDF.
- Watermarked synthetic demo revisions/excerpts so expected discrepancies are known.
- Selected fixture concepts from prior InterLock work.
- OSS libraries: PyMuPDF, Pydantic, Typer, Rich, RapidFuzz, Pint, Kuzu, Jinja2, Pillow, Structlog, PyYAML, LanceDB, Streamlit, OpenAI SDK.

## What Broke

- Early arbitrary cross-doc runs were noisy without paired project context.
- Low-text/scanned PDFs looked empty until coverage warnings were made explicit.
- Initial context/explainability UI repeated citation evidence instead of explaining the pairing.
- Full OCR/VLM and robust drawing/table understanding remain out of MVP scope.

## How I Debugged It

- Persisted every intermediate artifact for inspection.
- Added metrics and stage logs from the start.
- Added eval YAML for expected and forbidden findings.
- Added triage diagnostics for extraction, context, subject resolution, and reasoning risks.
- Browser-tested the Streamlit demo and ran public version/cross-doc evals before checkpointing.
