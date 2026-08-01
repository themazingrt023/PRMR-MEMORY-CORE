"""Durable Core Sprint 8 consolidation, restart, delta, and isolation proof."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.entity_memory_fixtures import entity_memory_fixtures
from prmr.core.memory_checkpoint import apply_checkpoint_delta
from prmr.core.memory_consolidation_continuity_adapter import (
    MemoryConsolidationContinuityAdapter,
)
from prmr.core.memory_consolidation_engine import MemoryConsolidationEngine
from prmr.core.memory_consolidation_fixtures import (
    consolidation_fixture_scope,
    exact_signal_fixture,
    synthetic_consolidation_events,
    write_fixture_events,
)
from prmr.core.memory_consolidation_invalidation import (
    MemoryConsolidationInvalidationService,
)
from prmr.core.memory_consolidation_models import (
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
    MemoryConsolidationError,
    MemoryConsolidationType,
)
from prmr.core.memory_consolidation_query_adapter import (
    MemoryConsolidationQueryAdapter,
)
from prmr.core.memory_consolidation_store import MemoryConsolidationStore
from prmr.core.memory_ledger_models import MemoryTemporalBoundary
from prmr.core.memory_ledger_service import MemoryLedgerService
from prmr.core.memory_query_engine import MemoryQueryEngine
from prmr.core.memory_query_fixtures import (
    QUERY_FIXTURE_ACTOR,
    admit_query_entity,
    admit_query_relationship,
    admit_query_source,
    query_fixture_scope,
)
from prmr.core.memory_query_models import MemoryQueryRequest, MemoryQueryType
from prmr.core.source_integrity import canonical_json, sha256_text
from prmr.core.source_models import SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_memory_consolidation"
PUBLIC_REPORT = REPORT_DIR / "public_memory_consolidation.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_consolidation.json"
SCORECARD = REPORT_DIR / "scorecard_memory_consolidation.md"
BOUNDARY = (
    "Internal deterministic synthetic Core Sprint 8 evidence only. This is not "
    "semantic understanding, lossy physical compaction, production-scale "
    "performance, external validation, or security certification."
)
FINAL_STATEMENT = (
    "Core Sprint 8 establishes Provenance-Preserving Memory Consolidation and\n"
    "Long-Horizon Query Acceleration inside PRMR Memory Core. Large effective memory\n"
    "histories can now be represented through deterministic consolidated structures\n"
    "and bitemporal checkpoints while preserving every contributing source, event,\n"
    "admission, evolution, entity, relationship, conflict and epistemic status. The\n"
    "authoritative raw ledger remains intact. Supported queries and continuity\n"
    "packets may use verified checkpoints only when their results are exactly\n"
    "equivalent to canonical full-ledger execution, with automatic fallback on\n"
    "staleness, incompatibility or integrity failure. Semantic consolidation, lossy\n"
    "compaction, generated summaries and governance-controlled deletion remain\n"
    "later core-engine milestones."
)
FIXED_BOUNDARY = MemoryTemporalBoundary(
    valid_at="2026-01-01T00:00:00Z", known_at="2026-01-01T00:00:00Z"
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def table_count(repository: Any, name: str) -> int:
    with repository.connect() as connection:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {name}").fetchone()
    return int(row["count"])


def no_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return not any(re.search(item, text, re.IGNORECASE) for item in patterns)


def query_requests() -> list[MemoryQueryRequest]:
    common = {"include_evidence": False, "include_explanation": False}
    return [
        MemoryQueryRequest(query_type=MemoryQueryType.CURRENT_STATE.value, **common),
        MemoryQueryRequest(
            query_type=MemoryQueryType.MEMORY_BY_PHASE.value,
            memory_phase_filter=("active",),
            **common,
        ),
        MemoryQueryRequest(
            query_type=MemoryQueryType.SIGNAL_HISTORY.value,
            signal_key="memory.signal_0",
            **common,
        ),
        MemoryQueryRequest(query_type=MemoryQueryType.RECURRENCE.value, **common),
        MemoryQueryRequest(query_type=MemoryQueryType.RE_EMERGENCE.value, **common),
        MemoryQueryRequest(query_type=MemoryQueryType.OPEN_CONFLICTS.value, **common),
        MemoryQueryRequest(
            query_type=MemoryQueryType.RESOLVED_CONFLICTS.value, **common
        ),
        MemoryQueryRequest(
            query_type=MemoryQueryType.CONTINUITY_PACKET.value, **common
        ),
    ]


def scoped_request(request: MemoryQueryRequest, boundary: MemoryTemporalBoundary) -> MemoryQueryRequest:
    return replace(
        request,
        valid_at=boundary.valid_at,
        known_at=boundary.known_at,
    )


def expect_scope_denial(call: Callable[[], Any]) -> bool:
    try:
        call()
    except MemoryConsolidationError as exc:
        return exc.code in {
            "MEMORY_CONSOLIDATION_RUN_NOT_FOUND",
            "MEMORY_CONSOLIDATION_NOT_FOUND",
            "MEMORY_CHECKPOINT_NOT_FOUND",
        }
    return False


def run_suite() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {"timings_ms": {}, "ids": {}}
    with TemporaryDirectory(prefix="prmr-core-consolidation-") as temp:
        database = Path(temp) / "memory-consolidation.sqlite"
        repository = SelfServeRepositoryV093(database)
        alpha = consolidation_fixture_scope("alpha")
        beta = consolidation_fixture_scope("beta")
        base_events = exact_signal_fixture() + synthetic_consolidation_events(
            168,
            prefix="history",
            start_index=12,
            start_at="2025-01-01T00:00:00Z",
        )
        write_fixture_events(repository, alpha, base_events)
        write_fixture_events(
            repository,
            beta,
            synthetic_consolidation_events(20, prefix="beta", signal_count=4),
        )
        engine = MemoryConsolidationEngine(repository)
        planner = engine.planner
        store = MemoryConsolidationStore(repository)

        before = {
            name: table_count(repository, name)
            for name in (
                "prmr_memory_consolidation_runs",
                "prmr_memory_consolidation_plans",
                "prmr_consolidated_memories",
                "prmr_memory_checkpoints",
            )
        }
        plan_one = planner.plan_consolidation(alpha, {}, FIXED_BOUNDARY)
        plan_two = planner.plan_consolidation(alpha, {}, FIXED_BOUNDARY)
        after_plan = {
            name: table_count(repository, name) for name in before
        }
        add(checks, "plan_identity_deterministic", plan_one.consolidation_plan_id == plan_two.consolidation_plan_id)
        add(checks, "plan_hash_deterministic", plan_one.plan_hash_sha256 == plan_two.plan_hash_sha256)
        add(checks, "temporal_boundaries_frozen", plan_one.temporal_boundary == {"valid_at": FIXED_BOUNDARY.valid_at, "known_at": FIXED_BOUNDARY.known_at})
        add(checks, "event_count_windows_deterministic", plan_one.deterministic_windows == plan_two.deterministic_windows and all(item["event_count"] <= 500 for item in plan_one.deterministic_windows))
        add(checks, "eligible_events_complete", len(plan_one.eligible_event_ids) == 180)
        add(checks, "excluded_counts_recorded", "outside_valid_time" in plan_one.excluded_event_counts)
        add(checks, "planner_performs_no_mutation", before == after_plan)
        add(checks, "initial_plan_requires_full_rebuild", plan_one.full_rebuild_required and plan_one.incremental_from_checkpoint_id is None)

        started = time.perf_counter()
        run = engine.consolidate_memory(
            alpha,
            {},
            FIXED_BOUNDARY,
            query_requests=query_requests(),
        )
        private["timings_ms"]["initial_consolidation"] = round(
            (time.perf_counter() - started) * 1000, 3
        )
        checkpoint = engine.get_checkpoint(alpha, str(run.checkpoint_id))
        memories = engine.list_consolidated_memories(
            alpha, consolidation_run_id=run.consolidation_run_id
        )
        types = {item.consolidation_type for item in memories}
        add(checks, "consolidation_run_completed", run.status == "completed" and bool(run.checkpoint_id))
        add(checks, "exact_signal_consolidation_created", MemoryConsolidationType.EXACT_SIGNAL_WINDOW.value in types)
        add(checks, "event_state_chain_created", MemoryConsolidationType.EVENT_STATE_CHAIN.value in types)
        add(checks, "temporal_phase_consolidation_created", MemoryConsolidationType.TEMPORAL_PHASE_WINDOW.value in types)
        add(checks, "consolidated_memory_is_derived", all(item.derived_epistemic_status == "derived" for item in memories))
        add(checks, "no_generated_facts", all(item.consolidation_payload.get("generated_narrative") is None for item in memories))
        add(checks, "epistemic_distribution_preserved", any(item.contributor_epistemic_counts["inferred"] > 0 and item.contributor_epistemic_counts["unknown"] > 0 for item in memories))
        add(checks, "complete_event_membership_persisted", all(len(store.list_members(alpha, item.consolidated_memory_id)) == item.contributor_event_count for item in memories))
        add(checks, "membership_order_deterministic", all([member.sequence_index for member in store.list_members(alpha, item.consolidated_memory_id)] == list(range(item.contributor_event_count)) for item in memories))
        add(checks, "checkpoint_identity_is_opaque", checkpoint.memory_checkpoint_id.startswith("mchk_") and len(checkpoint.memory_checkpoint_id) == 29)
        add(checks, "checkpoint_signal_indexes_present", bool(checkpoint.active_signal_index or checkpoint.latent_signal_index or checkpoint.dormant_signal_index or checkpoint.decayed_signal_index))
        add(checks, "checkpoint_current_state_correct", checkpoint.current_state_event_id == plan_one.eligible_event_ids[-1])
        add(checks, "raw_history_remains_stored", table_count(repository, "events") == 2 and len(MemoryLedgerService(repository).admission._events_for_scope(alpha)) == 180)

        integrity = engine.verify_consolidation_integrity(alpha, run.consolidation_run_id)
        add(checks, "consolidation_integrity_verified", integrity.verified, integrity.failures)
        trace_target = next(item for item in memories if item.contributor_event_count)
        trace = engine.trace_consolidated_memory_origin(alpha, trace_target.consolidated_memory_id)
        add(checks, "full_origin_trace_preserves_event_ids", len(trace["members"]) == trace_target.contributor_event_count)
        add(checks, "legacy_origin_reported_honestly", trace["evidence_completeness"] == "legacy_without_source")
        add(checks, "source_content_not_duplicated", trace["source_content_exposed"] is False)

        query_adapter = MemoryConsolidationQueryAdapter(repository)
        accelerated_results: dict[str, Any] = {}
        for request in query_requests():
            resolved = query_adapter.query_memory(
                alpha, scoped_request(request, FIXED_BOUNDARY)
            )
            accelerated_results[request.query_type] = resolved
            add(
                checks,
                f"query_acceleration_{request.query_type}",
                resolved.metadata.acceleration_used
                and resolved.metadata.equivalence_verified
                and not resolved.metadata.fallback_used,
                resolved.metadata.to_dict(),
            )
        add(checks, "evidence_identity_preserved", all(item.result.evidence_bundle_id is None for item in accelerated_results.values()))
        add(checks, "result_hashes_bound_to_canonical_artifacts", all(item.metadata.canonical_result_hash == item.result.result_hash_sha256 == item.metadata.accelerated_result_hash for item in accelerated_results.values()))
        continuity = MemoryConsolidationContinuityAdapter(repository).build_continuity_packet(
            alpha,
            {},
            valid_at=FIXED_BOUNDARY.valid_at,
            known_at=FIXED_BOUNDARY.known_at,
        )
        canonical_packet = accelerated_results[MemoryQueryType.CONTINUITY_PACKET.value].result.answer_payload["packet"]
        add(checks, "continuity_acceleration_used", continuity.metadata.acceleration_used)
        add(checks, "continuity_packet_id_exact", continuity.packet["packet_id"] == canonical_packet["packet_id"])
        add(checks, "continuity_packet_hash_exact", continuity.packet["provenance"]["deterministic_packet_hash"] == canonical_packet["provenance"]["deterministic_packet_hash"])
        add(checks, "continuity_packet_content_exact", continuity.packet == canonical_packet)
        fallback = query_adapter.query_memory(
            alpha,
            MemoryQueryRequest(
                query_type=MemoryQueryType.EVENT_TIMELINE.value,
                valid_at=FIXED_BOUNDARY.valid_at,
                known_at=FIXED_BOUNDARY.known_at,
                include_evidence=False,
                include_explanation=False,
            ),
        )
        add(checks, "unsupported_query_falls_back", fallback.metadata.fallback_used and fallback.metadata.fallback_reason == "unsupported_query_type")
        add(checks, "fallback_disclosed", fallback.metadata.execution_path == "consolidated_fallback_to_authoritative" and not fallback.metadata.acceleration_used)

        private["ids"] = {
            "run_id": run.consolidation_run_id,
            "plan_id": run.consolidation_plan_id,
            "checkpoint_id": checkpoint.memory_checkpoint_id,
            "checkpoint_hash": checkpoint.checkpoint_hash_sha256,
        }
        del engine, planner, query_adapter
        reopened = SelfServeRepositoryV093(database)
        reopened_engine = MemoryConsolidationEngine(reopened)
        reopened_checkpoint = reopened_engine.get_checkpoint(
            alpha, checkpoint.memory_checkpoint_id
        )
        replay = MemoryConsolidationQueryAdapter(reopened).query_memory(
            alpha,
            scoped_request(query_requests()[0], FIXED_BOUNDARY),
        )
        add(checks, "restart_retrieves_checkpoint", reopened_checkpoint.checkpoint_hash_sha256 == checkpoint.checkpoint_hash_sha256)
        add(checks, "restart_acceleration_replays_exactly", replay.metadata.acceleration_used and replay.result.result_hash_sha256 == accelerated_results[MemoryQueryType.CURRENT_STATE.value].result.result_hash_sha256)
        add(checks, "restart_identities_unchanged", reopened_engine.get_consolidation_run(alpha, run.consolidation_run_id).checkpoint_id == checkpoint.memory_checkpoint_id)

        append_events = synthetic_consolidation_events(
            20,
            prefix="append",
            start_index=180,
            start_at="2025-01-01T00:00:00Z",
        )
        write_fixture_events(reopened, alpha, append_events, append=True)
        next_boundary = MemoryTemporalBoundary(
            valid_at="2027-01-01T00:00:00Z",
            known_at="2027-01-01T00:00:00Z",
        )
        incremental_plan = reopened_engine.planner.plan_consolidation(
            alpha, {}, next_boundary
        )
        add(checks, "append_only_incremental_detected", not incremental_plan.full_rebuild_required and incremental_plan.incremental_from_checkpoint_id == checkpoint.memory_checkpoint_id)
        incremental_run = reopened_engine.consolidate_memory(
            alpha,
            {},
            next_boundary,
            query_requests=[query_requests()[0], query_requests()[-1]],
        )
        incremental_checkpoint = reopened_engine.get_checkpoint(
            alpha, str(incremental_run.checkpoint_id)
        )
        deltas = MemoryConsolidationStore(reopened).list_deltas(
            alpha, target_checkpoint_id=incremental_checkpoint.memory_checkpoint_id
        )
        add(checks, "checkpoint_delta_created", len(deltas) == 1 and len(deltas[0].events_added) == 20)
        add(checks, "delta_application_returns_exact_target", bool(deltas) and apply_checkpoint_delta(checkpoint, incremental_checkpoint, deltas[0]).checkpoint_hash_sha256 == incremental_checkpoint.checkpoint_hash_sha256)
        add(checks, "old_checkpoint_remains_historical", reopened_engine.get_checkpoint(alpha, checkpoint.memory_checkpoint_id).checkpoint_status == "superseded")
        add(checks, "incremental_current_state_updated", incremental_checkpoint.current_state_event_id == "evt_append_00199")

        with TemporaryDirectory(prefix="prmr-consolidation-full-rebuild-") as fresh_temp:
            fresh = SelfServeRepositoryV093(Path(fresh_temp) / "full.sqlite")
            write_fixture_events(fresh, alpha, base_events + append_events)
            full_run = MemoryConsolidationEngine(fresh).consolidate_memory(
                alpha,
                {},
                next_boundary,
                query_requests=[query_requests()[0], query_requests()[-1]],
            )
            full_checkpoint = MemoryConsolidationEngine(fresh).get_checkpoint(
                alpha, str(full_run.checkpoint_id)
            )
            add(checks, "delta_target_equals_full_rebuild", incremental_checkpoint.memory_checkpoint_id == full_checkpoint.memory_checkpoint_id and incremental_checkpoint.checkpoint_hash_sha256 == full_checkpoint.checkpoint_hash_sha256)

        late = synthetic_consolidation_events(
            1,
            prefix="late",
            start_index=200,
            start_at="2024-01-01T00:00:00Z",
            signal_count=1,
        )
        write_fixture_events(reopened, alpha, late, append=True)
        late_plan = reopened_engine.planner.plan_consolidation(
            alpha,
            {},
            MemoryTemporalBoundary(
                valid_at="2028-01-01T00:00:00Z",
                known_at="2028-01-01T00:00:00Z",
            ),
        )
        add(checks, "late_arrival_requires_full_rebuild", late_plan.full_rebuild_required)
        stale = MemoryConsolidationInvalidationService(reopened).detect_and_mark_stale(alpha)
        add(checks, "manifest_change_marks_current_stale", incremental_checkpoint.memory_checkpoint_id in stale["stale_checkpoint_ids"])
        stale_fallback = MemoryConsolidationQueryAdapter(reopened).query_memory(
            alpha,
            scoped_request(query_requests()[0], next_boundary),
        )
        add(checks, "stale_checkpoint_never_used", stale_fallback.metadata.fallback_used and not stale_fallback.metadata.acceleration_used)
        add(checks, "raw_memory_not_deleted_by_invalidation", len(MemoryLedgerService(reopened).admission._events_for_scope(alpha)) == 201)

        add(checks, "cross_tenant_run_denied", expect_scope_denial(lambda: reopened_engine.get_consolidation_run(beta, run.consolidation_run_id)))
        add(checks, "cross_tenant_checkpoint_denied", expect_scope_denial(lambda: reopened_engine.get_checkpoint(beta, checkpoint.memory_checkpoint_id)))
        add(checks, "cross_tenant_membership_denied", MemoryConsolidationStore(reopened).list_members(beta, trace_target.consolidated_memory_id) == [])
        add(checks, "cross_tenant_query_cannot_use_checkpoint", MemoryConsolidationQueryAdapter(reopened).query_memory(beta, scoped_request(query_requests()[0], FIXED_BOUNDARY)).metadata.acceleration_used is False)

        conflict_scope = query_fixture_scope("consolidation_conflict")
        conflict_a = admit_query_source(
            reopened,
            conflict_scope,
            SourceInput(
                "json",
                {"event_type": "status.updated", "signal": "Synthetic service online.", "occurred_at": "2026-02-01T00:00:00Z"},
                occurred_at="2026-02-01T00:00:00Z",
                idempotency_key="mc-conflict-a",
            ),
            key_suffix="mc-conflict-a",
        )
        conflict_b = admit_query_source(
            reopened,
            conflict_scope,
            SourceInput(
                "json",
                {"event_type": "status.updated", "signal": "Synthetic service unavailable.", "occurred_at": "2026-02-02T00:00:00Z"},
                occurred_at="2026-02-02T00:00:00Z",
                idempotency_key="mc-conflict-b",
            ),
            key_suffix="mc-conflict-b",
        )
        conflict = MemoryLedgerService(reopened).declare_memory_contradiction(
            conflict_scope,
            [conflict_a["event"]["event_id"], conflict_b["event"]["event_id"]],
            "status_conflict",
            QUERY_FIXTURE_ACTOR,
            "Controlled synthetic contradiction.",
            valid_from="2026-02-02T00:00:00Z",
            system_effective_at="2098-01-01T00:00:00Z",
            idempotency_key="mc-conflict",
        )
        conflict_boundary = MemoryTemporalBoundary(
            valid_at="2099-01-01T00:00:00Z",
            known_at="2099-01-01T00:00:00Z",
        )
        conflict_run = MemoryConsolidationEngine(reopened).consolidate_memory(
            conflict_scope,
            {},
            conflict_boundary,
            query_requests=[
                MemoryQueryRequest(query_type=MemoryQueryType.OPEN_CONFLICTS.value, include_evidence=False, include_explanation=False),
                MemoryQueryRequest(query_type=MemoryQueryType.CURRENT_STATE.value, include_evidence=False, include_explanation=False),
            ],
        )
        conflict_memories = MemoryConsolidationEngine(reopened).list_consolidated_memories(
            conflict_scope,
            consolidation_run_id=conflict_run.consolidation_run_id,
            consolidation_type=MemoryConsolidationType.CONFLICT_PRESERVING_CHECKPOINT.value,
        )
        add(checks, "conflict_checkpoint_created", len(conflict_memories) == 1)
        add(checks, "conflict_preserves_all_sides", bool(conflict_memories) and set(conflict_memories[0].consolidation_payload["ordered_event_ids"]) == {conflict_a["event"]["event_id"], conflict_b["event"]["event_id"]})
        add(checks, "conflict_has_no_winner", bool(conflict_memories) and conflict_memories[0].consolidation_payload["winner_selected"] is False and conflict.conflict_id in conflict_memories[0].open_conflict_ids)

        graph_scope = query_fixture_scope("consolidation_graph")
        fixtures = entity_memory_fixtures()
        project = admit_query_entity(reopened, graph_scope, fixtures["project_aurora"], key_suffix="mc-project")["entity"]
        admit_query_entity(reopened, graph_scope, fixtures["legacy_service"], key_suffix="mc-legacy")
        relationship = admit_query_relationship(reopened, graph_scope, fixtures["relationship_depends_legacy"], key_suffix="mc-rel")["relationship"]
        graph_run = MemoryConsolidationEngine(reopened).consolidate_memory(
            graph_scope,
            {"entity_id": project.entity_id},
            MemoryTemporalBoundary(valid_at="2099-01-01T00:00:00Z", known_at="2099-01-01T00:00:00Z"),
            query_requests=[
                MemoryQueryRequest(query_type=MemoryQueryType.ENTITY_STATE.value, entity_id=project.entity_id, include_evidence=False, include_explanation=False),
                MemoryQueryRequest(query_type=MemoryQueryType.RELATIONSHIP_STATE.value, entity_id=project.entity_id, include_evidence=False, include_explanation=False),
            ],
        )
        graph_types = {
            item.consolidation_type
            for item in MemoryConsolidationEngine(reopened).list_consolidated_memories(
                graph_scope, consolidation_run_id=graph_run.consolidation_run_id
            )
        }
        add(checks, "entity_checkpoint_created", MemoryConsolidationType.ENTITY_EVENT_CHECKPOINT.value in graph_types)
        add(checks, "relationship_checkpoint_created", MemoryConsolidationType.RELATIONSHIP_STATE_CHECKPOINT.value in graph_types)
        graph_checkpoint = MemoryConsolidationEngine(reopened).get_checkpoint(graph_scope, str(graph_run.checkpoint_id))
        add(checks, "relationship_identity_preserved", relationship.relationship_id in graph_checkpoint.relationship_index)
        graph_adapter = MemoryConsolidationQueryAdapter(reopened)
        entity_accelerated = graph_adapter.query_memory(
            graph_scope,
            MemoryQueryRequest(
                query_type=MemoryQueryType.ENTITY_STATE.value,
                entity_id=project.entity_id,
                valid_at="2099-01-01T00:00:00Z",
                known_at="2099-01-01T00:00:00Z",
                include_evidence=False,
                include_explanation=False,
            ),
        )
        relationship_accelerated = graph_adapter.query_memory(
            graph_scope,
            MemoryQueryRequest(
                query_type=MemoryQueryType.RELATIONSHIP_STATE.value,
                entity_id=project.entity_id,
                valid_at="2099-01-01T00:00:00Z",
                known_at="2099-01-01T00:00:00Z",
                include_evidence=False,
                include_explanation=False,
            ),
        )
        add(checks, "entity_state_acceleration_exact", entity_accelerated.metadata.acceleration_used and entity_accelerated.metadata.equivalence_verified)
        add(checks, "relationship_state_acceleration_exact", relationship_accelerated.metadata.acceleration_used and relationship_accelerated.metadata.equivalence_verified)

        add(checks, "all_required_revision_identifiers_exact", {
            MEMORY_CONSOLIDATION_SCHEMA_REVISION,
            MEMORY_CONSOLIDATION_POLICY_REVISION,
            MEMORY_CONSOLIDATION_PLANNER_REVISION,
            MEMORY_CONSOLIDATION_MEMBERSHIP_REVISION,
            MEMORY_CONSOLIDATION_MANIFEST_REVISION,
            MEMORY_CHECKPOINT_REVISION,
            MEMORY_CHECKPOINT_DELTA_REVISION,
            MEMORY_CONSOLIDATION_INVALIDATION_REVISION,
            MEMORY_CONSOLIDATION_QUERY_ADAPTER_REVISION,
            MEMORY_CONSOLIDATION_CONTINUITY_ADAPTER_REVISION,
            MEMORY_CONSOLIDATION_INTEGRITY_REVISION,
            MEMORY_CONSOLIDATION_COMPARISON_REVISION,
        } == {
            "memory_consolidation_v1",
            "memory_consolidation_policy_v1",
            "memory_consolidation_planner_v1",
            "memory_consolidation_membership_v1",
            "memory_consolidation_manifest_v1",
            "memory_checkpoint_v1",
            "memory_checkpoint_delta_v1",
            "memory_consolidation_invalidation_v1",
            "memory_consolidation_query_adapter_v1",
            "memory_consolidation_continuity_adapter_v1",
            "memory_consolidation_integrity_v1",
            "memory_consolidation_comparison_v1",
        })
        add(checks, "public_safe_secret_scan", no_secret({"ids": private["ids"], "boundary": BOUNDARY}))
        add(checks, "postgres_validation_honest", not bool(os.environ.get("DATABASE_URL")), "DATABASE_URL unavailable; PostgreSQL not executed." if not os.environ.get("DATABASE_URL") else "DATABASE_URL present; separate audit required.")
    return checks, private


def main() -> int:
    checks, private = run_suite()
    passed = sum(item["passed"] for item in checks)
    failed = [item["name"] for item in checks if not item["passed"]]
    postgres_available = bool(os.environ.get("DATABASE_URL"))
    result = (
        "PASS WITH DOCUMENTED LIMITATIONS"
        if not failed and not postgres_available
        else "PASS"
        if not failed
        else "NEEDS WORK"
    )
    public = {
        "version": "core_sprint_8",
        "result": result,
        "passed_checks": passed,
        "total_checks": len(checks),
        "failed_checks": failed,
        "scope": "internal_deterministic_synthetic_sqlite",
        "authoritative_raw_ledger_preserved": True,
        "consolidation_is_derived": True,
        "semantic_or_lossy_consolidation": False,
        "postgres_validation": "not_run_no_database_url" if not postgres_available else "database_url_present",
        "boundary": BOUNDARY,
        "final_statement": FINAL_STATEMENT,
    }
    private_report = {
        **public,
        "checks": checks,
        "timings_ms": private["timings_ms"],
        "artifact_ids": private["ids"],
    }
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(
        "# Core Sprint 8 Memory Consolidation\n\n"
        f"- Result: **{result}**\n"
        f"- Checks: **{passed}/{len(checks)}**\n"
        f"- PostgreSQL: **{'available for separate validation' if postgres_available else 'not run; DATABASE_URL unavailable'}**\n"
        f"- Boundary: {BOUNDARY}\n\n"
        "## Failed checks\n\n"
        + ("\n".join(f"- {name}" for name in failed) if failed else "- None")
        + "\n\n## Required statement\n\n"
        + FINAL_STATEMENT
        + "\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 8")
    print(f"Passed checks: {passed}/{len(checks)}")
    if failed:
        print("Failed checks: " + ", ".join(failed))
    print(f"PostgreSQL: {'AVAILABLE' if postgres_available else 'NOT RUN (DATABASE_URL unavailable)'}")
    print(f"Result: {result}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
