# PRMR Memory Core V0.52.0 Alpha API Contract

Company: Afternum Industries
Product: PRMR Memory Core
Status: Controlled alpha sandbox contract

## Purpose

This document defines the intended API contract for a controlled alpha sandbox.

It is a specification, not a hosted production API implementation.

Current truth state:

- V0.50 Whole Core Truth Gauntlet: PASS
- V0.51 Product Clarity Pack: complete
- V0.51.1 Ten-Piece Architecture Coverage Test: PASS

Boundary:

- Internal benchmark and simulation evidence only.
- No production certification.
- No bank approval.
- No compliance approval.
- No external security certification.
- No real sensitive data unless explicitly approved for a controlled evaluation.
- No final punitive decisions may be made from alpha outputs.

## Authentication

All endpoints require API key authentication.

Required headers:

```http
Authorization: Bearer <api_key>
X-PRMR-Client-ID: <client_id>
X-PRMR-Vault-ID: <vault_id>
X-PRMR-Namespace: <namespace>
```

Rules:

- `client_id` identifies the alpha client.
- `vault_id` scopes memory and report access.
- `namespace` separates workloads inside a vault.
- API keys must be active and scoped to the requested client and vault.
- Revoked or rotated-out keys must be rejected.
- Cross-client and cross-vault access must be rejected.
- Keys must not be returned in reports, logs, explanations, or customer-safe packets.

## Common Request Envelope

Most POST endpoints use this envelope:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "request_id": "req_001",
  "metadata": {
    "source": "controlled_alpha",
    "dataset_type": "synthetic_or_approved"
  }
}
```

## Event Schema

Events represent state changes, evidence updates, stale signals, or review-relevant observations.

```json
{
  "event_id": "evt_001",
  "entity_id": "acct_001",
  "entity_type": "account",
  "timestamp": "2026-06-20T12:00:00Z",
  "event_type": "current_state",
  "state_before": "ordinary account activity",
  "state_after": "unusual recipient introduced",
  "signal_type": "risk_signal",
  "status": "active",
  "trust_level": "trusted",
  "evidence": [
    {
      "evidence_id": "ev_001",
      "kind": "customer_note",
      "summary": "Customer reported unfamiliar recipient.",
      "supports": ["unusual_recipient"],
      "limits": ["not a final decision"]
    }
  ],
  "counter_evidence": [],
  "tags": ["synthetic", "controlled_alpha"]
}
```

Required event fields:

- `event_id`
- `entity_id`
- `entity_type`
- `timestamp`
- `event_type`
- `state_before`
- `state_after`
- `signal_type`
- `status`
- `trust_level`

Allowed `status` values:

- `active`
- `historical`
- `stale`
- `unresolved`
- `cleared`

Allowed `trust_level` values:

- `trusted`
- `untrusted`
- `needs_review`

## Continuity Packet Schema

Continuity packets summarize what changed, what matters now, what became stale, and what needs review.

```json
{
  "packet_id": "pkt_001",
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "entity_id": "acct_001",
  "current_state": "unusual recipient introduced",
  "previous_state": "ordinary account activity",
  "meaningful_changes": [
    "recipient changed from known pattern to unfamiliar recipient"
  ],
  "active_signals": [
    "unusual_recipient"
  ],
  "stale_signals": [],
  "counter_evidence": [],
  "unresolved_endpoints": [
    "recipient_identity_unknown"
  ],
  "evidence_summary": [
    {
      "evidence_id": "ev_001",
      "supports": ["unusual_recipient"],
      "confidence": "needs_review"
    }
  ],
  "recommended_next_step": "human_review",
  "human_review_required": true
}
```

## Explanation Packet Schema

Internal explanation packet:

```json
{
  "explanation_id": "exp_001",
  "packet_id": "pkt_001",
  "supporting_evidence": ["ev_001"],
  "counter_evidence": [],
  "reasoning_summary": "The current state changed because an unfamiliar recipient was introduced.",
  "review_boundary": "This explanation supports review only and is not a final punitive decision.",
  "sensitive_details_allowed": true
}
```

Customer-safe explanation packet:

```json
{
  "explanation_id": "exp_001_public",
  "packet_id": "pkt_001",
  "summary": "We noticed activity that may need review before continuing.",
  "customer_next_step": "Please confirm whether you recognize the recipient.",
  "review_boundary": "This is a review step, not a final conclusion.",
  "sensitive_details_allowed": false
}
```

## Least-Harm Action Schema

```json
{
  "action_id": "act_001",
  "packet_id": "pkt_001",
  "recommended_action": "human_review",
  "allowed_actions": [
    "do_nothing",
    "warn",
    "request_evidence",
    "pause_suspicious_funds",
    "protect_victim",
    "human_review",
    "release_cleared_funds",
    "mark_false_positive",
    "keep_dormant"
  ],
  "proportionality": "least_harm_available",
  "human_review_required": true,
  "not_allowed": [
    "final_punitive_decision",
    "automatic_account_closure",
    "public_accusation"
  ]
}
```

## Report Boundary

Public/private report separation is required.

Public reports may include:

- endpoint coverage
- status counts
- public-safe summaries
- non-sensitive metrics
- public-safe report IDs

Private reports may include:

- inspected evidence paths
- debug details
- internal reasoning traces
- restricted evidence summaries

Public reports must not include:

- raw API keys
- private packet field names
- protected engine internals
- customer-sensitive evidence
- detection-secret details

## Endpoints

### POST /v1/events/ingest

Purpose:
Accept raw alpha events and store them under the authenticated client, vault, and namespace.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "events": [
    {
      "event_id": "evt_001",
      "entity_id": "acct_001",
      "entity_type": "account",
      "timestamp": "2026-06-20T12:00:00Z",
      "event_type": "current_state",
      "state_before": "ordinary account activity",
      "state_after": "unusual recipient introduced",
      "signal_type": "risk_signal",
      "status": "active",
      "trust_level": "trusted"
    }
  ]
}
```

