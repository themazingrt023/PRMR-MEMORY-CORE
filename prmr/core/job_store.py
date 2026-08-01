"""Repository-backed durable storage for internal Memory Core jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .entity_store import json_value, placeholder, table
from .runtime_models import (
    JOB_HANDLER_REVISION,
    JOB_INTEGRITY_REVISION,
    MemoryJob,
    MemoryJobAttempt,
    MemoryJobEvent,
    RuntimeErrorCode,
)


ROOT = Path(__file__).resolve().parents[2]
SQLITE_MIGRATION = ROOT / "migrations" / "core_memory_runtime_v1_sqlite.sql"
POSTGRES_MIGRATION = ROOT / "migrations" / "core_memory_runtime_v1_postgres.sql"

JOB_TABLES = {
    "jobs": "prmr_memory_jobs",
    "attempts": "prmr_memory_job_attempts",
    "events": "prmr_memory_job_events",
    "dependencies": "prmr_memory_job_dependencies",
    "effects": "prmr_memory_job_effects",
    "schedules": "prmr_memory_job_schedules",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initialize_memory_job_schema(repository: Any) -> None:
    postgres = str(getattr(repository, "backend_name", "sqlite")) == "postgres"
    path = POSTGRES_MIGRATION if postgres else SQLITE_MIGRATION
    sql = path.read_text(encoding="utf-8")
    with repository.connect() as connection:
        if hasattr(connection, "executescript"):
            connection.executescript(sql)
        else:
            connection.execute(sql)


def _text_time(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


class MemoryJobStore:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_memory_job_schema(repository)
        self.postgres = str(getattr(repository, "backend_name", "sqlite")) == "postgres"
        self.p = placeholder(repository)
        self.tables = {
            key: table(repository, value) for key, value in JOB_TABLES.items()
        }

    def job_from_row(self, row: Any) -> MemoryJob:
        item = dict(row)
        payload = item.pop("safe_payload_json")
        item["safe_payload"] = (
            dict(payload) if isinstance(payload, dict) else json.loads(payload)
        )
        for key in (
            "scheduled_for",
            "available_after",
            "lease_acquired_at",
            "lease_expires_at",
            "heartbeat_at",
            "started_at",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ):
            item[key] = _text_time(item.get(key))
        return MemoryJob(**item)

    def get_job(
        self,
        job_id: str,
        *,
        scope: tuple[str, str, str] | None = None,
        connection: Any | None = None,
    ) -> MemoryJob:
        predicates = [f"job_id={self.p}"]
        params: list[Any] = [job_id]
        if scope:
            predicates.extend(
                (
                    f"client_id={self.p}",
                    f"vault_id={self.p}",
                    f"namespace={self.p}",
                )
            )
            params.extend(scope)
        if connection is not None:
            row = connection.execute(
                f"SELECT * FROM {self.tables['jobs']} WHERE "
                + " AND ".join(predicates),
                tuple(params),
            ).fetchone()
        else:
            with self.repository.connect() as owned:
                row = owned.execute(
                    f"SELECT * FROM {self.tables['jobs']} WHERE "
                    + " AND ".join(predicates),
                    tuple(params),
                ).fetchone()
        if not row:
            raise RuntimeErrorCode(
                "MEMORY_JOB_NOT_FOUND", "Job was not found in the requested scope."
            )
        return self.job_from_row(row)

    def find_identity(
        self,
        scope: tuple[str, str, str],
        job_type: str,
        target_object_type: str,
        target_object_id: str,
        idempotency_digest: str,
    ) -> MemoryJob | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.tables['jobs']} WHERE "
                f"client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND job_type={self.p} AND target_object_type={self.p} "
                f"AND target_object_id={self.p} AND idempotency_key_digest={self.p}",
                (
                    *scope,
                    job_type,
                    target_object_type,
                    target_object_id,
                    idempotency_digest,
                ),
            ).fetchone()
        return self.job_from_row(row) if row else None

    def insert_job(self, job: MemoryJob) -> None:
        payload = job.to_dict()
        payload.pop("safe_payload")
        columns = tuple(payload.keys()) + ("safe_payload_json",)
        values = tuple(payload.values()) + (
            json_value(self.repository, job.safe_payload),
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.tables['jobs']}({','.join(columns)}) "
                f"VALUES({','.join([self.p] * len(columns))})",
                values,
            )

    def update_job(
        self,
        connection: Any,
        job_id: str,
        values: dict[str, Any],
        *,
        lease_owner: str | None = None,
        lease_token_digest: str | None = None,
        allowed_statuses: tuple[str, ...] | None = None,
    ) -> int:
        assignments = [f"{key}={self.p}" for key in values]
        params: list[Any] = list(values.values())
        predicates = [f"job_id={self.p}"]
        params.append(job_id)
        if lease_owner is not None:
            predicates.append(f"lease_owner={self.p}")
            params.append(lease_owner)
        if lease_token_digest is not None:
            predicates.append(f"lease_token_digest={self.p}")
            params.append(lease_token_digest)
        if allowed_statuses:
            predicates.append(
                "job_status IN (" + ",".join([self.p] * len(allowed_statuses)) + ")"
            )
            params.extend(allowed_statuses)
        cursor = connection.execute(
            f"UPDATE {self.tables['jobs']} SET {','.join(assignments)} WHERE "
            + " AND ".join(predicates),
            tuple(params),
        )
        return int(cursor.rowcount)

    def append_event(
        self,
        connection: Any,
        *,
        job_id: str,
        event_type: str,
        previous_status: str | None,
        new_status: str,
        safe_reason: str,
        worker_id: str | None = None,
        job_attempt_id: str | None = None,
        created_at: str | None = None,
    ) -> MemoryJobEvent:
        sequence_row = connection.execute(
            f"SELECT COALESCE(MAX(sequence_number),0)+1 AS next_sequence "
            f"FROM {self.tables['events']} WHERE job_id={self.p}",
            (job_id,),
        ).fetchone()
        sequence = int(sequence_row["next_sequence"])
        event_id = f"jevt_{_digest(f'{job_id}:{sequence}:{event_type}')[:24]}"
        event = MemoryJobEvent(
            job_event_id=event_id,
            job_id=job_id,
            job_attempt_id=job_attempt_id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            worker_id=worker_id,
            safe_reason=safe_reason[:240],
            sequence_number=sequence,
            created_at=created_at or utc_now(),
        )
        columns = tuple(event.to_dict().keys())
        connection.execute(
            f"INSERT INTO {self.tables['events']}({','.join(columns)}) "
            f"VALUES({','.join([self.p] * len(columns))})",
            tuple(event.to_dict().values()),
        )
        return event

    def create_attempt(
        self,
        connection: Any,
        job: MemoryJob,
        *,
        worker_id: str,
        lease_token_digest: str,
        transaction_mode: str,
        now: str,
    ) -> MemoryJobAttempt:
        attempt_id = f"jatm_{_digest(f'{job.job_id}:{job.attempt_count}')[:24]}"
        attempt = MemoryJobAttempt(
            job_attempt_id=attempt_id,
            job_id=job.job_id,
            attempt_number=job.attempt_count,
            worker_id=worker_id,
            lease_token_digest=lease_token_digest,
            status="running",
            started_at=now,
            heartbeat_at=now,
            completed_at=None,
            duration_ms=None,
            handler_revision=JOB_HANDLER_REVISION,
            transaction_mode=transaction_mode,
            retryable=None,
            error_code=None,
            safe_error_details=None,
            result_reference_type=None,
            result_reference_id=None,
            created_at=now,
        )
        columns = tuple(attempt.to_dict().keys())
        values = tuple(attempt.to_dict().values())
        connection.execute(
            f"INSERT INTO {self.tables['attempts']}({','.join(columns)}) "
            f"VALUES({','.join([self.p] * len(columns))})",
            values,
        )
        return attempt

    def finish_attempt(
        self,
        connection: Any,
        attempt_id: str,
        *,
        status: str,
        completed_at: str,
        duration_ms: float,
        retryable: bool,
        error_code: str | None,
        safe_error_details: str | None,
        result_reference_type: str | None,
        result_reference_id: str | None,
    ) -> None:
        connection.execute(
            f"UPDATE {self.tables['attempts']} SET status={self.p},"
            f"completed_at={self.p},duration_ms={self.p},retryable={self.p},"
            f"error_code={self.p},safe_error_details={self.p},"
            f"result_reference_type={self.p},result_reference_id={self.p} "
            f"WHERE job_attempt_id={self.p}",
            (
                status,
                completed_at,
                duration_ms,
                retryable,
                error_code,
                safe_error_details,
                result_reference_type,
                result_reference_id,
                attempt_id,
            ),
        )

    def list_events(self, job_id: str) -> list[MemoryJobEvent]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.tables['events']} WHERE job_id={self.p} "
                "ORDER BY sequence_number",
                (job_id,),
            ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["created_at"] = _text_time(item["created_at"])
            values.append(MemoryJobEvent(**item))
        return values

    def list_attempts(self, job_id: str) -> list[MemoryJobAttempt]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.tables['attempts']} WHERE job_id={self.p} "
                "ORDER BY attempt_number",
                (job_id,),
            ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            if item.get("retryable") is not None:
                item["retryable"] = bool(item["retryable"])
            for key in ("started_at", "heartbeat_at", "completed_at", "created_at"):
                item[key] = _text_time(item.get(key))
            values.append(MemoryJobAttempt(**item))
        return values

    def get_effect(self, job_id: str) -> dict[str, Any] | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.tables['effects']} WHERE job_id={self.p}",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def record_effect(
        self,
        connection: Any,
        job: MemoryJob,
        *,
        result_reference_type: str,
        result_reference_id: str,
        result_hash_sha256: str,
        effect_status: str,
        committed_at: str,
    ) -> None:
        values = (
            job.job_id,
            job.client_id,
            job.vault_id,
            job.namespace,
            result_reference_type,
            result_reference_id,
            result_hash_sha256,
            effect_status,
            committed_at,
        )
        if self.postgres:
            suffix = " ON CONFLICT (job_id) DO NOTHING"
        else:
            suffix = " ON CONFLICT(job_id) DO NOTHING"
        connection.execute(
            f"INSERT INTO {self.tables['effects']}(job_id,client_id,vault_id,"
            "namespace,result_reference_type,result_reference_id,result_hash_sha256,"
            f"effect_status,committed_at) VALUES({','.join([self.p]*9)}){suffix}",
            values,
        )

    def count_jobs(self, scope: tuple[str, str, str] | None = None) -> int:
        predicates = ""
        params: tuple[Any, ...] = ()
        if scope:
            predicates = (
                f" WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p}"
            )
            params = scope
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {self.tables['jobs']}{predicates}",
                params,
            ).fetchone()
        return int(row["count"])


def _digest(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "JOB_TABLES",
    "MemoryJobStore",
    "POSTGRES_MIGRATION",
    "SQLITE_MIGRATION",
    "initialize_memory_job_schema",
    "utc_now",
]
