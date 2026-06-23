# PRMR Memory Core V0.65 Deployment Prep

V0.65 is domain/deployment preparation only. It is not a live deployment, not a connected domain, not hosted backend, not production onboarding, not billing, not live API access, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## Current State

The current app is a local controlled-alpha frontend/product shell. It includes local demos, local request capture, local review consoles, public-safe reports, private local reports, and file-writing local API routes.

This is useful for founder walkthroughs, synthetic demos, and local product proof. It is not yet a public hosted product.

## Future Version Boundaries

- V0.66: future live frontend domain preparation and launch gate, if route protection and public-safe copy are ready.
- V0.67+: future hosted backend sandbox work.
- V0.69+: future API key/client access work.
- V0.73+: future payments/billing work.
- V1.0: controlled alpha product shell, not certified production.

## Deployment Principle

Only public-safe frontend pages should be exposed on a domain. Local review consoles, local report stores, private/internal report files, and file-writing admin endpoints must stay local or be disabled/protected before any public deployment.

## Public Deployment Risks

- File-writing API routes currently write to local report JSON files.
- Review/admin pages expose request details and review metadata.
- Local demo bridge routes spawn a local Python process.
- Public/private report separation depends on route and file access discipline.
- No real authentication, database, permissions, deployed logging, rate limiting, or production secrets management is implemented.

## Safe V0.66 Direction

V0.66 may expose a public frontend only if:

- Local-only routes are blocked, disabled, or protected.
- Public pages use synthetic/demo data only.
- No API keys or secrets are bundled into frontend code.
- File-writing endpoints are not publicly exposed without a hosted backend design.
- Public copy preserves the local controlled-alpha boundary.

## Not Yet Implemented

- Hosted backend
- Auth
- Database
- Real client dashboard
- API key management
- Billing
- Production monitoring
- External security review
- Compliance/legal approval
- Real-world validation
