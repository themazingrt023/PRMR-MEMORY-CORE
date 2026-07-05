# PRMR Memory Core V0.98 External Event Contract

Truth label: V0.98 improves the generic external ingest contract and memory
visibility foundation. It does not claim long-term memory quality across weeks
of behavior, production security certification, compliance approval, legal
approval, or external validation.

## Base URL

```text
https://prmr-memory-core-api.onrender.com
```

## Authentication

Protected API routes require:

```http
Authorization: Bearer <PRMR_API_KEY>
Content-Type: application/json
```

API keys must be stored server-side only. Do not expose PRMR keys in browser
code, public logs, screenshots, source control, or `NEXT_PUBLIC_` environment
variables.

Unsupported auth formats:

- `x-api-key` is not supported
- raw `Authorization` values without the `Bearer` scheme
- browser-visible API keys

PRMR resolves client, vault, and namespace from the active key record.
Optional `X-Client-ID`, `X-Vault-ID`, and `X-Namespace` headers may be supplied
as explicit assertions. Mismatched explicit scope headers are denied.

## Public Health

```bash
curl https://prmr-memory-core-api.onrender.com/health
```

## Usage

```bash
curl https://prmr-memory-core-api.onrender.com/v1/usage \
  -H "Authorization: Bearer <PRMR_API_KEY>"
```

## Memory Ingest

Endpoint:

```text
POST /v1/events/ingest
```

### Shape A: Legacy/Internal-Compatible Batch

```json
{
  "events": [
    {
      "event_id": "evt_001",
      "user_id": "synthetic_user",
      "type": "project_updated",
      "content": "Synthetic update.",
      "timestamp": "2026-07-05T00:00:00Z",
      "timestamp_index": 1
    }
  ]
}
```

### Shape B: Generic External Batch

```json
{
  "events": [
    {
      "event_type": "external.project.updated",
      "signal": "User updated a project in an external product.",
      "metadata": {
        "source_app": "external_product",
        "project_ref": "safe_project_ref"
      },
      "occurred_at": "2026-07-05T00:00:00.000Z",
      "actor_reference": "hashed_actor",
      "workspace_reference": "hashed_workspace",
      "idempotency_key": "stable-event-id"
    }
  ]
}
```

### Shape C: Generic External Single Event

```json
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
```

Shape C is normalized internally as a one-event batch.

## Normalization

PRMR normalizes external event fields into the current internal event model:

| External field | Internal field |
| --- | --- |
| `event_id` or `idempotency_key` | `event_id` |
| `user_id` or `actor_reference` | `user_id` |
| `type` or `event_type` | `type` |
| `content`, `signal`, or `summary` | `content` |
| `timestamp` or `occurred_at` | `timestamp` |
| `timestamp_index` | `timestamp_index` |

Safe external context may be retained under sanitized metadata for future
packet improvements:

- `metadata`
- `source_app`
- `workspace_reference`
- `actor_reference`
- `idempotency_key`
- `external_event_type`
- `occurred_at`

Unknown fields should not crash ingestion. Safe unknown fields may be retained
inside sanitized metadata. Unsafe metadata is redacted.

Do not send credentials, tokens, Authorization values, API keys, payment card
details, raw file contents, database URLs, service-role keys, or sensitive file
paths.

## Continuity Packet

Endpoint:

```text
POST /v1/continuity/packet
```

```bash
curl -X POST https://prmr-memory-core-api.onrender.com/v1/continuity/packet \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Current deterministic behavior:

- reads scoped stored events;
- sorts by `timestamp_index`;
- sets `current_state` from the latest event `content`;
- derives `active_signals` from normalized event `type` values;
- creates a public-safe report ID.

The packet is deterministic memory infrastructure. It is not AI-generated and
is not a final automated decision.

## Example End-To-End

```bash
curl -X POST https://prmr-memory-core-api.onrender.com/v1/events/ingest \
  -H "Authorization: Bearer <PRMR_API_KEY>" \
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
  }'
```

Expected high-level result:

```json
{
  "status": "ok",
  "accepted_event_count": 1,
  "public_safe": true
}
```

## Boundary

Use synthetic or explicitly approved non-sensitive data unless Afternum has
approved a narrower test scope. This contract upgrade is for generic external
products and is not tailored to any single client.
