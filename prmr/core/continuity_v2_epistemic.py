"""Epistemic projection that never strengthens stored memory status."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .continuity_v2_policy import epistemic_weight, state_role
from .memory_recurrence import signal_identity


def event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    outer = event.get("external_metadata")
    metadata = outer.get("metadata") if isinstance(outer, dict) else None
    return dict(metadata) if isinstance(metadata, dict) else {}


def event_type(event: dict[str, Any]) -> str:
    return str(event.get("type") or event.get("event_type") or "event.recorded")


def event_signal(event: dict[str, Any]) -> str:
    key, _ = signal_identity(event)
    return str(key)


def event_content(event: dict[str, Any]) -> str:
    return str(event.get("content") or event.get("signal") or "")[:1200]


def event_time(event: dict[str, Any]) -> str:
    return str(event.get("timestamp") or event.get("occurred_at") or "")


def stored_epistemic_status(event: dict[str, Any], projection: Any | None = None) -> str:
    raw = str(
        getattr(projection, "epistemic_status", "")
        or event_metadata(event).get("epistemic_status")
        or "legacy_unclassified"
    )
    return raw if raw in {"explicit", "derived", "inferred", "unknown"} else "legacy_unclassified"


def packet_epistemic_class(status: str) -> str:
    return {
        "explicit": "asserted",
        "derived": "derived_assertion",
        "inferred": "tentative",
        "unknown": "unknown",
        "legacy_unclassified": "asserted",
    }[status]


def quantize8(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def project_epistemic_information(
    events: list[dict[str, Any]],
    projections_by_event: dict[str, Any],
    dynamics_by_signal: dict[str, Any],
    signal_projection: dict[str, dict[str, Any]],
    provenance_by_event: dict[str, dict[str, Any]],
    *,
    signal_identity_mode: str,
) -> dict[str, list[dict[str, Any]]]:
    layers: dict[str, list[dict[str, Any]]] = {
        "asserted_information": [],
        "derived_information": [],
        "tentative_information": [],
        "unknown_information": [],
        "conflicted_information": [],
    }
    layer_name = {
        "asserted": "asserted_information",
        "derived_assertion": "derived_information",
        "tentative": "tentative_information",
        "unknown": "unknown_information",
    }
    for event in sorted(events, key=lambda item: (event_time(item), str(item.get("event_id", "")))):
        event_id = str(event.get("event_id", ""))
        projection = projections_by_event.get(event_id)
        status = stored_epistemic_status(event, projection)
        packet_class = packet_epistemic_class(status)
        original_signal = event_signal(event)
        mapped = signal_projection.get(original_signal, {})
        selected_signal = str(mapped.get("canonical_signal_key") or original_signal)
        dynamic = dynamics_by_signal.get(selected_signal) or dynamics_by_signal.get(original_signal)
        raw_influence = float(getattr(dynamic, "final_influence", 0.0))
        weight = epistemic_weight(status)
        metadata = event_metadata(event)
        role = state_role(event_type(event), metadata)
        state_key = str(metadata.get("state_key") or selected_signal)
        conflict_ids = sorted(
            set(getattr(projection, "open_conflict_ids", []) if projection else [])
        )
        provenance = provenance_by_event.get(event_id, {})
        item = {
            "event_id": event_id,
            "signal": event_content(event),
            "event_type": event_type(event),
            "original_signal_key": original_signal,
            "canonical_signal_key": mapped.get("canonical_signal_key"),
            "state_dimension": state_key,
            "state_role": role,
            "state_value": str(metadata.get("state_value") or event_content(event)),
            "epistemic_status": status,
            "packet_epistemic_class": packet_class,
            "temporal_phase": getattr(dynamic, "memory_phase", None),
            "temporal_horizon": getattr(dynamic, "latest_horizon", None),
            "raw_temporal_influence": quantize8(raw_influence),
            "epistemic_weight": weight,
            "continuity_influence": quantize8(raw_influence * weight),
            "reinforced": bool(getattr(dynamic, "reinforced", False)),
            "re_emerging": bool(getattr(dynamic, "re_emerging", False)),
            "conflict_ids": conflict_ids,
            "entity_links": [],
            "evidence_completeness": provenance.get("status", "unavailable"),
            "provenance_references": provenance.get("references", []),
            "occurred_at": event_time(event),
            "valid_from": getattr(projection, "valid_from", event_time(event)),
            "known_from": getattr(projection, "system_known_from", event_time(event)),
            "signal_identity_mode": signal_identity_mode,
            "continuity_epistemic_projection_revision": "continuity_epistemic_projection_v1",
        }
        layers[layer_name[packet_class]].append(item)
        if conflict_ids:
            layers["conflicted_information"].append(dict(item))
    return layers


__all__ = [
    "event_content",
    "event_metadata",
    "event_signal",
    "event_time",
    "event_type",
    "packet_epistemic_class",
    "project_epistemic_information",
    "quantize8",
    "stored_epistemic_status",
]
