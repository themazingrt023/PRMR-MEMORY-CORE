# PRMR Memory Core V1.0 Dashboard Observability

Truth label: V1.0 improves the real Afternum/PRMR API dashboard observability
and a manual plan-upgrade shell. It does not implement Stripe billing, does not
claim enterprise certification, and does not replace future billing, security,
or compliance work.

## Purpose

The dashboard should let a developer/client inspect their own PRMR API usage,
request logs, continuity reports, packet history, plan status, and storage
boundary safely.

This is an Afternum API dashboard upgrade. It is not Continuum OS work and not a
marketing page.

## Request Logs

The dashboard supports a full request log view with:

- total log count;
- paginated rows;
- latest-first ordering;
- load-more behavior;
- method;
- endpoint/path;
- status;
- allowed/denied;
- scoped client/vault/namespace references;
- rejection reason when available;
- public-safe message;
- log ID.

The request log view must not expose:

- Authorization headers;
- raw API keys;
- hashes;
- request bodies containing secrets;
- database URLs;
- service role keys;
- tokens.

## Continuity Reports

The dashboard supports paginated continuity reports with:

- total report count;
- latest-first ordering where packet timestamps are available;
- report ID;
- packet ID;
- summary;
- endpoint/source;
- event count.

The report detail view safely renders V0.99 packet fields when available:

- `current_state`
- `active_information`
- `latent_information`
- `lineage_information`
- `causal_signature`
- `recursive_horizon`
- `coherence_score`
- `recoverability_score`
- `re_emergence_signals`
- `decayed_signals`
- `repeated_patterns`
- `state_transition_summary`
- `event_count`
- `last_updated`

Older reports may show:

```text
Older report format. Limited packet fields available.
```

## Packet Tester

The dashboard includes a server-side/authenticated button:

```text
Generate Continuity Packet
```

It generates a continuity packet for the authenticated dashboard user's own
client, vault, and namespace. The browser never receives raw API keys for this
operation.

## Plan Upgrade Shell

The dashboard shows:

- current plan;
- usage limit;
- requests used;
- requests remaining;
- an `Upgrade plan` button.

Clicking the upgrade button opens a manual beta shell:

```text
Billing is not connected yet. Builder and Pilot access are currently handled
manually during controlled beta.
```

Displayed tiers:

- Free: 100 requests/month
- Builder: 10,000 requests/month, manual beta access
- Controlled Pilot: custom/manual access

There is no fake Stripe checkout and no claim that payment is live.

## Storage Boundary

The storage panel shows:

- storage backend;
- storage mode;
- database connected true/false;
- durable storage verified true/false;
- raw key storage false;
- raw password storage false;
- public-safe status;
- storage boundary explanation.

Suggested public-safe explanation:

```text
PRMR stores account, key metadata, usage logs, reports, and continuity state in
hosted managed Postgres. Raw API keys are shown once and are not stored. Stored
key material remains hashed.
```

The dashboard must not expose:

- database URL;
- database password;
- connection string;
- service role key;
- raw secrets.

## Backend Support

The hosted backend supports Supabase-authenticated dashboard routes for:

- paginated request logs;
- paginated reports;
- report detail;
- dashboard packet generation;
- plan status;
- storage boundary.

All routes are scoped through the authenticated Supabase identity mapped to its
PRMR client/vault/namespace.

## Remaining Gaps

V1.0 does not include:

- Stripe billing;
- self-serve paid plan activation;
- enterprise billing operations;
- advanced query/filter UI beyond the first safe shell;
- external security certification;
- compliance/legal approval.
