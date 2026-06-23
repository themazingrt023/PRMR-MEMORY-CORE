# V0.66 Deployment Smoke Check

Use this checklist only after a public/staging frontend URL exists. V0.66 itself does not provide or verify a deployed URL.

## Preflight

- `npm run typecheck` passes in `frontend/`
- `npm run build` passes in `frontend/`
- `python examples/audit_v066_live_frontend_readiness.py` passes from the repo root
- `.env.example` remains placeholder-only
- deployed environment uses `NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend`
- local review, local file writes, and local demo bridge flags are false

## Public Page Smoke Checks

Open these paths on the deployed URL:

- `/`
- `/docs`
- `/demo`
- `/alpha`
- `/book-demo`
- `/contact`
- `/demo-video`

Expected: pages load with public-safe content, synthetic/demo boundaries, no private report data, no secrets, no local personal file paths, no hosted API claim, no production readiness claim, and no certification claim.

## Blocked Route Smoke Checks

Check these paths on the deployed URL:

- `/alpha/review`
- `/book-demo/review`
- `/api/alpha/review`
- `/api/demo/review`
- `/api/demo/scenarios`
- `/api/demo/run`
- `/api/demo/report`
- `/api/demo/health`

Expected: review routes are blocked or show a safe disabled page. Demo bridge APIs return `demo_bridge_disabled_on_public_frontend`.

## Form Smoke Checks

Submit or POST to:

- `/api/alpha/request`
- `/api/demo/book`

Expected in public frontend mode: safe disabled response with `request_capture_not_enabled_on_public_frontend`. No local files should be written. No access should be granted. No API key should be issued.

## Future Deployment Gaps

The real public launch still needs hosted backend storage, authentication, permissioned admin review, rate limiting, monitoring, secure report storage, secrets management, and incident/abuse handling.
