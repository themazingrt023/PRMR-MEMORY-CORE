# V0.85 Client Alpha Onboarding Pack

PRMR Memory Core is continuity infrastructure from Afternum Industries. It helps systems turn messy event histories into smaller, safer continuity packets that preserve what changed, what still matters, what became stale, and what needs review.

Truth label: controlled-alpha onboarding documentation and client-readiness evidence only. This is not self-serve signup, billing, production readiness, external validation, compliance approval, legal approval, external security certification, or real-world validation.

## What Problem PRMR Solves

Most systems store data, logs, chats, tickets, transactions, summaries, or vectors. Storage alone does not reliably preserve what changed over time, what is still active, what is stale, or what should be reviewed before the next action.

PRMR Memory Core provides a continuity layer:

- ingest synthetic or approved events
- generate continuity packets
- reconstruct current state
- create public-safe explanations
- recommend least-harm review actions
- expose scoped usage/report/dashboard evidence

## What The Client Receives

An approved controlled-alpha client receives:

- `<CLIENT_ID>`
- `<VAULT_ID>`
- `<NAMESPACE>`
- `<API_BASE_URL>`
- one fresh API key delivered privately through `<ONE_TIME_API_KEY_DELIVERY_METHOD>`
- dashboard access details through `<DASHBOARD_ACCESS_METHOD>` if approved
- boundary notes and data-use limits

The API key is not included in this document. It must be delivered once through a private approved channel.

## Base API URL

Hosted backend:

```text
https://prmr-memory-core-api.onrender.com
```

Use the placeholder in client handoff materials:

```text
<API_BASE_URL>
```

## Identity And Scope

`client_id` identifies the approved alpha client.

`vault_id` identifies the client's scoped storage area.

`namespace` separates a specific context, test, product surface, or environment inside the vault.

Requests must stay inside the approved client/vault/namespace scope. Cross-client, wrong-vault, and wrong-namespace requests are expected to be blocked.

## Required Headers

```text
Authorization: Bearer <PRMR_API_KEY>
X-Client-ID: <CLIENT_ID>
X-Vault-ID: <VAULT_ID>
X-Namespace: <NAMESPACE>
Content-Type: application/json
```

Dashboard access, when approved, uses a separate dashboard session path. Do not put raw dashboard tokens in frontend source, public docs, screenshots, or browser-visible JSON.

## Safe Example Request

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
        "event_id": "evt_alpha_example_001",
        "user_id": "synthetic_user_alpha",
        "type": "support_context_update",
        "content": "Synthetic user context changed after a support interaction.",
        "timestamp": "2026-06-23T12:00:00Z",
        "timestamp_index": 1
      }
    ]
  }'
```

## Safe Example Response

```json
{
  "status": "ok",
  "operation": "events_ingest",
  "client_id": "<CLIENT_ID>",
  "vault_id": "<VAULT_ID>",
  "namespace": "<NAMESPACE>",
  "accepted_event_count": 1,
  "public_safe": true
}
```

## Dashboard Access

Dashboard access is controlled and scoped. A dashboard token is separate from an API key. It must be handled server-side or through an approved private access method.

The dashboard may show:

- client overview
- safe key previews and hash prefixes only
- vault/namespace scope
- usage counts
- request log summaries
- public-safe report summaries
- memory health

The dashboard must not show raw API keys, raw dashboard tokens, unrelated client state, private internal traces, or real sensitive data unless explicitly approved.

## Reporting

Public reports contain public-safe summaries only. Private/internal reports are for Afternum operator review and may include debug or synthetic trace details, but should still avoid raw secrets unless a local one-time private key packet explicitly requires it.

Client-facing report access is scoped by client ID, vault ID, namespace, and key/session authorization.

## Usage And Logs

Usage logs and request logs are scoped per client. Clients should only see their own usage counts, blocked request summaries, reports, and dashboard state.

Blocked requests may appear as safety evidence, but failed auth must not create successful work artifacts.

## Revoke Process

Afternum may revoke API keys or dashboard sessions when:

- the alpha test ends
- scope changes
- key handling is uncertain
- a client requests closure
- there is any concern about exposure

After revocation, requests using that key/session should be blocked.

## Boundaries And Limitations

- Controlled alpha only.
- Synthetic or explicitly approved test data only.
- No real sensitive data unless separately approved.
- No self-serve signup.
- No billing.
- This is not production readiness.
- No production readiness claim.
- No compliance approval, legal approval, or external security certification.
- Current hosted smoke evidence does not replace durable storage verification.
- Render `/tmp` storage is smoke-only; durable hosted persistence requires a separate milestone.

## Feedback Guidance

Useful feedback:

- Did continuity feel different from summaries or vector search?
- Which endpoint or output felt most useful?
- Was client/vault/namespace scoping clear?
- Was the dashboard understandable?
- What would you need before a real pilot?
- What security, data, or workflow concerns remain?
