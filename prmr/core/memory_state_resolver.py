"""Deterministic bitemporal projection over the admitted PRMR event ledger."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any

from .admission_models import MemoryAdmissionError
from .memory_ledger_models import (
    BITEMPORAL_POLICY_REVISION,
    MEMORY_STATE_RESOLVER_REVISION,
    MemoryConflict,
    MemoryEventProjection,
    MemoryEventState,
    MemoryLedgerError,
    MemoryTemporalBoundary,
    ResolvedMemoryView,
)
from .memory_ledger_service import MemoryLedgerService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_state_resolver")
def _utc(value: str | None, *, default: str | None = None) -> str:
    raw = value or default
    if raw is None:
        raw = datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryLedgerError(
            "MEMORY_TEMPORAL_BOUNDARY_INVALID", "Temporal boundary is invalid."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_time(event: dict[str, Any]) -> str:
    return _utc(str(event.get("timestamp") or event.get("occurred_at") or ""))


def _subject_value(event: dict[str, Any], field: str) -> str | None:
    value = event.get(field)
    if value in (None, ""):
        value = (
            event.get("external_metadata", {}).get(field)
            if isinstance(event.get("external_metadata"), dict)
            else None
        )
    return str(value) if value not in (None, "") else None


class MemoryStateResolver:
    """Resolve current or historical effective memory without mutating history."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.ledger = MemoryLedgerService(repository, initialize=initialize)
        self.admission = self.ledger.admission

    def resolve_effective_events(
        self,
        authenticated_scope: AuthenticatedScope,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        *,
        application_reference: str | None = None,
        actor_reference: str | None = None,
        workspace_reference: str | None = None,
        entity_reference: str | None = None,
        session_reference: str | None = None,
        include_conflicted: bool = True,
        event_ids: set[str] | frozenset[str] | None = None,
    ) -> ResolvedMemoryView:
        started = time.perf_counter()
        requested = {
            "application_reference": application_reference,
            "actor_reference": actor_reference,
            "workspace_reference": workspace_reference,
            "entity_reference": entity_reference,
            "session_reference": session_reference,
        }
        assertions = {
            key: value
            for key, value in {
                "application_reference": authenticated_scope.application_reference,
                "actor_reference": authenticated_scope.actor_reference,
                "workspace_reference": authenticated_scope.workspace_reference,
                "entity_reference": authenticated_scope.entity_reference,
                "session_reference": authenticated_scope.session_reference,
            }.items()
            if value
        }
        for key, asserted in assertions.items():
            if requested[key] not in (None, asserted):
                raise MemoryLedgerError(
                    "MEMORY_EVENT_SCOPE_DENIED",
                    "Requested subject scope conflicts with authenticated scope.",
                )
            requested[key] = asserted

        boundary = temporal_boundary or MemoryTemporalBoundary()
        resolved_now = _utc(None)
        valid_at = _utc(boundary.valid_at, default=resolved_now)
        known_at = _utc(boundary.known_at, default=resolved_now)
        normal_boundary = MemoryTemporalBoundary(
            valid_at=boundary.valid_at and valid_at,
            known_at=boundary.known_at and known_at,
        )

        events = self.admission._events_for_scope(authenticated_scope)
        link_by_event: dict[str, Any] = {}
        admission_by_id: dict[str, Any] = {}
        p = self.admission._placeholder
        with self.repository.connect() as connection:
            link_rows = connection.execute(
                f"SELECT * FROM {self.admission.link_table} "
                f"WHERE client_id={p} AND vault_id={p} AND namespace={p}",
                authenticated_scope.memory_boundary(),
            ).fetchall()
            admission_rows = connection.execute(
                f"SELECT * FROM {self.admission.admission_table} "
                f"WHERE client_id={p} AND vault_id={p} AND namespace={p}",
                authenticated_scope.memory_boundary(),
            ).fetchall()
        for row in link_rows:
            link = self.admission._link_from_row(row)
            link_by_event[link.admitted_event_id] = link
        for row in admission_rows:
            admission = self.admission._decision_from_row(row)
            admission_by_id[admission.admission_id] = admission
        evolutions = [
            item
            for item in self.ledger.list_evolutions(authenticated_scope)
            if item.evolution_status in {"completed", "replayed"}
            and item.system_effective_at <= known_at
            and item.valid_from <= valid_at
        ]
        all_conflicts = self.ledger.list_conflicts(authenticated_scope)

        projections: dict[str, MemoryEventProjection] = {}
        event_map: dict[str, dict[str, Any]] = {}
        excluded: dict[str, int] = {
            "superseded": 0,
            "retracted": 0,
            "invalidated": 0,
            "outside_valid_time": 0,
            "not_yet_known": 0,
            "outside_subject_scope": 0,
            "resolved_conflict": 0,
            "conflicted": 0,
            "outside_event_set": 0,
        }

        for event in events:
            event_id = str(event.get("event_id", ""))
            if not event_id:
                continue
            event_map[event_id] = event
            valid_from = _event_time(event)
            link = link_by_event.get(event_id)
            admission = admission_by_id.get(link.admission_id) if link else None
            # Legacy external events remain usable. Their persisted event time is
            # the only honest known-time anchor available.
            system_known_from = _utc(
                admission.completed_at if admission and admission.completed_at else valid_from
            )
            metadata = event.get("external_metadata", {}).get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            projection = MemoryEventProjection(
                event_id=event_id,
                effective_state=MemoryEventState.ACTIVE.value,
                valid_from=valid_from,
                valid_until=None,
                system_known_from=system_known_from,
                system_known_until=None,
                superseded_by_event_id=None,
                correction_event_id=None,
                retraction_evolution_id=None,
                open_conflict_ids=[],
                resolved_conflict_ids=[],
                epistemic_status=str(metadata.get("epistemic_status", "legacy_unclassified")),
                event_type=str(event.get("type") or event.get("event_type") or "event.recorded"),
                event_hash=sha256_text(canonical_json(event)),
                source_id=link.source_id if link else None,
                admission_id=link.admission_id if link else None,
            )
            projections[event_id] = projection

        # Evolution records are authoritative and append-only. Processing is
        # deterministic, including when review/admission order differs.
        for evolution in sorted(
            evolutions, key=lambda item: (item.system_effective_at, item.evolution_id)
        ):
            projection = projections.get(evolution.source_event_id)
            if projection is None:
                continue
            if evolution.evolution_type in {"correct", "supersede"}:
                projection = replace(
                    projection,
                    effective_state=MemoryEventState.SUPERSEDED.value,
                    valid_until=evolution.valid_from,
                    system_known_until=evolution.system_effective_at,
                    superseded_by_event_id=evolution.replacement_event_id,
                    correction_event_id=(
                        evolution.replacement_event_id
                        if evolution.evolution_type == "correct"
                        else None
                    ),
                )
            elif evolution.evolution_type == "retract":
                projection = replace(
                    projection,
                    effective_state=MemoryEventState.RETRACTED.value,
                    system_known_until=evolution.system_effective_at,
                    retraction_evolution_id=evolution.evolution_id,
                )
            elif evolution.evolution_type == "invalidate":
                projection = replace(
                    projection,
                    effective_state=MemoryEventState.INVALIDATED.value,
                    system_known_until=evolution.system_effective_at,
                )
            projections[evolution.source_event_id] = projection

        open_conflicts: list[MemoryConflict] = []
        resolved_conflicts: list[MemoryConflict] = []
        for conflict in sorted(
            all_conflicts, key=lambda item: (item.system_effective_at, item.conflict_id)
        ):
            if conflict.system_effective_at > known_at or conflict.valid_from > valid_at:
                continue
            resolved_by_boundary = bool(
                conflict.resolved_at
                and conflict.resolution_event_id
                and conflict.resolved_at <= known_at
            )
            if resolved_by_boundary:
                historical = replace(conflict, conflict_status="resolved")
                resolved_conflicts.append(historical)
                for event_id in conflict.conflicting_event_ids:
                    projection = projections.get(event_id)
                    if projection:
                        projections[event_id] = replace(
                            projection,
                            effective_state=MemoryEventState.RESOLVED.value,
                            resolved_conflict_ids=sorted(
                                set(projection.resolved_conflict_ids + [conflict.conflict_id])
                            ),
                        )
            else:
                historical = replace(
                    conflict,
                    conflict_status="open",
                    resolution_event_id=None,
                    resolved_at=None,
                    resolution_reason=None,
                )
                open_conflicts.append(historical)
                for event_id in conflict.conflicting_event_ids:
                    projection = projections.get(event_id)
                    if projection and projection.effective_state == MemoryEventState.ACTIVE.value:
                        projections[event_id] = replace(
                            projection,
                            effective_state=MemoryEventState.CONFLICTED.value,
                            open_conflict_ids=sorted(
                                set(projection.open_conflict_ids + [conflict.conflict_id])
                            ),
                        )

        effective: list[dict[str, Any]] = []
        ordered_projections: list[MemoryEventProjection] = []
        for event_id, event in sorted(
            event_map.items(),
            key=lambda item: (
                int(item[1].get("timestamp_index", 0)),
                str(item[1].get("timestamp", "")),
                item[0],
            ),
        ):
            projection = projections[event_id]
            reason: str | None = None
            if projection.system_known_from > known_at:
                reason = "not_yet_known"
            elif projection.valid_from > valid_at:
                reason = "outside_valid_time"
            elif any(
                requested[key] is not None
                and _subject_value(event, key) != str(requested[key])
                for key in requested
            ):
                reason = "outside_subject_scope"
            elif event_ids is not None and event_id not in event_ids:
                reason = "outside_event_set"
            elif projection.effective_state == MemoryEventState.SUPERSEDED.value:
                reason = "superseded"
            elif projection.effective_state == MemoryEventState.RETRACTED.value:
                reason = "retracted"
            elif projection.effective_state == MemoryEventState.INVALIDATED.value:
                reason = "invalidated"
            elif projection.effective_state == MemoryEventState.RESOLVED.value:
                reason = "resolved_conflict"
            elif (
                projection.effective_state == MemoryEventState.CONFLICTED.value
                and not include_conflicted
            ):
                reason = "conflicted"

            if reason:
                excluded[reason] += 1
            else:
                effective.append(event)
            ordered_projections.append(projection)

        latest = max(
            evolutions,
            key=lambda item: (item.system_effective_at, item.evolution_id),
            default=None,
        )
        result = ResolvedMemoryView(
            effective_events=effective,
            projections=ordered_projections,
            excluded_counts=excluded,
            open_conflicts=open_conflicts,
            resolved_conflicts=resolved_conflicts,
            temporal_boundary=normal_boundary,
            evolution_record_count=len(evolutions),
            latest_evolution_id=latest.evolution_id if latest else None,
        )
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_state_resolved",
                    "event_count": len(effective),
                    "excluded_count": sum(excluded.values()),
                    "resolver_revision": MEMORY_STATE_RESOLVER_REVISION,
                    "bitemporal_policy_revision": BITEMPORAL_POLICY_REVISION,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "scope_fingerprint": sha256_text(
                        canonical_json(authenticated_scope.memory_boundary())
                    )[:16],
                },
                sort_keys=True,
            ),
        )
        return result


__all__ = ["MemoryStateResolver"]
