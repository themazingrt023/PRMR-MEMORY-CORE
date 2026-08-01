"""Deterministic typed query engine over authoritative PRMR memory services."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
import time
from typing import Any, Callable

from .admission_models import MemoryAdmissionError
from .entity_memory import EntityMemoryService
from .entity_models import EntityMemoryError
from .entity_reconstruction import EntityRelationshipReconstructionService
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_evidence_bundle import MemoryEvidenceBundleBuilder
from .memory_explanation import build_memory_explanation
from .memory_ledger_models import MemoryLedgerError, MemoryTemporalBoundary
from .memory_query_models import (
    MEMORY_CHANGE_PROJECTION_REVISION,
    MEMORY_EVIDENCE_BUNDLE_REVISION,
    MEMORY_EXPLANATION_REVISION,
    MEMORY_QUERY_COMPARISON_REVISION,
    MEMORY_QUERY_PLANNER_REVISION,
    MEMORY_QUERY_POLICY_REVISION,
    MEMORY_QUERY_RESULT_REVISION,
    MEMORY_QUERY_SCHEMA_REVISION,
    MEMORY_TIMELINE_REVISION,
    MemoryEvidenceBundle,
    MemoryExplanation,
    MemoryQueryError,
    MemoryQueryIntegrityResult,
    MemoryQueryPlan,
    MemoryQueryPolicy,
    MemoryQueryRequest,
    MemoryQueryResult,
    MemoryQueryResultComparison,
    MemoryQueryResultStatus,
    MemoryQueryRun,
    MemoryQueryType,
)
from .memory_query_planner import (
    MemoryQueryPlanner,
    encode_query_cursor,
    scope_fingerprint,
    utc,
)
from .memory_query_results import (
    build_epistemic_summary,
    canonical_items,
    current_event,
    epistemic_status_for_event,
    event_signal,
    event_time,
    ordered_events,
    phase_record,
    recurrence_record,
    reemergence_record,
    result_status_for,
    safe_event_projection,
    signal_key_for_event,
)
from .memory_query_store import (
    evidence_bundle_from_row,
    explanation_from_row,
    initialize_memory_query_schema,
    json_value,
    placeholder,
    result_from_row,
    run_from_row,
    table,
)
from .memory_reconstruction import MemoryReconstructionService
from .memory_state_resolver import MemoryStateResolver
from .memory_temporal_models import MemoryDynamicsError
from .relationship_models import RelationshipMemoryError
from .relationship_memory import RelationshipMemoryService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_query")


class MemoryQueryEngine:
    """Read authoritative memory and persist reproducible query audit artifacts."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_memory_query_schema(repository)
        self.planner = MemoryQueryPlanner()
        self.state = MemoryStateResolver(repository, initialize=initialize)
        self.dynamics = MemoryDynamicsEngine(repository, initialize=initialize)
        self.reconstruction = MemoryReconstructionService(
            repository, initialize=initialize
        )
        self.entities = EntityMemoryService(repository, initialize=initialize)
        self.entity_history = EntityRelationshipReconstructionService(
            repository, initialize=initialize
        )
        self.relationships = RelationshipMemoryService(
            repository, initialize=initialize
        )
        self.evidence = MemoryEvidenceBundleBuilder(repository)
        self.p = placeholder(repository)
        self.run_table = table(repository, "prmr_memory_query_runs")
        self.result_table = table(repository, "prmr_memory_query_results")
        self.bundle_table = table(repository, "prmr_memory_evidence_bundles")
        self.evidence_table = table(
            repository, "prmr_memory_query_evidence_items"
        )
        self.explanation_table = table(repository, "prmr_memory_explanations")
        self.comparison_table = table(
            repository, "prmr_memory_query_result_comparisons"
        )

    def query_continuity_packet_v2(
        self,
        authenticated_scope: AuthenticatedScope,
        *,
        subject_scope: dict[str, str | None] | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
        signal_identity_mode: str = "exact_signal_v1",
    ) -> dict[str, Any]:
        """Internal, explicit V2 query path; the existing V1 query stays unchanged."""

        from .continuity_v2_explanation import explain_packet_v2
        from .continuity_v2_packet import ContinuityPacketV2Service

        packet = ContinuityPacketV2Service(self.repository).generate_packet_v2(
            authenticated_scope,
            subject_scope=subject_scope,
            temporal_boundary=MemoryTemporalBoundary(
                valid_at=valid_at,
                known_at=known_at,
            ),
            signal_identity_mode=signal_identity_mode,
        )
        payload = packet.to_dict()
        provenance = payload["provenance_context"]
        governance = payload["governance_context"]
        return {
            "requested_packet_mode": "epistemic_continuity_v2",
            "packet_status": payload["packet_status"],
            "packet_id": payload["packet_id"],
            "packet_hash": payload["packet_hash"],
            "primary_state_status": payload["current_state"]["primary_state_status"],
            "epistemic_summary": {
                "asserted": len(payload["asserted_information"]),
                "derived": len(payload["derived_information"]),
                "tentative": len(payload["tentative_information"]),
                "unknown": len(payload["unknown_information"]),
                "conflicted": len(payload["conflicted_information"]),
            },
            "conflict_count": len(payload["conflict_context"]),
            "unknown_count": len(payload["unknown_information"]),
            "provenance_completeness": {
                "complete": provenance["complete_event_count"],
                "partial": provenance["partial_event_count"],
                "legacy_without_source": provenance["legacy_event_count"],
                "governance_erased": provenance["governance_erased_event_count"],
            },
            "governance_limitation_status": governance[
                "recoverability_limitation_status"
            ],
            "explanations": explain_packet_v2(payload),
        }

    def query_memory(
        self,
        authenticated_scope: AuthenticatedScope,
        query_request: MemoryQueryRequest,
        *,
        policy: MemoryQueryPolicy | None = None,
        frozen_now: str | None = None,
    ) -> MemoryQueryResult:
        started_perf = time.perf_counter()
        started_at = utc(frozen_now)
        request, selected_policy, plan = self.planner.plan(
            authenticated_scope,
            query_request,
            policy=policy,
            frozen_now=started_at,
        )
        LOGGER.info(
            "memory_query_started query_type=%s scope_fingerprint=%s",
            request.query_type,
            scope_fingerprint(authenticated_scope),
        )
        context = self._resolve_context(authenticated_scope, request, plan)
        fingerprint = self._query_fingerprint(
            authenticated_scope, plan, context["relevant_memory_manifest_hash"]
        )
        existing = self._run_by_fingerprint(authenticated_scope, fingerprint)
        if existing and existing.query_status == "completed" and existing.result_id:
            result = self.get_query_result(authenticated_scope, existing.result_id)
            LOGGER.info(
                "memory_query_replayed query_run_id=%s query_type=%s",
                existing.query_run_id,
                existing.query_type,
            )
            return replace(result, replayed=True)

        query_run_id = f"qrun_{fingerprint[:24]}"
        run = MemoryQueryRun(
            query_run_id=query_run_id,
            query_type=request.query_type,
            query_mode=request.query_mode,
            query_policy_id=selected_policy.policy_id,
            client_id=authenticated_scope.client_id,
            vault_id=authenticated_scope.vault_id,
            namespace=authenticated_scope.namespace,
            application_reference=request.application_reference,
            actor_reference=request.actor_reference,
            workspace_reference=request.workspace_reference,
            entity_id=request.entity_id,
            relationship_id=request.relationship_id,
            session_reference=request.session_reference,
            event_id=request.event_id,
            signal_key=request.signal_key,
            valid_at=plan.valid_at,
            known_at=plan.known_at,
            first_temporal_boundary=request.first_temporal_boundary,
            second_temporal_boundary=request.second_temporal_boundary,
            normalised_query_payload=plan.normalised_query_payload,
            query_fingerprint_sha256=fingerprint,
            query_plan_hash_sha256=plan.query_plan_hash_sha256,
            resolved_event_manifest_hash=context["resolved_event_manifest_hash"],
            relevant_memory_manifest_hash=context["relevant_memory_manifest_hash"],
            dynamics_snapshot_id=context.get("dynamics_snapshot_id"),
            reconstruction_id=None,
            entity_view_hash=context.get("entity_view_hash"),
            relationship_manifest_hash=context.get("relationship_manifest_hash"),
            query_status="pending",
            result_status=None,
            result_id=None,
            result_hash_sha256=None,
            evidence_bundle_id=None,
            result_count=0,
            evidence_count=0,
            truncated=False,
            memory_query_schema_revision=MEMORY_QUERY_SCHEMA_REVISION,
            memory_query_policy_revision=MEMORY_QUERY_POLICY_REVISION,
            memory_query_planner_revision=MEMORY_QUERY_PLANNER_REVISION,
            started_at=started_at,
            completed_at=None,
            duration_ms=0.0,
            error_code=None,
            created_at=started_at,
            updated_at=started_at,
        )
        self._insert_pending_run(run)
        try:
            answer, metadata = self._execute_projection(
                authenticated_scope, request, plan, context
            )
            event_ids = sorted(set(metadata.get("event_ids", [])))
            entity_ids = sorted(set(metadata.get("entity_ids", [])))
            relationship_ids = sorted(set(metadata.get("relationship_ids", [])))
            bundle = (
                self.evidence.build(
                    authenticated_scope,
                    query_run_id,
                    event_ids=event_ids,
                    entity_ids=entity_ids,
                    relationship_ids=relationship_ids,
                    evolution_ids=metadata.get("evolution_ids", []),
                    dynamics_snapshot_ids=[
                        item
                        for item in [context.get("dynamics_snapshot_id")]
                        if item
                    ],
                    conflict_ids=metadata.get("conflict_ids", []),
                    packet_ids=metadata.get("packet_ids", []),
                    reconstruction_ids=metadata.get("reconstruction_ids", []),
                    policy=selected_policy,
                )
                if selected_policy.include_evidence
                else None
            )
            partial_evidence = bool(
                bundle
                and bundle.completeness_status
                not in {"complete", "unavailable"}
            )
            truncated = bool(metadata.get("truncated")) or bool(
                bundle and bundle.truncated
            )
            status = metadata.get("status") or result_status_for(
                answer,
                no_data=bool(metadata.get("no_data")),
                partial=partial_evidence,
                truncated=truncated,
            )
            epistemic = build_epistemic_summary(answer).to_dict()
            result_count = int(metadata.get("result_count", len(canonical_items(answer))))
            result_material = {
                "query_run_id": query_run_id,
                "query_type": request.query_type,
                "status": status,
                "answer": answer,
                "epistemic_summary": epistemic,
                "temporal_boundary": {
                    "valid_at": plan.valid_at,
                    "known_at": plan.known_at,
                },
                "subject_scope": self._result_subject_scope(
                    authenticated_scope, request
                ),
                "evidence_manifest": (
                    bundle.evidence_manifest_hash_sha256 if bundle else None
                ),
                "result_revision": MEMORY_QUERY_RESULT_REVISION,
            }
            result_manifest = sha256_text(canonical_json(result_material))
            query_result_id = f"qres_{result_manifest[:24]}"
            explanation = (
                build_memory_explanation(
                    query_run_id=query_run_id,
                    query_result_id=query_result_id,
                    query_type=request.query_type,
                    result_status=status,
                    answer_payload=answer,
                    plan=plan,
                    evidence_bundle=bundle,
                    excluded_counts=context["view"].excluded_counts,
                )
                if selected_policy.include_explanation
                else None
            )
            result_payload = {
                **result_material,
                "query_result_id": query_result_id,
                "evidence_bundle_id": bundle.evidence_bundle_id if bundle else None,
                "explanation_id": explanation.explanation_id if explanation else None,
            }
            result_hash = sha256_text(canonical_json(result_payload))
            next_cursor = (
                encode_query_cursor(
                    authenticated_scope,
                    request.query_type,
                    str(plan.normalised_query_payload["base_query_hash"]),
                    plan.cursor_offset + plan.maximum_results,
                )
                if metadata.get("has_more")
                else None
            )
            completed_at = utc(None)
            result = MemoryQueryResult(
                query_result_id=query_result_id,
                query_run_id=query_run_id,
                query_type=request.query_type,
                result_status=status,
                answer_payload=answer,
                epistemic_summary=epistemic,
                temporal_boundary={
                    "valid_at": plan.valid_at,
                    "known_at": plan.known_at,
                },
                subject_scope=self._result_subject_scope(
                    authenticated_scope, request
                ),
                effective_event_count=len(context["view"].effective_events),
                excluded_event_counts=dict(context["view"].excluded_counts),
                conflict_count=int(metadata.get("conflict_count", 0)),
                unknown_count=int(epistemic["unknown_item_count"]),
                evidence_bundle_id=bundle.evidence_bundle_id if bundle else None,
                explanation_id=explanation.explanation_id if explanation else None,
                result_manifest_hash_sha256=result_manifest,
                result_hash_sha256=result_hash,
                memory_query_result_revision=MEMORY_QUERY_RESULT_REVISION,
                generated_at=completed_at,
                created_at=completed_at,
                next_cursor=next_cursor,
            )
            completed_run = replace(
                run,
                query_status="completed",
                result_status=status,
                result_id=result.query_result_id,
                result_hash_sha256=result.result_hash_sha256,
                evidence_bundle_id=bundle.evidence_bundle_id if bundle else None,
                result_count=result_count,
                evidence_count=bundle.evidence_item_count if bundle else 0,
                truncated=truncated,
                reconstruction_id=_first(metadata.get("reconstruction_ids", [])),
                completed_at=completed_at,
                duration_ms=round((time.perf_counter() - started_perf) * 1000, 3),
                updated_at=completed_at,
            )
            self._persist_completed(
                authenticated_scope, completed_run, result, bundle, explanation
            )
            LOGGER.info(
                "memory_query_completed query_run_id=%s query_type=%s "
                "result_status=%s result_count=%s evidence_count=%s duration_ms=%s",
                query_run_id,
                request.query_type,
                status,
                result_count,
                bundle.evidence_item_count if bundle else 0,
                completed_run.duration_ms,
            )
            return result
        except Exception as exc:
            self._mark_failed(
                authenticated_scope,
                run,
                getattr(exc, "code", "MEMORY_QUERY_EXECUTION_FAILED"),
                round((time.perf_counter() - started_perf) * 1000, 3),
            )
            LOGGER.error(
                "memory_query_failed query_run_id=%s query_type=%s error_code=%s",
                query_run_id,
                request.query_type,
                getattr(exc, "code", "MEMORY_QUERY_EXECUTION_FAILED"),
            )
            if isinstance(exc, MemoryQueryError):
                raise
            if isinstance(
                exc,
                (
                    MemoryAdmissionError,
                    MemoryLedgerError,
                    EntityMemoryError,
                    RelationshipMemoryError,
                ),
            ):
                raise MemoryQueryError(
                    "MEMORY_QUERY_TARGET_NOT_FOUND",
                    "The requested memory target was not found in authenticated scope.",
                ) from exc
            raise MemoryQueryError(
                "MEMORY_QUERY_EXECUTION_FAILED",
                "The deterministic memory query could not be completed.",
                retryable=True,
            ) from exc

    def get_query_run(
        self, scope: AuthenticatedScope, query_run_id: str
    ) -> MemoryQueryRun:
        row = self._scoped_row(self.run_table, "query_run_id", query_run_id, scope)
        if not row:
            raise MemoryQueryError(
                "MEMORY_QUERY_RESULT_NOT_FOUND",
                "The query artifact was not found in authenticated scope.",
            )
        return run_from_row(row)

    def get_query_result(
        self, scope: AuthenticatedScope, query_result_id: str
    ) -> MemoryQueryResult:
        row = self._scoped_row(
            self.result_table, "query_result_id", query_result_id, scope
        )
        if not row:
            raise MemoryQueryError(
                "MEMORY_QUERY_RESULT_NOT_FOUND",
                "The query artifact was not found in authenticated scope.",
            )
        return result_from_row(row)

    def get_evidence_bundle(
        self, scope: AuthenticatedScope, evidence_bundle_id: str
    ) -> MemoryEvidenceBundle:
        row = self._scoped_row(
            self.bundle_table, "evidence_bundle_id", evidence_bundle_id, scope
        )
        if not row:
            raise MemoryQueryError(
                "MEMORY_QUERY_EVIDENCE_NOT_FOUND",
                "The evidence artifact was not found in authenticated scope.",
            )
        return evidence_bundle_from_row(row)

    def get_explanation(
        self, scope: AuthenticatedScope, explanation_id: str
    ) -> MemoryExplanation:
        row = self._scoped_row(
            self.explanation_table, "explanation_id", explanation_id, scope
        )
        if not row:
            raise MemoryQueryError(
                "MEMORY_QUERY_RESULT_NOT_FOUND",
                "The explanation was not found in authenticated scope.",
            )
        return explanation_from_row(row)

    def list_query_runs(
        self,
        scope: AuthenticatedScope,
        query_type: str | None = None,
        entity_id: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not 1 <= int(limit) <= 500:
            raise MemoryQueryError(
                "MEMORY_QUERY_LIMIT_EXCEEDED", "Query-run list limit is invalid."
            )
        base_hash = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "query_type": query_type,
                    "entity_id": entity_id,
                    "revision": MEMORY_QUERY_SCHEMA_REVISION,
                }
            )
        )
        offset = 0
        if cursor:
            from .memory_query_planner import decode_query_cursor

            offset = decode_query_cursor(
                cursor, scope, "query_run_listing", base_hash
            )
        where = (
            f"client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
        )
        params: list[Any] = [*scope.memory_boundary()]
        for field, value in (("query_type", query_type), ("entity_id", entity_id)):
            if value:
                where += f" AND {field}={self.p}"
                params.append(value)
        params.extend([int(limit) + 1, offset])
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.run_table} WHERE {where} "
                f"ORDER BY created_at,query_run_id LIMIT {self.p} OFFSET {self.p}",
                tuple(params),
            ).fetchall()
        runs = [run_from_row(row) for row in rows]
        return {
            "items": runs[: int(limit)],
            "next_cursor": (
                encode_query_cursor(
                    scope,
                    "query_run_listing",
                    base_hash,
                    offset + int(limit),
                )
                if len(runs) > int(limit)
                else None
            ),
        }

    def replay_query(
        self, scope: AuthenticatedScope, query_run_id: str
    ) -> dict[str, Any]:
        previous = self.get_query_run(scope, query_run_id)
        request = _request_from_payload(previous.normalised_query_payload)
        replay = self.query_memory(scope, request, frozen_now=previous.started_at)
        changed = replay.query_run_id != previous.query_run_id
        return {
            "previous_query_run_id": previous.query_run_id,
            "query_run_id": replay.query_run_id,
            "query_result_id": replay.query_result_id,
            "replayed": replay.replayed,
            "memory_changed": (
                replay.result_hash_sha256 != previous.result_hash_sha256
            ),
            "created_new_query": not replay.replayed,
            "previous_result_preserved": bool(previous.result_id),
            "comparison_available": changed,
        }

    def compare_query_results(
        self,
        scope: AuthenticatedScope,
        first_result_id: str,
        second_result_id: str,
    ) -> MemoryQueryResultComparison:
        first = self.get_query_result(scope, first_result_id)
        second = self.get_query_result(scope, second_result_id)
        first_items = {
            canonical_json(item): item for item in canonical_items(first.answer_payload)
        }
        second_items = {
            canonical_json(item): item for item in canonical_items(second.answer_payload)
        }
        data = {
            "first_result_id": first_result_id,
            "second_result_id": second_result_id,
            "first_status": first.result_status,
            "second_status": second.result_status,
            "state_changed": (
                first.answer_payload.get("current_state")
                != second.answer_payload.get("current_state")
            ),
            "answer_items_added": [
                second_items[key] for key in sorted(set(second_items) - set(first_items))
            ],
            "answer_items_removed": [
                first_items[key] for key in sorted(set(first_items) - set(second_items))
            ],
            "epistemic_changes": {
                "from": first.epistemic_summary,
                "to": second.epistemic_summary,
            },
            "conflict_changes": {
                "from": first.conflict_count,
                "to": second.conflict_count,
            },
            "evidence_changes": {
                "from": first.evidence_bundle_id,
                "to": second.evidence_bundle_id,
            },
            "temporal_boundary_changes": {
                "from": first.temporal_boundary,
                "to": second.temporal_boundary,
            },
            "revision_changes": {
                "from": first.memory_query_result_revision,
                "to": second.memory_query_result_revision,
            },
            "result_hash_changed": (
                first.result_hash_sha256 != second.result_hash_sha256
            ),
        }
        digest = sha256_text(
            canonical_json(
                {**data, "comparison_revision": MEMORY_QUERY_COMPARISON_REVISION}
            )
        )
        comparison = MemoryQueryResultComparison(
            **data, comparison_hash_sha256=digest
        )
        self._persist_comparison(scope, comparison)
        return comparison

    def verify_memory_query_integrity(
        self, scope: AuthenticatedScope, query_run_id: str
    ) -> MemoryQueryIntegrityResult:
        from .memory_query_integrity import MemoryQueryIntegrityVerifier

        return MemoryQueryIntegrityVerifier(self).verify(scope, query_run_id)

    def recover_incomplete_query_runs(self) -> dict[str, Any]:
        now = utc(None)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.run_table} "
                f"WHERE query_status={self.p}",
                ("pending",),
            ).fetchall()
            recovered = 0
            for row in rows:
                run = run_from_row(row)
                failed = replace(
                    run,
                    query_status="failed",
                    error_code="MEMORY_QUERY_RECOVERED_INCOMPLETE",
                    completed_at=now,
                    updated_at=now,
                )
                connection.execute(
                    f"UPDATE {self.run_table} SET query_status={self.p},"
                    f"completed_at={self.p},updated_at={self.p},payload_json={self.p} "
                    f"WHERE query_run_id={self.p}",
                    (
                        failed.query_status,
                        failed.completed_at,
                        failed.updated_at,
                        json_value(self.repository, failed),
                        failed.query_run_id,
                    ),
                )
                recovered += 1
        return {
            "recovered_count": recovered,
            "recovery_action": "marked_failed_without_result",
        }

    def _resolve_context(
        self,
        scope: AuthenticatedScope,
        request: MemoryQueryRequest,
        plan: MemoryQueryPlan,
    ) -> dict[str, Any]:
        boundary = MemoryTemporalBoundary(valid_at=plan.valid_at, known_at=plan.known_at)
        subject = self._subject_scope(request)
        view = self.state.resolve_effective_events(
            scope,
            boundary,
            **{key: value for key, value in subject.items() if value is not None},
            include_conflicted=True,
        )
        dynamics = self.dynamics.compute_memory_dynamics(
            scope, subject, boundary, persist=False
        )
        try:
            relationship_view = self.relationships.resolve_effective_relationships(
                scope,
                entity_id=request.entity_id,
                relationship_type=(
                    request.relationship_type_filter[0]
                    if len(request.relationship_type_filter) == 1
                    else None
                ),
                temporal_boundary=boundary,
                include_conflicted=True,
            )
            entity_view = None
            if request.entity_id:
                entity_view = self.entities.build_entity_memory_view(
                    scope,
                    request.entity_id,
                    boundary,
                    persist_dynamics=False,
                )
        except (EntityMemoryError, RelationshipMemoryError) as exc:
            raise MemoryQueryError(
                "MEMORY_QUERY_TARGET_NOT_FOUND",
                "The requested memory target was not found in authenticated scope.",
            ) from exc
        projections = [
            item.to_dict()
            for item in view.projections
            if item.system_known_from <= plan.known_at
            and item.valid_from <= plan.valid_at
        ]
        memory_material = {
            "effective_event_ids": sorted(
                str(item.get("event_id")) for item in view.effective_events
            ),
            "projections": projections,
            "open_conflicts": [
                item.to_dict() for item in view.open_conflicts
            ],
            "resolved_conflicts": [
                item.to_dict() for item in view.resolved_conflicts
            ],
            "resolved_event_manifest": dynamics.snapshot.resolved_event_manifest_hash,
            "dynamics_identity": dynamics.snapshot.dynamics_snapshot_identity,
            "relationship_manifest": relationship_view.deterministic_relationship_manifest,
            "entity_view_hash": (
                entity_view.deterministic_view_hash if entity_view else None
            ),
            "revisions": {
                "query_schema": MEMORY_QUERY_SCHEMA_REVISION,
                "query_policy": MEMORY_QUERY_POLICY_REVISION,
                "query_planner": MEMORY_QUERY_PLANNER_REVISION,
                "state_resolver": view.resolver_revision,
                "relationship_resolver": relationship_view.resolver_revision,
            },
        }
        return {
            "view": view,
            "dynamics": dynamics,
            "relationship_view": relationship_view,
            "entity_view": entity_view,
            "resolved_event_manifest_hash": (
                dynamics.snapshot.resolved_event_manifest_hash
            ),
            "dynamics_snapshot_id": dynamics.snapshot.dynamics_snapshot_id,
            "relationship_manifest_hash": (
                relationship_view.deterministic_relationship_manifest
            ),
            "entity_view_hash": (
                entity_view.deterministic_view_hash if entity_view else None
            ),
            "relevant_memory_manifest_hash": sha256_text(
                canonical_json(memory_material)
            ),
        }

    def _execute_projection(
        self,
        scope: AuthenticatedScope,
        request: MemoryQueryRequest,
        plan: MemoryQueryPlan,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        handler = getattr(self, f"_query_{request.query_type}", None)
        if not isinstance(handler, Callable):
            raise MemoryQueryError(
                "MEMORY_QUERY_TYPE_INVALID", "The query type has no projection."
            )
        return handler(scope, request, plan, context)

    def _query_current_state(self, scope: Any, request: Any, plan: Any, context: Any):
        view = context["view"]
        latest = current_event(view.effective_events)
        if latest is None:
            return {"current_state": None, "current_state_event_id": None}, {
                "no_data": True,
                "event_ids": [],
                "result_count": 0,
            }
        event_id = str(latest["event_id"])
        conflicts = [
            item
            for item in view.open_conflicts
            if event_id in item.conflicting_event_ids
        ]
        event_map = {
            str(item.get("event_id")): item for item in view.effective_events
        }
        projection_map = {item.event_id: item for item in view.projections}
        signal_map = {
            item.signal_key: item for item in context["dynamics"].signals
        }
        if conflicts:
            conflict_event_ids = sorted(
                {
                    item_id
                    for conflict in conflicts
                    for item_id in conflict.conflicting_event_ids
                }
            )
            sides = [
                safe_event_projection(
                    event_map[item_id],
                    projection_map.get(item_id),
                    signal_map.get(signal_key_for_event(event_map[item_id])),
                )
                for item_id in conflict_event_ids
                if item_id in event_map
            ]
            return {
                "current_state": None,
                "current_state_event_id": None,
                "conflicted": True,
                "supported_sides": sides,
                "open_conflict_ids": sorted(item.conflict_id for item in conflicts),
                "winner_selected": False,
            }, {
                "status": MemoryQueryResultStatus.CONFLICTED.value,
                "event_ids": conflict_event_ids,
                "conflict_ids": [item.conflict_id for item in conflicts],
                "conflict_count": len(conflicts),
                "result_count": len(sides),
            }
        projection = projection_map.get(event_id)
        signal = signal_map.get(signal_key_for_event(latest))
        packet = self.dynamics.build_continuity_packet(
            scope,
            self._subject_scope(request),
            MemoryTemporalBoundary(valid_at=plan.valid_at, known_at=plan.known_at),
            persist_dynamics=False,
        )
        payload = {
            "current_state": event_signal(latest),
            "current_state_event_id": event_id,
            "current_state_signal_key": signal_key_for_event(latest),
            **safe_event_projection(latest, projection, signal),
            "source_count": signal.source_count if signal else int(bool(projection and projection.source_id)),
            "evidence_available": bool(projection and projection.source_id),
            "packet_id": packet["packet_id"] if request.include_packet else None,
            "exact_provenance_references": [
                {
                    "event_id": event_id,
                    "source_id": projection.source_id if projection else None,
                    "admission_id": projection.admission_id if projection else None,
                }
            ],
        }
        status = (
            MemoryQueryResultStatus.UNKNOWN.value
            if payload["event_type"] == "information.unknown"
            or payload["epistemic_status"] == "unknown"
            else MemoryQueryResultStatus.ANSWERED.value
        )
        return payload, {
            "status": status,
            "event_ids": [event_id],
            "packet_ids": [packet["packet_id"]],
            "result_count": 1,
        }

    def _query_memory_by_phase(self, scope: Any, request: Any, plan: Any, context: Any):
        phases = set(request.memory_phase_filter)
        records = [
            phase_record(item)
            for item in context["dynamics"].signals
            if item.memory_phase in phases
        ]
        records.sort(
            key=lambda item: (
                -float(item["final_influence"]),
                _descending_text(str(item["latest_occurrence_at"])),
                str(item["signal_key"]),
            )
        )
        page, more = self._page(records, plan)
        return {
            "requested_phases": sorted(phases),
            "signals": page,
            "ordering": [
                "final_influence_desc",
                "latest_occurrence_desc",
                "signal_key_asc",
            ],
        }, {
            "no_data": not records,
            "truncated": more,
            "has_more": more,
            "event_ids": _event_ids(page),
            "conflict_ids": _conflict_ids(page),
            "result_count": len(page),
        }

    def _query_changes_between(self, scope: Any, request: Any, plan: Any, context: Any):
        first = _temporal(request.first_temporal_boundary)
        second = _temporal(request.second_temporal_boundary)
        first_recon = self.reconstruction.reconstruct_bitemporal(
            scope,
            first.valid_at or "",
            first.known_at or "",
            self._subject_scope(request),
            persist=False,
        )
        second_recon = self.reconstruction.reconstruct_bitemporal(
            scope,
            second.valid_at or "",
            second.known_at or "",
            self._subject_scope(request),
            persist=False,
        )
        first_dyn = self.dynamics.compute_memory_dynamics(
            scope, self._subject_scope(request), first, persist=False
        )
        second_dyn = self.dynamics.compute_memory_dynamics(
            scope, self._subject_scope(request), second, persist=False
        )
        dynamics_change = _compare_dynamics(first_dyn.signals, second_dyn.signals)
        first_ids = set(first_recon.effective_event_ids)
        second_ids = set(second_recon.effective_event_ids)
        evolutions = self.state.ledger.list_evolutions(scope)
        first_conflicts = {
            item["conflict_id"] for item in first_recon.open_conflicts
        }
        second_conflicts = {
            item["conflict_id"] for item in second_recon.open_conflicts
        }
        previous_current = (
            first_recon.ordered_state_transitions[-1]
            if first_recon.ordered_state_transitions
            else None
        )
        new_current = (
            second_recon.ordered_state_transitions[-1]
            if second_recon.ordered_state_transitions
            else None
        )
        relationships = self.relationships.compare_relationship_views(
            scope, first, second, entity_id=request.entity_id
        )
        entity_changes = {
            "aliases_added": [],
            "entities_merged": [],
        }
        if request.entity_id:
            entity_changes = self.entity_history.compare_entity_views(
                scope, request.entity_id, first, second, persist=False
            )
        payload = {
            "events_became_effective": sorted(second_ids - first_ids),
            "events_became_superseded": sorted(
                item.source_event_id
                for item in evolutions
                if item.evolution_type in {"correct", "supersede"}
                and first.known_at < item.system_effective_at <= second.known_at
            ),
            "events_retracted": sorted(
                item.source_event_id
                for item in evolutions
                if item.evolution_type == "retract"
                and first.known_at < item.system_effective_at <= second.known_at
            ),
            "events_invalidated": sorted(
                item.source_event_id
                for item in evolutions
                if item.evolution_type == "invalidate"
                and first.known_at < item.system_effective_at <= second.known_at
            ),
            "events_added_by_late_arrival": sorted(
                event_id
                for event_id in second_ids - first_ids
                if _projection_known_at(context["view"], event_id) > first.known_at
            ),
            "current_state_changed": previous_current != new_current,
            "previous_current_state": previous_current,
            "new_current_state": new_current,
            **dynamics_change,
            "conflicts_opened": sorted(second_conflicts - first_conflicts),
            "conflicts_resolved": sorted(first_conflicts - second_conflicts),
            "aliases_added": entity_changes.get("aliases_added", []),
            "entities_merged": (
                [request.entity_id]
                if entity_changes.get("canonical_identity_changed")
                else []
            ),
            "relationships_added": relationships["added_relationship_ids"],
            "relationships_removed": relationships["removed_relationship_ids"],
            "relationships_superseded": relationships["removed_relationship_ids"],
            "first_reconstruction_id": first_recon.reconstruction_id,
            "second_reconstruction_id": second_recon.reconstruction_id,
            "change_projection_revision": MEMORY_CHANGE_PROJECTION_REVISION,
        }
        return payload, {
            "event_ids": sorted(first_ids | second_ids),
            "evolution_ids": [
                item.evolution_id
                for item in evolutions
                if first.known_at < item.system_effective_at <= second.known_at
            ],
            "conflict_ids": sorted(first_conflicts | second_conflicts),
            "relationship_ids": sorted(
                set(relationships["added_relationship_ids"])
                | set(relationships["removed_relationship_ids"])
            ),
            "reconstruction_ids": [
                first_recon.reconstruction_id,
                second_recon.reconstruction_id,
            ],
            "result_count": sum(
                len(value) for value in payload.values() if isinstance(value, list)
            ),
        }

    def _query_event_timeline(self, scope: Any, request: Any, plan: Any, context: Any):
        events = {
            str(item.get("event_id")): item
            for item in self.state.admission._events_for_scope(scope)
        }
        effective_ids = {
            str(item.get("event_id")) for item in context["view"].effective_events
        }
        signal_map = {
            item.signal_key: item for item in context["dynamics"].signals
        }
        evolutions_by_event: dict[str, list[str]] = {}
        for evolution in self.state.ledger.list_evolutions(scope):
            if (
                evolution.system_effective_at > plan.known_at
                or evolution.valid_from > plan.valid_at
            ):
                continue
            for event_id in (
                evolution.source_event_id,
                evolution.replacement_event_id,
            ):
                if event_id:
                    evolutions_by_event.setdefault(event_id, []).append(
                        evolution.evolution_id
                    )
        entries = []
        for projection in context["view"].projections:
            if (
                projection.system_known_from > plan.known_at
                or projection.valid_from > plan.valid_at
            ):
                continue
            event = events.get(projection.event_id)
            if not event:
                continue
            if not request.include_inactive_history and projection.event_id not in effective_ids:
                continue
            if request.event_type_filter and projection.event_type not in request.event_type_filter:
                continue
            entry = safe_event_projection(
                event,
                projection,
                signal_map.get(signal_key_for_event(event)),
            )
            entry["evolution_ids"] = sorted(
                evolutions_by_event.get(projection.event_id, [])
            )
            entry["entity_links"] = self._event_entity_links(
                scope, projection.event_id, plan.valid_at, plan.known_at
            )
            entries.append(entry)
        entries.sort(
            key=lambda item: (
                item["valid_at"],
                int(events[item["event_id"]].get("timestamp_index", 0)),
                item["event_id"],
            )
        )
        page, more = self._page(entries, plan)
        return {
            "events": page,
            "ordering_revision": MEMORY_TIMELINE_REVISION,
            "inactive_history_included": request.include_inactive_history,
        }, {
            "no_data": not entries,
            "truncated": more,
            "has_more": more,
            "event_ids": [item["event_id"] for item in page],
            "entity_ids": sorted(
                {
                    link["entity_id"]
                    for item in page
                    for link in item["entity_links"]
                }
            ),
            "evolution_ids": sorted(
                {value for item in page for value in item["evolution_ids"]}
            ),
            "conflict_ids": _conflict_ids(page),
            "result_count": len(page),
        }

    def _query_signal_history(self, scope: Any, request: Any, plan: Any, context: Any):
        signal = next(
            (
                item
                for item in context["dynamics"].signals
                if item.signal_key == request.signal_key
            ),
            None,
        )
        if signal is None:
            return {"signal_key": request.signal_key, "occurrences": []}, {
                "no_data": True,
                "event_ids": [],
                "result_count": 0,
            }
        events = {
            str(item.get("event_id")): item
            for item in context["view"].effective_events
        }
        occurrences = [
            {
                "event_id": event_id,
                "occurred_at": event_time(events[event_id]),
                "epistemic_status": epistemic_status_for_event(events[event_id]),
            }
            for event_id in signal.occurrence_event_ids
            if event_id in events
        ]
        page, more = self._page(occurrences, plan)
        payload = {
            **recurrence_record(signal),
            "occurrences": page,
            "re_emergence_episodes": (
                [reemergence_record(signal)] if signal.re_emerging else []
            ),
            "phase_history": [
                {
                    "boundary": plan.valid_at,
                    "phase": signal.memory_phase,
                    "influence": signal.final_influence,
                }
            ],
            "importance_history": self._importance_history_for_events(
                scope, signal.occurrence_event_ids
            ),
            "conflict_history": list(signal.open_conflict_ids),
            "source_references": list(signal.source_ids),
            "epistemic_status_distribution": dict(signal.epistemic_status_counts),
        }
        return payload, {
            "truncated": more,
            "has_more": more,
            "event_ids": [item["event_id"] for item in page],
            "conflict_ids": list(signal.open_conflict_ids),
            "result_count": len(page),
        }

    def _importance_history_for_events(
        self, scope: AuthenticatedScope, event_ids: list[str]
    ) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for event_id in event_ids:
            try:
                history.extend(
                    item.to_dict()
                    for item in self.dynamics.list_importance_annotations(
                        scope, event_id
                    )
                )
            except MemoryDynamicsError as exc:
                # Legacy/external events remain queryable but have no admitted
                # event to which a durable importance annotation can attach.
                if exc.code != "MEMORY_IMPORTANCE_SCOPE_DENIED":
                    raise
        return history

    def _query_recurrence(self, scope: Any, request: Any, plan: Any, context: Any):
        records = [
            recurrence_record(item)
            for item in context["dynamics"].signals
            if item.reinforced
        ]
        records.sort(
            key=lambda item: (
                -float(item["recurrence_boost"]),
                -float(item["cross_horizon_boost"]),
                -int(item["occurrence_count"]),
                item["signal_key"],
            )
        )
        page, more = self._page(records, plan)
        return {"signals": page, "truth_promotion": False}, {
            "no_data": not records,
            "truncated": more,
            "has_more": more,
            "event_ids": _event_ids(page),
            "result_count": len(page),
        }

    def _query_re_emergence(self, scope: Any, request: Any, plan: Any, context: Any):
        records = [
            reemergence_record(item)
            for item in context["dynamics"].signals
            if item.re_emerging
        ]
        records.sort(key=lambda item: item["signal_key"])
        page, more = self._page(records, plan)
        return {"signals": page, "immediate_repetition_excluded": True}, {
            "no_data": not records,
            "truncated": more,
            "has_more": more,
            "event_ids": _event_ids(page),
            "result_count": len(page),
        }

    def _query_open_conflicts(self, scope: Any, request: Any, plan: Any, context: Any):
        memory = [
            {
                "conflict_id": item.conflict_id,
                "conflict_type": item.conflict_type,
                "status": "open",
                "participating_event_references": list(item.conflicting_event_ids),
                "valid_time": item.valid_from,
                "system_known_time": item.system_effective_at,
                "evidence_bundle_available": True,
                "winner_selected": False,
                "conflicted": True,
            }
            for item in context["view"].open_conflicts
        ]
        relationships = [
            {
                **item,
                "participating_relationship_references": item["relationship_ids"],
                "winner_selected": False,
                "conflicted": True,
            }
            for item in context["relationship_view"].open_conflicts
        ]
        records = sorted(
            memory + relationships, key=lambda item: item["conflict_id"]
        )
        page, more = self._page(records, plan)
        return {"conflicts": page, "winner_selected": False}, {
            "status": (
                MemoryQueryResultStatus.CONFLICTED.value
                if records
                else MemoryQueryResultStatus.NO_DATA.value
            ),
            "truncated": more,
            "has_more": more,
            "event_ids": _event_ids(page),
            "relationship_ids": _relationship_ids(page),
            "conflict_ids": [item["conflict_id"] for item in page],
            "conflict_count": len(page),
            "result_count": len(page),
        }

    def _query_resolved_conflicts(self, scope: Any, request: Any, plan: Any, context: Any):
        records = [
            {
                "conflict_id": item.conflict_id,
                "conflict_type": item.conflict_type,
                "status": "resolved",
                "original_conflicting_items": list(item.conflicting_event_ids),
                "resolution_item": item.resolution_event_id,
                "resolution_time": item.resolved_at,
                "resolution_provenance": item.resolution_reason,
                "earlier_unresolved_interval": {
                    "from": item.system_effective_at,
                    "until": item.resolved_at,
                },
                "current_resolved_state": item.resolution_event_id,
            }
            for item in context["view"].resolved_conflicts
        ]
        relationship_conflicts = self.relationships._conflicts_as_known(
            scope, plan.valid_at, plan.known_at
        )
        records.extend(
            {
                "conflict_id": item["conflict_id"],
                "conflict_type": item["conflict_type"],
                "status": "resolved",
                "original_conflicting_items": item["relationship_ids"],
                "resolution_item": item["resolution_relationship_id"],
                "resolution_time": item["resolved_at"],
                "resolution_provenance": item["reason"],
                "earlier_unresolved_interval": {
                    "from": item["system_effective_at"],
                    "until": item["resolved_at"],
                },
                "current_resolved_state": item["resolution_relationship_id"],
            }
            for item in relationship_conflicts
            if item["conflict_status"] == "resolved"
        )
        records.sort(key=lambda item: item["conflict_id"])
        page, more = self._page(records, plan)
        return {"conflicts": page}, {
            "no_data": not records,
            "truncated": more,
            "has_more": more,
            "event_ids": _event_ids(page),
            "relationship_ids": _relationship_ids(page),
            "conflict_ids": [item["conflict_id"] for item in page],
            "result_count": len(page),
        }

    def _query_evidence_for_event(self, scope: Any, request: Any, plan: Any, context: Any):
        projection = next(
            (
                item
                for item in context["view"].projections
                if item.event_id == request.event_id
            ),
            None,
        )
        if (
            projection is None
            or projection.system_known_from > plan.known_at
            or projection.valid_from > plan.valid_at
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_TARGET_NOT_FOUND",
                "The requested memory target was not found in authenticated scope.",
            )
        event = self.state.admission.get_admitted_event(scope, request.event_id)
        try:
            trace = self.state.admission.trace_admitted_memory_origin(
                scope, request.event_id, include_evidence_preview=False
            )
            origin = "source_ledger"
            status = MemoryQueryResultStatus.ANSWERED.value
        except MemoryAdmissionError:
            trace = {
                "admitted_event_id": request.event_id,
                "source_content_included": False,
                "evidence": [],
            }
            origin = "external_event"
            status = MemoryQueryResultStatus.PARTIAL.value
        return {
            "event": safe_event_projection(event),
            "origin_category": origin,
            "origin_chain": trace,
            "source_provenance_available": origin == "source_ledger",
        }, {
            "status": status,
            "event_ids": [request.event_id],
            "result_count": 1,
        }

    def _query_evidence_for_current_state(self, scope: Any, request: Any, plan: Any, context: Any):
        payload, metadata = self._query_current_state(scope, request, plan, context)
        payload["selection_exclusions"] = dict(context["view"].excluded_counts)
        payload["ledger_evolution"] = [
            item.to_dict()
            for item in self.state.ledger.list_evolutions(scope)
            if item.source_event_id in metadata.get("event_ids", [])
            or item.replacement_event_id in metadata.get("event_ids", [])
        ]
        payload["temporal_dynamics_factors"] = [
            item.to_dict()
            for item in context["dynamics"].signals
            if item.latest_occurrence_event_id in metadata.get("event_ids", [])
        ]
        return payload, metadata

    def _query_provenance_trace(self, scope: Any, request: Any, plan: Any, context: Any):
        if request.event_id:
            self._require_event_visible_at_boundary(
                request.event_id, plan, context
            )
            event = self.state.admission.get_admitted_event(scope, request.event_id)
            nodes = [
                {"node_type": "event", "node_id": request.event_id},
            ]
            edges = []
            try:
                trace = self.state.admission.trace_admitted_memory_origin(
                    scope, request.event_id
                )
                for node_type, key in (
                    ("admission", "admission_id"),
                    ("candidate", "candidate_id"),
                    ("source", "source_id"),
                ):
                    nodes.append({"node_type": node_type, "node_id": trace[key]})
                edges.extend(
                    [
                        {
                            "edge_type": "admitted_as",
                            "from": trace["candidate_id"],
                            "to": request.event_id,
                        },
                        {
                            "edge_type": "derived_from",
                            "from": trace["candidate_id"],
                            "to": trace["source_id"],
                        },
                    ]
                )
            except MemoryAdmissionError:
                pass
            return {
                "target": {"type": "event", "id": request.event_id},
                "nodes": nodes,
                "edges": edges,
                "extra_relationships_inferred": False,
                "event_type": event_signal(event),
            }, {"event_ids": [request.event_id], "result_count": len(nodes)}
        if request.entity_id:
            trace = self.entity_history.trace_entity_origin(scope, request.entity_id)
            return {
                "target": {"type": "entity", "id": request.entity_id},
                "nodes": [
                    {"node_type": "entity", "node_id": request.entity_id},
                    {"node_type": "source", "node_id": trace["source"]["source_id"]},
                ],
                "edges": [
                    {
                        "edge_type": "supported_by",
                        "from": request.entity_id,
                        "to": trace["source"]["source_id"],
                    }
                ],
            }, {"entity_ids": [request.entity_id], "result_count": 2}
        if request.relationship_id:
            trace = self.entity_history.trace_relationship_origin(
                scope, request.relationship_id
            )
            source_ids = sorted(
                {
                    item["source_id"]
                    for item in trace["relationship_evidence"]
                }
            )
            return {
                "target": {
                    "type": "relationship",
                    "id": request.relationship_id,
                },
                "nodes": [
                    {"node_type": "relationship", "node_id": request.relationship_id},
                    *[
                        {"node_type": "source", "node_id": source_id}
                        for source_id in source_ids
                    ],
                ],
                "edges": [
                    {
                        "edge_type": "supported_by",
                        "from": request.relationship_id,
                        "to": source_id,
                    }
                    for source_id in source_ids
                ],
            }, {
                "relationship_ids": [request.relationship_id],
                "result_count": len(source_ids) + 1,
            }
        typed_targets = (
            ("source", request.source_id, "prmr_sources", "source_id"),
            ("candidate", request.candidate_id, "prmr_candidate_memories", "candidate_id"),
            ("admission", request.admission_id, "prmr_memory_admission_decisions", "admission_id"),
            ("packet", request.packet_id, "prmr_memory_dynamics_snapshots", "packet_id"),
            (
                "reconstruction",
                request.reconstruction_id,
                "prmr_memory_reconstructions",
                "reconstruction_id",
            ),
            (
                "dynamics_snapshot",
                request.dynamics_snapshot_id,
                "prmr_memory_dynamics_snapshots",
                "dynamics_snapshot_id",
            ),
        )
        for target_type, identifier, table_name, id_field in typed_targets:
            if not identifier:
                continue
            row = self._typed_provenance_row(
                scope, table_name, id_field, identifier
            )
            if row is None:
                raise MemoryQueryError(
                    "MEMORY_QUERY_TARGET_NOT_FOUND",
                    "The requested memory target was not found in authenticated scope.",
                )
            payload = _json_payload(row["payload_json"])
            references = self._typed_provenance_references(payload)
            nodes = [
                {"node_type": target_type, "node_id": identifier},
                *[
                    {"node_type": node_type, "node_id": node_id}
                    for node_type, node_id in references
                ],
            ]
            return {
                "target": {"type": target_type, "id": identifier},
                "nodes": nodes,
                "edges": [
                    {
                        "edge_type": "references",
                        "from": identifier,
                        "to": node_id,
                    }
                    for _, node_id in references
                ],
                "extra_relationships_inferred": False,
            }, {
                "event_ids": [
                    node_id for node_type, node_id in references if node_type == "event"
                ],
                "entity_ids": [
                    node_id for node_type, node_id in references if node_type == "entity"
                ],
                "relationship_ids": [
                    node_id
                    for node_type, node_id in references
                    if node_type == "relationship"
                ],
                "result_count": len(nodes),
            }
        raise MemoryQueryError(
            "MEMORY_QUERY_REQUEST_INVALID",
            "provenance_trace requires a supported typed target.",
        )

    def _query_state_as_known_at(self, scope: Any, request: Any, plan: Any, context: Any):
        return self._query_bitemporal(scope, request, plan, context)

    def _query_state_at_valid_time(self, scope: Any, request: Any, plan: Any, context: Any):
        return self._query_bitemporal(scope, request, plan, context)

    def _query_bitemporal_state(self, scope: Any, request: Any, plan: Any, context: Any):
        return self._query_bitemporal(scope, request, plan, context)

    def _query_bitemporal(self, scope: Any, request: Any, plan: Any, context: Any):
        reconstruction = self.reconstruction.reconstruct_bitemporal(
            scope,
            plan.valid_at,
            plan.known_at,
            self._subject_scope(request),
            persist=False,
        )
        dynamics = context["dynamics"]
        payload = {
            "reconstruction_id": reconstruction.reconstruction_id,
            "reconstruction_hash": reconstruction.reconstruction_hash,
            "current_state": (
                reconstruction.ordered_state_transitions[-1]
                if reconstruction.ordered_state_transitions
                else None
            ),
            "effective_events": list(reconstruction.effective_event_ids),
            "excluded_counts": dict(reconstruction.excluded_counts),
            "conflicts": list(reconstruction.open_conflicts),
            "dynamics_snapshot": dynamics.snapshot.to_dict(),
            "evidence_available": bool(reconstruction.provenance_references),
        }
        return payload, {
            "no_data": not reconstruction.effective_event_ids,
            "event_ids": list(reconstruction.effective_event_ids),
            "conflict_ids": [
                item["conflict_id"] for item in reconstruction.open_conflicts
            ],
            "reconstruction_ids": [reconstruction.reconstruction_id],
            "result_count": len(reconstruction.effective_event_ids),
        }

    def _query_entity_state(self, scope: Any, request: Any, plan: Any, context: Any):
        view = context["entity_view"]
        if view is None:
            raise MemoryQueryError(
                "MEMORY_QUERY_TARGET_NOT_FOUND",
                "The requested entity was not found in authenticated scope.",
            )
        packet = (
            self.entities.generate_entity_continuity(
                scope,
                request.entity_id,
                MemoryTemporalBoundary(valid_at=plan.valid_at, known_at=plan.known_at),
                persist_dynamics=False,
            )
            if request.include_packet
            else None
        )
        payload = {
            "requested_entity_id": request.entity_id,
            "canonical_entity_id": view.canonical_entity_id,
            "entity_type": view.canonical_type,
            "canonical_label": view.canonical_label,
            "active_aliases": list(view.aliases),
            "stable_identifier_hints": list(view.stable_identifiers),
            "first_seen": view.first_seen,
            "last_seen": view.last_seen,
            "linked_event_count": view.linked_event_count,
            "memory_phase_summary": view.temporal_memory_summary,
            "current_state": view.current_event_state_summary,
            "open_event_conflicts": [
                item.to_dict() for item in context["view"].open_conflicts
            ],
            "effective_relationship_count": view.active_relationship_count,
            "open_relationship_conflicts": view.open_relationship_conflict_count,
            "related_entities": list(view.related_entity_ids),
            "entity_continuity_packet_id": packet["packet_id"] if packet else None,
            "evidence_bundle_available": view.source_count > 0,
        }
        return payload, {
            "entity_ids": [view.canonical_entity_id],
            "event_ids": self._entity_event_ids(
                scope, view.canonical_entity_id, plan.valid_at, plan.known_at
            ),
            "packet_ids": [packet["packet_id"]] if packet else [],
            "result_count": 1,
        }

    def _query_entity_history(self, scope: Any, request: Any, plan: Any, context: Any):
        reconstruction = self.entity_history.reconstruct_entity_bitemporal(
            scope,
            request.entity_id,
            valid_at=plan.valid_at,
            known_at=plan.known_at,
            persist=False,
        )
        payload = {
            "identity_creation": reconstruction["entity"],
            "identifiers": reconstruction["effective_identifiers"],
            "aliases": reconstruction["effective_aliases"],
            "rename_history": reconstruction["effective_aliases"],
            "distinctness_assertions": self._entity_table_payloads(
                scope, "prmr_entity_distinctness_assertions", plan.known_at
            ),
            "merge_history": self._entity_table_payloads(
                scope, "prmr_entity_merges", plan.known_at
            ),
            "mentions": reconstruction["entity_mentions"],
            "linked_events": reconstruction["linked_events"],
            "temporal_phase_changes": [],
            "effective_relationships": reconstruction["effective_relationships"],
            "relationship_evolution": self._relationship_evolutions(
                scope, None, plan.known_at
            ),
            "conflicts": reconstruction["open_conflicts"],
            "reconstruction_boundaries": reconstruction["temporal_boundary"],
            "provenance_references": reconstruction["provenance_references"],
            "canonical_entity_id": reconstruction["canonical_entity_id"],
            "reconstruction_id": reconstruction["reconstruction_id"],
        }
        items = (
            payload["mentions"]
            + payload["linked_events"]
            + payload["effective_relationships"]
        )
        page, more = self._page(items, plan)
        payload["history"] = page
        return payload, {
            "entity_ids": [reconstruction["canonical_entity_id"]],
            "event_ids": [
                item["event_id"] for item in reconstruction["linked_events"]
            ],
            "relationship_ids": [
                item["relationship_id"]
                for item in reconstruction["effective_relationships"]
            ],
            "reconstruction_ids": [reconstruction["reconstruction_id"]],
            "truncated": more,
            "has_more": more,
            "result_count": len(page),
        }

    def _query_relationship_state(self, scope: Any, request: Any, plan: Any, context: Any):
        relationships = [
            item
            for item in context["relationship_view"].effective_relationships
            if request.relationship_id is None
            or item.relationship_id == request.relationship_id
        ]
        records = [
            {
                "relationship_id": item.relationship_id,
                "subject_canonical_entity": self.entities.identity.resolver.resolve_canonical_entity_id(
                    scope, item.subject_entity_id, known_at=plan.known_at
                ),
                "relationship_type": item.relationship_type,
                "object_canonical_entity": self.entities.identity.resolver.resolve_canonical_entity_id(
                    scope, item.object_entity_id, known_at=plan.known_at
                ),
                "epistemic_status": item.epistemic_status,
                "valid_interval": {
                    "from": item.valid_from,
                    "until": item.valid_until,
                },
                "system_known_interval": {
                    "from": item.system_known_from,
                    "until": item.system_known_until,
                },
                "relationship_status": item.relationship_status,
                "conflict_ids": [
                    conflict["conflict_id"]
                    for conflict in context["relationship_view"].open_conflicts
                    if item.relationship_id in conflict["relationship_ids"]
                ],
                "source_evidence_available": bool(item.originating_source_id),
                "conflicted": any(
                    item.relationship_id in conflict["relationship_ids"]
                    for conflict in context["relationship_view"].open_conflicts
                ),
            }
            for item in relationships
        ]
        records.sort(
            key=lambda item: (
                item["relationship_type"],
                item["subject_canonical_entity"],
                item["object_canonical_entity"],
                item["relationship_id"],
            )
        )
        page, more = self._page(records, plan)
        return {"relationships": page, "causation_inferred": False}, {
            "no_data": not records,
            "truncated": more,
            "has_more": more,
            "relationship_ids": [item["relationship_id"] for item in page],
            "entity_ids": sorted(
                {
                    value
                    for item in page
                    for value in (
                        item["subject_canonical_entity"],
                        item["object_canonical_entity"],
                    )
                }
            ),
            "conflict_ids": _conflict_ids(page),
            "result_count": len(page),
        }

    def _query_relationship_history(self, scope: Any, request: Any, plan: Any, context: Any):
        relationship = self.relationships.admission.get_relationship(
            scope, request.relationship_id
        )
        evolutions = self._relationship_evolutions(
            scope, request.relationship_id, plan.known_at
        )
        conflicts = [
            item
            for item in self.relationships._conflicts_as_known(
                scope, plan.valid_at, plan.known_at
            )
            if request.relationship_id in item["relationship_ids"]
        ]
        history = [
            {
                "history_type": "relationship_creation",
                **relationship.to_dict(),
            },
            *[
                {"history_type": item["evolution_type"], **item}
                for item in evolutions
            ],
            *[
                {"history_type": "conflict", **item}
                for item in conflicts
            ],
        ]
        history.sort(
            key=lambda item: (
                str(
                    item.get("system_effective_at")
                    or item.get("system_known_from")
                    or item.get("created_at")
                    or ""
                ),
                str(item.get("relationship_evolution_id") or item.get("conflict_id") or ""),
            )
        )
        page, more = self._page(history, plan)
        return {
            "relationship_id": request.relationship_id,
            "history": page,
            "historical_relationships_preserved": True,
            "causation_inferred": False,
        }, {
            "truncated": more,
            "has_more": more,
            "relationship_ids": [request.relationship_id],
            "entity_ids": [
                relationship.subject_entity_id,
                relationship.object_entity_id,
            ],
            "conflict_ids": [item["conflict_id"] for item in conflicts],
            "result_count": len(page),
        }

    def _query_recoverability_explanation(self, scope: Any, request: Any, plan: Any, context: Any):
        packet = self.dynamics.build_continuity_packet(
            scope,
            self._subject_scope(request),
            MemoryTemporalBoundary(valid_at=plan.valid_at, known_at=plan.known_at),
            persist_dynamics=False,
        )
        factors = packet.get("provenance", {}).get(
            "recoverability_factor_breakdown", {}
        )
        payload = {
            "recoverability_score": packet.get("recoverability_score"),
            "engine_revision": packet.get("provenance", {}).get(
                "algorithm_revision"
            ),
            "exact_factor_values": factors,
            "content_availability_factor": factors.get("has_content_ratio"),
            "ordering_factor": factors.get("has_order_ratio"),
            "event_id_factor": factors.get("has_anchor_ratio"),
            "timestamp_factor": factors.get("has_timestamp_ratio"),
            "lineage_factor": factors.get("lineage_factor"),
            "volume_factor": factors.get("event_volume_factor"),
            "contributing_event_count": packet.get("event_count", 0),
            "missing_factor_information": sorted(
                key
                for key in (
                    "has_content_ratio",
                    "has_order_ratio",
                    "has_anchor_ratio",
                    "has_timestamp_ratio",
                    "lineage_factor",
                    "event_volume_factor",
                )
                if key not in factors
            ),
            "event_references": packet.get("provenance", {}).get(
                "source_event_ids", []
            ),
            "packet_id": packet.get("packet_id"),
            "score_recalculated": False,
        }
        return payload, {
            "event_ids": payload["event_references"],
            "packet_ids": [packet["packet_id"]],
            "result_count": 1,
        }

    def _query_unknown_information(self, scope: Any, request: Any, plan: Any, context: Any):
        projection_map = {item.event_id: item for item in context["view"].projections}
        signal_map = {
            item.signal_key: item for item in context["dynamics"].signals
        }
        records = []
        for event in context["view"].effective_events:
            if (
                str(event.get("type") or event.get("event_type")) != "information.unknown"
                and epistemic_status_for_event(event) != "unknown"
            ):
                continue
            projection = projection_map.get(str(event.get("event_id")))
            signal = signal_map.get(signal_key_for_event(event))
            records.append(
                {
                    "event_id": str(event.get("event_id")),
                    "exact_unknown_statement": event_signal(event),
                    "occurred_at": event_time(event),
                    "valid_time": projection.valid_from if projection else event_time(event),
                    "known_time": projection.system_known_from if projection else event_time(event),
                    "entity_links": self._event_entity_links(
                        scope, str(event.get("event_id")), plan.valid_at, plan.known_at
                    ),
                    "source_id": projection.source_id if projection else None,
                    "evidence_available": bool(projection and projection.source_id),
                    "current_memory_phase": signal.memory_phase if signal else None,
                    "later_information_resolved": False,
                    "resolution_event": None,
                    "epistemic_status": "unknown",
                }
            )
        records.sort(key=lambda item: (item["occurred_at"], item["event_id"]))
        page, more = self._page(records, plan)
        return {"unknown_items": page, "gap_filled_automatically": False}, {
            "status": (
                MemoryQueryResultStatus.UNKNOWN.value
                if records
                else MemoryQueryResultStatus.NO_DATA.value
            ),
            "truncated": more,
            "has_more": more,
            "event_ids": [item["event_id"] for item in page],
            "entity_ids": sorted(
                {
                    link["entity_id"]
                    for item in page
                    for link in item["entity_links"]
                }
            ),
            "result_count": len(page),
        }

    def _query_continuity_packet(self, scope: Any, request: Any, plan: Any, context: Any):
        packet = self.dynamics.build_continuity_packet(
            scope,
            self._subject_scope(request),
            MemoryTemporalBoundary(valid_at=plan.valid_at, known_at=plan.known_at),
            persist_dynamics=False,
        )
        payload = {
            "packet": packet,
            "packet_id": packet["packet_id"],
            "packet_hash": packet.get("provenance", {}).get(
                "deterministic_packet_hash"
            ),
            "continuity_revision": packet.get("provenance", {}).get(
                "algorithm_revision"
            ),
            "temporal_policy": packet.get("memory_dynamics_context", {}).get(
                "temporal_policy_id"
            ),
            "temporal_boundary": packet.get("memory_dynamics_context", {}).get(
                "temporal_boundary"
            ),
            "effective_event_manifest": packet.get(
                "memory_dynamics_context", {}
            ).get("resolved_event_manifest_hash"),
            "unresolved_conflicts": [
                item.to_dict() for item in context["view"].open_conflicts
            ],
        }
        return payload, {
            "no_data": not context["view"].effective_events,
            "event_ids": [
                str(item.get("event_id")) for item in context["view"].effective_events
            ],
            "packet_ids": [packet["packet_id"]],
            "conflict_ids": [
                item.conflict_id for item in context["view"].open_conflicts
            ],
            "result_count": 1,
        }

    def _query_fingerprint(
        self, scope: AuthenticatedScope, plan: MemoryQueryPlan, memory_manifest: str
    ) -> str:
        return sha256_text(
            canonical_json(
                {
                    "normalised_query_request": plan.normalised_query_payload,
                    "authenticated_scope": scope.memory_boundary(),
                    "query_plan_hash": plan.query_plan_hash_sha256,
                    "memory_manifest": memory_manifest,
                    "query_schema_revision": MEMORY_QUERY_SCHEMA_REVISION,
                    "query_policy_revision": MEMORY_QUERY_POLICY_REVISION,
                    "query_planner_revision": MEMORY_QUERY_PLANNER_REVISION,
                }
            )
        )

    def _page(self, values: list[Any], plan: MemoryQueryPlan) -> tuple[list[Any], bool]:
        start = plan.cursor_offset
        end = start + plan.maximum_results
        return values[start:end], len(values) > end

    @staticmethod
    def _subject_scope(request: MemoryQueryRequest) -> dict[str, str | None]:
        return {
            "application_reference": request.application_reference,
            "actor_reference": request.actor_reference,
            "workspace_reference": request.workspace_reference,
            "entity_reference": None,
            "session_reference": request.session_reference,
        }

    @staticmethod
    def _result_subject_scope(
        scope: AuthenticatedScope, request: MemoryQueryRequest
    ) -> dict[str, str | None]:
        return {
            "client_id": scope.client_id,
            "vault_id": scope.vault_id,
            "namespace": scope.namespace,
            **MemoryQueryEngine._subject_scope(request),
        }

    def _insert_pending_run(self, run: MemoryQueryRun) -> None:
        columns = (
            "query_run_id,query_type,query_mode,query_policy_id,client_id,vault_id,"
            "namespace,application_reference,actor_reference,workspace_reference,"
            "entity_id,relationship_id,event_id,signal_key,valid_at,known_at,"
            "query_fingerprint_sha256,query_plan_hash_sha256,"
            "resolved_event_manifest_hash,relevant_memory_manifest_hash,"
            "query_status,result_status,result_id,result_hash_sha256,"
            "evidence_bundle_id,truncated,memory_query_schema_revision,"
            "memory_query_policy_revision,memory_query_planner_revision,started_at,"
            "completed_at,created_at,updated_at,payload_json"
        )
        values = (
            run.query_run_id,
            run.query_type,
            run.query_mode,
            run.query_policy_id,
            run.client_id,
            run.vault_id,
            run.namespace,
            run.application_reference,
            run.actor_reference,
            run.workspace_reference,
            run.entity_id,
            run.relationship_id,
            run.event_id,
            run.signal_key,
            run.valid_at,
            run.known_at,
            run.query_fingerprint_sha256,
            run.query_plan_hash_sha256,
            run.resolved_event_manifest_hash,
            run.relevant_memory_manifest_hash,
            run.query_status,
            run.result_status,
            run.result_id,
            run.result_hash_sha256,
            run.evidence_bundle_id,
            int(run.truncated),
            run.memory_query_schema_revision,
            run.memory_query_policy_revision,
            run.memory_query_planner_revision,
            run.started_at,
            run.completed_at,
            run.created_at,
            run.updated_at,
            json_value(self.repository, run),
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.run_table}({columns}) VALUES("
                + ",".join([self.p] * len(values))
                + ")",
                values,
            )

    def _persist_completed(
        self,
        scope: AuthenticatedScope,
        run: MemoryQueryRun,
        result: MemoryQueryResult,
        bundle: MemoryEvidenceBundle | None,
        explanation: MemoryExplanation | None,
    ) -> None:
        with self.repository.connect() as connection:
            if getattr(self.repository, "backend_name", "sqlite") == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"INSERT INTO {self.result_table}("
                "query_result_id,query_run_id,query_type,result_status,client_id,"
                "vault_id,namespace,result_manifest_hash_sha256,result_hash_sha256,"
                "memory_query_result_revision,generated_at,created_at,payload_json)"
                " VALUES(" + ",".join([self.p] * 13) + ")",
                (
                    result.query_result_id,
                    result.query_run_id,
                    result.query_type,
                    result.result_status,
                    *scope.memory_boundary(),
                    result.result_manifest_hash_sha256,
                    result.result_hash_sha256,
                    result.memory_query_result_revision,
                    result.generated_at,
                    result.created_at,
                    json_value(self.repository, result),
                ),
            )
            if bundle:
                connection.execute(
                    f"INSERT INTO {self.bundle_table}("
                    "evidence_bundle_id,query_run_id,client_id,vault_id,namespace,"
                    "evidence_manifest_hash_sha256,completeness_status,"
                    "evidence_item_count,truncated,memory_evidence_bundle_revision,"
                    "created_at,payload_json) VALUES("
                    + ",".join([self.p] * 12)
                    + ")",
                    (
                        bundle.evidence_bundle_id,
                        bundle.query_run_id,
                        *scope.memory_boundary(),
                        bundle.evidence_manifest_hash_sha256,
                        bundle.completeness_status,
                        bundle.evidence_item_count,
                        int(bundle.truncated),
                        bundle.memory_evidence_bundle_revision,
                        bundle.created_at,
                        json_value(self.repository, bundle),
                    ),
                )
                for item in bundle.evidence_items:
                    connection.execute(
                        f"INSERT INTO {self.evidence_table}("
                        "evidence_item_id,evidence_bundle_id,query_run_id,client_id,"
                        "vault_id,namespace,source_id,segment_id,event_id,entity_id,"
                        "relationship_id,candidate_id,admission_id,evidence_type,"
                        "integrity_status,sequence_index,content_hash_sha256,payload_json)"
                        " VALUES(" + ",".join([self.p] * 18) + ")",
                        (
                            item.evidence_item_id,
                            bundle.evidence_bundle_id,
                            run.query_run_id,
                            *scope.memory_boundary(),
                            item.source_id,
                            item.segment_id,
                            item.event_id,
                            item.entity_id,
                            item.relationship_id,
                            item.candidate_id,
                            item.admission_id,
                            item.evidence_type,
                            item.integrity_status,
                            item.sequence_index,
                            item.content_hash_sha256,
                            json_value(self.repository, item),
                        ),
                    )
            if explanation:
                connection.execute(
                    f"INSERT INTO {self.explanation_table}("
                    "explanation_id,query_run_id,query_result_id,client_id,vault_id,"
                    "namespace,explanation_type,explanation_status,"
                    "explanation_hash_sha256,memory_explanation_revision,created_at,"
                    "payload_json) VALUES(" + ",".join([self.p] * 12) + ")",
                    (
                        explanation.explanation_id,
                        explanation.query_run_id,
                        explanation.query_result_id,
                        *scope.memory_boundary(),
                        explanation.explanation_type,
                        explanation.explanation_status,
                        explanation.explanation_hash_sha256,
                        explanation.memory_explanation_revision,
                        explanation.created_at,
                        json_value(self.repository, explanation),
                    ),
                )
            connection.execute(
                f"UPDATE {self.run_table} SET query_status={self.p},"
                f"result_status={self.p},result_id={self.p},result_hash_sha256={self.p},"
                f"evidence_bundle_id={self.p},truncated={self.p},completed_at={self.p},"
                f"updated_at={self.p},payload_json={self.p} WHERE query_run_id={self.p}",
                (
                    run.query_status,
                    run.result_status,
                    run.result_id,
                    run.result_hash_sha256,
                    run.evidence_bundle_id,
                    int(run.truncated),
                    run.completed_at,
                    run.updated_at,
                    json_value(self.repository, run),
                    run.query_run_id,
                ),
            )

    def _mark_failed(
        self, scope: AuthenticatedScope, run: MemoryQueryRun, code: str, duration: float
    ) -> None:
        completed = utc(None)
        failed = replace(
            run,
            query_status="failed",
            error_code=code,
            completed_at=completed,
            duration_ms=duration,
            updated_at=completed,
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.run_table} SET query_status={self.p},"
                f"completed_at={self.p},updated_at={self.p},payload_json={self.p} "
                f"WHERE query_run_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (
                    "failed",
                    completed,
                    completed,
                    json_value(self.repository, failed),
                    run.query_run_id,
                    *scope.memory_boundary(),
                ),
            )

    def _run_by_fingerprint(
        self, scope: AuthenticatedScope, fingerprint: str
    ) -> MemoryQueryRun | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.run_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND query_fingerprint_sha256={self.p}",
                (*scope.memory_boundary(), fingerprint),
            ).fetchone()
        return run_from_row(row) if row else None

    def _scoped_row(
        self,
        table_name: str,
        id_field: str,
        identifier: str,
        scope: AuthenticatedScope,
    ) -> Any | None:
        with self.repository.connect() as connection:
            return connection.execute(
                f"SELECT payload_json FROM {table_name} WHERE {id_field}={self.p} "
                f"AND client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                (identifier, *scope.memory_boundary()),
            ).fetchone()

    def _persist_comparison(
        self, scope: AuthenticatedScope, comparison: MemoryQueryResultComparison
    ) -> None:
        now = utc(None)
        with self.repository.connect() as connection:
            if getattr(self.repository, "backend_name", "sqlite") == "sqlite":
                connection.execute(
                    f"INSERT OR IGNORE INTO {self.comparison_table} VALUES("
                    + ",".join([self.p] * 9)
                    + ")",
                    (
                        comparison.comparison_hash_sha256,
                        comparison.first_result_id,
                        comparison.second_result_id,
                        *scope.memory_boundary(),
                        comparison.comparison_revision,
                        now,
                        json_value(self.repository, comparison),
                    ),
                )
            else:
                connection.execute(
                    f"INSERT INTO {self.comparison_table} VALUES("
                    + ",".join([self.p] * 9)
                    + ") ON CONFLICT(comparison_hash_sha256) DO NOTHING",
                    (
                        comparison.comparison_hash_sha256,
                        comparison.first_result_id,
                        comparison.second_result_id,
                        *scope.memory_boundary(),
                        comparison.comparison_revision,
                        now,
                        json_value(self.repository, comparison),
                    ),
                )

    def _event_entity_links(
        self, scope: AuthenticatedScope, event_id: str, valid_at: str, known_at: str
    ) -> list[dict[str, Any]]:
        return [
            item.to_dict()
            for item in self.entities.identity.list_event_links(
                scope, event_id=event_id, valid_at=valid_at, known_at=known_at
            )
        ]

    def _entity_event_ids(
        self, scope: AuthenticatedScope, entity_id: str, valid_at: str, known_at: str
    ) -> list[str]:
        return sorted(
            item.event_id
            for item in self.entities.identity.list_event_links(
                scope, entity_id=entity_id, valid_at=valid_at, known_at=known_at
            )
        )

    def _entity_table_payloads(
        self, scope: AuthenticatedScope, name: str, known_at: str
    ) -> list[dict[str, Any]]:
        target = table(self.repository, name)
        payload_column = name != "prmr_entity_distinctness_assertions" and name != "prmr_entity_merges"
        with self.repository.connect() as connection:
            rows = connection.execute(
                (
                    f"SELECT payload_json FROM {target} "
                    if payload_column
                    else f"SELECT * FROM {target} "
                )
                + f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND system_effective_at<={self.p} "
                "ORDER BY system_effective_at",
                (*scope.memory_boundary(), known_at),
            ).fetchall()
        if payload_column:
            return [_json_payload(row["payload_json"]) for row in rows]
        return [
            {
                key: _json_payload(value)
                if key in {"entity_ids_json", "evidence_json"}
                else value
                for key, value in dict(row).items()
            }
            for row in rows
        ]

    def _relationship_evolutions(
        self, scope: AuthenticatedScope, relationship_id: str | None, known_at: str
    ) -> list[dict[str, Any]]:
        return [
            item.to_dict()
            for item in self.relationships.list_evolutions(scope)
            if item.system_effective_at <= known_at
            and (
                relationship_id is None
                or item.source_relationship_id == relationship_id
                or item.replacement_relationship_id == relationship_id
            )
        ]

    def _typed_provenance_row(
        self,
        scope: AuthenticatedScope,
        table_name: str,
        id_field: str,
        identifier: str,
    ) -> Any | None:
        target = table(self.repository, table_name)
        allowed_columns = {
            "prmr_sources": ("source_id",),
            "prmr_candidate_memories": (
                "candidate_id",
                "source_id",
                "extraction_run_id",
            ),
            "prmr_memory_admission_decisions": (
                "admission_id",
                "candidate_id",
                "source_id",
                "admitted_event_id",
            ),
            "prmr_memory_reconstructions": (
                "reconstruction_id",
                "payload_json",
            ),
            "prmr_memory_dynamics_snapshots": (
                "dynamics_snapshot_id",
                "payload_json",
            ),
        }
        columns = allowed_columns.get(table_name)
        if columns is None:
            return None
        with self.repository.connect() as connection:
            if id_field == "packet_id":
                rows = connection.execute(
                    f"SELECT dynamics_snapshot_id,payload_json FROM {target} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} "
                    f"AND namespace={self.p}",
                    scope.memory_boundary(),
                ).fetchall()
                for row in rows:
                    payload = _json_payload(row["payload_json"])
                    if payload.get("temporal_packet_id") == identifier:
                        return {
                            "payload_json": canonical_json(
                                {
                                    "packet_id": identifier,
                                    "dynamics_snapshot_id": row[
                                        "dynamics_snapshot_id"
                                    ],
                                }
                            )
                        }
                return None
            row = connection.execute(
                f"SELECT {','.join(columns)} FROM {target} "
                f"WHERE {id_field}={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (identifier, *scope.memory_boundary()),
            ).fetchone()
        if row is None:
            return None
        payload: dict[str, Any] = {}
        for column in columns:
            value = row[column]
            if column == "payload_json":
                payload.update(_json_payload(value))
            elif value is not None:
                key = "event_id" if column == "admitted_event_id" else column
                payload[key] = value
        return {"payload_json": canonical_json(payload)}

    @staticmethod
    def _require_event_visible_at_boundary(
        event_id: str,
        plan: MemoryQueryPlan,
        context: dict[str, Any],
    ) -> None:
        projection = next(
            (
                item
                for item in context["view"].projections
                if item.event_id == event_id
            ),
            None,
        )
        if (
            projection is None
            or projection.system_known_from > plan.known_at
            or projection.valid_from > plan.valid_at
        ):
            raise MemoryQueryError(
                "MEMORY_QUERY_TARGET_NOT_FOUND",
                "The requested memory target was not found in authenticated scope.",
            )

    @staticmethod
    def _typed_provenance_references(
        payload: dict[str, Any],
    ) -> list[tuple[str, str]]:
        prefixes = (
            ("source", "source_id", "src_"),
            ("candidate", "candidate_id", "cand_"),
            ("admission", "admission_id", "adm_"),
            ("event", "event_id", "evt_"),
            ("entity", "entity_id", "entity_"),
            ("relationship", "relationship_id", "rel_"),
            ("conflict", "conflict_id", "cnfl_"),
            ("packet", "packet_id", "packet_"),
            ("reconstruction", "reconstruction_id", "recon_"),
            ("dynamics_snapshot", "dynamics_snapshot_id", "dyn_"),
        )
        references: set[tuple[str, str]] = set()

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(item, str):
                        for node_type, field, prefix in prefixes:
                            if key == field and item.startswith(prefix):
                                references.add((node_type, item))
                    elif isinstance(item, list) and key.endswith("_ids"):
                        singular = key[:-4] + "_id"
                        for node_type, field, prefix in prefixes:
                            if singular == field:
                                references.update(
                                    (node_type, str(entry))
                                    for entry in item
                                    if isinstance(entry, str)
                                    and entry.startswith(prefix)
                                )
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(payload)
        return sorted(references)


