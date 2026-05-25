# 2-5 Minute Demo Video Script

## Setup

Open:

- Streamlit app: `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`
- Source repo: `https://github.com/funcpointer/interlock-ai-mvp-demo`

Keep cloud calls disabled and Kuzu disabled.

## Script

1. State the problem.
   - Engineering reviewers compare specs, studies, drawings, standards, and checklists by hand.
   - InterLock flags verifiable mismatches with citations; it does not replace engineering judgment.

2. Run Public Version Demo.
   - Click `Public version demo`.
   - Click `Run review`.
   - Show 2 review-required findings.
   - Show rating mismatch: `140 MVA` in A vs `120 MVA` in B.
   - Show impedance mismatch: `10%` in A vs `8%` in B.
   - Point at page quotes and crop images.

3. Run Public Cross-Doc Demo.
   - Click `Public cross-doc demo`.
   - Click `Run review`.
   - Show same discrepancy class across a specification and a protection-study excerpt.
   - Point out authority: protection study ranks higher than specification in configured AES precedence.

4. Show artifacts.
   - Expand `Artifacts`.
   - Mention `findings.json`, `metrics.json`, `reasoning_graph.json`, and `decision_traces.json`.
   - Say every finding has evidence IDs and source citations.

5. Show honesty on limitations.
   - The system does not claim unreadable scans are reviewed.
   - Low-text/scanned pages become coverage warnings.
   - Next accuracy lift is OCR/VLM/table extraction on private AES packets.

6. Close.
   - The wedge is cited cross-file discrepancy detection.
   - The platform path is studies, drawings, specs, standards, contracts, and checklists.

## One-Sentence Close

InterLock turns a pile of engineering PDFs into a cited review map, flags high-consequence mismatches, and gives senior reviewers evidence they can inspect instead of another uncited AI summary.
