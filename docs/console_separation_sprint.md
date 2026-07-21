# PRMR Marketing and Console Separation Sprint

Truth label: console separation preparation and shell implementation. This is not production authentication hardening, live billing, compliance approval, legal approval, external security certification, or completed DNS migration.

## Target Surfaces

Marketing website:

```text
prmr.afternumindustries.co.uk
```

Developer console:

```text
app.prmr.afternumindustries.co.uk
```

API:

```text
api.afternumindustries.co.uk
```

Existing live URLs must remain available until DNS, TLS, Supabase redirects, API proxying, and smoke tests pass.

## Current Implementation

- `console/` is a separate console application root prepared for separate Vercel deployment.
- Existing `frontend/app/dashboard/page.tsx` now uses a console shell instead of marketing navigation.
- The console nav contains operational sections only:
  - Overview
  - Playground
  - API Keys
  - Applications
  - Events
  - Continuity Packets
  - Request Logs
  - Usage
  - Billing
  - Team
  - Settings
  - Documentation

Marketing navigation such as Problem, Solution, Market, Pilot, Demo, and Start Building must not appear inside authenticated console screens.

## Staged Migration

1. Deploy the marketing app preview.
2. Deploy the console app preview.
3. Configure console environment variables.
4. Configure Supabase redirect URLs for the console domain.
5. Configure DNS for `prmr`, `app.prmr`, and `api`.
6. Verify authentication callback.
7. Verify dashboard API proxies.
8. Verify logout.
9. Verify public API integration from the reference client.
10. Only then redirect legacy dashboard routes.

## Boundary

Do not claim `app.prmr.afternumindustries.co.uk` or `api.afternumindustries.co.uk` are live until DNS and hosted smoke tests pass.
