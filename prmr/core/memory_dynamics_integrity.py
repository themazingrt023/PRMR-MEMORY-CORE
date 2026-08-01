"""Independent entry point for Temporal Memory Dynamics integrity checks."""

from __future__ import annotations

from typing import Any

from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_temporal_models import MemoryDynamicsIntegrityResult
from .source_models import AuthenticatedScope


def verify_memory_dynamics_integrity(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    dynamics_snapshot_id: str,
) -> MemoryDynamicsIntegrityResult:
    return MemoryDynamicsEngine(repository).verify_memory_dynamics_integrity(
        authenticated_scope, dynamics_snapshot_id
    )


__all__ = ["verify_memory_dynamics_integrity"]
