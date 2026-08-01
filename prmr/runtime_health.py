"""Typed release liveness, readiness and safe metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from prmr.core.runtime_migrations import detect_migration_drift, get_migration_status, migration_registry

from .release.identity import get_release_identity
from .release.version import RELEASE_HEALTH_REVISION, RELEASE_READINESS_REVISION
from .runtime_context import RuntimeContext


@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    status: str
    revision: str = RELEASE_HEALTH_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    status: str
    checks: dict[str, bool]
    safe_error_code: str | None = None
    revision: str = RELEASE_READINESS_REVISION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def runtime_health() -> HealthResult:
    return HealthResult(healthy=True, status="alive")


def runtime_readiness(context: RuntimeContext) -> ReadinessResult:
    checks = {
        "configuration_valid": False,
        "database_reachable": False,
        "schema_current": False,
        "migration_drift_absent": False,
        "repository_initialised": False,
        "job_store_available": False,
        "release_manifest_compatible": False,
        "runtime_accepting_work": not context.shutting_down,
    }
    try:
        context.configuration.validate()
        checks["configuration_valid"] = True
        health_check = getattr(context.repository, "health_check", None)
        if callable(health_check):
            checks["database_reachable"] = bool(health_check())
        else:
            with context.repository.connect() as connection:
                checks["database_reachable"] = bool(connection.execute("SELECT 1").fetchone())
        status = get_migration_status(context.repository)
        drift = detect_migration_drift(context.repository)
        checks["schema_current"] = len(status) == len(migration_registry())
        checks["migration_drift_absent"] = not drift["drift_detected"]
        checks["repository_initialised"] = checks["database_reachable"]
        from prmr.core.entity_store import table

        with context.repository.connect() as connection:
            connection.execute(f"SELECT COUNT(*) AS count FROM {table(context.repository, 'prmr_memory_jobs')}").fetchone()
        checks["job_store_available"] = True
        checks["release_manifest_compatible"] = get_release_identity()["package_version"] == "1.0.0rc1"
        ready = all(checks.values())
        context.ready = ready
        return ReadinessResult(ready, "ready" if ready else "not_ready", checks)
    except Exception as exc:
        context.ready = False
        return ReadinessResult(
            False,
            "not_ready",
            checks,
            safe_error_code=str(getattr(exc, "code", type(exc).__name__.upper())),
        )


def collect_runtime_metrics(context: RuntimeContext) -> dict[str, Any]:
    from prmr.core.entity_store import table

    counts = {name: 0 for name in ("queued", "leased", "retrying", "dead_letter", "completed")}
    try:
        with context.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT job_status, COUNT(*) AS count FROM {table(context.repository, 'prmr_memory_jobs')} GROUP BY job_status"
            ).fetchall()
        for row in rows:
            status = str(row["job_status"])
            if status in counts:
                counts[status] = int(row["count"])
    except Exception:
        pass
    return {
        "process_ready": context.ready,
        "database_backend": context.configuration.database_backend,
        "jobs": counts,
        "migration_count": len(get_migration_status(context.repository)),
        "pool": getattr(context.repository, "pool_stats", lambda: {})(),
    }


__all__ = ["HealthResult", "ReadinessResult", "collect_runtime_metrics", "runtime_health", "runtime_readiness"]
