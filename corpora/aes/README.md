# AES Corpus Intake

This folder is for partner-specific test corpora. Do not commit AES-private PDFs,
notes, marked-up review copies, or local manifests.

Use this workflow:

1. Put private files under `corpora/aes/docs/`, or reference absolute paths.
2. Copy `manifest.example.yaml` to `local_manifest.yaml`.
3. Add version-review and cross-document pairs.
4. Run:

```bash
make eval-aes-corpus
```

`local_manifest.yaml`, `docs/`, and PDFs under this folder are gitignored. The
committed code only stores the intake contract and repeatable harness.

Near-real seed manifests expect fixture PDFs under `fixtures/pdfs/` by default.
Override `source_root` in a local manifest when using a different fixture
directory. These seed files are not a substitute for AES project docs; they are
useful for smoke, negative, and cross-vendor extraction tests while private
corpora are being assembled.

## Public AES Smoke Corpus

Public AES/AES Indiana PDFs can be kept under the gitignored
`corpora/aes/docs/public_aes/` folder and referenced from
`corpora/aes/local_manifest.yaml`.

Downloaded locally on 2026-05-25:

- `aes_indiana_der_interconnection_2026.pdf`
  - source: `https://www.aesindiana.com/sites/aesvault.com/files/2026-02/AES-Indiana-Distribution-Interconnection-Standard-02-11-2026.pdf`
  - use: DER technical requirements / extraction and standards stress test
- `aes_indiana_goldbook_complete.pdf`
  - source: `https://apps.aesindiana.com/goldbook/Goldbook_Complete.pdf`
  - use: service and meter manual / large standards-manual stress test
- `somerset_main_power_transformer_spec_sheet.pdf`
  - source: `https://www.aes.com/sites/vault/files/2025-04/Appendix%205-D_Main%20Power%20Transformer%20Specification%20Sheet.pdf`
  - use: public transformer specification sheet
- `somerset_electrical_design_drawings_part1.pdf`
  - source: `https://www.aes.com/sites/aes.com/files/2023-08/Appendix%205-B_Revised_Electrical%20Design%20Drawings_Part%201%20of%203.pdf`
  - use: large drawing package; not in the default local smoke manifest because
    full page rendering can dominate iteration time

Current public-AES signal:

- `public_aes_der_standard_vs_goldbook`: feasible in about 30 seconds, but triage
  reports weak extraction pages, document-level context fallback, generic
  subjects, and absence-only findings.
- `public_aes_der_standard_vs_transformer_spec_sheet`: bounded smoke pair with
  the same core limitation: extraction works, but cross-document comparison does
  not yet align real claims.

These public documents are useful because they expose the real next problem:
subject/context extraction and value alignment, not another storage layer.

## Public Demo Synthetic Revision

`scripts/make_synthetic_transformer_revision.py` creates a watermarked synthetic
revision:

```text
corpora/aes/docs/public_aes/somerset_main_power_transformer_spec_sheet_synth_rev.pdf
```

It is generated from the public AES Somerset main power transformer specification
sheet and plants two explicit changes:

- `84/112/140 MVA` -> `84/112/120 MVA`
- `10% (+/- allowed tolerance)` -> `8% (+/- allowed tolerance)`

Run:

```bash
make eval-public-demo
```

The target uses `corpora/aes/public_demo_manifest.yaml` and
`eval/public_transformer_spec_synth.yaml`. This is the current best demo-quality
case because it uses a real public AES PDF while keeping the mutation source and
gold expectations explicit.
