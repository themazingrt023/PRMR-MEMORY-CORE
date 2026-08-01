# Troubleshooting

- `.env` is not loaded: pass `--env-file PATH` explicitly.
- Environment changes are invisible: restart the terminal or editor process.
- Wrong working directory: pass absolute `--config` and output paths.
- Guarded PostgreSQL variables missing: set them only for the isolated test database.
- Test guard missing: stop; do not use a production or unverified database.
- Undefined table: run `db status`, then `db migrate` before repository work.
- Migration ordering/checksum failure: do not edit an applied migration; investigate registry drift.
- Lock timeout or serialization retry: allow bounded retry or clear the conflicting operator transaction.
- Stale lease: run `worker recover`.
- Pool reset/exhaustion: stop new work, inspect `worker status`, then restart cleanly.
- `pg_dump` unavailable: install PostgreSQL client tooling or record the documented limitation.

Diagnostics output is safe by design, but operators must still review it before sharing.
