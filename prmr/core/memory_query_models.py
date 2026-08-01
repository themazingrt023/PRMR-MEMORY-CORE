"""Typed contracts for deterministic memory queries and their audit artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import re
from typing import Any


MEMORY_QUERY_SCHEMA_REVISION = "memory_query_v1"
MEMORY_QUERY_POLICY_REVISION = "memory_query_policy_v1"
MEMORY_QUERY_PLANNER_REVISION = "memory_query_planner_v1"
MEMORY_QUERY_RESULT_REVISION = "memory_query_result_v1"
MEMORY_EVIDENCE_BUNDLE_REVISION = "memory_evidence_bundle_v1"
MEMORY_EXPLANATION_REVISION = "memory_explanation_v1"
MEMORY_TIMELINE_REVISION = "memory_timeline_v1"
MEMORY_CHANGE_PROJECTION_REVISION = "memory_change_projection_v1"
MEMORY_QUERY_INTEGRITY_REVISION = "memory_query_integrity_v1"
MEMORY_QUERY_PAGINATION_REVISION = "memory_query_pagination_v1"
MEMORY_QUERY_COMPARISON_REVISION = "memory_query_comparison_v1"

QUERY_ID_PATTERN = re.compile(
    r"^(?:src|seg|cand|adm|evt|entity|rel|cnfl|rconf|packet|recon|ercon|dyn|qrun|qres|ebun|xpln)_[A-Za-z0-9_.:-]+$"
)
ENTITY_TARGET_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,255}$")
SIGNAL_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


class MemoryQueryMode(str, Enum):
    DETERMINISTIC_STRICT_V1 = "deterministic_strict_v1"
    SEMANTIC_ASSISTED = "semantic_assisted"
    MODEL_ASSISTED = "model_assisted"


class MemoryQueryType(str, Enum):
    CURRENT_STATE = "current_state"
    MEMORY_BY_PHASE = "memory_by_phase"
    CHANGES_BETWEEN = "changes_between"
    EVENT_TIMELINE = "event_timeline"
    SIGNAL_HISTORY = "signal_history"
    RECURRENCE = "recurrence"
    RE_EMERGENCE = "re_emergence"
    OPEN_CONFLICTS = "open_conflicts"
    RESOLVED_CONFLICTS = "resolved_conflicts"
    EVIDENCE_FOR_EVENT = "evidence_for_event"
    EVIDENCE_FOR_CURRENT_STATE = "evidence_for_current_state"
    PROVENANCE_TRACE = "provenance_trace"
    STATE_AS_KNOWN_AT = "state_as_known_at"
    STATE_AT_VALID_TIME = "state_at_valid_time"
    BITEMPORAL_STATE = "bitemporal_state"
    ENTITY_STATE = "entity_state"
    ENTITY_HISTORY = "entity_history"
    RELATIONSHIP_STATE = "relationship_state"
    RELATIONSHIP_HISTORY = "relationship_history"
    RECOVERABILITY_EXPLANATION = "recoverability_explanation"
    CONTINUITY_PACKET = "continuity_packet"
    UNKNOWN_INFORMATION = "unknown_information"


class MemoryQueryResultStatus(str, Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    CONFLICTED = "conflicted"
    NO_DATA = "no_data"
    NOT_APPLICABLE = "not_applicable"
    TRUNCATED = "truncated"


class EvidenceCompletenessStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    LEGACY_WITHOUT_SOURCE = "legacy_without_source"
    INTEGRITY_FAILED = "integrity_failed"
    TRUNCATED = "truncated"


class MemoryQueryError(RuntimeError):
    """Stable, non-sensitive query failure."""

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
class MemoryQueryRequest:
    query_type: str
    query_mode: str = MemoryQueryMode.DETERMINISTIC_STRICT_V1.value
    client_id: str | None = None
    vault_id: str | None = None
    namespace: str | None = None
    application_reference: str | None = None
    actor_reference: str | None = None
    workspace_reference: str | None = None
    entity_id: str | None = None
    relationship_id: str | None = None
    session_reference: str | None = None
    event_id: str | None = None
    signal_key: str | None = None
    conflict_id: str | None = None
    source_id: str | None = None
    candidate_id: str | None = None
    admission_id: str | None = None
    packet_id: str | None = None
    reconstruction_id: str | None = None
    dynamics_snapshot_id: str | None = None
    first_temporal_boundary: dict[str, str | None] | None = None
    second_temporal_boundary: dict[str, str | None] | None = None
    valid_at: str | None = None
    known_at: str | None = None
    memory_phase_filter: tuple[str, ...] = ()
    epistemic_status_filter: tuple[str, ...] = ()
    event_type_filter: tuple[str, ...] = ()
    relationship_type_filter: tuple[str, ...] = ()
    include_evidence: bool | None = None
    include_safe_evidence_preview: bool | None = None
    include_packet: bool | None = None
    include_explanation: bool | None = None
    include_conflicted: bool | None = None
    include_inactive_history: bool = False
    maximum_results: int | None = None
    maximum_evidence_items: int | None = None
    cursor: str | None = None
    query_policy_id: str = "strict_query_v1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "memory_phase_filter",
            "epistemic_status_filter",
            "event_type_filter",
            "relationship_type_filter",
        ):
            payload[key] = list(payload[key])
        return payload

    def resolved_scope(
        self, client_id: str, vault_id: str, namespace: str
    ) -> "MemoryQueryRequest":
        return replace(
            self,
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
        )


@dataclass(frozen=True)
class MemoryQueryPolicy:
    policy_id: str = "strict_query_v1"
    maximum_results: int = 500
    maximum_evidence_items: int = 100
    maximum_safe_preview_characters: int = 240
    include_evidence: bool = True
    include_safe_evidence_preview: bool = False
    include_explanation: bool = True
    include_packet: bool = False
    include_conflicted: bool = True
    require_integrity: bool = True
    preserve_epistemic_status: bool = True
    fail_on_scope_mismatch: bool = True
    exact_signal_matching_only: bool = True
    semantic_matching: bool = False
    persist_query_run: bool = True
    persist_result_payload: bool = True
    policy_revision: str = MEMORY_QUERY_POLICY_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQueryPlan:
    query_type: str
    query_mode: str
    query_policy_id: str
    valid_at: str
    known_at: str
    required_services: list[str]
    integrity_dependencies: list[str]
    evidence_required: bool
    explanation_required: bool
    packet_required: bool
    maximum_results: int
    maximum_evidence_items: int
    cursor_offset: int
    plan_steps: list[dict[str, Any]]
    normalised_query_payload: dict[str, Any]
    query_plan_hash_sha256: str
    memory_query_planner_revision: str = MEMORY_QUERY_PLANNER_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQueryRun:
    query_run_id: str
    query_type: str
    query_mode: str
    query_policy_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    relationship_id: str | None
    session_reference: str | None
    event_id: str | None
    signal_key: str | None
    valid_at: str
    known_at: str
    first_temporal_boundary: dict[str, str | None] | None
    second_temporal_boundary: dict[str, str | None] | None
    normalised_query_payload: dict[str, Any]
    query_fingerprint_sha256: str
    query_plan_hash_sha256: str
    resolved_event_manifest_hash: str
    relevant_memory_manifest_hash: str
    dynamics_snapshot_id: str | None
    reconstruction_id: str | None
    entity_view_hash: str | None
    relationship_manifest_hash: str | None
    query_status: str
    result_status: str | None
    result_id: str | None
    result_hash_sha256: str | None
    evidence_bundle_id: str | None
    result_count: int
    evidence_count: int
    truncated: bool
    memory_query_schema_revision: str
    memory_query_policy_revision: str
    memory_query_planner_revision: str
    started_at: str
    completed_at: str | None
    duration_ms: float
    error_code: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EpistemicSummary:
    explicit_item_count: int = 0
    derived_item_count: int = 0
    inferred_item_count: int = 0
    unknown_item_count: int = 0
    conflicted_item_count: int = 0
    dominant_epistemic_status: str | None = None
    contains_unconfirmed_information: bool = False
    contains_unknown_information: bool = False
    contains_conflict: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQueryResult:
    query_result_id: str
    query_run_id: str
    query_type: str
    result_status: str
    answer_payload: dict[str, Any]
    epistemic_summary: dict[str, Any]
    temporal_boundary: dict[str, str]
    subject_scope: dict[str, str | None]
    effective_event_count: int
    excluded_event_counts: dict[str, int]
    conflict_count: int
    unknown_count: int
    evidence_bundle_id: str | None
    explanation_id: str | None
    result_manifest_hash_sha256: str
    result_hash_sha256: str
    memory_query_result_revision: str
    generated_at: str
    created_at: str
    next_cursor: str | None = None
    replayed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryEvidenceItem:
    evidence_item_id: str
    evidence_type: str
    source_id: str
    segment_id: str | None
    event_id: str | None
    entity_id: str | None
    relationship_id: str | None
    candidate_id: str | None
    admission_id: str | None
    source_start_offset: int | None
    source_end_offset: int | None
    segment_start_offset: int | None
    segment_end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None
    content_hash_sha256: str
    safe_preview: str | None
    epistemic_status: str
    evidence_role: str
    integrity_status: str
    sequence_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryEvidenceBundle:
    evidence_bundle_id: str
    query_run_id: str
    client_id: str
    vault_id: str
    namespace: str
    source_ids: list[str]
    segment_ids: list[str]
    candidate_ids: list[str]
    admission_ids: list[str]
    event_ids: list[str]
    evolution_ids: list[str]
    dynamics_snapshot_ids: list[str]
    entity_ids: list[str]
    relationship_ids: list[str]
    conflict_ids: list[str]
    packet_ids: list[str]
    reconstruction_ids: list[str]
    evidence_items: list[MemoryEvidenceItem]
    evidence_item_count: int
    completeness_status: str
    truncated: bool
    evidence_manifest_hash_sha256: str
    memory_evidence_bundle_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_items"] = [item.to_dict() for item in self.evidence_items]
        return payload


@dataclass(frozen=True)
class MemoryExplanation:
    explanation_id: str
    query_run_id: str
    query_result_id: str
    explanation_type: str
    explanation_status: str
    summary_template_id: str
    summary_text: str
    basis_items: list[dict[str, Any]]
    selection_steps: list[dict[str, Any]]
    exclusions: list[dict[str, Any]]
    epistemic_warnings: list[str]
    conflict_warnings: list[str]
    unknown_warnings: list[str]
    policy_references: list[str]
    revision_references: list[str]
    explanation_hash_sha256: str
    memory_explanation_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQueryResultComparison:
    first_result_id: str
    second_result_id: str
    first_status: str
    second_status: str
    state_changed: bool
    answer_items_added: list[Any]
    answer_items_removed: list[Any]
    epistemic_changes: dict[str, Any]
    conflict_changes: dict[str, Any]
    evidence_changes: dict[str, Any]
    temporal_boundary_changes: dict[str, Any]
    revision_changes: dict[str, Any]
    result_hash_changed: bool
    comparison_hash_sha256: str
    comparison_revision: str = MEMORY_QUERY_COMPARISON_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQueryIntegrityResult:
    query_run_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    details: dict[str, Any] = field(default_factory=dict)
    memory_query_integrity_revision: str = MEMORY_QUERY_INTEGRITY_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [name for name in globals() if name.startswith("MEMORY_") or name in {
    "EvidenceCompletenessStatus",
    "EpistemicSummary",
    "ENTITY_TARGET_PATTERN",
    "MemoryEvidenceBundle",
    "MemoryEvidenceItem",
    "MemoryExplanation",
    "MemoryQueryError",
    "MemoryQueryIntegrityResult",
    "MemoryQueryMode",
    "MemoryQueryPlan",
    "MemoryQueryPolicy",
    "MemoryQueryRequest",
    "MemoryQueryResult",
    "MemoryQueryResultComparison",
    "MemoryQueryResultStatus",
    "MemoryQueryRun",
    "MemoryQueryType",
    "QUERY_ID_PATTERN",
    "SIGNAL_KEY_PATTERN",
}]
