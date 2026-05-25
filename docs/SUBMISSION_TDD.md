# TDD: InterLock AI MVP

## Architecture

CLI and Streamlit are adapters. Business logic lives in:

```python
run_review(request: ReviewRequest) -> ReviewResult
```

Pipeline:

1. resolve document type and authority,
2. extract PDF pages, text blocks, annotations, images, and crops,
3. mine evidence from regions,
4. build document graphs: contexts, subjects, claims,
5. build diff and reasoning graphs,
6. compare units and engineering quantities,
7. emit cited findings,
8. write JSON artifacts, report, logs, search index, wiki, and optional Kuzu graph.

JSON is canonical. Markdown, search, wiki, graph, and UI views are derived.

## Extraction

PyMuPDF provides:

- page dimensions and text counts,
- text blocks with bounding boxes,
- page images and citation crops,
- annotations, comments, and highlighted text.

Low-text pages produce coverage warnings. The system does not claim review coverage where text extraction fails.

## Reasoning And Comparison

Evidence is normalized into claims:

- subject,
- parameter,
- value/unit,
- context,
- source citation.

Comparison uses:

- subject and context alignment,
- AES glossary aliases,
- graph/search/memory signals as non-authoritative support,
- Pint for unit equivalence,
- custom `%Z` impedance handling,
- decimal/magnitude-slip checks,
- deterministic discrepancy gates.

Examples:

- `150 kVA` vs `0.15 MVA` is suppressed.
- `140 MVA` vs `120 MVA` is flagged.
- `%Z` with incomplete base context routes to engineer review.

## Authority And Severity

Authority is explicit:

- version mode: B supersedes A,
- cross-doc mode: configured AES precedence,
- unknown authority downgrades rather than overclaims.

`review_required` requires:

- cited evidence,
- deterministic discrepancy,
- strong enough identity,
- known authority direction.

## Explainability

Each Streamlit finding has a compact explainability graph:

```text
cited evidence -> context support -> candidate screening -> pairing
-> value check -> authority -> finding
```

The graph explains why evidence was paired and how the finding was decided. It is not a substitute for citations.

## Optional Cloud Review

When enabled, the external model receives only existing cited finding JSON, source quotes, authority, and context support. It can add advisory notes. It cannot create findings, bypass citations, or certify correctness.

## Evaluation

Eval checks:

- expected findings present,
- forbidden findings absent,
- every finding cited,
- language guard,
- max finding counts,
- decision artifacts present.

Current validation:

- public version demo passes,
- public cross-doc demo passes,
- negative/no-mismatch eval passes,
- scanned/low-text eval routes to coverage warnings,
- test suite: `94 passed`.

## Known Limits

- OCR/VLM extraction is not active in the public demo.
- Complex multi-page tables and drawing-only labels remain weak.
- Public demo uses watermarked synthetic mutations over real public AES source material.
- Production readiness needs private AES project packets and gold expectations.
