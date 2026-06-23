# PRMR Memory Core V0.65 Domain Launch Checklist

This checklist is for a future V0.66 live frontend domain. V0.65 does not deploy or connect a domain.

## Build Gates

- Production build passes.
- Typecheck passes.
- Public routes are classified.
- Local-only routes are blocked, disabled, or protected.
- File-writing admin endpoints are not public.
- Local bridge routes are disabled or replaced with public-safe hosted/static behavior.

## Data And Secrets Gates

- No secrets exposed.
- No API keys exposed.
- No private report exposure.
- No private/internal report paths exposed.
- No personal request details in public reports.
- Public demo uses synthetic/demo data only.
- Public environment variables contain no secrets.

## Copy And Claim Gates

- Public copy audited for claims.
- No hosted API claim.
- No production readiness claim.
- No bank approval claim.
- No compliance approval claim.
- No legal approval claim.
- No external security certification claim.
- No real-world validation claim.
- Boundaries visible on public pages.

## Product Gates

- Homepage works.
- Demo page works safely or is disabled.
- Docs page works without private internals.
- Book demo form is either disabled or backed by safe hosted request capture.
- Alpha form is either disabled or backed by safe hosted request capture.
- Review/admin pages are not public without auth.
- Privacy/boundary page exists or is planned.

## Infrastructure Gates

- Deployment target chosen but not connected in V0.65.
- Environment variable plan reviewed.
- Logging/monitoring plan documented.
- Rollback plan documented.
- Future hosted backend boundary documented.

## V0.66 Decision

Proceed only if every public route is safe, every local-only route is blocked or disabled, and the public copy remains honest.
