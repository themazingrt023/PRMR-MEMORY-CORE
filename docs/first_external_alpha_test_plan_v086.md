# V0.86 First External Controlled Alpha Test Plan

Truth label: external alpha test preparation only. This does not claim real external validation until a real tester completes the flow and feedback is recorded.

Do not treat a first alpha attempt as validation. It is one controlled external test attempt until the tester completes the flow, feedback is recorded, and evidence is reviewed honestly.

## Who Qualifies As First Tester

The first external controlled alpha tester should be one of:

- an AI startup founder
- an AI agent builder
- a SaaS founder or product operator
- a customer support or operations builder
- an education, legal, or research AI builder
- a fintech/risk reviewer using synthetic sandbox data only
- a technical collaborator who can give concrete product feedback

They should understand that this is controlled alpha testing, not production access.

## What They May Test

Allowed:

- API setup using placeholders and approved credentials
- synthetic event ingestion
- continuity packet generation
- memory/state reconstruction
- public-safe explanation
- least-harm action boundary
- public-safe report fetch
- scoped usage view
- dashboard access if separately approved
- feedback on client/vault/namespace clarity

## Data Allowed

Allowed by default:

- synthetic data
- toy examples
- fictional users
- public demo content
- approved non-sensitive test data

## Data Not Allowed

Do not use:

- real sensitive personal data
- production customer data
- payment card data
- bank credentials
- health records
- legal privileged material
- secrets, passwords, API keys, private tokens, or private logs
- data from third parties without approval

## What Success Means

Success means the tester can complete the controlled flow with synthetic or approved non-sensitive data and provide useful feedback.

Success does not mean production readiness, external validation, compliance approval, legal approval, bank approval, or external security certification.

## What Failure Means

Failure means the test did not complete, the setup was unclear, the product behavior was confusing, safety boundaries were insufficient, or a scoped access issue appeared.

Failure should be recorded honestly as `completed_needs_work`, `not_completed`, or `revoked`.

## Revoke Process

Revoke access when:

- the test is complete
- the tester asks to stop
- the test scope changes
- a key or dashboard token may have been exposed
- the tester attempts to use disallowed data
- the founder/operator decides the risk is too high

Record whether access was revoked or kept open in the evidence record.

## Feedback Collection

Collect feedback using `docs/first_alpha_feedback_questions_v086.md`.

Ask for:

- setup clarity
- endpoint clarity
- dashboard/report usefulness
- continuity concept clarity
- confusion points
- strongest use case
- pilot requirements
- trust/security concerns
- next-test improvements

## Evidence Recording

Use `docs/first_alpha_evidence_record_template_v086.md`.

Record:

- tester pseudonym or approved name only
- date/time
- data-safety confirmation
- endpoints tested
- dashboard tested
- issues found
- feedback summary
- next actions
- access status
- honest result status

## Honest Result Status

Use one of:

- `completed_positive`
- `completed_mixed`
- `completed_needs_work`
- `not_completed`
- `revoked`

## Boundary

This is first external controlled alpha preparation only. Do not claim real external validation until a real tester completes the flow and feedback is recorded. Do not use sensitive real client data. Do not issue access automatically. Do not promise production readiness, billing, compliance approval, legal approval, bank approval, or external security certification.
