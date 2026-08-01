"""Deterministic multi-dimensional state resolution for V2 packets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .continuity_v2_epistemic import quantize8
from .continuity_v2_models import (
    CONTINUITY_V2_STATE_REVISION,
    ContinuityCurrentStateV2,
    ContinuityStateDimension,
)
from .source_integrity import canonical_json, sha256_text


STATE_BEARING_ROLES = {
    "state_assertion",
    "state_transition",
    "milestone",
    "decision",
    "goal",
    "blocker",
    "observation",
    "statement",
    "unknown",
}


def _selected_value(item: dict[str, Any] | None) -> str | None:
    if not item:
        return None
    return str(item.get("state_value") or item.get("signal") or "")


def resolve_state_dimensions(
    layers: dict[str, list[dict[str, Any]]],
    *,
    signal_identity_mode: str,
) -> list[ContinuityStateDimension]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unique: dict[str, dict[str, Any]] = {}
    for name in (
        "asserted_information",
        "derived_information",
        "tentative_information",
        "unknown_information",
    ):
        for item in layers[name]:
            if item.get("state_role") not in STATE_BEARING_ROLES:
                continue
            unique[str(item["event_id"])] = item
    for item in unique.values():
        grouped[str(item["state_dimension"])].append(item)

    dimensions: list[ContinuityStateDimension] = []
    for key, items in sorted(grouped.items()):
        items.sort(key=lambda item: (str(item.get("valid_from", "")), str(item.get("known_from", "")), str(item["event_id"])))
        asserted = [item for item in items if item["packet_epistemic_class"] == "asserted"]
        derived = [item for item in items if item["packet_epistemic_class"] == "derived_assertion"]
        tentative = [item for item in items if item["packet_epistemic_class"] == "tentative"]
        unknown = [item for item in items if item["packet_epistemic_class"] == "unknown"]
        conflicts = sorted({cid for item in items for cid in item.get("conflict_ids", [])})
        selected_asserted = max([*asserted, *derived], key=lambda item: (str(item.get("valid_from", "")), str(item["event_id"])), default=None)
        selected_tentative = max(tentative, key=lambda item: (str(item.get("valid_from", "")), str(item["event_id"])), default=None)
        selected_unknown = max(unknown, key=lambda item: (str(item.get("valid_from", "")), str(item["event_id"])), default=None)
        if conflicts:
            resolution_status = "conflicted"
            selected_asserted = None
        elif selected_asserted:
            resolution_status = "derived" if selected_asserted["packet_epistemic_class"] == "derived_assertion" else "asserted"
        elif selected_tentative:
            resolution_status = "tentative_only"
        elif selected_unknown:
            resolution_status = "unknown_only"
        else:
            resolution_status = "no_data"
        selected = selected_asserted or selected_tentative or selected_unknown or items[-1]
        material = {
            "key": key,
            "mode": signal_identity_mode,
            "events": [item["event_id"] for item in items],
            "asserted": [item["event_id"] for item in asserted],
            "derived": [item["event_id"] for item in derived],
            "tentative": [item["event_id"] for item in tentative],
            "unknown": [item["event_id"] for item in unknown],
            "conflicts": conflicts,
            "resolution": resolution_status,
            "revision": CONTINUITY_V2_STATE_REVISION,
        }
        completeness = "complete"
        statuses = {str(item.get("evidence_completeness", "unavailable")) for item in items}
        if "governance_erased" in statuses:
            completeness = "governance_erased"
        elif "legacy_without_source" in statuses:
            completeness = "legacy_without_source"
        elif statuses != {"complete"}:
            completeness = "partial"
        dimensions.append(
            ContinuityStateDimension(
                state_dimension_key=key,
                signal_identity_mode=signal_identity_mode,
                canonical_signal_key=next((str(item["canonical_signal_key"]) for item in items if item.get("canonical_signal_key")), None),
                original_signal_keys=sorted({str(item["original_signal_key"]) for item in items}),
                effective_event_ids=[str(item["event_id"]) for item in items],
                asserted_event_ids=[str(item["event_id"]) for item in asserted],
                derived_event_ids=[str(item["event_id"]) for item in derived],
                inferred_event_ids=[str(item["event_id"]) for item in tentative],
                unknown_event_ids=[str(item["event_id"]) for item in unknown],
                conflict_ids=conflicts,
                resolution_status=resolution_status,
                selected_asserted_event_id=str(selected_asserted["event_id"]) if selected_asserted else None,
                selected_tentative_event_id=str(selected_tentative["event_id"]) if selected_tentative else None,
                selected_unknown_event_id=str(selected_unknown["event_id"]) if selected_unknown else None,
                current_value=None if conflicts else _selected_value(selected_asserted),
                tentative_value=_selected_value(selected_tentative),
                unknown_statement=_selected_value(selected_unknown),
                valid_from=str(selected.get("valid_from") or "") or None,
                known_from=str(selected.get("known_from") or "") or None,
                temporal_phase=selected.get("temporal_phase"),
                temporal_influence=quantize8(float(selected.get("raw_temporal_influence", 0.0))),
                epistemic_status=str(selected.get("epistemic_status", "unknown")),
                evidence_completeness=completeness,
                provenance_references=list(selected.get("provenance_references", [])),
                state_dimension_hash=sha256_text(canonical_json(material)),
            )
        )
    return dimensions


def resolve_primary_current_state(
    dimensions: list[ContinuityStateDimension],
    item_by_event: dict[str, dict[str, Any]],
) -> ContinuityCurrentStateV2:
    if not dimensions:
        return ContinuityCurrentStateV2(
            "no_data", None, None, None, None, None, None, None, [], None, None,
            None, None, None, 0.0, "unknown", "unavailable", [],
            "no effective state-bearing events",
        )
    priority = {
        "asserted": 4,
        "derived": 4,
        "conflicted": 4,
        "tentative_only": 3,
        "unknown_only": 2,
        "no_data": 1,
    }
    selected = max(
        dimensions,
        key=lambda item: (priority[item.resolution_status], item.valid_from or "", item.known_from or "", item.state_dimension_key),
    )
    selected_event_id = (
        selected.selected_asserted_event_id
        or selected.selected_tentative_event_id
        or selected.selected_unknown_event_id
    )
    item = item_by_event.get(str(selected_event_id), {})
    status = {
        "asserted": "supported",
        "derived": "derived",
        "tentative_only": "tentative",
        "unknown_only": "unknown",
        "conflicted": "conflicted",
        "no_data": "no_data",
    }[selected.resolution_status]
    return ContinuityCurrentStateV2(
        primary_state_status=status,
        primary_dimension_key=selected.state_dimension_key,
        primary_asserted_value=selected.current_value,
        primary_asserted_event_id=selected.selected_asserted_event_id,
        primary_tentative_value=selected.tentative_value,
        primary_tentative_event_id=selected.selected_tentative_event_id,
        primary_unknown_statement=selected.unknown_statement,
        primary_unknown_event_id=selected.selected_unknown_event_id,
        primary_conflict_ids=selected.conflict_ids,
        occurred_at=item.get("occurred_at"),
        valid_from=selected.valid_from,
        known_from=selected.known_from,
        temporal_phase=selected.temporal_phase,
        temporal_horizon=item.get("temporal_horizon"),
        temporal_influence=selected.temporal_influence,
        epistemic_status=selected.epistemic_status,
        evidence_completeness=selected.evidence_completeness,
        provenance_references=selected.provenance_references,
        selection_rule="epistemic class priority then deterministic bitemporal event order; open conflict selects no winner",
    )


__all__ = ["STATE_BEARING_ROLES", "resolve_primary_current_state", "resolve_state_dimensions"]
