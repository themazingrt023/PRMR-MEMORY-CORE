"""Versioned durable-job policy and retry classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .runtime_models import (
    JOB_RETRY_REVISION,
    RuntimeErrorClass,
    RuntimeErrorCode,
)


@dataclass(frozen=True)
class MemoryJobPolicy:
    policy_id: str = "durable_jobs_v1"
    maximum_attempts: int = 5
    initial_retry_delay_seconds: int = 2
    retry_multiplier: int = 2
    maximum_retry_delay_seconds: int = 300
    lease_duration_seconds: int = 60
    heartbeat_interval_seconds: int = 15
    stale_lease_grace_seconds: int = 10
    worker_poll_interval_seconds: float = 1.0
    maximum_payload_bytes: int = 32 * 1024
    cancellation_check_interval_seconds: int = 5
    dead_letter_on_non_retryable_error: bool = True
    revision: str = JOB_RETRY_REVISION

    def retry_delay_seconds(self, attempt_number: int) -> int:
        exponent = max(0, attempt_number - 1)
        return min(
            self.maximum_retry_delay_seconds,
            self.initial_retry_delay_seconds * (self.retry_multiplier**exponent),
        )

    def available_after_retry(self, now: str, attempt_number: int) -> str:
        parsed = datetime.fromisoformat(now.replace("Z", "+00:00"))
        value = parsed + timedelta(seconds=self.retry_delay_seconds(attempt_number))
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


RETRYABLE_CODES = {
    "POSTGRES_CONNECTION_FAILED": RuntimeErrorClass.RETRYABLE_TRANSIENT,
    "POSTGRES_TRANSACTION_FAILED": RuntimeErrorClass.RETRYABLE_TRANSIENT,
    "POSTGRES_SERIALIZATION_FAILURE": RuntimeErrorClass.RETRYABLE_SERIALIZATION,
    "POSTGRES_LOCK_TIMEOUT": RuntimeErrorClass.RETRYABLE_LOCK_TIMEOUT,
    "POSTGRES_DEADLOCK": RuntimeErrorClass.RETRYABLE_SERIALIZATION,
    "PROVIDER_TIMEOUT": RuntimeErrorClass.RETRYABLE_PROVIDER,
}

NON_RETRYABLE_PREFIXES = {
    "SOURCE_": RuntimeErrorClass.NON_RETRYABLE_VALIDATION,
    "GOVERNANCE_SCOPE": RuntimeErrorClass.NON_RETRYABLE_SCOPE,
    "GOVERNANCE_PLAN_STALE": RuntimeErrorClass.NON_RETRYABLE_POLICY,
    "MEMORY_JOB_SCOPE": RuntimeErrorClass.NON_RETRYABLE_SCOPE,
    "MEMORY_JOB_PAYLOAD": RuntimeErrorClass.NON_RETRYABLE_VALIDATION,
    "MEMORY_JOB_TYPE": RuntimeErrorClass.NON_RETRYABLE_VALIDATION,
    "RUNTIME_INTEGRITY": RuntimeErrorClass.NON_RETRYABLE_INTEGRITY,
}


def classify_runtime_error(error: BaseException) -> RuntimeErrorClass:
    if isinstance(error, RuntimeErrorCode):
        if error.code in RETRYABLE_CODES:
            return RETRYABLE_CODES[error.code]
        for prefix, classification in NON_RETRYABLE_PREFIXES.items():
            if error.code.startswith(prefix):
                return classification
    name = type(error).__name__.lower()
    message = str(error).lower()
    if "serialization" in name or "serialization" in message or "deadlock" in message:
        return RuntimeErrorClass.RETRYABLE_SERIALIZATION
    if "lock timeout" in message or "database is locked" in message:
        return RuntimeErrorClass.RETRYABLE_LOCK_TIMEOUT
    if "operationalerror" in name or "connection" in message:
        return RuntimeErrorClass.RETRYABLE_TRANSIENT
    return RuntimeErrorClass.NON_RETRYABLE_VALIDATION


def is_retryable(classification: RuntimeErrorClass | str) -> bool:
    return str(getattr(classification, "value", classification)).startswith("retryable_")


def sanitise_safe_error(error: BaseException) -> tuple[str, str]:
    code = getattr(error, "code", type(error).__name__.upper())
    detail = getattr(error, "safe_detail", "Runtime operation failed.")
    if not isinstance(detail, str) or len(detail) > 240:
        detail = "Runtime operation failed."
    return str(code)[:100], detail


__all__ = [
    "MemoryJobPolicy",
    "classify_runtime_error",
    "is_retryable",
    "sanitise_safe_error",
]
