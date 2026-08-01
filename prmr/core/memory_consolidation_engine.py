"""Exact structural consolidation over the authoritative PRMR memory ledger."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime
import logging
import time
from typing import Any

from .memory_checkpoint import (
    build_checkpoint_delta,
    compare_checkpoints as compare_checkpoint_payloads,
    finalize_checkpoint,
)
from .memory_consolidation_membership import (
    build_event_members,
    event_manifest,
    fast_authoritative_manifest,
)
from .memory_consolidation_models import (
    MEMORY_CHECKPOINT_DELTA_REVISION,
    MEMORY_CHECKPOINT_REVISION,
    MEMORY_CONSOLIDATION_COMPARISON_REVISION,
    MEMORY_CONSOLIDATION_CONTINUITY_ADAPTER_REVISION,
    MEMORY_CONSOLIDATION_INTEGRITY_REVISION,
    MEMORY_CONSOLIDATION_INVALIDATION_REVISION,
    MEMORY_CONSOLIDATION_MANIFEST_REVISION,
    MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
    MEMORY_CONSOLIDATION_PLANNER_REVISION,
    MEMORY_CONSOLIDATION_POLICY_REVISION,
    MEMORY_CONSOLIDATION_QUERY_ADAPTER_REVISION,
    MEMORY_CONSOLIDATION_SCHEMA_REVISION,
    ConsolidatedMemory,
    ConsolidatedMemoryMember,
    MemoryCheckpoint,
    MemoryCheckpointStatus,
    MemoryConsolidationError,
    MemoryConsolidationInvalidation,
    MemoryConsolidationRun,
    MemoryConsolidationStatus,
    MemoryConsolidationType,
)
from .memory_consolidation_planner import MemoryConsolidationPlanner, utc
from .memory_consolidation_store import MemoryConsolidationStore
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_query_engine import MemoryQueryEngine
from .memory_query_models import MemoryQueryRequest, MemoryQueryType
from .memory_query_results import event_time, signal_key_for_event
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_consolidation")


SUPPORTED_ACCELERATED_QUERY_TYPES = {
    MemoryQueryType.CURRENT_STATE.value,
    MemoryQueryType.MEMORY_BY_PHASE.value,
    MemoryQueryType.SIGNAL_HISTORY.value,
    MemoryQueryType.RECURRENCE.value,
    MemoryQueryType.RE_EMERGENCE.value,
    MemoryQueryType.OPEN_CONFLICTS.value,
    MemoryQueryType.RESOLVED_CONFLICTS.value,
    MemoryQueryType.ENTITY_STATE.value,
    MemoryQueryType.RELATIONSHIP_STATE.value,
    MemoryQueryType.CONTINUITY_PACKET.value,
}


def consolidation_query_key(request: MemoryQueryRequest) -> str:
    material = request.to_dict()
    material["revisions"] = {
        "query_adapter": MEMORY_CONSOLIDATION_QUERY_ADAPTER_REVISION,
        "checkpoint": MEMORY_CHECKPOINT_REVISION,
    }
    return sha256_text(canonical_json(material))


def _span_seconds(first: str | None, latest: str | None) -> float:
    if not first or not latest:
        return 0.0
    start = datetime.fromisoformat(first.replace("Z", "+00:00"))
    end = datetime.fromisoformat(latest.replace("Z", "+00:00"))
    return max(0.0, (end - start).total_seconds())


class MemoryConsolidationEngine:
    """Create immutable derived indexes while leaving raw memory authoritative."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryConsolidationStore(repository, initialize=initialize)
        self.planner = MemoryConsolidationPlanner(repository, initialize=initialize)
        self.queries = MemoryQueryEngine(repository, initialize=initialize)

    def consolidate_memory(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        policy_id: str = "exact_structural_v1",
        consolidation_types: list[str] | tuple[str, ...] | None = None,
        persist: bool = True,
        *,
        query_requests: list[MemoryQueryRequest] | None = None,
        precomputed_query_results: dict[str, Any] | None = None,
    ) -> MemoryConsolidationRun:
        if str(getattr(self.repository, "backend_name", "sqlite")) != "postgres":
            return self._consolidate_memory_unlocked(
                authenticated_scope,
                subject_scope,
                temporal_boundary,
                policy_id,
                consolidation_types,
                persist,
                query_requests=query_requests,
                precomputed_query_results=precomputed_query_results,
            )

        boundary_payload = (
            {
                "valid_at": temporal_boundary.valid_at,
                "known_at": temporal_boundary.known_at,
            }
            if temporal_boundary is not None
            else None
        )
        lock_identity = sha256_text(
            canonical_json(
                {
                    "scope": authenticated_scope.memory_boundary(),
                    "subject_scope": subject_scope or {},
                    "temporal_boundary": boundary_payload,
                    "policy_id": policy_id,
                    "consolidation_types": sorted(consolidation_types or ()),
                    "persist": persist,
                    "query_requests": [
                        item.to_dict() for item in (query_requests or [])
                    ],
                }
            )
        )
        lock_name = f"prmr_consolidation:{lock_identity}"
        with self.repository.connect() as lock_connection:
            lock_connection.execute("SET LOCAL lock_timeout='300s'")
            lock_connection.execute("SET LOCAL statement_timeout='300s'")
            lock_connection.execute(
                "SET LOCAL idle_in_transaction_session_timeout='300s'"
            )
            lock_connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_name,)
            )
            return self._consolidate_memory_unlocked(
                authenticated_scope,
                subject_scope,
                temporal_boundary,
                policy_id,
                consolidation_types,
                persist,
                query_requests=query_requests,
                precomputed_query_results=precomputed_query_results,
            )

    def _consolidate_memory_unlocked(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        policy_id: str = "exact_structural_v1",
        consolidation_types: list[str] | tuple[str, ...] | None = None,
        persist: bool = True,
        *,
        query_requests: list[MemoryQueryRequest] | None = None,
        precomputed_query_results: dict[str, Any] | None = None,
    ) -> MemoryConsolidationRun:
        started_perf = time.perf_counter()
        plan, context = self.planner.plan_consolidation_with_context(
            authenticated_scope,
            subject_scope,
            temporal_boundary=temporal_boundary,
            consolidation_types=consolidation_types,
            policy_id=policy_id,
        )
        requests = self._normalise_query_requests(
            plan, query_requests or self._default_query_requests(plan)
        )
        query_manifest = sha256_text(
            canonical_json([item.to_dict() for item in requests])
        )
        run_identity = sha256_text(
            canonical_json(
                {
                    "plan_identity": plan.consolidation_run_identity_hash,
                    "query_manifest": query_manifest,
                    "revisions": self._revisions(),
                }
            )
        )
        run_id = f"mcrun_{run_identity[:24]}"
        existing = self.store.get_run(authenticated_scope, run_id)
        if existing and existing.status == MemoryConsolidationStatus.COMPLETED.value:
            LOGGER.info(
                "memory_consolidation_replayed run_id=%s checkpoint_id=%s",
                run_id,
                existing.checkpoint_id,
            )
            return existing
        created_at = plan.temporal_boundary["known_at"]
        dependencies = plan.invalidation_dependencies
        run = MemoryConsolidationRun(
            consolidation_run_id=run_id,
            consolidation_mode="exact_structural_v1",
            consolidation_policy_id=policy_id,
            client_id=authenticated_scope.client_id,
            vault_id=authenticated_scope.vault_id,
            namespace=authenticated_scope.namespace,
            application_reference=plan.subject_scope.get("application_reference"),
            actor_reference=plan.subject_scope.get("actor_reference"),
            workspace_reference=plan.subject_scope.get("workspace_reference"),
            entity_id=plan.subject_scope.get("entity_id"),
            relationship_id=plan.subject_scope.get("relationship_id"),
            session_reference=plan.subject_scope.get("session_reference"),
            valid_at=plan.temporal_boundary["valid_at"],
            known_at=plan.temporal_boundary["known_at"],
            window_start=(
                plan.deterministic_windows[0]["window_start"]
                if plan.deterministic_windows
                else None
            ),
            window_end=(
                plan.deterministic_windows[-1]["window_end"]
                if plan.deterministic_windows
                else None
            ),
            source_event_count=context["fast_manifest"]["event_count"],
            effective_event_count=len(plan.eligible_event_ids),
            signal_count=len(plan.eligible_signal_keys),
            entity_count=len(plan.eligible_entity_ids),
            relationship_count=len(plan.eligible_relationship_ids),
            conflict_count=len(plan.open_conflict_ids),
            source_event_manifest_hash=dependencies[
                "authoritative_event_manifest_hash"
            ],
            effective_event_manifest_hash=dependencies[
                "effective_event_manifest_hash"
            ],
            ledger_evolution_manifest_hash=dependencies[
                "ledger_evolution_manifest_hash"
            ],
            importance_annotation_manifest_hash=dependencies[
                "importance_annotation_manifest_hash"
            ],
            entity_manifest_hash=dependencies["entity_manifest_hash"],
            relationship_manifest_hash=dependencies["relationship_manifest_hash"],
            query_manifest_hash=query_manifest,
            consolidation_plan_id=plan.consolidation_plan_id,
            consolidation_manifest_hash="",
            checkpoint_id=None,
            status=MemoryConsolidationStatus.PLANNED.value,
            created_item_count=0,
            reused_item_count=0,
            invalidated_item_count=0,
            started_at=created_at,
            completed_at=None,
            duration_ms=0.0,
            error_code=None,
            memory_consolidation_schema_revision=MEMORY_CONSOLIDATION_SCHEMA_REVISION,
            memory_consolidation_policy_revision=MEMORY_CONSOLIDATION_POLICY_REVISION,
            memory_consolidation_planner_revision=MEMORY_CONSOLIDATION_PLANNER_REVISION,
            memory_consolidation_membership_revision=MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
            memory_consolidation_manifest_revision=MEMORY_CONSOLIDATION_MANIFEST_REVISION,
            memory_checkpoint_revision=MEMORY_CHECKPOINT_REVISION,
            created_at=created_at,
            updated_at=created_at,
        )
        if persist:
            self.store.put_plan(authenticated_scope, plan)
            self.store.put_run(run)
            self.store.put_run(
                replace(run, status=MemoryConsolidationStatus.RUNNING.value)
            )
        LOGGER.info(
            "memory_consolidation_started run_id=%s event_count=%s signal_count=%s",
            run_id,
            len(plan.eligible_event_ids),
            len(plan.eligible_signal_keys),
        )
        try:
            memories, members = self._build_memories(
                authenticated_scope, run, plan, context
            )
            prior_memory_ids = set()
            if context.get("compatible_checkpoint"):
                prior_memory_ids = set(
                    context["compatible_checkpoint"].deterministic_state_payload.get(
                        "consolidated_memory_ids", []
                    )
                )
            created_memory_count = sum(
                item.consolidated_memory_id not in prior_memory_ids
                for item in memories
            )
            reused_memory_count = len(memories) - created_memory_count
            snapshots = self._build_query_snapshots(
                authenticated_scope,
                requests,
                precomputed_query_results=precomputed_query_results,
            )
            manifest = sha256_text(
                canonical_json(
                    sorted(
                        [
                        {
                            "id": item.consolidated_memory_id,
                            "hash": item.consolidated_memory_hash_sha256,
                        }
                        for item in memories
                        ],
                        key=lambda item: item["id"],
                    )
                )
            )
            checkpoint = self._build_checkpoint(
                run,
                plan,
                context,
                memories,
                manifest,
                snapshots,
            )
            base = context.get("compatible_checkpoint")
            delta = (
                build_checkpoint_delta(base, checkpoint, created_at=created_at)
                if base is not None
                else None
            )
            if delta:
                checkpoint = replace(
                    checkpoint,
                    delta_from_checkpoint_id=delta.checkpoint_delta_id,
                )
                checkpoint = finalize_checkpoint(
                    replace(
                        checkpoint,
                        memory_checkpoint_id="mchk_pending",
                        checkpoint_hash_sha256="",
                    )
                )
                delta = build_checkpoint_delta(base, checkpoint, created_at=created_at)
            if persist:
                for memory in memories:
                    self.store.put_memory(memory)
                by_memory: dict[str, list[ConsolidatedMemoryMember]] = {}
                for member in members:
                    by_memory.setdefault(member.consolidated_memory_id, []).append(
                        member
                    )
                for memory_id, memory_members in by_memory.items():
                    self.store.put_members(
                        authenticated_scope, run_id, memory_members
                    )
                self.store.put_checkpoint(checkpoint)
                if delta:
                    self.store.put_delta(authenticated_scope, delta)
                self._supersede_previous(authenticated_scope, checkpoint, base)
            completed_at = utc(None)
            completed = replace(
                run,
                consolidation_manifest_hash=manifest,
                checkpoint_id=checkpoint.memory_checkpoint_id,
                status=MemoryConsolidationStatus.COMPLETED.value,
                created_item_count=created_memory_count,
                reused_item_count=reused_memory_count,
                completed_at=completed_at,
                duration_ms=round(
                    (time.perf_counter() - started_perf) * 1000, 3
                ),
                updated_at=completed_at,
            )
            if persist:
                self.store.put_run(completed)
            LOGGER.info(
                "memory_consolidation_completed run_id=%s checkpoint_id=%s "
                "created_item_count=%s duration_ms=%s",
                run_id,
                checkpoint.memory_checkpoint_id,
                created_memory_count,
                completed.duration_ms,
            )
            return completed
        except Exception as exc:
            failed = replace(
                run,
                status=MemoryConsolidationStatus.FAILED.value,
                error_code=getattr(
                    exc, "code", "MEMORY_CONSOLIDATION_PLAN_FAILED"
                ),
                duration_ms=round(
                    (time.perf_counter() - started_perf) * 1000, 3
                ),
                completed_at=utc(None),
                updated_at=utc(None),
            )
            if persist:
                self.store.put_run(failed)
            LOGGER.error(
                "memory_consolidation_failed run_id=%s error_code=%s",
                run_id,
                failed.error_code,
            )
            if isinstance(exc, MemoryConsolidationError):
                raise
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_PLAN_FAILED",
                "Exact structural consolidation could not be completed.",
                retryable=True,
            ) from exc

    def get_consolidation_run(
        self, scope: AuthenticatedScope, consolidation_run_id: str
    ) -> MemoryConsolidationRun:
        item = self.store.get_run(scope, consolidation_run_id)
        if item is None:
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_RUN_NOT_FOUND",
                "The consolidation run was not found in authenticated scope.",
            )
        return item

    def get_consolidation_plan(
        self, scope: AuthenticatedScope, consolidation_plan_id: str
    ) -> Any:
        item = self.store.get_plan(scope, consolidation_plan_id)
        if item is None:
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_RUN_NOT_FOUND",
                "The consolidation plan was not found in authenticated scope.",
            )
        return item

    def get_consolidated_memory(
        self, scope: AuthenticatedScope, consolidated_memory_id: str
    ) -> ConsolidatedMemory:
        item = self.store.get_memory(scope, consolidated_memory_id)
        if item is None:
            raise MemoryConsolidationError(
                "MEMORY_CONSOLIDATION_NOT_FOUND",
                "The consolidated memory was not found in authenticated scope.",
            )
        return item

    def list_consolidated_memories(
        self,
        scope: AuthenticatedScope,
        *,
        consolidation_run_id: str | None = None,
        consolidation_type: str | None = None,
    ) -> list[ConsolidatedMemory]:
        if consolidation_run_id:
            run = self.get_consolidation_run(scope, consolidation_run_id)
            if run.checkpoint_id:
                checkpoint = self.get_checkpoint(scope, run.checkpoint_id)
                memories = [
                    self.store.get_memory(scope, memory_id)
                    for memory_id in checkpoint.deterministic_state_payload.get(
                        "consolidated_memory_ids", []
                    )
                ]
                return [
                    item
                    for item in memories
                    if item is not None
                    and (
                        consolidation_type is None
                        or item.consolidation_type == consolidation_type
                    )
                ]
        return self.store.list_memories(
            scope, consolidation_type=consolidation_type
        )

    def get_checkpoint(
        self, scope: AuthenticatedScope, checkpoint_id: str
    ) -> MemoryCheckpoint:
        item = self.store.get_checkpoint(scope, checkpoint_id)
        if item is None:
            raise MemoryConsolidationError(
                "MEMORY_CHECKPOINT_NOT_FOUND",
                "The memory checkpoint was not found in authenticated scope.",
            )
        return item

    def list_checkpoints(
        self, scope: AuthenticatedScope
    ) -> list[MemoryCheckpoint]:
        return self.store.list_checkpoints(scope)

    def compare_checkpoints(
        self,
        scope: AuthenticatedScope,
        first_checkpoint_id: str,
        second_checkpoint_id: str,
    ) -> dict[str, Any]:
        first = self.get_checkpoint(scope, first_checkpoint_id)
        second = self.get_checkpoint(scope, second_checkpoint_id)
        comparison = compare_checkpoint_payloads(first, second)
        material = {
            "first_checkpoint_id": first_checkpoint_id,
            "second_checkpoint_id": second_checkpoint_id,
            **comparison,
            "comparison_revision": MEMORY_CONSOLIDATION_COMPARISON_REVISION,
        }
        return {
            **material,
            "comparison_hash_sha256": sha256_text(canonical_json(material)),
        }

    def trace_consolidated_memory_origin(
        self, scope: AuthenticatedScope, consolidated_memory_id: str
    ) -> dict[str, Any]:
        memory = self.get_consolidated_memory(scope, consolidated_memory_id)
        members = self.store.list_members(scope, consolidated_memory_id)
        return {
            "consolidated_memory": {
                "consolidated_memory_id": memory.consolidated_memory_id,
                "consolidation_type": memory.consolidation_type,
                "consolidated_memory_hash_sha256": (
                    memory.consolidated_memory_hash_sha256
                ),
                "derived_epistemic_status": memory.derived_epistemic_status,
            },
            "members": [
                {
                    "member_id": item.consolidated_memory_member_id,
                    "member_type": item.member_type,
                    "event_id": item.event_id,
                    "source_id": item.source_id,
                    "candidate_id": item.candidate_id,
                    "admission_id": item.admission_id,
                    "evolution_id": item.evolution_id,
                    "conflict_id": item.conflict_id,
                    "entity_id": item.entity_id,
                    "relationship_id": item.relationship_id,
                    "member_hash_sha256": item.member_hash_sha256,
                    "epistemic_status": item.epistemic_status,
                }
                for item in members
            ],
            "evidence_completeness": (
                "legacy_without_source"
                if any(item.event_id and not item.source_id for item in members)
                else "complete"
            ),
            "source_content_exposed": False,
        }

    def verify_consolidation_integrity(
        self, scope: AuthenticatedScope, consolidation_run_id: str
    ) -> Any:
        from .memory_consolidation_integrity import (
            MemoryConsolidationIntegrityVerifier,
        )

        return MemoryConsolidationIntegrityVerifier(
            self.repository
        ).verify_consolidation_integrity(scope, consolidation_run_id)

    def invalidate_consolidation(
        self,
        scope: AuthenticatedScope,
        consolidation_run_id: str,
        *,
        invalidation_type: str,
        invalidation_reason: str,
        triggering_object_type: str,
        triggering_object_id: str,
        actor_type: str = "internal_operator",
        actor_reference: str = "core-engine",
    ) -> MemoryConsolidationInvalidation:
        run = self.get_consolidation_run(scope, consolidation_run_id)
        checkpoint = (
            self.get_checkpoint(scope, run.checkpoint_id) if run.checkpoint_id else None
        )
        current = fast_authoritative_manifest(
            self.repository, scope
        )["authoritative_manifest_hash"]
        created_at = utc(None)
        material = {
            "run_id": run.consolidation_run_id,
            "checkpoint_id": run.checkpoint_id,
            "type": invalidation_type,
            "reason": invalidation_reason,
            "trigger_type": triggering_object_type,
            "trigger_id": triggering_object_id,
            "previous_manifest": run.source_event_manifest_hash,
            "current_manifest": current,
            "revision": MEMORY_CONSOLIDATION_INVALIDATION_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        item = MemoryConsolidationInvalidation(
            invalidation_id=f"mcinv_{digest[:24]}",
            consolidation_run_id=run.consolidation_run_id,
            consolidated_memory_id=None,
            checkpoint_id=run.checkpoint_id,
            invalidation_type=invalidation_type,
            invalidation_reason=invalidation_reason,
            triggering_object_type=triggering_object_type,
            triggering_object_id=triggering_object_id,
            previous_manifest_hash=run.source_event_manifest_hash,
            current_manifest_hash=current,
            system_effective_at=created_at,
            actor_type=actor_type,
            actor_reference=actor_reference,
            invalidation_revision=MEMORY_CONSOLIDATION_INVALIDATION_REVISION,
            created_at=created_at,
        )
        self.store.put_invalidation(scope, item)
        self.store.put_run(
            replace(
                run,
                status=MemoryConsolidationStatus.INVALIDATED.value,
                updated_at=created_at,
            )
        )
        if checkpoint:
            self.store.put_checkpoint(
                replace(
                    checkpoint,
                    checkpoint_status=MemoryCheckpointStatus.INVALIDATED.value,
                )
            )
        return item

    def refresh_stale_consolidation(
        self, scope: AuthenticatedScope, consolidation_run_id: str
    ) -> MemoryConsolidationRun:
        run = self.get_consolidation_run(scope, consolidation_run_id)
        return self.consolidate_memory(
            scope,
            {
                "application_reference": run.application_reference,
                "actor_reference": run.actor_reference,
                "workspace_reference": run.workspace_reference,
                "entity_id": run.entity_id,
                "relationship_id": run.relationship_id,
                "session_reference": run.session_reference,
            },
            MemoryTemporalBoundary(valid_at=run.valid_at, known_at=utc(None)),
            policy_id=run.consolidation_policy_id,
        )

    def recover_incomplete_consolidation_runs(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        recovered = 0
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.store.run_table} WHERE client_id={self.store.p} "
                f"AND vault_id={self.store.p} AND namespace={self.store.p} "
                f"AND status IN ({self.store.p},{self.store.p})",
                (*scope.memory_boundary(), "planned", "running"),
            ).fetchall()
        from .memory_consolidation_store import _from_row

        for row in rows:
            run = _from_row(MemoryConsolidationRun, row)
            self.store.put_run(
                replace(
                    run,
                    status=MemoryConsolidationStatus.FAILED.value,
                    error_code="MEMORY_CONSOLIDATION_INCOMPLETE_RECOVERED",
                    completed_at=utc(None),
                    updated_at=utc(None),
                )
            )
            recovered += 1
        return {
            "recovered_count": recovered,
            "recovery_action": "marked_failed_without_current_checkpoint",
        }

    def _build_memories(
        self,
        scope: AuthenticatedScope,
        run: MemoryConsolidationRun,
        plan: Any,
        context: dict[str, Any],
    ) -> tuple[list[ConsolidatedMemory], list[ConsolidatedMemoryMember]]:
        events = list(context["view"].effective_events)
        by_id = {str(item["event_id"]): item for item in events}
        projections = {item.event_id: item for item in context["view"].projections}
        dynamics = {item.signal_key: item for item in context["dynamics"].signals}
        memories: list[ConsolidatedMemory] = []
        members: list[ConsolidatedMemoryMember] = []

        for group in plan.planned_groups:
            if group["consolidation_type"] not in {
                MemoryConsolidationType.EXACT_SIGNAL_WINDOW.value,
                MemoryConsolidationType.EVENT_STATE_CHAIN.value,
            }:
                continue
            grouped_events = [by_id[item] for item in group["event_ids"]]
            memory = self._event_group_memory(
                run, group, grouped_events, projections, dynamics
            )
            memories.append(memory)
            members.extend(
                build_event_members(
                    memory.consolidated_memory_id,
                    grouped_events,
                    projections,
                    created_at=run.known_at,
                )
            )

        phase_members = events
        phase_group = {
            "consolidation_type": MemoryConsolidationType.TEMPORAL_PHASE_WINDOW.value,
            "group_key": f"phase:{context['dynamics'].snapshot.dynamics_snapshot_id}",
            "signal_key": None,
            "event_ids": [str(item["event_id"]) for item in phase_members],
        }
        phase_memory = self._event_group_memory(
            run, phase_group, phase_members, projections, dynamics
        )
        memories.append(phase_memory)
        members.extend(
            build_event_members(
                phase_memory.consolidated_memory_id,
                phase_members,
                projections,
                created_at=run.known_at,
            )
        )

        if plan.eligible_entity_ids or run.entity_id:
            entity_group = {
                "consolidation_type": MemoryConsolidationType.ENTITY_EVENT_CHECKPOINT.value,
                "group_key": "entities:"
                + sha256_text(canonical_json(plan.eligible_entity_ids))[:16],
                "signal_key": None,
                "event_ids": [str(item["event_id"]) for item in events],
            }
            entity_memory = self._event_group_memory(
                run, entity_group, events, projections, dynamics
            )
            memories.append(entity_memory)
            members.extend(
                build_event_members(
                    entity_memory.consolidated_memory_id,
                    events,
                    projections,
                    created_at=run.known_at,
                )
            )
        if context["relationship_view"].effective_relationships:
            rel_group = {
                "consolidation_type": MemoryConsolidationType.RELATIONSHIP_STATE_CHECKPOINT.value,
                "group_key": "relationships:"
                + context["relationship_view"].deterministic_relationship_manifest[:16],
                "signal_key": None,
                "event_ids": [],
            }
            rel_memory = self._event_group_memory(
                run, rel_group, [], projections, dynamics
            )
            memories.append(rel_memory)
            for index, relationship in enumerate(
                context["relationship_view"].effective_relationships
            ):
                material = {
                    "memory_id": rel_memory.consolidated_memory_id,
                    "relationship_id": relationship.relationship_id,
                    "sequence_index": index,
                    "revision": MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
                }
                digest = sha256_text(canonical_json(material))
                members.append(
                    ConsolidatedMemoryMember(
                        consolidated_memory_member_id=f"cmemmem_{digest[:24]}",
                        consolidated_memory_id=rel_memory.consolidated_memory_id,
                        member_type="relationship",
                        event_id=None,
                        source_id=None,
                        candidate_id=None,
                        admission_id=None,
                        evolution_id=None,
                        conflict_id=None,
                        entity_id=None,
                        relationship_id=relationship.relationship_id,
                        sequence_index=index,
                        member_role="contributing",
                        member_hash_sha256=digest,
                        effective_state="active",
                        epistemic_status=relationship.epistemic_status,
                        valid_from=relationship.valid_from,
                        valid_until=relationship.valid_until,
                        system_known_from=relationship.system_known_from,
                        system_known_until=relationship.system_known_until,
                        membership_revision=MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
                        created_at=run.known_at,
                    )
                )
        if context["view"].open_conflicts or context["view"].resolved_conflicts:
            conflict_ids = sorted(
                [item.conflict_id for item in context["view"].open_conflicts]
                + [item.conflict_id for item in context["view"].resolved_conflicts]
            )
            conflict_event_ids = sorted(
                {
                    event_id
                    for item in (
                        list(context["view"].open_conflicts)
                        + list(context["view"].resolved_conflicts)
                    )
                    for event_id in item.conflicting_event_ids
                    if event_id in by_id
                }
            )
            conflict_group = {
                "consolidation_type": MemoryConsolidationType.CONFLICT_PRESERVING_CHECKPOINT.value,
                "group_key": "conflicts:"
                + sha256_text(canonical_json(conflict_ids))[:16],
                "signal_key": None,
                "event_ids": conflict_event_ids,
            }
            conflict_events = [by_id[item] for item in conflict_event_ids]
            conflict_memory = self._event_group_memory(
                run, conflict_group, conflict_events, projections, dynamics
            )
            memories.append(conflict_memory)
            members.extend(
                build_event_members(
                    conflict_memory.consolidated_memory_id,
                    conflict_events,
                    projections,
                    created_at=run.known_at,
                )
            )
        return memories, members

    def _event_group_memory(
        self,
        run: MemoryConsolidationRun,
        group: dict[str, Any],
        events: list[dict[str, Any]],
        projections: dict[str, Any],
        dynamics: dict[str, Any],
    ) -> ConsolidatedMemory:
        event_ids = [str(item["event_id"]) for item in events]
        contributor_manifest = event_manifest(events)
        statuses: Counter[str] = Counter()
        source_ids: set[str] = set()
        open_conflicts: set[str] = set()
        resolved_conflicts: set[str] = set()
        for event in events:
            projection = projections.get(str(event["event_id"]))
            raw = (
                str(projection.epistemic_status)
                if projection
                else str(
                    event.get("external_metadata", {})
                    .get("metadata", {})
                    .get("epistemic_status", "unknown")
                )
            )
            status = (
                "conflicted"
                if projection and projection.open_conflict_ids
                else raw
                if raw in {"explicit", "derived", "inferred", "unknown"}
                else "unknown"
            )
            statuses[status] += 1
            if projection and projection.source_id:
                source_ids.add(projection.source_id)
            if projection:
                open_conflicts.update(projection.open_conflict_ids)
                resolved_conflicts.update(projection.resolved_conflict_ids)
        signal_key = group.get("signal_key")
        signal = dynamics.get(signal_key) if signal_key else None
        first_at = event_time(events[0]) if events else None
        latest_at = event_time(events[-1]) if events else None
        influence_summary = (
            {
                "final_influence": signal.final_influence,
                "memory_phase": signal.memory_phase,
                "occurrences_by_horizon": signal.occurrences_by_horizon,
            }
            if signal
            else {}
        )
        recurrence_summary = (
            {
                "occurrence_count": signal.occurrence_count,
                "recurrence_span_seconds": signal.recurrence_span_seconds,
                "reinforced": signal.reinforced,
                "re_emergence_count": signal.re_emergence_count,
            }
            if signal
            else {}
        )
        payload = {
            "ordered_event_ids": event_ids,
            "effective_states": [
                {
                    "event_id": event_id,
                    "effective_state": (
                        projections[event_id].effective_state
                        if event_id in projections
                        else "active"
                    ),
                }
                for event_id in event_ids
            ],
            "signal_identity_exact": signal_key,
            "generated_narrative": None,
            "winner_selected": False,
            "dynamics_snapshot_id": (
                next(iter(dynamics.values())).dynamics_snapshot_id
                if group["consolidation_type"]
                == MemoryConsolidationType.TEMPORAL_PHASE_WINDOW.value
                and dynamics
                else None
            ),
        }
        material = {
            "type": group["consolidation_type"],
            "key": group["group_key"],
            "events": event_ids,
            "payload": payload,
            "influence_summary": influence_summary,
            "recurrence_summary": recurrence_summary,
            "epistemic": dict(sorted(statuses.items())),
            "open_conflicts": sorted(open_conflicts),
            "resolved_conflicts": sorted(resolved_conflicts),
            "revisions": {
                "schema": MEMORY_CONSOLIDATION_SCHEMA_REVISION,
                "policy": MEMORY_CONSOLIDATION_POLICY_REVISION,
            },
        }
        digest = sha256_text(canonical_json(material))
        return ConsolidatedMemory(
            consolidated_memory_id=f"cmem_{digest[:24]}",
            consolidation_run_id=run.consolidation_run_id,
            consolidation_type=group["consolidation_type"],
            client_id=run.client_id,
            vault_id=run.vault_id,
            namespace=run.namespace,
            application_reference=run.application_reference,
            actor_reference=run.actor_reference,
            workspace_reference=run.workspace_reference,
            entity_id=run.entity_id,
            relationship_id=run.relationship_id,
            session_reference=run.session_reference,
            signal_key=signal_key,
            consolidation_key=group["group_key"],
            window_start=first_at,
            window_end=latest_at,
            valid_at=run.valid_at,
            known_at=run.known_at,
            primary_memory_phase=signal.memory_phase if signal else None,
            derived_epistemic_status="derived",
            contributor_epistemic_counts={
                key: int(statuses.get(key, 0))
                for key in (
                    "explicit",
                    "derived",
                    "inferred",
                    "unknown",
                    "conflicted",
                )
            },
            contributor_event_count=len(events),
            contributor_source_count=len(source_ids),
            first_event_id=event_ids[0] if event_ids else None,
            latest_event_id=event_ids[-1] if event_ids else None,
            current_effective_event_id=event_ids[-1] if event_ids else None,
            occurrence_count=len(events),
            first_occurrence_at=first_at,
            latest_occurrence_at=latest_at,
            temporal_span_seconds=_span_seconds(first_at, latest_at),
            reinforced=bool(signal and signal.reinforced),
            re_emerging=bool(signal and signal.re_emerging),
            open_conflict_ids=sorted(open_conflicts),
            resolved_conflict_ids=sorted(resolved_conflicts),
            relationship_count=1 if run.relationship_id else 0,
            entity_count=1 if run.entity_id else 0,
            influence_summary=influence_summary,
            recurrence_summary=recurrence_summary,
            temporal_summary={
                "first_occurrence_at": first_at,
                "latest_occurrence_at": latest_at,
                "temporal_span_seconds": _span_seconds(first_at, latest_at),
            },
            consolidation_payload=payload,
            contributor_manifest_hash_sha256=contributor_manifest,
            evidence_manifest_hash_sha256=sha256_text(
                canonical_json(sorted(source_ids))
            ),
            consolidated_memory_hash_sha256=digest,
            status=MemoryConsolidationStatus.COMPLETED.value,
            previous_consolidated_memory_id=None,
            memory_consolidation_schema_revision=MEMORY_CONSOLIDATION_SCHEMA_REVISION,
            memory_consolidation_policy_revision=MEMORY_CONSOLIDATION_POLICY_REVISION,
            created_at=run.known_at,
            updated_at=run.known_at,
        )

    def _build_query_snapshots(
        self,
        scope: AuthenticatedScope,
        requests: list[MemoryQueryRequest],
        *,
        precomputed_query_results: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        snapshots: dict[str, dict[str, Any]] = {}
        for request in requests:
            if request.query_type not in SUPPORTED_ACCELERATED_QUERY_TYPES:
                continue
            key = consolidation_query_key(request)
            result = (precomputed_query_results or {}).get(key)
            if result is None:
                result = self.queries.query_memory(scope, request)
            elif result.query_type != request.query_type:
                raise MemoryConsolidationError(
                    "MEMORY_ACCELERATION_EQUIVALENCE_FAILED",
                    "Precomputed canonical query artifact does not match the requested query type.",
                )
            snapshots[key] = {
                "query_request": request.to_dict(),
                "query_type": request.query_type,
                "query_result_id": result.query_result_id,
                "query_run_id": result.query_run_id,
                "result_hash_sha256": result.result_hash_sha256,
                "result_manifest_hash_sha256": result.result_manifest_hash_sha256,
                "evidence_bundle_id": result.evidence_bundle_id,
                "explanation_id": result.explanation_id,
            }
        return snapshots

    def _build_checkpoint(
        self,
        run: MemoryConsolidationRun,
        plan: Any,
        context: dict[str, Any],
        memories: list[ConsolidatedMemory],
        memory_manifest: str,
        query_snapshots: dict[str, dict[str, Any]],
    ) -> MemoryCheckpoint:
        signals = context["dynamics"].signals
        phase = {
            name: [
                {
                    "signal_key": item.signal_key,
                    "occurrence_event_ids": list(item.occurrence_event_ids),
                    "occurrence_count": item.occurrence_count,
                    "final_influence": item.final_influence,
                    "memory_phase": item.memory_phase,
                    "reinforced": item.reinforced,
                    "re_emerging": item.re_emerging,
                    "epistemic_status_counts": item.epistemic_status_counts,
                    "open_conflict_ids": item.open_conflict_ids,
                }
                for item in signals
                if item.memory_phase == name
            ]
            for name in ("active", "latent", "dormant", "decayed")
        }
        events = list(context["view"].effective_events)
        latest = events[-1] if events else None
        relationships = {
            item.relationship_id: item.to_dict()
            for item in context["relationship_view"].effective_relationships
        }
        entities = {
            item: {
                "entity_id": item,
                "event_ids": [
                    str(event["event_id"])
                    for event in events
                    if str(event.get("entity_reference") or "") == item
                ],
            }
            for item in plan.eligible_entity_ids
        }
        packet_snapshot = next(
            (
                snapshot
                for snapshot in query_snapshots.values()
                if snapshot["query_type"] == MemoryQueryType.CONTINUITY_PACKET.value
            ),
            None,
        )
        packet_payload = None
        if packet_snapshot:
            result = self.queries.get_query_result(
                AuthenticatedScope(
                    run.client_id,
                    run.vault_id,
                    run.namespace,
                    application_reference=run.application_reference,
                    actor_reference=run.actor_reference,
                    workspace_reference=run.workspace_reference,
                    entity_reference=run.entity_id,
                    session_reference=run.session_reference,
                ),
                packet_snapshot["query_result_id"],
            )
            packet_payload = result.answer_payload.get("packet")
        state_payload = {
            "effective_event_ids": [str(item["event_id"]) for item in events],
            "projection_index": {
                item.event_id: item.to_dict() for item in context["view"].projections
            },
            "query_snapshots": query_snapshots,
            "continuity_packet": packet_payload,
            "authoritative_category_hashes": context["fast_manifest"][
                "category_hashes"
            ],
            "consolidated_memory_ids": [
                item.consolidated_memory_id for item in memories
            ],
            "revisions": self._revisions(),
            "raw_source_content_included": False,
        }
        draft = MemoryCheckpoint(
            memory_checkpoint_id="mchk_pending",
            consolidation_run_id=run.consolidation_run_id,
            checkpoint_type="bitemporal_exact_structural",
            client_id=run.client_id,
            vault_id=run.vault_id,
            namespace=run.namespace,
            application_reference=run.application_reference,
            actor_reference=run.actor_reference,
            workspace_reference=run.workspace_reference,
            entity_id=run.entity_id,
            relationship_id=run.relationship_id,
            session_reference=run.session_reference,
            valid_at=run.valid_at,
            known_at=run.known_at,
            window_start=run.window_start,
            window_end=run.window_end,
            authoritative_event_count=context["fast_manifest"]["event_count"],
            effective_event_count=len(events),
            authoritative_event_manifest_hash=run.source_event_manifest_hash,
            effective_event_manifest_hash=run.effective_event_manifest_hash,
            evolution_manifest_hash=run.ledger_evolution_manifest_hash,
            importance_manifest_hash=run.importance_annotation_manifest_hash,
            entity_manifest_hash=run.entity_manifest_hash,
            relationship_manifest_hash=run.relationship_manifest_hash,
            conflict_manifest_hash=plan.invalidation_dependencies[
                "conflict_manifest_hash"
            ],
            signal_dynamics_manifest_hash=plan.invalidation_dependencies[
                "signal_dynamics_manifest_hash"
            ],
            consolidated_memory_manifest_hash=memory_manifest,
            active_signal_index=phase["active"],
            latent_signal_index=phase["latent"],
            dormant_signal_index=phase["dormant"],
            decayed_signal_index=phase["decayed"],
            current_state_event_id=str(latest["event_id"]) if latest else None,
            latest_effective_event_id=str(latest["event_id"]) if latest else None,
            open_conflict_ids=sorted(
                item.conflict_id for item in context["view"].open_conflicts
            ),
            resolved_conflict_ids=sorted(
                item.conflict_id for item in context["view"].resolved_conflicts
            ),
            entity_index=entities,
            relationship_index=relationships,
            deterministic_state_payload=state_payload,
            checkpoint_hash_sha256="",
            checkpoint_status=MemoryCheckpointStatus.CURRENT.value,
            previous_checkpoint_id=(
                context["compatible_checkpoint"].memory_checkpoint_id
                if context.get("compatible_checkpoint")
                else None
            ),
            delta_from_checkpoint_id=None,
            memory_checkpoint_revision=MEMORY_CHECKPOINT_REVISION,
            created_at=run.known_at,
        )
        return finalize_checkpoint(draft)

    def _supersede_previous(
        self,
        scope: AuthenticatedScope,
        checkpoint: MemoryCheckpoint,
        previous: MemoryCheckpoint | None,
    ) -> None:
        if previous and previous.memory_checkpoint_id != checkpoint.memory_checkpoint_id:
            self.store.put_checkpoint(
                replace(
                    previous,
                    checkpoint_status=MemoryCheckpointStatus.SUPERSEDED.value,
                )
            )

    @staticmethod
    def _normalise_query_requests(
        plan: Any, requests: list[MemoryQueryRequest]
    ) -> list[MemoryQueryRequest]:
        output: list[MemoryQueryRequest] = []
        for request in requests:
            output.append(
                replace(
                    request,
                    client_id=None,
                    vault_id=None,
                    namespace=None,
                    application_reference=(
                        request.application_reference
                        or plan.subject_scope.get("application_reference")
                    ),
                    actor_reference=(
                        request.actor_reference
                        or plan.subject_scope.get("actor_reference")
                    ),
                    workspace_reference=(
                        request.workspace_reference
                        or plan.subject_scope.get("workspace_reference")
                    ),
                    entity_id=(
                        request.entity_id or plan.subject_scope.get("entity_id")
                    ),
                    relationship_id=(
                        request.relationship_id
                        or plan.subject_scope.get("relationship_id")
                    ),
                    session_reference=(
                        request.session_reference
                        or plan.subject_scope.get("session_reference")
                    ),
                    valid_at=plan.temporal_boundary["valid_at"],
                    known_at=plan.temporal_boundary["known_at"],
                )
            )
        deduplicated = {
            canonical_json(item.to_dict()): item for item in output
        }
        return [deduplicated[key] for key in sorted(deduplicated)]

    @staticmethod
    def _default_query_requests(plan: Any) -> list[MemoryQueryRequest]:
        requests = [
            MemoryQueryRequest(
                query_type=MemoryQueryType.CURRENT_STATE.value,
                include_evidence=True,
                include_explanation=True,
            ),
            MemoryQueryRequest(
                query_type=MemoryQueryType.CONTINUITY_PACKET.value,
                include_evidence=True,
                include_explanation=True,
            ),
        ]
        return requests

    @staticmethod
    def _revisions() -> dict[str, str]:
        return {
            "schema": MEMORY_CONSOLIDATION_SCHEMA_REVISION,
            "policy": MEMORY_CONSOLIDATION_POLICY_REVISION,
            "planner": MEMORY_CONSOLIDATION_PLANNER_REVISION,
            "membership": MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
            "manifest": MEMORY_CONSOLIDATION_MANIFEST_REVISION,
            "checkpoint": MEMORY_CHECKPOINT_REVISION,
            "checkpoint_delta": MEMORY_CHECKPOINT_DELTA_REVISION,
            "invalidation": MEMORY_CONSOLIDATION_INVALIDATION_REVISION,
            "query_adapter": MEMORY_CONSOLIDATION_QUERY_ADAPTER_REVISION,
            "continuity_adapter": MEMORY_CONSOLIDATION_CONTINUITY_ADAPTER_REVISION,
            "integrity": MEMORY_CONSOLIDATION_INTEGRITY_REVISION,
            "comparison": MEMORY_CONSOLIDATION_COMPARISON_REVISION,
        }


__all__ = [
    "MemoryConsolidationEngine",
    "SUPPORTED_ACCELERATED_QUERY_TYPES",
    "consolidation_query_key",
]
