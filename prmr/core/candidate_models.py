"""Typed models for provenance-backed candidate memories."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any


CANDIDATE_SCHEMA_REVISION = "candidate_memory_v1"
CANDIDATE_EXTRACTOR_REVISION = "candidate_extractor_v1"
CANDIDATE_RULE_REVISION = "candidate_rules_v1"
CANDIDATE_CLAIM_SPLITTER_REVISION = "candidate_claim_splitter_v1"
CANDIDATE_MANIFEST_REVISION = "candidate_manifest_v1"
ADMISSION_COMPATIBLE_CANDIDATE_MANIFEST_REVISION = "candidate_manifest_v2_admission_compatible"
EPISTEMIC_POLICY_REVISION = "epistemic_policy_v1"
EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class EpistemicStatus(str, Enum):
    EXPLICIT = "explicit"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ExtractionMethod(str, Enum):
    STRUCTURED_FIELD = "structured_field"
    EXPLICIT_LABEL = "explicit_label"
    DETERMINISTIC_PATTERN = "deterministic_pattern"
    DETERMINISTIC_DERIVATION = "deterministic_derivation"
    UNCERTAINTY_PATTERN = "uncertainty_pattern"
    UNKNOWN_MARKER = "unknown_marker"


class CandidateStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    DUPLICATE = "duplicate"
    INVALIDATED = "invalidated"


class ExtractionRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class EvidenceRole(str, Enum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    DERIVATION_INPUT = "derivation_input"
    CONTEXT = "context"


@dataclass(frozen=True)
class CandidateExtractionPolicy:
    policy_id: str = "strict_v1"
    allow_explicit: bool = True
    allow_derived: bool = True
    allow_inferred: bool = True
    record_unknown_markers: bool = True
    maximum_candidates_per_source: int = 2_000
    minimum_signal_length: int = 3
    maximum_signal_length: int = 2_000
    deduplicate_exact_candidates: bool = True
    require_source_integrity: bool = True
    require_segment_integrity: bool = True
    preserve_source_wording: bool = True
    structured_rules_enabled: bool = True
    labelled_rules_enabled: bool = True
    lexical_rules_enabled: bool = True
    uncertainty_rules_enabled: bool = True

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,80}", self.policy_id):
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate policy ID is invalid.")
        if not 1 <= self.maximum_candidates_per_source <= 100_000:
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate limit is outside allowed bounds.")
        if not 1 <= self.minimum_signal_length <= self.maximum_signal_length <= 10_000:
            raise CandidateEngineError("CANDIDATE_POLICY_INVALID", "Candidate signal bounds are invalid.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClaimSpan:
    segment_id: str
    segment_sequence_index: int
    claim_sequence_index: int
    text: str
    segment_start_offset: int
    segment_end_offset: int
    source_start_offset: int | None
    source_end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None = None


@dataclass(frozen=True)
class ExtractionRun:
    extraction_run_id: str
    extraction_identity_sha256: str
    source_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    source_content_hash_sha256: str
    source_canonical_hash_sha256: str
    source_segment_manifest_hash_sha256: str
    candidate_extractor_revision: str
    candidate_rule_revision: str
    candidate_claim_splitter_revision: str
    epistemic_policy_revision: str
    extraction_policy: dict[str, Any]
    status: str
    candidate_count: int
    explicit_count: int
    derived_count: int
    inferred_count: int
    unknown_count: int
    duplicate_count: int
    candidate_manifest_hash_sha256: str
    started_at: str
    completed_at: str | None
    duration_ms: float
    error_code: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateMemory:
    candidate_id: str
    extraction_run_id: str
    source_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    proposed_event_type: str | None
    proposed_signal: str
    proposed_occurred_at: str | None
    epistemic_status: str
    extraction_confidence: float
    confidence_basis: str
    extraction_method: str
    primary_rule_id: str
    matched_rule_ids: list[str]
    duplicate_match_count: int
    candidate_status: str
    candidate_fingerprint_sha256: str
    evidence_manifest_hash_sha256: str
    normalisation_details: dict[str, Any]
    candidate_schema_revision: str
    candidate_extractor_revision: str
    candidate_rule_revision: str
    epistemic_policy_revision: str
    created_at: str
    updated_at: str
    corrected_from_candidate_id: str | None = None
    replacement_candidate_id: str | None = None
    current_admission_state: str = CandidateStatus.PENDING_REVIEW.value
    accepted_admission_id: str | None = None
    accepted_event_id: str | None = None
    candidate_correction_revision: str | None = None

    def __post_init__(self) -> None:
        if not self.proposed_signal.strip():
            raise CandidateEngineError("CANDIDATE_EXTRACTION_FAILED", "Candidate signal must not be empty.")
        if not 0.0 <= self.extraction_confidence <= 1.0:
            raise CandidateEngineError("CANDIDATE_EXTRACTION_FAILED", "Extraction confidence is outside 0-1.")
        if self.proposed_event_type is not None and not EVENT_TYPE_PATTERN.fullmatch(self.proposed_event_type):
            raise CandidateEngineError("CANDIDATE_EXTRACTION_FAILED", "Proposed event type is invalid.")
        if self.proposed_event_type is None and self.epistemic_status != EpistemicStatus.UNKNOWN.value:
            raise CandidateEngineError(
                "CANDIDATE_EXTRACTION_FAILED",
                "Only unknown candidates may omit a proposed event type.",
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateEvidence:
    evidence_id: str
    candidate_id: str
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
class CandidateExtractionResult:
    run: ExtractionRun
    candidates: list[CandidateMemory]
    created: bool
    reused: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction_run_id": self.run.extraction_run_id,
            "source_id": self.run.source_id,
            "created": self.created,
            "reused": self.reused,
            "status": self.run.status,
            "candidate_count": self.run.candidate_count,
            "epistemic_counts": {
                "explicit": self.run.explicit_count,
                "derived": self.run.derived_count,
                "inferred": self.run.inferred_count,
                "unknown": self.run.unknown_count,
            },
            "duplicate_count": self.run.duplicate_count,
            "candidate_manifest_hash_sha256": self.run.candidate_manifest_hash_sha256,
            "candidate_ids": [candidate.candidate_id for candidate in self.candidates],
            "candidate_schema_revision": CANDIDATE_SCHEMA_REVISION,
            "candidate_extractor_revision": self.run.candidate_extractor_revision,
            "candidate_rule_revision": self.run.candidate_rule_revision,
            "epistemic_policy_revision": self.run.epistemic_policy_revision,
            "admitted_event_count": 0,
        }


@dataclass(frozen=True)
class CandidateIntegrityResult:
    extraction_run_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractionRunPage:
    items: list[ExtractionRun]
    next_cursor: str | None


@dataclass(frozen=True)
class CandidatePage:
    items: list[CandidateMemory]
    next_cursor: str | None


class CandidateEngineError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


__all__ = [
    "CANDIDATE_CLAIM_SPLITTER_REVISION",
    "ADMISSION_COMPATIBLE_CANDIDATE_MANIFEST_REVISION",
    "CANDIDATE_EXTRACTOR_REVISION",
    "CANDIDATE_MANIFEST_REVISION",
    "CANDIDATE_RULE_REVISION",
    "CANDIDATE_SCHEMA_REVISION",
    "EPISTEMIC_POLICY_REVISION",
    "CandidateEngineError",
    "CandidateEvidence",
    "CandidateExtractionPolicy",
    "CandidateExtractionResult",
    "CandidateIntegrityResult",
    "CandidateMemory",
    "CandidatePage",
    "CandidateStatus",
    "ClaimSpan",
    "EpistemicStatus",
    "EvidenceRole",
    "ExtractionMethod",
    "ExtractionRun",
    "ExtractionRunPage",
    "ExtractionRunStatus",
]
