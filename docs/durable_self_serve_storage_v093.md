# PRMR Memory Core V0.93 Durable Self-Serve Storage

## What V0.93 adds

V0.93 adds an explicit SQLite repository behind the generic V0.92 self-serve
product. State is reconstructed into the existing account, plan, key lifecycle,
protected API, and dashboard services after process restart.

Persisted entities:

- users with password salt and PBKDF2 password hash
- local verification state
- hashed local sessions
- plan subscriptions and monthly counters
- clients, vaults, namespaces, and usage limits
- API key hash, fingerprint, safe preview, status, label, and scope
- usage events and protected request logs
- continuity events, packets, and public/private report payloads
- reconstructable public-safe dashboard snapshots
- lifecycle and audit metadata

Raw API keys and raw passwords are never persisted. A key credential is returned
only by its creation or rotation response. Reloaded storage can validate a
caller-supplied key by hashing it and comparing that hash.

## Local SQLite

Set a path outside public/static folders:

```powershell
$env:PRMR_SELF_SERVE_STORAGE_PATH="$PWD\data\prmr_self_serve.sqlite"
$env:PRMR_API_MODE="local_alpha"
```

The repository creates parent directories and schema tables automatically.
Local SQLite proves restart persistence on one machine. It does not prove
hosted durability.

## Hosted persistent disk

Recommended near-term Render configuration:

1. Add a Render persistent disk.
2. Mount it at `/var/data`.
3. Set:

```text
PRMR_SELF_SERVE_STORAGE_PATH=/var/data/prmr_self_serve.sqlite
PRMR_API_MODE=hosted_alpha
PRMR_DURABLE_STORAGE_VERIFIED=true
```

`PRMR_DURABLE_STORAGE_VERIFIED=true` is an operator assertion that the path is
actually backed by the configured persistent disk. The path alone is only a
candidate and does not prove persistence.

The deployed FastAPI process must instantiate the V0.93 durable product adapter
before self-serve records can use this database. The current local evidence does
not claim that this hosted wiring is complete.

## Why `/tmp` is not durable

Paths under `/tmp` or `/var/tmp` are classified as
`hosted_ephemeral_sqlite`. They are acceptable for isolated smoke runs only.
Setting the verification flag does not override the ephemeral classification.

## Restart and redeploy proof

Local restart proof:

```powershell
python examples/run_durable_self_serve_storage_v093.py
python examples/audit_v093_durable_self_serve_storage.py
```

Hosted proof is a real two-run process:

```powershell
$env:PRMR_SELF_SERVE_STORAGE_PATH="/var/data/prmr_self_serve.sqlite"
$env:PRMR_DURABLE_STORAGE_VERIFIED="true"
$env:PRMR_HOSTED_API_URL="https://prmr-memory-core-api.onrender.com"
python examples/run_hosted_storage_redeploy_smoke_v093.py
```

The first run creates a safe checkpoint identifier. Restart or redeploy the
service, then run:

```powershell
$env:PRMR_V093_REDEPLOY_CHECKPOINT_ID="<CHECKPOINT_ID>"
python examples/run_hosted_storage_redeploy_smoke_v093.py
```

Only a successful second run proves that checkpoint survived. Without these
variables the helper returns `NEEDS_HOSTED_DURABLE_STORAGE`.

## Future managed Postgres

SQLite is suitable for the near-term controlled deployment with one attached
persistent disk. Managed Postgres remains the planned migration for concurrent
application instances, managed backups, connection pooling, operational
monitoring, and broader external use. V0.93 does not implement that migration.

## Secret hygiene

- Never store or log raw API keys.
- Never store raw passwords.
- Keep the database outside public web roots.
- Restrict disk and backup access.
- Public reports may contain safe previews and counts, never private hashes.
- Use only synthetic or approved non-sensitive data until the hosted boundary is
  separately approved.

## Honest boundary

V0.93 proves local SQLite restart/reload persistence. It does not prove hosted
redeploy survival until the two-run checkpoint passes on a real persistent disk.
It does not add real email, payments, production authentication, compliance or
legal approval, or external security certification.
