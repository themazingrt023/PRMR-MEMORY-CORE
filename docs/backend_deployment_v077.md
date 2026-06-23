# V0.77 Backend Deployment Prep

V0.77 prepares the PRMR Memory Core V0.76 FastAPI server for real hosted deployment. This is deployment prep and smoke harness work only.

Truth label: deployment prep plus hosted smoke harness. Hosted client access is only claimable after a real deployed API URL passes smoke tests.

## App Entry Point

FastAPI app:

```text
prmr.product.api_server_v076:app
```

## Start Command

Recommended hosted command:

```bash
uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT
```

Local fallback:

```bash
uvicorn prmr.product.api_server_v076:app --host 127.0.0.1 --port 8000
```

## Required Routes

- `GET /health`
- `POST /v1/events/ingest`
- `POST /v1/continuity/packet`
- `POST /v1/memory/reconstruct`
- `POST /v1/explain`
- `POST /v1/actions/least-harm`
- `GET /v1/reports/{report_id}`
- `GET /v1/usage`
- `GET /v1/dashboard/state`

## Required Headers

Protected routes require:

- `Authorization: Bearer <api_key>`
- `X-Client-ID: <client_id>`
- `X-Vault-ID: <vault_id>`
- `X-Namespace: <namespace>`

## Environment Plan

```env
PRMR_API_MODE=hosted_alpha
PRMR_STORAGE_PATH=/app/data/prmr_api_server.sqlite
PRMR_SYNTHETIC_ONLY=true
PRMR_PUBLIC_REPORTS_DIR=/app/reports/public
PRMR_PRIVATE_REPORTS_DIR=/app/reports/private
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000
PRMR_DEFAULT_REQUEST_LIMIT=100
```

Operational notes:

- Keep raw API key values out of committed files.
- Use host-managed environment variables for sensitive runtime settings.
- Keep public frontend origins explicit.
- Do not enable wildcard CORS for controlled alpha.
- Keep synthetic-only mode enabled until approved real-data handling exists.
- SQLite is acceptable for deployment smoke prep, not final hosted durability.

## Boundary

This pack does not claim hosted live API access, production readiness, billing, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.

## V0.78 Live Hosted Smoke Notes

V0.78 keeps the same FastAPI entrypoint and start command:

```text
prmr.product.api_server_v076:app
```

```bash
uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT
```

Hosted environment variables remain:

```env
PRMR_API_MODE=hosted_alpha
PRMR_STORAGE_PATH=<host-safe-path>
PRMR_SYNTHETIC_ONLY=true
PRMR_PUBLIC_REPORTS_DIR=<host-safe-public-report-dir>
PRMR_PRIVATE_REPORTS_DIR=<host-safe-private-report-dir>
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000
PRMR_DEFAULT_REQUEST_LIMIT=100
```

If the chosen host uses an ephemeral filesystem, treat V0.78 as ephemeral hosted
smoke storage only. Persistent hosted storage hardening is a later milestone.

V0.78 live smoke uses:

```env
PRMR_HOSTED_API_URL=
PRMR_TEST_API_KEY=
PRMR_TEST_CLIENT_ID=
PRMR_TEST_VAULT_ID=
PRMR_TEST_NAMESPACE=
```

No live client access claim should be made unless `PRMR_HOSTED_API_URL` is set
and the hosted smoke checks pass.
