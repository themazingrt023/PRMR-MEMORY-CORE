"""Durable-job lease and effect recovery helpers."""

from __future__ import annotations

from typing import Any

from .job_handlers import MemoryJobHandlerRegistry
from .job_queue import MemoryJobQueue
from .job_worker import MemoryJobWorker
from .runtime_models import RuntimeScope


class MemoryJobRecovery:
    def __init__(
        self, queue: MemoryJobQueue, handlers: MemoryJobHandlerRegistry
    ) -> None:
        self.queue = queue
        self.handlers = handlers

    def recover_expired_leases(self, *, now: str | None = None) -> list[str]:
        return self.queue.recover_expired_leases(now=now)

    def recover_until_idle(
        self, *, worker_id: str = "worker_recovery"
    ) -> dict[str, Any]:
        recovered = self.recover_expired_leases()
        worker = MemoryJobWorker(
            self.queue,
            self.handlers,
            worker_id=worker_id,
        )
        result = worker.run_until_idle()
        return {
            "recovered_job_ids": recovered,
            "processed": result["processed"],
            "outcomes": result["outcomes"],
        }

    def explicit_dead_letter_replay(
        self,
        scope: RuntimeScope,
        job_id: str,
        *,
        reason: str,
    ) -> Any:
        return self.queue.replay_dead_letter(scope, job_id, reason=reason)


__all__ = ["MemoryJobRecovery"]
