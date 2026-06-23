# V0.54 Frontend / Backend Integration Notes

Boundary statement: Current evidence is internal/local controlled-alpha evidence. External validation and production hardening are separate future milestones.

## Recommended Stack

- Next.js
- React
- TypeScript
- Tailwind CSS

## Frontend Rules

- Never expose API keys in frontend code, browser bundles, page source, logs, or public demo fixtures.
- Frontend should call backend proxy routes, not PRMR core directly.
- Public demo should use synthetic/demo data only.
- Public demo should fetch public-safe reports only.
- Private/internal reports must never be exposed in public frontend.
- Browser UI should display boundary notices near evidence and demo output.
- Public pages should avoid final punitive decisions and accusation wording.

## Backend Responsibilities

Backend proxy routes should handle:

- API key validation
- client IDs
- vaults
- namespaces
- report access checks
- usage logs
- key rotation
- key revocation
- public-safe report retrieval
- denial paths for wrong-key and cross-client attempts

## Suggested Backend Proxy Routes

- `/api/demo/run`
- `/api/demo/report`
- `/api/alpha/request`
- `/api/usage`
- `/api/keys/rotate`
- `/api/keys/revoke`

## Integration Flow

1. User opens the public demo page.
2. Frontend requests a synthetic scenario from `/api/demo/run`.
3. Backend runs or replays a deterministic synthetic fixture.
4. Backend returns only public-safe demo output.
5. Frontend requests a public-safe report through `/api/demo/report`.
6. Backend verifies report ownership and returns only the public-safe report.
7. Any restricted trace remains server-side and is not returned to the public frontend.

## Alpha Access Flow

1. Visitor submits an alpha request through `/api/alpha/request`.
2. Backend stores the request in the chosen internal workflow.
3. A human reviews the use case, data sensitivity, and evaluation scope.
4. Any approved sandbox credentials are delivered outside the public frontend.

## Security Notes

- Do not store credentials in local storage.
- Do not pass credentials as URL parameters.
- Do not include credentials in client-side telemetry.
- Do not expose raw event dumps in public demo responses.
- Do not expose restricted reports in public routes.
- Do not bypass client, vault, or namespace checks.
- Do not let frontend code call key rotation or revocation directly without backend authorization.

## Evidence Boundary

The frontend may display internal/local controlled-alpha evidence labels. It must not describe those labels as external validation or deployment proof.
