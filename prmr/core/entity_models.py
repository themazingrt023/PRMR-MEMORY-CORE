"""Typed contracts for evidence-backed entity identity memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


ENTITY_MEMORY_SCHEMA_REVISION = "entity_memory_v1"
ENTITY_CANDIDATE_REVISION = "entity_candidate_v1"
ENTITY_EXTRACTOR_REVISION = "entity_extractor_v1"
ENTITY_ADMISSION_REVISION = "entity_admission_v1"
ENTITY_IDENTITY_REVISION = "entity_identity_v1"
ENTITY_RESOLUTION_REVISION = "entity_resolution_v1"
ENTITY_ALIAS_REVISION = "entity_alias_v1"
ENTITY_MENTION_REVISION = "entity_mention_v1"
EVENT_ENTITY_LINK_REVISION = "event_entity_link_v1"
ENTITY_CONTINUITY_ADAPTER_REVISION = "entity_continuity_adapter_v1"

ENTITY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
BUILTIN_ENTITY_TYPES = frozenset(
    {
        "person",
        "organisation",
        "project",
        "account",
        "agent",
        "character",
        "device",
        "document",
        "location",
        "concept",
        "software_system",
        "team",
        "event",
        "unknown",
    }
)
ENTITY_CANDIDATE_STATUSES = frozenset(
    {
        "pending_review",
        "accepted",
        "rejected",
        "deferred",
        "duplicate",
        "corrected",
        "invalidated",
    }
)
ENTITY_STATUSES = frozenset({"active", "merged", "retired", "invalidated"})
IDENTITY_BASES = frozenset(
    {
        "stable_external_identifier",
        "explicit_source_identity",
        "manual_internal_confirmation",
        "explicit_alias_resolution",
        "unresolved_label_only",
    }
)
MENTION_ROLES = frozenset(
    {
        "subject",
        "object",
        "speaker",
        "owner",
        "participant",
        "author",
        "recipient",
        "referenced",
        "unknown",
    }
)
MENTION_RESOLUTION_STATUSES = frozenset(
    {
        "resolved",
        "possible_match",
        "ambiguous",
        "distinct",
        "unresolved",
        "invalidated",
    }
)
ALIAS_STATUSES = frozenset(
    {"active", "superseded", "retracted", "conflicted", "invalidated"}
)
RESOLUTION_TYPES = frozenset(
    {
        "create_new_entity",
        "confirm_existing_entity",
        "possible_match",
        "declare_distinct",
        "confirm_alias",
        "reject_entity_candidate",
        "defer_resolution",
    }
)
EVENT_ENTITY_ROLES = frozenset(
    {
        "primary_subject",
        "actor",
        "object",
        "participant",
        "owner",
        "related",
        "speaker",
        "target",
        "unknown",
    }
)
EVENT_ENTITY_LINK_METHODS = frozenset(
    {
        "explicit_event_reference",
        "structured_source_reference",
        "admitted_entity_candidate",
        "manual_internal_link",
        "alias_resolution",
        "legacy_reference_mapping",
    }
)


class EntityMemoryError(RuntimeError):
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


def validate_entity_type(value: str | None) -> str:
    normalised = str(value or "unknown").strip().lower().replace(" ", "_")
    if not ENTITY_TYPE_PATTERN.fullmatch(normalised):
        raise EntityMemoryError("ENTITY_TYPE_INVALID", "Entity type is invalid.")
    return normalised


@dataclass(frozen=True)
class EntityCandidate:
    entity_candidate_id: str
    extraction_run_id: str | None
    source_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    session_reference: str | None
    proposed_entity_type: str
    proposed_label: str | None
    proposed_external_identifiers: list[dict[str, str]]
    proposed_aliases: list[str]
    epistemic_status: str
    extraction_confidence: float
    confidence_basis: str
    extraction_method: str
    primary_rule_id: str
    matched_rule_ids: list[str]
    candidate_status: str
    entity_candidate_fingerprint_sha256: str
    evidence_manifest_hash_sha256: str
    normalisation_details: dict[str, Any]
    entity_candidate_revision: str
    entity_extractor_revision: str
    entity_resolution_revision: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_entity_type(self.proposed_entity_type)
        if self.candidate_status not in ENTITY_CANDIDATE_STATUSES:
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_INVALID", "Entity candidate status is invalid."
            )
        if not 0.0 <= self.extraction_confidence <= 1.0:
            raise EntityMemoryError(
                "ENTITY_CANDIDATE_INVALID",
                "Entity extraction confidence is outside 0-1.",
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityEvidence:
    entity_evidence_id: str
    entity_candidate_id: str
    source_id: str
    segment_id: str
    evidence_role: str
    sequence_index: int
    source_start_offset: int | None
    source_end_offset: int | None
    segment_start_offset: int | None
    segment_end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None
    evidence_text_hash_sha256: str
    segment_content_hash_sha256: str
    source_content_hash_sha256: str
    extraction_rule_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str
    client_id: str
    vault_id: str
    namespace: str
    canonical_entity_type: str
    canonical_label: str | None
    entity_status: str
    originating_entity_candidate_id: str
    originating_source_id: str
    originating_admission_id: str
    identity_fingerprint_sha256: str
    identity_basis: str
    first_known_at: str
    first_valid_at: str
    retired_at: str | None
    merged_into_entity_id: str | None
    entity_schema_revision: str
    entity_identity_revision: str
    entity_resolution_revision: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_entity_type(self.canonical_entity_type)
        if self.entity_status not in ENTITY_STATUSES:
            raise EntityMemoryError("ENTITY_INTEGRITY_FAILED", "Entity status is invalid.")
        if self.identity_basis not in IDENTITY_BASES:
            raise EntityMemoryError(
                "ENTITY_INTEGRITY_FAILED", "Entity identity basis is invalid."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityIdentifier:
    entity_identifier_id: str
    entity_id: str
    identifier_namespace: str
    identifier_value_digest: str
    identifier_display_hint: str | None
    identifier_type: str
    source_id: str
    segment_id: str | None
    epistemic_status: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    identifier_status: str
    entity_identity_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityMention:
    entity_mention_id: str
    entity_id: str | None
    entity_candidate_id: str
    source_id: str
    segment_id: str
    client_id: str
    vault_id: str
    namespace: str
    mention_text_hash_sha256: str
    safe_display_text: str
    mention_start_offset: int | None
    mention_end_offset: int | None
    json_pointer: str | None
    speaker: str | None
    occurred_at: str | None
    mention_role: str
    epistemic_status: str
    resolution_status: str
    resolution_decision_id: str | None
    entity_mention_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityAliasAssertion:
    alias_assertion_id: str
    entity_id: str
    alias_value: str
    alias_normalised: str
    alias_hash_sha256: str
    source_id: str
    segment_id: str | None
    evidence_manifest_hash_sha256: str
    epistemic_status: str
    assertion_actor_type: str
    assertion_actor_reference: str
    assertion_reason: str
    valid_from: str
    valid_until: str | None
    system_effective_at: str
    alias_status: str
    entity_alias_revision: str
    idempotency_digest: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityResolutionDecision:
    entity_resolution_decision_id: str
    entity_candidate_id: str | None
    entity_mention_id: str | None
    selected_entity_id: str | None
    resolution_type: str
    resolution_status: str
    candidate_entity_ids: list[str]
    decision_actor_type: str
    decision_actor_reference: str
    decision_reason: str
    decision_evidence: list[dict[str, Any]]
    entity_resolution_revision: str
    idempotency_digest: str
    decided_at: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventEntityLink:
    event_entity_link_id: str
    event_id: str
    entity_id: str
    entity_role: str
    link_epistemic_status: str
    link_method: str
    source_id: str
    segment_id: str | None
    candidate_id: str | None
    admission_id: str | None
    entity_candidate_id: str | None
    entity_resolution_decision_id: str | None
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    event_entity_link_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityMemoryView:
    entity_id: str
    canonical_entity_id: str
    canonical_label: str | None
    canonical_type: str
    aliases: list[str]
    stable_identifiers: list[dict[str, str | None]]
    first_seen: str
    last_seen: str | None
    source_count: int
    mention_count: int
    linked_event_count: int
    active_relationship_count: int
    open_relationship_conflict_count: int
    current_event_state_summary: dict[str, Any]
    temporal_memory_summary: dict[str, Any]
    related_entity_ids: list[str]
    entity_identity_revisions: list[str]
    reconstruction_boundary: dict[str, str | None]
    deterministic_view_hash: str
    provenance_references: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "ALIAS_STATUSES",
    "BUILTIN_ENTITY_TYPES",
    "ENTITY_ADMISSION_REVISION",
    "ENTITY_ALIAS_REVISION",
    "ENTITY_CANDIDATE_REVISION",
    "ENTITY_CONTINUITY_ADAPTER_REVISION",
    "ENTITY_EXTRACTOR_REVISION",
    "ENTITY_IDENTITY_REVISION",
    "ENTITY_MEMORY_SCHEMA_REVISION",
    "ENTITY_MENTION_REVISION",
    "ENTITY_RESOLUTION_REVISION",
    "ENTITY_TYPE_PATTERN",
    "EVENT_ENTITY_LINK_REVISION",
    "EntityAliasAssertion",
    "EntityCandidate",
    "EntityEvidence",
    "EntityIdentifier",
    "EntityMemoryError",
    "EntityMemoryView",
    "EntityMention",
    "EntityRecord",
    "EntityResolutionDecision",
    "EventEntityLink",
    "validate_entity_type",
]
