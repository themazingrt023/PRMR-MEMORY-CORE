# Operations Runbook

## Install and Start

Run `prmr-core config init`, `config validate`, `db status`, `db migrate`, `engine init`, `engine ready`, then start `worker run`. SQLite must use one worker. PostgreSQL may use bounded multiple workers.

## Stop

Send Ctrl+C or SIGTERM. The runtime marks readiness false, stops new leasing, stops polling and heartbeats, allows bounded current work, and closes repositories and pools.

## Incidents

- Database unavailable: stop new work, check network/provider status without printing credentials, then rerun `engine ready`.
- Migration drift: stop startup, preserve the database, run `db verify`, and compare checksums. Never rewrite applied SQL.
- Pool exhaustion: stop workers, inspect safe pool metrics, resolve long transactions, restart.
- Stuck jobs/stale leases: run `worker status`, then `worker recover`.
- Dead letter: inspect safe code and operator metadata, correct the cause, then use the governed replay service.
- Interrupted governance/consolidation/export: run recovery before reissuing work; effect receipts prevent duplicate committed effects.
- Packet integrity failure: stop serving that packet, retain evidence, run `integrity sweep --mode full-scope`.
- Backup: create and verify to a new destination. Never overwrite the active database.
- Configuration or credential rotation: update the explicit environment source, restart, and verify redacted config plus readiness.
- Diagnostics: run `diagnostics collect --output PATH`; review before sharing.
