# VC Perspective And Next Steps - 2026-05-25

## Investor Read

A VC will not fund this because we built Kuzu, LanceDB, a memory palace, or a CLI. They will care if the demo proves a painful, expensive review failure can be caught with citations in a workflow that plausibly expands from one wedge into a larger review platform.

The fundable wedge is:

```text
Cross-file engineering discrepancy detection with source citations.
```

The current MVP now has two credible proof points:

- version-review: public AES transformer spec vs watermarked synthetic revision,
- cross-document review: public AES transformer spec vs watermarked synthetic protection-study excerpt.

Both are controlled and eval-backed. That is good for a first funding demo. It is not yet proof of broad real-world robustness.

## What A VC Will Like

- Real public AES source document anchors the demo.
- Synthetic changes are watermarked and explicit, so the demo is honest.
- Findings are cited to pages, quotes, and crops.
- Authority is directional: protection study can outrank specification; revised doc can outrank baseline.
- The engine emits reasoning artifacts, not just chat output.
- Runs are repeatable through one command.
- Evaluation catches expected and forbidden findings.
- The product story maps to a large workflow: studies, drawings, contracts, standards, checklists.

## What A VC Will Challenge

1. Is this just a scripted demo?
2. Can it handle real messy AES project packets?
3. Does it catch things an engineer actually cares about?
4. How many false positives does it create?
5. Why now? Why not generic document AI?
6. What is proprietary over time?
7. Who buys it, and where does it enter the workflow?
8. Can this become a platform, or is it a services-heavy tool?

The answer must be evidence, not architecture. Show:

- one clean version-review demo,
- one clean cross-document demo,
- one negative/no-mismatch run,
- one scanned/low-text run that honestly routes to coverage warnings,
- one triage artifact proving we know what failed.

## Next Engineering Priority

### P0: Make The Demo Story Airtight

Deliverable:

```bash
make eval-public-demo
make eval-public-cross-doc-demo
make eval-negative
make eval-scanned
```

These four runs tell the whole MVP story:

- catches planted version mismatches,
- catches planted cross-doc mismatches,
- does not invent findings on identical docs,
- does not pretend unreadable scans are reviewed.

Action:

- add a single demo command that runs these four and writes a compact demo summary.
- include exact report paths and headline metrics.
- keep Kuzu/search/wiki as derived artifacts, not the main pitch.

### P1: Remove Cross-Doc Fixture Noise

The old fixture pair `spec_xfmr_001.pdf` vs `doc_a_60pct.pdf` currently produces two useful possible-issue value mismatches plus four noisy missing-item findings.

The useful findings:

- `XFMR-001` rating: `1100 kVA` vs `1000KVA`
- `XFMR-001` impedance: `4.5%` vs `5.75% Z`

The noisy findings:

- document IDs and aliases treated as missing equipment presence:
  - `SPEC-XFMR-001`
  - `XFMR-001`
  - `XFMR-001-REV-A`
  - `XFMR XFMR-001`

Action:

- suppress `equipment_presence` missing-item findings for document IDs and revision labels,
- keep real equipment-missing detection for part numbers / devices / explicit equipment rows,
- add tests so this cannot hide actual missing fuses or devices.

This improves precision without weakening the two cross-doc value mismatches.

### P1: One More Cross-Doc Finding Class

Current clean cross-doc demo only shows value mismatches.

Add one controlled public cross-doc case for either:

- missing required item, or
- reference conflict.

Preferred next demo mutation:

```text
Spec says transformer impedance basis / standard / required item exists.
Protection-study excerpt omits or conflicts with it.
```

Guardrails:

- no missing-item flood,
- no generic document-ID missing findings,
- every finding cited,
- no downgraded `review_required` finding.

### P2: Private AES Data Intake

The next real proof requires AES packet data:

- real study + drawing + spec pair from the same project,
- reviewer notes or marked-up PDFs if available,
- known historical discrepancy if possible,
- one negative pair where no discrepancy should be found.

Action:

- use `corpora/aes/local_manifest.yaml`,
- add per-pair eval YAML,
- run `interlock_mvp triage` after each run,
- only then decide whether OCR, VLM, table parsing, or alias dictionaries are the next bottleneck.

## Demo Narrative

The pitch should be:

1. Engineering reviewers lose time because mismatches hide across documents.
2. InterLock ingests two PDFs and builds a cited review map.
3. Version-review catches a transformer rating change and impedance change.
4. Cross-document review catches the same class of issue when expressed in a protection-study excerpt instead of a revised spec.
5. Every flag has page, quote, crop, authority direction, and reasoning trace.
6. The system refuses to overclaim: scans become coverage warnings; noisy/generic cases appear in triage.
7. The wedge expands from transformer specs/studies into drawings, standards, checklists, and contracts.

## What Not To Pitch

- Do not pitch graph DB as the product.
- Do not pitch memory palace as the product.
- Do not pitch local SLMs as the product.
- Do not claim arbitrary engineering-document understanding.
- Do not claim it replaces senior engineering judgment.
- Do not hide that the current demo uses synthetic mutations.

Pitch the system as an expert-assist reviewer that makes human review faster, more systematic, and more auditable.

## Immediate Build Queue

1. Done: add a simple local UI adapter over `run_review`.
2. Add `make eval-demo-package`.
3. Add `runs/demo-package/summary.md`.
4. Fix cross-doc fixture noise from document/revision IDs.
5. Add a third public cross-doc demo finding class: missing-item or reference conflict.
6. Re-run coverage and evals.
7. Record demo video.

## Funding Readiness Bar

Ready for VC demo when:

- public version demo passes,
- public cross-doc demo passes,
- negative eval passes,
- scanned eval routes to warnings,
- old fixture cross-doc value findings remain,
- old fixture cross-doc noisy missing-item count drops,
- all headline artifacts can be shown in under 5 minutes.
