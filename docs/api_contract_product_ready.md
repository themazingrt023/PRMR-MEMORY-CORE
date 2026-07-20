# PRMR Memory Core API Contract

Truth label: product-facing API contract for current implementation. This is
not a compliance, legal, bank, or external security certification document.

## Authentication

Use `Authorization: Bearer <PRMR_API_KEY>`.

The API key determines the owning `client_id`, `vault_id`, and `namespace`.
Optional `X-Client-ID`, `X-Vault-ID`, and `X-Namespace` headers are assertions;
if supplied and mismatched, the request is denied.

## Application Management

- `GET /v1/auth/supabase/applications`
- `POST /v1/auth/supabase/applications`
- `GET /v1/self-serve/applications`
- `POST /v1/self-serve/applications`

Create body:

```json
{
  "name": "Production CRM",
  "application_reference": "app_product",
  "environment": "production"
}
```

Allowed environments: `production`, `staging`, `development`, `test`.

## Event Ingest

Endpoint: `POST /v1/events/ingest`

Batch body:

```json
{
  "events": [
    {
      "event_type": "project.updated",
      "signal": "The user changed the project launch date.",
      "metadata": {
        "source_app": "external_product",
        "domain": "project"
      },
      "occurred_at": "2026-07-20T10:00:00Z",
      "application_reference": "app_main",
      "actor_reference": "user_8f21",
      "workspace_reference": "workspace_91",
      "entity_reference": "project_42",
      "session_reference": "session_optional",
      "idempotency_key": "project-42-update-173"
    }
  ]
}
```

Single-event bodies are also accepted for the generic external event shape.

Duplicate event IDs/idempotency keys are ignored inside the authorized
client/vault/namespace and returned in `duplicate_event_count`.

## Continuity Packet

Endpoint: `POST /v1/continuity/packet`

When scoped events exist, supply at least one of:

- `application_reference`
- `actor_reference`
- `workspace_reference`
- `entity_reference`

`session_reference` is optional and narrows the scope when supplied.

Example:

```json
{
  "application_reference": "app_main",
  "actor_reference": "user_8f21",
  "workspace_reference": "workspace_91",
  "entity_reference": "project_42"
}
```

Broad packets that match multiple actors/workspaces/entities require:

```json
{ "allow_broad_scope": true }
```

The packet returns deterministic V1 fields including `current_state`,
`active_information`, `latent_information`, `lineage_information`,
`causal_signature`, `recursive_horizon`, `coherence_score`,
`recoverability_score`, `re_emergence_signals`, `decayed_signals`,
`repeated_patterns`, `state_transition_summary`, `source_event_count`,
`packet_version`, `algorithm_revision`, and `provenance`.

## Operational Endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Readiness reports storage and dependency status without exposing secrets.

## Limits and Safety

Current documented implementation uses plan quotas and duplicate protection.
Large-scale payload, rate-limit, and hosted performance limits still require
additional measurement before broad external alpha.
