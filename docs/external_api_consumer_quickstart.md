# PRMR External API Consumer Quickstart

Base URL:

```text
https://prmr-memory-core-api.onrender.com
```

Public health:

```bash
curl https://prmr-memory-core-api.onrender.com/health
```

Protected routes use one server-side header:

```text
Authorization: Bearer <PRMR_API_KEY>
```

The API resolves the client, vault, and namespace from the active key record.
Optional `X-Client-ID`, `X-Vault-ID`, and `X-Namespace` headers may be supplied
as explicit assertions; any mismatch is denied.

Usage test:

```bash
curl -H "Authorization: Bearer $PRMR_API_KEY" \
  https://prmr-memory-core-api.onrender.com/v1/usage
```

Synthetic event write:

```bash
curl -X POST \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"project_updated","content":"Synthetic update","timestamp_index":1}]}' \
  https://prmr-memory-core-api.onrender.com/v1/events/ingest
```

Generic external event write:

```bash
curl -X POST \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "external.project.updated",
    "signal": "User updated a project in an external product.",
    "metadata": {
      "source_app": "external_product"
    },
    "occurred_at": "2026-07-05T00:00:00.000Z",
    "actor_reference": "hashed_actor",
    "workspace_reference": "hashed_workspace",
    "idempotency_key": "stable-event-id"
  }' \
  https://prmr-memory-core-api.onrender.com/v1/events/ingest
```

PRMR also accepts a generic batch shape:

```json
{
  "events": [
    {
      "event_type": "external.project.updated",
      "signal": "User updated a project in an external product.",
      "metadata": {
        "source_app": "external_product"
      },
      "occurred_at": "2026-07-05T00:00:00.000Z",
      "actor_reference": "hashed_actor",
      "workspace_reference": "hashed_workspace",
      "idempotency_key": "stable-event-id"
    }
  ]
}
```

Generic fields are normalized into PRMR memory events: `event_type` becomes
the internal event `type`, `signal` becomes `content`, `occurred_at` becomes
`timestamp`, `actor_reference` maps to `user_id`, and `idempotency_key` may be
used as the event ID. Safe metadata is retained for future continuity packet
improvements; unsafe credential-like metadata is redacted.

Continuity packet:

```bash
curl -X POST \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://prmr-memory-core-api.onrender.com/v1/continuity/packet
```

`x-api-key` is not supported. A raw Authorization value without the `Bearer`
scheme is not supported.

Store the key in a server-side environment variable. Never put it in browser
code, public logs, screenshots, source control, or a variable named
`NEXT_PUBLIC_PRMR_API_KEY`. Raw keys are shown once and cannot be recovered
from later dashboard views.

This remains controlled-alpha infrastructure. Use synthetic or explicitly
approved non-sensitive data only.
