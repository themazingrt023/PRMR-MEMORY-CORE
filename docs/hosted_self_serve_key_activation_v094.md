# PRMR Memory Core V0.94 Hosted Self-Serve Key Activation

> Current deployment direction: V0.94.1 replaces the Render persistent-disk
> requirement below with server-side Postgres through `DATABASE_URL`. See
> `docs/postgres_durable_storage_v0941.md`. This V0.94 disk section is retained
> as historical evidence for the SQLite deployment option.

## Purpose

V0.94 exposes the generic V0.92 account/key flow and V0.93 SQLite repository
through a deployable FastAPI surface. It is not tailored to a particular client
product.

User flow:

```text
Vercel site
-> signup form
-> server-side Vercel proxy
-> local/test verification state
-> Free plan
-> generic client + vault + namespace
-> HTTP-only MVP session cookie
-> dashboard
-> copy-once API key
-> protected hosted PRMR routes
```

Real email delivery and Stripe billing are not connected. The session design is
an MVP, not production authentication hardening.

## Render persistent disk

The Render service must have a real persistent disk mounted at `/var/data`.
Confirm any provider pricing or plan requirements in the Render dashboard.

Required environment:

```env
PRMR_API_MODE=hosted_alpha
PRMR_SELF_SERVE_STORAGE_PATH=/var/data/prmr_self_serve.sqlite
PRMR_DURABLE_STORAGE_VERIFIED=true
PRMR_SYNTHETIC_ONLY=true
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app
```

Start command:

```bash
uvicorn prmr.product.api_server_v094:app --host 0.0.0.0 --port $PORT
```

Do not set `PRMR_DURABLE_STORAGE_VERIFIED=true` until `/var/data` is actually a
mounted persistent disk. `/tmp` and `/var/tmp` are ephemeral and never count as
durable storage.

The included `render.yaml` describes this path, but an existing Render service
must still be reviewed in the Render dashboard. A local file does not prove the
live service adopted the disk.

## Backend routes

Public account activation:

```text
POST /v1/self-serve/signup
POST /v1/self-serve/verify
POST /v1/self-serve/login
```

Session-scoped routes use:

```http
Authorization: Session <MVP_SESSION_TOKEN>
```

```text
POST /v1/self-serve/plan
POST /v1/self-serve/provision
GET /v1/self-serve/keys
POST /v1/self-serve/keys
PATCH /v1/self-serve/keys
DELETE /v1/self-serve/keys
GET /v1/self-serve/dashboard
```

Protected PRMR routes use the created API key plus client scope:

```http
Authorization: Bearer <PRMR_API_KEY>
X-Client-ID: <CLIENT_ID>
X-Vault-ID: <VAULT_ID>
X-Namespace: <NAMESPACE>
```

```text
POST /v1/events/ingest
POST /v1/continuity/packet
POST /v1/memory/reconstruct
POST /v1/explain
POST /v1/actions/least-harm
GET /v1/reports/{report_id}
GET /v1/usage
```

## Vercel configuration

Server-only Vercel environment:

```env
PRMR_HOSTED_API_URL=https://prmr-memory-core-api.onrender.com
```

This URL is not a credential. Do not place API keys or session tokens in
`NEXT_PUBLIC_*` variables.

Vercel proxy routes:

```text
POST /api/self-serve/activate
POST /api/self-serve/logout
GET /api/dashboard/state
GET|POST|PATCH|DELETE /api/dashboard/keys
```

The activation proxy performs signup, labelled local/test verification, login,
Free-plan selection, and scope provisioning. It stores the returned session
token in an HTTP-only, SameSite=Strict cookie. It never returns that token to
browser JavaScript.

A newly created or rotated PRMR API key is returned to the active dashboard
once. Later list and dashboard responses contain only safe previews.

## Hosted smoke

```powershell
$env:PRMR_HOSTED_API_URL="https://prmr-memory-core-api.onrender.com"
$env:PRMR_SELF_SERVE_TEST_EMAIL="hosted-smoke@example.test"
$env:PRMR_SELF_SERVE_TEST_PASSWORD="<PRIVATE_SYNTHETIC_TEST_PASSWORD>"
python examples/run_hosted_self_serve_key_activation_v094.py
```

The runner first checks `/health`. If storage is not reported as verified
`hosted_durable_sqlite`, it returns `NEEDS_HOSTED_DURABLE_STORAGE` without
creating a user or claiming a pass.

## Redeploy checkpoint

Create:

```powershell
python examples/run_hosted_self_serve_redeploy_checkpoint_v094.py --mode create_checkpoint
```

This writes a private local packet at:

```text
reports/v094/private_redeploy_checkpoint_v094.json
```

Do not commit or share that packet. Redeploy/restart Render, then verify:

```powershell
python examples/run_hosted_self_serve_redeploy_checkpoint_v094.py --mode verify_checkpoint
```

Verification must recover the user, safe key preview, usage, report reference,
and dashboard state. It also checks that the raw key cannot be recovered from
public dashboard or key-list responses.

## Current limitations

- Verification is a labelled local/test state; no verification email is sent.
- Only the Free plan activates automatically.
- Stripe is not connected.
- Session cookies and password login need production auth hardening.
- SQLite assumes a single attached persistent disk and one active writer model.
- Managed Postgres remains future work for broader concurrency and operations.
- External launch and security/compliance certification are not claimed.
