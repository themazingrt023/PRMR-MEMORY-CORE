"""Ordered RC1 runtime bootstrap that cleans up partial startup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prmr.core.runtime_migrations import apply_pending_migrations, verify_schema_revision

from .release.identity import get_release_identity
from .runtime_config import RuntimeConfiguration
from .runtime_context import RuntimeContext, build_repository
from .runtime_health import runtime_readiness


@dataclass(frozen=True)
class BootstrapResult:
    context: RuntimeContext
    phases: tuple[str, ...]
    migrations_applied: tuple[str, ...]


def bootstrap_runtime(configuration: RuntimeConfiguration, *, migrate: bool = False) -> BootstrapResult:
    phases: list[str] = ["configuration_loaded"]
    configuration.validate()
    phases.extend(("configuration_validated", "release_identity_built", "logging_initialised"))
    repository = None
    try:
        repository = build_repository(configuration)
        phases.append("database_connected")
        applied = apply_pending_migrations(repository) if migrate else []
        phases.append("schema_verified")
        revision = verify_schema_revision(repository)
        if not revision["verified"]:
            raise RuntimeError("MIGRATION_REQUIRED")
        phases.extend(
            (
                "migration_state_verified",
                "repositories_initialised",
                "core_services_initialised",
                "job_queue_initialised",
                "handlers_registered",
            )
        )
        context = RuntimeContext(configuration, repository)
        readiness = runtime_readiness(context)
        if not readiness.ready:
            raise RuntimeError(readiness.safe_error_code or "READINESS_FAILED")
        phases.extend(("readiness_verified", "runtime_ready"))
        return BootstrapResult(context, tuple(phases), tuple(applied))
    except Exception:
        close = getattr(repository, "close", None)
        if callable(close):
            close()
        raise


__all__ = ["BootstrapResult", "bootstrap_runtime"]
