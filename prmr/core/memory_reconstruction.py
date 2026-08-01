"""Historical and current reconstruction over the resolved memory ledger."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from prmr.product.controlled_alpha_api_v071 import ALGORITHM_REVISION

from .memory_ledger_models import (
    BITEMPORAL_POLICY_REVISION,
    CONTINUITY_INPUT_RESOLVER_REVISION,
    MEMORY_RECONSTRUCTION_REVISION,
    MEMORY_STATE_RESOLVER_REVISION,
    MemoryLedgerError,
    MemoryReconstruction,
    MemoryTemporalBoundary,
)
from .memory_state_resolver import MemoryStateResolver
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_reconstruction")
CONTINUITY_INPUT_MODES = ("legacy_all_events", "resolved_memory_events_v1")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryReconstructionService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.resolver = MemoryStateResolver(repository, initialize=initialize)
        self.ledger = self.resolver.ledger
        self.bridge = self.resolver.admission.bridge
        self.backend = self.ledger.backend
        self.table = self.ledger.reconstruction_table
        self.placeholder = "%s" if self.backend == "postgres" else "?"

    def reconstruct_current_state(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        *,
        persist: bool = True,
    ) -> MemoryReconstruction:
        return self._reconstruct(
            authenticated_scope, MemoryTemporalBoundary(), subject_scope, persist
        )

    def reconstruct_at_valid_time(
        self,
        authenticated_scope: AuthenticatedScope,
        valid_at: str,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        *,
        persist: bool = True,
    ) -> MemoryReconstruction:
        return self._reconstruct(
            authenticated_scope,
            MemoryTemporalBoundary(valid_at=valid_at),
            subject_scope,
            persist,
        )

    def reconstruct_as_known_at(
        self,
        authenticated_scope: AuthenticatedScope,
        known_at: str,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        *,
        persist: bool = True,
    ) -> MemoryReconstruction:
        return self._reconstruct(
            authenticated_scope,
            MemoryTemporalBoundary(known_at=known_at),
            subject_scope,
            persist,
        )

    def reconstruct_bitemporal(
        self,
        authenticated_scope: AuthenticatedScope,
        valid_at: str,
        known_at: str,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        *,
        persist: bool = True,
    ) -> MemoryReconstruction:
        return self._reconstruct(
            authenticated_scope,
            MemoryTemporalBoundary(valid_at=valid_at, known_at=known_at),
            subject_scope,
            persist,
        )

    def compare_reconstructions(
        self,
        authenticated_scope: AuthenticatedScope,
        first_boundary: MemoryTemporalBoundary,
        second_boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
    ) -> dict[str, Any]:
        first = self._reconstruct(authenticated_scope, first_boundary, subject_scope)
        second = self._reconstruct(authenticated_scope, second_boundary, subject_scope)
        first_ids = set(first.effective_event_ids)
        second_ids = set(second.effective_event_ids)
        return {
            "first_reconstruction_id": first.reconstruction_id,
            "second_reconstruction_id": second.reconstruction_id,
            "added_event_ids": sorted(second_ids - first_ids),
            "removed_event_ids": sorted(first_ids - second_ids),
            "unchanged_event_ids": sorted(first_ids & second_ids),
            "changed": first.reconstruction_hash != second.reconstruction_hash,
            "comparison_revision": MEMORY_RECONSTRUCTION_REVISION,
        }

    def build_continuity_packet(
        self,
        authenticated_scope: AuthenticatedScope,
        *,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None = None,
        previous_packet: dict[str, Any] | None = None,
        input_mode: str = "resolved_memory_events_v1",
        include_conflicted: bool = True,
        event_ids: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any]:
        if input_mode not in CONTINUITY_INPUT_MODES:
            raise MemoryLedgerError(
                "MEMORY_CONTINUITY_RESOLUTION_FAILED",
                "Continuity input mode is unsupported.",
            )
        if input_mode == "legacy_all_events":
            events = self.resolver.admission._events_for_scope(authenticated_scope)
            return self.bridge.build_packet(
                authenticated_scope, events, previous_packet=previous_packet
            )
        kwargs = self._subject_kwargs(subject_scope)
        view = self.resolver.resolve_effective_events(
            authenticated_scope,
            temporal_boundary,
            include_conflicted=include_conflicted,
            event_ids=event_ids,
            **kwargs,
        )
        packet = self.bridge.build_packet(
            authenticated_scope,
            view.effective_events,
            previous_packet=previous_packet,
        )
        identity = self._identity(authenticated_scope, view, kwargs)
        reconstruction_hash = sha256_text(canonical_json(identity))
        packet["memory_ledger_context"] = {
            "resolver_revision": MEMORY_STATE_RESOLVER_REVISION,
            "continuity_input_resolver_revision": CONTINUITY_INPUT_RESOLVER_REVISION,
            "continuity_input_mode": input_mode,
            "temporal_boundary": view.temporal_boundary.to_dict(),
            "effective_event_count": len(view.effective_events),
            "superseded_event_count": view.excluded_counts.get("superseded", 0),
            "retracted_event_count": view.excluded_counts.get("retracted", 0),
            "invalidated_event_count": view.excluded_counts.get("invalidated", 0),
            "unresolved_conflict_count": len(view.open_conflicts),
            "resolved_conflict_count": len(view.resolved_conflicts),
            "evolution_record_count": view.evolution_record_count,
            "latest_evolution_id": view.latest_evolution_id,
            "reconstruction_hash": reconstruction_hash,
            "excluded_counts": dict(view.excluded_counts),
        }
        packet["unresolved_contradictions"] = [
            {
                "conflict_id": item.conflict_id,
                "conflict_type": item.conflict_type,
                "event_count": len(item.conflicting_event_ids),
                "status": "open",
                "resolution_event_id": None,
            }
            for item in view.open_conflicts
        ]
        return packet

    def _reconstruct(
        self,
        scope: AuthenticatedScope,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | AuthenticatedScope | None,
        persist: bool = True,
    ) -> MemoryReconstruction:
        kwargs = self._subject_kwargs(subject_scope)
        view = self.resolver.resolve_effective_events(scope, boundary, **kwargs)
        identity = self._identity(scope, view, kwargs)
        reconstruction_hash = sha256_text(canonical_json(identity))
        reconstruction_id = f"recon_{reconstruction_hash[:24]}"
        existing = self._load_by_identity(reconstruction_hash)
        if existing:
            LOGGER.info(
                "%s",
                json.dumps(
                    {
                        "event": "memory_reconstruction_replayed",
                        "reconstruction_id": reconstruction_id,
                    },
                    sort_keys=True,
                ),
            )
            return existing

        packet = self.build_continuity_packet(
            scope,
            temporal_boundary=boundary,
            subject_scope=subject_scope,
        )
        event_by_id = {
            str(item.get("event_id")): item for item in view.effective_events
        }
        ordered_ids = [str(item.get("event_id")) for item in view.effective_events]
        transitions = [
            {
                "event_id": event_id,
                "event_type": str(
                    event_by_id[event_id].get("type")
                    or event_by_id[event_id].get("event_type")
                    or "event.recorded"
                ),
                "valid_at": str(event_by_id[event_id].get("timestamp", "")),
                "sequence_index": index,
            }
            for index, event_id in enumerate(ordered_ids)
        ]
        projection_map = {item.event_id: item for item in view.projections}
        provenance = [
            {
                "event_id": event_id,
                "source_id": projection_map[event_id].source_id,
                "admission_id": projection_map[event_id].admission_id,
            }
            for event_id in ordered_ids
        ]
        result = MemoryReconstruction(
            reconstruction_id=reconstruction_id,
            temporal_boundary=view.temporal_boundary,
            subject_scope=kwargs,
            resolver_revision=MEMORY_STATE_RESOLVER_REVISION,
            effective_event_ids=ordered_ids,
            excluded_counts=dict(view.excluded_counts),
            open_conflicts=[
                self._safe_conflict(item, status="open") for item in view.open_conflicts
            ],
            resolved_conflicts=[
                self._safe_conflict(item, status="resolved")
                for item in view.resolved_conflicts
            ],
            ordered_state_transitions=transitions,
            reconstruction_hash=reconstruction_hash,
            provenance_references=provenance,
            continuity_packet=packet,
            generated_at=_now(),
            engine_revision=ALGORITHM_REVISION,
        )
        if persist:
            self._persist(reconstruction_hash, scope, result)
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_reconstruction_created",
                    "reconstruction_id": reconstruction_id,
                },
                sort_keys=True,
            ),
        )
        return result

    @staticmethod
    def _subject_kwargs(
        subject_scope: dict[str, str | None] | AuthenticatedScope | None,
    ) -> dict[str, str | None]:
        keys = (
            "application_reference",
            "actor_reference",
            "workspace_reference",
            "entity_reference",
            "session_reference",
        )
        if subject_scope is None:
            return {key: None for key in keys}
        if isinstance(subject_scope, AuthenticatedScope):
            return {key: getattr(subject_scope, key) for key in keys}
        return {key: subject_scope.get(key) for key in keys}

    @staticmethod
    def _identity(
        scope: AuthenticatedScope, view: Any, subject_scope: dict[str, Any]
    ) -> dict[str, Any]:
        projections = {item.event_id: item for item in view.projections}
        return {
            "scope": scope.memory_boundary(),
            "subject_scope": subject_scope,
            "temporal_boundary": view.temporal_boundary.to_dict(),
            "effective_events": [
                {
                    "event_id": str(event.get("event_id")),
                    "event_hash": projections[str(event.get("event_id"))].event_hash,
                }
                for event in view.effective_events
            ],
            "excluded_counts": view.excluded_counts,
            "open_conflicts": [item.conflict_id for item in view.open_conflicts],
            "resolved_conflicts": [item.conflict_id for item in view.resolved_conflicts],
            "evolutions": view.evolution_record_count,
            "latest_evolution_id": view.latest_evolution_id,
            "resolver_revision": MEMORY_STATE_RESOLVER_REVISION,
            "reconstruction_revision": MEMORY_RECONSTRUCTION_REVISION,
            "bitemporal_policy_revision": BITEMPORAL_POLICY_REVISION,
            "continuity_revision": ALGORITHM_REVISION,
        }

    @staticmethod
    def _safe_conflict(conflict: Any, *, status: str) -> dict[str, Any]:
        return {
            "conflict_id": conflict.conflict_id,
            "conflict_type": conflict.conflict_type,
            "event_count": len(conflict.conflicting_event_ids),
            "status": status,
            "resolution_event_id": (
                conflict.resolution_event_id if status == "resolved" else None
            ),
        }

    def _persist(
        self, identity: str, scope: AuthenticatedScope, result: MemoryReconstruction
    ) -> None:
        payload = result.to_dict()
        value: Any = canonical_json(payload)
        if self.backend == "postgres":
            value = json.loads(value)
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"INSERT INTO {self.table}("
                "reconstruction_id,reconstruction_identity,client_id,vault_id,namespace,"
                "valid_at,known_at,reconstruction_hash,payload_json,created_at"
                f") VALUES({','.join([self.placeholder] * 10)}) "
                "ON CONFLICT(reconstruction_identity) DO NOTHING",
                (
                    result.reconstruction_id,
                    identity,
                    *scope.memory_boundary(),
                    result.temporal_boundary.valid_at,
                    result.temporal_boundary.known_at,
                    result.reconstruction_hash,
                    value,
                    result.generated_at,
                ),
            )

    def _load_by_identity(self, identity: str) -> MemoryReconstruction | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.table} "
                f"WHERE reconstruction_identity={self.placeholder}",
                (identity,),
            ).fetchone()
        if not row:
            return None
        payload = row["payload_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload["temporal_boundary"] = MemoryTemporalBoundary(
            **payload["temporal_boundary"]
        )
        return MemoryReconstruction(**payload)


__all__ = ["CONTINUITY_INPUT_MODES", "MemoryReconstructionService"]
