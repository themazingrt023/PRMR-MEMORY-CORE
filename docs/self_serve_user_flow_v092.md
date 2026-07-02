# V0.92 Self-Serve User Flow

## 1. Sign up

Open `/signup` and enter name, email, password, plan, and boundary acceptance.
The Python service hashes passwords with PBKDF2. Public reports never include
passwords, password hashes, or session tokens.

## 2. Verify

V0.92 uses `local_simulated_no_email_sent`. The account moves from `unverified`
to `verified`, but no message is sent and the interface says so.

## 3. Choose a plan

Free activates in the local MVP. Builder records selection as
`selected_billing_not_live` and processes no payment. Controlled Pilot records
`pending_manual_approval`.

## 4. Provision a workspace

An active user receives a random `client_ss_*` client, a random `vault_ss_*`
vault, and the `default` namespace. These are generic PRMR scopes.

## 5. Create a key

PRMR returns the credential value in the creation response once. It retains a
SHA-256 hash and safe preview. Later key lists never return the credential.

## 6. Build server-side

Place the five PRMR variables in a server-side `.env`. Do not put them in
browser code, `NEXT_PUBLIC_*` variables, screenshots, public reports, or Git.

## 7. Operate

The dashboard presents overview, keys, usage, request logs, continuity reports,
vaults and namespaces, quickstart, plan state, account state, and support.
Rotation blocks the old key. Revocation blocks the revoked key.

## Evidence boundary

The protected operations and lifecycle checks are executable local/deployable
MVP evidence. Real email, payments, durable hosted account storage, production
auth hardening, and external launch remain unfinished.

