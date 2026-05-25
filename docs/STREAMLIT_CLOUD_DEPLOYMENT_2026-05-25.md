# Streamlit Cloud Deployment

Status: deploy-ready locally. Blocked only on GitHub/Streamlit account authentication.

## What Streamlit Cloud Needs

- GitHub repository containing this project.
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

1. Push this repo to GitHub.
2. Open Streamlit Community Cloud.
3. Create app from existing GitHub repo.
4. Select:
   - repo: the pushed InterLock MVP repo,
   - branch: `main`,
   - main file path: `streamlit_app.py`.
5. In advanced settings, choose Python `3.12`.
6. Leave secrets empty for the default no-cloud demo.
7. Deploy.

## Runtime Behavior

- Output runs are written under `runs/` by default.
- Set `INTERLOCK_RUN_ROOT=/tmp/interlock-runs` on hosts where the repo directory is read-only.
- The app defaults to no-cloud and no-Kuzu for repeatable VC demos.
- If cloud calls are enabled later, add secrets through Streamlit Cloud secrets, not files committed to git.

## Current Blocker

The local `gh` auth tokens are invalid, and the repo has no GitHub remote. I cannot complete the Streamlit Cloud deployment until GitHub is authenticated or a target remote is provided.
