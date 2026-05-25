# Demo Walkthrough - 2026-05-25

Purpose: a 2-5 minute funding-demo path that shows the strongest current MVP behavior without overstating cross-document maturity.

## Demo Claim

InterLock MVP can review two engineering PDFs, extract cited evidence, compare engineering values with units, apply directional authority, and produce auditable reviewer-assist findings.

This demo uses a real public AES transformer specification sheet as the baseline and a generated, watermarked synthetic revision as the revised document. The planted changes are explicit and evaluation-checked:

- transformer rating: `84/112/140 MVA` -> `84/112/120 MVA`
- transformer impedance: `10%` -> `8%`

Do not claim this synthetic revision is a real AES-issued revision.

## One Command

```bash
make eval-public-demo
```

That target:

- regenerates the synthetic revised PDF,
- runs the review through the same CLI/API spine,
- checks `eval/public_transformer_spec_synth.yaml`,
- writes triage diagnostics.

Primary run folder:

```text
runs/public-demo/public_transformer_spec_synthetic_revision/
```

## Files To Open During Recording

Start with:

```text
runs/public-demo/public_transformer_spec_synthetic_revision/report.md
```

Then show the exact audit artifacts:

```text
runs/public-demo/public_transformer_spec_synthetic_revision/findings.json
runs/public-demo/public_transformer_spec_synthetic_revision/decision_traces.json
runs/public-demo/public_transformer_spec_synthetic_revision/reasoning_graph.json
runs/public-demo/public_transformer_spec_synthetic_revision/triage.json
```

Useful citation crops:

```text
runs/public-demo/public_transformer_spec_synthetic_revision/crops/A_p4_r13.png
runs/public-demo/public_transformer_spec_synthetic_revision/crops/B_p4_r28.png
runs/public-demo/public_transformer_spec_synthetic_revision/crops/A_p5_r4.png
runs/public-demo/public_transformer_spec_synthetic_revision/crops/B_p5_r29.png
```

Optional reviewer-memory pages:

```text
runs/public-demo/public_transformer_spec_synthetic_revision/wiki/index.md
runs/public-demo/public_transformer_spec_synthetic_revision/wiki/review-map.md
runs/public-demo/public_transformer_spec_synthetic_revision/wiki/memory-palace.md
runs/public-demo/public_transformer_spec_synthetic_revision/wiki/findings/find_00001.md
runs/public-demo/public_transformer_spec_synthetic_revision/wiki/findings/find_00002.md
```

## Recording Script

1. Run `make eval-public-demo`.
2. Open `report.md`.
3. Show executive summary:
   - 2 findings,
   - 2 review-required,
   - 0 coverage warnings,
   - authority `B` because revised document supersedes baseline.
4. Show finding `find_00001`:
   - subject `XFMR`,
   - parameter `rating`,
   - A citation page 4: `Primary to Secondary Winding: 84/112/140 MVA`,
   - B citation page 4: `84/112/120 MVA`,
   - unit method `pint`.
5. Show finding `find_00002`:
   - subject `XFMR`,
   - parameter `impedance`,
   - A citation page 5: `Primary - Secondary (ONAF): 10% (+/- allowed tolerance)`,
   - B citation page 5: `8% (+/- allowed tolerance)`,
   - unit method `custom_percent_impedance`.
6. Open the four crop PNGs and show that every flag is tied to source image evidence.
7. Open `decision_traces.json` and show that each finding has:
   - citation signal,
   - authority signal,
   - alignment signal,
   - comparison signal,
   - no downgrade.
8. Open `triage.json` and say what still needs work:
   - some generic evidence remains,
   - no current blocker for these two findings,
   - extraction/context improvements remain the next accuracy work.

## What This Proves

- The core review spine is reusable: CLI is only an adapter over `run_review`.
- The system can produce cited, directional, unit-aware version-review findings.
- The system suppresses unrelated noise for this demo case:
  - no voltage mismatch,
  - no missing item,
  - no tap-step percentage finding,
  - no coverage warning.
- Telemetry is available from the start: metrics, logs, triage, reasoning graph, decision traces, search index, wiki, and crops.

## What This Does Not Prove

- It does not prove broad cross-document robustness across drawings, studies, contracts, standards, and checklists.
- It does not prove OCR/VLM recall on heavily scanned or rotated drawing packages.
- It does not prove a real AES private project review packet.
- It does not prove fully semantic table understanding.

The honest product message: version-review is demo-ready on the public synthetic revision; cross-document review exists and passes a controlled fixture, but real cross-document value comparison still needs paired project data and stronger table/subject extraction.

## Cross-Doc Demo Add-On

Run:

```bash
make eval-public-cross-doc-demo
```

This compares the same real public AES transformer specification sheet against a watermarked synthetic protection-study excerpt.

Primary run folder:

```text
runs/public-cross-doc-demo/public_transformer_spec_vs_synthetic_protection_excerpt/
```

Show:

- `report.md`
- `findings.json`
- `reasoning_graph.json`
- `decision_traces.json`
- `triage.json`

Expected result:

- 2 findings,
- 2 review-required,
- 0 coverage warnings,
- 2 alignment decisions,
- 2 comparison decisions,
- 0 absence searches,
- 0 downgraded traces.

The key difference from the version-review demo is the reasoning method:

- `alignment_decisions_by_context_method`: `{'cross_doc_bridge': 2}`
- authority: `B`, because `protection_study` ranks above `specification` in the AES authority config.

Use this as the cross-doc proof point. Keep the caveat: it is still a controlled synthetic cross-doc pair, not a claim that unrelated standards/manuals can be compared as if they were paired project documents.
