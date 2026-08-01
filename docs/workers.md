# Durable Workers

`worker run-once`, `worker run --until-idle`, `worker recover`, and `worker status` operate on the Core Sprint 11 durable queue. PostgreSQL supports bounded multiple workers and leased work. SQLite supports one bounded worker only.

Workers use heartbeats, stale-lease recovery, idempotent effect receipts, retry classification, cancellation, and dead-letter handling. Graceful stop ends new leasing, stops polling, and closes database resources.
