"""Typed bitemporal memory-ledger evolution models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


MEMORY_LEDGER_SCHEMA_REVISION = "memory_ledger_v2"
MEMORY_EVOLUTION_REVISION = "memory_evolution_v1"
MEMORY_STATE_RESOLVER_REVISION = "memory_state_resolver_v1"
MEMORY_CONFLICT_REVISION = "memory_conflict_v1"
MEMORY_RECONSTRUCTION_REVISION = "memory_reconstruction_v1"
BITEMPORAL_POLICY_REVISION = "memory_bitemporal_v1"
CONTINUITY_INPUT_RESOLVER_REVISION = "continuity_input_resolver_v1"


class MemoryEventState(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    CONFLICTED = "conflicted"
    RESOLVED = "resolved"
    INVALIDATED = "invalidated"


class MemoryEvolutionType(str, Enum):
    CORRECT = "correct"
    SUPERSEDE = "supersede"
    RETRACT = "retract"
    DECLARE_CONTRADICTION = "declare_contradiction"
    RESOLVE_CONTRADICTION = "resolve_contradiction"
    INVALIDATE = "invalidate"


class MemoryEvolutionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLAYED = "replayed"


class MemoryEvolutionActorType(str, Enum):
    ENGINE_POLICY = "engine_policy"
    HUMAN = "human"
    INTERNAL_SERVICE = "internal_service"
    TEST_RUNNER = "test_runner"


class MemoryConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class MemoryTemporalBoundary:
    valid_at: str | None = None
    known_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryEvolutionRecord:
    evolution_id: str
    evolution_type: str
    evolution_status: str
    source_event_id: str
    replacement_event_id: str | None
    conflict_id: str | None
    resolution_event_id: str | None
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    valid_from: str
    valid_until: str | None
    system_effective_at: str
    evolution_actor_type: str
    evolution_actor_reference: str
    evolution_reason: str
    evolution_metadata: dict[str, Any]
    source_event_hash: str
    replacement_event_hash: str | None
    source_admission_id: str
    replacement_admission_id: str | None
    memory_ledger_schema_revision: str
    memory_evolution_revision: str
    bitemporal_policy_revision: str
    idempotency_digest: str
    completed_at: str
    duration_ms: float
    error_code: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConflict:
    conflict_id: str
    conflict_status: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    conflicting_event_ids: list[str]
    conflict_key: str | None
    conflict_type: str
    declared_by: str
    declaration_reason: str
    valid_from: str
    system_effective_at: str
    resolution_event_id: str | None
    resolved_at: str | None
    resolution_reason: str | None
    memory_conflict_revision: str
    memory_ledger_schema_revision: str
    idempotency_digest: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryEventProjection:
    event_id: str
    effective_state: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    superseded_by_event_id: str | None
    correction_event_id: str | None
    retraction_evolution_id: str | None
    open_conflict_ids: list[str]
    resolved_conflict_ids: list[str]
    epistemic_status: str
    event_type: str
    event_hash: str
    source_id: str | None
    admission_id: str | None
    projection_revision: str = MEMORY_STATE_RESOLVER_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedMemoryView:
    effective_events: list[dict[str, Any]]
    projections: list[MemoryEventProjection]
    excluded_counts: dict[str, int]
    open_conflicts: list[MemoryConflict]
    resolved_conflicts: list[MemoryConflict]
    temporal_boundary: MemoryTemporalBoundary
    evolution_record_count: int
    latest_evolution_id: str | None
    resolver_revision: str = MEMORY_STATE_RESOLVER_REVISION
    memory_ledger_schema_revision: str = MEMORY_LEDGER_SCHEMA_REVISION
    bitemporal_policy_revision: str = BITEMPORAL_POLICY_REVISION


@dataclass(frozen=True)
class MemoryReconstruction:
    reconstruction_id: str
    temporal_boundary: MemoryTemporalBoundary
    subject_scope: dict[str, str | None]
    resolver_revision: str
    effective_event_ids: list[str]
    excluded_counts: dict[str, int]
    open_conflicts: list[dict[str, Any]]
    resolved_conflicts: list[dict[str, Any]]
    ordered_state_transitions: list[dict[str, Any]]
    reconstruction_hash: str
    provenance_references: list[dict[str, str | None]]
    continuity_packet: dict[str, Any]
    generated_at: str
    engine_revision: str
    memory_reconstruction_revision: str = MEMORY_RECONSTRUCTION_REVISION
    bitemporal_policy_revision: str = BITEMPORAL_POLICY_REVISION
    continuity_input_resolver_revision: str = CONTINUITY_INPUT_RESOLVER_REVISION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["temporal_boundary"] = self.temporal_boundary.to_dict()
        return payload


@dataclass(frozen=True)
class MemoryLedgerIntegrityResult:
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    details: dict[str, Any] = field(default_factory=dict)


class MemoryLedgerError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


__all__ = [name for name in globals() if name.startswith("MEMORY_") or name.startswith("BITEMPORAL") or name.startswith("CONTINUITY") or name in {
    "MemoryEventState", "MemoryEvolutionType", "MemoryEvolutionStatus", "MemoryEvolutionActorType", "MemoryConflictStatus",
    "MemoryTemporalBoundary", "MemoryEvolutionRecord", "MemoryConflict", "MemoryEventProjection",
    "ResolvedMemoryView", "MemoryReconstruction", "MemoryLedgerIntegrityResult", "MemoryLedgerError",
}]
