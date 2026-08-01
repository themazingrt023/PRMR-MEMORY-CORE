"""Durable-job handler contracts wrapping existing Memory Core services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any, Callable

from .runtime_models import (
    JOB_HANDLER_REVISION,
    MemoryJob,
    MemoryJobHandlerResult,
    MemoryJobType,
    RuntimeErrorCode,
)
from .source_integrity import canonical_json, sha256_text


class MemoryJobHandler(ABC):
    job_types: tuple[str, ...] = ()
    handler_revision = JOB_HANDLER_REVISION

    @abstractmethod
    def validate_job(self, job: MemoryJob) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, job: MemoryJob) -> MemoryJobHandlerResult:
        raise NotImplementedError

    def recover(self, job: MemoryJob) -> MemoryJobHandlerResult | None:
        return None

    def cancel(self, job: MemoryJob) -> str:
        return "cancelled_before_effect"

    def verify_result(
        self, job: MemoryJob, result: MemoryJobHandlerResult
    ) -> bool:
        return bool(
            result.result_reference_type
            and result.result_reference_id
            and len(result.result_hash_sha256) == 64
        )


class MemoryJobHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, MemoryJobHandler] = {}

    def register(self, handler: MemoryJobHandler) -> None:
        for job_type in handler.job_types:
            if job_type in self._handlers:
                raise ValueError(f"Handler already registered for {job_type}.")
            self._handlers[job_type] = handler

    def resolve(self, job_type: str) -> MemoryJobHandler:
        handler = self._handlers.get(job_type)
        if not handler:
            raise RuntimeErrorCode(
                "MEMORY_JOB_TYPE_INVALID", "No handler is registered for job type."
            )
        return handler

    @property
    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


class CoreServiceReferenceHandler(MemoryJobHandler):
    """Call a supplied existing core service without duplicating its logic."""

    def __init__(
        self,
        job_types: tuple[str, ...],
        operation: Callable[[MemoryJob], Any],
        *,
        recovery: Callable[[MemoryJob], Any | None] | None = None,
        result_type: str,
    ) -> None:
        self.job_types = job_types
        self.operation = operation
        self.recovery = recovery
        self.result_type = result_type

    def validate_job(self, job: MemoryJob) -> None:
        if job.job_type not in self.job_types:
            raise RuntimeErrorCode(
                "MEMORY_JOB_TYPE_INVALID", "Handler cannot execute this job type."
            )
        if not job.target_object_id:
            raise RuntimeErrorCode(
                "MEMORY_JOB_PAYLOAD_INVALID", "Handler target reference is missing."
            )

    def execute(self, job: MemoryJob) -> MemoryJobHandlerResult:
        value = self.operation(job)
        return self._result(job, value, replayed=False)

    def recover(self, job: MemoryJob) -> MemoryJobHandlerResult | None:
        if not self.recovery:
            return None
        value = self.recovery(job)
        return self._result(job, value, replayed=True) if value is not None else None

    def _result(
        self, job: MemoryJob, value: Any, *, replayed: bool
    ) -> MemoryJobHandlerResult:
        if isinstance(value, MemoryJobHandlerResult):
            return replace(value, replayed=replayed or value.replayed)
        if isinstance(value, dict):
            reference_id = str(
                value.get("result_reference_id")
                or value.get("id")
                or value.get("execution_id")
                or value.get("bundle_id")
                or job.target_object_id
            )
            safe_metrics = {
                str(key): item
                for key, item in value.get("safe_metrics", {}).items()
                if isinstance(item, (str, int, float, bool))
            }
            digest_material = {
                "job_id": job.job_id,
                "result_type": self.result_type,
                "reference_id": reference_id,
                "result_hash": value.get("result_hash"),
            }
        else:
            reference_id = str(value or job.target_object_id)
            safe_metrics = {}
            digest_material = {
                "job_id": job.job_id,
                "result_type": self.result_type,
                "reference_id": reference_id,
            }
        return MemoryJobHandlerResult(
            result_reference_type=self.result_type,
            result_reference_id=reference_id,
            result_hash_sha256=sha256_text(canonical_json(digest_material)),
            effect_status="committed",
            replayed=replayed,
            safe_metrics=safe_metrics,
        )


def build_initial_handler_registry(
    *,
    interpretation: Callable[[MemoryJob], Any] | None = None,
    temporal_refresh: Callable[[MemoryJob], Any] | None = None,
    consolidation: Callable[[MemoryJob], Any] | None = None,
    governance_execution: Callable[[MemoryJob], Any] | None = None,
    governance_recovery: Callable[[MemoryJob], Any] | None = None,
    export_generation: Callable[[MemoryJob], Any] | None = None,
    source_expiry: Callable[[MemoryJob], Any] | None = None,
    integrity_sweep: Callable[[MemoryJob], Any] | None = None,
    derived_invalidation: Callable[[MemoryJob], Any] | None = None,
) -> MemoryJobHandlerRegistry:
    """Build adapters only for explicitly supplied authoritative services."""

    registry = MemoryJobHandlerRegistry()
    mappings = (
        (
            (MemoryJobType.INTERPRETATION_RUN.value,),
            interpretation,
            "interpretation_request",
        ),
        (
            (
                MemoryJobType.TEMPORAL_DYNAMICS_REFRESH.value,
                MemoryJobType.CANONICAL_PROJECTION_REFRESH.value,
                MemoryJobType.CHECKPOINT_REFRESH.value,
                MemoryJobType.QUERY_PRECOMPUTE.value,
            ),
            temporal_refresh,
            "memory_projection",
        ),
        (
            (
                MemoryJobType.CONSOLIDATION_BUILD.value,
                MemoryJobType.CONSOLIDATION_REFRESH.value,
            ),
            consolidation,
            "consolidation",
        ),
        (
            (MemoryJobType.GOVERNANCE_EXECUTION.value,),
            governance_execution,
            "governance_execution",
        ),
        (
            (MemoryJobType.GOVERNANCE_RECOVERY.value,),
            governance_recovery,
            "governance_execution",
        ),
        (
            (MemoryJobType.EXPORT_GENERATION.value, MemoryJobType.EXPORT_EXPIRY.value),
            export_generation,
            "memory_export",
        ),
        (
            (MemoryJobType.SOURCE_EXPIRY_PURGE.value,),
            source_expiry,
            "governance_execution",
        ),
        (
            (MemoryJobType.INTEGRITY_SWEEP.value,),
            integrity_sweep,
            "runtime_integrity_sweep",
        ),
        (
            (
                MemoryJobType.DERIVED_ARTIFACT_INVALIDATION.value,
                MemoryJobType.POST_ERASURE_RECOMPUTE.value,
            ),
            derived_invalidation,
            "derived_artifact",
        ),
    )
    for job_types, operation, result_type in mappings:
        if operation:
            registry.register(
                CoreServiceReferenceHandler(
                    job_types,
                    operation,
                    result_type=result_type,
                )
            )
    return registry


__all__ = [
    "CoreServiceReferenceHandler",
    "MemoryJobHandler",
    "MemoryJobHandlerRegistry",
    "build_initial_handler_registry",
]
