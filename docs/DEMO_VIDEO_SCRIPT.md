# Demo Video Script

Target length: 3 minutes.

## 0:00-0:20 - Open

Action: open the shared live prototype URL.

Voice-over:

> InterLock AI is an engineering review assistant for comparing technical PDFs. The goal is not to replace expert judgment. The goal is to find verifiable mismatches, cite the source evidence, and make senior review faster and more systematic.

## 0:20-1:15 - Version Review

Action: select `Public version demo`, leave cloud calls off, click `Run review`.

Voice-over:

> This is a version review: baseline document versus revised document. The revised document is treated as authoritative, but every finding still has to be proven with source citations.
>
> The demo uses a real public AES transformer specification sheet and a watermarked synthetic revision so the expected discrepancies are known and eval-checked.

Action: open the two findings.

Voice-over:

> The system finds two review-required changes: transformer rating from 140 MVA to 120 MVA, and impedance from 10 percent to 8 percent.
>
> Each finding shows the subject, parameter, values, authority direction, page quote, and source crop. The rule is simple: no citation, no finding.

## 1:15-2:00 - Explainability

Action: expand `Explainability: why this finding was made`.

Voice-over:

> This is the explainability layer. The graph shows how the system moved from cited evidence to context support, candidate screening, pairing, value comparison, authority direction, and finally the finding.
>
> This matters because a reviewer needs to know why two pieces of evidence were paired, what else was considered, and which comparison rule fired. The graph and text explain the reasoning, but they do not replace the source citations.

## 2:00-2:35 - Cross-Document Review

Action: select `Public cross-doc demo`, click `Run review`, open one finding.

Voice-over:

> This is the broader product wedge: cross-document review. The system compares a transformer specification against a protection-study excerpt. The same engineering assumptions appear in a different document shape.
>
> Authority matters here. The AES configuration ranks the protection study above the specification. If authority is unknown, the system should downgrade instead of overclaiming.

## 2:35-3:00 - Architecture And Close

Action: show artifacts/downloads or context layer briefly.

Voice-over:

> The UI is only an adapter. The core engine writes structured artifacts: extracted regions, evidence, document graphs, reasoning graph, decision traces, findings, metrics, logs, search index, and wiki.
>
> That observability is critical for accuracy work. When a finding is weak, we can see whether the issue came from extraction, subject alignment, unit comparison, authority, or rendering.
>
> The current MVP is conservative: cited parameter discrepancies first, coverage warnings for low-text pages, and no fabricated confidence. The next lift is OCR/VLM, stronger table structure, and private AES packet evaluation.
