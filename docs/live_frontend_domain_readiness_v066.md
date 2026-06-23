# V0.66 Live Frontend Domain Readiness

Purpose: prepare PRMR Memory Core for a future public frontend deployment without exposing local review consoles, local file-writing APIs, local demo bridge execution, private reports, secrets, or inflated claims.

V0.66 does not deploy a domain. It does not create hosted backend infrastructure, production onboarding, billing, live API access, API key issuing, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.

## Deployment Mode Flags

Use these environment flags:

- `NEXT_PUBLIC_DEPLOYMENT_MODE=local | public_frontend`
- `LOCAL_REVIEW_ENABLED=false`
- `LOCAL_FILE_WRITES_ENABLED=false`
- `LOCAL_DEMO_BRIDGE_ENABLED=false`
- `PUBLIC_FORM_CAPTURE_ENABLED=false`
- `PUBLIC_DEMO_BRIDGE_ENABLED=false`

If `NEXT_PUBLIC_DEPLOYMENT_MODE` is unset, production builds default to `public_frontend` and development defaults to `local`.

## Public Frontend Mode

`public_frontend` mode is presentation-only. It can show public-safe pages and static/synthetic product evidence, but it must not expose local admin/review surfaces, local request files, local report files, or local process execution.

Allowed public-safe pages:

- `/`
- `/demo`
- `/docs`
- `/alpha`
- `/book-demo`
- `/contact`
- `/demo-video`
- `/capabilities/[slug]`

## Blocked Local Routes

The following are disabled unless local review mode is explicitly enabled:

- `/alpha/review`
- `/book-demo/review`
- `/api/alpha/review`
- `/api/demo/review`

The API response uses `local_only_route_disabled` and does not include private request data.

## Disabled Local Demo Bridge Routes

The following routes are disabled unless the local demo bridge is explicitly enabled in local mode:

- `/api/demo/scenarios`
- `/api/demo/run`
- `/api/demo/report`
- `/api/demo/health`

The disabled response uses `demo_bridge_disabled_on_public_frontend`. These routes must not spawn local processes on a public domain.

## Public Form Limitation

The alpha request and book-demo APIs write to local JSON files in the current local shell:

- `/api/alpha/request`
- `/api/demo/book`

In public frontend mode, these return a safe disabled response: `request_capture_not_enabled_on_public_frontend`. V0.66 does not pretend hosted storage exists.

## Build Commands

Run from `frontend/`:

```bash
npm run typecheck
npm run build
```

Then run from the repo root:

```bash
python examples/audit_v066_live_frontend_readiness.py
```

## Future Work

Before a real public launch, PRMR needs hosted storage, authentication, permissioned admin review, rate limiting, secure logging, deployed monitoring, abuse controls, private report storage, key management, and a real smoke check against the deployed URL.
