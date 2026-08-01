"""Typed contracts for bounded, evidence-backed interpretation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


INTERPRETATION_SCHEMA_REVISION = "information_interpretation_v1"
INTERPRETATION_REQUEST_REVISION = "interpretation_request_v1"
INTERPRETATION_POLICY_REVISION = "interpretation_policy_v1"
INTERPRETATION_CHUNKING_REVISION = "interpretation_chunking_v1"
INTERPRETATION_PROVIDER_CONTRACT_REVISION = "interpretation_provider_contract_v1"
INTERPRETATION_OUTPUT_VALIDATION_REVISION = "interpretation_output_validation_v1"
INTERPRETATION_EVIDENCE_VALIDATION_REVISION = "interpretation_evidence_validation_v1"
INTERPRETATION_INTEGRITY_REVISION = "interpretation_integrity_v1"


class InterpretationMode(str, Enum):
    DETERMINISTIC_ONLY_V1 = "deterministic_only_v1"
    MODEL_ASSISTED_REVIEW_V1 = "model_assisted_review_v1"
    RECORDED_RESPONSE_REPLAY_V1 = "recorded_response_replay_v1"


class InterpretationDataPolicyId(str, Enum):
    INTERNAL_RECORDED_ONLY_V1 = "internal_recorded_only_v1"
    EXTERNAL_SANITISED_REVIEW_V1 = "external_sanitised_review_v1"


class ProcessingPermission(str, Enum):
    INTERNAL_ONLY = "internal_only"
    EXTERNAL_PROCESSING_ALLOWED = "external_processing_allowed"
    EXTERNAL_PROCESSING_BLOCKED = "external_processing_blocked"
    REQUIRES_REVIEW = "requires_review"


class ProposalType(str, Enum):
    CANDIDATE_MEMORY = "candidate_memory"
    ENTITY_CANDIDATE = "entity_candidate"
    RELATIONSHIP_CANDIDATE = "relationship_candidate"
    CANONICAL_SIGNAL_PROPOSAL = "canonical_signal_proposal"
    UNKNOWN_RESULT = "unknown_result"


@dataclass(frozen=True)
class EvidenceReference:
    source_id: str
    segment_id: str
    segment_start_offset: int
    segment_end_offset: int
    source_start_offset: int | None
    source_end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None
    exact_quote_hash: str
    segment_content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterpretationOutputItem:
    proposal_type: str
    epistemic_status: str
    extraction_confidence: float
    confidence_basis: str
    evidence_references: tuple[EvidenceReference, ...]
    uncertainty_flags: tuple[str, ...] = ()
    concise_justification: str = ""
    proposed_event_type: str | None = None
    proposed_signal: str | None = None
    proposed_entity_type: str | None = None
    proposed_entity_label: str | None = None
    proposed_subject_reference: str | None = None
    proposed_relationship_type: str | None = None
    proposed_object_reference: str | None = None
    proposed_canonical_signal: str | None = None
    original_signal: str | None = None
    unknown_reason: str | None = None
    derivation_operator: str | None = None
    quoted_claim: bool = False
    attribution: str | None = None
    negated: bool = False
    future_or_hypothetical: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_references"] = [
            item.to_dict() for item in self.evidence_references
        ]
        return payload


@dataclass(frozen=True)
class InterpretationChunk:
    chunk_id: str
    ordered_segment_ids: tuple[str, ...]
    overlap_segment_ids: tuple[str, ...]
    first_segment_index: int
    last_segment_index: int
    character_count: int
    source_start_offset: int | None
    source_end_offset: int | None
    chunk_hash_sha256: str
    chunking_revision: str = INTERPRETATION_CHUNKING_REVISION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ordered_segment_ids"] = list(self.ordered_segment_ids)
        payload["overlap_segment_ids"] = list(self.overlap_segment_ids)
        return payload


@dataclass(frozen=True)
class InterpretationChunkPlan:
    chunk_plan_id: str
    source_id: str
    chunks: tuple[InterpretationChunk, ...]
    selected_segment_ids: tuple[str, ...]
    segment_manifest_hash_sha256: str
    chunk_plan_hash_sha256: str
    chunking_revision: str = INTERPRETATION_CHUNKING_REVISION

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "chunks": [item.to_dict() for item in self.chunks],
            "selected_segment_ids": list(self.selected_segment_ids),
        }


@dataclass(frozen=True)
class InterpretationRequest:
    interpretation_request_id: str
    source_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: tuple[str, ...]
    session_reference: str | None
    interpretation_mode: str
    interpretation_policy_id: str
    data_policy_id: str
    provider_id: str
    model_id: str
    model_revision: str
    requested_output_types: tuple[str, ...]
    source_content_hash_sha256: str
    source_segment_manifest_hash_sha256: str
    selected_segment_ids: tuple[str, ...]
    segment_selection_manifest_hash: str
    chunk_plan_id: str
    prompt_template_id: str
    prompt_template_hash_sha256: str
    request_fingerprint_sha256: str
    request_status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("entity_references", "requested_output_types", "selected_segment_ids"):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True)
class InterpretationAttempt:
    interpretation_attempt_id: str
    interpretation_request_id: str
    attempt_number: int
    provider_id: str
    model_id: str
    model_revision: str
    provider_request_id: str | None
    seed: int | None
    temperature: float | None
    structured_output_enabled: bool
    attempt_status: str
    input_character_count: int
    input_segment_count: int
    output_item_count: int
    started_at: str
    completed_at: str | None
    duration_ms: float
    provider_error_code: str | None
    response_record_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterpretationResponseRecord:
    interpretation_response_record_id: str
    interpretation_attempt_id: str
    provider_id: str
    model_id: str
    model_revision: str
    validated_structured_output: tuple[InterpretationOutputItem, ...]
    provider_response_hash_sha256: str
    validated_output_hash_sha256: str
    validation_status: str
    rejected_output_count: int
    accepted_proposal_count: int
    schema_error_count: int
    evidence_error_count: int
    scope_error_count: int
    secret_redaction_count: int
    interpretation_schema_revision: str
    interpretation_output_validation_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "validated_structured_output": [
                item.to_dict() for item in self.validated_structured_output
            ],
        }


@dataclass(frozen=True)
class InterpretationUnknownResult:
    unknown_result_id: str
    interpretation_response_record_id: str
    source_id: str
    segment_ids: tuple[str, ...]
    unknown_type: str
    unknown_reason: str
    evidence_manifest_hash: str
    uncertainty_flags: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["segment_ids"] = list(self.segment_ids)
        payload["uncertainty_flags"] = list(self.uncertainty_flags)
        return payload


@dataclass(frozen=True)
class InterpretationValidationFailure:
    validation_failure_id: str
    interpretation_attempt_id: str
    proposal_index: int
    failure_code: str
    safe_detail: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterpretationProviderRequest:
    interpretation_request_id: str
    chunks: tuple[dict[str, Any], ...]
    allowed_proposal_types: tuple[str, ...]
    allowed_epistemic_statuses: tuple[str, ...]
    allowed_event_types: tuple[str, ...]
    allowed_relationship_types: tuple[str, ...]
    allowed_entity_types: tuple[str, ...]
    system_policy: str
    output_schema: dict[str, Any]


@dataclass(frozen=True)
class InterpretationProviderResponse:
    provider_request_id: str | None
    status: str
    items: tuple[dict[str, Any], ...] = ()
    error_code: str | None = None


@dataclass(frozen=True)
class InterpretationRunResult:
    request: InterpretationRequest
    attempt: InterpretationAttempt | None
    response: InterpretationResponseRecord | None
    candidate_memory_ids: tuple[str, ...] = ()
    entity_candidate_ids: tuple[str, ...] = ()
    relationship_candidate_ids: tuple[str, ...] = ()
    canonical_signal_proposal_ids: tuple[str, ...] = ()
    unknown_result_ids: tuple[str, ...] = ()
    reused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "attempt": self.attempt.to_dict() if self.attempt else None,
            "response": self.response.to_dict() if self.response else None,
            "candidate_memory_ids": list(self.candidate_memory_ids),
            "entity_candidate_ids": list(self.entity_candidate_ids),
            "relationship_candidate_ids": list(self.relationship_candidate_ids),
            "canonical_signal_proposal_ids": list(
                self.canonical_signal_proposal_ids
            ),
            "unknown_result_ids": list(self.unknown_result_ids),
            "reused": self.reused,
        }


@dataclass(frozen=True)
class InterpretationIntegrityResult:
    interpretation_request_id: str
    verified: bool
    checks: dict[str, bool]
    failures: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


class InterpretationError(RuntimeError):
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


__all__ = [name for name in globals() if not name.startswith("_")]
