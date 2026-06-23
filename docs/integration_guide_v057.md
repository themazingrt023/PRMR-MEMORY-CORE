# PRMR V0.57 Integration Guide

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.57

## Purpose

This guide explains how a future builder would connect an application to PRMR Memory Core while preserving the current truth boundary.

V0.57 is documentation only. It does not implement a hosted API, billing, production authentication, real credential issuing, or external validation.

## Recommended Application Shape

```text
Your frontend
-> your backend proxy
-> PRMR continuity layer
-> public-safe output back to frontend
```

Browser code should not call PRMR core directly. The backend should own request authorization, vault scope, namespace scope, report access, usage logs, credential rotation, and credential revocation.

## Integration Steps

1. Define the continuity use case.
2. Convert raw activity into scoped events.
3. Send events under a client, vault, and namespace.
4. Generate a continuity packet for the target entity or workflow.
5. Reconstruct current state when needed.
6. Request a public-safe explanation for user-facing or operator-facing review.
7. Request a least-harm action boundary.
8. Fetch only public-safe report previews for frontend display.
9. Keep restricted diagnostics server-side.

## Current Local Demo Wiring

V0.55 uses:

```text
Browser /demo
-> Next.js server-side proxy
-> local Python PRMR bridge
-> V0.52.1 sandbox / V0.53.1 synthetic fixtures
-> public-safe JSON
-> frontend cards
```

This proves local demo wiring only. It is not hosted production architecture.

## Example Domains

- AI agent memory continuity
- Customer support/user-history continuity
- SaaS user-history continuity
- Education progress continuity
- Legal/research case continuity
- Fraud/risk sandbox evaluation
- Company knowledge continuity

## Safety Rules

- Use synthetic/demo data for local demos.
- Do not use real sensitive data unless explicitly approved.
- Do not expose raw credentials in browser code.
- Do not expose restricted diagnostic reports in public frontend output.
- Do not use PRMR output for final punitive decisions.
- Keep external validation and production hardening as future milestones.

## Future Hosted API Work

A hosted PRMR service would need separate work for:

- hosted backend
- client accounts
- vaults and namespaces
- credential issuing
- usage logs
- rate limits
- dashboard
- billing
- external security review

Those are future milestones, not current V0.57 claims.
