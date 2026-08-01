"""Synthetic, content-free fixtures for durable-job runtime tests."""

from __future__ import annotations

from collections import Counter
import threading
from typing import Any

from .job_handlers import CoreServiceReferenceHandler, MemoryJobHandlerRegistry
from .runtime_models import MemoryJob, MemoryJobType, RuntimeErrorCode, RuntimeScope


def synthetic_runtime_scope(label: str = "alpha") -> RuntimeScope:
    return RuntimeScope(
        client_id=f"client_runtime_{label}",
        vault_id=f"vault_runtime_{label}",
        namespace="runtime_test",
        application_reference=f"app_runtime_{label}",
        actor_reference=f"actor_runtime_{label}",
        workspace_reference=f"workspace_runtime_{label}",
    )


class SyntheticEffectService:
    """Thread-safe test service exposing only deterministic result references."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self._lock = threading.Lock()
        self.failures_remaining: Counter[str] = Counter()

    def configure_failures(self, target_id: str, count: int) -> None:
        self.failures_remaining[target_id] = count

    def execute(self, job: MemoryJob) -> dict[str, Any]:
        with self._lock:
            self.calls[job.job_id] += 1
            if self.failures_remaining[job.target_object_id] > 0:
                self.failures_remaining[job.target_object_id] -= 1
                raise RuntimeErrorCode(
                    "POSTGRES_CONNECTION_FAILED",
                    "Synthetic transient runtime failure.",
                )
        return {
            "result_reference_id": f"effect_{job.job_id[5:]}",
            "safe_metrics": {"call_count": self.calls[job.job_id]},
        }


def synthetic_handler_registry(
    service: SyntheticEffectService,
) -> MemoryJobHandlerRegistry:
    registry = MemoryJobHandlerRegistry()
    registry.register(
        CoreServiceReferenceHandler(
            tuple(item.value for item in MemoryJobType),
            service.execute,
            result_type="synthetic_runtime_effect",
        )
    )
    return registry


__all__ = [
    "SyntheticEffectService",
    "synthetic_handler_registry",
    "synthetic_runtime_scope",
]
