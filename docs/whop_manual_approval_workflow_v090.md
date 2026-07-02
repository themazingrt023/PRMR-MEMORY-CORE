# V0.90 Whop to Manual Approval Workflow

## Truth label

V0.90 is verified Whop event intake and a durable manual-review queue. It does
not prove that the hosted endpoint is deployed, that a live Whop webhook has
been received, that a real payment has succeeded, or that a client has been
approved.

A Whop event can never create a PRMR API key or dashboard session directly.

## Official event contract

Whop documents that webhooks:

- must be signature verified before the payload is trusted;
- use the Standard Webhooks format;
- may be delivered more than once;
- do not guarantee ordering;
- should receive a quick 2xx response after verification and minimal intake.

Sources:

- [Whop webhook guide](https://docs.whop.com/developer/guides/webhooks)
- [Whop payment.succeeded event](https://docs.whop.com/api-reference/payments/payment-succeeded)
- [Whop membership.activated event](https://docs.whop.com/api-reference/memberships/membership-activated)
- [Standard Webhooks specification](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md)

V0.90 uses the pinned `standardwebhooks==1.0.1` Python verifier and stores
`webhook-id` as a unique SQLite key for idempotency.

## Intake route

Deployable entrypoint:

```text
prmr.product.api_server_v090:app
```

Route:

```text
POST /v1/integrations/whop/webhook
```

The route reads the raw request body, verifies the Standard Webhooks headers,
checks the configured Whop company and product IDs, stores a minimal review
record, and returns the intake result.

Required server-only environment variables:

```env
WHOP_WEBHOOK_SECRET=<FRESH_WHOP_WEBHOOK_SECRET>
WHOP_EXPECTED_COMPANY_ID=<WHOP_COMPANY_ID>
WHOP_EXPECTED_PRODUCT_ID=<WHOP_PRODUCT_ID>
```

Never use a `NEXT_PUBLIC_*` variable for the webhook secret.

## Review statuses

- `pending_manual_review`: verified waitlist, successful payment, or active
  membership event in the expected company/product scope.
- `access_review_required`: failed payment, deactivated membership, refund, or
  dispute event that needs operator attention.
- `approved_for_manual_onboarding`: an operator reviewed the record and approved
  the next manual onboarding step.
- `rejected`: an operator rejected the request.

Approval only creates a safe handoff packet for V0.80/V0.88 onboarding. The
packet contains no credential and does not start onboarding automatically.

## Stored data

Stored:

- webhook ID;
- event type and timestamp;
- external payment/membership/waitlist reference;
- expected company, product, and plan references;
- hashed external user reference;
- amount and currency when present;
- review status and operator audit fields.

Not stored:

- raw webhook secret;
- raw API keys or dashboard tokens;
- card or payment-method details;
- customer name, email, address, or phone;
- unrestricted webhook payload.

## Operator procedure

1. Confirm the event is signature verified and in the expected company/product
   scope.
2. Confirm the Whop payment, waitlist, or membership status in Whop.
3. Review the submitted use case and data boundary.
4. Confirm the client will use synthetic or explicitly approved non-sensitive
   data.
5. Approve or reject with an operator ID and reason.
6. If approved, separately run the V0.80/V0.88 manual onboarding flow.
7. Deliver the copy-once key through an approved private channel.
8. Keep revoke and usage monitoring available.

## Deployment procedure

Do not change the live Render start command until:

1. The Whop product and checkout/waitlist link exist.
2. Fresh server-side environment values are configured on Render.
3. Durable storage is mounted or a managed database replacement is ready.
4. The V0.90 local runner and audit pass.
5. A Whop test webhook succeeds against a staging endpoint.

Then change the Render start command to:

```text
uvicorn prmr.product.api_server_v090:app --host 0.0.0.0 --port $PORT
```

Configure the Whop webhook URL as:

```text
https://prmr-memory-core-api.onrender.com/v1/integrations/whop/webhook
```

Subscribe only to the events the workflow handles. Start with:

- `entry.created`
- `payment.succeeded`
- `payment.failed`
- `membership.activated`
- `membership.deactivated`
- `refund.created`
- `dispute.created`

External deployment and live event evidence remain future manual steps.

