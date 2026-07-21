# PRMR Real Client Reference Client Sprint

Truth label: local HTTP public-contract reference-client evidence plus deployment preparation. Hosted external-client proof is not complete until a deployed reference-client URL and `PRMR_REFERENCE_API_KEY` are supplied and the hosted smoke passes.

## Reference Client

Application root:

```text
reference-client/
```

Name:

```text
PRMR Reference Project Client
```

The app is separate from the PRMR marketing site and console. It uses:

```text
PRMR_API_URL
PRMR_API_KEY
POST /v1/events/ingest
POST /v1/continuity/packet
```

It must not import PRMR backend modules, use dashboard tokens, read PRMR Postgres, use TestClient, or know client/vault/namespace values.

## Project Actions

Each project-management action creates a PRMR event:

- `reference.project.created`
- `reference.project.goal_updated`
- `reference.project.deadline_changed`
- `reference.project.blocker_recorded`
- `reference.project.decision_recorded`
- `reference.project.milestone_completed`

Every event includes actor, workspace, entity, event type, signal, occurred time, idempotency key, and safe metadata with:

```text
metadata.source_app = "prmr_reference_client"
```

## Continuity View

The client displays packet fields from PRMR:

- current state
- active information
- latent information
- lineage information
- repeated patterns
- state transition summary
- coherence score
- recoverability score
- event count
- packet ID
- last updated

## Hosted Smoke

From `reference-client/`:

```bash
PRMR_API_URL=https://prmr-memory-core-api.onrender.com PRMR_API_KEY=<server-side-key> npm run hosted:smoke
```

If credentials are missing, the smoke reports `NEEDS_CREDENTIALS` rather than faking a pass.
