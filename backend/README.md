# PRMR Memory Core Backend Deployment Notes V0.77

V0.77 prepares the V0.76 FastAPI server for hosted deployment smoke testing.
It does not prove hosted live client access by itself.

## Scope

- Deployment prep for the existing FastAPI app at `prmr.product.api_server_v076:app`.
- Local and hosted smoke-test instructions.
- Environment variable plan for controlled-alpha deployment.
- No billing, no automatic key issuing, no production claim, and no external certification claim.

## Start Commands

Recommended hosted start command:

```bash
uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT
```

Local fallback when `$PORT` is not set:

```bash
uvicorn prmr.product.api_server_v076:app --host 127.0.0.1 --port 8000
```

## Environment Variables

Use host-managed environment variables. Do not commit credential values.

```env
PRMR_API_MODE=hosted_alpha
PRMR_STORAGE_PATH=/app/data/prmr_api_server.sqlite
PRMR_SYNTHETIC_ONLY=true
PRMR_PUBLIC_REPORTS_DIR=/app/reports/public
PRMR_PRIVATE_REPORTS_DIR=/app/reports/private
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000
PRMR_DEFAULT_REQUEST_LIMIT=100
```

Notes:

- Keep `PRMR_SYNTHETIC_ONLY=true` until a later approved milestone changes this.
- Keep CORS origins explicit; do not use wildcard origins for controlled alpha.
- Raw API keys should not be stored in environment variables unless a later approved deployment flow specifically requires it.
- Secrets should be handled through the host environment, not committed files.
- SQLite storage is acceptable for smoke prep only. Durable hosted storage hardening is a later milestone.

## Smoke Tests

Without a deployed URL:

```bash
python examples/audit_v077_hosted_api_smoke.py
```

Expected result: `PASS_READINESS_NEEDS_HOSTED_URL`.

With a deployed URL:

```bash
export PRMR_HOSTED_API_URL="https://YOUR-HOSTED-API-URL"
python examples/audit_v077_hosted_api_smoke.py
```

Optional protected-route variables, only if a controlled test key exists:

```env
PRMR_HOSTED_API_KEY=
PRMR_HOSTED_CLIENT_ID=
PRMR_HOSTED_VAULT_ID=
PRMR_HOSTED_NAMESPACE=
```

Hosted client access may only be claimed after a real deployed backend URL passes smoke tests.

## V0.78 Live Hosted Smoke

V0.78 changes the no-URL result from readiness-pass wording to an explicit
`NEEDS_HOSTED_URL` live-smoke status. This is intentional: deployment prep can
pass locally, but live hosted API smoke evidence needs a real public or staging
backend URL.

```bash
python examples/run_live_hosted_api_smoke_v078.py
```

With a hosted URL:

```bash
export PRMR_HOSTED_API_URL="https://YOUR-HOSTED-API-URL"
python examples/run_live_hosted_api_smoke_v078.py
```

Optional controlled protected-route variables:

```env
PRMR_TEST_API_KEY=
PRMR_TEST_CLIENT_ID=
PRMR_TEST_VAULT_ID=
PRMR_TEST_NAMESPACE=
```

If the host filesystem is ephemeral, V0.78 smoke uses ephemeral smoke storage
only. Durable hosted persistence must be addressed in V0.79/V0.80 before any
stronger hosted-storage claim is made.

## V0.78.1 First Host Path

Primary first host path: Render Web Service.

Host-specific runbook:

```text
docs/backend_host_deploy_v0781.md
```

Build command:

```bash
pip install -r requirements-api.txt
```

Start command:

```bash
uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT
```

After the host gives you a backend URL, run:

```powershell
$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-BACKEND-URL"
python examples/run_backend_hosted_smoke_v0781.py
```

This still does not claim live API access unless V0.78 smoke passes against the real URL.
