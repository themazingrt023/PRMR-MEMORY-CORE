# PRMR Memory Core V0.65 Secrets Policy

V0.65 does not add production secrets, hosted services, billing, API key issuing, or live access.

## Rules

- No API keys in frontend code.
- No secrets committed to the repo.
- Use `.env.local` for local development values.
- Future deployed environment variables must be server-side only unless intentionally public and non-sensitive.
- `NEXT_PUBLIC_*` variables must never contain secrets.
- Public reports must not expose keys, private internals, personal request details, or debug traces.
- Public pages must not expose private engine internals.
- Private/internal reports must remain local unless sanitized.
- Do not place real credentials in docs, examples, screenshots, generated reports, or test fixtures.

## Placeholder Environment Variables

The `.env.example` file contains placeholders only. It does not contain real secrets.

Suggested future flags:

- `NEXT_PUBLIC_ENABLE_LOCAL_REVIEW=false`
- `LOCAL_REVIEW_ENABLED=false`
- `LOCAL_FILE_WRITES_ENABLED=false`
- `LOCAL_DEMO_BRIDGE_ENABLED=false`
- `PRMR_LOCAL_DEMO_PYTHON=python`

## Public Deployment Requirement

Before a public domain launch, scan:

- frontend source
- reports
- docs
- generated JSON
- build output
- environment files

The scan must confirm that no secrets, API keys, private request details, private/internal report content, or private engine internals are exposed.
