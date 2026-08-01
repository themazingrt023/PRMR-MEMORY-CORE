"""Versioned policy for bounded interpretation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .interpretation_models import (
    INTERPRETATION_POLICY_REVISION,
    InterpretationDataPolicyId,
    InterpretationError,
    ProcessingPermission,
)


@dataclass(frozen=True)
class InterpretationPolicy:
    policy_id: str = INTERPRETATION_POLICY_REVISION
    maximum_segments_per_chunk: int = 40
    maximum_characters_per_chunk: int = 20_000
    overlap_segments: int = 3
    maximum_output_items: int = 500
    allowed_derived_operators: tuple[str, ...] = ("state_transition_v1",)
    reject_secret_looking_output: bool = True
    require_exact_evidence: bool = True
    model_assisted_requires_manual_review: bool = True

    def validate(self) -> None:
        if not 1 <= self.maximum_segments_per_chunk <= 100:
            raise InterpretationError(
                "INTERPRETATION_POLICY_INVALID", "Segment chunk limit is invalid."
            )
        if not 100 <= self.maximum_characters_per_chunk <= 100_000:
            raise InterpretationError(
                "INTERPRETATION_POLICY_INVALID", "Character chunk limit is invalid."
            )
        if not 0 <= self.overlap_segments < self.maximum_segments_per_chunk:
            raise InterpretationError(
                "INTERPRETATION_POLICY_INVALID", "Chunk overlap is invalid."
            )


@dataclass(frozen=True)
class InterpretationDataPolicy:
    data_policy_id: str = (
        InterpretationDataPolicyId.INTERNAL_RECORDED_ONLY_V1.value
    )
    blocked_sensitivity_labels: tuple[str, ...] = (
        "secret",
        "credential",
        "authentication",
        "restricted_external_processing",
    )

    def authorise(
        self,
        *,
        provider_kind: str,
        processing_permission: str,
        source_retention: str,
        source_metadata: dict[str, object],
        redaction_count: int,
    ) -> None:
        if (
            self.data_policy_id
            == InterpretationDataPolicyId.INTERNAL_RECORDED_ONLY_V1.value
        ):
            if provider_kind not in {"recorded_fixture", "null"}:
                raise InterpretationError(
                    "INTERPRETATION_DATA_POLICY_DENIED",
                    "Internal recorded policy does not permit an external provider.",
                )
            return
        if (
            self.data_policy_id
            != InterpretationDataPolicyId.EXTERNAL_SANITISED_REVIEW_V1.value
        ):
            raise InterpretationError(
                "INTERPRETATION_DATA_POLICY_DENIED",
                "Interpretation data policy is not recognised.",
            )
        if processing_permission != ProcessingPermission.EXTERNAL_PROCESSING_ALLOWED.value:
            raise InterpretationError(
                "INTERPRETATION_DATA_POLICY_DENIED",
                "Trusted policy has not permitted external processing.",
            )
        if source_retention != "standard":
            raise InterpretationError(
                "INTERPRETATION_DATA_POLICY_DENIED",
                "External processing requires standard source retention.",
            )
        sensitivity = {
            str(item).lower()
            for item in source_metadata.get("sensitivity_labels", [])
            if isinstance(item, str)
        }
        if sensitivity.intersection(self.blocked_sensitivity_labels):
            raise InterpretationError(
                "INTERPRETATION_DATA_POLICY_DENIED",
                "Source sensitivity labels block external processing.",
            )
        if redaction_count < 0:
            raise InterpretationError(
                "INTERPRETATION_DATA_POLICY_DENIED",
                "Source sanitisation state is invalid.",
            )


SECRET_PATTERN = re.compile(
    r"(?:\bprmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{8,}\b|"
    r"authorization\s*:\s*bearer\s+\S+|"
    r"postgres(?:ql)?://\S+|"
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----)",
    re.IGNORECASE,
)


def contains_secret(value: object) -> bool:
    return bool(SECRET_PATTERN.search(str(value)))


__all__ = [
    "InterpretationDataPolicy",
    "InterpretationPolicy",
    "contains_secret",
]
