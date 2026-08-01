"""Deterministic structural comparison for V2 packets."""

from __future__ import annotations

from typing import Any

from .continuity_v2_models import ContinuityPacketComparisonV2
from .source_integrity import canonical_json, sha256_text


def _ids(packet: dict[str, Any], layer: str, key: str = "event_id") -> set[str]:
    return {str(item[key]) for item in packet.get(layer, []) if item.get(key)}


def _change(first: Any, second: Any) -> dict[str, Any] | None:
    return None if first == second else {"from": first, "to": second}


def compare_packet_payloads(first: dict[str, Any], second: dict[str, Any]) -> ContinuityPacketComparisonV2:
    first_dimensions = {item["state_dimension_key"]: item for item in first["state_dimensions"]}
    second_dimensions = {item["state_dimension_key"]: item for item in second["state_dimensions"]}
    common_dimensions = sorted(set(first_dimensions) & set(second_dimensions))
    first_conflicts = {item["conflict_id"]: item for item in first["conflict_context"]}
    second_conflicts = {item["conflict_id"]: item for item in second["conflict_context"]}
    first_relationships = {
        item["relationship_id"]: item
        for values in first["relationship_context"].values()
        for item in values
    }
    second_relationships = {
        item["relationship_id"]: item
        for values in second["relationship_context"].values()
        for item in values
    }
    material: dict[str, Any] = {
        "first_packet_id": first["packet_id"],
        "second_packet_id": second["packet_id"],
        "boundary_changes": {
            "valid_at": _change(first["valid_at"], second["valid_at"]),
            "known_at": _change(first["known_at"], second["known_at"]),
        },
        "packet_status_change": _change(first["packet_status"], second["packet_status"]),
        "primary_state_change": _change(first["current_state"], second["current_state"]),
        "state_dimensions_added": sorted(set(second_dimensions) - set(first_dimensions)),
        "state_dimensions_removed": sorted(set(first_dimensions) - set(second_dimensions)),
        "state_dimension_changes": [
            {"state_dimension_key": key, "from": first_dimensions[key], "to": second_dimensions[key]}
            for key in common_dimensions
            if first_dimensions[key] != second_dimensions[key]
        ],
        "asserted_items_added": sorted(_ids(second, "asserted_information") - _ids(first, "asserted_information")),
        "asserted_items_removed": sorted(_ids(first, "asserted_information") - _ids(second, "asserted_information")),
        "tentative_items_added": sorted(_ids(second, "tentative_information") - _ids(first, "tentative_information")),
        "tentative_items_removed": sorted(_ids(first, "tentative_information") - _ids(second, "tentative_information")),
        "unknown_items_added": sorted(_ids(second, "unknown_information") - _ids(first, "unknown_information")),
        "unknown_items_resolved": sorted(_ids(first, "unknown_information") - _ids(second, "unknown_information")),
        "conflicts_opened": sorted(set(second_conflicts) - set(first_conflicts)),
        "conflicts_resolved": sorted(
            key for key in set(first_conflicts) & set(second_conflicts)
            if first_conflicts[key]["status"] == "open" and second_conflicts[key]["status"] == "resolved"
        ),
        "phase_changes": [],
        "reinforcement_changes": [],
        "re_emergence_changes": [],
        "entity_changes": (
            []
            if first["entity_context"] == second["entity_context"]
            else [{"from": first["entity_context"], "to": second["entity_context"]}]
        ),
        "relationship_changes": [
            {"relationship_id": key, "from": first_relationships.get(key), "to": second_relationships.get(key)}
            for key in sorted(set(first_relationships) | set(second_relationships))
            if first_relationships.get(key) != second_relationships.get(key)
        ],
        "provenance_changes": _change(first["provenance_context"], second["provenance_context"]) or {},
        "governance_changes": _change(first["governance_context"], second["governance_context"]) or {},
        "metric_changes": _change(first["v2_metrics"], second["v2_metrics"]) or {},
        "policy_changes": _change(first["packet_policy_configuration"], second["packet_policy_configuration"]) or {},
        "comparison_revision": "continuity_comparison_v2",
    }
    first_items = {
        item["event_id"]: item
        for name in ("asserted_information", "derived_information", "tentative_information", "unknown_information")
        for item in first[name]
    }
    second_items = {
        item["event_id"]: item
        for name in ("asserted_information", "derived_information", "tentative_information", "unknown_information")
        for item in second[name]
    }
    for event_id in sorted(set(first_items) & set(second_items)):
        before, after = first_items[event_id], second_items[event_id]
        if before.get("temporal_phase") != after.get("temporal_phase"):
            material["phase_changes"].append({"event_id": event_id, "from": before.get("temporal_phase"), "to": after.get("temporal_phase")})
        if before.get("reinforced") != after.get("reinforced"):
            material["reinforcement_changes"].append({"event_id": event_id, "from": before.get("reinforced"), "to": after.get("reinforced")})
        if before.get("re_emerging") != after.get("re_emerging"):
            material["re_emergence_changes"].append({"event_id": event_id, "from": before.get("re_emerging"), "to": after.get("re_emerging")})
    digest = sha256_text(canonical_json(material))
    return ContinuityPacketComparisonV2(comparison_hash=digest, **material)


__all__ = ["compare_packet_payloads"]
