# InterLock AI MVP Submission Packet

## Links

- Live prototype: `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`
- Static read-only demo: `https://interlock-ai-mvp-demo.vercel.app`
- Source repo: `https://github.com/funcpointer/interlock-ai-mvp-demo`
- Demo video: TBD

## What To Review

- PRD: `docs/SUBMISSION_PRD.md`
- TDD: `docs/SUBMISSION_TDD.md`
- Demo voice-over script: `docs/DEMO_VIDEO_SCRIPT.md`
- Authorship/build note: `docs/SUBMISSION_AUTHORSHIP.md`

## Access Notes

No credentials are required for the default demo.

The Streamlit app includes two preset demos:

- version review: public AES transformer spec vs watermarked synthetic revision,
- cross-document review: public AES transformer spec vs watermarked synthetic protection-study excerpt.

Cloud calls are disabled by default. Kuzu graph generation is disabled by default in the live app to keep the demo fast. The upload flow can review two PDFs, but private or regulated documents should not be uploaded to the public demo URL.

## Requirement Coverage

| Requirement | MVP coverage |
|---|---|
| Ingest two engineering PDFs | Yes. Preset demos and upload flow. |
| Extract structured data | Yes. Pages, regions, annotations, evidence, claims, contexts, reasoning graph, findings, metrics. |
| Detect mismatches / gaps | Yes for cited parameter mismatches in the demo cases; coverage warnings for low-text pages. |
| Source citations | Yes. Every finding has page, quote, bbox, crop, and evidence IDs. |
| Messy PDFs | Mixed text/tables handled at MVP level. Scans are flagged as coverage gaps rather than overclaimed. |
| PRD/TDD/source/runnable artifact | Included. |

## Demo Claim

InterLock turns two engineering PDFs into a cited review map. It finds verifiable discrepancies, explains why evidence was paired, and gives senior reviewers traceable source crops instead of an uncited model answer.

The demo is intentionally conservative. It proves the review spine, citation gate, authority direction, unit-aware comparison, explainability graph, telemetry, and repeatable eval harness. It does not claim full production readiness across arbitrary scanned drawings or private AES project packets.
