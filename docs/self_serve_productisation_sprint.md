# PRMR Memory Core Self-Serve Productisation Sprint

Truth label: this is a hosted/self-serve product activation path for PRMR Memory Core. It is not production authentication hardening, Stripe billing, compliance approval, legal approval, external security certification, or enterprise readiness.

## Intended First-Run Journey

1. A visitor creates an account on the Afternum PRMR site.
2. Email confirmation is handled by Supabase Auth.
3. The verified user opens `/start`.
4. PRMR automatically creates:
   - one account record
   - one Free subscription
   - one client ID
   - one vault ID
   - one namespace
   - one sandbox application named `My First Application`
   - one copy-once sandbox server API key
5. The dashboard shows the key once, then only safe previews.
6. The user sends one synthetic event from the playground.
7. The user generates one continuity packet.
8. The dashboard shows usage, request logs, reports, storage status, billing status, and activation progress.

## Public Concepts

PRMR keeps the first-run vocabulary small:

- Workspace: the account-level place where the user manages PRMR.
- Application: the product sending events into PRMR.
- API key: a server-side credential used by the user's backend.
- Event: a compact record of something that changed.
- Continuity packet: PRMR's scoped memory output built from stored event history.
- Report: a public-safe view of packet evidence and status.

## Current Boundaries

- Use synthetic or approved non-sensitive data only.
- API keys must stay server-side.
- The first key is shown once; later dashboard views show safe previews only.
- Billing is not live. Free usage is enforced by the self-serve plan service.
- Storage durability depends on the configured hosted backend storage mode.
- This is not open enterprise onboarding, compliance approval, legal approval, or external security certification.

## Activation Tracking

PRMR records a public-safe activation funnel:

- account created
- email verified
- default client/vault/namespace ready
- sandbox key created
- first event ingested
- first continuity packet generated

The funnel stores public-safe event types and safe details only. It does not store raw keys, tokens, authorization headers, or sensitive event content.
