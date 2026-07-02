# V0.85 Controlled Alpha Safety Checklist

Use this checklist before any approved controlled-alpha handoff.

Truth label: controlled-alpha onboarding documentation and client-readiness evidence only. This is not self-serve signup, billing, production readiness, compliance approval, legal approval, external security certification, or real-world validation.

## Approval

- [ ] Client approved manually by founder/operator.
- [ ] Use case confirmed as appropriate for controlled alpha.
- [ ] No real sensitive data unless explicitly approved.
- [ ] Boundary notes prepared for the client.

## Scope

- [ ] `<CLIENT_ID>` created.
- [ ] `<VAULT_ID>` created.
- [ ] `<NAMESPACE>` created.
- [ ] Client/vault/namespace scope recorded.
- [ ] Cross-client access expectations explained.

## Key Handling

- [ ] Fresh API key issued.
- [ ] One-time private key packet generated.
- [ ] Raw key not placed in docs, public reports, frontend code, screenshots, or Git history.
- [ ] Public report checked for secret safety.
- [ ] Revoke path verified.

## Dashboard

- [ ] Dashboard token scoped to the client.
- [ ] Dashboard access method documented as `<DASHBOARD_ACCESS_METHOD>`.
- [ ] Public frontend remains locked unless controlled access is present.
- [ ] Raw dashboard token not exposed in browser-visible code or public reports.

## Storage

- [ ] Storage mode understood.
- [ ] Render `/tmp` limitation acknowledged as smoke-only.
- [ ] Durable storage limitation acknowledged before real external records.
- [ ] Persistent disk or managed database plan reviewed if alpha use needs retention.

## Client Handoff

- [ ] API base URL included as `<API_BASE_URL>`.
- [ ] Required headers included.
- [ ] Quickstart sent.
- [ ] Boundary and limitations included.
- [ ] Feedback questions prepared.

## Feedback Questions

- Did the problem make sense?
- Did continuity feel different from summaries or vector search?
- Which endpoint or dashboard panel felt strongest?
- What confused you?
- Would you want to test this with synthetic data?
- What would make this credible enough for a pilot?
- What risks or missing pieces do you see?
