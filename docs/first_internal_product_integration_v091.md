# V0.91 First Internal Product Integration

## Truth label

V0.91 is the first internal server-side consumer of the PRMR HTTP API using a
controlled synthetic client scope. It proves the client workflow locally:

1. create a copy-once key;
2. put it in a temporary server-side `.env`;
3. load a scoped PRMR client;
4. ingest synthetic events;
5. generate and reconstruct continuity;
6. request explanation and least-harm output;
7. read the owned public-safe report and usage summary.

It does not prove a hosted internal integration until the same workflow passes
against the deployed backend with a dedicated controlled internal scope.

## Integration client

Module:

```text
prmr.integrations.internal_product_client_v091
```

Required server-side environment:

```env
PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<COPY_ONCE_PRMR_KEY>
PRMR_CLIENT_ID=<INTERNAL_CLIENT_ID>
PRMR_VAULT_ID=<INTERNAL_VAULT_ID>
PRMR_NAMESPACE=default
```

Never put `PRMR_API_KEY` in:

- browser JavaScript;
- a `NEXT_PUBLIC_*` variable;
- source control;
- public reports;
- screenshots, chat, tickets, or shared documents.

The V0.91 runner writes the synthetic key only into a temporary directory
outside the repository and lets the operating system remove it when the test
finishes.

## Internal scenario

The synthetic scenario represents an Afternum build-session memory:

- a technical direction is selected;
- a storage or access boundary changes;
- the latest decision should remain active;
- older assumptions should become stale;
- the current state should be reconstructable without replaying the entire raw
  history in the consuming application.

This is internal synthetic evidence, not external product validation.

## Hosted follow-up

To run the same internal client against Render, create a fresh dedicated
internal client scope and set the five environment variables in a private
operator shell. Do not reuse V0.79 smoke credentials or any old local key.

The hosted result must remain `SKIPPED_NEEDS_INTERNAL_SCOPE` until those values
exist. A local pass must not be relabelled as a hosted pass.

