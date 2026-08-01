"""Typed contracts for evidence-backed bitemporal relationship memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


RELATIONSHIP_MEMORY_SCHEMA_REVISION = "relationship_memory_v1"
RELATIONSHIP_CANDIDATE_REVISION = "relationship_candidate_v1"
RELATIONSHIP_EXTRACTOR_REVISION = "relationship_extractor_v1"
RELATIONSHIP_ADMISSION_REVISION = "relationship_admission_v1"
RELATIONSHIP_EVOLUTION_REVISION = "relationship_evolution_v1"
RELATIONSHIP_RESOLVER_REVISION = "relationship_resolver_v1"
RELATIONSHIP_TYPE_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
)
BUILTIN_RELATIONSHIP_TYPES = frozenset(
    {
        "mentioned_in",
        "participates_in",
        "owns",
        "belongs_to",
        "depends_on",
        "supports",
        "opposes",
        "interacts_with",
        "authored",
        "sent_to",
        "located_in",
        "member_of",
        "responsible_for_statement",
        "supersedes",
        "contradicts",
        "contributed_to",
        "related_to",
        "unknown_relationship",
    }
)
CAUSAL_OR_HIGH_RISK_RELATIONSHIPS = frozenset(
    {"responsible_for", "caused", "caused_by", "intends", "guilty_of", "owns"}
)
RELATIONSHIP_CANDIDATE_STATUSES = frozenset(
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
RELATIONSHIP_STATUSES = frozenset(
    {"active", "superseded", "retracted", "conflicted", "resolved", "invalidated"}
)
RELATIONSHIP_EVOLUTION_TYPES = frozenset(
    {
        "supersede",
        "retract",
        "declare_contradiction",
        "resolve_contradiction",
        "invalidate",
    }
)


class RelationshipMemoryError(RuntimeError):
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


def validate_relationship_type(value: str | None) -> str:
    normalised = str(value or "unknown_relationship").strip().lower().replace(" ", "_")
    if not RELATIONSHIP_TYPE_PATTERN.fullmatch(normalised):
        raise RelationshipMemoryError(
            "RELATIONSHIP_TYPE_INVALID", "Relationship type is invalid."
        )
    return normalised


@dataclass(frozen=True)
class RelationshipCandidate:
    relationship_candidate_id: str
    extraction_run_id: str | None
    source_id: str
    client_id: str
    vault_id: str
    namespace: str
    subject_entity_candidate_id: str | None
    subject_entity_id: str | None
    object_entity_candidate_id: str | None
    object_entity_id: str | None
    proposed_relationship_type: str
    proposed_valid_from: str | None
    proposed_valid_until: str | None
    epistemic_status: str
    extraction_confidence: float
    extraction_method: str
    primary_rule_id: str
    matched_rule_ids: list[str]
    candidate_status: str
    relationship_candidate_fingerprint_sha256: str
    evidence_manifest_hash_sha256: str
    normalisation_details: dict[str, Any]
    relationship_candidate_revision: str
    relationship_extractor_revision: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_relationship_type(self.proposed_relationship_type)
        if self.candidate_status not in RELATIONSHIP_CANDIDATE_STATUSES:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CANDIDATE_INVALID",
                "Relationship candidate status is invalid.",
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationshipEvidence:
    relationship_evidence_id: str
    relationship_candidate_id: str
    source_id: str
    segment_id: str
    evidence_role: str
    sequence_index: int
    source_start_offset: int | None
    source_end_offset: int | None
    segment_start_offset: int | None
    segment_end_offset: int | None
    json_pointer: str | None
    evidence_text_hash_sha256: str
    segment_content_hash_sha256: str
    subject_entity_evidence_id: str | None
    object_entity_evidence_id: str | None
    extraction_rule_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationshipRecord:
    relationship_id: str
    client_id: str
    vault_id: str
    namespace: str
    subject_entity_id: str
    relationship_type: str
    object_entity_id: str
    relationship_status: str
    epistemic_status: str
    originating_relationship_candidate_id: str
    originating_source_id: str
    originating_admission_id: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    relationship_fingerprint_sha256: str
    evidence_manifest_hash_sha256: str
    relationship_schema_revision: str
    relationship_admission_revision: str
    relationship_evolution_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationshipEvolutionRecord:
    relationship_evolution_id: str
    evolution_type: str
    source_relationship_id: str
    replacement_relationship_id: str | None
    conflict_id: str | None
    resolution_relationship_id: str | None
    client_id: str
    vault_id: str
    namespace: str
    valid_from: str
    system_effective_at: str
    actor_type: str
    actor_reference: str
    reason: str
    idempotency_digest: str
    relationship_evolution_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedRelationshipView:
    effective_relationships: list[RelationshipRecord]
    excluded_counts: dict[str, int]
    open_conflicts: list[dict[str, Any]]
    temporal_boundary: dict[str, str | None]
    deterministic_relationship_manifest: str
    resolver_revision: str = RELATIONSHIP_RESOLVER_REVISION

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_relationships": [
                item.to_dict() for item in self.effective_relationships
            ],
            "excluded_counts": self.excluded_counts,
            "open_conflicts": self.open_conflicts,
            "temporal_boundary": self.temporal_boundary,
            "deterministic_relationship_manifest": (
                self.deterministic_relationship_manifest
            ),
            "resolver_revision": self.resolver_revision,
        }


__all__ = [
    "BUILTIN_RELATIONSHIP_TYPES",
    "CAUSAL_OR_HIGH_RISK_RELATIONSHIPS",
    "RELATIONSHIP_ADMISSION_REVISION",
    "RELATIONSHIP_CANDIDATE_REVISION",
    "RELATIONSHIP_EVOLUTION_REVISION",
    "RELATIONSHIP_EXTRACTOR_REVISION",
    "RELATIONSHIP_MEMORY_SCHEMA_REVISION",
    "RELATIONSHIP_RESOLVER_REVISION",
    "RelationshipCandidate",
    "RelationshipEvidence",
    "RelationshipEvolutionRecord",
    "RelationshipMemoryError",
    "RelationshipRecord",
    "ResolvedRelationshipView",
    "validate_relationship_type",
]
