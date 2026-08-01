"""Revisioned canonical-signal registry contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Any


CANONICAL_SIGNAL_SCHEMA_REVISION = "canonical_signal_v1"
CANONICAL_SIGNAL_REGISTRY_REVISION = "canonical_signal_registry_v1"
CANONICAL_SIGNAL_PROPOSAL_REVISION = "canonical_signal_proposal_v1"
CANONICAL_SIGNAL_DECISION_REVISION = "canonical_signal_decision_v1"
CANONICAL_SIGNAL_PROJECTION_REVISION = "canonical_signal_projection_v1"
CANONICAL_SIGNAL_MANIFEST_REVISION = "canonical_signal_manifest_v1"
SIGNAL_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class SignalIdentityMode(str, Enum):
    EXACT_SIGNAL_V1 = "exact_signal_v1"
    CANONICAL_SIGNAL_V1 = "canonical_signal_v1"


@dataclass(frozen=True)
class CanonicalSignalDefinition:
    canonical_signal_id: str
    client_id: str
    vault_id: str
    namespace: str
    canonical_signal_key: str
    display_label: str | None
    description: str | None
    signal_status: str
    originating_decision_id: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    canonical_signal_schema_revision: str
    canonical_signal_registry_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalSignalProposal:
    canonical_signal_proposal_id: str
    client_id: str
    vault_id: str
    namespace: str
    original_signal_key: str
    proposed_canonical_signal_key: str
    proposal_basis: str
    proposal_method: str
    source_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    interpretation_response_record_id: str | None
    epistemic_status: str
    proposal_confidence: float
    evidence_manifest_hash: str
    proposal_status: str
    canonical_signal_proposal_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("source_ids", "event_ids", "candidate_ids"):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True)
class CanonicalSignalDecision:
    canonical_signal_decision_id: str
    canonical_signal_proposal_id: str
    decision_type: str
    decision_actor_type: str
    decision_actor_reference: str
    decision_reason: str
    original_signal_key: str
    canonical_signal_key: str
    valid_from: str
    system_effective_at: str
    decision_idempotency_digest: str
    canonical_signal_decision_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalSignalAliasAssertion:
    signal_alias_assertion_id: str
    client_id: str
    vault_id: str
    namespace: str
    original_signal_key: str
    canonical_signal_id: str
    assertion_status: str
    assertion_basis: str
    proposal_id: str
    decision_id: str
    valid_from: str
    valid_until: str | None
    system_known_from: str
    system_known_until: str | None
    alias_fingerprint_sha256: str
    canonical_signal_projection_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventSignalProjection:
    event_signal_projection_id: str
    event_id: str
    client_id: str
    vault_id: str
    namespace: str
    original_signal_key: str
    canonical_signal_key: str
    mapping_applied: bool
    mapping_source: str
    alias_assertion_id: str | None
    mapping_decision_id: str | None
    valid_at: str
    known_at: str
    projection_revision: str
    projection_hash_sha256: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalSignalResolution:
    original_signal_key: str
    canonical_signal_key: str
    mapping_applied: bool
    alias_assertion_ids: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    mapping_chain: tuple[str, ...]
    manifest_hash_sha256: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "alias_assertion_ids",
            "mapping_decision_ids",
            "mapping_chain",
        ):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True)
class CanonicalSignalIntegrityResult:
    verified: bool
    checks: dict[str, bool]
    failures: tuple[str, ...]
    details: dict[str, Any]


class CanonicalSignalError(RuntimeError):
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


def validate_signal_key(value: str) -> str:
    key = str(value).strip()
    if not SIGNAL_KEY_PATTERN.fullmatch(key):
        raise CanonicalSignalError(
            "CANONICAL_SIGNAL_INVALID", "Signal key must be lowercase dot-separated."
        )
    return key


__all__ = [name for name in globals() if not name.startswith("_")]
