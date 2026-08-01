"""Durable-job model compatibility module.

The authoritative runtime and job revision contracts live together in
runtime_models so one queue schema cannot drift from its runtime boundary.
"""

from .runtime_models import (
    JOB_HANDLER_REVISION,
    JOB_INTEGRITY_REVISION,
    JOB_LEASE_REVISION,
    JOB_QUEUE_REVISION,
    JOB_RECOVERY_REVISION,
    JOB_RETRY_REVISION,
    JOB_SCHEMA_REVISION,
    LeasedMemoryJob,
    MemoryJob,
    MemoryJobAttempt,
    MemoryJobEvent,
    MemoryJobHandlerResult,
    MemoryJobStatus,
    MemoryJobType,
)


__all__ = [
    "JOB_HANDLER_REVISION",
    "JOB_INTEGRITY_REVISION",
    "JOB_LEASE_REVISION",
    "JOB_QUEUE_REVISION",
    "JOB_RECOVERY_REVISION",
    "JOB_RETRY_REVISION",
    "JOB_SCHEMA_REVISION",
    "LeasedMemoryJob",
    "MemoryJob",
    "MemoryJobAttempt",
    "MemoryJobEvent",
    "MemoryJobHandlerResult",
    "MemoryJobStatus",
    "MemoryJobType",
]
