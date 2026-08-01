"""Deterministic checkpoint identity, hashing, comparison, and exact deltas."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .memory_consolidation_models import (
    MEMORY_CHECKPOINT_DELTA_REVISION,
    MEMORY_CHECKPOINT_REVISION,
    MemoryCheckpoint,
    MemoryCheckpointDelta,
)
from .source_integrity import canonical_json, sha256_text


def checkpoint_identity_material(checkpoint: MemoryCheckpoint) -> dict[str, Any]:
    payload = checkpoint.to_dict()
    for key in (
        "memory_checkpoint_id",
        "consolidation_run_id",
        "checkpoint_hash_sha256",
        "checkpoint_status",
        "previous_checkpoint_id",
        "delta_from_checkpoint_id",
        "created_at",
    ):
        payload.pop(key, None)
    return payload


def checkpoint_hash(checkpoint: MemoryCheckpoint) -> str:
    return sha256_text(canonical_json(checkpoint_identity_material(checkpoint)))


def finalize_checkpoint(checkpoint: MemoryCheckpoint) -> MemoryCheckpoint:
    digest = checkpoint_hash(checkpoint)
    identity = sha256_text(
        canonical_json(
            {
                "checkpoint_hash": digest,
                "checkpoint_revision": MEMORY_CHECKPOINT_REVISION,
                "scope": [
                    checkpoint.client_id,
                    checkpoint.vault_id,
                    checkpoint.namespace,
                ],
            }
        )
    )
    return replace(
        checkpoint,
        memory_checkpoint_id=f"mchk_{identity[:24]}",
        checkpoint_hash_sha256=digest,
    )


def compare_checkpoints(
    base: MemoryCheckpoint, target: MemoryCheckpoint
) -> dict[str, Any]:
    old_ids = list(base.deterministic_state_payload.get("effective_event_ids", []))
    new_ids = list(target.deterministic_state_payload.get("effective_event_ids", []))
    old_set, new_set = set(old_ids), set(new_ids)
    old_phases = _phase_by_signal(base)
    new_phases = _phase_by_signal(target)
    phase_changes = [
        {"signal_key": key, "from": old_phases.get(key), "to": new_phases.get(key)}
        for key in sorted(set(old_phases) | set(new_phases))
        if old_phases.get(key) != new_phases.get(key)
    ]
    return {
        "events_added": [item for item in new_ids if item not in old_set],
        "events_removed_from_effective_view": [
            item for item in old_ids if item not in new_set
        ],
        "conflicts_opened": sorted(
            set(target.open_conflict_ids) - set(base.open_conflict_ids)
        ),
        "conflicts_resolved": sorted(
            set(target.resolved_conflict_ids) - set(base.resolved_conflict_ids)
        ),
        "signal_phase_changes": phase_changes,
        "current_state_change": {
            "from": base.current_state_event_id,
            "to": target.current_state_event_id,
            "changed": base.current_state_event_id != target.current_state_event_id,
        },
    }


def build_checkpoint_delta(
    base: MemoryCheckpoint,
    target: MemoryCheckpoint,
    *,
    created_at: str,
) -> MemoryCheckpointDelta:
    comparison = compare_checkpoints(base, target)
    projections = target.deterministic_state_payload.get("projection_index", {})
    removed = comparison["events_removed_from_effective_view"]
    states = {
        "superseded": [],
        "retracted": [],
        "invalidated": [],
    }
    for event_id in removed:
        state = str(projections.get(event_id, {}).get("effective_state", ""))
        if state in states:
            states[state].append(event_id)
    material = {
        "base_checkpoint_id": base.memory_checkpoint_id,
        "target_checkpoint_id": target.memory_checkpoint_id,
        **comparison,
        "events_superseded": states["superseded"],
        "events_retracted": states["retracted"],
        "events_invalidated": states["invalidated"],
        "importance_annotations_added": [],
        "entity_changes": _index_changes(base.entity_index, target.entity_index),
        "relationship_changes": _index_changes(
            base.relationship_index, target.relationship_index
        ),
        "revision": MEMORY_CHECKPOINT_DELTA_REVISION,
    }
    digest = sha256_text(canonical_json(material))
    return MemoryCheckpointDelta(
        checkpoint_delta_id=f"mcdelta_{digest[:24]}",
        base_checkpoint_id=base.memory_checkpoint_id,
        target_checkpoint_id=target.memory_checkpoint_id,
        valid_from=target.valid_at,
        known_from=target.known_at,
        events_added=comparison["events_added"],
        events_removed_from_effective_view=removed,
        events_superseded=states["superseded"],
        events_retracted=states["retracted"],
        events_invalidated=states["invalidated"],
        conflicts_opened=comparison["conflicts_opened"],
        conflicts_resolved=comparison["conflicts_resolved"],
        importance_annotations_added=[],
        entity_changes=material["entity_changes"],
        relationship_changes=material["relationship_changes"],
        signal_phase_changes=comparison["signal_phase_changes"],
        current_state_change=comparison["current_state_change"],
        delta_manifest_hash_sha256=digest,
        memory_checkpoint_delta_revision=MEMORY_CHECKPOINT_DELTA_REVISION,
        created_at=created_at,
    )


def apply_checkpoint_delta(
    base: MemoryCheckpoint,
    target: MemoryCheckpoint,
    delta: MemoryCheckpointDelta,
) -> MemoryCheckpoint:
    """Return target only after proving the delta binds the exact base and target."""

    expected = build_checkpoint_delta(base, target, created_at=delta.created_at)
    if (
        expected.checkpoint_delta_id != delta.checkpoint_delta_id
        or expected.delta_manifest_hash_sha256
        != delta.delta_manifest_hash_sha256
    ):
        raise ValueError("MEMORY_CHECKPOINT_DELTA_INVALID")
    return target


def _phase_by_signal(checkpoint: MemoryCheckpoint) -> dict[str, str]:
    phases: dict[str, str] = {}
    for phase, items in (
        ("active", checkpoint.active_signal_index),
        ("latent", checkpoint.latent_signal_index),
        ("dormant", checkpoint.dormant_signal_index),
        ("decayed", checkpoint.decayed_signal_index),
    ):
        for item in items:
            phases[str(item.get("signal_key"))] = phase
    return phases


def _index_changes(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    return [
        key
        for key in sorted(set(first) | set(second))
        if first.get(key) != second.get(key)
    ]


__all__ = [
    "apply_checkpoint_delta",
    "build_checkpoint_delta",
    "checkpoint_hash",
    "checkpoint_identity_material",
    "compare_checkpoints",
    "finalize_checkpoint",
]
