# V0.88 API Client Dashboard + Key Creation MVP

## Truth label

V0.88 is an approved-client dashboard and key-management MVP using controlled
synthetic evidence. It is not open public signup, unreviewed self-serve access,
production authentication, production billing, compliance or legal approval,
external security certification, or real-world client validation.

## Approved-client flow

1. A founder/operator approves and scopes a client manually.
2. The approved client opens its scoped dashboard.
3. The client enters a useful key label and selects **Create API Key**.
4. PRMR returns the credential value in that response only.
5. The client copies it into a private server-side `.env` file.
6. Later dashboard views show only the key ID, label, safe preview, status, and
   last-use metadata.
7. The client monitors usage, request logs, public-safe continuity reports,
   vaults, namespaces, and memory health.
8. The client rotates or revokes a key when needed.

An unapproved or random client is denied. V0.88 does not add a public signup
path or automatic approval.

## Copy-once key behavior

Create and rotate responses contain the newly generated API key once. The
service stores a SHA-256 hash for validation and a safe preview for display. It
does not retain the generated credential value in dashboard state, key lists,
public reports, or private audit reports.

The UI warning is:

> Copy this key now. PRMR will not show it again.

Rotation immediately marks the old key as rotated and returns one replacement
credential value. Revocation marks the selected key as revoked. Rotated and
revoked values fail later validation.

## Server-side `.env` quickstart

```env
PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<YOUR_PRMR_KEY>
PRMR_CLIENT_ID=<CLIENT_ID>
PRMR_VAULT_ID=<VAULT_ID>
PRMR_NAMESPACE=default
```

Do not expose PRMR API keys in frontend or browser code. Use them server-side only.
Keep credentials in a trusted server process and do not commit `.env` files.

## Dashboard sections

- **Overview**: approved client, scope, and synthetic/local boundary.
- **API Keys**: create, copy once, safe previews, rotate, and revoke.
- **Vaults & Namespaces**: the client-owned API scope.
- **Usage**: allowed/blocked counts and controlled-alpha limits.
- **Request Logs**: public-safe operation outcomes scoped to the client.
- **Continuity Reports**: client-owned public-safe report references.
- **Memory Health**: event, packet, reconstruction, and report availability.
- **Quickstart**: server-side environment setup and operating sequence.

## Public and local modes

The deployed public frontend keeps `/dashboard` locked unless controlled
dashboard access is explicitly configured. It does not expose real client data,
dashboard tokens, or API keys.

Local development mode provides an interactive synthetic preview. Its Next.js
route creates transient, non-functional local credentials and does not persist
them. The Python V0.88 runner independently verifies the actual lifecycle model:
hash storage, safe listing, validation, rotation, revocation, usage, logs, and
reports.

## Current limitations

- Client approval is manual.
- Dashboard authentication is still controlled-alpha scope evidence, not
  production identity/authentication.
- The local interactive key preview is not connected to hosted key persistence.
- Durable hosted storage remains a prerequisite for real external alpha data.
- Billing automation and the Whop approval bridge are future milestones.
- Synthetic or explicitly approved non-sensitive data only.