def _request_from_payload(payload: dict[str, Any]) -> MemoryQueryRequest:
    fields = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "cursor_offset",
            "base_query_hash",
        }
    }
    for key in (
        "memory_phase_filter",
        "epistemic_status_filter",
        "event_type_filter",
        "relationship_type_filter",
    ):
        fields[key] = tuple(fields.get(key, []))
    fields["cursor"] = None
    return MemoryQueryRequest(**fields)


def _temporal(payload: dict[str, str | None] | None) -> MemoryTemporalBoundary:
    if not payload:
        raise MemoryQueryError(
            "MEMORY_QUERY_TEMPORAL_BOUNDARY_INVALID",
            "A complete temporal boundary is required.",
        )
    return MemoryTemporalBoundary(
        valid_at=str(payload["valid_at"]), known_at=str(payload["known_at"])
    )


def _compare_dynamics(first: list[Any], second: list[Any]) -> dict[str, Any]:
    a = {item.signal_key: item for item in first}
    b = {item.signal_key: item for item in second}
    common = sorted(set(a) & set(b))
    phase_changes = [
        {"signal_key": key, "from": a[key].memory_phase, "to": b[key].memory_phase}
        for key in common
        if a[key].memory_phase != b[key].memory_phase
    ]
    return {
        "signals_added": sorted(set(b) - set(a)),
        "signals_removed": sorted(set(a) - set(b)),
        "phase_changes": phase_changes,
        "influence_changes": [
            {
                "signal_key": key,
                "from": a[key].final_influence,
                "to": b[key].final_influence,
            }
            for key in common
            if a[key].final_influence != b[key].final_influence
        ],
        "newly_reinforced": [
            key for key in common if not a[key].reinforced and b[key].reinforced
        ],
        "newly_re_emerging": [
            key for key in common if not a[key].re_emerging and b[key].re_emerging
        ],
        "newly_dormant": [
            item["signal_key"] for item in phase_changes if item["to"] == "dormant"
        ],
        "newly_decayed": [
            item["signal_key"] for item in phase_changes if item["to"] == "decayed"
        ],
    }


