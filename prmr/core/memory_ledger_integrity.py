"""Read-only integrity verification for bitemporal memory evolution."""

from __future__ import annotations

import json
import logging
from typing import Any

from .memory_ledger_models import (
    MEMORY_RECONSTRUCTION_REVISION,
    MemoryLedgerIntegrityResult,
    MemoryTemporalBoundary,
)
from .memory_reconstruction import MemoryReconstructionService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_ledger_integrity")


class MemoryLedgerIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.reconstruction = MemoryReconstructionService(
            repository, initialize=initialize
        )
        self.ledger = self.reconstruction.ledger
        self.resolver = self.reconstruction.resolver
        self.repository = repository

    def verify_memory_ledger_integrity(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
    ) -> MemoryLedgerIntegrityResult:
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}
        events = self.resolver.admission._events_for_scope(authenticated_scope)
        event_map = {str(item.get("event_id")): item for item in events}
        evolutions = self.ledger.list_evolutions(authenticated_scope)
        conflicts = self.ledger.list_conflicts(authenticated_scope)

        admitted_integrity: list[bool] = []
        for event_id, event in event_map.items():
            metadata = event.get("external_metadata", {}).get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("memory_origin") != "candidate_admission":
                continue
            try:
                link = self.resolver.admission.get_admitted_memory_link(
                    authenticated_scope, event_id
                )
                admitted_integrity.append(
                    self.resolver.admission.verify_admission_integrity(
                        authenticated_scope, link.admission_id
                    ).verified
                )
            except Exception:
                admitted_integrity.append(False)
        checks["admitted_provenance"] = all(admitted_integrity)
        checks["evolution_sources_exist"] = all(
            item.source_event_id in event_map for item in evolutions
        )
        checks["replacement_events_exist"] = all(
            item.replacement_event_id is None
            or item.replacement_event_id in event_map
            for item in evolutions
        )
        checks["evolution_hashes_match"] = all(
            item.source_event_id in event_map
            and item.source_event_hash
            == sha256_text(canonical_json(event_map[item.source_event_id]))
            and (
                item.replacement_event_id is None
                or (
                    item.replacement_event_id in event_map
                    and item.replacement_event_hash
                    == sha256_text(
                        canonical_json(event_map[item.replacement_event_id])
                    )
                )
            )
            for item in evolutions
        )

        graph: dict[str, set[str]] = {}
        terminal_by_source: dict[str, list[Any]] = {}
        for item in evolutions:
            if item.evolution_type in {"correct", "supersede"} and item.replacement_event_id:
                graph.setdefault(item.source_event_id, set()).add(
                    item.replacement_event_id
                )
            if item.evolution_type in {
                "correct",
                "supersede",
                "retract",
                "invalidate",
            } and item.evolution_status in {"completed", "replayed"}:
                terminal_by_source.setdefault(item.source_event_id, []).append(item)
        checks["no_evolution_cycles"] = not self._has_cycle(graph)
        checks["single_terminal_evolution_per_event"] = all(
            len(items) <= 1 for items in terminal_by_source.values()
        )
        checks["retractions_reference_events"] = all(
            item.source_event_id in event_map
            for item in evolutions
            if item.evolution_type == "retract"
        )
        checks["conflicts_have_valid_events"] = all(
            len(set(item.conflicting_event_ids)) >= 2
            and all(event_id in event_map for event_id in item.conflicting_event_ids)
            for item in conflicts
        )
        checks["resolved_conflicts_complete"] = all(
            item.conflict_status != "resolved"
            or (
                bool(item.resolution_event_id)
                and item.resolution_event_id in event_map
                and bool(item.resolved_at)
                and bool(item.resolution_reason)
            )
            for item in conflicts
        )
        resolution_records = [
            item for item in evolutions if item.evolution_type == "resolve_contradiction"
        ]
        checks["single_resolution_per_conflict"] = len(
            {item.conflict_id for item in resolution_records}
        ) == len(resolution_records)

        try:
            kwargs = self.reconstruction._subject_kwargs(subject_scope)
            current = self.resolver.resolve_effective_events(
                authenticated_scope, **kwargs
            )
            event_ids = set(event_map)
            projection_ids = {item.event_id for item in current.projections}
            checks["projections_cover_ledger"] = projection_ids == event_ids
            checks["inactive_history_preserved"] = all(
                item.source_event_id in event_ids for item in evolutions
            )
            packet = self.reconstruction.build_continuity_packet(
                authenticated_scope, subject_scope=subject_scope
            )
            context = packet["memory_ledger_context"]
            checks["packet_exclusions_match"] = (
                context["excluded_counts"] == current.excluded_counts
                and context["effective_event_count"] == len(current.effective_events)
            )
        except Exception:
            checks["projections_cover_ledger"] = False
            checks["inactive_history_preserved"] = False
            checks["packet_exclusions_match"] = False

        reconstruction_rows = self._reconstruction_rows(authenticated_scope)
        reconstruction_checks: list[bool] = []
        reconstruction_failures: list[dict[str, Any]] = []
        for row in reconstruction_rows:
            payload = row["payload_json"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            boundary = MemoryTemporalBoundary(**payload["temporal_boundary"])
            kwargs = dict(payload.get("subject_scope") or {})
            try:
                view = self.resolver.resolve_effective_events(
                    authenticated_scope, boundary, **kwargs
                )
                identity = self.reconstruction._identity(
                    authenticated_scope, view, kwargs
                )
                digest = sha256_text(canonical_json(identity))
                passed = (
                    digest == row["reconstruction_identity"]
                    and digest == row["reconstruction_hash"]
                    and digest == payload["reconstruction_hash"]
                    and payload["reconstruction_id"] == f"recon_{digest[:24]}"
                    and payload["memory_reconstruction_revision"]
                    == MEMORY_RECONSTRUCTION_REVISION
                )
                reconstruction_checks.append(passed)
                if not passed:
                    reconstruction_failures.append(
                        {
                            "reconstruction_id": payload.get("reconstruction_id"),
                            "stored_hash_prefix": str(row["reconstruction_hash"])[:16],
                            "recomputed_hash_prefix": digest[:16],
                            "temporal_boundary": payload.get("temporal_boundary"),
                        }
                    )
            except Exception as exc:
                reconstruction_checks.append(False)
                reconstruction_failures.append(
                    {
                        "reconstruction_id": payload.get("reconstruction_id"),
                        "error_type": type(exc).__name__,
                    }
                )
        checks["reconstruction_hashes_reproduce"] = all(reconstruction_checks)

        details.update(
            {
                "event_count": len(events),
                "admitted_event_count": len(admitted_integrity),
                "evolution_count": len(evolutions),
                "conflict_count": len(conflicts),
                "reconstruction_count": len(reconstruction_rows),
                "reconstruction_failures": reconstruction_failures,
            }
        )
        failures = [name for name, passed in checks.items() if not passed]
        result = MemoryLedgerIntegrityResult(
            verified=not failures,
            checks=checks,
            failures=failures,
            details=details,
        )
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": (
                        "memory_ledger_integrity_verified"
                        if result.verified
                        else "memory_ledger_integrity_failed"
                    ),
                    "event_count": len(events),
                    "error_code": None if result.verified else "MEMORY_LEDGER_INTEGRITY_FAILED",
                },
                sort_keys=True,
            ),
        )
        return result

    def _reconstruction_rows(self, scope: AuthenticatedScope) -> list[Any]:
        p = self.reconstruction.placeholder
        with self.repository.connect() as connection:
            return list(
                connection.execute(
                    f"SELECT * FROM {self.reconstruction.table} "
                    f"WHERE client_id={p} AND vault_id={p} AND namespace={p}",
                    scope.memory_boundary(),
                ).fetchall()
            )

    @staticmethod
    def _has_cycle(graph: dict[str, set[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(child) for child in graph.get(node, ())):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)


def verify_memory_ledger_integrity(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
) -> MemoryLedgerIntegrityResult:
    return MemoryLedgerIntegrityVerifier(repository).verify_memory_ledger_integrity(
        authenticated_scope, subject_scope
    )


__all__ = [
    "MemoryLedgerIntegrityVerifier",
    "verify_memory_ledger_integrity",
]
