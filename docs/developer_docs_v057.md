# PRMR V0.57 Developer Docs

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.57

## Purpose

These developer docs explain how AI builders, SaaS teams, and organisations would integrate PRMR Memory Core as a continuity infrastructure layer.

V0.57 is documentation and docs-page improvement only. It is not a hosted API, not production readiness, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## Overview

PRMR Memory Core helps systems preserve continuity over time by turning event history into:

- continuity packets
- reconstructed state
- public-safe explanations
- least-harm action boundaries
- public and restricted report outputs

Core line:

> Storage remembers data. PRMR remembers change.

PRMR Memory Core is not an AI model. It is a continuity infrastructure layer that sits beside databases, vector stores, AI models, agents, SaaS tools, support systems, and organisational workflows.

## What PRMR Is Not

PRMR Memory Core is:

- not an AI model
- not a database replacement
- not a vector database replacement
- not a final decision engine
- not production-certified
- not bank approved
- not compliance approved
- not legal approval
- not external security certification

## Basic Integration Flow

1. Send scoped events.
2. Generate a continuity packet.
3. Reconstruct current state.
4. Request a public-safe explanation.
5. Request a least-harm action boundary.
6. Fetch a public report preview.

## Required Scope Fields

Every controlled-alpha request is scoped by:

- `client_id`
- `vault_id`
- `namespace`

Browser code should call backend proxy routes. Browser code should not call PRMR core directly and should never receive raw credential material.

## Endpoint Reference

The endpoint reference follows the V0.52.0 alpha API contract:

- `POST /v1/events/ingest`
- `POST /v1/continuity/packet`
- `POST /v1/memory/reconstruct`
- `POST /v1/explain`
- `POST /v1/actions/least-harm`
- `GET /v1/reports/{report_id}`
- `GET /v1/usage`
- `POST /v1/keys/rotate`
- `POST /v1/keys/revoke`

See `docs/api_examples_v057.md` for sample requests and responses.

## Example Use Cases

- AI agent memory continuity
- Customer support/user-history continuity
- SaaS user-history continuity
- Education progress continuity
- Legal/research case continuity
- Fraud/risk sandbox evaluation
- Company knowledge continuity

## Local Demo Integration

V0.55 local demo architecture:

```text
Browser /demo
-> Next.js server-side proxy
-> local Python PRMR bridge
-> V0.52.1 sandbox / V0.53.1 synthetic fixtures
-> public-safe JSON
-> frontend cards
```

This is local-only demo wiring. It is not production architecture.

## Safety Boundaries

- Synthetic/demo data only for the current local demo.
- No real sensitive data unless explicitly approved.
- No final punitive decisions.
- Restricted diagnostic reports remain server-side.
- Browser never receives raw credentials.
- External validation and production hardening are future milestones.

## Future Hosted API Notes

Future hosted API work may include:

- hosted backend
- client accounts
- vaults and namespaces
- credential issuing
- usage logs
- rate limits
- dashboard
- billing
- external security review

These are future milestones, not current V0.57 implementation claims.
