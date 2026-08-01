"""Versioned conservative admission policies."""

from __future__ import annotations

from dataclasses import dataclass

from .admission_models import ADMISSION_POLICY_REVISION, MemoryAdmissionError
from .candidate_models import CandidateMemory


MANUAL_STRICT_V1 = "manual_strict_v1"
SAFE_EXPLICIT_AUTO_V1 = "safe_explicit_auto_v1"


@dataclass(frozen=True)
class MemoryAdmissionPolicy:
    policy_id: str
    automatic: bool
    minimum_extraction_confidence: float = 0.95
    allow_derived_operators: tuple[str, ...] = ("state_transition_v1",)
    admission_policy_revision: str = ADMISSION_POLICY_REVISION

    def validate(self) -> None:
        if self.policy_id not in {MANUAL_STRICT_V1, SAFE_EXPLICIT_AUTO_V1}:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Admission policy is not supported.")
        if not 0 <= self.minimum_extraction_confidence <= 1:
            raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Admission confidence threshold is invalid.")

    def auto_eligible(self, candidate: CandidateMemory, *, source_retention: str) -> tuple[bool, str]:
        self.validate()
        if not self.automatic:
            return False, "manual_policy_requires_explicit_decision"
        if source_retention != "standard":
            return False, "source_retention_not_standard"
        if candidate.candidate_status != "pending_review":
            return False, "candidate_not_pending"
        if candidate.extraction_confidence < self.minimum_extraction_confidence:
            return False, "extraction_confidence_below_policy_threshold"
        if candidate.proposed_event_type is None or not candidate.proposed_signal.strip():
            return False, "candidate_event_material_incomplete"
        if candidate.normalisation_details.get("reported_statement"):
            return False, "quoted_statement_requires_manual_review"
        if candidate.epistemic_status in {"inferred", "unknown"}:
            return False, "epistemic_status_requires_manual_review"
        if candidate.epistemic_status == "explicit":
            if candidate.extraction_method not in {"structured_field", "explicit_label"}:
                return False, "explicit_extraction_method_not_allowlisted"
            return True, "safe_explicit_allowlist"
        if candidate.epistemic_status == "derived":
            if candidate.extraction_method != "deterministic_derivation":
                return False, "derived_extraction_method_not_allowlisted"
            if candidate.normalisation_details.get("derivation_operator") not in self.allow_derived_operators:
                return False, "derivation_operator_not_allowlisted"
            return True, "safe_derived_allowlist"
        return False, "epistemic_status_not_supported"


def admission_policy(policy_id: str) -> MemoryAdmissionPolicy:
    if policy_id == MANUAL_STRICT_V1:
        return MemoryAdmissionPolicy(policy_id=policy_id, automatic=False)
    if policy_id == SAFE_EXPLICIT_AUTO_V1:
        return MemoryAdmissionPolicy(policy_id=policy_id, automatic=True)
    raise MemoryAdmissionError("ADMISSION_POLICY_INVALID", "Admission policy is not supported.")


__all__ = [
    "MANUAL_STRICT_V1",
    "SAFE_EXPLICIT_AUTO_V1",
    "MemoryAdmissionPolicy",
    "admission_policy",
]
