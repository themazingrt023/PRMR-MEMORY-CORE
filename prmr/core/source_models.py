"""Typed models and errors for the PRMR source ledger."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


SOURCE_SCHEMA_REVISION = "source_ledger_v1"
CANONICALISATION_REVISION = "source_canonical_v1"
SEGMENTER_REVISION = "source_segmenter_v1"
SANITISATION_REVISION = "source_sanitiser_v1"


class SourceType(str, Enum):
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    CONVERSATION = "conversation"
    JSON = "json"
    TIMELINE = "timeline"
    LOG = "log"


class RetentionPolicy(str, Enum):
    STANDARD = "standard"
    EPHEMERAL = "ephemeral"


@dataclass(frozen=True)
class AuthenticatedScope:
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None = None
    actor_reference: str | None = None
    workspace_reference: str | None = None
    entity_reference: str | None = None
    session_reference: str | None = None

    def memory_boundary(self) -> tuple[str, str, str]:
        return self.client_id, self.vault_id, self.namespace


@dataclass(frozen=True)
class MaintenanceContext:
    privileged: bool = False
    scope: AuthenticatedScope | None = None


@dataclass(frozen=True)
class SourceInput:
    source_type: SourceType | str
    payload: Any
    occurred_at: str | None = None
    application_reference: str | None = None
    actor_reference: str | None = None
    workspace_reference: str | None = None
    entity_references: list[str] = field(default_factory=list)
    session_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retention_policy: RetentionPolicy | str = RetentionPolicy.STANDARD
    expires_at: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class SanitisationReport:
    redaction_count: int
    redaction_categories: dict[str, int]
    affected_segment_count: int
    null_character_count: int
    sanitisation_revision: str = SANITISATION_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_type: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_references: list[str]
    session_reference: str | None
    occurred_at: str | None
    ingested_at: str
    sanitised_payload: Any
    payload_encoding: str
    content_hash_sha256: str
    canonical_payload_hash_sha256: str
    segment_manifest_hash_sha256: str
    idempotency_key_digest: str | None
    input_fingerprint_sha256: str
    metadata: dict[str, Any]
    retention_policy: str
    expires_at: str | None
    sanitisation_report: SanitisationReport
    source_schema_revision: str
    canonicalisation_revision: str
    segmenter_revision: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sanitisation_report"] = self.sanitisation_report.to_dict()
        return payload


@dataclass(frozen=True)
class SourceSegment:
    segment_id: str
    source_id: str
    sequence_index: int
    parent_segment_id: str | None
    segment_type: str
    content: str
    content_hash_sha256: str
    start_offset: int | None
    end_offset: int | None
    start_line: int | None
    end_line: int | None
    json_pointer: str | None
    speaker: str | None
    occurred_at: str | None
    label: str | None
    metadata: dict[str, Any]
    segmenter_revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceIngestResult:
    source: SourceRecord
    created: bool
    replayed: bool
    segment_count: int
    integrity_status: str

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result = {
            "source_id": self.source.source_id,
            "created": self.created,
            "replayed": self.replayed,
            "source_type": self.source.source_type,
            "content_hash_sha256": self.source.content_hash_sha256,
            "canonical_payload_hash_sha256": self.source.canonical_payload_hash_sha256,
            "segment_manifest_hash_sha256": self.source.segment_manifest_hash_sha256,
            "segment_count": self.segment_count,
            "redaction_count": self.source.sanitisation_report.redaction_count,
            "retention_policy": self.source.retention_policy,
            "integrity_status": self.integrity_status,
            "source_schema_revision": self.source.source_schema_revision,
        }
        if include_payload:
            result["source"] = self.source.to_dict()
        return result


@dataclass(frozen=True)
class IntegrityResult:
    source_id: str
    verified: bool
    checks: dict[str, bool]
    failures: list[str]
    source_schema_revision: str
    segmenter_revision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourcePage:
    items: list[SourceRecord]
    next_cursor: str | None


@dataclass(frozen=True)
class SegmentPage:
    items: list[SourceSegment]
    next_cursor: str | None


class SourceLedgerError(RuntimeError):
    """Structured source-ledger failure with a stable, non-sensitive code."""

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


__all__ = [
    "AuthenticatedScope",
    "CANONICALISATION_REVISION",
    "IntegrityResult",
    "MaintenanceContext",
    "RetentionPolicy",
    "SANITISATION_REVISION",
    "SEGMENTER_REVISION",
    "SOURCE_SCHEMA_REVISION",
    "SanitisationReport",
    "SegmentPage",
    "SourceIngestResult",
    "SourceInput",
    "SourceLedgerError",
    "SourcePage",
    "SourceRecord",
    "SourceSegment",
    "SourceType",
]
