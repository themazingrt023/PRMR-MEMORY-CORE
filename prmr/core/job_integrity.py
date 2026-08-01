"""Deterministic integrity checks for durable jobs and their history."""

from __future__ import annotations

from typing import Any

from .job_store import MemoryJobStore
from .runtime_models import (
    JOB_HANDLER_REVISION,
    JOB_INTEGRITY_REVISION,
    MemoryJobStatus,
)
from .source_integrity import canonical_json, sha256_text


TERMINAL = {
    MemoryJobStatus.COMPLETED.value,
    MemoryJobStatus.FAILED.value,
    MemoryJobStatus.DEAD_LETTER.value,
    MemoryJobStatus.CANCELLED.value,
}


def verify_job_integrity(
    store: MemoryJobStore,
    job_id: str,
    *,
    scope: tuple[str, str, str] | None = None,
) -> dict[str, Any]:
    job = store.get_job(job_id, scope=scope)
    events = store.list_events(job_id)
    attempts = store.list_attempts(job_id)
    payload_hash_valid = (
        sha256_text(canonical_json(job.safe_payload)) == job.payload_hash_sha256
    )
    sequences = [event.sequence_number for event in events]
    sequence_valid = sequences == list(range(1, len(sequences) + 1))
    attempt_numbers = [attempt.attempt_number for attempt in attempts]
    attempts_valid = (
        attempt_numbers == list(range(1, len(attempt_numbers) + 1))
        and len(attempts) == job.attempt_count
    )
    lease_valid = not (
        job.job_status in TERMINAL
        and any(
            value is not None
            for value in (
                job.lease_owner,
                job.lease_token_digest,
                job.lease_expires_at,
            )
        )
    )
    event_terminal_valid = (
        not events
        or job.job_status == events[-1].new_status
        or (
            job.job_status == MemoryJobStatus.RETRY_WAIT.value
            and events[-1].event_type in {"lease_expired", "retry_scheduled"}
        )
    )
    handlers_valid = all(
        attempt.handler_revision == JOB_HANDLER_REVISION for attempt in attempts
    )
    effect = store.get_effect(job_id)
    result_valid = (
        job.job_status != MemoryJobStatus.COMPLETED.value
        or (
            effect is not None
            and job.result_reference_type == effect["result_reference_type"]
            and job.result_reference_id == effect["result_reference_id"]
        )
    )
    checks = {
        "payload_hash": payload_hash_valid,
        "scope": all(job.to_dict().get(key) for key in ("client_id", "vault_id", "namespace")),
        "status_transitions": event_terminal_valid,
        "attempt_sequence": attempts_valid,
        "lease_ownership": lease_valid,
        "event_sequence": sequence_valid,
        "result_reference": result_valid,
        "idempotency_identity": len(job.idempotency_key_digest) == 64,
        "handler_revision": handlers_valid,
        "no_duplicate_completed_effect": effect is None or bool(effect["job_id"]),
        "retry_history": len(attempts) <= job.maximum_attempts
        or job.job_status == MemoryJobStatus.QUEUED.value,
        "cancellation_history": job.cancelled_at is None
        or job.job_status == MemoryJobStatus.CANCELLED.value,
        "dead_letter_state": job.job_status != MemoryJobStatus.DEAD_LETTER.value
        or bool(job.last_error_code),
    }
    return {
        "job_id": job_id,
        "verified": all(checks.values()),
        "checks": checks,
        "event_count": len(events),
        "attempt_count": len(attempts),
        "revision": JOB_INTEGRITY_REVISION,
    }


class MemoryJobIntegrity:
    def __init__(self, store: MemoryJobStore) -> None:
        self.store = store

    def verify_job_integrity(
        self,
        job_id: str,
        *,
        scope: tuple[str, str, str] | None = None,
    ) -> dict[str, Any]:
        return verify_job_integrity(self.store, job_id, scope=scope)


__all__ = ["MemoryJobIntegrity", "verify_job_integrity"]
