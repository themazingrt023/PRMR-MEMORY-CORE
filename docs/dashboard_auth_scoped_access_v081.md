# V0.81 Dashboard Auth And Scoped Client Access

V0.81 adds a local/deployable dashboard access layer for controlled alpha evidence.

Truth label: dashboard scoped access evidence only. This is not full production authentication, not self-serve login, not billing, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## What It Proves

V0.81 proves that a synthetic dashboard session can be scoped to one controlled alpha client and that wrong-client access is blocked.

The local smoke verifies:

- client A can view client A dashboard state
- client A cannot view client B dashboard state
- missing dashboard token is blocked
- invalid dashboard token is blocked
- revoked dashboard token is blocked
- dashboard state contains client overview, vault/namespace, usage, request logs, reports, and memory health
- dashboard state shows safe key preview/hash-prefix only
- raw API keys and raw dashboard tokens are not in public reports

## How Scoped Access Works

The V0.81 module creates a synthetic dashboard session token for one client.

Internally:

- the raw dashboard token is generated at runtime
- only a token hash and safe token preview are stored
- access validation compares token hash and requested client ID
- dashboard state is assembled only for the authorized client
- wrong-client requests return a public-safe denial

The dashboard token is separate from alpha API keys. API key records shown in dashboard state contain safe previews and hash prefixes only.

## Controlled Alpha Handling

Founder/operator steps for controlled alpha:

1. Manually approve the alpha client.
2. Create or confirm the client, vault, and namespace.
3. Issue alpha API access through the manual onboarding workflow.
4. Create a scoped dashboard session only for that client.
5. Share access through a private approved channel.
6. Revoke dashboard access when the test ends or scope changes.

## Frontend Behavior

Local mode may show a synthetic dashboard preview.

Public frontend mode must not expose real dashboard data without controlled auth. If auth is missing, the frontend shows a locked controlled-alpha dashboard placeholder.

No raw API keys or raw dashboard tokens should be exposed in frontend source, public reports, browser-visible payloads, or screenshots.

## What It Does Not Prove

V0.81 does not prove:

- production authentication
- self-serve login
- hosted dashboard account management
- durable hosted account storage
- billing
- real external alpha client usage
- compliance approval
- legal approval
- external security certification
- real-world validation

## Commands

```powershell
python examples/run_dashboard_auth_scoped_access_v081.py
python examples/audit_v081_dashboard_auth_scoped_access.py
```

If frontend files changed:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Boundary

V0.81 is dashboard scoped access evidence only. It is not full production auth, not self-serve login, not billing, not production readiness, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.
