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

Local search on 2026-05-25 did not find a private AES PDF bundle by filename.
It did find useful near-real seed documents:

- `/Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs/doc_a_60pct.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs/doc_b_90pct.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs/spec_xfmr_001.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs/real_ieee_xfmr_spec_guide.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs/real_sel_xfmr_protection.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock AI/fixtures/pdfs/bus-ele-sample-coordination-study.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock AI/fixtures/pdfs/6079_TransformerProtection_Web.pdf`
- `/Users/kc/Documents/Claude/Projects/interlock AI/fixtures/pdfs/Preparation-of-Transformer-Specifications1.pdf`

These are not a substitute for AES project docs. They are useful for smoke,
negative, and cross-vendor extraction tests while private corpora are being
assembled.
