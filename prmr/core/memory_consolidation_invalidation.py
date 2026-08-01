"""Manifest-based staleness detection for consolidation checkpoints."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .memory_consolidation_membership import fast_authoritative_manifest
from .memory_consolidation_models import (
    MemoryCheckpointStatus,
    MemoryConsolidationStatus,
)
from .memory_consolidation_planner import utc
from .memory_consolidation_store import MemoryConsolidationStore
from .source_models import AuthenticatedScope


class MemoryConsolidationInvalidationService:
    """Detect manifest drift without deleting historical derived records."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryConsolidationStore(repository, initialize=initialize)

    def detect_and_mark_stale(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        current = fast_authoritative_manifest(
            self.repository, scope
        )["authoritative_manifest_hash"]
        stale: list[str] = []
        for checkpoint in self.store.list_checkpoints(
            scope, statuses=(MemoryCheckpointStatus.CURRENT.value,)
        ):
            if checkpoint.authoritative_event_manifest_hash == current:
                continue
            stale.append(checkpoint.memory_checkpoint_id)
            self.store.put_checkpoint(
                replace(
                    checkpoint,
                    checkpoint_status=MemoryCheckpointStatus.STALE.value,
                )
            )
            run = self.store.get_run(scope, checkpoint.consolidation_run_id)
            if run:
                self.store.put_run(
                    replace(
                        run,
                        status=MemoryConsolidationStatus.STALE.value,
                        updated_at=utc(None),
                    )
                )
        return {
            "stale_checkpoint_ids": stale,
            "stale_count": len(stale),
            "authoritative_manifest_hash": current,
            "raw_memory_deleted": False,
        }


__all__ = ["MemoryConsolidationInvalidationService"]
