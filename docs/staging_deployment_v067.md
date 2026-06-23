# V0.67 Staging Deployment Readiness

Purpose: prepare PRMR Memory Core for a public-safe frontend staging deployment and, only if a deployed URL is provided, smoke-check that URL.

V0.67 does not itself prove a live deployment. If no deployed URL is provided through `PRMR_STAGING_DEPLOYMENT_URL` or `STAGING_DEPLOYMENT_URL`, the deployed URL smoke check must be recorded as `not_run_no_url`.

Boundary: V0.67 is staging deployment readiness and/or deployed URL smoke testing only. It is not hosted backend, not production onboarding, not billing, not live API access, not API key issuance, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## Required Public Frontend Environment

Use these values for staging/public frontend deployment:

```env
NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend
LOCAL_REVIEW_ENABLED=false
LOCAL_FILE_WRITES_ENABLED=false
LOCAL_DEMO_BRIDGE_ENABLED=false
PUBLIC_FORM_CAPTURE_ENABLED=false
PUBLIC_DEMO_BRIDGE_ENABLED=false
```

No secrets are required for public frontend mode.

## Deployment Target

Preferred target: Vercel, with the project root set to `frontend/`.

The frontend has a local `frontend/vercel.json` that sets the Next.js framework, build command, install command, output directory, and public-safe disabled defaults.

## Public-Safe Routes

The staging deployment should allow:

- `/`
- `/demo`
- `/docs`
- `/alpha`
- `/book-demo`
- `/contact`
- `/demo-video`
- `/capabilities/[slug]`

These routes must not expose secrets, private reports, local request files, local personal paths, hosted API claims, production readiness claims, or certification claims.

## Local/Admin Routes

These must remain blocked in public frontend mode:

- `/alpha/review`
- `/book-demo/review`
- `/api/alpha/review`
- `/api/demo/review`

Allowed behavior: 404, a safe disabled page, or JSON code `local_only_route_disabled`.

## Disabled Local Demo Bridge APIs

These must remain disabled in public frontend mode:

- `/api/demo/scenarios`
- `/api/demo/run`
- `/api/demo/report`
- `/api/demo/health`

Expected JSON code: `demo_bridge_disabled_on_public_frontend`.

## Disabled Local File-Writing Forms

These must not write local files in public frontend mode:

- `/api/alpha/request`
- `/api/demo/book`

Expected JSON code: `request_capture_not_enabled_on_public_frontend`.

They must not send email, create calendar events, issue API keys, grant live access, or connect billing.

## Future Work

V0.68+ still needs a real deployed URL smoke check if no URL is available in V0.67, plus hosted storage, database, authentication, key issuance, billing policy, monitoring, rate limiting, abuse controls, private report storage, and operational security review before any broader launch.
