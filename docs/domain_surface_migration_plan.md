# PRMR Domain Surface Migration Plan

Truth label: domain and routing plan only. This does not claim production hardening or external security certification.

## Current Public Surfaces

- Company/proof/docs site: `https://afternumindustries.co.uk`
- Existing Vercel deployment alias: `https://prmr-memory-core.vercel.app`
- Hosted API: `https://prmr-memory-core-api.onrender.com`

## Recommended Target Shape

- `https://afternumindustries.co.uk`: company site and product proof.
- `https://app.afternumindustries.co.uk`: authenticated PRMR dashboard.
- `https://api.afternumindustries.co.uk`: PRMR API, if DNS and host support are configured.
- `https://docs.afternumindustries.co.uk`: developer docs, later.

## Migration Steps

1. Keep the existing Vercel and Render URLs working during transition.
2. Add subdomains in DNS.
3. Configure Vercel domain aliases for site/app surfaces.
4. Configure Render custom domain for API if available.
5. Update allowed origins to include the official site/app domains.
6. Run hosted smoke tests before announcing any domain as current.

## Boundary

Do not claim a custom API domain is live until DNS, TLS, CORS, and hosted smoke tests pass.
