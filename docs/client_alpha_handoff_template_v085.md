# V0.85 Client Alpha Handoff Template

Use this template only after a client has been manually approved for controlled-alpha access.

Do not include raw API keys in this document. Deliver the one-time API key through the approved private delivery method.

## Subject

PRMR Memory Core controlled-alpha access details for `<CLIENT_NAME>`

## Message

Hi `<CLIENT_NAME>`,

Thank you for reviewing PRMR Memory Core with Afternum Industries.

Your controlled-alpha scope is ready for synthetic or explicitly approved test data only.

## Scope Details

```text
Client: <CLIENT_NAME>
Client ID: <CLIENT_ID>
Vault ID: <VAULT_ID>
Namespace: <NAMESPACE>
API Base URL: <API_BASE_URL>
One-time API key delivery method: <ONE_TIME_API_KEY_DELIVERY_METHOD>
Dashboard access method: <DASHBOARD_ACCESS_METHOD>
Boundary notes: <BOUNDARY_NOTES>
```

## Required API Headers

```text
Authorization: Bearer <PRMR_API_KEY>
X-Client-ID: <CLIENT_ID>
X-Vault-ID: <VAULT_ID>
X-Namespace: <NAMESPACE>
Content-Type: application/json
```

## What You Can Test

- event ingestion with synthetic/approved data
- continuity packet generation
- memory/state reconstruction
- public-safe explanations
- least-harm review actions
- public-safe report fetch
- scoped usage view
- scoped dashboard view if approved

## What Not To Do

- do not send real sensitive data unless explicitly approved
- do not share the API key in public channels
- do not paste the API key into frontend source
- do not put the API key in screenshots, public docs, public reports, or Git history
- do not treat this as production access
- do not treat this as billing, compliance approval, legal approval, or external security certification

## Revocation

Afternum can revoke the key or dashboard session when the alpha test ends, scope changes, key handling is uncertain, or you request closure.

## Feedback We Need

- Did the continuity concept make sense?
- Which endpoint or dashboard view was most useful?
- Did the client/vault/namespace model feel clear?
- What would be required before a real pilot?
- What safety, security, or workflow risks remain?

## Boundary

This is controlled-alpha access for synthetic or explicitly approved test data only. It is not self-serve signup, billing, production readiness, external validation, compliance approval, legal approval, external security certification, or real-world validation.
