# Migrations

The ordered checksummed registry is authoritative. `db migrations` lists it, `db status` reports pending migrations, `db migrate --dry-run` makes no changes, `db migrate` applies non-destructive entries under a PostgreSQL advisory lock, and `db verify` detects missing or checksum-drifted migrations.

Ordinary migration commands never reset data or drop schemas. The isolated PostgreSQL test guard is preserved by test reset routines. Downgrades are not automatic.
