# PRMR Memory Core V0.65 Public / Private Route Policy

Route classifications:

- `public_safe`: safe candidate for public frontend exposure if copy remains bounded and synthetic/demo-only.
- `local_only`: must remain local in the current implementation.
- `needs_auth_before_deploy`: cannot be public without authentication, authorization, storage, and abuse controls.
- `disable_before_deploy`: should be disabled or replaced before public deployment.
- `future_hosted_backend`: belongs to a future hosted backend, not the current local shell.

## Page Routes

| Route | Classification | Reason |
|---|---|---|
| `/` | public_safe | Public landing page with bounded copy. |
| `/demo` | public_safe | Public-safe only if synthetic/demo data is used and unsafe bridge execution is disabled or replaced. |
| `/docs` | public_safe | Public-safe if docs exclude secrets/private internals. |
| `/alpha` | public_safe | Page can be public, but submit endpoint needs hosted/protected request handling before deployment. |
| `/alpha/review` | local_only | Review/admin route exposes local request details and has no auth. |
| `/book-demo` | public_safe | Page can be public, but submit endpoint needs hosted/protected request handling before deployment. |
| `/book-demo/review` | local_only | Review/admin route exposes local demo request details and has no auth. |
| `/contact` | public_safe | Static public contact page. |
| `/demo-video` | public_safe | Public-safe only if video/copy preserves boundaries. |
| `/capabilities/[slug]` | public_safe | Public capability pages if no private/internal data appears. |

## API Routes

| Route | Classification | Reason |
|---|---|---|
| `/api/alpha/request` | needs_auth_before_deploy | File-writing request capture route. Needs hosted storage/rate limiting before public exposure. |
| `/api/alpha/review` | local_only | File-writing review/admin route with private local review details. |
| `/api/demo/book` | needs_auth_before_deploy | File-writing demo request route. Needs hosted storage/rate limiting before public exposure. |
| `/api/demo/review` | local_only | File-writing review/admin route with private local demo details. |
| `/api/demo/scenarios` | disable_before_deploy | Uses local demo bridge. Replace with static/public-safe hosted data or disable. |
| `/api/demo/run` | disable_before_deploy | Uses local demo bridge. Replace with hosted demo backend or static demo. |
| `/api/demo/report` | disable_before_deploy | Uses local demo bridge. Must not expose local/private report paths. |
| `/api/demo/health` | disable_before_deploy | Local bridge health route; not public product health. |

## Launch Rule

No `local_only`, `needs_auth_before_deploy`, `disable_before_deploy`, or `future_hosted_backend` route should be publicly exposed on a domain unless it has been redesigned, protected, and re-audited.
