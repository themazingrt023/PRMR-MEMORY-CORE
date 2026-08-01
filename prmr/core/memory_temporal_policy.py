"""Versioned deterministic policy and numeric helpers for temporal memory."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
import math
from typing import Any

from .memory_temporal_models import (
    MemoryDynamicsError,
    MemoryHorizon,
    MemoryPhase,
    TemporalHorizonPolicy,
    TemporalMemoryPolicy,
)


QUANTUM_8 = Decimal("0.00000001")


def quantize8(value: float | int | Decimal) -> float:
    return float(Decimal(str(value)).quantize(QUANTUM_8, rounding=ROUND_HALF_EVEN))


def clamp01(value: float) -> float:
    return quantize8(max(0.0, min(1.0, value)))


def validate_policy(policy: TemporalMemoryPolicy) -> TemporalMemoryPolicy:
    horizon = policy.horizon_policy
    boundaries = [
        horizon.immediate_max_seconds,
        horizon.short_max_seconds,
        horizon.medium_max_seconds,
        horizon.long_max_seconds,
    ]
    if any(not isinstance(value, int) or value <= 0 for value in boundaries):
        raise MemoryDynamicsError(
            "MEMORY_HORIZON_POLICY_INVALID",
            "Horizon boundaries must be positive integer seconds.",
        )
    if boundaries != sorted(set(boundaries)):
        raise MemoryDynamicsError(
            "MEMORY_HORIZON_POLICY_INVALID",
            "Horizon boundaries must be strictly increasing.",
        )
    if policy.half_life_seconds <= 0:
        raise MemoryDynamicsError(
            "MEMORY_TEMPORAL_POLICY_INVALID", "Half-life must be positive."
        )
    if not (
        1.0 >= policy.active_threshold
        > policy.latent_threshold
        > policy.dormant_threshold
        > 0.0
    ):
        raise MemoryDynamicsError(
            "MEMORY_TEMPORAL_POLICY_INVALID",
            "Memory phase thresholds must be strictly decreasing.",
        )
    if (
        policy.recurrence_weight < 0
        or policy.maximum_recurrence_boost < 0
        or policy.cross_horizon_weight < 0
        or policy.maximum_cross_horizon_boost < 0
        or policy.minimum_reemergence_gap_seconds <= 0
        or policy.minimum_reemergence_gap_events <= 0
        or not 0 < policy.numeric_importance_min <= policy.numeric_importance_max
    ):
        raise MemoryDynamicsError(
            "MEMORY_TEMPORAL_POLICY_INVALID",
            "Temporal policy weights or limits are invalid.",
        )
    weights = policy.importance_weights or {
        "low": 0.75,
        "normal": 1.00,
        "high": 1.25,
        "critical": 1.50,
    }
    if set(weights) != {"low", "normal", "high", "critical"} or any(
        not policy.numeric_importance_min <= float(value) <= policy.numeric_importance_max
        for value in weights.values()
    ):
        raise MemoryDynamicsError(
            "MEMORY_IMPORTANCE_INVALID", "Importance configuration is invalid."
        )
    return policy


def classify_horizon(age_seconds: float, policy: TemporalHorizonPolicy) -> str:
    if age_seconds < 0:
        raise MemoryDynamicsError(
            "MEMORY_EVENT_TIME_INVALID",
            "A future event reached temporal horizon classification.",
        )
    if age_seconds <= policy.immediate_max_seconds:
        return MemoryHorizon.IMMEDIATE.value
    if age_seconds <= policy.short_max_seconds:
        return MemoryHorizon.SHORT.value
    if age_seconds <= policy.medium_max_seconds:
        return MemoryHorizon.MEDIUM.value
    if age_seconds <= policy.long_max_seconds:
        return MemoryHorizon.LONG.value
    return MemoryHorizon.HISTORICAL.value


def base_time_influence(age_seconds: float, half_life_seconds: int) -> float:
    if age_seconds < 0:
        raise MemoryDynamicsError(
            "MEMORY_EVENT_TIME_INVALID",
            "A future event cannot receive temporal influence.",
        )
    return clamp01(math.pow(2.0, -(age_seconds / float(half_life_seconds))))


def recurrence_boost(
    occurrence_count: int, policy: TemporalMemoryPolicy
) -> float:
    additional = max(0, occurrence_count - 1)
    return quantize8(
        min(
            policy.maximum_recurrence_boost,
            policy.recurrence_weight * math.log1p(additional),
        )
    )


def cross_horizon_boost(
    distinct_horizon_count: int, policy: TemporalMemoryPolicy
) -> float:
    additional = max(0, distinct_horizon_count - 1)
    return quantize8(
        min(
            policy.maximum_cross_horizon_boost,
            policy.cross_horizon_weight * additional,
        )
    )


def classify_phase(final_influence: float, policy: TemporalMemoryPolicy) -> str:
    if final_influence >= policy.active_threshold:
        return MemoryPhase.ACTIVE.value
    if final_influence >= policy.latent_threshold:
        return MemoryPhase.LATENT.value
    if final_influence >= policy.dormant_threshold:
        return MemoryPhase.DORMANT.value
    return MemoryPhase.DECAYED.value


def policy_from_configuration(configuration: dict[str, Any]) -> TemporalMemoryPolicy:
    values = dict(configuration)
    values["horizon_policy"] = TemporalHorizonPolicy(**values["horizon_policy"])
    return validate_policy(TemporalMemoryPolicy(**values))


__all__ = [
    "base_time_influence",
    "clamp01",
    "classify_horizon",
    "classify_phase",
    "cross_horizon_boost",
    "policy_from_configuration",
    "quantize8",
    "recurrence_boost",
    "validate_policy",
]
