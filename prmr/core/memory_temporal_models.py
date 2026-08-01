"""Typed models for deterministic Temporal Memory Dynamics V1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


MEMORY_TEMPORAL_SCHEMA_REVISION = "memory_temporal_v1"
MEMORY_TEMPORAL_POLICY_REVISION = "temporal_memory_policy_v1"
MEMORY_HORIZON_REVISION = "memory_horizons_v1"
MEMORY_INFLUENCE_REVISION = "memory_influence_v1"
MEMORY_RECURRENCE_REVISION = "memory_recurrence_v1"
MEMORY_REEMERGENCE_REVISION = "memory_reemergence_v1"
MEMORY_IMPORTANCE_REVISION = "memory_importance_v1"
MEMORY_DYNAMICS_SNAPSHOT_REVISION = "memory_dynamics_snapshot_v1"
CONTINUITY_TEMPORAL_ADAPTER_REVISION = "continuity_temporal_adapter_v1"
SIGNAL_IDENTITY_REVISION = "signal_identity_v1"
MEMORY_DYNAMICS_COMPARISON_REVISION = "memory_dynamics_comparison_v1"


class MemoryDynamicsMode(str, Enum):
    LEGACY_RECENT5_V1 = "legacy_recent5_v1"
    TEMPORAL_MEMORY_V1 = "temporal_memory_v1"


class MemoryHorizon(str, Enum):
    IMMEDIATE = "immediate"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    HISTORICAL = "historical"


class MemoryPhase(str, Enum):
    ACTIVE = "active"
    LATENT = "latent"
    DORMANT = "dormant"
    DECAYED = "decayed"


class MemoryImportanceLevel(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TemporalHorizonPolicy:
    immediate_max_seconds: int = 86_400
    short_max_seconds: int = 604_800
    medium_max_seconds: int = 2_592_000
    long_max_seconds: int = 15_552_000
    revision: str = MEMORY_HORIZON_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalMemoryPolicy:
    policy_id: str = MemoryDynamicsMode.TEMPORAL_MEMORY_V1.value
    horizon_policy: TemporalHorizonPolicy = TemporalHorizonPolicy()
    half_life_seconds: int = 2_592_000
    recurrence_weight: float = 0.10
    maximum_recurrence_boost: float = 0.25
    cross_horizon_weight: float = 0.05
    maximum_cross_horizon_boost: float = 0.15
    active_threshold: float = 0.65
    latent_threshold: float = 0.35
    dormant_threshold: float = 0.10
    minimum_reemergence_gap_seconds: int = 1_209_600
    minimum_reemergence_gap_events: int = 5
    importance_weights: dict[str, float] | None = None
    numeric_importance_min: float = 0.50
    numeric_importance_max: float = 2.00
    policy_revision: str = MEMORY_TEMPORAL_POLICY_REVISION

    def configuration(self) -> dict[str, Any]:
        weights = self.importance_weights or {
            "low": 0.75,
            "normal": 1.00,
            "high": 1.25,
            "critical": 1.50,
        }
        return {
            **asdict(self),
            "horizon_policy": self.horizon_policy.to_dict(),
            "importance_weights": dict(sorted(weights.items())),
        }


@dataclass(frozen=True)
class MemoryImportanceAnnotation:
    importance_annotation_id: str
    event_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    importance_level: str | None
    importance_weight: float
    annotation_actor_type: str
    annotation_actor_reference: str
    annotation_reason: str
    system_effective_at: str
    memory_importance_revision: str
    idempotency_digest: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemorySignalDynamics:
    signal_dynamics_id: str
    dynamics_snapshot_id: str
    signal_key: str
    signal_identity_source: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_reference: str | None
    session_reference: str | None
    first_occurrence_at: str
    latest_occurrence_at: str
    occurrence_count: int
    occurrence_event_ids: list[str]
    occurrences_by_horizon: dict[str, int]
    distinct_horizon_count: int
    latest_horizon: str
    age_seconds: float
    age_days: float
    event_time_basis: str
    base_time_influence: float
    importance_weight: float
    importance_selected_event_id: str | None
    importance_annotation_id: str | None
    importance_aggregation_method: str
    weighted_time_influence: float
    recurrence_boost: float
    cross_horizon_boost: float
    total_reinforcement_boost: float
    reinforcement_reason: str | None
    unclamped_influence: float
    final_influence: float
    memory_phase: str
    reinforced: bool
    re_emerging: bool
    re_emergence_count: int
    prior_occurrence_event_id: str | None
    latest_occurrence_event_id: str
    reemergence_gap_seconds: float | None
    reemergence_gap_event_count: int | None
    prior_memory_phase: str | None
    reemergence_detection_revision: str
    conflicted: bool
    superseded: bool
    retracted: bool
    invalidated: bool
    open_conflict_ids: list[str]
    epistemic_status_counts: dict[str, int]
    source_count: int
    source_ids: list[str]
    maximum_gap_seconds: float
    maximum_gap_event_count: int
    recurrence_span_seconds: float
    signal_identity_revision: str
    memory_temporal_policy_revision: str
    memory_influence_revision: str
    memory_recurrence_revision: str
    memory_reemergence_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryDynamicsSnapshot:
    dynamics_snapshot_id: str
    dynamics_snapshot_identity: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_reference: str | None
    session_reference: str | None
    valid_at: str
    known_at: str
    computed_at: str
    dynamics_mode: str
    temporal_policy_id: str
    temporal_policy_configuration: dict[str, Any]
    resolved_event_count: int
    resolved_event_manifest_hash: str
    importance_annotation_manifest_hash: str
    signal_count: int
    active_signal_count: int
    latent_signal_count: int
    dormant_signal_count: int
    decayed_signal_count: int
    reinforced_signal_count: int
    re_emerging_signal_count: int
    conflicted_signal_count: int
    signal_dynamics_manifest_hash: str
    temporal_packet_id: str | None
    temporal_packet_hash: str | None
    memory_temporal_schema_revision: str
    memory_temporal_policy_revision: str
    memory_horizon_revision: str
    memory_influence_revision: str
    memory_recurrence_revision: str
    memory_reemergence_revision: str
    memory_importance_revision: str
    memory_state_resolver_revision: str
    bitemporal_policy_revision: str
    duration_ms: float
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryDynamicsResult:
    snapshot: MemoryDynamicsSnapshot
    signals: list[MemorySignalDynamics]
    created: bool
    replayed: bool
    resolver_duration_ms: float
    recurrence_duration_ms: float
    reemergence_duration_ms: float
    persistence_duration_ms: float


@dataclass(frozen=True)
class MemoryDynamicsComparison:
    first_snapshot_id: str
    second_snapshot_id: str
    first_boundary: dict[str, str]
    second_boundary: dict[str, str]
    signals_added: list[str]
    signals_removed: list[str]
    phase_changes: list[dict[str, str]]
    influence_changes: list[dict[str, Any]]
    newly_reinforced: list[str]
    no_longer_reinforced: list[str]
    newly_re_emerging: list[str]
    newly_dormant: list[str]
    newly_decayed: list[str]
    reactivated_signals: list[str]
    conflict_state_changes: list[dict[str, Any]]
    comparison_hash: str
    comparison_revision: str = MEMORY_DYNAMICS_COMPARISON_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryDynamicsIntegrityResult:
    dynamics_snapshot_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    details: dict[str, Any]


class MemoryDynamicsError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


__all__ = [name for name in globals() if name.startswith("MEMORY_") or name.startswith("CONTINUITY_") or name.startswith("SIGNAL_") or name in {
    "MemoryDynamicsMode", "MemoryHorizon", "MemoryPhase", "MemoryImportanceLevel",
    "TemporalHorizonPolicy", "TemporalMemoryPolicy", "MemoryImportanceAnnotation",
    "MemorySignalDynamics", "MemoryDynamicsSnapshot", "MemoryDynamicsResult",
    "MemoryDynamicsComparison", "MemoryDynamicsIntegrityResult", "MemoryDynamicsError",
}]
