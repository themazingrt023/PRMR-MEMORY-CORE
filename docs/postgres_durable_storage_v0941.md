# PRMR V0.94.1 Postgres Durable Storage

## Purpose

V0.94.1 adds Postgres as an optional durable storage backend for PRMR's
self-serve account, key, usage, continuity, report, and dashboard state.
SQLite remains the default for local development.

Render Free cannot attach the persistent disk expected by the V0.94 SQLite
deployment plan. A hosted Postgres database avoids treating Render's ephemeral
filesystem as durable storage.

This is a Postgres adapter MVP. It is not real email delivery, Stripe billing,
production authentication hardening, compliance approval, legal approval, or
external security certification.

## Storage backends

### Local SQLite

```text
PRMR_STORAGE_BACKEND=sqlite
PRMR_SELF_SERVE_STORAGE_PATH=reports/v094/prmr_self_serve_local.sqlite
PRMR_DURABLE_STORAGE_VERIFIED=false
```

SQLite is the default when `PRMR_STORAGE_BACKEND` is unset.

### Hosted Postgres

```text
PRMR_STORAGE_BACKEND=postgres
DATABASE_URL=<POOLED_POSTGRES_CONNECTION_STRING>
PRMR_DURABLE_STORAGE_VERIFIED=true
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app
```

`DATABASE_URL` is a server-only secret. Never put it in frontend variables,
public reports, source control, screenshots, tickets, or client handoff files.
Use a fresh provider connection string and rotate it if exposure is suspected.

Set `PRMR_DURABLE_STORAGE_VERIFIED=true` only after the application connects,
initializes the schema, and `/health` reports:

```json
{
  "storage_backend": "postgres",
  "storage_mode": "hosted_managed_postgres",
  "database_connected": true,
  "durable_storage_verified": true,
  "durable_storage_claim_allowed": true,
  "database_url_exposed": false
}
```

## Provider path

The first hosted database can be Neon Postgres or Supabase Postgres. Use the
provider's pooled server connection string. Render is a long-running server,
but a pooled URL still gives a safer connection ceiling for early hosted use.

For Supabase:

1. Create a project and copy a pooled Postgres URI from the Connect panel.
2. Keep PRMR tables in the private `prmr_self_serve` schema.
3. Do not add `prmr_self_serve` to Supabase Data API exposed schemas.
4. If the project does not use Supabase REST or GraphQL, disable the Data API.
5. Use a dedicated least-privilege database role before external alpha.

PRMR connects directly from the Render backend. The browser and Vercel
frontend never receive the Postgres URI.

References:

* Supabase database connections:
  <https://supabase.com/docs/guides/database/connecting-to-postgres>
* Supabase API hardening:
  <https://supabase.com/docs/guides/api/securing-your-api>
* Psycopg installation:
  <https://www.psycopg.org/psycopg3/docs/basic/install.html>

## Schema and persistence

Initialization uses `CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`,
and `CREATE INDEX IF NOT EXISTS`. It does not drop, truncate, or clear tables.
State saves use idempotent upserts. Historical log rows use stable fingerprints
so repeated snapshots do not duplicate the same records.

The private schema contains:

* users and email verification state
* hashed sessions
* plans and monthly usage
* clients, vaults, namespaces, and usage limits
* API key hashes, fingerprints, safe previews, and lifecycle state
* usage events and request logs
* continuity events, packets, and public/private reports
* public-safe dashboard snapshots
* audit metadata

Raw passwords and raw API keys are never persisted. Raw credentials are
returned only through their existing copy-once response paths.

## Render configuration

Deploy from the repository root.

Build command:

```text
pip install -r requirements-api.txt
```

Start command:

```text
uvicorn prmr.product.api_server_v094:app --host 0.0.0.0 --port $PORT
```

Render environment:

```text
PRMR_API_MODE=hosted_alpha
PRMR_STORAGE_BACKEND=postgres
DATABASE_URL=<POOLED_POSTGRES_CONNECTION_STRING>
PRMR_DURABLE_STORAGE_VERIFIED=true
PRMR_SYNTHETIC_ONLY=true
PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app
```

Do not put the database URL in `render.yaml`. Its `sync: false` entry requires
the operator to enter the value privately in Render.

## Verification

Before configuring a database:

```powershell
python examples/run_postgres_durable_storage_v0941.py
```

Expected honest result:

```text
NEEDS_DATABASE_URL
```

With a fresh pooled database URL set privately:

```powershell
$env:DATABASE_URL="<POOLED_POSTGRES_CONNECTION_STRING>"
$env:PRMR_STORAGE_BACKEND="postgres"
$env:PRMR_DURABLE_STORAGE_VERIFIED="true"
python examples/run_postgres_durable_storage_v0941.py
```

Expected only after a real connection and full persistence flow:

```text
PASS
```

After Render redeploys:

```powershell
$env:PRMR_HOSTED_API_URL="https://prmr-memory-core-api.onrender.com"
$env:PRMR_SELF_SERVE_TEST_EMAIL="<CONTROLLED_TEST_EMAIL>"
python examples/run_hosted_self_serve_key_activation_v094.py
```

The V0.94 hosted smoke accepts either verified durable SQLite or verified
Postgres. A health response that merely says `postgres` without a successful
connection and explicit verification does not pass.

## Current limitations

* Local/test email verification remains simulated.
* Stripe and automatic billing are not connected.
* Authentication is still an MVP, not production-hardened auth.
* Horizontal multi-process write coordination has not been load-tested.
* Hosted Postgres persistence is not proven until the real `DATABASE_URL`
  runner and hosted V0.94 smoke both pass.
* Use synthetic or approved non-sensitive data only.
