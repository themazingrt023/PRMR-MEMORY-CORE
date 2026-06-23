# PRMR V0.57 API Examples

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.57

## Boundary

These examples are public-safe controlled-alpha examples. They use synthetic/demo values only. They do not show real secrets, real sensitive data, restricted diagnostics, or production credentials.

## POST /v1/events/ingest

Purpose: send scoped events.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "events": [
    {
      "event_id": "evt_demo_001",
      "entity_id": "agent_demo_001",
      "entity_type": "agent_memory",
      "timestamp": "2026-06-20T15:01:00Z",
      "event_type": "state_change",
      "state_before": "new workspace session",
      "state_after": "project preference recorded",
      "signal_type": "preference_origin",
      "status": "active",
      "trust_level": "trusted"
    }
  ],
  "metadata": {
    "dataset_type": "synthetic"
  }
}
```

Response:

```json
{
  "ok": true,
  "accepted_event_count": 1,
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default"
}
```

## POST /v1/continuity/packet

Purpose: generate a continuity packet.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "entity_id": "agent_demo_001"
}
```

Response:

```json
{
  "ok": true,
  "packet": {
    "packet_id": "pkt_demo_001",
    "entity_id": "agent_demo_001",
    "current_state": "agent can continue with current project preference",
    "active_signals": ["continuity_ready"],
    "stale_signals": ["outdated_setup_note"],
    "continuity_summary": "Current state preserves active and stale signals for review."
  }
}
```

## POST /v1/memory/reconstruct

Purpose: reconstruct useful current state.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001"
}
```

Response:

```json
{
  "ok": true,
  "reconstruction_match": true,
  "reconstructable_state": {
    "current_state": "agent can continue with current project preference",
    "active_signals": ["continuity_ready"],
    "stale_signals": ["outdated_setup_note"]
  }
}
```

## POST /v1/explain

Purpose: request a public-safe explanation.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001",
  "audience": "customer_safe"
}
```

Response:

```json
{
  "ok": true,
  "explanation": {
    "summary": "We noticed activity that may need review before continuing.",
    "customer_next_step": "Please confirm whether you recognize the change.",
    "review_boundary": "This is a review step, not a final conclusion."
  }
}
```

## POST /v1/actions/least-harm

Purpose: request a proportionate next-step boundary.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001"
}
```

Response:

```json
{
  "ok": true,
  "recommended_action": "request_evidence",
  "allowed_actions": [
    "do_nothing",
    "warn",
    "request_evidence",
    "human_review",
    "keep_dormant"
  ],
  "not_final_decision": true
}
```

## GET /v1/reports/{report_id}

Purpose: fetch a public-safe report preview.

Request:

```http
GET /v1/reports/rep_demo_001
Authorization: Bearer <redacted local alpha token>
X-PRMR-Client-ID: client_alpha
X-PRMR-Vault-ID: alpha_vault
X-PRMR-Namespace: default
```

Response:

```json
{
  "ok": true,
  "report": {
    "report_id": "rep_demo_001",
    "public_safe": true,
    "summary": "Continuity packet generated for controlled alpha review."
  }
}
```

## GET /v1/usage

Purpose: return scoped usage counts.

Response:

```json
{
  "ok": true,
  "usage": {
    "events_ingested": 4,
    "packets_generated": 1,
    "reports_created": 1,
    "reports_read": 1
  }
}
```

## POST /v1/keys/rotate

Purpose: rotate an active local alpha credential.

Response:

```json
{
  "ok": true,
  "rotated": true,
  "old_key_status": "revoked",
  "new_key_delivery": "show_once_or_out_of_band"
}
```

Boundary: browser code should never receive raw credential material.

## POST /v1/keys/revoke

Purpose: revoke an active local alpha credential.

Response:

```json
{
  "ok": true,
  "revoked": true
}
```

Boundary: revoked credentials must not authorize future requests.
