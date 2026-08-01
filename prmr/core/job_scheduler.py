"""Deterministic persisted schedules for internal maintenance jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .entity_store import json_value
from .job_queue import MemoryJobQueue
from .job_store import utc_now
from .runtime_models import RuntimeErrorCode, RuntimeScope
from .source_integrity import canonical_json, sha256_text


class MemoryJobScheduler:
    def __init__(self, queue: MemoryJobQueue) -> None:
        self.queue = queue
        self.store = queue.store
        self.p = self.store.p

    def create_schedule(
        self,
        scope: RuntimeScope,
        *,
        schedule_type: str,
        job_type: str,
        target_object_type: str,
        target_object_id: str,
        safe_payload: dict[str, Any],
        next_run_at: str,
        interval_seconds: int | None = None,
        created_at: str | None = None,
    ) -> str:
        if schedule_type not in {
            "one_time",
            "interval",
            "retention_scan",
            "expired_export_scan",
            "integrity_sweep",
            "stale_consolidation_refresh",
        }:
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID", "Unsupported schedule type."
            )
        self.queue._validate_type(job_type)
        self.queue._validate_payload(safe_payload)
        if schedule_type != "one_time" and (
            interval_seconds is None or interval_seconds <= 0
        ):
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID",
                "Recurring schedule requires a positive interval.",
            )
        now = created_at or utc_now()
        material = {
            "scope": scope.boundary(),
            "schedule_type": schedule_type,
            "job_type": job_type,
            "target_type": target_object_type,
            "target_id": target_object_id,
            "payload": safe_payload,
            "next_run": next_run_at,
            "interval": interval_seconds,
        }
        schedule_id = f"msched_{sha256_text(canonical_json(material))[:24]}"
        values = (
            schedule_id,
            schedule_type,
            job_type,
            scope.client_id,
            scope.vault_id,
            scope.namespace,
            target_object_type,
            target_object_id,
            json_value(self.store.repository, safe_payload),
            interval_seconds,
            next_run_at,
            "active",
            0,
            now,
            now,
        )
        suffix = (
            " ON CONFLICT (schedule_id) DO NOTHING"
            if self.store.postgres
            else " ON CONFLICT(schedule_id) DO NOTHING"
        )
        with self.store.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.store.tables['schedules']}(schedule_id,"
                "schedule_type,job_type,client_id,vault_id,namespace,"
                "target_object_type,target_object_id,safe_payload_json,"
                "interval_seconds,next_run_at,schedule_status,occurrence_number,"
                f"created_at,updated_at) VALUES({','.join([self.p]*15)}){suffix}",
                values,
            )
        return schedule_id

    def enqueue_due(self, *, now: str | None = None) -> list[str]:
        captured = now or utc_now()
        with self.store.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.store.tables['schedules']} WHERE "
                f"schedule_status={self.p} AND next_run_at<={self.p} "
                "ORDER BY next_run_at,schedule_id",
                ("active", captured),
            ).fetchall()
        enqueued: list[str] = []
        for row in rows:
            item = dict(row)
            payload = item["safe_payload_json"]
            if not isinstance(payload, dict):
                import json

                payload = json.loads(payload)
            occurrence = int(item["occurrence_number"]) + 1
            scope = RuntimeScope(
                str(item["client_id"]),
                str(item["vault_id"]),
                str(item["namespace"]),
            )
            job = self.queue.enqueue(
                scope,
                job_type=str(item["job_type"]),
                target_object_type=str(item["target_object_type"]),
                target_object_id=str(item["target_object_id"]),
                safe_payload=payload,
                idempotency_key=f"{item['schedule_id']}:{occurrence}",
                scheduled_for=captured,
                correlation_id=f"schedule:{item['schedule_id']}",
                created_at=captured,
            )
            enqueued.append(job.job_id)
            if item["schedule_type"] == "one_time":
                status = "completed"
                next_run = item["next_run_at"]
            else:
                status = "active"
                next_run = _plus_seconds(
                    captured, int(item["interval_seconds"])
                )
            with self.store.repository.connect() as connection:
                connection.execute(
                    f"UPDATE {self.store.tables['schedules']} SET "
                    f"occurrence_number={self.p},next_run_at={self.p},"
                    f"schedule_status={self.p},updated_at={self.p} "
                    f"WHERE schedule_id={self.p} AND occurrence_number={self.p}",
                    (
                        occurrence,
                        next_run,
                        status,
                        captured,
                        item["schedule_id"],
                        occurrence - 1,
                    ),
                )
        return enqueued


def _plus_seconds(value: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


__all__ = ["MemoryJobScheduler"]
