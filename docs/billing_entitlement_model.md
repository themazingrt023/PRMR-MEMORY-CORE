# PRMR Billing and Entitlement Model

Truth label: billing foundation and entitlement model. Stripe or payment collection is not live in this sprint.

## Plans

- Free: self-serve sandbox activation, limited monthly requests.
- Builder: planned paid developer tier, not billed yet.
- Controlled Pilot: manual approval and manual commercial handling.

## Entitlements

Each plan can control:

- monthly request limit
- active key limit
- application count
- dashboard visibility
- support mode
- production environment eligibility

## Current State

The Free plan can activate automatically after verified identity. Builder and Controlled Pilot are visible as future/manual paths only. No checkout, invoice automation, or automatic paid entitlement is implemented.

## Required Before Live Billing

- payment provider integration
- webhook verification
- entitlement reconciliation
- downgrade and failed-payment behavior
- refund/cancellation policy
- tax and accounting review

No production, legal, compliance, or security certification is claimed here.
