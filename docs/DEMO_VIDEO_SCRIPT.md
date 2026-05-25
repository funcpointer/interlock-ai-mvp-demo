# Demo Video Voice-Over Script

Target length: 3 minutes.

## 0:00-0:25 — Open

Action: Open `https://interlock-ai-mvp-demo-ddptwdsnkhnf84zqf6nd3q.streamlit.app/`.

Voice-over:

> InterLock AI is an engineering review assistant for comparing technical PDFs. The wedge is simple: find verifiable mismatches across documents, cite the source evidence, and help senior reviewers inspect the right issues faster.
>
> This does not replace engineering judgment. It gives the reviewer an evidence-backed review map instead of another uncited AI summary.

## 0:25-1:20 — Version Review

Action: Select `Public version demo`, keep cloud calls off, and click `Run review`.

Voice-over:

> First, I am running a version review. This compares a baseline PDF against a revised PDF. In version mode, the revised document is treated as authoritative, but the system still has to prove every finding with source citations.
>
> This demo uses a real public AES transformer specification sheet and a watermarked synthetic revision. The synthetic revision gives us known expected discrepancies, so we can test precision instead of just showing a nice-looking output.

Action: Open the two review-required findings. Point to subject, parameter, values, authority, quotes, and crop images.

Voice-over:

> The system found two review-required findings: transformer rating changed from 140 MVA to 120 MVA, and impedance changed from 10 percent to 8 percent.
>
> Each finding includes the subject, parameter, values from both documents, authority direction, page references, quotes, bounding boxes, and a crop from the PDF. The rule is: no citation, no finding.

## 1:20-2:05 — Cross-Document Review

Action: Select `Public cross-doc demo` and click `Run review`.

Voice-over:

> Now I am switching to cross-document review. This is the broader product direction: comparing different document types, not just two revisions of the same file.
>
> Here the system compares the transformer specification against a synthetic protection-study excerpt. The same engineering assumptions appear in a different document shape, which is much closer to real review work.

Action: Open a cross-doc finding. Point to authority and evidence from both files.

Voice-over:

> Authority matters here. A generic "A does not equal B" flag is not enough. The reviewer needs to know which document is treated as controlling and why. In this demo, the AES authority configuration ranks the protection study above the specification.
>
> If authority is unknown, the system should not overclaim. It should route the item to engineer review.

## 2:05-2:45 — Architecture

Action: Expand artifacts or debug/details. Show `findings.json`, `metrics.json`, `reasoning_graph.json`, and `decision_traces.json` if visible.

Voice-over:

> The UI is only an adapter. The core product is a reusable review engine: the CLI, Streamlit app, and a future API can all call the same review function.
>
> The engine persists intermediate artifacts: extracted pages, regions, evidence, document graphs, reasoning decisions, findings, metrics, and logs. That matters because accuracy work needs observability. When a flag is wrong, we can inspect whether the issue came from extraction, subject alignment, unit comparison, authority resolution, or rendering.
>
> JSON is the source of truth. The report, graph, search layer, wiki, and UI are derived from it. That keeps the prototype easy to debug now and easy to port later.

## 2:45-3:10 — Close

Action: Return to the findings list.

Voice-over:

> The MVP is intentionally conservative. It handles cited parameter discrepancies first, and it surfaces low-text or scanned pages as coverage warnings instead of pretending it reviewed what it could not read.
>
> The next accuracy lift is OCR, VLM extraction, table structure, and evaluation on private AES document packets. But the product thesis is already visible: turn engineering PDFs into a cited review map, flag costly mismatches, and make expert review faster and more systematic.
