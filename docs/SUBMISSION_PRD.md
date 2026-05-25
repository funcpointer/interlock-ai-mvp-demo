# PRD: InterLock AI MVP

## Problem

Energy infrastructure review teams compare studies, drawings, specifications, contracts, standards, and checklists by hand. Important mismatches can hide across files until late design or construction review, where they become expensive schedule and safety risks.

The MVP wedge is cross-file discrepancy detection for engineering PDFs with source citations. The product does not replace engineering judgment. It helps reviewers find, inspect, and triage verifiable issues faster.

## User

Primary user: senior or staff electrical/protection engineer reviewing design packages.

Workflow fit:

- reviewer already receives multiple PDFs,
- reviewer must compare assumptions, ratings, references, and missing items,
- reviewer needs traceable evidence, not a chatbot answer,
- reviewer must decide final engineering significance.

## MVP Scope

The MVP reviews two PDFs in either:

- `version` mode: revised document supersedes baseline,
- `cross_doc` mode: authority follows configured document-type precedence.

The system extracts page text, regions, annotations, source crops, evidence items, claims, reasoning decisions, and reviewer-facing findings.

Each finding includes:

- finding type and severity,
- subject and parameter,
- authority direction,
- page/quote/crop citations,
- reasoning trace IDs,
- metrics and triage artifacts.

## Current Demo Cases

1. Public AES transformer specification sheet vs watermarked synthetic revision.
   - `140 MVA -> 120 MVA`
   - `10% impedance -> 8%`

2. Public AES transformer specification sheet vs watermarked synthetic protection-study excerpt.
   - same two discrepancies expressed across document types.

Both cases are eval-backed and produce two review-required cited findings.

## Non-Goals

- Replace final engineering review.
- Claim broad arbitrary-document understanding.
- Hide unreadable scans behind fabricated confidence.
- Make graph/search/LLM output authoritative by itself.

## Platform Path

Wedge: transformer specs and protection-study comparisons.

Next expansion:

- OCR/VLM for scans and image-only drawings,
- stronger table extraction,
- reviewer-authored glossaries and aliases,
- private AES packet evaluation,
- additional finding classes: missing required item, conflicting reference, checklist gap,
- API/FE surface over the same `run_review(ReviewRequest)` core.

## Success Criteria

- two real engineering PDFs ingested,
- cited mismatch findings produced,
- negative pair produces no review-required findings,
- scan/low-text pair routes to coverage warnings,
- findings are reproducible through CLI and live demo,
- reviewer can inspect source evidence in under one minute.
