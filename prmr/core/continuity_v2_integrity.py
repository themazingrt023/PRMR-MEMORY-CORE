"""Independent structural integrity checks for persisted V2 packets."""

from __future__ import annotations

from typing import Any

from .continuity_v2_models import (
    CONTINUITY_V2_INTEGRITY_REVISION,
    CONTINUITY_V2_SCHEMA_REVISION,
    ContinuityPacketV2IntegrityResult,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope
from .continuity_v2_epistemic import quantize8
from .continuity_v2_policy import epistemic_weight


def packet_identity_material(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": [packet["client_id"], packet["vault_id"], packet["namespace"]],
        "subject_scope": {
            "application_reference": packet.get("application_reference"),
            "actor_reference": packet.get("actor_reference"),
            "workspace_reference": packet.get("workspace_reference"),
            "entity_id": packet.get("entity_id"),
            "session_reference": packet.get("session_reference"),
        },
        "valid_at": packet["valid_at"],
        "known_at": packet["known_at"],
        "packet_mode": packet["packet_mode"],
        "policy": packet["packet_policy_configuration"],
        "signal_identity_mode": packet["packet_policy_configuration"]["signal_identity_mode"],
        "effective_event_manifest": packet["effective_event_manifest_hash"],
        "temporal_dynamics_snapshot_id": packet["temporal_dynamics_snapshot_id"],
        "entity_manifest": packet["entity_manifest_hash"],
        "relationship_manifest": packet["relationship_manifest_hash"],
        "conflict_manifest": packet["conflict_manifest_hash"],
        "canonical_signal_manifest": packet["canonical_signal_manifest_hash"],
        "governance_manifest": packet["governance_manifest_hash"],
        "revisions": packet["revisions"],
    }


def packet_id_for(packet: dict[str, Any]) -> str:
    return "pktv2_" + sha256_text(canonical_json(packet_identity_material(packet)))[:32]


def packet_hash_for(packet: dict[str, Any]) -> str:
    payload = {key: value for key, value in packet.items() if key != "packet_hash"}
    return sha256_text(canonical_json(payload))


def packet_manifest_hash_for(packet: dict[str, Any]) -> str:
    material = {
        "current_state": packet["current_state"],
        "state_dimensions": [item["state_dimension_hash"] for item in packet["state_dimensions"]],
        "epistemic_layers": {
            name: [item["event_id"] for item in packet[name]]
            for name in ("asserted_information", "derived_information", "tentative_information", "unknown_information", "conflicted_information")
        },
        "conflicts": [item["conflict_hash"] for item in packet["conflict_context"]],
        "entities": [item["entity_view_hash"] for item in packet["entity_context"]],
        "relationships": sorted(
            item["relationship_hash"]
            for values in packet["relationship_context"].values()
            for item in values
        ),
        "lineage": packet["lineage_context"]["lineage_manifest_hash"],
        "provenance": packet["provenance_context"]["provenance_manifest_hash"],
        "governance": packet["governance_context"]["governance_context_hash"],
        "metrics": packet["v2_metrics"],
        "revision": CONTINUITY_V2_SCHEMA_REVISION,
    }
    return sha256_text(canonical_json(material))


def verify_packet_v2_integrity(
    scope: AuthenticatedScope,
    packet: dict[str, Any],
) -> ContinuityPacketV2IntegrityResult:
    checks: dict[str, bool] = {}
    checks["packet_identity"] = packet.get("packet_id") == packet_id_for(packet)
    checks["packet_hash"] = packet.get("packet_hash") == packet_hash_for(packet)
    checks["packet_manifest"] = packet.get("packet_manifest_hash") == packet_manifest_hash_for(packet)
    checks["authenticated_scope"] = tuple(
        packet.get(key) for key in ("client_id", "vault_id", "namespace")
    ) == scope.memory_boundary()
    checks["schema_revision"] = packet.get("packet_version") == CONTINUITY_V2_SCHEMA_REVISION
    expected = {
        "asserted_information": {"explicit", "legacy_unclassified"},
        "derived_information": {"derived"},
        "tentative_information": {"inferred"},
        "unknown_information": {"unknown"},
    }
    checks["epistemic_categorisation"] = all(
        all(item.get("epistemic_status") in allowed for item in packet.get(layer, []))
        for layer, allowed in expected.items()
    )
    checks["no_inferred_promotion"] = all(
        item.get("epistemic_status") != "inferred" for item in packet.get("asserted_information", [])
    )
    checks["no_unknown_promotion"] = all(
        item.get("epistemic_status") != "unknown"
        for layer in ("asserted_information", "derived_information", "tentative_information")
        for item in packet.get(layer, [])
    )
    checks["unknown_has_no_state_value"] = all(
        item.get("resolution_status") != "unknown_only"
        or item.get("current_value") is None
        for item in packet.get("state_dimensions", [])
    )
    checks["no_conflict_winner"] = all(
        item.get("resolution_status") != "conflicted"
        or (item.get("current_value") is None and item.get("selected_asserted_event_id") is None)
        for item in packet.get("state_dimensions", [])
    )
    all_items = {
        str(item["event_id"]): item
        for layer in expected
        for item in packet.get(layer, [])
    }
    checks["no_future_leakage"] = all(
        str(item.get("valid_from") or "") <= packet["valid_at"]
        and str(item.get("known_from") or "") <= packet["known_at"]
        for item in all_items.values()
    )
    checks["event_manifest"] = packet.get("effective_event_manifest_hash") == sha256_text(
        canonical_json(sorted(all_items))
    )
    checks["epistemic_weights_revision_bound"] = all(
        float(item.get("epistemic_weight", -1.0))
        == epistemic_weight(str(item.get("epistemic_status")))
        and float(item.get("continuity_influence", -1.0))
        == quantize8(
            float(item.get("raw_temporal_influence", 0.0))
            * float(item.get("epistemic_weight", 0.0))
        )
        for item in all_items.values()
    )
    relationship_layers = {
        "asserted_relationships": {"explicit"},
        "derived_relationships": {"derived"},
        "tentative_relationships": {"inferred"},
        "unknown_relationships": {"unknown"},
    }
    checks["relationship_epistemic_categorisation"] = all(
        all(item.get("epistemic_status") in allowed for item in packet.get("relationship_context", {}).get(layer, []))
        for layer, allowed in relationship_layers.items()
    )
    metrics = packet.get("v2_metrics", {})
    checks["metric_calculations"] = all(
        metrics.get(metric) == len(packet.get(layer, []))
        for metric, layer in {
            "asserted_item_count": "asserted_information",
            "derived_item_count": "derived_information",
            "tentative_item_count": "tentative_information",
            "unknown_item_count": "unknown_information",
            "conflicted_item_count": "conflicted_information",
            "active_item_count": "active_information_v2",
            "latent_item_count": "latent_information_v2",
            "dormant_item_count": "dormant_information_v2",
            "decayed_item_count": "decayed_information_v2",
            "reinforced_item_count": "reinforced_information_v2",
            "re_emerging_item_count": "re_emergence_information_v2",
        }.items()
    )
    checks["governance_opaque"] = all(
        str(value).startswith("govref_")
        for value in packet.get("governance_context", {}).get("opaque_tombstone_references", [])
    )
    checks["provenance_members"] = all(
        str(item.get("event_id")) in all_items
        for item in packet.get("provenance_context", {}).get("evidence_bundle_references", [])
    )
    provenance_event_ids = {
        str(item.get("event_id"))
        for item in packet.get("provenance_context", {}).get("evidence_bundle_references", [])
    }
    checks["complete_provenance_members_present"] = all(
        item.get("evidence_completeness") != "complete"
        or event_id in provenance_event_ids
        for event_id, item in all_items.items()
    )
    checks["entity_identity_not_collapsed"] = len(
        [item.get("canonical_entity_id") for item in packet.get("entity_context", [])]
    ) == len(
        set(item.get("canonical_entity_id") for item in packet.get("entity_context", []))
    )
    checks["legacy_score_formula_unchanged"] = bool(
        packet.get("legacy_coherence_breakdown", {}).get("formula_unchanged")
    ) and bool(
        packet.get("legacy_recoverability_breakdown", {}).get("formula_unchanged")
    )
    failures = sorted(key for key, passed in checks.items() if not passed)
    return ContinuityPacketV2IntegrityResult(
        packet_id=str(packet.get("packet_id", "")),
        verified=not failures,
        checks=checks,
        failures=failures,
        details={"integrity_revision": CONTINUITY_V2_INTEGRITY_REVISION},
    )


__all__ = [
    "packet_hash_for",
    "packet_id_for",
    "packet_identity_material",
    "packet_manifest_hash_for",
    "verify_packet_v2_integrity",
]
