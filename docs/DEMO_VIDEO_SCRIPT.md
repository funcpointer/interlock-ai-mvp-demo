# 2-5 Minute Demo Voice-Over Script

Target length: 3 to 4 minutes.

Open before recording:

- Streamlit app: `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`
- Source repo: `https://github.com/funcpointer/interlock-ai-mvp-demo`

Use the app defaults:

- cloud calls disabled,
- Kuzu disabled,
- preset public demos.

## 0:00-0:25 — Problem

On screen: Streamlit app landing view.

Voice-over:

> InterLock AI is a review assistant for engineering document packages. In energy infrastructure work, reviewers compare specifications, studies, drawings, standards, contracts, and checklists by hand. The problem is not that engineers lack judgment. The problem is that high-consequence mismatches hide across files, and they often surface late, when redesign is expensive.
>
> This MVP focuses on one wedge: cross-file discrepancy detection with citations. It does not replace an engineer. It gives the reviewer a shorter, more systematic list of evidence-backed items to inspect.

## 0:25-1:25 — Version Review Demo

On screen:

1. Choose `Public version demo`.
2. Keep cloud calls off.
3. Click `Run review`.
4. Wait for findings.

Voice-over:

> First I will run a version review. This compares a baseline engineering PDF against a revised PDF. In this mode, the revised document is treated as authoritative, but every finding still has to be cited back to source evidence.
>
> The bundled demo uses a real public AES transformer specification sheet and a watermarked synthetic revision. The synthetic revision is intentional: it gives us a controlled expected answer so we can evaluate whether the system finds the planted discrepancies without overclaiming.
>
> Here the system found two review-required findings. The first is a transformer rating mismatch: the baseline says 140 MVA, while the revised document says 120 MVA. The second is an impedance mismatch: 10 percent versus 8 percent.

On screen:

- Open the first finding.
- Point to subject, parameter, A value, B value.
- Point to page quote and crop.
- Open the second finding and do the same.

Voice-over:

> The important part is not just the number. Each flag has the subject, the parameter, the values on both sides, the authority direction, page numbers, quotes, bounding boxes, and a crop from the original PDF. That is the core product behavior: no citation, no finding.

## 1:25-2:20 — Cross-Document Review Demo

On screen:

1. Choose `Public cross-doc demo`.
2. Click `Run review`.
3. Show findings.

Voice-over:

> Now I will switch to cross-document review. This is closer to the broader InterLock thesis: compare different document types, not just two revisions of the same file.
>
> In this demo, the system compares the transformer specification against a synthetic protection-study excerpt. The values appear in a different document shape, but the reviewer still cares whether the assumptions agree.
>
> The authority model is explicit. For this demo configuration, a protection study ranks above a specification. If authority is unknown, the system should not overstate direction. It should route the item to engineer review.

On screen:

- Open a cross-doc finding.
- Show authority direction.
- Show quote/crop evidence from both documents.

Voice-over:

> This matters because a generic "A does not equal B" flag is not enough for engineering review. The reviewer needs to know which document is treated as controlling, why that authority decision was made, and where the evidence came from.

## 2:20-3:10 — Audit Trail And Artifacts

On screen:

1. Expand artifacts/debug section.
2. Show `findings.json`, `metrics.json`, `reasoning_graph.json`, and `decision_traces.json` if available.

Voice-over:

> Under the UI, the engine writes a full audit trail. The UI is only an adapter. The same core review function can be called from the CLI, an API, or a future production interface.
>
> The canonical outputs are JSON artifacts: findings, metrics, extracted evidence, document graphs, reasoning decisions, and decision traces. The markdown report, graph, search index, and UI are derived from those artifacts.
>
> This makes the system debuggable. If a finding is wrong, we can inspect whether the problem came from extraction, subject alignment, unit comparison, authority resolution, or final rendering.

## 3:10-3:45 — Limits And Why They Are Honest

On screen:

- Show note about scans/coverage warnings if available.
- Or keep findings visible and speak to limitations.

Voice-over:

> There are real limits. The public demo does not claim solved OCR or image-only drawing review. If a PDF page has too little extractable text, the system should produce a coverage warning instead of pretending it reviewed the page.
>
> The next accuracy lift is OCR, VLM extraction, table structure, and evaluation on private AES review packets. The MVP is intentionally conservative: cited high-confidence discrepancies first, broader document intelligence second.

## 3:45-4:00 — Close

On screen:

- Return to findings list or source repo.

Voice-over:

> The wedge is simple: turn a pile of engineering PDFs into a cited review map, flag mismatches that are expensive to miss, and give senior reviewers evidence they can inspect quickly. The platform path is broader review across studies, drawings, specs, standards, contracts, and checklists.

## Shorter 2-Minute Cut

Use this if the recording needs to be tighter:

1. Say the problem in 15 seconds.
2. Run only the version demo.
3. Show both findings and their citations.
4. Mention the cross-doc demo exists and uses the same engine.
5. Close with "no citation, no finding."

## One-Sentence Close

InterLock turns engineering PDFs into a cited review map, flags high-consequence mismatches, and gives senior reviewers evidence they can inspect instead of another uncited AI summary.
