"""Typed models for deterministic Epistemic Continuity Packet V2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


CONTINUITY_V2_SCHEMA_REVISION = "epistemic_continuity_packet_v2"
CONTINUITY_V2_STATE_REVISION = "continuity_state_resolution_v2"
CONTINUITY_V2_EPISTEMIC_REVISION = "continuity_epistemic_projection_v1"
CONTINUITY_V2_TEMPORAL_REVISION = "continuity_temporal_projection_v1"
CONTINUITY_V2_ENTITY_REVISION = "continuity_entity_context_v1"
CONTINUITY_V2_RELATIONSHIP_REVISION = "continuity_relationship_context_v1"
CONTINUITY_V2_PROVENANCE_REVISION = "continuity_provenance_v2"
CONTINUITY_V2_GOVERNANCE_REVISION = "continuity_governance_context_v1"
CONTINUITY_V2_COMPARISON_REVISION = "continuity_comparison_v2"
CONTINUITY_V2_INTEGRITY_REVISION = "continuity_integrity_v2"
CONTINUITY_V2_ACCELERATION_REVISION = "continuity_acceleration_v2"


class ContinuityPacketStatus(str, Enum):
    SUPPORTED = "supported"
    DERIVED = "derived"
    TENTATIVE = "tentative"
    UNKNOWN = "unknown"
    CONFLICTED = "conflicted"
    NO_DATA = "no_data"
    PARTIALLY_RECOVERABLE = "partially_recoverable"
    GOVERNANCE_ERASURE_LIMITED = "governance_erasure_limited"


class ProvenanceCompletenessStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LEGACY_WITHOUT_SOURCE = "legacy_without_source"
    GOVERNANCE_ERASED = "governance_erased"
    INTEGRITY_FAILED = "integrity_failed"
    UNAVAILABLE = "unavailable"


class ContinuityPacketV2Error(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ContinuityStateDimension:
    state_dimension_key: str
    signal_identity_mode: str
    canonical_signal_key: str | None
    original_signal_keys: list[str]
    effective_event_ids: list[str]
    asserted_event_ids: list[str]
    derived_event_ids: list[str]
    inferred_event_ids: list[str]
    unknown_event_ids: list[str]
    conflict_ids: list[str]
    resolution_status: str
    selected_asserted_event_id: str | None
    selected_tentative_event_id: str | None
    selected_unknown_event_id: str | None
    current_value: str | None
    tentative_value: str | None
    unknown_statement: str | None
    valid_from: str | None
    known_from: str | None
    temporal_phase: str | None
    temporal_influence: float
    epistemic_status: str
    evidence_completeness: str
    provenance_references: list[dict[str, Any]]
    state_dimension_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityCurrentStateV2:
    primary_state_status: str
    primary_dimension_key: str | None
    primary_asserted_value: str | None
    primary_asserted_event_id: str | None
    primary_tentative_value: str | None
    primary_tentative_event_id: str | None
    primary_unknown_statement: str | None
    primary_unknown_event_id: str | None
    primary_conflict_ids: list[str]
    occurred_at: str | None
    valid_from: str | None
    known_from: str | None
    temporal_phase: str | None
    temporal_horizon: str | None
    temporal_influence: float
    epistemic_status: str
    evidence_completeness: str
    provenance_references: list[dict[str, Any]]
    selection_rule: str
    selection_revision: str = CONTINUITY_V2_STATE_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityUnknownContext:
    unknown_event_ids: list[str]
    unknown_dimension_keys: list[str]
    exact_unknown_statements: list[str]
    first_unknown_at: str | None
    latest_unknown_at: str | None
    currently_active_unknown_count: int
    historically_resolved_unknown_count: int
    unresolved_unknown_count: int
    resolution_event_ids: list[str]
    evidence_references: list[dict[str, Any]]
    unknown_context_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityConflictContext:
    conflict_id: str
    conflict_type: str
    status: str
    affected_dimension_keys: list[str]
    participating_event_ids: list[str]
    participating_relationship_ids: list[str]
    epistemic_statuses: list[str]
    valid_from: str
    known_from: str
    resolution_event_id: str | None
    resolution_relationship_id: str | None
    evidence_references: list[dict[str, Any]]
    conflict_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityEntityContextV2:
    requested_entity_id: str | None
    canonical_entity_id: str | None
    entity_type: str | None
    canonical_label: str | None
    active_aliases: list[str]
    identity_status: str
    linked_event_ids: list[str]
    asserted_memory_count: int
    derived_memory_count: int
    tentative_memory_count: int
    unknown_memory_count: int
    conflicted_memory_count: int
    active_relationship_ids: list[str]
    entity_conflict_ids: list[str]
    entity_view_hash: str
    identity_revision: str = CONTINUITY_V2_ENTITY_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityRelationshipContextV2:
    relationship_id: str
    subject_entity_id: str
    relationship_type: str
    object_entity_id: str
    epistemic_status: str
    relationship_status: str
    valid_from: str
    valid_until: str | None
    known_from: str
    known_until: str | None
    temporal_phase: str | None
    conflict_ids: list[str]
    superseded_by_relationship_id: str | None
    evidence_completeness: str
    provenance_references: list[dict[str, Any]]
    relationship_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityLineageContextV2:
    originating_event_ids: list[str]
    correction_chains: list[dict[str, Any]]
    supersession_chains: list[dict[str, Any]]
    retraction_records: list[dict[str, Any]]
    conflict_declarations: list[dict[str, Any]]
    conflict_resolutions: list[dict[str, Any]]
    entity_merge_history: list[dict[str, Any]]
    relationship_evolution: list[dict[str, Any]]
    canonical_signal_mapping_history: list[dict[str, Any]]
    state_transition_records: list[dict[str, Any]]
    lineage_manifest_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityProvenanceContextV2:
    source_count: int
    segment_count: int
    candidate_count: int
    admission_count: int
    event_count: int
    complete_event_count: int
    partial_event_count: int
    legacy_event_count: int
    governance_erased_event_count: int
    integrity_failed_event_count: int
    evidence_bundle_references: list[dict[str, Any]]
    provenance_coverage_rate: dict[str, Any]
    provenance_manifest_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityGovernanceContext:
    governance_erasure_present: bool
    erasure_tombstone_count: int
    opaque_tombstone_references: list[str]
    erased_dependency_count: int
    partial_provenance_count: int
    historically_unrecoverable_item_count: int
    invalidated_packet_count: int
    governance_policy_revisions: list[str]
    recoverability_limitation_status: str
    governance_context_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityPacketV2:
    packet_id: str
    packet_version: str
    packet_mode: str
    packet_status: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    session_reference: str | None
    valid_at: str
    known_at: str
    generated_at: str
    current_state: dict[str, Any]
    state_dimensions: list[dict[str, Any]]
    asserted_information: list[dict[str, Any]]
    derived_information: list[dict[str, Any]]
    tentative_information: list[dict[str, Any]]
    unknown_information: list[dict[str, Any]]
    conflicted_information: list[dict[str, Any]]
    active_information_v2: list[dict[str, Any]]
    latent_information_v2: list[dict[str, Any]]
    dormant_information_v2: list[dict[str, Any]]
    decayed_information_v2: list[dict[str, Any]]
    reinforced_information_v2: list[dict[str, Any]]
    re_emergence_information_v2: list[dict[str, Any]]
    conflict_context: list[dict[str, Any]]
    unknown_context: dict[str, Any]
    entity_context: list[dict[str, Any]]
    relationship_context: dict[str, list[dict[str, Any]]]
    lineage_context: dict[str, Any]
    provenance_context: dict[str, Any]
    governance_context: dict[str, Any]
    temporal_horizon_summary: dict[str, int]
    legacy_coherence_score: float
    legacy_coherence_breakdown: dict[str, Any]
    legacy_recoverability_score: float
    legacy_recoverability_breakdown: dict[str, Any]
    v2_metrics: dict[str, Any]
    source_event_manifest_hash: str
    effective_event_manifest_hash: str
    temporal_dynamics_snapshot_id: str | None
    entity_manifest_hash: str
    relationship_manifest_hash: str
    conflict_manifest_hash: str
    canonical_signal_manifest_hash: str
    governance_manifest_hash: str
    packet_policy_configuration: dict[str, Any]
    revisions: dict[str, str]
    packet_manifest_hash: str
    packet_hash: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityPacketComparisonV2:
    first_packet_id: str
    second_packet_id: str
    boundary_changes: dict[str, Any]
    packet_status_change: dict[str, Any] | None
    primary_state_change: dict[str, Any] | None
    state_dimensions_added: list[str]
    state_dimensions_removed: list[str]
    state_dimension_changes: list[dict[str, Any]]
    asserted_items_added: list[str]
    asserted_items_removed: list[str]
    tentative_items_added: list[str]
    tentative_items_removed: list[str]
    unknown_items_added: list[str]
    unknown_items_resolved: list[str]
    conflicts_opened: list[str]
    conflicts_resolved: list[str]
    phase_changes: list[dict[str, Any]]
    reinforcement_changes: list[dict[str, Any]]
    re_emergence_changes: list[dict[str, Any]]
    entity_changes: list[dict[str, Any]]
    relationship_changes: list[dict[str, Any]]
    provenance_changes: dict[str, Any]
    governance_changes: dict[str, Any]
    metric_changes: dict[str, Any]
    policy_changes: dict[str, Any]
    comparison_hash: str
    comparison_revision: str = CONTINUITY_V2_COMPARISON_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuityPacketV2IntegrityResult:
    packet_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [name for name in globals() if name.startswith("CONTINUITY_V2_") or name.startswith("Continuity") or name == "ProvenanceCompletenessStatus"]
