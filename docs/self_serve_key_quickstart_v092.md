# V0.92 API Key Quickstart

## Server environment

```dotenv
PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<YOUR_PRMR_KEY>
PRMR_CLIENT_ID=<CLIENT_ID>
PRMR_VAULT_ID=<VAULT_ID>
PRMR_NAMESPACE=default
```

Keep these variables on the server. Never expose `PRMR_API_KEY` through
frontend JavaScript, browser storage, `NEXT_PUBLIC_*`, public logs, or reports.

## Ingest an event

```bash
curl "$PRMR_API_BASE_URL/v1/events/ingest" \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "X-Client-ID: $PRMR_CLIENT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "<CLIENT_ID>",
    "vault_id": "<VAULT_ID>",
    "namespace": "default",
    "events": [{
      "event_id": "evt_example_001",
      "type": "project_updated",
      "content": "A synthetic project moved into review.",
      "timestamp_index": 1
    }]
  }'
```

Use synthetic or approved non-sensitive data during the MVP. Continue with
`POST /v1/continuity/packet`, `POST /v1/memory/reconstruct`,
`POST /v1/explain`, `POST /v1/actions/least-harm`,
`GET /v1/reports/{report_id}`, and `GET /v1/usage`.

## Lifecycle

- Creation returns the credential once.
- Listing shows a safe preview only.
- Rotation immediately blocks the old key and returns the replacement once.
- Revocation immediately blocks the revoked key.
- Free-plan requests are blocked after the monthly quota is reached.

V0.92 does not claim production authentication, live billing, real email
delivery, durable hosted self-serve storage, or external certification.
