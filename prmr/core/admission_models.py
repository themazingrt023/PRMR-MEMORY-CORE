"""Typed models for controlled candidate-memory admission."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


ADMISSION_SCHEMA_REVISION = "memory_admission_v1"
ADMISSION_POLICY_REVISION = "memory_admission_policy_v1"
ADMISSION_BRIDGE_REVISION = "candidate_event_bridge_v1"
ADMISSION_INTEGRITY_REVISION = "memory_admission_integrity_v1"
ADMITTED_EVENT_METADATA_REVISION = "admitted_event_metadata_v1"
CANDIDATE_CORRECTION_REVISION = "candidate_correction_v1"


class AdmissionDecisionType(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    CORRECT = "correct"


class AdmissionDecisionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLAYED = "replayed"


class AdmissionDecisionActorType(str, Enum):
    ENGINE_POLICY = "engine_policy"
    HUMAN = "human"
    INTERNAL_SERVICE = "internal_service"
    TEST_RUNNER = "test_runner"


@dataclass(frozen=True)
class AdmissionDecisionActor:
    actor_type: str
    actor_reference: str

    def validate(self) -> None:
        if self.actor_type not in {item.value for item in AdmissionDecisionActorType}:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Decision actor type is invalid.")
        if not self.actor_reference.strip() or len(self.actor_reference) > 160:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Decision actor reference is invalid.")


@dataclass(frozen=True)
class MemoryAdmissionDecision:
    admission_id: str
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
    decision_type: str
    decision_status: str
    decision_actor_type: str
    decision_actor_reference: str
    decision_reason: str
    decision_metadata: dict[str, Any]
    admission_policy_id: str
    admission_policy_revision: str
    admission_schema_revision: str
    admission_bridge_revision: str
    candidate_fingerprint_sha256: str
    candidate_evidence_manifest_hash_sha256: str
    source_content_hash_sha256: str
    source_segment_manifest_hash_sha256: str
    admitted_event_id: str | None
    replacement_candidate_id: str | None
    decision_idempotency_digest: str
    decided_at: str
    completed_at: str | None
    duration_ms: float
    error_code: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdmittedMemoryLink:
    admitted_memory_link_id: str
    admission_id: str
    candidate_id: str
    extraction_run_id: str
    source_id: str
    admitted_event_id: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    epistemic_status: str
    proposed_event_type: str
    candidate_fingerprint_sha256: str
    source_content_hash_sha256: str
    evidence_manifest_hash_sha256: str
    admission_policy_revision: str
    admission_bridge_revision: str
    admitted_event_metadata_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdmissionResult:
    admission: MemoryAdmissionDecision
    admitted_memory_link: AdmittedMemoryLink | None
    admitted_event: dict[str, Any] | None
    replayed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission": self.admission.to_dict(),
            "admitted_memory_link": self.admitted_memory_link.to_dict() if self.admitted_memory_link else None,
            "admitted_event_id": self.admitted_event.get("event_id") if self.admitted_event else None,
            "replayed": self.replayed,
            "truth_status_promoted": False,
        }


@dataclass(frozen=True)
class AdmissionIntegrityResult:
    admission_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    admission_integrity_revision: str = ADMISSION_INTEGRITY_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdmissionPage:
    items: list[MemoryAdmissionDecision]
    next_cursor: str | None


@dataclass(frozen=True)
class PolicyAdmissionResult:
    policy_id: str
    inspected_count: int
    accepted_count: int
    skipped_count: int
    failed_count: int
    admitted_event_ids: list[str] = field(default_factory=list)
    skipped_candidate_ids: list[str] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryAdmissionError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


__all__ = [
    "ADMISSION_BRIDGE_REVISION",
    "ADMISSION_INTEGRITY_REVISION",
    "ADMISSION_POLICY_REVISION",
    "ADMISSION_SCHEMA_REVISION",
    "ADMITTED_EVENT_METADATA_REVISION",
    "CANDIDATE_CORRECTION_REVISION",
    "AdmissionDecisionActor",
    "AdmissionDecisionActorType",
    "AdmissionDecisionStatus",
    "AdmissionDecisionType",
    "AdmissionIntegrityResult",
    "AdmissionPage",
    "AdmissionResult",
    "AdmittedMemoryLink",
    "MemoryAdmissionDecision",
    "MemoryAdmissionError",
    "PolicyAdmissionResult",
]