def _event_ids(value: Any) -> list[str]:
    output: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in {
                    "event_id",
                    "current_state_event_id",
                    "prior_occurrence_event_id",
                    "latest_occurrence_event_id",
                    "resolution_item",
                } and isinstance(child, str) and child.startswith("evt_"):
                    output.add(child)
                elif key in {
                    "event_references",
                    "occurrence_event_ids",
                    "participating_event_references",
                    "original_conflicting_items",
                } and isinstance(child, list):
                    output.update(
                        str(value) for value in child if str(value).startswith("evt_")
                    )
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(output)


def _relationship_ids(value: Any) -> list[str]:
    output: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "relationship_id" and isinstance(child, str):
                    output.add(child)
                elif key in {
                    "relationship_ids",
                    "participating_relationship_references",
                    "original_conflicting_items",
                } and isinstance(child, list):
                    output.update(
                        str(value)
                        for value in child
                        if str(value).startswith("rel_")
                    )
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(output)


def _conflict_ids(value: Any) -> list[str]:
    output: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "conflict_id" and isinstance(child, str):
                    output.add(child)
                elif key in {"conflict_ids", "open_conflict_ids"} and isinstance(
                    child, list
                ):
                    output.update(str(value) for value in child)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(output)


def _projection_known_at(view: Any, event_id: str) -> str:
    projection = next(
        (item for item in view.projections if item.event_id == event_id), None
    )
    return projection.system_known_from if projection else ""


def _descending_text(value: str) -> tuple[int, ...]:
    return tuple(-ord(character) for character in value)


def _json_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _first(values: list[Any]) -> Any | None:
    return values[0] if values else None


__all__ = ["MemoryQueryEngine"]
