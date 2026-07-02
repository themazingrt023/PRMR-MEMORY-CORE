# V0.82 Hosted Dashboard To Hosted API Connection

V0.82 creates a safe bridge pattern between the frontend dashboard and hosted backend dashboard state.

Truth label: hosted dashboard connection evidence only. This is not production login, not self-serve dashboard access, not billing, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## How The Connection Works

The dashboard connection uses a server-side proxy pattern:

1. Browser requests the frontend proxy route: `/api/dashboard/state`.
2. The proxy stays locked by default.
3. If controlled dashboard access is explicitly enabled, the proxy calls the hosted backend dashboard state endpoint.
4. The backend receives only server-side headers:
   - `X-Dashboard-Token`
   - `X-Client-ID`
5. The backend validates the dashboard session token and client scope.
6. The backend returns public-safe dashboard state only.

The browser must never receive raw API keys or raw dashboard tokens.

## Backend Adapter

V0.82 introduces:

`prmr/product/hosted_dashboard_connection_v082.py`

The adapter models deployable hosted dashboard access using the V0.81 dashboard auth layer. It validates:

- valid dashboard token
- requested client ID
- wrong-client denial
- missing token denial
- invalid token denial
- revoked token denial

The adapter returns safe dashboard state with:

- client overview
- safe API key preview/hash-prefix
- vault/namespace panel
- usage overview
- request log summary
- public-safe report panel
- memory health panel

## Frontend Proxy Route

V0.82 adds:

`frontend/app/api/dashboard/state/route.ts`

The proxy route:

- is locked by default
- can return local synthetic preview only when local preview is explicitly enabled
- calls the backend only when `CONTROLLED_DASHBOARD_ACCESS_ENABLED=true`
- keeps `PRMR_DASHBOARD_TOKEN` server-side
- never hardcodes dashboard tokens
- never exposes API keys
- removes obvious raw credential fields from the returned payload

## Environment Variables

Server-side controlled dashboard access variables:

```text
CONTROLLED_DASHBOARD_ACCESS_ENABLED=false
PRMR_HOSTED_API_URL=https://prmr-memory-core-api.onrender.com
PRMR_DASHBOARD_CLIENT_ID=
PRMR_DASHBOARD_TOKEN=
```

Optional local synthetic preview:

```text
LOCAL_DASHBOARD_PREVIEW_ENABLED=true
```

Do not put real dashboard tokens in frontend source, tracked docs, public reports, screenshots, or browser-visible JSON.

## What Is Safe To Expose

Safe:

- client ID for synthetic/manual alpha scope
- safe key preview
- key hash prefix
- vault ID and namespace for the scoped client
- usage counts
- public-safe request summaries
- public-safe report IDs/summaries
- memory health counts

Not safe:

- raw API keys
- raw dashboard tokens
- private internal traces
- unrelated client state
- real sensitive client data

## What V0.82 Proves

V0.82 proves that the dashboard bridge can remain locked by default, can use a server-side proxy, and can fetch scoped public-safe dashboard state only through controlled access.

It also proves that missing, invalid, wrong-client, and revoked dashboard session paths are blocked.

## What V0.82 Does Not Prove

V0.82 does not prove:

- production login
- self-serve dashboard access
- hosted account management
- durable hosted dashboard storage
- billing
- real external alpha client usage
- compliance approval
- legal approval
- external security certification
- real-world validation

## Commands

```powershell
python examples/run_hosted_dashboard_connection_v082.py
python examples/audit_v082_hosted_dashboard_connection.py
```

Inside `frontend/`:

```powershell
npm run build
npm run typecheck
```
