# Streamlit Cloud Deployment

Status: pushed to GitHub and ready for Streamlit Cloud app creation.

## What Streamlit Cloud Needs

- Public GitHub repository containing this project:
  `https://github.com/funcpointer/interlock-ai-mvp-demo`
- Branch: `main`.
- Main file path: `streamlit_app.py`.
- Python version: choose `3.12` in Streamlit Cloud advanced settings.
- Dependencies: `requirements.txt`.
- Secrets: none required for the default demo. Cloud calls are disabled by default in the UI.

## Included Demo Assets

The hosted app includes three small public/synthetic PDFs under:

```text
demo_assets/public_aes/
```

These make the hosted URL useful immediately:

- public version demo,
- public cross-document demo,
- upload-your-own two-PDF review.

Private AES PDFs remain gitignored under `corpora/aes/docs/`.

## Deployment Steps

1. Open Streamlit Community Cloud.
2. Create app from existing GitHub repo.
3. Select repository `funcpointer/interlock-ai-mvp-demo`.
4. Select:
   - branch: `main`,
   - main file path: `streamlit_app.py`.
5. In advanced settings:
   - choose Python `3.12`,
   - leave secrets empty,
   - choose a public/custom app URL suitable for VC sharing.
6. Leave secrets empty for the default no-cloud demo.
7. Deploy.

## Runtime Behavior

- Output runs are written under `runs/` by default.
- Set `INTERLOCK_RUN_ROOT=/tmp/interlock-runs` on hosts where the repo directory is read-only.
- The app defaults to no-cloud and no-Kuzu for repeatable VC demos.
- If cloud calls are enabled later, add secrets through Streamlit Cloud secrets, not files committed to git.

## Current Blocker

Streamlit Cloud app creation requires the account workspace UI. The source repo is ready and pushed; the remaining step is selecting repo `funcpointer/interlock-ai-mvp-demo`, branch `main`, and file `streamlit_app.py` in Streamlit Cloud.
