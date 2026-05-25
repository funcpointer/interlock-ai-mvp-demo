# Streamlit Dynamic App - 2026-05-25

Purpose: interactive demo surface for public presets and uploading two PDFs for a live review.

Run locally:

```bash
make streamlit
```

Entry point:

```text
streamlit_app.py
```

Behavior:

- supports two-PDF uploads,
- writes each review to a unique run directory to avoid cross-session artifact reuse,
- enforces an upload-size cap for the public demo host,
- supports `version` and `cross_doc` modes,
- defaults to no-cloud and no-Kuzu for predictable demo runs,
- calls the same `run_review(ReviewRequest)` core as the CLI and local UI,
- renders review findings separately from extraction coverage warnings,
- aggregates scanned/low-text coverage warnings so they do not look like 18 separate engineering discrepancies.

Hosted behavior:

- if public preset PDFs are present, the app shows public demo presets,
- if preset PDFs are absent, the app falls back to upload-only mode.

Deployment note:

- Vercel remains the static investor URL.
- Streamlit is the live upload/review URL once connected to a GitHub repo or another Streamlit-capable host.
- Do not expose arbitrary local-path input in a hosted app.

Known limitation:

- scanned/low-text PDFs still require OCR/VLM extraction to recover evidence. The current app correctly shows them as coverage warnings, not completed review findings.
