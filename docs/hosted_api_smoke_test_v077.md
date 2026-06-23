# V0.77 Hosted API Smoke Test

The hosted smoke test verifies a deployed PRMR backend URL when one exists. If no URL exists, the smoke harness reports readiness without faking hosted access.

## No Hosted URL Yet

```bash
python examples/audit_v077_hosted_api_smoke.py
```

Expected result:

```text
PASS_READINESS_NEEDS_HOSTED_URL
```

This means the smoke harness is ready, but no deployed backend URL has been verified.

## With Hosted URL

```bash
$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-API-URL"
python examples/audit_v077_hosted_api_smoke.py
```

The smoke harness checks:

- `GET /health`
- missing-auth denial on a protected route
- malformed-auth denial on a protected route
- optional protected-route calls when a controlled test key and scope are provided

Optional protected-route variables:

```env
PRMR_HOSTED_API_KEY=
PRMR_HOSTED_CLIENT_ID=
PRMR_HOSTED_VAULT_ID=
PRMR_HOSTED_NAMESPACE=
```

If those optional values are absent, protected valid-flow checks are marked as not run rather than faked.

## Boundary

A URL must pass this smoke harness before PRMR claims live hosted client access.

## V0.78 Live Smoke Status Levels

V0.78 uses stricter live-smoke result labels:

- `NEEDS_HOSTED_URL`: no deployed backend URL was supplied.
- `PASS_BASIC_HOSTED_SMOKE`: hosted `/health` and auth-denial checks passed.
- `PASS_FULL_CONTROLLED_HOSTED_SMOKE`: basic checks passed and controlled protected-route checks passed with supplied test scope.
- `NEEDS_WORK`: supplied URL or smoke checks failed.

Run:

```bash
python examples/run_live_hosted_api_smoke_v078.py
```

With a hosted URL:

```powershell
$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-API-URL"
python examples/run_live_hosted_api_smoke_v078.py
```

Optional controlled test scope:

```powershell
$env:PRMR_TEST_API_KEY="CONTROLLED_TEST_KEY"
$env:PRMR_TEST_CLIENT_ID="client_demo"
$env:PRMR_TEST_VAULT_ID="vault_demo"
$env:PRMR_TEST_NAMESPACE="default"
python examples/run_live_hosted_api_smoke_v078.py
```

If the controlled test scope is missing, protected-flow smoke is marked
`SKIPPED_NEEDS_TEST_SCOPE` rather than faked.
