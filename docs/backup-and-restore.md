# Backup and Restore

SQLite backup performs a WAL checkpoint and the SQLite backup API, then verifies database integrity, migration state, and a stored V2 packet when present. It refuses implicit overwrite and writes a hash manifest.

PostgreSQL logical backup requires `pg_dump` plus `pg_restore` or `psql`. If unavailable, RC1 reports `POSTGRES_LOGICAL_BACKUP_NOT_RUN_TOOLING_UNAVAILABLE`; governance export is not a database backup.

`restore verify` only checks an explicitly supplied destination and requires an explicit destructive-test acknowledgement. It never overwrites the active configured database.
