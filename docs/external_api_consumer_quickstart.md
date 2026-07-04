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
