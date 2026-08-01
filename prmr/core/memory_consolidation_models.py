"""Typed contracts for exact, provenance-preserving memory consolidation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


MEMORY_CONSOLIDATION_SCHEMA_REVISION = "memory_consolidation_v1"
MEMORY_CONSOLIDATION_POLICY_REVISION = "memory_consolidation_policy_v1"
MEMORY_CONSOLIDATION_PLANNER_REVISION = "memory_consolidation_planner_v1"
MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION = "memory_consolidation_membership_v1"
MEMORY_CONSOLIDATION_MANIFEST_REVISION = "memory_consolidation_manifest_v1"
MEMORY_CHECKPOINT_REVISION = "memory_checkpoint_v1"
MEMORY_CHECKPOINT_DELTA_REVISION = "memory_checkpoint_delta_v1"
MEMORY_CONSOLIDATION_INVALIDATION_REVISION = (
    "memory_consolidation_invalidation_v1"
)
MEMORY_CONSOLIDATION_QUERY_ADAPTER_REVISION = (
    "memory_consolidation_query_adapter_v1"
)
MEMORY_CONSOLIDATION_CONTINUITY_ADAPTER_REVISION = (
    "memory_consolidation_continuity_adapter_v1"
)
MEMORY_CONSOLIDATION_INTEGRITY_REVISION = "memory_consolidation_integrity_v1"
MEMORY_CONSOLIDATION_COMPARISON_REVISION = "memory_consolidation_comparison_v1"
MEMORY_CONSOLIDATION_WINDOW_REVISION = "event_count_window_v1"


class MemoryConsolidationMode(str, Enum):
    DISABLED = "disabled"
    EXACT_STRUCTURAL_V1 = "exact_structural_v1"


class MemoryConsolidationType(str, Enum):
    EXACT_SIGNAL_WINDOW = "exact_signal_window"
    EVENT_STATE_CHAIN = "event_state_chain"
    TEMPORAL_PHASE_WINDOW = "temporal_phase_window"
    ENTITY_EVENT_CHECKPOINT = "entity_event_checkpoint"
    RELATIONSHIP_STATE_CHECKPOINT = "relationship_state_checkpoint"
    CONFLICT_PRESERVING_CHECKPOINT = "conflict_preserving_checkpoint"
    QUERY_RESOLUTION_CHECKPOINT = "query_resolution_checkpoint"
    CONTINUITY_INPUT_CHECKPOINT = "continuity_input_checkpoint"


class MemoryConsolidationStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    STALE = "stale"
    INVALIDATED = "invalidated"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class MemoryCheckpointStatus(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    STALE = "stale"
    INVALIDATED = "invalidated"
    SUPERSEDED = "superseded"


class MemoryConsolidationError(RuntimeError):
    """Stable, non-sensitive consolidation failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass(frozen=True)
