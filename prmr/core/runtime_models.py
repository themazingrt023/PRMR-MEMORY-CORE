"""Typed contracts for PRMR runtime hardening and database validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


RUNTIME_SCHEMA_REVISION = "memory_runtime_v1"
POSTGRES_VALIDATION_REVISION = "postgres_runtime_validation_v1"
REPOSITORY_PARITY_REVISION = "repository_parity_v1"
MIGRATION_VALIDATION_REVISION = "migration_validation_v1"
JOB_SCHEMA_REVISION = "durable_memory_jobs_v1"
JOB_QUEUE_REVISION = "memory_job_queue_v1"
JOB_LEASE_REVISION = "memory_job_lease_v1"
JOB_RETRY_REVISION = "memory_job_retry_v1"
JOB_HANDLER_REVISION = "memory_job_handlers_v1"
JOB_RECOVERY_REVISION = "memory_job_recovery_v1"
JOB_INTEGRITY_REVISION = "memory_job_integrity_v1"
RUNTIME_INTEGRITY_SWEEP_REVISION = "runtime_integrity_sweep_v1"
RUNTIME_PERFORMANCE_REVISION = "runtime_performance_v1"


class RuntimeErrorCode(RuntimeError):
    """Runtime failure carrying a public-safe deterministic error code."""

    def __init__(self, code: str, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


class RuntimeTransactionPolicy(str, Enum):
    READ_COMMITTED_V1 = "read_committed_v1"
    SERIALIZABLE_RETRY_V1 = "serializable_retry_v1"


class RuntimeErrorClass(str, Enum):
    RETRYABLE_TRANSIENT = "retryable_transient"
    RETRYABLE_SERIALIZATION = "retryable_serialization"
    RETRYABLE_LOCK_TIMEOUT = "retryable_lock_timeout"
    RETRYABLE_PROVIDER = "retryable_provider"
    NON_RETRYABLE_VALIDATION = "non_retryable_validation"
    NON_RETRYABLE_SCOPE = "non_retryable_scope"
    NON_RETRYABLE_INTEGRITY = "non_retryable_integrity"
    NON_RETRYABLE_POLICY = "non_retryable_policy"
    CANCELLED = "cancelled"


class MemoryJobType(str, Enum):
    SOURCE_EXPIRY_PURGE = "source_expiry_purge"
    INTERPRETATION_RUN = "interpretation_run"
    CANONICAL_PROJECTION_REFRESH = "canonical_projection_refresh"
    TEMPORAL_DYNAMICS_REFRESH = "temporal_dynamics_refresh"
    CONSOLIDATION_BUILD = "consolidation_build"
    CONSOLIDATION_REFRESH = "consolidation_refresh"
    CHECKPOINT_REFRESH = "checkpoint_refresh"
    QUERY_PRECOMPUTE = "query_precompute"
    INTEGRITY_SWEEP = "integrity_sweep"
    GOVERNANCE_EXECUTION = "governance_execution"
    GOVERNANCE_RECOVERY = "governance_recovery"
    EXPORT_GENERATION = "export_generation"
    EXPORT_EXPIRY = "export_expiry"
    DERIVED_ARTIFACT_INVALIDATION = "derived_artifact_invalidation"
    POST_ERASURE_RECOMPUTE = "post_erasure_recompute"


class MemoryJobStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RuntimeScope:
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None = None
    actor_reference: str | None = None
    workspace_reference: str | None = None
    entity_id: str | None = None
    session_reference: str | None = None

    def boundary(self) -> tuple[str, str, str]:
        return self.client_id, self.vault_id, self.namespace

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MigrationDefinition:
    migration_id: str
    sprint: str
    sqlite_path: str
    postgres_path: str
    checksum_sha256: str
    dependencies: tuple[str, ...]
    transactional: bool
    destructive: bool
    minimum_schema_state: str
    resulting_schema_state: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["dependencies"] = list(self.dependencies)
        return value


@dataclass(frozen=True)
class PostgresEnvironmentEvidence:
    status: str
    database_hint: str | None
    schema: str | None
    server_version: str | None
    transaction_support: bool
    destructive_tests_allowed: bool
    guard_verified: bool
    production_guard_absent: bool
    statement_timeout: str | None
    lock_timeout: str | None
    revision: str = POSTGRES_VALIDATION_REVISION
    safe_error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryJob:
    job_id: str
    job_type: str
    client_id: str
    vault_id: str
    namespace: str
    application_reference: str | None
    actor_reference: str | None
    workspace_reference: str | None
    entity_id: str | None
    session_reference: str | None
    target_object_type: str
    target_object_id: str
    safe_payload: dict[str, Any]
    payload_hash_sha256: str
    idempotency_key_digest: str
    job_status: str
    priority: int
    scheduled_for: str
    available_after: str
    attempt_count: int
    maximum_attempts: int
    lease_owner: str | None
    lease_token_digest: str | None
    lease_acquired_at: str | None
    lease_expires_at: str | None
    heartbeat_at: str | None
    started_at: str | None
    completed_at: str | None
    cancelled_at: str | None
    last_error_code: str | None
    result_reference_type: str | None
    result_reference_id: str | None
    parent_job_id: str | None
    correlation_id: str
    runtime_schema_revision: str = RUNTIME_SCHEMA_REVISION
    job_schema_revision: str = JOB_SCHEMA_REVISION
    job_queue_revision: str = JOB_QUEUE_REVISION
    job_lease_revision: str = JOB_LEASE_REVISION
    job_retry_revision: str = JOB_RETRY_REVISION
    job_handler_revision: str = JOB_HANDLER_REVISION
    job_recovery_revision: str = JOB_RECOVERY_REVISION
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryJobAttempt:
    job_attempt_id: str
    job_id: str
    attempt_number: int
    worker_id: str
    lease_token_digest: str
    status: str
    started_at: str
    heartbeat_at: str | None
    completed_at: str | None
    duration_ms: float | None
    handler_revision: str
    transaction_mode: str
    retryable: bool | None
    error_code: str | None
    safe_error_details: str | None
    result_reference_type: str | None
    result_reference_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryJobEvent:
    job_event_id: str
    job_id: str
    job_attempt_id: str | None
    event_type: str
    previous_status: str | None
    new_status: str
    worker_id: str | None
    safe_reason: str
    sequence_number: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LeasedMemoryJob:
    job: MemoryJob
    lease_token: str = field(repr=False)


@dataclass(frozen=True)
class MemoryJobHandlerResult:
    result_reference_type: str
    result_reference_id: str
    result_hash_sha256: str
    effect_status: str
    replayed: bool
    safe_metrics: dict[str, int | float | str | bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "JOB_HANDLER_REVISION",
    "JOB_INTEGRITY_REVISION",
    "JOB_LEASE_REVISION",
    "JOB_QUEUE_REVISION",
    "JOB_RECOVERY_REVISION",
    "JOB_RETRY_REVISION",
    "JOB_SCHEMA_REVISION",
    "LeasedMemoryJob",
    "MIGRATION_VALIDATION_REVISION",
    "MemoryJob",
    "MemoryJobAttempt",
    "MemoryJobEvent",
    "MemoryJobHandlerResult",
    "MemoryJobStatus",
    "MemoryJobType",
    "MigrationDefinition",
    "POSTGRES_VALIDATION_REVISION",
    "PostgresEnvironmentEvidence",
    "REPOSITORY_PARITY_REVISION",
    "RUNTIME_INTEGRITY_SWEEP_REVISION",
    "RUNTIME_PERFORMANCE_REVISION",
    "RUNTIME_SCHEMA_REVISION",
    "RuntimeErrorClass",
    "RuntimeErrorCode",
    "RuntimeScope",
    "RuntimeTransactionPolicy",
]
