"""RC1 backend, Python and Core Sprint 13 upgrade compatibility checks."""

from __future__ import annotations

import platform
from typing import Any

from prmr.core.runtime_migrations import detect_migration_drift, get_migration_status, migration_registry

from .version import RELEASE_COMPATIBILITY_REVISION, SUPPORTED_PYTHON


def check_runtime_compatibility(repository: Any) -> dict[str, Any]:
    status = get_migration_status(repository)
    expected = migration_registry()
    drift = detect_migration_drift(repository)
    python_minor = ".".join(platform.python_version_tuple()[:2])
    applied_ids = {row["migration_id"] for row in status}
    sprint_13_present = "core_13_continuity_packet_v2" in applied_ids
    return {
        "revision": RELEASE_COMPATIBILITY_REVISION,
        "python_version": platform.python_version(),
        "python_supported": python_minor in SUPPORTED_PYTHON,
        "operating_system": platform.system(),
        "database_backend": str(getattr(repository, "backend_name", "unknown")),
        "schema_current": len(status) == len(expected),
        "sprint_13_database_recognised": sprint_13_present,
        "migration_drift_absent": not drift["drift_detected"],
        "destructive_migration_required": False,
        "compatible": python_minor in SUPPORTED_PYTHON and sprint_13_present and not drift["drift_detected"],
    }


__all__ = ["check_runtime_compatibility"]
