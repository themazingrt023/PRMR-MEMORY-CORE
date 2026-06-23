# PRMR V0.55 Frontend to Local Demo Backend Connection

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.55

## Purpose

V0.55 connects the local `frontend/` Next.js product shell to a local PRMR demo bridge. This is a local-only demo connection for controlled-alpha demonstration only.

This is not a hosted API, not a production backend, not deployment readiness, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

## Local Flow

1. The browser opens `/demo`.
2. The user selects one synthetic scenario.
3. The user clicks `Run Local Demo`.
4. Browser code calls `POST /api/demo/run`.
5. The Next.js route runs server-side only.
6. The route calls `examples/demo_v055_frontend_bridge.py` through a local child process.
7. The bridge uses the V0.52.1 sandbox and V0.53.1 deterministic fixture shape.
8. The frontend receives public-safe JSON only.
9. The page renders synthetic events, continuity packet, reconstruction, explanation, least-harm action, report preview, and denial path proof.

## Local Proxy Routes

- `GET /api/demo/scenarios`
- `POST /api/demo/run`
- `GET /api/demo/report`
- `GET /api/demo/health`

These routes are local server-side proxy routes. They are not a production architecture.

## Safety Rules

- Synthetic data only by default.
- Browser code never receives raw keys.
- Browser code never receives vault secrets.
- Browser code never receives restricted diagnostic packets.
- Frontend output is public-safe only.
- Report previews returned to the frontend are public-safe summaries only.
- Denial path output is limited to public-safe access outcomes.
- No final punitive decision is made by the demo.

## Current Scenarios

- AI agent memory continuity
- Customer support/user-history continuity
- Fraud/risk continuity sandbox

## Current Limitations

- Local child-process bridge only.
- No hosted API.
- No billing.
- No login or production authentication flow.
- No real sensitive data.
- No persistent backend service.
- No external validation.
- No production hardening.

## Future Hosted Backend Work

Future work would need a real backend service boundary, deployment hardening, credential custody, rate limiting, request logging policy, observability, environment isolation, secret rotation operations, formal threat modeling, and external validation before any production claims.
