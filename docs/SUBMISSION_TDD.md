# TDD: InterLock AI MVP

## Architecture

The CLI and Streamlit app are adapters. The reusable business entrypoint is:

```python
run_review(request: ReviewRequest) -> ReviewResult
```

Pipeline:

1. resolve document types and authority,
2. extract PDF pages, text blocks, annotations, images, and crops,
3. mine evidence items from regions,
4. build document graphs: contexts, subjects, claims,
5. build diff and reasoning graphs,
6. apply unit/plausibility comparison,
7. produce cited findings,
8. write JSON artifacts, report, logs, search index, wiki, and optional graph.

JSON artifacts are canonical. Markdown, search, wiki, and Kuzu are derived.

## Ingestion And Extraction

PyMuPDF provides:

- page dimensions and text counts,
- text blocks with bounding boxes,
- page images and citation crops,
- PDF annotations and highlighted text.

Low-text/scanned pages produce `coverage_warning` findings. The MVP does not pretend OCR/VLM coverage exists when text extraction fails.

## Comparison Logic

Evidence is normalized into claims:

- subject,
- parameter,
- value,
- unit,
- context,
- citation.

Comparison uses:

- subject/context alignment,
- graph/search/memory context support as non-authoritative quorum signals,
- unit equivalence through Pint,
- custom `%Z` impedance handling,
- decimal/magnitude-slip notes,
- deterministic mismatch gating.

Examples:

- `150 kVA` equals `0.15 MVA`, suppressed.
- `140 MVA` vs `120 MVA`, flagged.
- `%Z` with conflicting or missing base context routes to engineer review.

## Authority And Confidence

Authority is explicit:

- version mode: B supersedes A by default,
- cross-doc mode: configured AES precedence, e.g. protection study over specification,
- unknown direction downgrades to review rather than overclaim.

`review_required` requires:

- cited evidence,
- deterministic discrepancy,
- strong enough subject identity,
- known authority direction.

## Citation System

Every finding must have source evidence:

- page,
- quote,
- bbox,
- crop image path,
- evidence IDs,
- reasoning decision IDs.

No citation means no finding.

## Evaluation

Eval YAML checks:

- expected findings present,
- forbidden findings absent,
- citation fields exist,
- max finding counts,
- language guard,
- reasoning/decision artifacts.

Current validation:

- public version demo passes,
- public cross-doc demo passes,
- negative/no-mismatch eval passes,
- scanned eval routes to coverage warnings,
- coverage gate: 68 tests, 79% line coverage.

## Known Limits

- OCR/VLM extraction is not yet active in the public demo.
- Complex multi-page tables and drawing-only labels remain weak.
- Current public demo uses watermarked synthetic mutations over real public AES source material.
- Broad AES production readiness requires private paired project packets and gold expectations.
