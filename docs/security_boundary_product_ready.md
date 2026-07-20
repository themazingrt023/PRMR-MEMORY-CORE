# PRMR Security Boundary

Truth label: current security boundary after the product-readiness sprint. This
is not external security certification.

## Implemented

- Copy-once API keys.
- Raw API keys are not persisted in repository storage.
- Key records are hashed at rest.
- Bearer authentication for public protected API routes.
- Optional explicit client/vault/namespace headers are assertion-only.
- Wrong client/vault/namespace assertions are denied.
- Client report access is scoped to owning client/vault/namespace.
- Entity packet generation is scoped inside the authorized namespace.
- Unsafe metadata keys and secret-looking values are redacted.
- Dashboard proxy routes do not expose Supabase access tokens or raw API keys.
- Liveness/readiness endpoints expose no secrets.

## Not Yet Claimed

- No compliance approval.
- No legal approval.
- No bank approval.
- No external security certification.
- No public self-serve billing security claim.
- No guarantee of large-scale abuse resistance.

## Remaining Security Work

- Per-key and per-IP rate limiting.
- Brute-force counters and temporary lockouts.
- CSRF review for dashboard mutations.
- Full CORS production review.
- Independent hosted security review.
- Retention and deletion policy for event/report data.