class MemoryConsolidationPolicy:
    policy_id: str = "exact_structural_v1"
    consolidation_mode: str = MemoryConsolidationMode.EXACT_STRUCTURAL_V1.value
    minimum_events_per_signal_group: int = 3
    minimum_events_per_state_chain: int = 3
    minimum_window_event_count: int = 100
    checkpoint_interval_event_count: int = 500
    maximum_events_per_consolidation: int = 10_000
    maximum_members_per_consolidated_memory: int = 10_000
    maximum_open_conflicts_per_checkpoint: int = 1_000
    preserve_all_event_membership: bool = True
    preserve_source_references: bool = True
    preserve_epistemic_distribution: bool = True
    preserve_conflicts: bool = True
    permit_incremental_update: bool = True
    require_integrity: bool = True
    permit_query_acceleration: bool = True
    permit_continuity_acceleration: bool = True
    fallback_to_authoritative_ledger: bool = True
    verify_accelerated_result_equivalence: bool = True
    persist_checkpoints: bool = True
    policy_revision: str = MEMORY_CONSOLIDATION_POLICY_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConsolidationPlan:
    consolidation_plan_id: str
    consolidation_run_identity_hash: str
    consolidation_types: list[str]
    subject_scope: dict[str, str | None]
    temporal_boundary: dict[str, str]
    deterministic_windows: list[dict[str, Any]]
    eligible_event_ids: list[str]
    excluded_event_counts: dict[str, int]
    eligible_signal_keys: list[str]
    eligible_entity_ids: list[str]
    eligible_relationship_ids: list[str]
    open_conflict_ids: list[str]
    planned_groups: list[dict[str, Any]]
    full_rebuild_required: bool
    incremental_from_checkpoint_id: str | None
    invalidation_dependencies: dict[str, str]
    planner_revision: str
    plan_hash_sha256: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConsolidationRun:
    consolidation_run_id: str
    consolidation_mode: str
    consolidation_policy_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    relationship_id: str | None
    session_reference: str | None
    valid_at: str
    known_at: str
    window_start: str | None
    window_end: str | None
    source_event_count: int
    effective_event_count: int
    signal_count: int
    entity_count: int
    relationship_count: int
    conflict_count: int
    source_event_manifest_hash: str
    effective_event_manifest_hash: str
    ledger_evolution_manifest_hash: str
    importance_annotation_manifest_hash: str
    entity_manifest_hash: str
    relationship_manifest_hash: str
    query_manifest_hash: str | None
    consolidation_plan_id: str
    consolidation_manifest_hash: str
    checkpoint_id: str | None
    status: str
    created_item_count: int
    reused_item_count: int
    invalidated_item_count: int
    started_at: str
    completed_at: str | None
    duration_ms: float
    error_code: str | None
    memory_consolidation_schema_revision: str
    memory_consolidation_policy_revision: str
    memory_consolidation_planner_revision: str
    memory_consolidation_membership_revision: str
    memory_consolidation_manifest_revision: str
    memory_checkpoint_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConsolidatedMemory:
    consolidated_memory_id: str
    consolidation_run_id: str
    consolidation_type: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    relationship_id: str | None
    session_reference: str | None
    signal_key: str | None
    consolidation_key: str
    window_start: str | None
    window_end: str | None
    valid_at: str
    known_at: str
    primary_memory_phase: str | None
    derived_epistemic_status: str
    contributor_epistemic_counts: dict[str, int]
    contributor_event_count: int
    contributor_source_count: int
    first_event_id: str | None
    latest_event_id: str | None
    current_effective_event_id: str | None
    occurrence_count: int
    first_occurrence_at: str | None
    latest_occurrence_at: str | None
    temporal_span_seconds: float
    reinforced: bool
    re_emerging: bool
    open_conflict_ids: list[str]
    resolved_conflict_ids: list[str]
    relationship_count: int
    entity_count: int
    influence_summary: dict[str, Any]
    recurrence_summary: dict[str, Any]
    temporal_summary: dict[str, Any]
    consolidation_payload: dict[str, Any]
    contributor_manifest_hash_sha256: str
    evidence_manifest_hash_sha256: str
    consolidated_memory_hash_sha256: str
    status: str
    previous_consolidated_memory_id: str | None
    memory_consolidation_schema_revision: str
    memory_consolidation_policy_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConsolidatedMemoryMember:
    consolidated_memory_member_id: str
    consolidated_memory_id: str
    member_type: str
    event_id: str | None
    source_id: str | None
    candidate_id: str | None
    admission_id: str | None
    evolution_id: str | None
    conflict_id: str | None
    entity_id: str | None
    relationship_id: str | None
    sequence_index: int
    member_role: str
    member_hash_sha256: str
    effective_state: str
    epistemic_status: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    membership_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryCheckpoint:
    memory_checkpoint_id: str
    consolidation_run_id: str
    checkpoint_type: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    relationship_id: str | None
    session_reference: str | None
    valid_at: str
    known_at: str
    window_start: str | None
    window_end: str | None
    authoritative_event_count: int
    effective_event_count: int
    authoritative_event_manifest_hash: str
    effective_event_manifest_hash: str
    evolution_manifest_hash: str
    importance_manifest_hash: str
    entity_manifest_hash: str
    relationship_manifest_hash: str
    conflict_manifest_hash: str
    signal_dynamics_manifest_hash: str
    consolidated_memory_manifest_hash: str
    active_signal_index: list[dict[str, Any]]
    latent_signal_index: list[dict[str, Any]]
    dormant_signal_index: list[dict[str, Any]]
    decayed_signal_index: list[dict[str, Any]]
    current_state_event_id: str | None
    latest_effective_event_id: str | None
    open_conflict_ids: list[str]
    resolved_conflict_ids: list[str]
    entity_index: dict[str, Any]
    relationship_index: dict[str, Any]
    deterministic_state_payload: dict[str, Any]
    checkpoint_hash_sha256: str
    checkpoint_status: str
    previous_checkpoint_id: str | None
    delta_from_checkpoint_id: str | None
    memory_checkpoint_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryCheckpointDelta:
    checkpoint_delta_id: str
    base_checkpoint_id: str
    target_checkpoint_id: str
    valid_from: str
    known_from: str
    events_added: list[str]
    events_removed_from_effective_view: list[str]
    events_superseded: list[str]
    events_retracted: list[str]
    events_invalidated: list[str]
    conflicts_opened: list[str]
    conflicts_resolved: list[str]
    importance_annotations_added: list[str]
    entity_changes: list[str]
    relationship_changes: list[str]
    signal_phase_changes: list[dict[str, Any]]
    current_state_change: dict[str, Any]
    delta_manifest_hash_sha256: str
    memory_checkpoint_delta_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConsolidationInvalidation:
    invalidation_id: str
    consolidation_run_id: str
    consolidated_memory_id: str | None
    checkpoint_id: str | None
    invalidation_type: str
    invalidation_reason: str
    triggering_object_type: str
    triggering_object_id: str
    previous_manifest_hash: str
    current_manifest_hash: str
    system_effective_at: str
    actor_type: str
    actor_reference: str
    invalidation_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConsolidationEquivalenceProof:
    equivalence_proof_id: str
    consolidation_run_id: str
    checkpoint_id: str
    proof_type: str
    query_type: str | None
    canonical_result_id: str | None
    accelerated_result_id: str | None
    canonical_result_hash: str | None
    accelerated_result_hash: str | None
    canonical_packet_id: str | None
    accelerated_packet_id: str | None
    canonical_packet_hash: str | None
    accelerated_packet_hash: str | None
    equivalent: bool
    mismatch_fields: list[str]
    canonical_duration_ms: float | None
    accelerated_duration_ms: float | None
    speedup_ratio: float | None
    proof_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConsolidationIntegrityResult:
    consolidation_run_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    details: dict[str, Any] = field(default_factory=dict)
    memory_consolidation_integrity_revision: str = (
        MEMORY_CONSOLIDATION_INTEGRITY_REVISION
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryAccelerationMetadata:
    execution_path: str
    checkpoint_id: str | None
    consolidation_run_id: str | None
    acceleration_supported: bool
    acceleration_used: bool
    fallback_used: bool
    fallback_reason: str | None
    canonical_verification_performed: bool
    canonical_result_hash: str | None
    accelerated_result_hash: str | None
    equivalence_verified: bool
    checkpoint_age: int | None
    delta_event_count: int
    acceleration_duration_ms: float
    canonical_comparison_duration_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryAcceleratedQueryResult:
    result: Any
    metadata: MemoryAccelerationMetadata


@dataclass(frozen=True)
class MemoryAcceleratedContinuityResult:
    packet: dict[str, Any]
    metadata: MemoryAccelerationMetadata


__all__ = [name for name in globals() if name.startswith("MEMORY_") or name.startswith("Memory") or name.startswith("Consolidated")]
