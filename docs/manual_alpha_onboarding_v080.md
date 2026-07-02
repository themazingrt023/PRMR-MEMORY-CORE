# V0.80 Manual Alpha Client Onboarding

V0.80 defines the first founder/operator-controlled alpha onboarding workflow for PRMR Memory Core.

This is not self-serve signup, billing, automatic access, production readiness, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.

## Purpose

Now that V0.79 proved a full protected hosted API flow with synthetic controlled test credentials, V0.80 describes how a founder/operator can manually create a synthetic or approved alpha client scope and issue one fresh alpha key with safe handling.

The workflow is intentionally manual.

## Manual Approval Steps

1. Review the alpha candidate.
2. Confirm the use case is appropriate for controlled-alpha testing.
3. Confirm synthetic or approved test data only.
4. Confirm boundaries are visible to the recipient.
5. Create a client record, vault, namespace, and usage limit.
6. Issue one fresh alpha key.
7. Deliver the key through a private approved channel.
8. Record delivery status.
9. Revoke the key when testing ends, when scope changes, or if handling is uncertain.

## Local Operator Command

```powershell
python examples/run_manual_client_onboarding_v080.py
```

This creates one synthetic/manual alpha client locally and writes:

- `reports/v080/public_manual_client_onboarding_v080.json`
- `reports/v080/private_internal_manual_client_onboarding_v080.json`
- `reports/v080/private_one_time_key_packet_v080.json`
- `reports/v080/scorecard_v080.md`

The private one-time key packet may contain the generated alpha key. It is local/private-only and must not be committed, pasted into public docs, or shared in screenshots.

## Key Handling Rules

- Generate a fresh key for each approved alpha scope.
- Do not reuse old local/dev keys.
- Store only safe preview/hash evidence in public reports.
- Return the full key only once in a private local packet.
- Deliver the key through a private approved channel.
- Do not expose keys in frontend code.
- Do not put keys in `.env.example`, docs, Git history, screenshots, or public reports.
- Revoke keys immediately if delivery is uncertain or the test ends.

## Vault And Namespace Setup

Each manual alpha scope should have:

- one `client_id`
- one `vault_id`
- one `namespace`
- one usage limit
- one active key at a time unless a rotation is explicitly approved

The vault and namespace should be scoped to the approved alpha use case only. Cross-client or cross-vault access must remain blocked.

## Statuses

The local workflow supports:

- `pending_manual_delivery`
- `delivered`
- `revoked`
- `archived`

Use `pending_manual_delivery` immediately after key creation. Mark `delivered` only after private delivery is complete. Mark `revoked` when access should stop. Mark `archived` when the onboarding record is closed.

## What To Say To Alpha Recipients

Use careful boundary language:

> This is a controlled-alpha test of PRMR Memory Core using synthetic or approved test data only. Access is manual, scoped, and revocable. It is not production access, billing, compliance approval, legal approval, bank approval, external security certification, or real-world validation.

## What Not To Promise

Do not promise:

- self-serve signup
- public onboarding
- production availability
- billing or paid account management
- bank approval
- compliance approval
- legal approval
- external security certification
- real-world validation
- final automated decisions
- use with real sensitive data unless separately approved

## Revocation

Revoke a key when:

- the alpha test is finished
- the recipient no longer needs access
- the key may have been exposed
- scope changes
- the recipient requests closure
- the founder/operator wants to rotate access

The V0.80 local runner verifies that a key validates before revocation and is blocked after revocation.

## Boundary

V0.80 is manual controlled-alpha onboarding evidence only. It does not prove dashboard auth, durable hosted account storage, billing, external alpha client testing, production readiness, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.
