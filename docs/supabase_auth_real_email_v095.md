# PRMR V0.95 Supabase Auth and Real Email Confirmation

## Purpose

V0.95 changes the normal hosted signup and login path from PRMR's historical
local/test verification state to Supabase Auth email/password identity.

Supabase owns:

* password handling
* signup and login
* confirmation-email delivery
* confirmation links
* browser identity sessions

PRMR owns:

* the durable mapping from confirmed identity to PRMR user
* plan state
* client, vault, and namespace provisioning
* copy-once PRMR API keys
* usage, reports, and dashboard state

Supabase session tokens and PRMR API keys are separate credentials. A Supabase
session opens the dashboard. A PRMR API key is used server-side by a client's
application.

This is an Auth integration MVP. It is not Stripe billing, production
authentication hardening, enterprise SSO, compliance approval, legal approval,
or external security certification.

## Supabase project setup

1. Create or select a Supabase project.
2. In Authentication providers, keep Email enabled.
3. Enable email confirmations.
4. Set the production Site URL to:

   ```text
   https://afternumindustries.co.uk
   ```

5. Add exact redirect URLs:

   ```text
   https://afternumindustries.co.uk/auth/callback
   https://www.afternumindustries.co.uk/auth/callback
   https://prmr-memory-core.vercel.app/auth/callback
   http://localhost:3000/auth/callback
   ```

   Production confirmation tests should use
   `https://afternumindustries.co.uk`. Keep the Vercel callback during the
   domain transition so links started on the fallback domain still complete.
   If a Vercel preview deployment is
   tested, add that exact preview callback URL separately:

   ```text
   https://<preview-domain>/auth/callback
   ```

   A production confirmation link cannot establish a session on a different
   preview domain because the PKCE verifier and auth cookies belong to the
   browser/domain where signup began.

6. Review the Confirm signup email template. If the template uses a redirect
   target, ensure it respects the requested redirect URL.
7. Before external launch, configure a custom SMTP sender/domain. Supabase's
   default email service is suitable for initial testing but is rate-limited
   and best-effort.

Do not place a Supabase secret key or service-role key in the frontend.

## Vercel environment

Set these for Production and the intended Preview environments:

```text
NEXT_PUBLIC_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<SUPABASE_PUBLISHABLE_OR_LEGACY_ANON_KEY>
PRMR_HOSTED_API_URL=https://prmr-memory-core-api.onrender.com
```

These two `NEXT_PUBLIC_` values are browser configuration. They are not
service-role credentials. After changing them, redeploy Vercel.

## Render environment

Keep the V0.94.1 Postgres configuration and add:

```text
PRMR_AUTH_BACKEND=supabase
SUPABASE_PROJECT_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<SUPABASE_PUBLISHABLE_OR_LEGACY_ANON_KEY>
```

Existing storage values remain:

```text
PRMR_STORAGE_BACKEND=postgres
DATABASE_URL=<POOLED_POSTGRES_CONNECTION_STRING>
PRMR_DURABLE_STORAGE_VERIFIED=true
PRMR_ALLOWED_ORIGINS=https://afternumindustries.co.uk,https://www.afternumindustries.co.uk,https://prmr-memory-core.vercel.app
```

`DATABASE_URL` remains server-only. No Supabase service-role key is required by
this bridge.

Render start command:

```text
uvicorn prmr.product.api_server_v094:app --host 0.0.0.0 --port $PORT
```

## Hosted auth flow

```text
/signup
-> supabase.auth.signUp
-> Supabase confirmation email
-> /auth/callback
-> exchangeCodeForSession
-> /start
-> choose plan
-> Vercel server proxy reads verified Supabase session
-> Render verifies token with Supabase Auth
-> PRMR maps identity and provisions scope
-> /dashboard
-> copy-once PRMR API key
```

The hosted frontend no longer calls PRMR's local verification endpoint.
When `PRMR_AUTH_BACKEND=supabase`, the backend returns `410
local_mvp_auth_disabled` for the historical local signup, verification, login,
and local-session routes.

## Identity mapping

The Render bridge validates the access token using:

```text
GET <SUPABASE_PROJECT_URL>/auth/v1/user
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
apikey: <SUPABASE_PUBLISHABLE_KEY>
```

Only an `authenticated` identity with `email_confirmed_at` may proceed.
Unconfirmed and unauthenticated requests do not create users, scopes, or keys.

PRMR maps by normalized email when a record already exists. Otherwise it uses a
one-way hash of the Supabase subject to create a stable PRMR user ID. PRMR does
not store the Supabase password. User metadata may supply a display name, but
it is never used for authorization.

## Plan behavior

* Free: activates and can provision a PRMR client, vault, and namespace.
* Builder: selectable as an unbilled beta state; no Stripe charge is claimed.
* Controlled Pilot: remains manual approval/custom access.

## Verification commands

Without configured Supabase variables:

```powershell
python examples/run_supabase_auth_real_email_v095.py
```

Expected:

```text
NEEDS_SUPABASE_ENV
```

Static and deterministic fixture audit:

```powershell
python examples/audit_v095_supabase_auth_real_email.py
```

The audit may PASS readiness while the integration runner remains
`NEEDS_SUPABASE_ENV`. That is not real email evidence.

No automated test sends an email unless a future test is deliberately
configured with `PRMR_SUPABASE_EMAIL_TEST_RECIPIENT`. V0.95 does not store or
print that value in reports.

## Remaining work

* Configure Supabase and run one controlled real confirmation email.
* Configure custom SMTP and a verified sender domain before external launch.
* Add production session hardening, revocation handling, abuse protection, and
  account recovery review.
* Connect Stripe before paid Builder activation.
* Perform external security and operational validation separately.

References:

* <https://supabase.com/docs/guides/auth/passwords>
* <https://supabase.com/docs/guides/auth/redirect-urls>
* <https://supabase.com/docs/guides/auth/jwts>
