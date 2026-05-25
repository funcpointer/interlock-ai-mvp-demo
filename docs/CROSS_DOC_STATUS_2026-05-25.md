# Cross-Document Status - 2026-05-25

## Current State

Cross-document review is functional, but not yet demo-grade on arbitrary real public documents.

The controlled cross-doc fixture passes:

```bash
make eval-cross
```

Current triage for `runs/checkpoint-cross`:

- 6 findings,
- 4 review-required findings,
- 0 coverage warnings,
- 2 generic/weak evidence subjects,
- 4 absence-search-only non-coverage findings,
- 2 downgraded decision traces.

That is acceptable as an executable contract. It is not enough to claim robust cross-file engineering review.

## What Works

- Directional authority is present for cross-doc mode.
- Specification-vs-study precedence can be configured through `examples/aes_authority.yaml`.
- Controlled fixture expectations pass through `eval/cross_doc.yaml`.
- Findings are cited and traceable through `reasoning_graph.json` and `decision_traces.json`.
- Triage now exposes when cross-doc output is relying on absence search instead of aligned value comparison.

## What Partially Works

Public AES stress runs complete without crashing and produce useful telemetry, but they do not yet produce high-confidence value comparisons:

- DER standard vs Goldbook: many coverage warnings and no review-required value comparisons.
- DER standard vs transformer spec sheet: transformer spec values are now extracted better, but the pair is not a true paired project review case.
- Public/vendor transformer cross-doc smoke: bounded and useful, but still absence-search-heavy.

The extraction can see many values. The hard part is attaching those values to the correct subject and context across document types.

## What Does Not Work Well Enough Yet

- True cross-document subject equivalence across doc types.
- Multi-page table and schedule context.
- Drawing/study/spec alignment when one side uses prose and the other uses tables.
- Absence-search precision on documents that were never intended to be direct counterparts.
- Public real-doc cross-doc demo with planted, known expected value changes.

## Why This Is Not a Graph/Search Problem First

Kuzu, LanceDB, SQLite FTS, `rg`, the wiki, and the memory-palace layer are useful derived debug surfaces.

They do not solve the current blocker by themselves. The blocker is earlier:

```text
PDF layout -> table/context extraction -> subject attachment -> cross-doc alignment
```

If the subject/context layer is weak, every downstream graph or search layer faithfully indexes weak claims.

## Next Cross-Doc Move

Build one controlled public cross-doc demo pair before trying to generalize:

1. Start from the public AES transformer specification sheet.
2. Generate a second document in a different form, such as a short protection-study excerpt or equipment-setting table.
3. Keep it watermarked as synthetic.
4. Plant 2-3 known cross-document mismatches:
   - transformer rating,
   - impedance,
   - one missing required item or reference conflict.
5. Add `eval/public_transformer_cross_doc_synth.yaml`.
6. Require:
   - at least two aligned comparison decisions,
   - no forbidden voltage mismatch,
   - no missing-item flood,
   - every finding has citation crops,
   - no downgraded review-required finding.

This creates a real cross-doc demo wedge without pretending that unrelated public standards are paired project documents.

## Demo Guidance

For the next funding demo:

- lead with version-review over the public AES synthetic revision,
- mention cross-doc as the same engine path with a passing controlled fixture,
- do not claim broad real-AES cross-doc readiness until the controlled public cross-doc pair exists and passes triage.

