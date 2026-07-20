# PRMR Operational Runbook

## Health

- Liveness: `GET /health/live`
- Readiness: `GET /health/ready`
- General status: `GET /health`

Readiness should be checked before routing protected traffic to the backend.

## Logs

Use the dashboard request logs for client-visible request outcomes. Logs include
endpoint, status, reason, and safe messages. They must not include raw API keys
or authorization headers.

## Storage

Postgres mode requires server-side `DATABASE_URL`. Do not expose database URLs
in frontend code, public reports, or logs.

## Rollback

1. Stop new deploy rollout.
2. Revert to previous Render deployment.
3. Verify `/health/live` and `/health/ready`.
4. Run hosted smoke tests before reopening traffic.

## Backup and Restore

For Postgres deployments, use provider-native backup snapshots before applying
schema migrations. Restore should be tested on a non-production database before
claiming recovery readiness.

## Incident Basics

- Revoke affected API keys.
- Preserve private request logs.
- Identify client/vault/namespace and application scope.
- Do not publish raw keys or private traces.
- Record timeline, impact, and corrective action.
