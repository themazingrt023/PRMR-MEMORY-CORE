# V0.85 Client API Quickstart

This quickstart is for approved controlled-alpha clients using synthetic or explicitly approved test data only.

Truth label: controlled-alpha onboarding documentation and client-readiness evidence only. This is not self-serve signup, billing, production readiness, compliance approval, legal approval, external security certification, or real-world validation.

## Placeholders

Use placeholders in shared docs and examples:

```text
<PRMR_API_KEY>
<CLIENT_ID>
<VAULT_ID>
<NAMESPACE>
<API_BASE_URL>
<REPORT_ID>
<PACKET_ID>
```

Do not paste real keys into docs, frontend code, screenshots, public reports, or browser-visible JSON.

## Base URL

```text
https://prmr-memory-core-api.onrender.com
```

Use:

```text
<API_BASE_URL>
```

## Required Headers

```text
Authorization: Bearer <PRMR_API_KEY>
X-Client-ID: <CLIENT_ID>
X-Vault-ID: <VAULT_ID>
X-Namespace: <NAMESPACE>
Content-Type: application/json
```

## GET /health

```bash
curl "<API_BASE_URL>/health"
```

Safe response shape:

```json
{
  "status": "ok",
  "public_safe": true,
  "storage_boundary_v083": {
    "storage_mode": "hosted_ephemeral_sqlite",
    "durable_storage_verified": false
  }
}
```

## POST /v1/events/ingest

```bash
curl -X POST "<API_BASE_URL>/v1/events/ingest" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "event_id": "evt_quickstart_001",
        "user_id": "synthetic_user",
        "type": "context_update",
        "content": "Synthetic event for controlled-alpha continuity testing.",
        "timestamp": "2026-06-23T12:00:00Z",
        "timestamp_index": 1
      }
    ]
  }'
```

## POST /v1/continuity/packet

```bash
curl -X POST "<API_BASE_URL>/v1/continuity/packet" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>"
```

Safe response includes:

```json
{
  "status": "ok",
  "packet_id": "<PACKET_ID>",
  "report_id": "<REPORT_ID>",
  "public_safe": true
}
```

## POST /v1/memory/reconstruct

```bash
curl -X POST "<API_BASE_URL>/v1/memory/reconstruct" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>" \
  -H "Content-Type: application/json" \
  -d '{ "packet_id": "<PACKET_ID>" }'
```

## POST /v1/explain

```bash
curl -X POST "<API_BASE_URL>/v1/explain" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>" \
  -H "Content-Type: application/json" \
  -d '{ "packet_id": "<PACKET_ID>" }'
```

## POST /v1/actions/least-harm

```bash
curl -X POST "<API_BASE_URL>/v1/actions/least-harm" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>" \
  -H "Content-Type: application/json" \
  -d '{ "packet_id": "<PACKET_ID>" }'
```

This endpoint returns review support only. It does not make final automated decisions.

## GET /v1/reports/{report_id}

```bash
curl "<API_BASE_URL>/v1/reports/<REPORT_ID>" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>"
```

## GET /v1/usage

```bash
curl "<API_BASE_URL>/v1/usage" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>"
```

Usage should be scoped to the requesting client.

## GET /v1/dashboard/state

API-key path:

```bash
curl "<API_BASE_URL>/v1/dashboard/state" \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "X-Client-ID: <CLIENT_ID>" \
  -H "X-Vault-ID: <VAULT_ID>" \
  -H "X-Namespace: <NAMESPACE>"
```

Dashboard-session path, if separately approved:

```bash
curl "<API_BASE_URL>/v1/dashboard/state" \
  -H "X-Dashboard-Token: <DASHBOARD_SESSION_TOKEN>" \
  -H "X-Client-ID: <CLIENT_ID>"
```

Do not expose dashboard session tokens in browser source or public reports.

## Boundary

Use controlled-alpha data only. Do not send real sensitive data unless Afternum explicitly approves the scope. Durable hosted persistence remains a separate milestone before real external alpha records.
