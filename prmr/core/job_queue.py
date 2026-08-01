"""Durable database-backed Memory Core job queue."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import secrets
from typing import Any

from .job_policy import MemoryJobPolicy
from .job_store import MemoryJobStore, utc_now
from .runtime_models import (
    JOB_HANDLER_REVISION,
    JOB_LEASE_REVISION,
    JOB_QUEUE_REVISION,
    JOB_RECOVERY_REVISION,
    JOB_RETRY_REVISION,
    JOB_SCHEMA_REVISION,
    RUNTIME_SCHEMA_REVISION,
    LeasedMemoryJob,
    MemoryJob,
    MemoryJobHandlerResult,
    MemoryJobStatus,
    MemoryJobType,
    RuntimeErrorCode,
    RuntimeScope,
)
from .source_integrity import canonical_json, sha256_text


LOGGER = logging.getLogger("prmr.core.runtime.jobs")
FORBIDDEN_PAYLOAD_KEYS = {
    "api_key",
    "authorization",
    "content",
    "database_url",
    "evidence_text",
    "event_content",
    "password",
    "raw_source",
    "secret",
    "signal",
    "source_content",
    "source_text",
    "token",
}


def _plus_seconds(value: str, seconds: float) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


class MemoryJobQueue:
    def __init__(
        self,
        repository: Any,
        *,
        policy: MemoryJobPolicy | None = None,
        initialize: bool = True,
    ) -> None:
        self.repository = repository
        self.store = MemoryJobStore(repository, initialize=initialize)
        self.policy = policy or MemoryJobPolicy()
        self.postgres = self.store.postgres
        self.p = self.store.p

    def enqueue(
        self,
        scope: RuntimeScope,
        *,
        job_type: str,
        target_object_type: str,
        target_object_id: str,
        safe_payload: dict[str, Any],
        idempotency_key: str,
        priority: int = 0,
        scheduled_for: str | None = None,
        maximum_attempts: int | None = None,
        parent_job_id: str | None = None,
        correlation_id: str | None = None,
        created_at: str | None = None,
    ) -> MemoryJob:
        self._validate_type(job_type)
        self._validate_payload(safe_payload)
        if not target_object_type or not target_object_id or not idempotency_key:
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID",
                "Job target and idempotency key are required.",
            )
        now = created_at or utc_now()
        scheduled = scheduled_for or now
        payload_hash = sha256_text(canonical_json(safe_payload))
        idempotency_digest = sha256_text(idempotency_key)
        identity = {
            "scope": scope.boundary(),
            "job_type": job_type,
            "target_type": target_object_type,
            "target_id": target_object_id,
            "idempotency": idempotency_digest,
            "queue_revision": JOB_QUEUE_REVISION,
        }
        identity_digest = sha256_text(canonical_json(identity))
        job_id = f"mjob_{identity_digest[:24]}"
        existing = self.store.find_identity(
            scope.boundary(),
            job_type,
            target_object_type,
            target_object_id,
            idempotency_digest,
        )
        if existing:
            if existing.payload_hash_sha256 != payload_hash:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_IDEMPOTENCY_CONFLICT",
                    "Existing job identity has different safe payload material.",
                )
            return existing
        maximum = maximum_attempts or self.policy.maximum_attempts
        if maximum <= 0:
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID", "Maximum attempts must be positive."
            )
        job = MemoryJob(
            job_id=job_id,
            job_type=job_type,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            application_reference=scope.application_reference,
            actor_reference=scope.actor_reference,
            workspace_reference=scope.workspace_reference,
            entity_id=scope.entity_id,
            session_reference=scope.session_reference,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            safe_payload=dict(safe_payload),
            payload_hash_sha256=payload_hash,
            idempotency_key_digest=idempotency_digest,
            job_status=MemoryJobStatus.QUEUED.value,
            priority=int(priority),
            scheduled_for=scheduled,
            available_after=scheduled,
            attempt_count=0,
            maximum_attempts=maximum,
            lease_owner=None,
            lease_token_digest=None,
            lease_acquired_at=None,
            lease_expires_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            cancelled_at=None,
            last_error_code=None,
            result_reference_type=None,
            result_reference_id=None,
            parent_job_id=parent_job_id,
            correlation_id=correlation_id or f"corr_{identity_digest[24:48]}",
            runtime_schema_revision=RUNTIME_SCHEMA_REVISION,
            job_schema_revision=JOB_SCHEMA_REVISION,
            job_queue_revision=JOB_QUEUE_REVISION,
            job_lease_revision=JOB_LEASE_REVISION,
            job_retry_revision=JOB_RETRY_REVISION,
            job_handler_revision=JOB_HANDLER_REVISION,
            job_recovery_revision=JOB_RECOVERY_REVISION,
            created_at=now,
            updated_at=now,
        )
        self.store.insert_job(job)
        with self.repository.connect() as connection:
            self.store.append_event(
                connection,
                job_id=job_id,
                event_type="created",
                previous_status=None,
                new_status=MemoryJobStatus.QUEUED.value,
                safe_reason="Job created.",
                created_at=now,
            )
            if parent_job_id:
                connection.execute(
                    f"INSERT INTO {self.store.tables['dependencies']}"
                    f"(parent_job_id,child_job_id,dependency_status,created_at) "
                    f"VALUES({','.join([self.p]*4)})",
                    (parent_job_id, job_id, "required", now),
                )
        LOGGER.info(
            "memory_job_enqueued",
            extra={"job_id": job_id, "job_type": job_type, "status": "queued"},
        )
        return job

    def lease_next_job(
        self, worker_id: str, *, now: str | None = None
    ) -> LeasedMemoryJob | None:
        captured = now or utc_now()
        lease_token = secrets.token_urlsafe(32)
        lease_digest = sha256_text(lease_token)
        lease_expires = _plus_seconds(captured, self.policy.lease_duration_seconds)
        with self.repository.connect() as connection:
            if not self.postgres:
                connection.execute("BEGIN IMMEDIATE")
            query = (
                f"SELECT j.* FROM {self.store.tables['jobs']} j "
                f"WHERE j.job_status IN ({self.p},{self.p}) "
                f"AND j.available_after<={self.p} AND j.scheduled_for<={self.p} "
                "AND NOT EXISTS ("
                f"SELECT 1 FROM {self.store.tables['dependencies']} d "
                f"JOIN {self.store.tables['jobs']} pjob ON pjob.job_id=d.parent_job_id "
                "WHERE d.child_job_id=j.job_id AND pjob.job_status<>"
                f"{self.p}) "
                "ORDER BY j.priority DESC,j.available_after ASC,j.created_at ASC,j.job_id ASC "
                "LIMIT 1"
            )
            if self.postgres:
                query += " FOR UPDATE SKIP LOCKED"
            row = connection.execute(
                query,
                (
                    MemoryJobStatus.QUEUED.value,
                    MemoryJobStatus.RETRY_WAIT.value,
                    captured,
                    captured,
                    MemoryJobStatus.COMPLETED.value,
                ),
            ).fetchone()
            if not row:
                return None
            job = self.store.job_from_row(row)
            changed = self.store.update_job(
                connection,
                job.job_id,
                {
                    "job_status": MemoryJobStatus.LEASED.value,
                    "lease_owner": worker_id,
                    "lease_token_digest": lease_digest,
                    "lease_acquired_at": captured,
                    "lease_expires_at": lease_expires,
                    "heartbeat_at": captured,
                    "attempt_count": job.attempt_count + 1,
                    "updated_at": captured,
                },
                allowed_statuses=(
                    MemoryJobStatus.QUEUED.value,
                    MemoryJobStatus.RETRY_WAIT.value,
                ),
            )
            if changed != 1:
                return None
            self.store.append_event(
                connection,
                job_id=job.job_id,
                event_type="leased",
                previous_status=job.job_status,
                new_status=MemoryJobStatus.LEASED.value,
                worker_id=worker_id,
                safe_reason="Lease acquired.",
                created_at=captured,
            )
            leased = replace(
                job,
                job_status=MemoryJobStatus.LEASED.value,
                lease_owner=worker_id,
                lease_token_digest=lease_digest,
                lease_acquired_at=captured,
                lease_expires_at=lease_expires,
                heartbeat_at=captured,
                attempt_count=job.attempt_count + 1,
                updated_at=captured,
            )
        LOGGER.info(
            "memory_job_leased",
            extra={"job_id": leased.job_id, "worker_id": worker_id},
        )
        return LeasedMemoryJob(leased, lease_token)

    def start_job(
        self,
        leased: LeasedMemoryJob,
        *,
        worker_id: str,
        transaction_mode: str,
        now: str | None = None,
    ) -> tuple[MemoryJob, str]:
        captured = now or utc_now()
        digest = sha256_text(leased.lease_token)
        with self.repository.connect() as connection:
            current = self.store.get_job(
                leased.job.job_id,
                connection=connection,
            )
            self._assert_lease(current, worker_id, digest)
            attempt = self.store.create_attempt(
                connection,
                current,
                worker_id=worker_id,
                lease_token_digest=digest,
                transaction_mode=transaction_mode,
                now=captured,
            )
            changed = self.store.update_job(
                connection,
                current.job_id,
                {
                    "job_status": MemoryJobStatus.RUNNING.value,
                    "started_at": current.started_at or captured,
                    "heartbeat_at": captured,
                    "updated_at": captured,
                },
                lease_owner=worker_id,
                lease_token_digest=digest,
                allowed_statuses=(MemoryJobStatus.LEASED.value,),
            )
            if changed != 1:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_LEASE_LOST", "Worker no longer owns the job lease."
                )
            self.store.append_event(
                connection,
                job_id=current.job_id,
                job_attempt_id=attempt.job_attempt_id,
                event_type="started",
                previous_status=MemoryJobStatus.LEASED.value,
                new_status=MemoryJobStatus.RUNNING.value,
                worker_id=worker_id,
                safe_reason="Handler started.",
                created_at=captured,
            )
        return (
            replace(
                current,
                job_status=MemoryJobStatus.RUNNING.value,
                started_at=current.started_at or captured,
                heartbeat_at=captured,
                updated_at=captured,
            ),
            attempt.job_attempt_id,
        )

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_token: str,
        attempt_id: str | None = None,
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        digest = sha256_text(lease_token)
        expires = _plus_seconds(captured, self.policy.lease_duration_seconds)
        with self.repository.connect() as connection:
            current = self.store.get_job(job_id, connection=connection)
            self._assert_lease(current, worker_id, digest)
            changed = self.store.update_job(
                connection,
                job_id,
                {
                    "heartbeat_at": captured,
                    "lease_expires_at": expires,
                    "updated_at": captured,
                },
                lease_owner=worker_id,
                lease_token_digest=digest,
                allowed_statuses=(
                    MemoryJobStatus.LEASED.value,
                    MemoryJobStatus.RUNNING.value,
                    MemoryJobStatus.CANCEL_REQUESTED.value,
                ),
            )
            if changed != 1:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_HEARTBEAT_FAILED", "Job heartbeat was rejected."
                )
            if attempt_id:
                connection.execute(
                    f"UPDATE {self.store.tables['attempts']} SET heartbeat_at={self.p} "
                    f"WHERE job_attempt_id={self.p} AND lease_token_digest={self.p}",
                    (captured, attempt_id, digest),
                )
            self.store.append_event(
                connection,
                job_id=job_id,
                job_attempt_id=attempt_id,
                event_type="heartbeat",
                previous_status=current.job_status,
                new_status=current.job_status,
                worker_id=worker_id,
                safe_reason="Lease heartbeat accepted.",
                created_at=captured,
            )
        return replace(
            current,
            heartbeat_at=captured,
            lease_expires_at=expires,
            updated_at=captured,
        )

    def commit_effect_receipt(
        self,
        job: MemoryJob,
        *,
        worker_id: str,
        lease_token: str,
        result: MemoryJobHandlerResult,
        now: str | None = None,
    ) -> None:
        """Persist replay evidence before final job completion."""

        captured = now or utc_now()
        digest = sha256_text(lease_token)
        with self.repository.connect() as connection:
            current = self.store.get_job(job.job_id, connection=connection)
            self._assert_lease(current, worker_id, digest)
            self.store.record_effect(
                connection,
                current,
                result_reference_type=result.result_reference_type,
                result_reference_id=result.result_reference_id,
                result_hash_sha256=result.result_hash_sha256,
                effect_status=result.effect_status,
                committed_at=captured,
            )

    def complete(
        self,
        job: MemoryJob,
        *,
        worker_id: str,
        lease_token: str,
        attempt_id: str,
        result: MemoryJobHandlerResult,
        duration_ms: float,
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        digest = sha256_text(lease_token)
        with self.repository.connect() as connection:
            current = self.store.get_job(job.job_id, connection=connection)
            self._assert_lease(current, worker_id, digest)
            self.store.record_effect(
                connection,
                current,
                result_reference_type=result.result_reference_type,
                result_reference_id=result.result_reference_id,
                result_hash_sha256=result.result_hash_sha256,
                effect_status=result.effect_status,
                committed_at=captured,
            )
            changed = self.store.update_job(
                connection,
                current.job_id,
                {
                    "job_status": MemoryJobStatus.COMPLETED.value,
                    "completed_at": captured,
                    "result_reference_type": result.result_reference_type,
                    "result_reference_id": result.result_reference_id,
                    "lease_owner": None,
                    "lease_token_digest": None,
                    "lease_acquired_at": None,
                    "lease_expires_at": None,
                    "heartbeat_at": captured,
                    "last_error_code": None,
                    "updated_at": captured,
                },
                lease_owner=worker_id,
                lease_token_digest=digest,
                allowed_statuses=(
                    MemoryJobStatus.RUNNING.value,
                    MemoryJobStatus.CANCEL_REQUESTED.value,
                ),
            )
            if changed != 1:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_LEASE_LOST", "Stale worker cannot complete this job."
                )
            self.store.finish_attempt(
                connection,
                attempt_id,
                status="completed",
                completed_at=captured,
                duration_ms=duration_ms,
                retryable=False,
                error_code=None,
                safe_error_details=None,
                result_reference_type=result.result_reference_type,
                result_reference_id=result.result_reference_id,
            )
            self.store.append_event(
                connection,
                job_id=current.job_id,
                job_attempt_id=attempt_id,
                event_type="completed",
                previous_status=current.job_status,
                new_status=MemoryJobStatus.COMPLETED.value,
                worker_id=worker_id,
                safe_reason="Authoritative effect verified and job completed.",
                created_at=captured,
            )
        return self.store.get_job(job.job_id)

    def fail(
        self,
        job: MemoryJob,
        *,
        worker_id: str,
        lease_token: str,
        attempt_id: str,
        error_code: str,
        safe_error_details: str,
        retryable: bool,
        duration_ms: float,
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        digest = sha256_text(lease_token)
        exhausted = job.attempt_count >= job.maximum_attempts
        if retryable and not exhausted:
            new_status = MemoryJobStatus.RETRY_WAIT.value
            available_after = self.policy.available_after_retry(
                captured, job.attempt_count
            )
            event_type = "retry_scheduled"
        else:
            new_status = (
                MemoryJobStatus.DEAD_LETTER.value
                if self.policy.dead_letter_on_non_retryable_error or exhausted
                else MemoryJobStatus.FAILED.value
            )
            available_after = captured
            event_type = (
                "dead_lettered"
                if new_status == MemoryJobStatus.DEAD_LETTER.value
                else "failed"
            )
        with self.repository.connect() as connection:
            current = self.store.get_job(job.job_id, connection=connection)
            self._assert_lease(current, worker_id, digest)
            changed = self.store.update_job(
                connection,
                current.job_id,
                {
                    "job_status": new_status,
                    "available_after": available_after,
                    "last_error_code": error_code,
                    "lease_owner": None,
                    "lease_token_digest": None,
                    "lease_acquired_at": None,
                    "lease_expires_at": None,
                    "updated_at": captured,
                },
                lease_owner=worker_id,
                lease_token_digest=digest,
                allowed_statuses=(
                    MemoryJobStatus.RUNNING.value,
                    MemoryJobStatus.LEASED.value,
                    MemoryJobStatus.CANCEL_REQUESTED.value,
                ),
            )
            if changed != 1:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_LEASE_LOST", "Stale worker cannot fail this job."
                )
            self.store.finish_attempt(
                connection,
                attempt_id,
                status=new_status,
                completed_at=captured,
                duration_ms=duration_ms,
                retryable=retryable,
                error_code=error_code,
                safe_error_details=safe_error_details[:240],
                result_reference_type=None,
                result_reference_id=None,
            )
            self.store.append_event(
                connection,
                job_id=current.job_id,
                job_attempt_id=attempt_id,
                event_type=event_type,
                previous_status=current.job_status,
                new_status=new_status,
                worker_id=worker_id,
                safe_reason=safe_error_details,
                created_at=captured,
            )
        return self.store.get_job(job.job_id)

    def cancel_running(
        self,
        job: MemoryJob,
        *,
        worker_id: str,
        lease_token: str,
        attempt_id: str,
        reason: str,
        duration_ms: float,
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        digest = sha256_text(lease_token)
        with self.repository.connect() as connection:
            current = self.store.get_job(job.job_id, connection=connection)
            self._assert_lease(current, worker_id, digest)
            effect = connection.execute(
                f"SELECT job_id FROM {self.store.tables['effects']} "
                f"WHERE job_id={self.p}",
                (job.job_id,),
            ).fetchone()
            if effect:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_RESULT_INVALID",
                    "Cancellation cannot undo an already committed effect.",
                )
            changed = self.store.update_job(
                connection,
                current.job_id,
                {
                    "job_status": MemoryJobStatus.CANCELLED.value,
                    "cancelled_at": captured,
                    "lease_owner": None,
                    "lease_token_digest": None,
                    "lease_acquired_at": None,
                    "lease_expires_at": None,
                    "updated_at": captured,
                },
                lease_owner=worker_id,
                lease_token_digest=digest,
                allowed_statuses=(
                    MemoryJobStatus.RUNNING.value,
                    MemoryJobStatus.CANCEL_REQUESTED.value,
                ),
            )
            if changed != 1:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_LEASE_LOST", "Stale worker cannot cancel this job."
                )
            self.store.finish_attempt(
                connection,
                attempt_id,
                status=MemoryJobStatus.CANCELLED.value,
                completed_at=captured,
                duration_ms=duration_ms,
                retryable=False,
                error_code="MEMORY_JOB_CANCELLED",
                safe_error_details=reason[:240],
                result_reference_type=None,
                result_reference_id=None,
            )
            self.store.append_event(
                connection,
                job_id=current.job_id,
                job_attempt_id=attempt_id,
                event_type="cancelled",
                previous_status=current.job_status,
                new_status=MemoryJobStatus.CANCELLED.value,
                worker_id=worker_id,
                safe_reason=reason[:240],
                created_at=captured,
            )
        return self.store.get_job(job.job_id)

    def request_cancellation(
        self,
        scope: RuntimeScope,
        job_id: str,
        *,
        reason: str = "Cancellation requested.",
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        with self.repository.connect() as connection:
            current = self.store.get_job(
                job_id, scope=scope.boundary(), connection=connection
            )
            if current.job_status in {
                MemoryJobStatus.QUEUED.value,
                MemoryJobStatus.RETRY_WAIT.value,
            }:
                new_status = MemoryJobStatus.CANCELLED.value
                event_type = "cancelled"
                cancelled_at = captured
            elif current.job_status in {
                MemoryJobStatus.LEASED.value,
                MemoryJobStatus.RUNNING.value,
            }:
                new_status = MemoryJobStatus.CANCEL_REQUESTED.value
                event_type = "cancel_requested"
                cancelled_at = None
            else:
                return current
            self.store.update_job(
                connection,
                current.job_id,
                {
                    "job_status": new_status,
                    "cancelled_at": cancelled_at,
                    "updated_at": captured,
                },
                allowed_statuses=(current.job_status,),
            )
            self.store.append_event(
                connection,
                job_id=current.job_id,
                event_type=event_type,
                previous_status=current.job_status,
                new_status=new_status,
                safe_reason=reason[:240],
                created_at=captured,
            )
        return self.store.get_job(job_id, scope=scope.boundary())

    def recover_expired_leases(self, *, now: str | None = None) -> list[str]:
        captured = now or utc_now()
        recovered: list[str] = []
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.store.tables['jobs']} WHERE "
                f"job_status IN ({self.p},{self.p},{self.p}) "
                f"AND lease_expires_at IS NOT NULL AND lease_expires_at<{self.p} "
                "ORDER BY lease_expires_at,job_id",
                (
                    MemoryJobStatus.LEASED.value,
                    MemoryJobStatus.RUNNING.value,
                    MemoryJobStatus.CANCEL_REQUESTED.value,
                    captured,
                ),
            ).fetchall()
            for row in rows:
                job = self.store.job_from_row(row)
                if job.job_status == MemoryJobStatus.CANCEL_REQUESTED.value:
                    status = MemoryJobStatus.CANCELLED.value
                    event_type = "cancelled"
                else:
                    status = (
                        MemoryJobStatus.RETRY_WAIT.value
                        if job.attempt_count < job.maximum_attempts
                        else MemoryJobStatus.DEAD_LETTER.value
                    )
                    event_type = "lease_expired"
                changed = self.store.update_job(
                    connection,
                    job.job_id,
                    {
                        "job_status": status,
                        "available_after": captured,
                        "lease_owner": None,
                        "lease_token_digest": None,
                        "lease_acquired_at": None,
                        "lease_expires_at": None,
                        "cancelled_at": captured
                        if status == MemoryJobStatus.CANCELLED.value
                        else None,
                        "last_error_code": "MEMORY_JOB_LEASE_LOST",
                        "updated_at": captured,
                    },
                    allowed_statuses=(job.job_status,),
                )
                if changed:
                    attempt_row = connection.execute(
                        f"SELECT job_attempt_id FROM {self.store.tables['attempts']} "
                        f"WHERE job_id={self.p} AND attempt_number={self.p} "
                        f"AND status={self.p}",
                        (job.job_id, job.attempt_count, "running"),
                    ).fetchone()
                    if attempt_row:
                        self.store.finish_attempt(
                            connection,
                            str(attempt_row["job_attempt_id"]),
                            status="failed",
                            completed_at=captured,
                            duration_ms=0.0,
                            retryable=(status == MemoryJobStatus.RETRY_WAIT.value),
                            error_code="MEMORY_JOB_LEASE_LOST",
                            safe_error_details="Expired lease recovered.",
                            result_reference_type=None,
                            result_reference_id=None,
                        )
                    self.store.append_event(
                        connection,
                        job_id=job.job_id,
                        event_type=event_type,
                        previous_status=job.job_status,
                        new_status=status,
                        safe_reason="Expired lease recovered.",
                        created_at=captured,
                    )
                    recovered.append(job.job_id)
        return recovered

    def replay_dead_letter(
        self,
        scope: RuntimeScope,
        job_id: str,
        *,
        reason: str = "Explicit internal dead-letter replay.",
        now: str | None = None,
    ) -> MemoryJob:
        captured = now or utc_now()
        with self.repository.connect() as connection:
            current = self.store.get_job(
                job_id, scope=scope.boundary(), connection=connection
            )
            if current.job_status != MemoryJobStatus.DEAD_LETTER.value:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_DEAD_LETTERED",
                    "Only a dead-letter job may be explicitly replayed.",
                )
            self.store.update_job(
                connection,
                job_id,
                {
                    "job_status": MemoryJobStatus.QUEUED.value,
                    "maximum_attempts": current.maximum_attempts
                    + self.policy.maximum_attempts,
                    "available_after": captured,
                    "last_error_code": None,
                    "updated_at": captured,
                },
                allowed_statuses=(MemoryJobStatus.DEAD_LETTER.value,),
            )
            self.store.append_event(
                connection,
                job_id=job_id,
                event_type="replayed",
                previous_status=MemoryJobStatus.DEAD_LETTER.value,
                new_status=MemoryJobStatus.QUEUED.value,
                safe_reason=reason[:240],
                created_at=captured,
            )
        return self.store.get_job(job_id, scope=scope.boundary())

    def _validate_type(self, job_type: str) -> None:
        if job_type not in {item.value for item in MemoryJobType}:
            raise RuntimeErrorCode(
                "MEMORY_JOB_TYPE_INVALID", "Unsupported durable job type."
            )

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID", "Job payload must be an object."
            )

        def inspect(value: Any, path: str = "") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    lowered = str(key).strip().lower()
                    if lowered in FORBIDDEN_PAYLOAD_KEYS or any(
                        token in lowered
                        for token in ("password", "credential", "authorization")
                    ):
                        raise RuntimeErrorCode(
                            "MEMORY_JOB_PAYLOAD_INVALID",
                            "Job payload may contain references and digests only.",
                        )
                    inspect(item, f"{path}.{lowered}")
            elif isinstance(value, list):
                for item in value:
                    inspect(item, path)
            elif not isinstance(value, (str, int, float, bool, type(None))):
                raise RuntimeErrorCode(
                    "MEMORY_JOB_PAYLOAD_INVALID",
                    "Job payload contains an unsupported value.",
                )

        inspect(payload)
        encoded = canonical_json(payload).encode("utf-8")
        if len(encoded) > self.policy.maximum_payload_bytes:
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID", "Job payload exceeds policy size limit."
            )

    @staticmethod
    def _assert_lease(job: MemoryJob, worker_id: str, digest: str) -> None:
        if (
            job.lease_owner != worker_id
            or job.lease_token_digest != digest
            or job.job_status
            not in {
                MemoryJobStatus.LEASED.value,
                MemoryJobStatus.RUNNING.value,
                MemoryJobStatus.CANCEL_REQUESTED.value,
            }
        ):
            raise RuntimeErrorCode(
                "MEMORY_JOB_LEASE_LOST", "Worker no longer owns the job lease."
            )


__all__ = ["FORBIDDEN_PAYLOAD_KEYS", "MemoryJobQueue"]
