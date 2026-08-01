"""Deterministic Core Sprint 1-10 lifecycle and repository parity fixtures."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .candidate_engine import CandidateMemoryEngine
from .entity_admission import EntityAdmissionService
from .entity_candidates import EntityCandidateEngine
from .entity_store import placeholder, table
from .entity_memory_fixtures import entity_memory_fixtures
from .interpretation_engine import InterpretationEngine
from .interpretation_fixtures import RICH_STORY, recorded_fixture_items
from .interpretation_provider import RecordedFixtureInterpretationProvider
from .memory_consolidation_continuity_adapter import (
    MemoryConsolidationContinuityAdapter,
)
from .memory_consolidation_engine import MemoryConsolidationEngine
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_export_service import MemoryExportService
from .memory_governance_models import GovernanceActor
from .memory_governance_executor import MemoryGovernanceExecutor
from .memory_governance_planner import MemoryGovernancePlanner
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_ledger_service import MemoryLedgerService
from .memory_query_engine import MemoryQueryEngine
from .memory_query_models import MemoryQueryRequest, MemoryQueryType
from .relationship_admission import RelationshipAdmissionService
from .relationship_candidates import RelationshipCandidateEngine
from .runtime_failure_injection import RuntimeFailureInjector
from .source_integrity import canonical_json, sha256_text
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceInput


FIXED_BOUNDARY = MemoryTemporalBoundary(
    valid_at="2099-01-01T00:00:00Z",
    known_at="2099-01-01T00:00:00Z",
)
ADMISSION_ACTOR = AdmissionDecisionActor("test_runner", "postgres-lifecycle")
GOVERNANCE_ACTOR = GovernanceActor("test_runner", "postgres-lifecycle")


_OPERATIONAL_SEMANTIC_KEYS = {
    "created_at",
    "updated_at",
    "ingested_at",
    "generated_at",
    "completed_at",
    "started_at",
    "decided_at",
    "known_at",
    "system_effective_at",
}


def semantic_projection(value: Any) -> Any:
    """Remove backend-generated identity while retaining exact memory meaning."""

    if isinstance(value, dict):
        projected: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if (
                key in _OPERATIONAL_SEMANTIC_KEYS
                or key.endswith("_id")
                or key.endswith("_ids")
                or "hash" in key
            ):
                continue
            projected[key] = semantic_projection(item)
        return projected
    if isinstance(value, (list, tuple)):
        return [semantic_projection(item) for item in value]
    return value


def lifecycle_scope(label: str) -> AuthenticatedScope:
    return AuthenticatedScope(
        f"client_lifecycle_{label}",
        f"vault_lifecycle_{label}",
        "runtime_test",
        application_reference=f"app_lifecycle_{label}",
        actor_reference=f"actor_lifecycle_{label}",
        workspace_reference=f"workspace_lifecycle_{label}",
        session_reference=f"session_lifecycle_{label}",
    )


def run_core_lifecycle(repository: Any, label: str = "parity") -> dict[str, Any]:
    """Run Sprints 1-10 through migrated tables without runtime DDL."""

    scope = lifecycle_scope(label)
    ledger = SourceLedger(repository, initialize=False)

    story = ledger.ingest_source(
        scope,
        SourceInput(
            "plain_text",
            RICH_STORY,
            occurred_at="2025-01-01T00:00:00Z",
            application_reference=scope.application_reference,
            actor_reference=scope.actor_reference,
            workspace_reference=scope.workspace_reference,
            session_reference=scope.session_reference,
            idempotency_key=f"lifecycle-story:{label}",
        ),
    ).source
    segments = ledger.list_source_segments(
        scope, story.source_id, limit=1000
    ).items
    provider = RecordedFixtureInterpretationProvider(
        {"*": recorded_fixture_items(story, segments)}
    )
    interpretation = InterpretationEngine(
        repository,
        providers={provider.metadata.provider_id: provider},
        initialize=False,
    ).run_interpretation(
        scope,
        story.source_id,
        "model_assisted_review_v1",
        "interpretation_policy_v1",
        [
            "candidate_memory",
            "entity_candidate",
            "relationship_candidate",
            "canonical_signal_proposal",
            "unknown_result",
        ],
        provider.metadata.provider_id,
    )

    admitted: list[Any] = []
    sources: list[Any] = []
    candidates: list[Any] = []
    event_states = (
        ("queued", "active", "Project state became active."),
        ("active", "blocked", "Project state became blocked."),
        ("blocked", "resolved", "Project state became resolved."),
    )
    for index, (previous_state, current_state, signal) in enumerate(event_states):
        source = ledger.ingest_source(
            scope,
            SourceInput(
                "json",
                {
                    "event_type": "project.updated",
                    "signal": signal,
                    "previous_state": previous_state,
                    "current_state": current_state,
                    "occurred_at": f"2026-01-0{index + 1}T00:00:00Z",
                },
                occurred_at=f"2026-01-0{index + 1}T00:00:00Z",
                application_reference=scope.application_reference,
                actor_reference=scope.actor_reference,
                workspace_reference=scope.workspace_reference,
                session_reference=scope.session_reference,
                idempotency_key=f"lifecycle-event:{label}:{index}",
            ),
        ).source
        candidate = CandidateMemoryEngine(
            repository, initialize=False
        ).extract_candidates(scope, source.source_id).candidates[0]
        result = MemoryAdmissionService(
            repository, initialize=False
        ).accept_candidate(
            scope,
            candidate.candidate_id,
            ADMISSION_ACTOR,
            "Synthetic PostgreSQL lifecycle admission.",
            f"lifecycle-admission:{label}:{index}",
        )
        assert result.admitted_event is not None
        sources.append(source)
        candidates.append(candidate)
        admitted.append(result)

    evolution = MemoryLedgerService(
        repository, initialize=False
    ).supersede_admitted_memory(
        scope,
        admitted[0].admitted_event["event_id"],
        admitted[1].admitted_event["event_id"],
        ADMISSION_ACTOR,
        "Synthetic lifecycle state supersession.",
        valid_from="2026-01-02T00:00:00Z",
        system_effective_at="2098-01-01T00:00:00Z",
        idempotency_key=f"lifecycle-evolution:{label}",
    )

    dynamics = MemoryDynamicsEngine(
        repository, initialize=False
    ).compute_memory_dynamics(
        scope, temporal_boundary=FIXED_BOUNDARY
    )

    entity_fixtures = entity_memory_fixtures()
    entity_ids: list[str] = []
    for index, fixture_name in enumerate(("project_aurora", "auth_service")):
        fixture = replace(
            entity_fixtures[fixture_name],
            idempotency_key=f"lifecycle-entity-source:{label}:{index}",
        )
        source = ledger.ingest_source(scope, fixture).source
        entity_candidate = EntityCandidateEngine(
            repository, initialize=False
        ).extract_source_entities(scope, source.source_id)[0]
        entity_result = EntityAdmissionService(
            repository, initialize=False
        ).admit_entity_candidate(
            scope,
            entity_candidate.entity_candidate_id,
            ADMISSION_ACTOR,
            "create_new_entity",
            reason="Synthetic lifecycle entity admission.",
            idempotency_key=f"lifecycle-entity:{label}:{index}",
        )
        entity_ids.append(entity_result["entity"].entity_id)

    relationship_source = ledger.ingest_source(
        scope,
        replace(
            entity_fixtures["relationship_depends_auth"],
            idempotency_key=f"lifecycle-relationship-source:{label}",
        ),
    ).source
    relationship_candidate = RelationshipCandidateEngine(
        repository, initialize=False
    ).extract_source_relationships(scope, relationship_source.source_id)[0]
    relationship = RelationshipAdmissionService(
        repository, initialize=False
    ).admit_relationship_candidate(
        scope,
        relationship_candidate.relationship_candidate_id,
        ADMISSION_ACTOR,
        subject_entity_id=entity_ids[0],
        object_entity_id=entity_ids[1],
        reason="Synthetic lifecycle relationship admission.",
        idempotency_key=f"lifecycle-relationship:{label}",
    )["relationship"]

    current_request = MemoryQueryRequest(
        query_type=MemoryQueryType.CURRENT_STATE.value,
        valid_at=FIXED_BOUNDARY.valid_at,
        known_at=FIXED_BOUNDARY.known_at,
        include_evidence=False,
        include_explanation=False,
    )
    packet_request = MemoryQueryRequest(
        query_type=MemoryQueryType.CONTINUITY_PACKET.value,
        valid_at=FIXED_BOUNDARY.valid_at,
        known_at=FIXED_BOUNDARY.known_at,
        include_evidence=False,
        include_explanation=False,
    )
    query_engine = MemoryQueryEngine(repository, initialize=False)
    current = query_engine.query_memory(scope, current_request)
    packet_result = query_engine.query_memory(scope, packet_request)
    packet = packet_result.answer_payload["packet"]
    current_semantic_hash = sha256_text(
        canonical_json(semantic_projection(current.answer_payload))
    )
    packet_semantic_hash = sha256_text(
        canonical_json(semantic_projection(packet))
    )

    consolidation = MemoryConsolidationEngine(
        repository, initialize=False
    ).consolidate_memory(
        scope,
        {},
        FIXED_BOUNDARY,
        query_requests=[current_request, packet_request],
    )
    accelerated = MemoryConsolidationContinuityAdapter(
        repository, initialize=False
    ).build_continuity_packet(
        scope,
        {},
        valid_at=FIXED_BOUNDARY.valid_at,
        known_at=FIXED_BOUNDARY.known_at,
    )

    planner = MemoryGovernancePlanner(repository, initialize=False)
    request = planner.create_request(
        scope,
        action_type="export",
        target_type="actor",
        target_reference=str(scope.actor_reference),
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic lifecycle export.",
        idempotency_key=f"lifecycle-export-request:{label}",
        governance_policy_id="subject_export_v1",
        requested_at="2099-01-01T00:00:00Z",
    )
    plan = planner.plan(
        scope, request.governance_request_id, generated_at="2099-01-01T00:00:00Z"
    )
    planner.approve_governance_plan(
        scope,
        plan.governance_plan_id,
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic lifecycle export approval.",
        idempotency_key=f"lifecycle-export-approve:{label}",
        approved_at="2099-01-01T00:00:00Z",
    )
    export = MemoryExportService(
        repository, initialize=False
    ).create_export(
        scope,
        plan.governance_plan_id,
        valid_at=FIXED_BOUNDARY.valid_at,
        known_at=FIXED_BOUNDARY.known_at,
        include_raw_sources=False,
        generated_at="2099-01-01T00:00:00Z",
    )
    export_integrity = MemoryExportService(
        repository, initialize=False
    ).verify_export_integrity(scope, export.memory_export_bundle_id)

    evidence = {
        "source_ids": [story.source_id, *[item.source_id for item in sources]],
        "candidate_ids": [item.candidate_id for item in candidates],
        "admission_ids": [item.admission.admission_id for item in admitted],
        "event_ids": [item.admitted_event["event_id"] for item in admitted],
        "interpretation_request_id": interpretation.request.interpretation_request_id,
        "interpretation_response_id": (
            interpretation.response.interpretation_response_record_id
            if interpretation.response
            else None
        ),
        "evolution_id": evolution.evolution_id,
        "dynamics_snapshot_id": dynamics.snapshot.dynamics_snapshot_id,
        "dynamics_snapshot_hash": dynamics.snapshot.signal_dynamics_manifest_hash,
        "entity_ids": entity_ids,
        "relationship_candidate_id": (
            relationship_candidate.relationship_candidate_id
        ),
        "relationship_id": relationship.relationship_id,
        "current_result_hash": current.result_hash_sha256,
        "current_semantic_hash": current_semantic_hash,
        "current_result_id": current.query_result_id,
        "current_query_run_id": current.query_run_id,
        "packet_id": packet["packet_id"],
        "packet_hash": packet["provenance"]["deterministic_packet_hash"],
        "packet_semantic_hash": packet_semantic_hash,
        "accelerated_packet_id": accelerated.packet["packet_id"],
        "accelerated_packet_hash": accelerated.packet["provenance"][
            "deterministic_packet_hash"
        ],
        "consolidation_run_id": consolidation.consolidation_run_id,
        "checkpoint_id": consolidation.checkpoint_id,
        "governance_request_id": request.governance_request_id,
        "governance_plan_id": plan.governance_plan_id,
        "export_bundle_id": export.memory_export_bundle_id,
        "export_manifest_hash": export.bundle_manifest_hash_sha256,
        "export_integrity": export_integrity["verified"],
    }
    evidence["lifecycle_hash"] = sha256_text(canonical_json(evidence))
    return evidence


def prepare_export_plan(
    repository: Any, scope: AuthenticatedScope, label: str
) -> str:
    ledger = SourceLedger(repository, initialize=False)
    source = ledger.ingest_source(
        scope,
        SourceInput(
            "json",
            {
                "event_type": "project.updated",
                "signal": "Synthetic export recovery fixture.",
                "previous_state": "queued",
                "current_state": "active",
                "occurred_at": "2026-01-01T00:00:00Z",
            },
            occurred_at="2026-01-01T00:00:00Z",
            actor_reference=scope.actor_reference,
            idempotency_key=f"export-recovery-source:{label}",
        ),
    ).source
    candidate = CandidateMemoryEngine(
        repository, initialize=False
    ).extract_candidates(scope, source.source_id).candidates[0]
    MemoryAdmissionService(repository, initialize=False).accept_candidate(
        scope,
        candidate.candidate_id,
        ADMISSION_ACTOR,
        "Synthetic export recovery admission.",
        f"export-recovery-admission:{label}",
    )
    planner = MemoryGovernancePlanner(repository, initialize=False)
    request = planner.create_request(
        scope,
        action_type="export",
        target_type="actor",
        target_reference=str(scope.actor_reference),
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic export recovery request.",
        idempotency_key=f"export-recovery-request:{label}",
        governance_policy_id="subject_export_v1",
        requested_at="2099-01-01T00:00:00Z",
    )
    plan = planner.plan(
        scope, request.governance_request_id, generated_at="2099-01-01T00:00:00Z"
    )
    planner.approve_governance_plan(
        scope,
        plan.governance_plan_id,
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic export recovery approval.",
        idempotency_key=f"export-recovery-approve:{label}",
        approved_at="2099-01-01T00:00:00Z",
    )
    return plan.governance_plan_id


def run_export_atomic_recovery(repository: Any) -> dict[str, Any]:
    scope = lifecycle_scope("export_recovery")
    plan_id = prepare_export_plan(repository, scope, "postgres")
    injector = RuntimeFailureInjector(
        enabled_for_tests=True, fail_counts={"after_first_write": 1}
    )
    failed = False
    try:
        MemoryExportService(
            repository, initialize=False, failure_injector=injector
        ).create_export(
            scope,
            plan_id,
            valid_at=FIXED_BOUNDARY.valid_at,
            known_at=FIXED_BOUNDARY.known_at,
            include_raw_sources=False,
            generated_at="2099-01-01T00:00:00Z",
        )
    except Exception:
        failed = True
    p = placeholder(repository)
    request_table = table(repository, "prmr_memory_export_requests")
    bundle_table = table(repository, "prmr_memory_export_bundles")
    with repository.connect() as connection:
        request_count_after_failure = int(
            connection.execute(
                f"SELECT COUNT(*) AS count FROM {request_table} "
                f"WHERE client_id={p} AND vault_id={p} AND namespace={p}",
                scope.memory_boundary(),
            ).fetchone()["count"]
        )
        bundle_count_after_failure = int(
            connection.execute(
                f"SELECT COUNT(*) AS count FROM {bundle_table} "
                f"WHERE client_id={p} AND vault_id={p} AND namespace={p}",
                scope.memory_boundary(),
            ).fetchone()["count"]
        )
    service = MemoryExportService(repository, initialize=False)
    bundle = service.create_export(
        scope,
        plan_id,
        valid_at=FIXED_BOUNDARY.valid_at,
        known_at=FIXED_BOUNDARY.known_at,
        include_raw_sources=False,
        generated_at="2099-01-01T00:00:00Z",
    )
    verified = service.verify_export_integrity(
        scope, bundle.memory_export_bundle_id
    )["verified"]
    return {
        "failure_injected": failed,
        "request_rows_after_failure": request_count_after_failure,
        "bundle_rows_after_failure": bundle_count_after_failure,
        "retry_verified": verified,
        "passed": failed
        and request_count_after_failure == 0
        and bundle_count_after_failure == 0
        and verified,
    }


def _seed_recovery_events(
    repository: Any, scope: AuthenticatedScope, label: str
) -> list[Any]:
    results: list[Any] = []
    for index in range(3):
        source = SourceLedger(repository, initialize=False).ingest_source(
            scope,
            SourceInput(
                "json",
                {
                    "event_type": "recovery.state",
                    "signal": "Synthetic recovery state repeated.",
                    "previous_state": f"state_{index}",
                    "current_state": f"state_{index + 1}",
                    "occurred_at": f"2026-02-0{index + 1}T00:00:00Z",
                },
                occurred_at=f"2026-02-0{index + 1}T00:00:00Z",
                actor_reference=scope.actor_reference,
                idempotency_key=f"{label}:source:{index}",
            ),
        ).source
        candidate = CandidateMemoryEngine(
            repository, initialize=False
        ).extract_candidates(scope, source.source_id).candidates[0]
        results.append(
            MemoryAdmissionService(repository, initialize=False).accept_candidate(
                scope,
                candidate.candidate_id,
                ADMISSION_ACTOR,
                "Synthetic recovery admission.",
                f"{label}:admission:{index}",
            )
        )
    return results


def run_consolidation_recovery(repository: Any) -> dict[str, Any]:
    scope = lifecycle_scope("consolidation_recovery")
    _seed_recovery_events(repository, scope, "consolidation-recovery")
    engine = MemoryConsolidationEngine(repository, initialize=False)
    original_put_run = engine.store.put_run
    crashed_run_id: str | None = None

    def crash_after_running(run: Any) -> None:
        nonlocal crashed_run_id
        original_put_run(run)
        if run.status == "running":
            crashed_run_id = run.consolidation_run_id
            raise SystemExit("synthetic process interruption")

    engine.store.put_run = crash_after_running  # type: ignore[method-assign]
    interrupted = False
    try:
        engine.consolidate_memory(scope, {}, FIXED_BOUNDARY)
    except SystemExit:
        interrupted = True
    restarted = MemoryConsolidationEngine(repository, initialize=False)
    recovery = restarted.recover_incomplete_consolidation_runs(scope)
    failed_status = (
        restarted.get_consolidation_run(scope, str(crashed_run_id)).status
        if crashed_run_id
        else None
    )
    replay = restarted.consolidate_memory(scope, {}, FIXED_BOUNDARY)
    return {
        "process_interrupted": interrupted,
        "recovered_count": recovery["recovered_count"],
        "interrupted_run_status": failed_status,
        "replay_status": replay.status,
        "checkpoint_created": bool(replay.checkpoint_id),
        "passed": interrupted
        and recovery["recovered_count"] == 1
        and failed_status == "failed"
        and replay.status == "completed"
        and bool(replay.checkpoint_id),
    }


def run_governance_recovery(repository: Any) -> dict[str, Any]:
    scope = lifecycle_scope("governance_recovery")
    admitted = _seed_recovery_events(repository, scope, "governance-recovery")
    source_id = admitted[0].admission.source_id
    planner = MemoryGovernancePlanner(repository, initialize=False)
    plan = planner.plan_erasure(
        scope,
        target_type="source",
        target_reference=source_id,
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic governance recovery proof.",
        idempotency_key="governance-recovery-plan",
        generated_at="2099-01-01T00:00:00Z",
    )
    planner.approve_governance_plan(
        scope,
        plan.governance_plan_id,
        actor=GOVERNANCE_ACTOR,
        reason="Synthetic governance recovery approval.",
        idempotency_key="governance-recovery-approve",
        approved_at="2099-01-01T00:00:00Z",
    )
    executor = MemoryGovernanceExecutor(repository, initialize=False)
    partial = executor.execute(
        scope,
        plan.governance_plan_id,
        idempotency_key="governance-recovery-execute",
        started_at="2099-01-01T00:00:00Z",
        interrupt_after_items=1,
    )
    recovered = MemoryGovernanceExecutor(
        repository, initialize=False
    ).recover_incomplete_governance_executions(scope)
    replay = MemoryGovernanceExecutor(repository, initialize=False).execute(
        scope,
        plan.governance_plan_id,
        idempotency_key="governance-recovery-execute",
    )
    verification_status = (
        replay.verification.get("verification_status")
        if isinstance(replay.verification, dict)
        else (
            replay.verification.verification_status
            if replay.verification is not None
            else None
        )
    )
    return {
        "partial_status": partial.execution.execution_status,
        "recovered_execution": partial.execution.governance_execution_id in recovered,
        "final_status": replay.execution.execution_status,
        "verification_status": verification_status,
        "passed": partial.execution.execution_status == "running"
        and partial.execution.governance_execution_id in recovered
        and replay.execution.execution_status
        in {"completed", "completed_with_invalidations"}
        and verification_status == "verified",
    }


__all__ = [
    "FIXED_BOUNDARY",
    "lifecycle_scope",
    "prepare_export_plan",
    "run_core_lifecycle",
    "run_consolidation_recovery",
    "run_export_atomic_recovery",
    "run_governance_recovery",
]
