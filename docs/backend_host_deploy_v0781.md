# V0.78.1 Backend Host Deploy Runbook

Truth label: backend deployment execution prep. Hosted API access is only claimable after a real deployed URL passes V0.78 smoke.

## Primary Host Path

Primary first host: Render Web Service.

Why this path:

- The repo already has a FastAPI app entrypoint: `prmr.product.api_server_v076:app`.
- The repo already has a Uvicorn start command in `Procfile`.
- Render's official FastAPI deployment guide uses a Python web service with a build command and a Uvicorn start command that binds to `$PORT`.
- This path avoids adding Docker or changing the existing V0.76 server.

Do not treat this as a pricing, uptime, production, security, compliance, or bank-readiness claim. Confirm current host limits and pricing inside the Render dashboard before relying on them.

Reference checked: Render official FastAPI deployment docs, which show a Python service using `pip install -r requirements.txt` and `uvicorn main:app --host 0.0.0.0 --port $PORT`. This repo uses the same pattern with `requirements-api.txt` and `prmr.product.api_server_v076:app`.

## Deploy From

Deploy from the repository root:

```text
C:\Users\theam\PRMR MEMORY CORE
```

The app entrypoint is:

```text
prmr.product.api_server_v076:app
```

## Render Web Service Setup

1. Push this repository to a Git provider Render can access.
2. In Render, create a new Web Service.
3. Connect the PRMR Memory Core repository.
4. Set the root directory to the repository root unless your Git host changes the layout.
5. Use Python as the runtime/language.
6. Set the build command:

```bash
pip install -r requirements-api.txt
```

7. Set the start command:

```bash
uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT
```

Local fallback for manual testing:

```bash
uvicorn prmr.product.api_server_v076:app --host 127.0.0.1 --port 8000
```

## Hosted Environment Variables

Set these in the host environment, not in committed files:

```env
PRMR_API_MODE=hosted_alpha
PRMR_STORAGE_PATH=/tmp/prmr_api_server_v0781.sqlite
PRMR_SYNTHETIC_ONLY=true
PRMR_PUBLIC_REPORTS_DIR=/tmp/prmr-reports-public
PRMR_PRIVATE_REPORTS_DIR=/tmp/prmr-reports-private
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000
PRMR_DEFAULT_REQUEST_LIMIT=100
```

Storage path note:

- `/tmp/...` is acceptable for first smoke deployment only.
- If the host filesystem is ephemeral, smoke data can disappear across restarts or deploys.
- Persistent hosted storage must be addressed later before any durable hosted-storage claim.

CORS note:

- Keep the deployed frontend origin explicit: `https://prmr-memory-core.vercel.app`.
- Keep `http://localhost:3000` only for local development.
- Do not use wildcard CORS for controlled alpha.

Secrets note:

- Do not commit raw API keys.
- Do not place real secrets in `.env.example`.
- Use host-managed environment variables for sensitive values.

## First Hosted URL

After the service deploys, copy the generated public backend URL from the host dashboard. It will look like a host-managed HTTPS URL.

Do not claim hosted API access yet.

First check:

```powershell
$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-BACKEND-URL"
python examples/run_live_hosted_api_smoke_v078.py
```

Expected honest outcomes:

- `PASS_BASIC_HOSTED_SMOKE` if `/health` and auth-denial checks pass.
- `NEEDS_WORK` if the URL or basic checks fail.
- `NEEDS_HOSTED_URL` if the URL was not set.

## Controlled Protected Smoke

Only run the full controlled protected smoke if a controlled hosted test scope exists:

```powershell
$env:PRMR_TEST_API_KEY="CONTROLLED_TEST_KEY"
$env:PRMR_TEST_CLIENT_ID="client_demo"
$env:PRMR_TEST_VAULT_ID="vault_demo"
$env:PRMR_TEST_NAMESPACE="default"
$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-BACKEND-URL"
python examples/run_live_hosted_api_smoke_v078.py
```

Expected honest full result:

```text
PASS_FULL_CONTROLLED_HOSTED_SMOKE
```

If the controlled test scope is missing, protected smoke remains `SKIPPED_NEEDS_TEST_SCOPE`.

## Logs

Use the host dashboard logs for:

- build failures
- dependency install failures
- Uvicorn boot failures
- route errors
- missing environment variables
- filesystem write errors

The first live smoke should also check:

```text
GET /health
```

## Boundary

V0.78.1 is a runbook and deployment package only. It is not hosted API smoke evidence, not live client access, not production readiness, not billing, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.
