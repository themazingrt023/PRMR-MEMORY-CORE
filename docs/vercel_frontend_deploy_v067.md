# V0.67 Vercel Frontend Deployment Notes

Preferred target: Vercel for the Next.js frontend only.

This document is a deployment-prep guide, not evidence that a deployment exists. A live deployment is only confirmed after a real deployed URL is provided and smoke-checked.

## Project Settings

Use these settings:

- Framework preset: Next.js
- Project root: `frontend/`
- Install command: `npm install`
- Build command: `npm run build`
- Output directory: `.next`

The repository includes `frontend/vercel.json` with those frontend-only settings and safe public-mode defaults.

## Environment Variables

Set:

```env
NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend
LOCAL_REVIEW_ENABLED=false
LOCAL_FILE_WRITES_ENABLED=false
LOCAL_DEMO_BRIDGE_ENABLED=false
PUBLIC_FORM_CAPTURE_ENABLED=false
PUBLIC_DEMO_BRIDGE_ENABLED=false
```

No secrets are required for this public frontend mode.

Do not add API keys, database secrets, calendar credentials, email credentials, billing credentials, or private report paths to public frontend variables.

## Before Deploying

Run from `frontend/`:

```bash
npm run typecheck
npm run build
```

Run from the repo root:

```bash
python examples/audit_v067_staging_deployment.py
```

## After Deploying

Set `PRMR_STAGING_DEPLOYMENT_URL` or `STAGING_DEPLOYMENT_URL` to the deployed URL and rerun:

```bash
python examples/audit_v067_staging_deployment.py
```

The deployed smoke check must verify public pages, blocked review routes, disabled demo bridge APIs, and disabled local file-writing form APIs.

## Future Work Not Covered Here

This frontend deployment does not provide hosted backend storage, database persistence, authentication, key issuance, billing, deployed admin review, external validation, legal approval, compliance approval, bank approval, external security certification, or production readiness.
