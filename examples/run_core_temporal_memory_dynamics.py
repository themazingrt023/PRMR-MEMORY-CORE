"""Durable Core Sprint 5 proof for deterministic Temporal Memory Dynamics."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
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

from prmr.core.admission_models import AdmissionDecisionActor
from prmr.core.admission_service import MemoryAdmissionService
from prmr.core.candidate_engine import CandidateMemoryEngine
from prmr.core.memory_dynamics_engine import MemoryDynamicsEngine
from prmr.core.memory_ledger_models import MemoryLedgerError, MemoryTemporalBoundary
from prmr.core.memory_ledger_service import MemoryLedgerService
from prmr.core.memory_reconstruction import MemoryReconstructionService
from prmr.core.memory_temporal_fixtures import temporal_memory_fixtures
from prmr.core.memory_temporal_models import (
    CONTINUITY_TEMPORAL_ADAPTER_REVISION,
    MEMORY_DYNAMICS_SNAPSHOT_REVISION,
    MEMORY_HORIZON_REVISION,
    MEMORY_IMPORTANCE_REVISION,
    MEMORY_INFLUENCE_REVISION,
    MEMORY_RECURRENCE_REVISION,
    MEMORY_REEMERGENCE_REVISION,
    MEMORY_TEMPORAL_POLICY_REVISION,
    MEMORY_TEMPORAL_SCHEMA_REVISION,
    SIGNAL_IDENTITY_REVISION,
    MemoryDynamicsError,
    MemoryDynamicsMode,
    TemporalMemoryPolicy,
)
from prmr.core.memory_temporal_policy import (
    base_time_influence,
    classify_horizon,
    classify_phase,
    cross_horizon_boost,
    quantize8,
    recurrence_boost,
    validate_policy,
)
from prmr.core.source_ledger import SourceLedger, utc_now
from prmr.core.source_models import AuthenticatedScope, SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_temporal_memory_dynamics"
PUBLIC_REPORT = REPORT_DIR / "public_temporal_memory_dynamics.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_temporal_memory_dynamics.json"
SCORECARD = REPORT_DIR / "scorecard_temporal_memory_dynamics.md"
BOUNDARY = (
    "Internal deterministic Core Sprint 5 evidence only. Half-life, horizon, "
    "reinforcement, importance and phase values are revisioned product heuristics, "
    "not biological-memory or scientific-validation claims. Repetition does not prove truth."
)
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 5 establishes Temporal Memory Dynamics inside PRMR Memory Core. "
    "Effective admitted memory can now evolve through deterministic time-based influence, "
    "immediate-to-historical horizons, active, latent, dormant and decayed phases, "
    "recurrence reinforcement, explicit importance and genuine re-emergence after absence. "
    "Decay reduces current influence without deleting history or provenance. The bitemporal "
    "ledger remains authoritative, existing coherence and recoverability formulas remain "
    "unchanged, and the legacy five-event behaviour remains revisioned for replay "
    "compatibility. Semantic signal equivalence, entity memory, relationship memory and "
    "memory consolidation remain later core-engine milestones."
)
ACTOR = AdmissionDecisionActor("test_runner", "core-sprint-5")
KNOWN_FUTURE = "2099-01-01T00:00:00Z"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def before(value: str) -> str:
    return (parse_time(value) - timedelta(microseconds=1)).isoformat().replace(
        "+00:00", "Z"
    )


def after(value: str) -> str:
    return (parse_time(value) + timedelta(microseconds=1)).isoformat().replace(
        "+00:00", "Z"
    )


def boundary(valid_at: str, known_at: str = KNOWN_FUTURE) -> MemoryTemporalBoundary:
    return MemoryTemporalBoundary(valid_at=valid_at, known_at=known_at)


def scope(name: str, *, asserted: bool = False) -> AuthenticatedScope:
    kwargs = {}
    if asserted:
        kwargs = {
            "application_reference": f"app_{name}",
            "actor_reference": f"actor_{name}",
            "workspace_reference": f"workspace_{name}",
            "entity_reference": f"entity_{name}",
            "session_reference": f"session_{name}",
        }
    return AuthenticatedScope(f"client_{name}", f"vault_{name}", "default", **kwargs)


def admit_source(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    source_input: SourceInput,
    name: str,
) -> dict[str, Any]:
    scoped = replace(
        source_input,
        application_reference=authenticated_scope.application_reference,
        actor_reference=authenticated_scope.actor_reference,
        workspace_reference=authenticated_scope.workspace_reference,
        entity_references=(
            [authenticated_scope.entity_reference]
            if authenticated_scope.entity_reference
            else []
        ),
        session_reference=authenticated_scope.session_reference,
    )
    source = SourceLedger(repository).ingest_source(authenticated_scope, scoped).source
    candidate = CandidateMemoryEngine(repository).extract_candidates(
        authenticated_scope, source.source_id
    ).candidates[0]
    admitted = MemoryAdmissionService(repository).accept_candidate(
        authenticated_scope,
        candidate.candidate_id,
        ACTOR,
        "Admit deterministic synthetic Core Sprint 5 fixture.",
        f"admit:core-sprint-5:{name}",
    )
    return {
        "source_id": source.source_id,
        "candidate_id": candidate.candidate_id,
        "admission_id": admitted.admission.admission_id,
        "admission_completed_at": admitted.admission.completed_at,
        "event": admitted.admitted_event,
    }


def admit_fixture(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    name: str,
    *,
    suffix: str = "",
) -> dict[str, Any]:
    fixture = temporal_memory_fixtures()[name]
    canonical_signals = {
        "project_1": "project.updated",
        "project_2": "project.updated",
        "project_3": "project.updated",
        "project_4": "project.updated",
        "importance_normal": "priority.normal",
        "importance_critical": "priority.critical",
        "late_arrival": "checkpoint.recorded",
        "retraction": "claim.recorded",
        "conflict_a": "service.status",
        "conflict_b": "service.status",
        "conflict_resolution": "service.resolution",
    }
    source_input = fixture.source(idempotency_suffix=suffix)
    source_input = replace(
        source_input,
        metadata={
            **source_input.metadata,
            "canonical_signal": canonical_signals.get(name, fixture.event_type),
        },
    )
    return admit_source(
        repository,
        authenticated_scope,
        source_input,
        f"{authenticated_scope.client_id}:{name}:{suffix}",
    )


def admit_event(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    event_type: str,
    occurred_at: str,
    name: str,
) -> dict[str, Any]:
    approved_types = {
        "goal.created",
        "goal.updated",
        "decision.recorded",
        "blocker.detected",
        "blocker.resolved",
        "state.changed",
        "status.updated",
        "action.started",
        "action.completed",
        "milestone.completed",
        "observation.recorded",
        "statement.recorded",
        "information.unknown",
    }
    admitted_event_type = (
        event_type if event_type in approved_types else "observation.recorded"
    )
    return admit_source(
        repository,
        authenticated_scope,
        SourceInput(
            "json",
            {
                "event_type": admitted_event_type,
                "signal": f"Synthetic temporal fixture {name}.",
                "occurred_at": occurred_at,
                "metadata": {"synthetic": True, "fixture": name},
            },
            occurred_at=occurred_at,
            metadata={"synthetic": True, "canonical_signal": event_type},
            idempotency_key=f"temporal-memory-v1:{authenticated_scope.client_id}:{name}",
        ),
        f"{authenticated_scope.client_id}:{name}",
    )


def signal(result: Any, key: str) -> Any:
    return next(item for item in result.signals if item.signal_key == key)


def expect_error(call: Callable[[], Any], code: str) -> bool:
    try:
        call()
    except (MemoryDynamicsError, MemoryLedgerError) as exc:
        return exc.code == code
    return False


def no_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def table_count(repository: Any, table: str) -> int:
    with repository.connect() as connection:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def insert_legacy_events(
    repository: Any,
    authenticated_scope: AuthenticatedScope,
    count: int,
    *,
    signal_count: int = 17,
) -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        {
            "event_id": f"evt_temporal_perf_{count}_{index:06d}",
            "user_id": "synthetic_user",
            "type": f"observation.signal_{index % signal_count}",
            "content": f"Synthetic temporal performance event {index}.",
            "timestamp": (start + timedelta(minutes=index)).isoformat().replace(
                "+00:00", "Z"
            ),
            "timestamp_index": index,
            "synthetic": True,
            "application_reference": "",
            "actor_reference": "",
            "workspace_reference": "",
            "entity_reference": "",
            "session_reference": "",
            "external_metadata": {
                "metadata": {"synthetic": True},
                "occurred_at": (start + timedelta(minutes=index))
                .isoformat()
                .replace("+00:00", "Z"),
            },
        }
        for index in range(count)
    ]
    scope_key = MemoryAdmissionService(repository).bridge.scope_key(authenticated_scope)
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO events(scope_key,payload_json) VALUES(?,?) "
            "ON CONFLICT(scope_key) DO UPDATE SET payload_json=excluded.payload_json",
            (scope_key, json.dumps(events, sort_keys=True)),
        )


def run_sqlite_suite() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}
    policy = validate_policy(TemporalMemoryPolicy())
    with TemporaryDirectory(prefix="prmr_temporal_memory_v1_") as temp:
        db_path = Path(temp) / "temporal-memory-v1.sqlite"
        repository = SelfServeRepositoryV093(db_path)
        engine = MemoryDynamicsEngine(repository)

        add(checks, "temporal_schema_initialized", table_count(repository, "prmr_memory_temporal_schema_migrations") == 1)
        add(checks, "horizon_policy_valid", validate_policy(policy) == policy)
        horizon_cases = {
            "immediate": 0,
            "short": 86_401,
            "medium": 604_801,
            "long": 2_592_001,
            "historical": 15_552_001,
        }
        for expected, age in horizon_cases.items():
            add(
                checks,
                f"horizon_{expected}",
                classify_horizon(age, policy.horizon_policy) == expected,
            )
        add(
            checks,
            "future_age_rejected",
            expect_error(
                lambda: classify_horizon(-1, policy.horizon_policy),
                "MEMORY_EVENT_TIME_INVALID",
            ),
        )
        add(checks, "age_zero_influence", base_time_influence(0, policy.half_life_seconds) == 1.0)
        add(checks, "half_life_influence", base_time_influence(policy.half_life_seconds, policy.half_life_seconds) == 0.5)
        add(checks, "time_influence_monotonic", base_time_influence(1, policy.half_life_seconds) > base_time_influence(2, policy.half_life_seconds))
        add(checks, "influence_quantized", base_time_influence(123456, policy.half_life_seconds) == quantize8(base_time_influence(123456, policy.half_life_seconds)))
        add(checks, "recurrence_single_zero", recurrence_boost(1, policy) == 0.0)
        add(checks, "recurrence_repeated_positive", recurrence_boost(4, policy) > 0.0)
        add(checks, "recurrence_cap_respected", recurrence_boost(1_000_000, policy) <= policy.maximum_recurrence_boost)
        add(checks, "cross_horizon_positive", cross_horizon_boost(4, policy) > 0.0)

        natural_scope = scope("temporal_natural", asserted=True)
        natural = admit_fixture(repository, natural_scope, "natural_decay")
        natural_boundaries = {
            "active": "2026-01-02T00:00:00Z",
            "latent": "2026-01-31T00:00:00Z",
            "dormant": "2026-03-02T00:00:00Z",
            "decayed": "2026-05-01T00:00:00Z",
        }
        natural_results = {
            phase: engine.compute_memory_dynamics(
                natural_scope, temporal_boundary=boundary(at)
            )
            for phase, at in natural_boundaries.items()
        }
        for phase, result in natural_results.items():
            item = signal(result, "goal.created")
            add(checks, f"natural_decay_{phase}", item.memory_phase == phase, item.final_influence)
        phase_transition_ages = {
            "active_to_latent_days": -30.0 * math.log2(policy.active_threshold),
            "latent_to_dormant_days": -30.0 * math.log2(policy.latent_threshold),
            "dormant_to_decayed_days": -30.0 * math.log2(policy.dormant_threshold),
        }
        add(checks, "decay_preserves_event", MemoryAdmissionService(repository).get_admitted_event(natural_scope, natural["event"]["event_id"])["event_id"] == natural["event"]["event_id"])
        add(checks, "decay_preserves_source", SourceLedger(repository).get_source(natural_scope, natural["source_id"]).source_id == natural["source_id"])
        comparison_started = time.perf_counter()
        progression_comparison = engine.compare_dynamics_snapshots(
            natural_scope,
            natural_results["active"].snapshot.dynamics_snapshot_id,
            natural_results["decayed"].snapshot.dynamics_snapshot_id,
        )
        comparison_duration_ms = round(
            (time.perf_counter() - comparison_started) * 1000, 3
        )
        add(checks, "snapshot_comparison_tracks_decay", progression_comparison.phase_changes[0]["from"] == "active" and progression_comparison.phase_changes[0]["to"] == "decayed")

        one_scope = scope("temporal_recurrence_one")
        many_scope = scope("temporal_recurrence_many")
        admit_fixture(repository, one_scope, "project_4", suffix="one")
        for name in ("project_1", "project_2", "project_3", "project_4"):
            admit_fixture(repository, many_scope, name, suffix="many")
        final_boundary = boundary("2026-07-02T00:00:00Z")
        one_result = engine.compute_memory_dynamics(one_scope, temporal_boundary=final_boundary)
        many_result = engine.compute_memory_dynamics(many_scope, temporal_boundary=final_boundary)
        one_signal = signal(one_result, "project.updated")
        many_signal = signal(many_result, "project.updated")
        add(checks, "recurrence_occurrences_complete", many_signal.occurrence_count == 4 and len(many_signal.occurrence_event_ids) == 4)
        add(checks, "recurrence_reinforced", many_signal.reinforced and many_signal.recurrence_boost > one_signal.recurrence_boost)
        add(checks, "recurrence_influence_not_lower", many_signal.final_influence >= one_signal.final_influence)
        add(checks, "cross_horizon_reinforcement", many_signal.distinct_horizon_count >= 3 and many_signal.cross_horizon_boost > 0)
        add(checks, "recurrence_epistemic_status_preserved", set(many_signal.epistemic_status_counts) == {"explicit"})

        reem_scope = scope("temporal_reemergence")
        admit_fixture(repository, reem_scope, "blocker_old", suffix="gap")
        for index, occurred_at in enumerate(
            (
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
                "2026-04-01T00:00:00Z",
                "2026-05-01T00:00:00Z",
                "2026-06-01T00:00:00Z",
            )
        ):
            admit_event(
                repository,
                reem_scope,
                f"unrelated.signal_{index}",
                occurred_at,
                f"reemergence-gap-{index}",
            )
        admit_fixture(repository, reem_scope, "blocker_returned", suffix="gap")
        reem_result = engine.compute_memory_dynamics(
            reem_scope, temporal_boundary=final_boundary
        )
        reem_signal = signal(reem_result, "blocker.detected")
        add(checks, "genuine_reemergence_detected", reem_signal.re_emerging)
        add(checks, "reemergence_prior_and_latest_recorded", bool(reem_signal.prior_occurrence_event_id) and reem_signal.latest_occurrence_event_id in reem_signal.occurrence_event_ids)
        add(checks, "reemergence_gap_recorded", reem_signal.reemergence_gap_seconds >= policy.minimum_reemergence_gap_seconds and reem_signal.reemergence_gap_event_count >= 5)
        add(checks, "reemergence_prior_phase_nonactive", reem_signal.prior_memory_phase in {"latent", "dormant", "decayed"})
        immediate_scope = scope("temporal_immediate_repeat")
        admit_event(repository, immediate_scope, "blocker.detected", "2026-07-01T00:00:00Z", "immediate-a")
        admit_event(repository, immediate_scope, "blocker.detected", "2026-07-01T01:00:00Z", "immediate-b")
        immediate_signal = signal(
            engine.compute_memory_dynamics(immediate_scope, temporal_boundary=final_boundary),
            "blocker.detected",
        )
        add(checks, "immediate_repeat_reinforced", immediate_signal.reinforced)
        add(checks, "immediate_repeat_not_reemergence", not immediate_signal.re_emerging)

        importance_scope = scope("temporal_importance")
        normal = admit_fixture(repository, importance_scope, "importance_normal")
        critical = admit_fixture(repository, importance_scope, "importance_critical")
        annotation = engine.annotate_memory_importance(
            importance_scope,
            critical["event"]["event_id"],
            "critical",
            ACTOR,
            "Explicit synthetic critical importance for deterministic comparison.",
            idempotency_key="importance-critical-v1",
        )
        before_importance = engine.compute_memory_dynamics(
            importance_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", before(annotation.system_effective_at)
            ),
        )
        after_importance = engine.compute_memory_dynamics(
            importance_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(annotation.system_effective_at)
            ),
        )
        normal_signal = signal(after_importance, "priority.normal")
        critical_signal = signal(after_importance, "priority.critical")
        add(checks, "importance_annotation_append_only", len(engine.list_importance_annotations(importance_scope, critical["event"]["event_id"])) == 1)
        importance_replay = engine.annotate_memory_importance(
            importance_scope,
            critical["event"]["event_id"],
            "critical",
            ACTOR,
            "Explicit synthetic critical importance for deterministic comparison.",
            idempotency_key="importance-critical-v1",
        )
        add(
            checks,
            "importance_idempotent_replay",
            importance_replay.importance_annotation_id
            == annotation.importance_annotation_id
            and len(
                engine.list_importance_annotations(
                    importance_scope, critical["event"]["event_id"]
                )
            )
            == 1,
        )
        add(
            checks,
            "importance_idempotency_conflict_detected",
            expect_error(
                lambda: engine.annotate_memory_importance(
                    importance_scope,
                    critical["event"]["event_id"],
                    "low",
                    ACTOR,
                    "Different intent under the same key.",
                    idempotency_key="importance-critical-v1",
                ),
                "MEMORY_IMPORTANCE_IDEMPOTENCY_CONFLICT",
            ),
        )
        add(checks, "importance_bitemporal_before_neutral", signal(before_importance, "priority.critical").importance_weight == 1.0)
        add(checks, "importance_after_effective", critical_signal.importance_weight == 1.5 and critical_signal.importance_annotation_id == annotation.importance_annotation_id)
        add(checks, "critical_retains_higher_influence", critical_signal.final_influence > normal_signal.final_influence)
        add(checks, "importance_epistemic_unchanged", critical_signal.epistemic_status_counts == signal(before_importance, "priority.critical").epistemic_status_counts)
        add(checks, "invalid_importance_rejected", expect_error(lambda: engine.annotate_memory_importance(importance_scope, normal["event"]["event_id"], 2.1, ACTOR, "Invalid weight.", idempotency_key="invalid-weight"), "MEMORY_IMPORTANCE_INVALID"))
        field_importance_scope = scope("temporal_field_importance")
        field_importance = admit_source(
            repository,
            field_importance_scope,
            SourceInput(
                "json",
                {
                    "event_type": "observation.recorded",
                    "signal": "A synthetic event with validated explicit importance.",
                    "occurred_at": "2026-05-01T00:00:00Z",
                },
                occurred_at="2026-05-01T00:00:00Z",
                metadata={
                    "synthetic": True,
                    "canonical_signal": "priority.field_validated",
                    "importance_level": "high",
                },
                idempotency_key="temporal-memory-v1:field-importance",
            ),
            "field-importance",
        )
        field_importance_result = engine.compute_memory_dynamics(
            field_importance_scope,
            temporal_boundary=boundary("2026-07-02T00:00:00Z"),
        )
        field_importance_signal = signal(
            field_importance_result, "priority.field_validated"
        )
        add(
            checks,
            "validated_event_importance_field_applied",
            field_importance_signal.importance_weight == 1.25
            and field_importance_signal.importance_annotation_id is None
            and field_importance["event"]["external_metadata"]["metadata"][
                "importance_level"
            ]
            == "high",
        )

        late_scope = scope("temporal_late")
        late = admit_fixture(repository, late_scope, "late_arrival")
        before_late = engine.compute_memory_dynamics(
            late_scope,
            temporal_boundary=boundary(
                "2026-01-15T00:00:00Z", before(late["admission_completed_at"])
            ),
        )
        after_late = engine.compute_memory_dynamics(
            late_scope,
            temporal_boundary=boundary(
                "2026-01-15T00:00:00Z", after(late["admission_completed_at"])
            ),
        )
        add(checks, "late_arrival_absent_before_known", before_late.snapshot.resolved_event_count == 0)
        add(checks, "late_arrival_present_after_known", after_late.snapshot.resolved_event_count == 1)
        add(checks, "late_arrival_age_uses_valid_time", signal(after_late, "checkpoint.recorded").age_seconds == 14 * 86_400)

        evolution_scope = scope("temporal_evolution")
        old_status = admit_fixture(repository, evolution_scope, "supersession_old")
        new_status = admit_fixture(repository, evolution_scope, "supersession_new")
        retract_record = admit_fixture(repository, evolution_scope, "retraction")
        ledger = MemoryLedgerService(repository)
        supersession_time = utc_now()
        ledger.supersede_admitted_memory(
            evolution_scope,
            old_status["event"]["event_id"],
            new_status["event"]["event_id"],
            ACTOR,
            "Synthetic successor replaces the old state.",
            valid_from=new_status["event"]["timestamp"],
            system_effective_at=supersession_time,
            idempotency_key="temporal-supersession-v1",
        )
        before_supersession = engine.compute_memory_dynamics(
            evolution_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", before(supersession_time)
            ),
        )
        after_supersession = engine.compute_memory_dynamics(
            evolution_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(supersession_time)
            ),
        )
        add(checks, "superseded_visible_before_evolution", old_status["event"]["event_id"] in signal(before_supersession, "status.updated").occurrence_event_ids)
        add(checks, "superseded_excluded_after_evolution", old_status["event"]["event_id"] not in signal(after_supersession, "status.updated").occurrence_event_ids)
        retraction_time = utc_now()
        ledger.retract_admitted_memory(
            evolution_scope,
            retract_record["event"]["event_id"],
            ACTOR,
            "Synthetic claim is explicitly withdrawn.",
            system_effective_at=retraction_time,
            idempotency_key="temporal-retraction-v1",
        )
        before_retraction = engine.compute_memory_dynamics(
            evolution_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", before(retraction_time)
            ),
        )
        after_retraction = engine.compute_memory_dynamics(
            evolution_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(retraction_time)
            ),
        )
        add(checks, "retracted_visible_before_system_time", any(item.signal_key == "claim.recorded" for item in before_retraction.signals))
        add(checks, "retracted_excluded_after_system_time", all(item.signal_key != "claim.recorded" for item in after_retraction.signals))
        add(checks, "retraction_not_false_decay", all(item.signal_key != "claim.recorded" for item in after_retraction.signals if item.memory_phase == "decayed"))

        conflict_scope = scope("temporal_conflict")
        conflict_a = admit_fixture(repository, conflict_scope, "conflict_a")
        conflict_b = admit_fixture(repository, conflict_scope, "conflict_b")
        conflict_time = utc_now()
        conflict = ledger.declare_memory_contradiction(
            conflict_scope,
            [conflict_a["event"]["event_id"], conflict_b["event"]["event_id"]],
            "status_conflict",
            ACTOR,
            "Synthetic incompatible states remain unresolved.",
            system_effective_at=conflict_time,
            idempotency_key="temporal-conflict-v1",
        )
        open_conflict = engine.compute_memory_dynamics(
            conflict_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(conflict_time)
            ),
        )
        conflict_signal = signal(open_conflict, "service.status")
        add(checks, "open_conflict_events_both_influence", conflict_signal.occurrence_count == 2)
        add(checks, "open_conflict_marker_retained", conflict_signal.conflicted and conflict.conflict_id in conflict_signal.open_conflict_ids)
        add(checks, "recurrence_does_not_resolve_conflict", conflict_signal.reinforced and conflict_signal.conflicted)
        resolution = admit_fixture(repository, conflict_scope, "conflict_resolution")
        resolution_time = utc_now()
        ledger.resolve_memory_contradiction(
            conflict_scope,
            conflict.conflict_id,
            resolution["event"]["event_id"],
            ACTOR,
            "Synthetic explicit resolution remains authoritative.",
            system_effective_at=resolution_time,
            idempotency_key="temporal-conflict-resolution-v1",
        )
        resolved = engine.compute_memory_dynamics(
            conflict_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(resolution_time)
            ),
        )
        add(checks, "resolved_event_follows_ledger", any(item.signal_key == "service.resolution" for item in resolved.signals))
        open_replay = engine.compute_memory_dynamics(
            conflict_scope,
            temporal_boundary=boundary(
                "2026-07-02T00:00:00Z", after(conflict_time)
            ),
        )
        add(checks, "historical_conflict_snapshot_reproducible", open_replay.snapshot.dynamics_snapshot_id == open_conflict.snapshot.dynamics_snapshot_id)

        horizon_scope = scope("temporal_horizons")
        horizon_dates = (
            ("historical", "2025-12-01T00:00:00Z"),
            ("long", "2026-04-01T00:00:00Z"),
            ("medium", "2026-06-30T00:00:00Z"),
            ("short", "2026-07-18T00:00:00Z"),
            ("immediate", "2026-07-22T12:00:00Z"),
        )
        for label, occurred_at in horizon_dates:
            admit_event(repository, horizon_scope, "heartbeat.recorded", occurred_at, f"horizon-{label}")
        horizon_result = engine.compute_memory_dynamics(
            horizon_scope, temporal_boundary=boundary("2026-07-23T00:00:00Z")
        )
        horizon_signal = signal(horizon_result, "heartbeat.recorded")
        add(checks, "all_horizons_represented", set(horizon_signal.occurrences_by_horizon) == {"immediate", "short", "medium", "long", "historical"})
        add(checks, "multi_horizon_distinct_count", horizon_signal.distinct_horizon_count == 5)
        add(checks, "multi_horizon_cross_boost_capped", horizon_signal.cross_horizon_boost == policy.maximum_cross_horizon_boost)

        base_packet = MemoryReconstructionService(repository).build_continuity_packet(
            horizon_scope, temporal_boundary=boundary("2026-07-23T00:00:00Z")
        )
        legacy_packet = engine.build_continuity_packet(
            horizon_scope,
            temporal_boundary=boundary("2026-07-23T00:00:00Z"),
            dynamics_mode=MemoryDynamicsMode.LEGACY_RECENT5_V1.value,
        )
        packet_started = time.perf_counter()
        temporal_packet = engine.build_continuity_packet(
            horizon_scope,
            temporal_boundary=boundary("2026-07-23T00:00:00Z"),
        )
        packet_duration_ms = round((time.perf_counter() - packet_started) * 1000, 3)
        add(checks, "legacy_recent5_packet_reproducible", legacy_packet["packet_id"] == base_packet["packet_id"] and legacy_packet["active_information"] == base_packet["active_information"])
        add(checks, "temporal_packet_fields_present", all(key in temporal_packet for key in ("dormant_information", "decayed_signals", "reinforced_signals", "re_emergence_signals", "memory_dynamics_context")))
        add(checks, "current_state_freshness_present", all(key in temporal_packet for key in ("current_state_event_id", "current_state_signal", "current_state_age_seconds", "current_state_horizon", "current_state_memory_phase", "current_state_influence", "current_state_time_basis")))
        add(checks, "coherence_formula_unchanged", temporal_packet["coherence_score"] == base_packet["coherence_score"])
        add(checks, "recoverability_formula_unchanged", temporal_packet["recoverability_score"] == base_packet["recoverability_score"])
        temporal_packet_replay = engine.build_continuity_packet(
            horizon_scope,
            temporal_boundary=boundary("2026-07-23T00:00:00Z"),
        )
        add(checks, "temporal_packet_id_deterministic", temporal_packet_replay["packet_id"] == temporal_packet["packet_id"] and temporal_packet_replay["provenance"]["deterministic_packet_hash"] == temporal_packet["provenance"]["deterministic_packet_hash"])
        add(checks, "temporal_packet_provenance_safe", no_secret(temporal_packet) and temporal_packet["provenance"]["source_text_exposed"] is False)

        beta_scope = scope("temporal_beta", asserted=True)
        beta = admit_event(repository, beta_scope, "beta.signal", "2026-07-22T00:00:00Z", "beta")
        beta_result = engine.compute_memory_dynamics(
            beta_scope, temporal_boundary=boundary("2026-07-23T00:00:00Z")
        )
        add(checks, "alpha_cannot_read_beta_snapshot", expect_error(lambda: engine.get_dynamics_snapshot(natural_scope, beta_result.snapshot.dynamics_snapshot_id), "MEMORY_DYNAMICS_SNAPSHOT_NOT_FOUND"))
        add(checks, "alpha_cannot_list_beta_signals", expect_error(lambda: engine.list_signal_dynamics(natural_scope, beta_result.snapshot.dynamics_snapshot_id), "MEMORY_DYNAMICS_SNAPSHOT_NOT_FOUND"))
        add(checks, "alpha_cannot_annotate_beta_event", expect_error(lambda: engine.annotate_memory_importance(natural_scope, beta["event"]["event_id"], "high", ACTOR, "Wrong-scope test.", idempotency_key="wrong-scope"), "MEMORY_IMPORTANCE_SCOPE_DENIED"))
        wrong_assertion_scope = replace(natural_scope, actor_reference="actor_wrong")
        wrong_assertion = engine.compute_memory_dynamics(
            wrong_assertion_scope,
            temporal_boundary=boundary("2026-07-23T00:00:00Z"),
        )
        add(checks, "wrong_actor_assertion_yields_no_memory", wrong_assertion.snapshot.resolved_event_count == 0)
        add(checks, "scope_signal_counts_do_not_leak", beta_result.snapshot.signal_count == 1 and natural_results["decayed"].snapshot.signal_count == 1)

        linked_snapshot = engine.get_dynamics_snapshot(
            horizon_scope, horizon_result.snapshot.dynamics_snapshot_id
        )
        integrity_started = time.perf_counter()
        integrity = engine.verify_memory_dynamics_integrity(
            horizon_scope, linked_snapshot.dynamics_snapshot_id
        )
        integrity_duration_ms = round(
            (time.perf_counter() - integrity_started) * 1000, 3
        )
        add(checks, "dynamics_integrity_verified", integrity.verified, integrity.failures)

        deterministic_scope = scope("temporal_deterministic")
        deterministic_events = [
            {
                "event_id": "evt_temporal_deterministic_0001",
                "user_id": "synthetic_user",
                "type": "deterministic.signal",
                "content": "Synthetic deterministic event.",
                "timestamp": "2026-07-01T00:00:00Z",
                "timestamp_index": 1,
                "synthetic": True,
                "application_reference": "",
                "actor_reference": "",
                "workspace_reference": "",
                "entity_reference": "",
                "session_reference": "",
                "external_metadata": {
                    "metadata": {"synthetic": True},
                    "occurred_at": "2026-07-01T00:00:00Z",
                },
            }
        ]
        scope_key = MemoryAdmissionService(repository).bridge.scope_key(deterministic_scope)
        with repository.connect() as connection:
            connection.execute(
                "INSERT INTO events(scope_key,payload_json) VALUES(?,?)",
                (scope_key, json.dumps(deterministic_events, sort_keys=True)),
            )
        deterministic_boundary = boundary("2026-07-02T00:00:00Z")
        first_deterministic = engine.compute_memory_dynamics(
            deterministic_scope, temporal_boundary=deterministic_boundary
        )
        second_deterministic = engine.compute_memory_dynamics(
            deterministic_scope, temporal_boundary=deterministic_boundary
        )
        add(checks, "snapshot_id_deterministic", first_deterministic.snapshot.dynamics_snapshot_id == second_deterministic.snapshot.dynamics_snapshot_id)
        add(checks, "snapshot_manifest_deterministic", first_deterministic.snapshot.signal_dynamics_manifest_hash == second_deterministic.snapshot.signal_dynamics_manifest_hash)
        add(checks, "signal_id_deterministic", first_deterministic.signals[0].signal_dynamics_id == second_deterministic.signals[0].signal_dynamics_id)
        add(checks, "same_policy_replays_snapshot", second_deterministic.replayed and not second_deterministic.created)

        snapshot_id_before_restart = linked_snapshot.dynamics_snapshot_id
        packet_id_before_restart = temporal_packet["packet_id"]
        del engine
        del repository
        reopened = SelfServeRepositoryV093(db_path)
        reopened_engine = MemoryDynamicsEngine(reopened)
        reopened_snapshot = reopened_engine.get_dynamics_snapshot(
            horizon_scope, snapshot_id_before_restart
        )
        reopened_integrity = reopened_engine.verify_memory_dynamics_integrity(
            horizon_scope, snapshot_id_before_restart
        )
        reopened_packet = reopened_engine.build_continuity_packet(
            horizon_scope,
            temporal_boundary=boundary("2026-07-23T00:00:00Z"),
        )
        add(checks, "restart_preserves_snapshot", reopened_snapshot.dynamics_snapshot_id == snapshot_id_before_restart)
        add(checks, "restart_integrity_reproduces", reopened_integrity.verified)
        add(checks, "restart_packet_reproduces", reopened_packet["packet_id"] == packet_id_before_restart)
        add(checks, "restart_annotation_preserved", len(reopened_engine.list_importance_annotations(importance_scope, critical["event"]["event_id"])) == 1)

        independent_db = Path(temp) / "temporal-independent.sqlite"
        independent_repo = SelfServeRepositoryV093(independent_db)
        independent_scope = deterministic_scope
        independent_scope_key = MemoryAdmissionService(independent_repo).bridge.scope_key(independent_scope)
        with independent_repo.connect() as connection:
            connection.execute(
                "INSERT INTO events(scope_key,payload_json) VALUES(?,?)",
                (independent_scope_key, json.dumps(deterministic_events, sort_keys=True)),
            )
        independent_engine = MemoryDynamicsEngine(independent_repo)
        independent_result = independent_engine.compute_memory_dynamics(
            independent_scope, temporal_boundary=deterministic_boundary
        )
        add(checks, "independent_identical_history_same_snapshot", independent_result.snapshot.dynamics_snapshot_id == first_deterministic.snapshot.dynamics_snapshot_id)
        independent_packet = independent_engine.build_continuity_packet(
            independent_scope, temporal_boundary=deterministic_boundary
        )
        deterministic_packet = reopened_engine.build_continuity_packet(
            deterministic_scope, temporal_boundary=deterministic_boundary
        )
        add(checks, "independent_identical_history_same_packet", independent_packet["packet_id"] == deterministic_packet["packet_id"])

        performance: dict[str, Any] = {}
        for count in (100, 1_000, 10_000):
            perf_scope = scope(f"temporal_perf_{count}")
            insert_legacy_events(reopened, perf_scope, count)
            started = time.perf_counter()
            perf_result = reopened_engine.compute_memory_dynamics(
                perf_scope,
                temporal_boundary=boundary("2026-01-01T00:00:00Z"),
                persist=False,
            )
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            performance[str(count)] = {
                "duration_ms": duration_ms,
                "signal_count": perf_result.snapshot.signal_count,
                "occurrence_count": perf_result.snapshot.resolved_event_count,
                "resolver_duration_ms": perf_result.resolver_duration_ms,
                "recurrence_duration_ms": perf_result.recurrence_duration_ms,
                "reemergence_duration_ms": perf_result.reemergence_duration_ms,
            }
            add(checks, f"performance_{count}_events_completed", perf_result.snapshot.resolved_event_count == count, duration_ms)

        database_size = db_path.stat().st_size
        evidence = {
            "database_path_kind": "temporary durable SQLite file",
            "database_size_bytes": database_size,
            "natural_decay": {
                phase: {
                    "snapshot_id": result.snapshot.dynamics_snapshot_id,
                    "influence": signal(result, "goal.created").final_influence,
                    "phase": signal(result, "goal.created").memory_phase,
                }
                for phase, result in natural_results.items()
            },
            "calculated_phase_transition_ages": phase_transition_ages,
            "reinforcement": {
                "single_occurrence_influence": one_signal.final_influence,
                "four_occurrence_influence": many_signal.final_influence,
                "recurrence_boost": many_signal.recurrence_boost,
                "cross_horizon_boost": many_signal.cross_horizon_boost,
                "truth_inference": "none",
            },
            "reemergence": {
                "detected": reem_signal.re_emerging,
                "gap_seconds": reem_signal.reemergence_gap_seconds,
                "gap_event_count": reem_signal.reemergence_gap_event_count,
                "prior_phase": reem_signal.prior_memory_phase,
            },
            "importance": {
                "annotation_id": annotation.importance_annotation_id,
                "normal_influence": normal_signal.final_influence,
                "critical_influence": critical_signal.final_influence,
            },
            "packet": {
                "packet_id": temporal_packet["packet_id"],
                "snapshot_id": linked_snapshot.dynamics_snapshot_id,
                "coherence_score": temporal_packet["coherence_score"],
                "recoverability_score": temporal_packet["recoverability_score"],
            },
            "integrity": integrity.checks,
            "operation_timings_ms": {
                "snapshot_comparison": comparison_duration_ms,
                "temporal_packet_generation": packet_duration_ms,
                "integrity_verification": integrity_duration_ms,
                "snapshot_persistence": horizon_result.persistence_duration_ms,
                "memory_state_resolver": horizon_result.resolver_duration_ms,
                "recurrence_grouping": horizon_result.recurrence_duration_ms,
                "reemergence_detection": horizon_result.reemergence_duration_ms,
            },
            "restart": {
                "snapshot_preserved": reopened_snapshot.dynamics_snapshot_id == snapshot_id_before_restart,
                "packet_preserved": reopened_packet["packet_id"] == packet_id_before_restart,
            },
            "performance_local_observations": performance,
            "performance_100000": "not run; bounded local suite stops at 10,000 events",
        }
    return checks, evidence


def write_reports(
    checks: list[dict[str, Any]], evidence: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str]:
    failed = [item["name"] for item in checks if not item["passed"]]
    postgres_available = bool(os.environ.get("DATABASE_URL", "").strip())
    status = (
        "NEEDS WORK"
        if failed
        else ("PASS" if postgres_available else "PASS WITH DOCUMENTED LIMITATIONS")
    )
    public = {
        "version": "Core Sprint 5",
        "result": status,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "sqlite": "exercised with durable close/reopen proof",
        "postgresql": (
            "DATABASE_URL detected; independent audit must record exercised result"
            if postgres_available
            else "not exercised because DATABASE_URL is unavailable"
        ),
        "capabilities_proven": [
            "bitemporally resolved temporal horizons",
            "deterministic half-life influence",
            "active latent dormant and decayed phases without deletion",
            "recurrence and cross-horizon reinforcement without truth inference",
            "explicit bitemporal importance",
            "genuine re-emergence after absence",
            "durable temporal snapshots and packet identities",
            "legacy recent-five replay compatibility",
        ],
        "boundary": BOUNDARY,
        "required_final_statement": REQUIRED_FINAL_STATEMENT,
    }
    private = {
        **public,
        "checks": checks,
        "evidence": evidence,
        "revisions": {
            "memory_temporal_schema_revision": MEMORY_TEMPORAL_SCHEMA_REVISION,
            "memory_temporal_policy_revision": MEMORY_TEMPORAL_POLICY_REVISION,
            "memory_horizon_revision": MEMORY_HORIZON_REVISION,
            "memory_influence_revision": MEMORY_INFLUENCE_REVISION,
            "memory_recurrence_revision": MEMORY_RECURRENCE_REVISION,
            "memory_reemergence_revision": MEMORY_REEMERGENCE_REVISION,
            "memory_importance_revision": MEMORY_IMPORTANCE_REVISION,
            "memory_dynamics_snapshot_revision": MEMORY_DYNAMICS_SNAPSHOT_REVISION,
            "continuity_temporal_adapter_revision": CONTINUITY_TEMPORAL_ADAPTER_REVISION,
            "signal_identity_revision": SIGNAL_IDENTITY_REVISION,
        },
        "limitations": [
            "PostgreSQL is not exercised when DATABASE_URL is absent.",
            "Signal identity is validated canonical_signal or structural event type; semantic equivalence is not implemented.",
            "Temporal constants are versioned product heuristics, not scientific constants.",
            "The bounded local performance observation stops at 10,000 events.",
        ],
    }
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    scorecard = "\n".join(
        [
            "# Core Sprint 5 - Temporal Memory Dynamics",
            "",
            f"**Result:** {status}",
            f"**Checks:** {public['passed_checks']}/{public['total_checks']}",
            "",
            "## Evidence",
            "",
            "- Durable SQLite source -> candidate -> admission -> bitemporal resolver -> dynamics proof.",
            "- Fixed-boundary active -> latent -> dormant -> decayed progression.",
            "- Recurrence, cross-horizon reinforcement, explicit importance, and re-emergence.",
            "- Supersession, retraction, open conflict, historical replay, isolation, integrity, and restart.",
            "- Legacy recent-five coherence and recoverability remain unchanged.",
            "",
            "## Limitation",
            "",
            public["postgresql"] + ".",
            "",
            "## Boundary",
            "",
            BOUNDARY,
            "",
            "## Required Final Statement",
            "",
            REQUIRED_FINAL_STATEMENT,
            "",
        ]
    )
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(scorecard, encoding="utf-8")
    return public, private, status


def main() -> int:
    checks, evidence = run_sqlite_suite()
    public, private, status = write_reports(checks, evidence)
    add(
        checks,
        "public_report_secret_safe",
        no_secret(public),
    )
    add(
        checks,
        "private_report_secret_safe",
        no_secret(private),
    )
    public, _, status = write_reports(checks, evidence)
    print("PRMR Memory Core - Core Sprint 5 Temporal Memory Dynamics")
    print(f"Result: {status}")
    print(f"Passed checks: {public['passed_checks']}/{public['total_checks']}")
    print(f"SQLite: durable close/reopen proof completed")
    print(f"PostgreSQL: {public['postgresql']}")
    if public["failed_checks"]:
        print("Failed: " + ", ".join(public["failed_checks"]))
    return 0 if not public["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
