"""Deterministic, read-only planning for exact structural consolidation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .memory_consolidation_membership import (
    deterministic_windows,
    event_manifest,
    fast_authoritative_manifest,
    group_exact_signals,
)
from .memory_consolidation_models import (
    MEMORY_CHECKPOINT_REVISION,
    MEMORY_CONSOLIDATION_MANIFEST_REVISION,
    MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
    MEMORY_CONSOLIDATION_PLANNER_REVISION,
    MEMORY_CONSOLIDATION_POLICY_REVISION,
    MEMORY_CONSOLIDATION_SCHEMA_REVISION,
    MemoryCheckpointStatus,
    MemoryConsolidationError,
    MemoryConsolidationPlan,
    MemoryConsolidationPolicy,
    MemoryConsolidationType,
)
from .memory_consolidation_policy import policy_from_id, validate_policy
from .memory_consolidation_store import MemoryConsolidationStore
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_query_results import signal_key_for_event
from .memory_state_resolver import MemoryStateResolver
from .relationship_memory import RelationshipMemoryService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


def utc(value: str | None) -> str:
    raw = value or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


DEFAULT_CONSOLIDATION_TYPES = tuple(item.value for item in MemoryConsolidationType)


class MemoryConsolidationPlanner:
    """Freeze scope, manifests, windows, groups, and rebuild requirements."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.state = MemoryStateResolver(repository, initialize=initialize)
        self.dynamics = MemoryDynamicsEngine(repository, initialize=initialize)
        self.relationships = RelationshipMemoryService(repository, initialize=initialize)
        self.store = MemoryConsolidationStore(repository, initialize=initialize)

    def plan_consolidation(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        consolidation_types: list[str] | tuple[str, ...] | None = None,
        policy_id: str = "exact_structural_v1",
    ) -> MemoryConsolidationPlan:
        plan, _ = self.plan_consolidation_with_context(
            authenticated_scope,
            subject_scope,
            temporal_boundary=temporal_boundary,
            consolidation_types=consolidation_types,
            policy_id=policy_id,
        )
        return plan

    def plan_consolidation_with_context(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        consolidation_types: list[str] | tuple[str, ...] | None = None,
        policy_id: str = "exact_structural_v1",
        *,
        policy: MemoryConsolidationPolicy | None = None,
    ) -> tuple[MemoryConsolidationPlan, dict[str, Any]]:
        selected = validate_policy(policy or policy_from_id(policy_id))
        if selected.consolidation_mode == "disabled":
            raise MemoryConsolidationError(
                "MEMORY_ACCELERATION_UNSUPPORTED",
                "Consolidation is disabled by policy.",
            )
        requested_types = list(consolidation_types or DEFAULT_CONSOLIDATION_TYPES)
        allowed = set(DEFAULT_CONSOLIDATION_TYPES)
        if not requested_types or set(requested_types) - allowed:
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_POLICY_INVALID",
                "Consolidation type is not supported.",
            )
        subject = self._subject_scope(authenticated_scope, subject_scope or {})
        temporal_subject = {
            "application_reference": subject.get("application_reference"),
            "actor_reference": subject.get("actor_reference"),
            "workspace_reference": subject.get("workspace_reference"),
            "entity_reference": subject.get("entity_id"),
            "session_reference": subject.get("session_reference"),
        }
        now = utc(None)
        boundary = temporal_boundary or MemoryTemporalBoundary()
        valid_at = utc(boundary.valid_at or now)
        known_at = utc(boundary.known_at or now)
        frozen = MemoryTemporalBoundary(valid_at=valid_at, known_at=known_at)
        view = self.state.resolve_effective_events(
            authenticated_scope,
            frozen,
            **{
                key: value
                for key, value in temporal_subject.items()
                if value is not None
            },
            include_conflicted=True,
        )
        if len(view.effective_events) > selected.maximum_events_per_consolidation:
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_LIMIT_EXCEEDED",
                "Effective event count exceeds the consolidation policy limit.",
                details={
                    "effective_event_count": len(view.effective_events),
                    "maximum_events_per_consolidation": (
                        selected.maximum_events_per_consolidation
                    ),
                },
            )
        dynamics = self.dynamics.compute_memory_dynamics(
            authenticated_scope, temporal_subject, frozen, persist=False
        )
        relationship_view = self.relationships.resolve_effective_relationships(
            authenticated_scope,
            entity_id=subject.get("entity_id"),
            temporal_boundary=frozen,
            include_conflicted=True,
        )
        events = list(view.effective_events)
        windows = deterministic_windows(
            events,
            selected.checkpoint_interval_event_count,
            policy_revision=selected.policy_revision,
        )
        groups = group_exact_signals(
            events, windows, selected.minimum_events_per_signal_group
        )
        fast_manifest = fast_authoritative_manifest(
            self.repository, authenticated_scope
        )
        category = fast_manifest["category_hashes"]
        effective_hash = event_manifest(events)
        projections = [item.to_dict() for item in view.projections]
        conflict_hash = sha256_text(
            canonical_json(
                {
                    "open": [item.to_dict() for item in view.open_conflicts],
                    "resolved": [item.to_dict() for item in view.resolved_conflicts],
                }
            )
        )
        dependencies = {
            "authoritative_event_manifest_hash": fast_manifest[
                "authoritative_manifest_hash"
            ],
            "effective_event_manifest_hash": effective_hash,
            "ledger_evolution_manifest_hash": category.get(
                "prmr_memory_evolution_records", sha256_text("[]")
            ),
            "importance_annotation_manifest_hash": category.get(
                "prmr_memory_importance_annotations", sha256_text("[]")
            ),
            "entity_manifest_hash": sha256_text(
                canonical_json(
                    {
                        "entities": category.get("prmr_entities"),
                        "identifiers": category.get("prmr_entity_identifiers"),
                        "aliases": category.get("prmr_entity_alias_assertions"),
                        "merges": category.get("prmr_entity_merges"),
                        "links": category.get("prmr_event_entity_links"),
                    }
                )
            ),
            "relationship_manifest_hash": sha256_text(
                canonical_json(
                    {
                        "relationships": category.get("prmr_relationships"),
                        "evolutions": category.get(
                            "prmr_relationship_evolution_records"
                        ),
                        "conflicts": category.get("prmr_relationship_conflicts"),
                    }
                )
            ),
            "conflict_manifest_hash": conflict_hash,
            "signal_dynamics_manifest_hash": (
                dynamics.snapshot.signal_dynamics_manifest_hash
            ),
            "state_resolver_revision": view.resolver_revision,
            "policy_revision": selected.policy_revision,
            "checkpoint_revision": MEMORY_CHECKPOINT_REVISION,
        }
        compatible = self._compatible_checkpoint(
            authenticated_scope, subject, valid_at, known_at
        )
        incremental = self._incremental_eligibility(
            compatible, events, dependencies
        )
        full_rebuild = not incremental["eligible"]
        planned_groups = [
            {
                "consolidation_type": MemoryConsolidationType.EXACT_SIGNAL_WINDOW.value,
                **group,
            }
            for group in groups
        ]
        if len(events) >= selected.minimum_events_per_state_chain:
            by_signal: dict[str, list[str]] = {}
            for event in events:
                by_signal.setdefault(signal_key_for_event(event), []).append(
                    str(event["event_id"])
                )
            planned_groups.extend(
                {
                    "consolidation_type": MemoryConsolidationType.EVENT_STATE_CHAIN.value,
                    "group_key": f"state:{signal}",
                    "signal_key": signal,
                    "event_ids": ids,
                    "event_count": len(ids),
                    "event_manifest_hash": sha256_text(canonical_json(ids)),
                }
                for signal, ids in sorted(by_signal.items())
                if len(ids) >= selected.minimum_events_per_state_chain
            )
        material = {
            "scope": list(authenticated_scope.memory_boundary()),
            "subject_scope": subject,
            "temporal_boundary": {"valid_at": valid_at, "known_at": known_at},
            "types": requested_types,
            "windows": windows,
            "eligible_event_ids": [str(item["event_id"]) for item in events],
            "excluded_event_counts": view.excluded_counts,
            "eligible_signal_keys": sorted(
                {signal_key_for_event(item) for item in events}
            ),
            "eligible_entity_ids": sorted(
                {
                    str(item.get("entity_reference"))
                    for item in events
                    if item.get("entity_reference")
                }
            ),
            "eligible_relationship_ids": sorted(
                item.relationship_id
                for item in relationship_view.effective_relationships
            ),
            "open_conflict_ids": sorted(
                item.conflict_id for item in view.open_conflicts
            ),
            "groups": planned_groups,
            "full_rebuild_required": full_rebuild,
            "incremental_from_checkpoint_id": (
                compatible.memory_checkpoint_id
                if compatible and incremental["eligible"]
                else None
            ),
            "dependencies": dependencies,
            "revisions": {
                "schema": MEMORY_CONSOLIDATION_SCHEMA_REVISION,
                "policy": MEMORY_CONSOLIDATION_POLICY_REVISION,
                "planner": MEMORY_CONSOLIDATION_PLANNER_REVISION,
                "membership": MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
                "manifest": MEMORY_CONSOLIDATION_MANIFEST_REVISION,
                "checkpoint": MEMORY_CHECKPOINT_REVISION,
            },
        }
        # Execution strategy is deliberately excluded: incremental application and
        # a fresh full rebuild over the same authoritative state must converge on
        # the same run/checkpoint identity.
        identity_material = {
            key: value
            for key, value in material.items()
            if key
            not in {
                "full_rebuild_required",
                "incremental_from_checkpoint_id",
            }
        }
        run_identity = sha256_text(canonical_json(identity_material))
        plan_hash = sha256_text(
            canonical_json(
                {
                    "run_identity": run_identity,
                    "steps": [
                        "scope_resolved",
                        "temporal_boundary_frozen",
                        "state_resolved",
                        "dynamics_loaded",
                        "relationship_state_loaded",
                        "authoritative_manifests_calculated",
                        "compatible_checkpoint_checked",
                        "incremental_or_rebuild_selected",
                        "deterministic_windows_built",
                        "exact_groups_built",
                    ],
                }
            )
        )
        plan = MemoryConsolidationPlan(
            consolidation_plan_id=f"mcplan_{plan_hash[:24]}",
            consolidation_run_identity_hash=run_identity,
            consolidation_types=requested_types,
            subject_scope=subject,
            temporal_boundary={"valid_at": valid_at, "known_at": known_at},
            deterministic_windows=windows,
            eligible_event_ids=[str(item["event_id"]) for item in events],
            excluded_event_counts=dict(view.excluded_counts),
            eligible_signal_keys=material["eligible_signal_keys"],
            eligible_entity_ids=material["eligible_entity_ids"],
            eligible_relationship_ids=material["eligible_relationship_ids"],
            open_conflict_ids=material["open_conflict_ids"],
            planned_groups=planned_groups,
            full_rebuild_required=full_rebuild,
            incremental_from_checkpoint_id=material[
                "incremental_from_checkpoint_id"
            ],
            invalidation_dependencies=dependencies,
            planner_revision=MEMORY_CONSOLIDATION_PLANNER_REVISION,
            plan_hash_sha256=plan_hash,
            created_at=known_at,
        )
        return plan, {
            "policy": selected,
            "view": view,
            "dynamics": dynamics,
            "relationship_view": relationship_view,
            "fast_manifest": fast_manifest,
            "projections": projections,
            "compatible_checkpoint": compatible,
            "incremental": incremental,
        }

    def _compatible_checkpoint(
        self,
        scope: AuthenticatedScope,
        subject: dict[str, str | None],
        valid_at: str,
        known_at: str,
    ) -> Any:
        for checkpoint in self.store.list_checkpoints(
            scope, statuses=(MemoryCheckpointStatus.CURRENT.value,)
        ):
            if (
                checkpoint.application_reference
                == subject.get("application_reference")
                and checkpoint.actor_reference == subject.get("actor_reference")
                and checkpoint.workspace_reference
                == subject.get("workspace_reference")
                and checkpoint.entity_id == subject.get("entity_id")
                and checkpoint.relationship_id == subject.get("relationship_id")
                and checkpoint.session_reference
                == subject.get("session_reference")
                and checkpoint.valid_at <= valid_at
                and checkpoint.known_at <= known_at
            ):
                return checkpoint
        return None

    @staticmethod
    def _incremental_eligibility(
        checkpoint: Any,
        events: list[dict[str, Any]],
        dependencies: dict[str, str],
    ) -> dict[str, Any]:
        if checkpoint is None:
            return {"eligible": False, "reason": "no_compatible_checkpoint"}
        old_ids = list(
            checkpoint.deterministic_state_payload.get("effective_event_ids", [])
        )
        current_ids = [str(item["event_id"]) for item in events]
        stable = (
            checkpoint.evolution_manifest_hash
            == dependencies["ledger_evolution_manifest_hash"]
            and checkpoint.importance_manifest_hash
            == dependencies["importance_annotation_manifest_hash"]
            and checkpoint.entity_manifest_hash
            == dependencies["entity_manifest_hash"]
            and checkpoint.relationship_manifest_hash
            == dependencies["relationship_manifest_hash"]
            and checkpoint.conflict_manifest_hash
            == dependencies["conflict_manifest_hash"]
        )
        prefix = current_ids[: len(old_ids)] == old_ids
        append_only = len(current_ids) >= len(old_ids) and prefix
        added_events = events[len(old_ids) :] if prefix else []
        late_arrival = bool(
            checkpoint.window_end
            and any(
                str(item.get("timestamp") or item.get("occurred_at") or "")
                <= checkpoint.window_end
                for item in added_events
            )
        )
        return {
            "eligible": bool(
                stable
                and append_only
                and len(current_ids) > len(old_ids)
                and not late_arrival
            ),
            "reason": (
                "append_safe"
                if stable
                and append_only
                and len(current_ids) > len(old_ids)
                and not late_arrival
                else "late_arriving_event_requires_rebuild"
                if late_arrival
                else "authoritative_history_or_revision_changed"
            ),
            "events_added": current_ids[len(old_ids) :] if prefix else [],
            "late_arrival": late_arrival,
        }

    @staticmethod
    def _subject_scope(
        scope: AuthenticatedScope, requested: dict[str, str | None]
    ) -> dict[str, str | None]:
        mapping = {
            "application_reference": scope.application_reference,
            "actor_reference": scope.actor_reference,
            "workspace_reference": scope.workspace_reference,
            "entity_id": scope.entity_reference,
            "session_reference": scope.session_reference,
        }
        output = {
            "application_reference": requested.get("application_reference"),
            "actor_reference": requested.get("actor_reference"),
            "workspace_reference": requested.get("workspace_reference"),
            "entity_id": requested.get("entity_id")
            or requested.get("entity_reference"),
            "relationship_id": requested.get("relationship_id"),
            "session_reference": requested.get("session_reference"),
        }
        for key, asserted in mapping.items():
            if asserted and output.get(key) not in (None, asserted):
                raise MemoryConsolidationError(
                    "MEMORY_CONSOLIDATION_SCOPE_DENIED",
                    "Requested subject scope conflicts with authenticated scope.",
                )
            if asserted:
                output[key] = asserted
        return output


__all__ = [
    "DEFAULT_CONSOLIDATION_TYPES",
    "MemoryConsolidationPlanner",
    "utc",
]
