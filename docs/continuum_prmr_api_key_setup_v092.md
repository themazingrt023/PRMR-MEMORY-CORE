# V0.92 Continuum OS PRMR API Key Setup

## Product boundary

Continuum OS and PRMR Memory Core are separate products.

- **Continuum OS** is the first approved internal client.
- **PRMR Memory Core** is the independent API infrastructure provider.
- Continuum OS must use PRMR through the same scoped HTTP contract intended for
  an external approved client.

V0.92 is first internal-client provisioning evidence using synthetic Continuum
events and local protected PRMR logic. It is not open signup, automatic billing,
production authentication, compliance approval, or external security
certification.

## Provisioned scope

```text
Client ID: client_continuum_os
Product: Continuum OS
Status: approved_internal_client
Vault ID: vault_continuum_os
Namespace: default
```

The access runtime uses an active internal record while the product-facing
approval status remains `approved_internal_client`.

## Private environment packet

The runner writes the one-time credential packet to:

```text
reports/v092/private_continuum_env_packet_v092.json
```

`reports/` is ignored by Git. The packet is classified:

```text
PRIVATE LOCAL ONLY. DO NOT COMMIT. DO NOT SHARE.
```

It contains:

```env
PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<COPY_ONCE_PRMR_KEY>
PRMR_CLIENT_ID=client_continuum_os
PRMR_VAULT_ID=vault_continuum_os
PRMR_NAMESPACE=default
```

The raw key is released once by the provisioning service. Later dashboard and
report views retain only its key ID and safe preview.

## Important activation boundary

The generated key is validated against local protected PRMR logic during V0.92.
It is **not yet registered in the currently deployed Render backend**.

Do not place the packet into the actual Continuum OS application until:

1. PRMR has durable hosted storage.
2. The Continuum client, vault, namespace, key hash, and usage limit are
   installed in that hosted store through an operator-only path.
3. A hosted scoped smoke proves the key works at the configured base URL.
4. The local packet is transferred to Continuum OS through a private approved
   channel.

Without those steps, the key is a real generated credential record in local
PRMR evidence but is not a live hosted credential.

## Continuum OS server-side configuration

Store the variables in the Continuum OS server environment only. Do not put the
key in:

- `NEXT_PUBLIC_*` variables;
- browser JavaScript or mobile client code;
- source control;
- public logs, reports, screenshots, or support messages.

The server should send:

```http
Authorization: Bearer <PRMR_API_KEY>
X-Client-ID: client_continuum_os
X-Vault-ID: vault_continuum_os
X-Namespace: default
Content-Type: application/json
```

## Event intake

Continuum OS can send synthetic or explicitly approved non-sensitive events:

- `mission_created`
- `mission_completed`
- `project_updated`
- `habit_completed`
- `money_action_logged`
- `sunday_reset_completed`

Example:

```json
{
  "events": [
    {
      "event_id": "continuum-event-001",
      "user_id": "synthetic_continuum_user",
      "type": "mission_created",
      "content": "A synthetic mission was created.",
      "timestamp": "2026-07-01T09:00:00Z",
      "timestamp_index": 1
    }
  ]
}
```

## Outputs

The V0.92 flow exercises:

- event ingest;
- continuity packet generation;
- memory reconstruction;
- public-safe explanation;
- least-harm action;
- owner-scoped report retrieval;
- owner-scoped usage retrieval;
- safe dashboard state.

No real Continuum user data is permitted by default.

