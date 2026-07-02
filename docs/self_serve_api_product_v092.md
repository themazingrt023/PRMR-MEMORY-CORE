# PRMR Memory Core V0.92 Self-Serve API Product MVP

## Purpose

V0.92 turns the existing protected PRMR API into a generic API product flow:

1. Create an account.
2. Record email verification.
3. Select a plan.
4. Provision one client, vault, and default namespace.
5. Create a copy-once API key.
6. Use the key from a server-side environment.
7. Review scoped usage, request logs, reports, plan state, and key status.

The product is not tailored to any particular application. Each user receives a
random generic client and vault identifier.

## Functional service

The Python V0.92 service implements account creation, PBKDF2 password hashing,
local session-token hashing, plan state, monthly quotas, scoped key creation,
rotation, revocation, and protected PRMR calls.

The protected API validates the API key, client, vault, namespace, key status,
and usage boundary. Public dashboard state contains safe key previews only.

## Plans

| Plan | Requests | Scope | V0.92 activation |
| --- | ---: | --- | --- |
| Free | 100/month | 1 client, 1 vault, 1 namespace, 1 active key | Local MVP activation |
| Builder | 10,000/month | 1 client, up to 5 vaults, 10 namespaces, 5 keys | Billing not connected; no charge |
| Controlled Pilot | Custom | Manually agreed | Manual approval; from GBP 250 |

## Frontend boundary

The `/signup`, `/start`, and `/dashboard` routes provide the product shell and a
local browser walkthrough. Browser state never stores the password or a real
PRMR key. Public deployment does not pretend that a durable account was created.

## Current limits

- Email verification is a labelled local/test state. No email is sent.
- Payment processing is not connected.
- The self-serve account/key registry is not deployed to a durable hosted database.
- The hosted protected API exists, but V0.92 user provisioning is proven locally.
- This is not production security certification, legal or compliance approval, enterprise readiness, guaranteed scale, or external launch evidence.
