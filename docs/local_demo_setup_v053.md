# PRMR Memory Core V0.53 Local Demo Setup

Purpose: provide a local controlled-alpha walkthrough for founder demos, pitch competition recordings, early buyer explanation, and internal product proof.

This is a local sandbox demo only. It does not provide hosted infrastructure, production readiness, banking approval, compliance approval, legal approval, external security approval, or real-world validation.

## Run

From the repository root:

```powershell
python examples/demo_v053_local_live_demo.py
```

The script prints a walkthrough and writes:

- `reports/v053/public_local_live_demo_v053.json`
- `reports/v053/private_internal_local_live_demo_v053.json`
- `reports/v053/scorecard_v053.md`

## Scenario

The demo uses synthetic account events only. It shows:

- client initialization in the local sandbox
- owner-scoped event ingest
- a messy state change over time
- continuity packet generation
- memory reconstruction
- public-safe explanation
- least-harm action
- owner report access
- wrong-key and cross-client denial
- alpha boundary reporting

## Boundaries

- Synthetic data only unless an approved dataset is explicitly provided.
- No billing.
- No hosted API claim.
- No production readiness claim.
- No banking, compliance, legal, external security, or real-world validation claim.
- No final punitive decisions.
- Public output is sanitized; detailed traces stay in the restricted report.
