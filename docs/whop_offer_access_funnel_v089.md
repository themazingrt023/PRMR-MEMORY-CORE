# V0.89 Whop PRMR Offer Page + Access Funnel

## Truth label

V0.89 prepares the PRMR Controlled Alpha Pilot offer and a configurable Whop
checkout-link funnel. It does not prove that the Whop product, price, checkout,
payment processing, webhook, or paid customer exists until those are configured
and verified externally.

Payment or waitlist intent does not approve a PRMR client, issue an API key,
unlock the dashboard, or bypass founder review.

## Chosen Whop path

Use a hosted Whop checkout link rather than embedding an SDK in V0.89. Whop's
official documentation describes checkout links as the lowest-effort option and
supports one-time pricing, subscriptions, waitlists, questions, stock limits,
auto-expiry, and post-checkout redirects:

- [Create a checkout link](https://docs.whop.com/manage-your-business/payment-processing/create-checkout-link)
- [Accept payments](https://docs.whop.com/developer/guides/accept-payments)

Webhooks and verified membership/payment events belong to V0.90:

- [Whop webhooks](https://docs.whop.com/developer/guides/webhooks)

## Offer

- **Name:** PRMR Controlled Alpha Pilot
- **Price copy:** From GBP 250
- **Recommended first checkout:** GBP 250 one-time
- **Access:** Manual founder approval only
- **Data:** Synthetic or explicitly approved non-sensitive data only
- **Duration:** Define the exact pilot window before publishing
- **Capacity:** Use a conservative stock limit that the founder can service

Included:

1. 15-minute onboarding call.
2. Limited controlled-alpha API access.
3. One manually issued copy-once test key.
4. Scoped client ID, vault ID, and namespace.
5. Usage limits and scoped request logs.
6. Continuity output and public-safe report.
7. Integration recommendation and feedback call.
8. Manual revoke path.

## Suggested Whop listing copy

### Headline

Give your system memory that evolves.

### Summary

PRMR Memory Core is a continuity infrastructure layer for products that need to
preserve what changed, what still matters, what became stale, and what needs
review. This controlled-alpha pilot is manually reviewed and uses synthetic or
explicitly approved non-sensitive data only.

### Commercial line

You build the app. PRMR preserves the memory layer underneath.

### Boundaries

- This is not a self-serve production API.
- Payment does not trigger automatic API key delivery.
- Access is manually approved and scoped.
- Sensitive data is not accepted without explicit approval.
- No production-readiness or certification claim is made.

## Whop dashboard setup

1. Create a Whop named **PRMR Memory Core**.
2. Create the product **PRMR Controlled Alpha Pilot**.
3. Create a one-time GBP 250 checkout link.
4. Enable a waitlist if payment should be held until founder approval.
5. Set a conservative stock/capacity limit.
6. Add these required questions:
   - What are you building?
   - Which PRMR use case do you want to test?
   - Will you use synthetic or approved non-sensitive data only?
   - Who will handle the server-side integration?
   - What outcome would make the pilot useful?
7. Do not enable automatic key delivery or unrestricted digital access.
8. Set the redirect to the controlled next-step page selected by the founder.
9. Copy the public checkout URL.
10. Set it in Vercel as `NEXT_PUBLIC_WHOP_CHECKOUT_URL`.
11. Redeploy and verify `/whop` opens the intended official Whop URL.

Only accept an HTTPS URL on `whop.com`. The frontend falls back to
`/alpha?source=whop-pilot` when the variable is absent or invalid.

## Funnel

1. Visitor reviews the pilot scope and boundaries.
2. Visitor uses Whop checkout/waitlist or the manual alpha request fallback.
3. Founder reviews fit, permitted data, capacity, and technical readiness.
4. V0.80 manual onboarding creates the scoped client, vault, and namespace.
5. V0.88 dashboard key creation returns the credential once.
6. Client uses PRMR server-side and monitors scoped usage and reports.

## V0.90 handoff

V0.90 should receive and verify signed Whop webhook events, store a minimal
idempotent event record, map payment/membership state to `pending_manual_review`,
and require an explicit operator approval before onboarding. No webhook event
should directly create a PRMR API key.

