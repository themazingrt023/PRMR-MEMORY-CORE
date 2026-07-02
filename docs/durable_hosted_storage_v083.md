# V0.83 Durable Hosted Storage Plan

V0.83 clarifies PRMR Memory Core's storage boundary before real external alpha testing.

Truth label: storage boundary and durable-hosting readiness evidence only. This is not a full production database migration, paid managed storage, compliance approval, legal approval, external security certification, or real-world validation.

## Current Storage Reality

Local storage exists and works:

- SQLite is used for local synthetic/dev evidence.
- Local report and smoke runs store SQLite files under repo-local ignored paths such as `reports/...`.
- This is enough for local truth gauntlets, local product demos, and controlled synthetic smoke evidence.

Hosted storage is currently smoke-only:

- Render hosted smoke can use `/tmp/...` SQLite paths.
- `/tmp` on hosted platforms should be treated as ephemeral.
- Ephemeral storage is acceptable for smoke tests only.
- It must not be described as durable hosted persistence.

## Why `/tmp` Is Not Enough

`/tmp` storage may be reset when the service restarts, redeploys, scales, or moves hosts.

That means `/tmp` is not suitable for:

- real external alpha records
- durable manual onboarding records
- long-lived dashboard sessions
- persistent usage logs
- revocation/audit history
- customer-facing continuity reports

Using `/tmp` is acceptable only while the evidence label remains hosted smoke/testing.

## Storage Mode Labels

V0.83 classifies storage as:

- `local_sqlite`: local synthetic/dev SQLite evidence.
- `hosted_ephemeral_sqlite`: hosted `/tmp` or similar ephemeral SQLite storage, smoke-only.
- `hosted_durable_sqlite`: hosted SQLite path that is intended to be durable, but only claim durability when verified.
- `hosted_managed_database_planned`: managed durable database path is planned or represented but not completed here.
- `unknown_storage_mode`: missing or unclear storage configuration.

## Options

### Option 1: Render Persistent Disk

Use a Render persistent disk mounted to a durable path such as `/var/data` and set:

```text
PRMR_STORAGE_PATH=/var/data/prmr_api_server.sqlite
PRMR_STORAGE_MODE=hosted_durable_sqlite
PRMR_DURABLE_STORAGE_VERIFIED=true
```

This is the lowest-friction next step if staying close to the current SQLite implementation.

Before claiming durable hosted storage, verify:

- the disk is attached to the running service
- the file persists across restart/redeploy
- backups/export process is documented
- key/session/revocation records survive restart

### Option 2: Managed Postgres

Move durable hosted records to managed Postgres.

This is the stronger long-term path for:

- multiple external alpha clients
- durable dashboard sessions
- usage logs
- revocation history
- report registry
- audit records

It requires a schema/migration layer and a separate smoke/audit milestone.

### Option 3: SQLite-Compatible External Storage

Use a SQLite-compatible hosted storage system only if it provides clear durability, backup, and concurrency guarantees.

This should not be assumed without provider-specific verification.

## Recommended Next Step

For the next milestone, use Render persistent disk or equivalent durable mounted storage first, because it is closest to the current SQLite implementation.

Recommended V0.84 direction:

1. Configure a persistent hosted storage path.
2. Run restart/redeploy persistence smoke.
3. Verify onboarding record, dashboard session, usage log, and revocation history survive restart.
4. Only then mark `PRMR_DURABLE_STORAGE_VERIFIED=true`.

Managed Postgres remains the recommended later path before broader external alpha or pilot use.

## Before Real External Client Data

Before any real external alpha client data is stored, PRMR needs:

- durable hosted storage verified
- backup/export plan
- data retention policy
- operator revocation process
- dashboard session persistence policy
- environment secret rotation plan
- clear approval for any non-synthetic data
- stronger production authentication plan

## Public-Safe Wording

Safe wording:

> Current hosted backend evidence uses controlled synthetic smoke tests. Durable hosted storage is a separate milestone before real external alpha records.

Avoid:

- saying hosted persistence is ready for production
- suggesting hosted records are durably guaranteed before verification
- implying real client data can be stored before approval
- implying regulatory approval
- implying third-party security certification
- implying the managed database migration is already finished

## Boundary

V0.83 is storage boundary and durable-hosting readiness evidence only. It is not a full production database migration, paid managed storage, compliance approval, legal approval, external security certification, or real-world validation.
