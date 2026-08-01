"""Durable Core Sprint 7 deterministic memory-query proof."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

from prmr.core.entity_identity_service import EntityIdentityService
from prmr.core.entity_memory_fixtures import entity_memory_fixtures
from prmr.core.memory_ledger_fixtures import memory_ledger_fixtures
from prmr.core.memory_ledger_service import MemoryLedgerService
from prmr.core.memory_query_engine import MemoryQueryEngine
from prmr.core.memory_query_fixtures import (
    QUERY_FIXTURE_ACTOR,
    admit_query_entity,
    admit_query_relationship,
    admit_query_source,
    insert_legacy_query_event,
    query_fixture_scope,
)
from prmr.core.memory_query_models import (
    MEMORY_CHANGE_PROJECTION_REVISION,
    MEMORY_EVIDENCE_BUNDLE_REVISION,
    MEMORY_EXPLANATION_REVISION,
    MEMORY_QUERY_INTEGRITY_REVISION,
    MEMORY_QUERY_PAGINATION_REVISION,
    MEMORY_QUERY_PLANNER_REVISION,
    MEMORY_QUERY_POLICY_REVISION,
    MEMORY_QUERY_RESULT_REVISION,
    MEMORY_QUERY_SCHEMA_REVISION,
    MEMORY_TIMELINE_REVISION,
    MemoryQueryError,
    MemoryQueryMode,
    MemoryQueryRequest,
    MemoryQueryType,
)
from prmr.core.memory_temporal_fixtures import temporal_memory_fixtures
from prmr.core.relationship_memory import RelationshipMemoryService
from prmr.core.source_models import AuthenticatedScope, SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_memory_query"
PUBLIC_REPORT = REPORT_DIR / "public_memory_query.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_query.json"
SCORECARD = REPORT_DIR / "scorecard_memory_query.md"
BOUNDARY = (
    "Internal deterministic synthetic Core Sprint 7 evidence only. This does not "
    "provide natural-language understanding, semantic retrieval, automatic truth "
    "determination, production readiness, external validation, or security certification."
)
FINAL_STATEMENT = (
    "Core Sprint 7 establishes Deterministic Memory Query, Evidence Retrieval and "
    "Historical Explanation inside PRMR Memory Core. The engine can now answer typed "
    "questions about current state, change, temporal memory phases, recurrence, "
    "re-emergence, conflicts, entities, relationships and bitemporal history while "
    "preserving epistemic status and returning exact provenance-backed evidence. "
    "Explanations describe deterministic engine selection and evidence rather than "
    "inventing semantic conclusions. Natural-language query interpretation, semantic "
    "retrieval, autonomous reasoning and memory consolidation remain later core-engine "
    "milestones."
)
FUTURE = "2099-01-01T00:00:00Z"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def expect_error(call: Callable[[], Any], code: str) -> bool:
    try:
        call()
    except MemoryQueryError as exc:
        return exc.code == code
    return False


def query(
    engine: MemoryQueryEngine,
    scope: Any,
    query_type: str,
    *,
    valid_at: str = FUTURE,
    known_at: str = FUTURE,
    timings: dict[str, list[float]] | None = None,
    **kwargs: Any,
) -> Any:
    started = time.perf_counter()
    result = engine.query_memory(
        scope,
        MemoryQueryRequest(
            query_type=query_type,
            valid_at=valid_at,
            known_at=known_at,
            **kwargs,
        ),
    )
    if timings is not None:
        timings.setdefault(query_type, []).append(
            round((time.perf_counter() - started) * 1000, 3)
        )
    return result


def table_count(repository: Any, table: str) -> int:
    with repository.connect() as connection:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def authoritative_counts(repository: Any) -> dict[str, int]:
    return {
        name: table_count(repository, name)
        for name in (
            "events",
            "prmr_sources",
            "prmr_candidate_memories",
            "prmr_memory_admission_decisions",
            "prmr_memory_evolution_records",
            "prmr_memory_conflicts",
            "prmr_memory_importance_annotations",
            "prmr_memory_dynamics_snapshots",
            "prmr_memory_reconstructions",
            "prmr_entities",
            "prmr_relationships",
            "prmr_relationship_evolution_records",
            "prmr_entity_relationship_reconstructions",
        )
    }


def no_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def iso_after(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(microseconds=1)).isoformat().replace("+00:00", "Z")


def insert_performance_events(
    repository: Any, scope: Any, count: int
) -> None:
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        {
            "event_id": f"evt_query_perf_{count}_{index:05d}",
            "user_id": "synthetic_user",
            "type": f"observation.signal_{index % 31}",
            "content": f"Synthetic local query observation {index}.",
            "timestamp": (base + timedelta(minutes=index)).isoformat().replace(
                "+00:00", "Z"
            ),
            "timestamp_index": index,
            "synthetic": True,
            "application_reference": "",
            "actor_reference": "",
            "workspace_reference": "",
            "entity_reference": "",
            "session_reference": "",
            "external_metadata": {"metadata": {"synthetic": True}},
        }
        for index in range(count)
    ]
    key = f"{scope.client_id}::{scope.vault_id}::{scope.namespace}"
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO events(scope_key,payload_json) VALUES(?,?)",
            (key, json.dumps(events, sort_keys=True)),
        )


def performance_observations() -> dict[str, Any]:
    observations: dict[str, Any] = {}
    for count in (100, 1_000, 10_000):
        with TemporaryDirectory(prefix=f"prmr-query-perf-{count}-") as temp:
            repository = SelfServeRepositoryV093(Path(temp) / "query.sqlite")
            scope = AuthenticatedScope(
                f"client_query_perf_{count}",
                f"vault_query_perf_{count}",
                "default",
            )
            insert_performance_events(repository, scope, count)
            engine = MemoryQueryEngine(repository)
            started = time.perf_counter()
            result = query(
                engine,
                scope,
                MemoryQueryType.CURRENT_STATE.value,
                valid_at="2026-01-01T00:00:00Z",
                known_at="2026-01-01T00:00:00Z",
                include_evidence=False,
                include_explanation=False,
            )
            observations[str(count)] = {
                "event_count": count,
                "current_state_duration_ms": round(
                    (time.perf_counter() - started) * 1000, 3
                ),
                "result_status": result.result_status,
                "scope": "local_synthetic_sqlite",
            }
    return observations


def run_sqlite_suite() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {"timings_ms": {}}
    with TemporaryDirectory(prefix="prmr-core-query-") as temp:
        database = Path(temp) / "memory-query.sqlite"
        repository = SelfServeRepositoryV093(database)
        alpha = query_fixture_scope("alpha")
        beta = query_fixture_scope("beta")
        temporal = temporal_memory_fixtures()
        admitted: dict[str, dict[str, Any]] = {}

        for name in (
            "natural_decay",
            "project_1",
            "project_2",
            "project_3",
            "project_4",
            "importance_normal",
            "importance_critical",
            "blocker_old",
            "blocker_returned",
        ):
            admitted[name] = admit_query_source(
                repository,
                alpha,
                temporal[name].source(),
                key_suffix=name,
            )
        admitted["baseline_latest"] = admit_query_source(
            repository,
            alpha,
            SourceInput(
                "json",
                {
                    "event_type": "milestone.completed",
                    "signal": "The synthetic project milestone completed.",
                    "occurred_at": "2026-07-08T00:00:00Z",
                },
                occurred_at="2026-07-08T00:00:00Z",
                idempotency_key="query-baseline-latest",
            ),
            key_suffix="baseline-latest",
        )

        ledger_fixtures = memory_ledger_fixtures()
        correction_original = admit_query_source(
            repository,
            alpha,
            ledger_fixtures["correction_original"].source,
            key_suffix="correction-original",
        )
        pre_correction_known = correction_original["admission"].completed_at
        correction_replacement = admit_query_source(
            repository,
            alpha,
            ledger_fixtures["correction_replacement"].source,
            key_suffix="correction-replacement",
        )
        correction = MemoryLedgerService(repository).correct_admitted_memory(
            alpha,
            correction_original["event"]["event_id"],
            correction_replacement["event"]["event_id"],
            QUERY_FIXTURE_ACTOR,
            "Synthetic replacement explicitly corrects the verified record count.",
            valid_from=correction_replacement["event"]["timestamp"],
            system_effective_at="2098-01-01T00:00:00Z",
            idempotency_key="query-correction",
        )

        fixtures = entity_memory_fixtures()
        entities: dict[str, Any] = {}
        for name in (
            "alex_person_one",
            "alex_person_two",
            "project_aurora",
            "legacy_service",
            "memory_service",
        ):
            entities[name] = admit_query_entity(
                repository, alpha, fixtures[name], key_suffix=name
            )["entity"]
        relationships: dict[str, Any] = {}
        for name in (
            "relationship_depends_legacy",
            "relationship_depends_memory",
        ):
            relationships[name] = admit_query_relationship(
                repository, alpha, fixtures[name], key_suffix=name
            )["relationship"]
        relationship_evolution = RelationshipMemoryService(
            repository
        ).supersede_relationship(
            alpha,
            relationships["relationship_depends_legacy"].relationship_id,
            relationships["relationship_depends_memory"].relationship_id,
            QUERY_FIXTURE_ACTOR,
            "Memory Service explicitly replaces the Legacy Service dependency.",
            valid_from="2025-04-01T00:00:00Z",
            system_effective_at="2098-01-02T00:00:00Z",
            idempotency_key="query-relationship-supersession",
        )
        EntityIdentityService(repository).link_event_to_entity(
            alpha,
            admitted["project_4"]["event"]["event_id"],
            entities["project_aurora"].entity_id,
            "primary_subject",
            "explicit",
            QUERY_FIXTURE_ACTOR,
            "Synthetic fixture contains an explicit project link.",
            source_id=admitted["project_4"]["source"].source_id,
            candidate_id=admitted["project_4"]["candidate"].candidate_id,
            admission_id=admitted["project_4"]["admission"].admission_id,
            link_method="explicit_event_reference",
            system_known_from="2098-01-03T00:00:00Z",
            idempotency_key="query-project-event-link",
        )
        legacy = insert_legacy_query_event(repository, alpha)

        engine = MemoryQueryEngine(repository)
        timings = private["timings_ms"]

        current = query(
            engine,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2026-07-10T00:00:00Z",
            timings=timings,
        )
        add(checks, "current_state_answered", current.result_status == "answered")
        add(
            checks,
            "current_state_exact_latest_event",
            current.answer_payload["current_state_event_id"]
            == admitted["baseline_latest"]["event"]["event_id"],
        )
        add(
            checks,
            "current_state_epistemic_preserved",
            current.answer_payload["epistemic_status"] == "explicit",
        )
        add(
            checks,
            "current_state_phase_included",
            current.answer_payload["memory_phase"]
            in {"active", "latent", "dormant", "decayed"},
        )
        current_bundle = engine.get_evidence_bundle(
            alpha, current.evidence_bundle_id or ""
        )
        current_explanation = engine.get_explanation(
            alpha, current.explanation_id or ""
        )
        add(
            checks,
            "current_state_exact_source_evidence",
            current_bundle.completeness_status == "complete"
            and admitted["baseline_latest"]["source"].source_id
            in current_bundle.source_ids,
        )
        add(
            checks,
            "current_state_structural_explanation",
            current_explanation.summary_template_id
            == "current_state_selection_v1",
        )
        integrity = engine.verify_memory_query_integrity(
            alpha, current.query_run_id
        )
        add(checks, "current_state_query_integrity", integrity.verified)

        phase_boundaries = {
            "active": "2026-01-06T00:00:00Z",
            "latent": "2026-02-01T00:00:00Z",
            "dormant": "2026-04-01T00:00:00Z",
            "decayed": "2026-06-01T00:00:00Z",
        }
        for phase, boundary in phase_boundaries.items():
            result = query(
                engine,
                alpha,
                MemoryQueryType.MEMORY_BY_PHASE.value,
                valid_at=boundary,
                memory_phase_filter=(phase,),
                timings=timings,
            )
            records = result.answer_payload["signals"]
            add(
                checks,
                f"natural_phase_{phase}",
                any(item["signal_key"] == "goal.created" for item in records),
            )

        timeline = query(
            engine,
            alpha,
            MemoryQueryType.EVENT_TIMELINE.value,
            valid_at="2026-07-10T00:00:00Z",
            include_inactive_history=True,
            maximum_results=2,
            timings=timings,
        )
        timeline_page_two = query(
            engine,
            alpha,
            MemoryQueryType.EVENT_TIMELINE.value,
            valid_at="2026-07-10T00:00:00Z",
            include_inactive_history=True,
            maximum_results=2,
            cursor=timeline.next_cursor,
        )
        first_ids = {
            item["event_id"] for item in timeline.answer_payload["events"]
        }
        second_ids = {
            item["event_id"] for item in timeline_page_two.answer_payload["events"]
        }
        add(
            checks,
            "timeline_pagination_deterministic",
            bool(timeline.next_cursor) and not (first_ids & second_ids),
        )
        add(
            checks,
            "timeline_truncation_disclosed",
            timeline.result_status == "truncated",
        )

        signal_history = query(
            engine,
            alpha,
            MemoryQueryType.SIGNAL_HISTORY.value,
            valid_at="2026-07-10T00:00:00Z",
            signal_key="status.updated",
            timings=timings,
        )
        recurrence = query(
            engine,
            alpha,
            MemoryQueryType.RECURRENCE.value,
            valid_at="2026-07-10T00:00:00Z",
            timings=timings,
        )
        reemergence = query(
            engine,
            alpha,
            MemoryQueryType.RE_EMERGENCE.value,
            valid_at="2026-07-05T00:00:00Z",
            timings=timings,
        )
        add(
            checks,
            "signal_history_exact_match",
            signal_history.answer_payload["signal_key"] == "status.updated"
            and signal_history.answer_payload["occurrence_count"] >= 4,
        )
        add(
            checks,
            "recurrence_reinforcement_returned",
            any(
                item["signal_key"] == "status.updated"
                for item in recurrence.answer_payload["signals"]
            ),
        )
        add(
            checks,
            "reemergence_gap_returned",
            any(
                item["signal_key"] == "blocker.detected"
                for item in reemergence.answer_payload["signals"]
            ),
        )

        before_correction = query(
            engine,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2025-07-03T00:00:00Z",
            known_at=pre_correction_known,
        )
        after_correction = query(
            engine,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2025-07-03T00:00:00Z",
        )
        changes = query(
            engine,
            alpha,
            MemoryQueryType.CHANGES_BETWEEN.value,
            first_temporal_boundary={
                "valid_at": "2025-07-03T00:00:00Z",
                "known_at": pre_correction_known,
            },
            second_temporal_boundary={
                "valid_at": "2025-07-03T00:00:00Z",
                "known_at": FUTURE,
            },
            timings=timings,
        )
        add(
            checks,
            "correction_before_state_1200",
            "1,200" in before_correction.answer_payload["current_state"],
        )
        add(
            checks,
            "correction_after_state_1150",
            "1,150" in after_correction.answer_payload["current_state"],
        )
        add(
            checks,
            "changes_between_correction_exact",
            correction_original["event"]["event_id"]
            in changes.answer_payload["events_became_superseded"]
            and correction.evolution_id
            in engine.get_evidence_bundle(
                alpha, changes.evidence_bundle_id or ""
            ).evolution_ids,
        )

        late_before = query(
            engine,
            alpha,
            MemoryQueryType.EVIDENCE_FOR_EVENT.value,
            valid_at="2026-07-10T00:00:00Z",
            known_at="2026-07-10T00:00:00Z",
            event_id=admitted["blocker_returned"]["event"]["event_id"],
        ) if False else None
        add(
            checks,
            "future_admission_direct_evidence_blocked",
            expect_error(
                lambda: query(
                    engine,
                    alpha,
                    MemoryQueryType.EVIDENCE_FOR_EVENT.value,
                    valid_at="2026-07-10T00:00:00Z",
                    known_at="2026-07-10T00:00:00Z",
                    event_id=admitted["blocker_returned"]["event"]["event_id"],
                ),
                "MEMORY_QUERY_TARGET_NOT_FOUND",
            ),
        )
        historical_timeline = query(
            engine,
            alpha,
            MemoryQueryType.EVENT_TIMELINE.value,
            valid_at="2026-07-10T00:00:00Z",
            known_at="2026-07-10T00:00:00Z",
            include_inactive_history=True,
        )
        add(
            checks,
            "future_admission_timeline_blocked",
            admitted["blocker_returned"]["event"]["event_id"]
            not in {
                item["event_id"]
                for item in historical_timeline.answer_payload["events"]
            },
        )

        conflict_a = admit_query_source(
            repository,
            alpha,
            SourceInput(
                "json",
                {
                    "event_type": "status.updated",
                    "signal": "The service remained online.",
                    "occurred_at": "2026-07-20T00:00:00Z",
                },
                occurred_at="2026-07-20T00:00:00Z",
                idempotency_key="query-conflict-a",
            ),
            key_suffix="conflict-a",
        )
        conflict_b = admit_query_source(
            repository,
            alpha,
            SourceInput(
                "json",
                {
                    "event_type": "status.updated",
                    "signal": "The service was unavailable for twelve minutes.",
                    "occurred_at": "2026-07-21T00:00:00Z",
                },
                occurred_at="2026-07-21T00:00:00Z",
                idempotency_key="query-conflict-b",
            ),
            key_suffix="conflict-b",
        )
        conflict = MemoryLedgerService(repository).declare_memory_contradiction(
            alpha,
            [conflict_a["event"]["event_id"], conflict_b["event"]["event_id"]],
            "status_conflict",
            QUERY_FIXTURE_ACTOR,
            "Two explicit synthetic service-state claims remain incompatible.",
            valid_from="2026-07-21T00:00:00Z",
            system_effective_at="2098-02-01T00:00:00Z",
            idempotency_key="query-conflict",
        )
        conflicted = query(
            engine,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2026-07-21T12:00:00Z",
        )
        open_conflicts = query(
            engine,
            alpha,
            MemoryQueryType.OPEN_CONFLICTS.value,
            valid_at="2026-07-21T12:00:00Z",
        )
        add(
            checks,
            "conflict_returns_both_sides_no_winner",
            conflicted.result_status == "conflicted"
            and len(conflicted.answer_payload["supported_sides"]) == 2
            and conflicted.answer_payload["winner_selected"] is False,
        )
        add(
            checks,
            "open_conflict_evidence_exact",
            conflict.conflict_id
            in [item["conflict_id"] for item in open_conflicts.answer_payload["conflicts"]]
            and set(
                engine.get_evidence_bundle(
                    alpha, conflicted.evidence_bundle_id or ""
                ).event_ids
            )
            == {
                conflict_a["event"]["event_id"],
                conflict_b["event"]["event_id"],
            },
        )

        resolution = admit_query_source(
            repository,
            alpha,
            SourceInput(
                "json",
                {
                    "event_type": "observation.recorded",
                    "signal": "Monitoring records confirm a twelve-minute outage.",
                    "occurred_at": "2026-07-22T00:00:00Z",
                },
                occurred_at="2026-07-22T00:00:00Z",
                idempotency_key="query-conflict-resolution",
            ),
            key_suffix="conflict-resolution",
        )
        MemoryLedgerService(repository).resolve_memory_contradiction(
            alpha,
            conflict.conflict_id,
            resolution["event"]["event_id"],
            QUERY_FIXTURE_ACTOR,
            "Explicit synthetic monitoring evidence resolves the contradiction.",
            system_effective_at="2098-03-01T00:00:00Z",
            idempotency_key="query-conflict-resolve",
        )
        resolved_conflicts = query(
            engine,
            alpha,
            MemoryQueryType.RESOLVED_CONFLICTS.value,
            valid_at="2026-07-22T12:00:00Z",
        )
        add(
            checks,
            "resolved_conflict_history_preserved",
            any(
                item["conflict_id"] == conflict.conflict_id
                and item["resolution_item"] == resolution["event"]["event_id"]
                for item in resolved_conflicts.answer_payload["conflicts"]
            ),
        )

        unknown_scope = query_fixture_scope("unknown")
        unknown = admit_query_source(
            repository,
            unknown_scope,
            SourceInput(
                "json",
                {
                    "event_type": "information.unknown",
                    "signal": "The cause of the corruption remains unknown.",
                    "occurred_at": "2026-01-01T00:00:00Z",
                },
                occurred_at="2026-01-01T00:00:00Z",
                idempotency_key="query-unknown",
            ),
            key_suffix="unknown",
        )
        unknown_engine = MemoryQueryEngine(repository)
        unknown_current = query(
            unknown_engine,
            unknown_scope,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2026-01-02T00:00:00Z",
        )
        unknown_list = query(
            unknown_engine,
            unknown_scope,
            MemoryQueryType.UNKNOWN_INFORMATION.value,
            valid_at="2026-01-02T00:00:00Z",
        )
        add(
            checks,
            "unknown_remains_unknown",
            unknown_current.result_status == "unknown"
            and unknown_list.result_status == "unknown"
            and unknown["event"]["event_id"]
            in [
                item["event_id"]
                for item in unknown_list.answer_payload["unknown_items"]
            ],
        )

        legacy_evidence = query(
            engine,
            alpha,
            MemoryQueryType.EVIDENCE_FOR_EVENT.value,
            valid_at="2025-01-16T00:00:00Z",
            event_id=legacy["event_id"],
        )
        add(
            checks,
            "legacy_event_partial_provenance",
            legacy_evidence.result_status == "partial"
            and legacy_evidence.answer_payload["origin_category"] == "external_event"
            and not legacy_evidence.answer_payload["source_provenance_available"],
        )

        for query_type in (
            MemoryQueryType.EVIDENCE_FOR_CURRENT_STATE.value,
            MemoryQueryType.PROVENANCE_TRACE.value,
            MemoryQueryType.STATE_AS_KNOWN_AT.value,
            MemoryQueryType.STATE_AT_VALID_TIME.value,
            MemoryQueryType.BITEMPORAL_STATE.value,
            MemoryQueryType.RECOVERABILITY_EXPLANATION.value,
            MemoryQueryType.CONTINUITY_PACKET.value,
        ):
            kwargs: dict[str, Any] = {}
            if query_type == MemoryQueryType.PROVENANCE_TRACE.value:
                kwargs["event_id"] = admitted["project_4"]["event"]["event_id"]
            result = query(
                engine,
                alpha,
                query_type,
                valid_at="2026-07-10T00:00:00Z",
                timings=timings,
                **kwargs,
            )
            add(
                checks,
                f"query_type_{query_type}_works",
                result.result_status
                in {"answered", "partial", "unknown", "conflicted"},
            )

        entity_one = query(
            engine,
            alpha,
            MemoryQueryType.ENTITY_STATE.value,
            entity_id=entities["alex_person_one"].entity_id,
            timings=timings,
        )
        entity_two = query(
            engine,
            alpha,
            MemoryQueryType.ENTITY_STATE.value,
            entity_id=entities["alex_person_two"].entity_id,
        )
        entity_history = query(
            engine,
            alpha,
            MemoryQueryType.ENTITY_HISTORY.value,
            entity_id=entities["project_aurora"].entity_id,
        )
        add(
            checks,
            "same_name_entities_remain_separate",
            entity_one.answer_payload["canonical_entity_id"]
            != entity_two.answer_payload["canonical_entity_id"],
        )
        add(
            checks,
            "entity_history_provenance_backed",
            entity_history.answer_payload["provenance_references"]
            and entity_history.answer_payload["canonical_entity_id"]
            == entities["project_aurora"].entity_id,
        )
        relationship_before = query(
            engine,
            alpha,
            MemoryQueryType.RELATIONSHIP_STATE.value,
            valid_at="2025-03-15T00:00:00Z",
            entity_id=entities["project_aurora"].entity_id,
            timings=timings,
        )
        relationship_after = query(
            engine,
            alpha,
            MemoryQueryType.RELATIONSHIP_STATE.value,
            valid_at="2025-05-01T00:00:00Z",
            entity_id=entities["project_aurora"].entity_id,
        )
        relationship_history = query(
            engine,
            alpha,
            MemoryQueryType.RELATIONSHIP_HISTORY.value,
            relationship_id=relationships[
                "relationship_depends_legacy"
            ].relationship_id,
        )
        add(
            checks,
            "relationship_state_bitemporal",
            relationships["relationship_depends_legacy"].relationship_id
            in [
                item["relationship_id"]
                for item in relationship_before.answer_payload["relationships"]
            ]
            and relationships["relationship_depends_memory"].relationship_id
            in [
                item["relationship_id"]
                for item in relationship_after.answer_payload["relationships"]
            ],
        )
        add(
            checks,
            "relationship_history_preserved",
            relationship_evolution.relationship_evolution_id
            in [
                item.get("relationship_evolution_id")
                for item in relationship_history.answer_payload["history"]
            ],
        )

        add(
            checks,
            "cross_tenant_entity_denied",
            expect_error(
                lambda: query(
                    MemoryQueryEngine(repository),
                    beta,
                    MemoryQueryType.ENTITY_STATE.value,
                    entity_id=entities["project_aurora"].entity_id,
                ),
                "MEMORY_QUERY_TARGET_NOT_FOUND",
            ),
        )
        add(
            checks,
            "cross_tenant_result_denied",
            expect_error(
                lambda: engine.get_query_result(beta, current.query_result_id),
                "MEMORY_QUERY_RESULT_NOT_FOUND",
            ),
        )
        add(
            checks,
            "scope_assertion_denied",
            expect_error(
                lambda: engine.query_memory(
                    alpha,
                    MemoryQueryRequest(
                        query_type="current_state",
                        client_id=beta.client_id,
                    ),
                ),
                "MEMORY_QUERY_SCOPE_DENIED",
            ),
        )
        add(
            checks,
            "semantic_mode_rejected",
            expect_error(
                lambda: engine.query_memory(
                    alpha,
                    MemoryQueryRequest(
                        query_type="current_state",
                        query_mode=MemoryQueryMode.SEMANTIC_ASSISTED.value,
                    ),
                ),
                "MEMORY_QUERY_SEMANTIC_MODE_UNAVAILABLE",
            ),
        )
        add(
            checks,
            "malformed_cursor_rejected",
            expect_error(
                lambda: query(
                    engine,
                    alpha,
                    MemoryQueryType.EVENT_TIMELINE.value,
                    cursor="not-a-valid-cursor",
                ),
                "MEMORY_QUERY_CURSOR_INVALID",
            ),
        )
        add(
            checks,
            "oversized_limit_rejected",
            expect_error(
                lambda: query(
                    engine,
                    alpha,
                    MemoryQueryType.EVENT_TIMELINE.value,
                    maximum_results=5_001,
                ),
                "MEMORY_QUERY_LIMIT_EXCEEDED",
            ),
        )

        replay = engine.replay_query(alpha, current.query_run_id)
        add(
            checks,
            "unchanged_query_replays",
            replay["query_run_id"] == current.query_run_id
            and replay["replayed"],
        )
        original_ids = {
            "query_run_id": current.query_run_id,
            "query_result_id": current.query_result_id,
            "result_hash": current.result_hash_sha256,
            "evidence_hash": current_bundle.evidence_manifest_hash_sha256,
            "explanation_hash": current_explanation.explanation_hash_sha256,
        }
        counts_before_queries = authoritative_counts(repository)
        query(
            engine,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2026-07-22T12:00:00Z",
        )
        counts_after_queries = authoritative_counts(repository)
        add(
            checks,
            "queries_do_not_mutate_authoritative_memory",
            counts_before_queries == counts_after_queries,
            {
                "before": counts_before_queries,
                "after": counts_after_queries,
            },
        )

        del engine
        restarted_repository = SelfServeRepositoryV093(database)
        restarted = MemoryQueryEngine(restarted_repository)
        stored = restarted.get_query_result(alpha, current.query_result_id)
        stored_bundle = restarted.get_evidence_bundle(
            alpha, current_bundle.evidence_bundle_id
        )
        stored_explanation = restarted.get_explanation(
            alpha, current_explanation.explanation_id
        )
        restarted_integrity = restarted.verify_memory_query_integrity(
            alpha, current.query_run_id
        )
        add(
            checks,
            "restart_preserves_query_artifacts",
            stored.result_hash_sha256 == original_ids["result_hash"]
            and stored_bundle.evidence_manifest_hash_sha256
            == original_ids["evidence_hash"]
            and stored_explanation.explanation_hash_sha256
            == original_ids["explanation_hash"],
        )
        add(
            checks,
            "restart_integrity_verified",
            restarted_integrity.verified,
        )
        replay_after_restart = restarted.replay_query(alpha, current.query_run_id)
        add(
            checks,
            "restart_replay_same_identity",
            replay_after_restart["query_run_id"] == current.query_run_id
            and replay_after_restart["replayed"],
        )

        new_event = admit_query_source(
            restarted_repository,
            alpha,
            SourceInput(
                "json",
                {
                    "event_type": "milestone.completed",
                    "signal": "A later synthetic milestone was completed.",
                    "occurred_at": "2026-07-09T00:00:00Z",
                },
                occurred_at="2026-07-09T00:00:00Z",
                idempotency_key="query-memory-change",
            ),
            key_suffix="memory-change",
        )
        changed = query(
            restarted,
            alpha,
            MemoryQueryType.CURRENT_STATE.value,
            valid_at="2026-07-10T00:00:00Z",
        )
        add(
            checks,
            "changed_memory_creates_new_query",
            changed.query_run_id != current.query_run_id
            and changed.query_result_id != current.query_result_id,
        )
        add(
            checks,
            "historical_result_remains_available",
            restarted.get_query_result(
                alpha, current.query_result_id
            ).result_hash_sha256
            == current.result_hash_sha256,
        )
        comparison = restarted.compare_query_results(
            alpha, current.query_result_id, changed.query_result_id
        )
        add(
            checks,
            "result_comparison_detects_change",
            comparison.result_hash_changed
            and new_event["event"]["event_id"]
            in changed.answer_payload["current_state_event_id"],
        )

        private.update(
            {
                "database_close_reopen": True,
                "original_artifact_ids": original_ids,
                "changed_query_run_id": changed.query_run_id,
                "query_run_count": table_count(
                    restarted_repository, "prmr_memory_query_runs"
                ),
                "query_result_count": table_count(
                    restarted_repository, "prmr_memory_query_results"
                ),
                "evidence_bundle_count": table_count(
                    restarted_repository, "prmr_memory_evidence_bundles"
                ),
                "explanation_count": table_count(
                    restarted_repository, "prmr_memory_explanations"
                ),
                "authoritative_counts_before_queries": counts_before_queries,
                "authoritative_counts_after_queries": counts_after_queries,
                "integrity_checks": restarted_integrity.to_dict(),
            }
        )
    return checks, private


def main() -> int:
    checks, private = run_sqlite_suite()
    performance = performance_observations()
    postgres_status = (
        "not_exercised_database_url_unavailable"
        if not os.getenv("DATABASE_URL")
        else "not_exercised_requires_isolated_test_database"
    )
    add(
        checks,
        "all_query_types_declared",
        {item.value for item in MemoryQueryType}
        == {
            "current_state",
            "memory_by_phase",
            "changes_between",
            "event_timeline",
            "signal_history",
            "recurrence",
            "re_emergence",
            "open_conflicts",
            "resolved_conflicts",
            "evidence_for_event",
            "evidence_for_current_state",
            "provenance_trace",
            "state_as_known_at",
            "state_at_valid_time",
            "bitemporal_state",
            "entity_state",
            "entity_history",
            "relationship_state",
            "relationship_history",
            "recoverability_explanation",
            "continuity_packet",
            "unknown_information",
        },
    )
    revisions = {
        "memory_query_schema_revision": MEMORY_QUERY_SCHEMA_REVISION,
        "memory_query_policy_revision": MEMORY_QUERY_POLICY_REVISION,
        "memory_query_planner_revision": MEMORY_QUERY_PLANNER_REVISION,
        "memory_query_result_revision": MEMORY_QUERY_RESULT_REVISION,
        "memory_evidence_bundle_revision": MEMORY_EVIDENCE_BUNDLE_REVISION,
        "memory_explanation_revision": MEMORY_EXPLANATION_REVISION,
        "memory_timeline_revision": MEMORY_TIMELINE_REVISION,
        "memory_change_projection_revision": MEMORY_CHANGE_PROJECTION_REVISION,
        "memory_query_integrity_revision": MEMORY_QUERY_INTEGRITY_REVISION,
        "memory_query_pagination_revision": MEMORY_QUERY_PAGINATION_REVISION,
    }
    add(checks, "revision_identifiers_exact", all(value.endswith("_v1") for value in revisions.values()))
    failed = [item for item in checks if not item["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failed else "NEEDS WORK"
    public = {
        "sprint": "Core Sprint 7",
        "result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "sqlite": "durable close/reopen query proof completed",
        "postgresql": postgres_status,
        "query_mode": "deterministic_strict_v1",
        "query_types": [item.value for item in MemoryQueryType],
        "revisions": revisions,
        "performance_observations": performance,
        "limitations": [
            "PostgreSQL was not exercised without a confirmed isolated DATABASE_URL.",
            "Performance values are local synthetic observations, not production benchmarks.",
            "Natural-language, semantic, model-assisted, and fuzzy query modes are not implemented.",
        ],
        "boundary": BOUNDARY,
        "final_statement": FINAL_STATEMENT,
    }
    private_report = {
        **public,
        "checks": checks,
        "private_execution_trace": private,
    }
    add(checks, "public_report_secret_safe", no_secret(public))
    failed = [item for item in checks if not item["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failed else "NEEDS WORK"
    public["result"] = result
    public["passed_checks"] = len(checks) - len(failed)
    public["total_checks"] = len(checks)
    public["failed_checks"] = [item["name"] for item in failed]
    private_report.update(
        {
            "result": result,
            "passed_checks": len(checks) - len(failed),
            "total_checks": len(checks),
            "failed_checks": [item["name"] for item in failed],
            "checks": checks,
        }
    )
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(
        "\n".join(
            [
                "# Core Sprint 7 Memory Query Scorecard",
                "",
                f"- Result: **{result}**",
                f"- Checks: **{len(checks) - len(failed)}/{len(checks)}**",
                "- SQLite: durable close/reopen proof completed",
                f"- PostgreSQL: {postgres_status}",
                "- Query mode: deterministic_strict_v1",
                "",
                "## Failed Checks",
                "",
                *(
                    [f"- {item['name']}: {item.get('detail')}" for item in failed]
                    or ["- None"]
                ),
                "",
                "## Boundary",
                "",
                BOUNDARY,
                "",
                "## Required Statement",
                "",
                FINAL_STATEMENT,
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 7 Memory Query")
    print(f"Result: {result}")
    print(f"Passed checks: {len(checks) - len(failed)}/{len(checks)}")
    print("SQLite: durable close/reopen proof completed")
    print(f"PostgreSQL: {postgres_status}")
    if failed:
        print("Failed:", ", ".join(item["name"] for item in failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
