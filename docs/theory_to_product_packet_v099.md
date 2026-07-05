# PRMR Memory Core V0.99 Theory-to-Product Packet

Truth label: V0.99 is a deterministic product implementation of PRMR concepts
for scoped software event streams. It does not claim full empirical validation
of PRMR theory, production security certification, compliance approval, legal
approval, or long-term external proof.

## Purpose

V0.99 upgrades `POST /v1/continuity/packet` from a minimal packet generator into
a deterministic Memory Core engine layer:

```text
events -> normalized signals -> PRMR continuity packet
```

The packet is computed inside the PRMR backend from scoped stored events for the
authenticated client, vault, and namespace. It is not dashboard-only display
logic, not client-product logic, and not LLM-generated text.

## Packet Fields

The API packet includes:

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

## Deterministic Product Approximation

This is a deterministic product approximation of PRMR concepts. The formulas are
simple, inspectable, and testable.

### Current State

`current_state` is the latest scoped event `content` after sorting by
`timestamp_index`, timestamp, and event ID.

### Active Information

`active_information` is derived from the recent event horizon. Each active row
contains:

- signal name;
- recent count;
- total count;
- latest content;
- last seen timestamp.

### Latent Information

`latent_information` contains historical signals that are absent from the recent
horizon. These are preserved as dormant continuity traces rather than deleted.

### Lineage Information

`lineage_information` is generated for repeated signals. It records:

- signal;
- count;
- first event ID;
- latest event ID;
- first seen;
- last seen;
- timestamp indexes.

### Causal Signature

`causal_signature` summarizes stable deterministic patterns:

- top event types;
- recurring signal names;
- signal frequency distribution;
- first seen / last seen by signal;
- transition pairs between event types;
- stable repeated patterns;
- safe source app distribution;
- safe actor/workspace continuity markers.

### Recursive Horizon

`recursive_horizon` separates a short recent window from the longer historical
signal set:

- short horizon event count;
- long horizon event count;
- horizon window size;
- recent signal set;
- historical signal set;
- overlapping signals;
- decayed or missing signals.

### Coherence Score

`coherence_score` is a deterministic 0-1 score. It combines:

- repeated signal ratio;
- overlap between recent and historical signals;
- workspace reference consistency;
- actor reference consistency;
- event volume.

It is a product signal, not a scientific measurement.

### Recoverability Score

`recoverability_score` is a deterministic 0-1 estimate of whether prior state
can be reconstructed from the current packet. It combines:

- event count;
- content/signal text presence;
- timestamp ordering;
- event ID/idempotency anchors;
- timestamp presence;
- lineage continuity.

It is a product heuristic, not a guarantee.

### Re-Emergence Signals

`re_emergence_signals` identifies signals that appear, disappear for a gap, and
then return later in the ordered event history.

### Decayed Signals

`decayed_signals` are historical signals absent from the recent horizon.

### Repeated Patterns

`repeated_patterns` includes repeated signal types and repeated transition pairs.

### State Transition Summary

`state_transition_summary` compares the previous ordered event with the current
event and records what signal/state transition occurred.

## External Event Compatibility

V0.99 builds on V0.98. Both legacy and generic external event shapes contribute
to packet computation.

Legacy:

```json
{
  "events": [
    {
      "type": "project_updated",
      "content": "User updated a project."
    }
  ]
}
```

Generic:

```json
{
  "event_type": "external.project.updated",
  "signal": "User updated a project in an external product.",
  "metadata": {
    "source_app": "external_product"
  },
  "occurred_at": "2026-07-05T00:00:00.000Z",
  "actor_reference": "hashed_actor",
  "workspace_reference": "hashed_workspace",
  "idempotency_key": "stable-event-id"
}
```

## Security Boundary

Packets remain scoped by authenticated API key. PRMR must not expose:

- raw API keys;
- Authorization headers;
- hashes;
- tokens;
- credentials;
- service role keys;
- database URLs;
- payment details;
- raw file contents;
- unsafe metadata.

Optional explicit scope headers remain assertions only. Wrong client, vault, or
namespace values are denied.

## What Is Not Proven

V0.99 does not prove:

- full scientific validation of PRMR theory;
- long-term memory quality over weeks or months;
- enterprise compliance;
- legal approval;
- external security certification;
- real-world performance on sensitive client datasets.

Those require later longitudinal tests and approved external evidence.
