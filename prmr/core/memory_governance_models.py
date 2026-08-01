"""Typed contracts for deterministic memory lifecycle governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


MEMORY_GOVERNANCE_SCHEMA_REVISION = "memory_governance_v1"
MEMORY_GOVERNANCE_POLICY_REVISION = "memory_governance_policy_v1"
MEMORY_DEPENDENCY_GRAPH_REVISION = "memory_dependency_graph_v1"
MEMORY_GOVERNANCE_PLAN_REVISION = "memory_governance_plan_v1"
MEMORY_GOVERNANCE_EXECUTION_REVISION = "memory_governance_execution_v1"
MEMORY_GOVERNANCE_VERIFICATION_REVISION = "memory_governance_verification_v1"
MEMORY_RETENTION_POLICY_REVISION = "memory_retention_policy_v1"
MEMORY_PRESERVATION_HOLD_REVISION = "memory_preservation_hold_v1"
MEMORY_EXPORT_SCHEMA_REVISION = "memory_export_v1"
MEMORY_EXPORT_MANIFEST_REVISION = "memory_export_manifest_v1"
MEMORY_CORRECTION_REQUEST_REVISION = "memory_correction_request_v1"
MEMORY_ERASURE_TOMBSTONE_REVISION = "memory_erasure_tombstone_v1"


class MemoryGovernanceError(RuntimeError):
    def __init__(self, code: str, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


class MemoryGovernanceActionType(str, Enum):
    EXPORT = "export"
    CORRECT = "correct"
    EXPIRE = "expire"
    ERASE_SOURCE = "erase_source"
    ERASE_ACTOR = "erase_actor"
    ERASE_ENTITY = "erase_entity"
    ERASE_SESSION = "erase_session"
    ERASE_WORKSPACE = "erase_workspace"
    ERASE_APPLICATION = "erase_application"
    ERASE_TENANT_MEMORY = "erase_tenant_memory"
    VERIFY_ERASURE = "verify_erasure"
    APPLY_HOLD = "apply_hold"
    RELEASE_HOLD = "release_hold"


class MemoryGovernanceTargetType(str, Enum):
    SOURCE = "source"
    CANDIDATE = "candidate"
    ADMISSION = "admission"
    EVENT = "event"
    ACTOR = "actor"
    ENTITY = "entity"
    SESSION = "session"
    WORKSPACE = "workspace"
    APPLICATION = "application"
    RELATIONSHIP = "relationship"
    CONFLICT = "conflict"
    INTERPRETATION_REQUEST = "interpretation_request"
    CANONICAL_SIGNAL_MAPPING = "canonical_signal_mapping"
    TENANT_MEMORY_BOUNDARY = "tenant_memory_boundary"


class MemoryGovernanceActorType(str, Enum):
    HUMAN = "human"
    INTERNAL_SERVICE = "internal_service"
    ENGINE_POLICY = "engine_policy"
    MAINTENANCE = "maintenance"
    TEST_RUNNER = "test_runner"


class DependencyClassification(str, Enum):
    EXCLUSIVE_REQUIRED = "exclusive_required"
    SHARED_REQUIRED = "shared_required"
    OPTIONAL_CONTEXT = "optional_context"
    DERIVED_CACHE = "derived_cache"
    AUDIT_REFERENCE = "audit_reference"
    GOVERNANCE_REFERENCE = "governance_reference"


@dataclass(frozen=True)
class GovernanceActor:
    actor_type: str
    actor_reference: str


@dataclass(frozen=True)
class MemoryGovernanceRequest:
    governance_request_id: str
    action_type: str
    target_type: str
    opaque_target_reference: str
    target_reference_digest: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    session_reference: str | None
    requested_by_actor_type: str
    requested_by_actor_reference: str
    request_reason: str
    request_metadata: dict[str, Any]
    governance_policy_id: str
    requested_at: str
    request_idempotency_digest: str
    request_status: str
    approved_plan_id: str | None
    completed_execution_id: str | None
    memory_governance_schema_revision: str
    memory_governance_policy_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DependencyNode:
    node_id: str
    node_type: str
    storage_table: str
    storage_key: str
    scope_fingerprint: str
    content_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DependencyEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: str
    classification: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryDependencyGraphResult:
    dependency_graph_id: str
    governance_request_id: str
    target_nodes: tuple[DependencyNode, ...]
    discovered_nodes: tuple[DependencyNode, ...]
    discovered_edges: tuple[DependencyEdge, ...]
    exclusive_dependency_count: int
    shared_dependency_count: int
    cache_dependency_count: int
    blockers: tuple[str, ...]
    active_holds: tuple[str, ...]
    graph_manifest_hash: str
    graph_revision: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["target_nodes"] = [item.to_dict() for item in self.target_nodes]
        value["discovered_nodes"] = [item.to_dict() for item in self.discovered_nodes]
        value["discovered_edges"] = [item.to_dict() for item in self.discovered_edges]
        return value


@dataclass(frozen=True)
class MemoryGovernancePlan:
    governance_plan_id: str
    governance_request_id: str
    action_type: str
    target_type: str
    target_digest: str
    scope: tuple[str, str, str]
    dependency_graph_id: str
    source_manifest_before: str
    event_manifest_before: str
    entity_manifest_before: str
    relationship_manifest_before: str
    canonical_signal_manifest_before: str
    planned_erase_nodes: tuple[str, ...]
    planned_detach_edges: tuple[str, ...]
    planned_recompute_nodes: tuple[str, ...]
    planned_invalidate_nodes: tuple[str, ...]
    planned_retain_nodes: tuple[str, ...]
    planned_tombstones: tuple[str, ...]
    blockers: tuple[str, ...]
    preservation_holds: tuple[str, ...]
    estimated_counts_by_type: dict[str, int]
    estimated_storage_bytes: int | None
    plan_status: str
    plan_hash_sha256: str
    memory_governance_plan_revision: str
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


@dataclass(frozen=True)
class MemoryGovernanceExecution:
    governance_execution_id: str
    governance_request_id: str
    governance_plan_id: str
    action_type: str
    target_type: str
    scope: tuple[str, str, str]
    execution_status: str
    phase: str
    manifest_before: str
    manifest_after: str | None
    erased_counts: dict[str, int]
    detached_counts: dict[str, int]
    recomputed_counts: dict[str, int]
    invalidated_counts: dict[str, int]
    retained_counts: dict[str, int]
    tombstone_count: int
    verification_id: str | None
    started_at: str
    completed_at: str | None
    duration_ms: int | None
    error_code: str | None
    execution_idempotency_digest: str
    memory_governance_execution_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


@dataclass(frozen=True)
class MemoryGovernanceVerification:
    governance_verification_id: str
    governance_execution_id: str
    verification_status: str
    target_absent: bool
    governed_dependencies_absent_or_valid: bool
    shared_dependencies_recomputed: bool
    indexes_cleared: bool
    checkpoints_invalidated: bool
    queries_invalidated: bool
    exports_invalidated: bool
    no_cross_scope_change: bool
    integrity_checks: dict[str, bool]
    remaining_reference_counts: dict[str, int]
    verification_manifest_hash: str
    memory_governance_verification_revision: str
    verified_at: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryErasureTombstone:
    erasure_tombstone_id: str
    governance_execution_id: str
    target_type: str
    target_reference_digest: str
    scope_fingerprint: str
    governance_policy_id: str
    plan_hash_sha256: str
    object_counts_by_type: dict[str, int]
    manifest_before_hash: str
    manifest_after_hash: str
    verification_hash: str
    completed_at: str
    tombstone_status: str
    memory_erasure_tombstone_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryPreservationHold:
    preservation_hold_id: str
    client_id: str
    vault_id: str
    namespace: str
    target_type: str
    target_reference_digest: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    session_reference: str | None
    hold_status: str
    hold_reason: str
    applied_by_actor_type: str
    applied_by_actor_reference: str
    applied_at: str
    release_at: str | None
    released_by_actor_reference: str | None
    released_reason: str | None
    hold_idempotency_digest: str
    memory_preservation_hold_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryRetentionAnnotation:
    retention_annotation_id: str
    target_type: str
    target_reference_digest: str
    scope: tuple[str, str, str]
    retention_mode: str
    retain_until: str | None
    annotation_actor_type: str
    annotation_actor_reference: str
    annotation_reason: str
    system_effective_at: str
    idempotency_digest: str
    memory_retention_policy_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


@dataclass(frozen=True)
class MemoryExportRequest:
    memory_export_request_id: str
    governance_request_id: str
    export_type: str
    target_type: str
    target_reference_digest: str
    scope: tuple[str, str, str]
    export_policy_id: str
    valid_at: str | None
    known_at: str | None
    include_raw_sources: bool
    include_segments: bool
    include_candidates: bool
    include_admissions: bool
    include_events: bool
    include_evolutions: bool
    include_temporal_dynamics: bool
    include_entities: bool
    include_relationships: bool
    include_conflicts: bool
    include_queries: bool
    include_consolidations: bool
    include_interpretation: bool
    include_canonical_mappings: bool
    export_status: str
    created_at: str
    completed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


@dataclass(frozen=True)
class MemoryExportBundle:
    memory_export_bundle_id: str
    memory_export_request_id: str
    scope: tuple[str, str, str]
    target_type: str
    valid_at: str | None
    known_at: str | None
    export_schema_revision: str
    export_policy_revision: str
    sections: dict[str, tuple[dict[str, Any], ...]]
    object_counts: dict[str, int]
    completeness_status: str
    redaction_count: int
    bundle_manifest_hash_sha256: str
    generated_at: str
    expires_at: str | None
    storage_reference: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        value["sections"] = {
            key: list(items) for key, items in self.sections.items()
        }
        return value


@dataclass(frozen=True)
class MemoryCorrectionRequest:
    memory_correction_request_id: str
    target_type: str
    target_id: str
    scope: tuple[str, str, str]
    requested_change_type: str
    requested_replacement_reference: str | None
    requested_value_digest: str | None
    correction_reason: str
    requested_by_actor_type: str
    requested_by_actor_reference: str
    request_status: str
    routed_operation_type: str | None
    routed_operation_id: str | None
    memory_correction_request_revision: str
    created_at: str
    resolved_at: str | None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


@dataclass(frozen=True)
class GovernanceExecutionResult:
    execution: MemoryGovernanceExecution
    verification: MemoryGovernanceVerification | None
    tombstone: MemoryErasureTombstone | None
    replayed: bool = False
    safe_notices: tuple[str, ...] = field(default_factory=tuple)


__all__ = [name for name in globals() if name.startswith("MEMORY_")] + [
    "DependencyClassification",
    "DependencyEdge",
    "DependencyNode",
    "GovernanceActor",
    "GovernanceExecutionResult",
    "MemoryCorrectionRequest",
    "MemoryDependencyGraphResult",
    "MemoryErasureTombstone",
    "MemoryExportBundle",
    "MemoryExportRequest",
    "MemoryGovernanceActionType",
    "MemoryGovernanceActorType",
    "MemoryGovernanceError",
    "MemoryGovernanceExecution",
    "MemoryGovernancePlan",
    "MemoryGovernanceRequest",
    "MemoryGovernanceTargetType",
    "MemoryGovernanceVerification",
    "MemoryPreservationHold",
    "MemoryRetentionAnnotation",
]