Response:

```json
{
  "ok": true,
  "ingested_events": 1,
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default"
}
```

### POST /v1/continuity/packet

Purpose:
Generate a continuity packet for one entity or scope from ingested or supplied events.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "entity_id": "acct_001",
  "include_stale_signals": true,
  "include_counter_evidence": true
}
```

Response:

```json
{
  "ok": true,
  "packet": {
    "packet_id": "pkt_001",
    "entity_id": "acct_001",
    "current_state": "unusual recipient introduced",
    "recommended_next_step": "human_review",
    "human_review_required": true
  }
}
```

### POST /v1/memory/reconstruct

Purpose:
Reconstruct scoped memory rows or continuity state for verification.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_001",
  "mode": "continuity_state"
}
```

Response:

```json
{
  "ok": true,
  "reconstruction_match": true,
  "entity_id": "acct_001",
  "state": {
    "current_state": "unusual recipient introduced",
    "previous_state": "ordinary account activity"
  }
}
```

### POST /v1/explain

Purpose:
Create internal and customer-safe explanation packets.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_001",
  "audience": "customer_safe"
}
```

Response:

```json
{
  "ok": true,
  "explanation": {
    "summary": "We noticed activity that may need review before continuing.",
    "customer_next_step": "Please confirm whether you recognize the recipient.",
    "review_boundary": "This is a review step, not a final conclusion."
  }
}
```

### POST /v1/actions/least-harm

Purpose:
Recommend a proportionate next action while preserving human review.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_001",
  "available_actions": [
    "do_nothing",
    "warn",
    "request_evidence",
    "pause_suspicious_funds",
    "protect_victim",
    "human_review",
    "release_cleared_funds",
    "mark_false_positive",
    "keep_dormant"
  ]
}
```

Response:

```json
{
  "ok": true,
  "recommended_action": "human_review",
  "human_review_required": true,
  "not_final_decision": true
}
```

### GET /v1/reports/{report_id}

Purpose:
Return a public-safe report by ID when the authenticated client has access.

Response:

```json
{
  "ok": true,
  "report_id": "rep_001",
  "public_safe": true,
  "report_type": "continuity_alpha_summary",
  "summary": "Continuity packet generated and human review preserved."
}
```

### GET /v1/usage

Purpose:
Return alpha usage for the authenticated client and vault.

Response:

```json
{
  "ok": true,
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "events_ingested": 100,
  "packets_generated": 12,
  "reports_created": 4
}
```

### POST /v1/keys/rotate

Purpose:
Rotate an active API key and return only safe status information.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "reason": "scheduled_rotation"
}
```

Response:

```json
{
  "ok": true,
  "rotated": true,
  "old_key_status": "revoked",
  "new_key_delivery": "out_of_band_or_show_once"
}
```

### POST /v1/keys/revoke

Purpose:
Revoke an active API key.

Request:

```json
{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "reason": "manual_revoke"
}
```

Response:

```json
{
  "ok": true,
  "revoked": true
}
```

## Error Codes

```json
{
  "ok": false,
  "error": {
    "code": "invalid_key",
    "message": "Request is not authorized."
  }
}
```

Required error codes:

- `missing_auth`
- `invalid_key`
- `revoked_key`
- `vault_denied`
- `namespace_denied`
- `payload_invalid`
- `payload_too_large`
- `report_not_found`
- `rate_limited`
- `alpha_boundary_violation`
- `unsupported_operation`

## Alpha Safety Boundaries

The controlled alpha sandbox must enforce these limits:

- Use synthetic data or explicitly approved datasets only.
- Do not upload real sensitive data unless approved.
- Do not use outputs for final punitive decisions.
- Do not use alpha access as production fraud infrastructure.
- Do not claim bank certification.
- Do not claim compliance approval.
- Do not claim production security certification.
- Preserve human review for review-sensitive actions.
- Customer-safe explanations must avoid accusations and detection-secret leakage.
- Reports must keep public and private outputs separate.

## Current Limitations

- This is an API contract, not a hosted full API.
- The repo has internal benchmark and simulation evidence, not external validation.
- Entity resolution is partial.
- Dormant chain memory is not implemented.
- Recurrence detection is simulated through pattern-preservation tests, not a full cross-case recurrence service.
- Federated PRMR remains a future enterprise layer.
- No real client-data performance claim is made.
