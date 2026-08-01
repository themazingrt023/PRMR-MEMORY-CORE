"""Leased durable-job worker with retry and crash recovery semantics."""

from __future__ import annotations

from dataclasses import replace
import logging
import threading
import time
from typing import Any

from .job_handlers import MemoryJobHandlerRegistry
from .job_policy import (
    classify_runtime_error,
    is_retryable,
    sanitise_safe_error,
)
from .job_queue import MemoryJobQueue
from .job_store import utc_now
from .runtime_failure_injection import (
    InjectedRuntimeFailure,
    RuntimeFailureInjector,
)
from .runtime_models import (
    MemoryJobHandlerResult,
    MemoryJobStatus,
    RuntimeErrorCode,
    RuntimeScope,
    RuntimeTransactionPolicy,
)
from .source_integrity import canonical_json, sha256_text


LOGGER = logging.getLogger("prmr.core.runtime.worker")


class MemoryJobWorker:
    def __init__(
        self,
        queue: MemoryJobQueue,
        handlers: MemoryJobHandlerRegistry,
        *,
        worker_id: str,
        failure_injector: RuntimeFailureInjector | None = None,
    ) -> None:
        if not worker_id.startswith("worker_"):
            raise ValueError("Worker IDs must use the worker_ prefix.")
        self.queue = queue
        self.handlers = handlers
        self.worker_id = worker_id
        self.failure_injector = failure_injector or RuntimeFailureInjector()
        self._stop = threading.Event()

    def run_once(self) -> dict[str, Any]:
        leased = self.queue.lease_next_job(self.worker_id)
        if not leased:
            return {"status": "idle", "worker_id": self.worker_id}
        return self.execute_job(leased)

    def run_until_idle(self, *, maximum_jobs: int | None = None) -> dict[str, Any]:
        outcomes: list[dict[str, Any]] = []
        while maximum_jobs is None or len(outcomes) < maximum_jobs:
            outcome = self.run_once()
            if outcome["status"] == "idle":
                break
            outcomes.append(outcome)
        return {
            "worker_id": self.worker_id,
            "processed": len(outcomes),
            "outcomes": outcomes,
        }

    def start_polling(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            outcome = self.run_once()
            if outcome["status"] == "idle":
                self._stop.wait(self.queue.policy.worker_poll_interval_seconds)

    def stop_gracefully(self) -> None:
        self._stop.set()

    def lease_next_job(self):
        return self.queue.lease_next_job(self.worker_id)

    def heartbeat_job(self, leased: Any, attempt_id: str | None = None) -> Any:
        self.failure_injector.inject("during_heartbeat")
        return self.queue.heartbeat(
            leased.job.job_id,
            worker_id=self.worker_id,
            lease_token=leased.lease_token,
            attempt_id=attempt_id,
        )

    def execute_job(self, leased: Any) -> dict[str, Any]:
        started = time.perf_counter()
        attempt_id: str | None = None
        job = leased.job
        try:
            transaction_mode = RuntimeTransactionPolicy.READ_COMMITTED_V1.value
            job, attempt_id = self.queue.start_job(
                leased,
                worker_id=self.worker_id,
                transaction_mode=transaction_mode,
            )
            handler = self.handlers.resolve(job.job_type)
            handler.validate_job(job)
            current = self.queue.store.get_job(
                job.job_id, scope=(job.client_id, job.vault_id, job.namespace)
            )
            if current.job_status == MemoryJobStatus.CANCEL_REQUESTED.value:
                cancellation = handler.cancel(current)
                raise RuntimeErrorCode("MEMORY_JOB_CANCELLED", cancellation)
            existing_effect = self.queue.store.get_effect(job.job_id)
            result = handler.recover(job)
            if result is None and existing_effect:
                result = MemoryJobHandlerResult(
                    result_reference_type=existing_effect["result_reference_type"],
                    result_reference_id=existing_effect["result_reference_id"],
                    result_hash_sha256=existing_effect["result_hash_sha256"],
                    effect_status=existing_effect["effect_status"],
                    replayed=True,
                    safe_metrics={"effect_receipt_recovered": True},
                )
            if result is None:
                self.failure_injector.inject("before_transaction")
                result = handler.execute(job)
            if not handler.verify_result(job, result):
                raise RuntimeErrorCode(
                    "MEMORY_JOB_RESULT_INVALID",
                    "Handler result did not pass deterministic verification.",
                )
            self.queue.commit_effect_receipt(
                job,
                worker_id=self.worker_id,
                lease_token=leased.lease_token,
                result=result,
            )
            self.failure_injector.inject(
                "after_effect_commit_before_job_completion"
            )
            self.failure_injector.inject("before_job_completion")
            completed = self.queue.complete(
                job,
                worker_id=self.worker_id,
                lease_token=leased.lease_token,
                attempt_id=attempt_id,
                result=result,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            LOGGER.info(
                "memory_job_completed",
                extra={"job_id": job.job_id, "worker_id": self.worker_id},
            )
            return {
                "status": completed.job_status,
                "job_id": completed.job_id,
                "replayed": result.replayed,
                "result_reference_type": result.result_reference_type,
                "result_reference_id": result.result_reference_id,
            }
        except InjectedRuntimeFailure as exc:
            LOGGER.warning(
                "runtime_failure_injected",
                extra={"job_id": job.job_id, "safe_error_code": exc.code},
            )
            if exc.crash:
                return {
                    "status": "worker_crashed",
                    "job_id": job.job_id,
                    "injection_point": exc.injection_point,
                }
            return self._fail(job, leased.lease_token, attempt_id, exc, started)
        except Exception as exc:
            if getattr(exc, "code", "") == "MEMORY_JOB_CANCELLED":
                return self._cancel_running(
                    job, leased.lease_token, attempt_id, str(exc), started
                )
            return self._fail(job, leased.lease_token, attempt_id, exc, started)

    def _fail(
        self,
        job: Any,
        lease_token: str,
        attempt_id: str | None,
        error: BaseException,
        started: float,
    ) -> dict[str, Any]:
        if not attempt_id:
            return {
                "status": "lease_start_failed",
                "job_id": job.job_id,
                "safe_error_code": getattr(error, "code", type(error).__name__),
            }
        classification = classify_runtime_error(error)
        code, detail = sanitise_safe_error(error)
        failed = self.queue.fail(
            job,
            worker_id=self.worker_id,
            lease_token=lease_token,
            attempt_id=attempt_id,
            error_code=code,
            safe_error_details=detail,
            retryable=is_retryable(classification),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return {
            "status": failed.job_status,
            "job_id": failed.job_id,
            "safe_error_code": code,
            "error_class": classification.value,
        }

    def _cancel_running(
        self,
        job: Any,
        lease_token: str,
        attempt_id: str | None,
        reason: str,
        started: float,
    ) -> dict[str, Any]:
        if not attempt_id:
            return {"status": "cancelled", "job_id": job.job_id}
        cancelled = self.queue.cancel_running(
            job,
            worker_id=self.worker_id,
            lease_token=lease_token,
            attempt_id=attempt_id,
            reason=reason,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return {"status": cancelled.job_status, "job_id": cancelled.job_id}

    def request_job_cancellation(
        self, scope: RuntimeScope, job_id: str, *, reason: str
    ) -> Any:
        return self.queue.request_cancellation(scope, job_id, reason=reason)

    def recover_expired_leases(self) -> list[str]:
        return self.queue.recover_expired_leases()

    def replay_dead_letter_job(
        self, scope: RuntimeScope, job_id: str, *, reason: str
    ) -> Any:
        return self.queue.replay_dead_letter(scope, job_id, reason=reason)


__all__ = ["MemoryJobWorker"]
