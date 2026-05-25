# PRD: InterLock AI MVP

## Problem

Energy infrastructure teams compare studies, drawings, specifications, contracts, standards, and checklists by hand. Mismatches in ratings, assumptions, references, or missing items often surface late, when redesign and construction delays are expensive.

InterLock AI is a reviewer-assist tool. It does not replace engineering judgment. It helps senior reviewers find cited discrepancies faster and inspect the evidence behind them.

## User

Primary user: senior electrical, protection, or design-review engineer working through a multi-document project packet.

The tool fits the existing workflow because reviewers already:

- receive PDFs from multiple sources,
- compare values and assumptions across files,
- need directional authority, not just "A differs from B,"
- require traceable evidence before acting.

## MVP

The MVP reviews two PDFs in:

- `version` mode: revised document supersedes baseline,
- `cross_doc` mode: authority follows configured document-type precedence.

The system extracts page text, regions, annotations, crops, evidence items, claims, contexts, reasoning decisions, findings, logs, and metrics.

Each finding includes:

- subject and parameter,
- finding type and severity,
- authority direction and basis,
- page/quote/bbox/crop citations,
- explainability graph showing evidence -> context -> candidate screening -> pairing -> comparison -> authority -> finding.

## Demo Cases

1. Public AES transformer specification vs watermarked synthetic revision.
   - `140 MVA -> 120 MVA`
   - `10% impedance -> 8%`

2. Public AES transformer specification vs watermarked synthetic protection-study excerpt.
   - same planted discrepancies, expressed across document types.

Both are eval-backed and produce two review-required cited findings.

## Non-Goals

- Replace final engineering review.
- Certify engineering correctness.
- Overclaim coverage on unreadable scans.
- Treat graph/search/LLM output as authoritative without citations.

## Wedge To Platform

Wedge: transformer specification and protection-study comparison.

Expansion path:

- OCR/VLM for scans and image-heavy drawings,
- stronger table extraction,
- AES-specific glossaries and aliases,
- private AES packet evaluation,
- more finding classes: missing required items, reference conflicts, checklist gaps,
- API and richer UI over the same `run_review(ReviewRequest)` core.

## Success Criteria

- Two engineering PDFs ingested.
- Expected cited findings present.
- Negative pair produces no review-required findings.
- Low-text pages produce coverage warnings.
- Reviewer can inspect why a finding was made in under one minute.
