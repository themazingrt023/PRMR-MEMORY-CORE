# PRMR Five-Minute Quickstart

Truth label: self-serve alpha quickstart. Use synthetic data by default. This is not a production certification or external validation claim.

## 1. Store Server Environment Variables

```bash
PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<YOUR_COPY_ONCE_PRMR_KEY>
```

Scope headers are optional assertions. PRMR can infer client, vault, and namespace from the API key.

## 2. Check Health

```bash
curl "$PRMR_API_BASE_URL/health"
```

## 3. Send One Event

```bash
curl -X POST "$PRMR_API_BASE_URL/v1/events/ingest" \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "event_type": "demo.task_completed",
      "signal": "A synthetic demo task was completed.",
      "application_reference": "app_main",
      "actor_reference": "user_123",
      "workspace_reference": "workspace_demo",
      "entity_reference": "task_demo",
      "occurred_at": "2026-07-20T12:00:00Z",
      "metadata": { "synthetic": true },
      "idempotency_key": "demo-task-completed-001"
    }]
  }'
```

## 4. Generate One Continuity Packet

```bash
curl -X POST "$PRMR_API_BASE_URL/v1/continuity/packet" \
  -H "Authorization: Bearer $PRMR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "application_reference": "app_main",
    "actor_reference": "user_123",
    "workspace_reference": "workspace_demo",
    "entity_reference": "task_demo"
  }'
```

## TypeScript Example

```ts
const response = await fetch(`${process.env.PRMR_API_BASE_URL}/v1/events/ingest`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${process.env.PRMR_API_KEY}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    events: [{
      event_type: "demo.task_completed",
      signal: "A synthetic demo task was completed.",
      application_reference: "app_main",
      actor_reference: "user_123",
      workspace_reference: "workspace_demo",
      entity_reference: "task_demo",
      metadata: { synthetic: true }
    }]
  })
});
```

## Python Example

```python
import os
import requests

response = requests.post(
    f"{os.environ['PRMR_API_BASE_URL']}/v1/continuity/packet",
    headers={"Authorization": f"Bearer {os.environ['PRMR_API_KEY']}"},
    json={
        "application_reference": "app_main",
        "actor_reference": "user_123",
        "workspace_reference": "workspace_demo",
        "entity_reference": "task_demo",
    },
    timeout=20,
)
print(response.json())
```

No browser or frontend bundle should contain the API key.
