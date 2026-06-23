# V0.78.2 Key Revocation Record

Truth label: local secret hygiene and revocation evidence only. This is not external security certification.

## Manual Token Check

GitHub personal access tokens were checked manually by the founder/operator during the deployment cleanup. None were found to remain active in the intended GitHub deployment path at the time of this record.

## Revocation Position

- Old local/dev keys are considered revoked.
- Any API key, GitHub token, Render token, Vercel token, or external provider key that may have existed in local/generated files must not be reused.
- Any external provider keys must be revoked manually in the provider dashboard because this repository cannot revoke third-party credentials on its own.
- Future Render, Vercel, GitHub, or other deployment environment values must be fresh.
- No old local key should be reused.
- No raw key value should be committed.
- Only `.env.example` placeholders may be tracked.

## Tracked Repo Policy

The following paths should remain ignored or untracked for deployment hygiene:

- `.env`
- `reports/`
- `logs/`
- `config/`
- root `data/`
- `inputs/`
- `design_sources/`
- `node_modules/`
- `.next/`
- SQLite/database files

`frontend/data/*` is allowed because it is public frontend source data, not root local/private generated state.

## Boundary

This record is local repository hygiene evidence only. It is not external security certification, legal approval, compliance approval, bank approval, production readiness, or real-world validation.
