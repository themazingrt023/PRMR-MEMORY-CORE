# PRMR Memory Core Product Readiness Architecture Map

Truth label: current implementation map for engineering handoff. This is not
enterprise readiness, compliance approval, legal approval, or external security
certification.

## External API Flow

1. A user creates an account and verifies email.
2. PRMR provisions a client, vault, namespace, and default application.
3. The user creates an application such as `Production CRM` or `Education Platform`.
4. The user creates a copy-once server API key associated with an application.
5. External systems send events to `POST /v1/events/ingest` using `Authorization: Bearer <PRMR_API_KEY>`.
6. PRMR validates the hashed key record and infers client/vault/namespace from the key.
7. Optional explicit scope headers are assertions only; mismatches are denied.
8. Events are normalized, metadata is sanitized, duplicates are ignored by event ID/idempotency key, and scoped records are stored.
9. `POST /v1/continuity/packet` requires an entity scope when scoped events exist.
10. PRMR computes a deterministic packet from only the permitted application/actor/workspace/entity/session history.
11. Reports and dashboard details expose public-safe packet fields and provenance.

## Implemented Critical Fixes

- Entity-scoped packet generation inside authorized client/vault/namespace.
- Required no-global-packet guard when scoped events exist.
- Broad workspace/application packets require explicit `allow_broad_scope=true`.
- Deterministic packet IDs from scoped source history and algorithm revision.
- Safe packet provenance: source event IDs, normalized types, included/excluded summaries, classification basis, factor breakdowns, transition sequence, previous packet/diff metadata.
- Application object with default `app_main`, create/list endpoints, key association, and dashboard counters.
- Idempotent ingest behavior for duplicate event IDs/idempotency keys.
- Liveness and readiness endpoints.

## Current Storage Reality

SQLite and Postgres repositories still store event and packet payloads as JSON
blobs keyed by namespace or packet ID. Entity isolation is enforced by the PRMR
engine at read/packet time. A relational event table is recommended before
large-scale external usage.

## Boundary

PRMR can now preserve and return isolated deterministic continuity for scoped
application events in controlled product flows. It still needs hosted
performance measurements, relational event storage migration, mature rate
limiting, production security review, and external engineering validation.
