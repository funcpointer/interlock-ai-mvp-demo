# InterLock AI MVP Submission Packet

## Demo Video

Recording link: TBD.

Suggested recording flow: use `docs/DEMO_VIDEO_SCRIPT.md`. Target length: 3 minutes.

## Working Prototype

- Live Streamlit app: `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`
- Static read-only demo: `https://interlock-ai-mvp-demo.vercel.app`
- Source repo: `https://github.com/funcpointer/interlock-ai-mvp-demo`

## Access Notes

No credentials are required for the default demo.

The Streamlit app defaults to:

- cloud calls disabled,
- Kuzu graph disabled,
- public/synthetic demo PDFs bundled in the repo.

The upload flow accepts two PDFs and runs the same review engine. Uploaded files are processed only for that run. Do not upload private or regulated documents to the public demo URL.

## Required Documents

- PRD: `docs/SUBMISSION_PRD.md`
- TDD: `docs/SUBMISSION_TDD.md`
- Authorship/build note: `docs/SUBMISSION_AUTHORSHIP.md`
- Demo script: `docs/DEMO_VIDEO_SCRIPT.md`

## Requirement Coverage

| Requirement | Current MVP coverage |
|---|---|
| Ingest at least two engineering PDFs | Yes. Upload flow supports arbitrary two-PDF review. Bundled validation uses a real public AES transformer spec plus watermarked synthetic revision/protection-study PDFs so the expected discrepancies are known. |
| Extract structured data | Yes. Pages, regions, annotations, evidence, claims, contexts, reasoning graph, findings, metrics. |
| Detect mismatches / conflicts / gaps | Yes for parameter mismatches in demo cases; controlled scan and negative cases are eval-checked. |
| Source citations for every flag | Yes. Findings include page, quote, bbox, and crop path. |
| Messy PDFs including scans/tables/mixed layouts | Tables/mixed text handled at MVP level through PyMuPDF blocks and crops. Scans are handled honestly as coverage warnings, not false findings. OCR/VLM is the next accuracy lift. |
| PRD and TDD | Included. |
| Runnable artifact and source | Included. |
