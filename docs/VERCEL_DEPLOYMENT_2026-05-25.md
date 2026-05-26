# Vercel Deployment - 2026-05-25

Production URL:

```text
shared separately
```

Deployment inspector:

```text
shared separately
```

Source deployed:

```text
runs/demo-package/site/
```

Deploy command used:

```bash
npx -y vercel@latest deploy runs/demo-package/site --prod --yes --name <project-name>
```

Browser verification:

- page loaded at the production alias,
- headline showed `InterLock AI MVP Demo`,
- four cases rendered,
- totals rendered as:
  - 4 demo cases,
  - 4 review findings,
  - 4 review required,
  - 18 coverage warnings,
- 26 citation/crop images were present in the DOM.

Pre-deploy safety check:

```bash
rg -n "(/Users/kc|OPENAI|ANTHROPIC|VOYAGE|API_KEY|SECRET|TOKEN|corpora/aes/docs|Documents/Claude|venv-12)" runs/demo-package/site runs/demo-package/summary.md
```

Expected result: no matches.

Security posture:

- this is a static site,
- no upload form,
- no local file-path input,
- no server execution endpoint,
- no copied wiki pages with local document paths,
- exported metrics remove `env_keys_loaded`,
- exported JSON text is sanitized for local filesystem paths and key names.
