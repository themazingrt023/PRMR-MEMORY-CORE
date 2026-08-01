"""Safe runtime schema, queue and isolation integrity helpers."""

from __future__ import annotations

from typing import Any

from .job_integrity import verify_job_integrity
from .job_store import MemoryJobStore
from .runtime_models import JOB_INTEGRITY_REVISION


def verify_runtime_job_scope_isolation(
    store: MemoryJobStore,
    *,
    scope: tuple[str, str, str],
    foreign_job_id: str,
) -> dict[str, Any]:
    try:
        store.get_job(foreign_job_id, scope=scope)
    except Exception as exc:
        return {
            "verified": getattr(exc, "code", None) == "MEMORY_JOB_NOT_FOUND",
            "safe_error_code": getattr(exc, "code", type(exc).__name__.upper()),
            "revision": JOB_INTEGRITY_REVISION,
        }
    return {
        "verified": False,
        "safe_error_code": "RUNTIME_SCOPE_LEAK",
        "revision": JOB_INTEGRITY_REVISION,
    }


def verify_runtime_jobs(
    store: MemoryJobStore, job_ids: list[str]
) -> dict[str, Any]:
    results = [verify_job_integrity(store, job_id) for job_id in job_ids]
    return {
        "verified": all(item["verified"] for item in results),
        "checked_count": len(results),
        "results": results,
        "revision": JOB_INTEGRITY_REVISION,
    }


__all__ = [
    "verify_runtime_job_scope_isolation",
    "verify_runtime_jobs",
]
