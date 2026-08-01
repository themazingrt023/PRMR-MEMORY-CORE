"""Validation for exact structural memory-consolidation policy."""

from __future__ import annotations

from .memory_consolidation_models import (
    MemoryConsolidationError,
    MemoryConsolidationMode,
    MemoryConsolidationPolicy,
)


def policy_from_id(policy_id: str) -> MemoryConsolidationPolicy:
    if policy_id == MemoryConsolidationMode.DISABLED.value:
        return MemoryConsolidationPolicy(
            policy_id=policy_id,
            consolidation_mode=MemoryConsolidationMode.DISABLED.value,
            permit_incremental_update=False,
            permit_query_acceleration=False,
            permit_continuity_acceleration=False,
            persist_checkpoints=False,
        )
    if policy_id != MemoryConsolidationMode.EXACT_STRUCTURAL_V1.value:
        raise MemoryConsolidationError(
            "MEMORY_CONSOLIDATION_POLICY_INVALID",
            "Memory consolidation policy is not supported.",
        )
    return MemoryConsolidationPolicy()


def validate_policy(policy: MemoryConsolidationPolicy) -> MemoryConsolidationPolicy:
    if policy.consolidation_mode not in {
        MemoryConsolidationMode.DISABLED.value,
        MemoryConsolidationMode.EXACT_STRUCTURAL_V1.value,
    }:
        raise MemoryConsolidationError(
            "MEMORY_CONSOLIDATION_POLICY_INVALID",
            "Memory consolidation mode is not supported.",
        )
    limits = {
        "minimum_events_per_signal_group": policy.minimum_events_per_signal_group,
        "minimum_events_per_state_chain": policy.minimum_events_per_state_chain,
        "minimum_window_event_count": policy.minimum_window_event_count,
        "checkpoint_interval_event_count": policy.checkpoint_interval_event_count,
        "maximum_events_per_consolidation": policy.maximum_events_per_consolidation,
        "maximum_members_per_consolidated_memory": (
            policy.maximum_members_per_consolidated_memory
        ),
        "maximum_open_conflicts_per_checkpoint": (
            policy.maximum_open_conflicts_per_checkpoint
        ),
    }
    if any(value <= 0 for value in limits.values()):
        raise MemoryConsolidationError(
            "MEMORY_CONSOLIDATION_POLICY_INVALID",
            "Memory consolidation limits must be positive.",
            details={"invalid_limits": sorted(name for name, value in limits.items() if value <= 0)},
        )
    if (
        policy.maximum_members_per_consolidated_memory
        < policy.minimum_events_per_signal_group
        or policy.checkpoint_interval_event_count
        > policy.maximum_events_per_consolidation
    ):
        raise MemoryConsolidationError(
            "MEMORY_CONSOLIDATION_POLICY_INVALID",
            "Memory consolidation limits are internally inconsistent.",
        )
    if not (
        policy.preserve_all_event_membership
        and policy.preserve_epistemic_distribution
        and policy.preserve_conflicts
    ):
        raise MemoryConsolidationError(
            "MEMORY_CONSOLIDATION_POLICY_INVALID",
            "Exact structural consolidation requires membership, epistemic, and conflict preservation.",
        )
    return policy


__all__ = ["policy_from_id", "validate_policy"]
