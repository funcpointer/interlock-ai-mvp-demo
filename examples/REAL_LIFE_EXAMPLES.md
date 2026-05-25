# InterLock MVP Real-Life / Near-Real Examples

These are fixture-backed examples for evaluation and demo rehearsal.

Only `eval/demo.yaml`, `eval/cross_doc.yaml`, `eval/negative.yaml`, and `eval/scanned.yaml` are labeled gold-style contracts. The examples below are smoke tests unless explicitly labeled.

## Version Gold: Coordination Study Revision

Command:

```bash
make eval-version
```

Files:

- `doc_a_60pct.pdf`
- `doc_b_90pct.pdf`

Purpose:

- catches known transformer/fuse/fault-current changes,
- verifies citations,
- verifies unit-equivalent suppression.

Latest result:

```text
5 findings
5 review_required
0 coverage_warnings
eval passed
```

## Negative: Same Document

Command:

```bash
make eval-negative
```

Files:

- `doc_a_60pct.pdf`
- `doc_a_60pct.pdf`

Purpose:

- protects false-positive rate on identical inputs.

Latest result:

```text
0 findings
0 review_required
eval passed
```

## Cross-Doc Gold: Transformer Spec vs Study

Command:

```bash
make eval-cross
```

Files:

- `spec_xfmr_001.pdf`
- `doc_a_60pct.pdf`

Purpose:

- catches rating, impedance, and primary-voltage conflicts,
- suppresses known non-conflicts such as secondary voltage and BIL.

Latest result:

```text
7 findings
4 review_required
eval passed
```

## Scanned / Low-Text Stress

Command:

```bash
make eval-scanned
```

Files:

- `doc_a_scanned.pdf`
- `doc_a_scanned.pdf`

Purpose:

- verifies low-text pages become coverage warnings,
- prevents scan failure from becoming false engineering findings.

Latest result:

```text
18 coverage_warnings
0 review_required
eval passed
```

## Synthetic Equipment Spec Reference Smoke

Command:

```bash
make eval-examples
```

Files:

- `synth_equipment_spec_v2.pdf`
- `synth_equipment_spec_v3.pdf`

Purpose:

- protects against standards/references being treated as missing equipment.
- `NEMA`, `IEC`, and `IEEE` references must remain evidence/search records, not `equipment_presence` findings.

Latest result:

```text
0 findings
0 review_required
eval passed
```

## Real Cross-Doc Smoke: IEEE Guide vs SEL App Note

Command:

```bash
make eval-examples
```

Files:

- `real_ieee_xfmr_spec_guide.pdf`
- `real_sel_xfmr_protection.pdf`

Purpose:

- stress-tests extraction and review-map search on less fixture-shaped engineering PDFs,
- exercises long document extraction,
- checks that review-required count does not explode.

Latest result:

```text
17 findings
1 review_required
0 coverage_warnings
eval passed under loose smoke cap
```

Important caveat:

- This is not a gold precision/recall label. It is an inspection smoke. The current output still has many repeated possible impedance findings and needs later dedup/alignment work.

## Known Extraction-Gap Examples

Observed but not yet promoted to eval:

- `synth_pid.pdf` vs `synth_pid_v2.pdf`: extractable regions, but current evidence miner finds almost no usable claims.
- `synth_hvac_schedule.pdf` vs `synth_hvac_schedule_v2.pdf`: table values exist, but current subject/parameter extraction is too weak.
- `synth_relay_setting_sheet.pdf` vs `synth_coordination_study_v2.pdf`: claim extraction happens, but cross-doc alignment is currently too conservative.

These should drive the next accuracy phase: table extraction and VLM/OCR-assisted evidence mining.
