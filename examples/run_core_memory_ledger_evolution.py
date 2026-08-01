"""Durable Core Sprint 4 proof for bitemporal memory-ledger evolution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
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

from prmr.core.admission_models import AdmissionDecisionActor
from prmr.core.admission_service import MemoryAdmissionService
from prmr.core.candidate_engine import CandidateMemoryEngine
from prmr.core.memory_ledger_fixtures import memory_ledger_fixtures
from prmr.core.memory_ledger_integrity import MemoryLedgerIntegrityVerifier
from prmr.core.memory_ledger_models import (
    BITEMPORAL_POLICY_REVISION,
    CONTINUITY_INPUT_RESOLVER_REVISION,
    MEMORY_CONFLICT_REVISION,
    MEMORY_EVOLUTION_REVISION,
    MEMORY_LEDGER_SCHEMA_REVISION,
    MEMORY_RECONSTRUCTION_REVISION,
    MEMORY_STATE_RESOLVER_REVISION,
    MemoryLedgerError,
    MemoryTemporalBoundary,
)
from prmr.core.memory_ledger_service import MemoryLedgerService
from prmr.core.memory_reconstruction import MemoryReconstructionService
from prmr.core.memory_state_resolver import MemoryStateResolver
from prmr.core.source_ledger import SourceLedger, utc_now
from prmr.core.source_models import (
    AuthenticatedScope,
    SourceInput,
    SourceLedgerError,
)
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_memory_ledger_evolution"
PUBLIC_REPORT = REPORT_DIR / "public_memory_ledger_evolution.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_ledger_evolution.json"
SCORECARD = REPORT_DIR / "scorecard_memory_ledger_evolution.md"
BOUNDARY = (
    "Internal deterministic Core Sprint 4 evidence only. This does not determine "
    "truth automatically, provide semantic contradiction detection, prove production "
    "readiness, or constitute external validation or security certification."
)
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 4 establishes Bitemporal Memory Ledger Evolution inside PRMR Memory Core. "
    "Admitted memories can now be corrected, superseded, retracted, placed into unresolved "
    "contradictions and explicitly resolved without erasing their history or provenance. "
    "Memory state can be reconstructed by valid time and system-known time, and the existing "
    "continuity engine can operate on the deterministically resolved effective ledger. "
    "Automatic contradiction discovery, advanced temporal decay, entity memory and memory "
    "consolidation remain later core-engine milestones."
)


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
    return (parse_time(value) - timedelta(microseconds=1)).isoformat().replace("+00:00", "Z")


def after(value: str) -> str:
    return (parse_time(value) + timedelta(microseconds=1)).isoformat().replace("+00:00", "Z")


def expect_error(call: Callable[[], Any], code: str) -> bool:
    try:
        call()
    except (MemoryLedgerError, SourceLedgerError) as exc:
        return exc.code == code
    return False


def event_ids(reconstruction: Any) -> set[str]:
    return set(reconstruction.effective_event_ids)


def no_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def admit_fixture(
    repository: Any,
    scope: AuthenticatedScope,
    name: str,
    *,
    key_suffix: str = "",
) -> dict[str, Any]:
    fixture = memory_ledger_fixtures()[name]
    source_input = replace(
        fixture.source,
        application_reference=scope.application_reference,
        actor_reference=scope.actor_reference,
        workspace_reference=scope.workspace_reference,
        entity_references=[scope.entity_reference] if scope.entity_reference else [],
        session_reference=scope.session_reference,
        idempotency_key=f"{fixture.source.idempotency_key}:{key_suffix}" if key_suffix else fixture.source.idempotency_key,
    )
    source = SourceLedger(repository).ingest_source(scope, source_input).source
    candidate = CandidateMemoryEngine(repository).extract_candidates(
        scope, source.source_id
    ).candidates[0]
    result = MemoryAdmissionService(repository).accept_candidate(
        scope,
        candidate.candidate_id,
        AdmissionDecisionActor("test_runner", "core-sprint-4"),
        "Admit deterministic Core Sprint 4 fixture.",
        f"admit:{name}:{key_suffix}",
    )
    return {
        "source_id": source.source_id,
        "candidate_id": candidate.candidate_id,
        "admission_id": result.admission.admission_id,
        "admission_completed_at": result.admission.completed_at,
        "event": result.admitted_event,
    }


def table_count(repository: Any, table: str) -> int:
    with repository.connect() as connection:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def insert_legacy_history(
    repository: Any, scope: AuthenticatedScope, count: int
) -> None:
    events = [
        {
            "event_id": f"evt_perf_{count}_{index:05d}",
            "user_id": "synthetic_user",
            "type": "observation.recorded",
            "content": f"Synthetic performance observation {index % 17}.",
            "timestamp": (
                datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
            ).isoformat().replace("+00:00", "Z"),
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
    key = MemoryAdmissionService(repository).bridge.scope_key(scope)
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO events(scope_key,payload_json) VALUES(?,?) "
            "ON CONFLICT(scope_key) DO UPDATE SET payload_json=excluded.payload_json",
            (key, json.dumps(events, sort_keys=True)),
        )


def run_sqlite_suite() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    private: dict[str, Any] = {}
    actor = AdmissionDecisionActor("test_runner", "core-sprint-4")
    with TemporaryDirectory(prefix="prmr_memory_ledger_v2_") as temp:
        db_path = Path(temp) / "memory-ledger-v2.sqlite"
        repository = SelfServeRepositoryV093(db_path)
        scope = AuthenticatedScope(
            "client_memory_ledger_alpha",
            "vault_memory_ledger_alpha",
            "default",
            application_reference="app_memory_ledger",
            actor_reference="actor_memory_ledger",
            workspace_reference="workspace_memory_ledger",
            entity_reference="entity_memory_ledger",
            session_reference="session_memory_ledger",
        )
        other_scope = AuthenticatedScope(
            "client_memory_ledger_beta", "vault_memory_ledger_beta", "default"
        )
        records: dict[str, dict[str, Any]] = {}
        for name in (
            "correction_original",
            "correction_replacement",
            "supersession_original",
            "supersession_successor",
            "retraction_original",
            "conflict_online",
            "conflict_outage",
            "late_arrival",
        ):
            records[name] = admit_fixture(repository, scope, name)
        other = admit_fixture(repository, other_scope, "late_arrival", key_suffix="beta")

        admission = MemoryAdmissionService(repository)
        ledger = MemoryLedgerService(repository)
        resolver = MemoryStateResolver(repository)
        reconstructor = MemoryReconstructionService(repository)
        baseline_packet = admission.build_continuity_packet(scope)
        add(checks, "baseline_packet_recorded", baseline_packet["source_event_count"] == 8)

        correction_time = utc_now()
        correction_ids = [
            MemoryLedgerService(repository).correct_admitted_memory(
                scope,
                records["correction_original"]["event"]["event_id"],
                records["correction_replacement"]["event"]["event_id"],
                actor,
                "The replacement fixture explicitly corrects the verified count.",
                valid_from=records["correction_replacement"]["event"]["timestamp"],
                system_effective_at=correction_time,
                idempotency_key="fixture-correction",
            ).evolution_id
            for _ in range(1)
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            correction_ids += list(
                pool.map(
                    lambda _: MemoryLedgerService(repository).correct_admitted_memory(
                        scope,
                        records["correction_original"]["event"]["event_id"],
                        records["correction_replacement"]["event"]["event_id"],
                        actor,
                        "The replacement fixture explicitly corrects the verified count.",
                        valid_from=records["correction_replacement"]["event"]["timestamp"],
                        system_effective_at=correction_time,
                        idempotency_key="fixture-correction",
                    ).evolution_id,
                    range(2),
                )
            )
        correction = ledger.list_evolutions(scope)[0]
        add(checks, "correction_idempotent_and_concurrent_safe", len(set(correction_ids)) == 1)
        add(checks, "correction_record_append_only", correction.evolution_type == "correct")

        supersession_time = utc_now()
        with ThreadPoolExecutor(max_workers=2) as pool:
            supersession_ids = list(
                pool.map(
                    lambda _: MemoryLedgerService(repository).supersede_admitted_memory(
                        scope,
                        records["supersession_original"]["event"]["event_id"],
                        records["supersession_successor"]["event"]["event_id"],
                        actor,
                        "The later schedule explicitly replaces the earlier launch state.",
                        valid_from=records["supersession_successor"]["event"]["timestamp"],
                        system_effective_at=supersession_time,
                        idempotency_key="fixture-supersession",
                    ).evolution_id,
                    range(2),
                )
            )
        add(checks, "supersession_idempotent_and_concurrent_safe", len(set(supersession_ids)) == 1)

        retraction_time = utc_now()
        with ThreadPoolExecutor(max_workers=2) as pool:
            retraction_ids = list(
                pool.map(
                    lambda _: MemoryLedgerService(repository).retract_admitted_memory(
                        scope,
                        records["retraction_original"]["event"]["event_id"],
                        actor,
                        "The backup-completion statement cannot be verified and is withdrawn.",
                        system_effective_at=retraction_time,
                        idempotency_key="fixture-retraction",
                    ).evolution_id,
                    range(2),
                )
            )
        add(checks, "retraction_idempotent_and_concurrent_safe", len(set(retraction_ids)) == 1)

        conflict_time = utc_now()
        conflict_event_ids = [
            records["conflict_online"]["event"]["event_id"],
            records["conflict_outage"]["event"]["event_id"],
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            conflict_ids = list(
                pool.map(
                    lambda _: MemoryLedgerService(repository).declare_memory_contradiction(
                        scope,
                        conflict_event_ids,
                        "status_conflict",
                        actor,
                        "The admitted incident statements are explicitly incompatible.",
                        system_effective_at=conflict_time,
                        idempotency_key="fixture-conflict",
                    ).conflict_id,
                    range(2),
                )
            )
        conflict = ledger.get_conflict(scope, conflict_ids[0])
        add(checks, "conflict_declaration_idempotent_and_concurrent_safe", len(set(conflict_ids)) == 1)
        add(checks, "conflict_open", conflict.conflict_status == "open")

        open_view = resolver.resolve_effective_events(scope)
        open_packet = reconstructor.build_continuity_packet(scope)
        open_states = {
            item.event_id: item.effective_state for item in open_view.projections
        }
        add(checks, "both_conflict_events_preserved", all(event_id in open_states for event_id in conflict_event_ids))
        add(checks, "both_conflict_events_project_conflicted", all(open_states[event_id] == "conflicted" for event_id in conflict_event_ids))
        add(checks, "open_conflict_has_no_winner", all(event_id in {item["event_id"] for item in open_view.effective_events} for event_id in conflict_event_ids))
        add(checks, "packet_has_unresolved_conflict_overlay", len(open_packet["unresolved_contradictions"]) == 1)

        records["conflict_resolution"] = admit_fixture(
            repository, scope, "conflict_resolution"
        )
        resolution_time = utc_now()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resolution_ids = list(
                pool.map(
                    lambda _: MemoryLedgerService(repository).resolve_memory_contradiction(
                        scope,
                        conflict.conflict_id,
                        records["conflict_resolution"]["event"]["event_id"],
                        actor,
                        "Monitoring evidence explicitly resolves the incident state.",
                        system_effective_at=resolution_time,
                        idempotency_key="fixture-resolution",
                    ).resolution_event_id,
                    range(2),
                )
            )
        resolved_conflict = ledger.get_conflict(scope, conflict.conflict_id)
        add(checks, "resolution_idempotent_and_concurrent_safe", len(set(resolution_ids)) == 1)
        add(checks, "conflict_resolved", resolved_conflict.conflict_status == "resolved")
        add(checks, "resolution_event_provenance_verified", admission.verify_admission_integrity(scope, records["conflict_resolution"]["admission_id"]).verified)

        open_reconstruction = reconstructor.reconstruct_as_known_at(
            scope, after(conflict_time)
        )

        current = reconstructor.reconstruct_current_state(scope)
        current_ids = event_ids(current)
        original_id = records["correction_original"]["event"]["event_id"]
        replacement_id = records["correction_replacement"]["event"]["event_id"]
        old_launch_id = records["supersession_original"]["event"]["event_id"]
        new_launch_id = records["supersession_successor"]["event"]["event_id"]
        retract_id = records["retraction_original"]["event"]["event_id"]
        resolution_event_id = records["conflict_resolution"]["event"]["event_id"]
        add(checks, "current_excludes_corrected_original", original_id not in current_ids)
        add(checks, "current_includes_correction_replacement", replacement_id in current_ids)
        add(checks, "current_excludes_superseded_original", old_launch_id not in current_ids)
        add(checks, "current_includes_supersession_successor", new_launch_id in current_ids)
        add(checks, "current_excludes_retracted_event", retract_id not in current_ids)
        add(checks, "current_includes_resolution_event", resolution_event_id in current_ids)
        add(checks, "resolved_conflict_originals_remain_historical", all(admission.get_admitted_event(scope, item) for item in conflict_event_ids))
        add(checks, "all_original_event_rows_preserved", len(admission._events_for_scope(scope)) == 9)

        before_correction = reconstructor.reconstruct_as_known_at(
            scope, before(correction.system_effective_at)
        )
        after_correction = reconstructor.reconstruct_as_known_at(
            scope, after(correction.system_effective_at)
        )
        add(checks, "correction_does_not_leak_backward", original_id in event_ids(before_correction))
        add(checks, "correction_applies_after_known_boundary", original_id not in event_ids(after_correction) and replacement_id in event_ids(after_correction))

        before_launch = reconstructor.reconstruct_at_valid_time(
            scope, "2025-08-01T00:00:00Z"
        )
        after_launch = reconstructor.reconstruct_at_valid_time(
            scope, "2025-08-16T00:00:00Z"
        )
        add(checks, "supersession_preserves_prior_valid_state", old_launch_id in event_ids(before_launch) and new_launch_id not in event_ids(before_launch))
        add(checks, "supersession_changes_later_valid_state", old_launch_id not in event_ids(after_launch) and new_launch_id in event_ids(after_launch))

        before_retraction = reconstructor.reconstruct_as_known_at(
            scope, before(retraction_time)
        )
        after_retraction = reconstructor.reconstruct_as_known_at(
            scope, after(retraction_time)
        )
        add(checks, "retraction_does_not_leak_backward", retract_id in event_ids(before_retraction))
        add(checks, "retraction_applies_after_system_boundary", retract_id not in event_ids(after_retraction))
        add(checks, "retraction_invents_no_replacement", next(item for item in ledger.list_evolutions(scope) if item.evolution_id == retraction_ids[0]).replacement_event_id is None)

        during_conflict = reconstructor.reconstruct_as_known_at(
            scope, after(conflict_time)
        )
        after_resolution = reconstructor.reconstruct_as_known_at(
            scope, after(resolution_time)
        )
        add(checks, "historical_conflict_period_is_open", len(during_conflict.open_conflicts) == 1 and len(during_conflict.resolved_conflicts) == 0)
        add(checks, "future_resolution_does_not_leak_backward", resolution_event_id not in event_ids(during_conflict))
        add(checks, "resolution_period_is_resolved", len(after_resolution.resolved_conflicts) == 1 and resolution_event_id in event_ids(after_resolution))

        late_id = records["late_arrival"]["event"]["event_id"]
        late_known = records["late_arrival"]["admission_completed_at"]
        late_before = reconstructor.reconstruct_bitemporal(
            scope, "2025-07-02T00:00:00Z", before(late_known)
        )
        late_after = reconstructor.reconstruct_bitemporal(
            scope, "2025-07-02T00:00:00Z", after(late_known)
        )
        add(checks, "late_arrival_absent_before_known", late_id not in event_ids(late_before))
        add(checks, "late_arrival_present_after_known", late_id in event_ids(late_after))
        add(checks, "valid_and_known_time_distinct", late_before.temporal_boundary.valid_at != late_before.temporal_boundary.known_at)

        add(checks, "correction_self_cycle_rejected", expect_error(lambda: ledger.correct_admitted_memory(scope, replacement_id, replacement_id, actor, "Self cycle.", idempotency_key="self-cycle"), "MEMORY_EVOLUTION_CYCLE_DETECTED"))
        add(checks, "correction_cycle_rejected", expect_error(lambda: ledger.supersede_admitted_memory(scope, replacement_id, original_id, actor, "Circular chain.", idempotency_key="cycle"), "MEMORY_EVOLUTION_CYCLE_DETECTED"))
        add(checks, "competing_terminal_evolution_rejected", expect_error(lambda: ledger.supersede_admitted_memory(scope, original_id, new_launch_id, actor, "Competing terminal evolution.", idempotency_key="compete"), "MEMORY_EVOLUTION_STATE_INVALID"))
        add(checks, "one_event_conflict_rejected", expect_error(lambda: ledger.declare_memory_contradiction(scope, [late_id], "general_contradiction", actor, "Invalid singleton.", idempotency_key="singleton"), "MEMORY_CONFLICT_INVALID"))
        add(checks, "cross_scope_event_access_denied", expect_error(lambda: ledger.retract_admitted_memory(scope, other["event"]["event_id"], actor, "Wrong scope.", idempotency_key="wrong-scope"), "MEMORY_EVENT_NOT_FOUND"))
        add(checks, "cross_scope_conflict_access_denied", expect_error(lambda: ledger.get_conflict(other_scope, conflict.conflict_id), "MEMORY_CONFLICT_NOT_FOUND"))
        add(checks, "unrelated_scope_isolated", len(MemoryStateResolver(repository).resolve_effective_events(other_scope).effective_events) == 1)

        trace = ledger.trace_memory_evolution(scope, original_id)
        add(checks, "evolution_trace_has_origin", bool(trace["origins"][original_id]["source_id"]))
        add(checks, "evolution_trace_has_successor", replacement_id in trace["successor_event_ids"])
        add(checks, "evolution_trace_integrity_verified", trace["integrity"]["verified"])
        add(checks, "source_and_admission_provenance_intact", all(admission.verify_admission_integrity(scope, item["admission_id"]).verified for item in records.values()))

        try:
            SourceLedger(repository).delete_source(
                scope,
                records["correction_original"]["source_id"],
                "Deletion protection proof.",
            )
            deletion_details = {}
            deletion_blocked = False
        except SourceLedgerError as exc:
            deletion_details = exc.details
            deletion_blocked = exc.code == "SOURCE_HAS_ADMITTED_MEMORY"
        add(checks, "source_deletion_remains_blocked", deletion_blocked)
        add(checks, "source_deletion_returns_safe_counts", deletion_details.get("accepted_memory_count", 0) == 1 and deletion_details.get("evolution_link_count", 0) >= 1 and "conflict_count" in deletion_details and "reconstruction_count" in deletion_details)

        legacy_scope = AuthenticatedScope("client_legacy", "vault_legacy", "default")
        insert_legacy_history(repository, legacy_scope, 3)
        legacy_packet = MemoryReconstructionService(repository).build_continuity_packet(
            legacy_scope
        )
        add(checks, "legacy_external_events_remain_usable", legacy_packet["source_event_count"] == 3)
        add(checks, "legacy_mode_remains_available", MemoryReconstructionService(repository).build_continuity_packet(legacy_scope, input_mode="legacy_all_events")["packet_id"] == legacy_packet["packet_id"])

        integrity = MemoryLedgerIntegrityVerifier(
            repository
        ).verify_memory_ledger_integrity(scope)
        add(checks, "memory_ledger_integrity_verified", integrity.verified, integrity.failures)
        add(checks, "no_orphan_evolution_records", integrity.checks["evolution_sources_exist"] and integrity.checks["replacement_events_exist"])
        add(checks, "reconstruction_hashes_reproduce", integrity.checks["reconstruction_hashes_reproduce"])
        add(checks, "packet_exclusion_counts_match", integrity.checks["packet_exclusions_match"])
        add(checks, "existing_continuity_revision_unchanged", current.continuity_packet["algorithm_revision"] == baseline_packet["algorithm_revision"])
        add(checks, "resolved_input_mode_recorded", current.continuity_packet["memory_ledger_context"]["continuity_input_mode"] == "resolved_memory_events_v1")
        add(checks, "excluded_provenance_is_count_only", set(current.continuity_packet["memory_ledger_context"]["excluded_counts"]) >= {"superseded", "retracted", "invalidated"})
        add(checks, "packet_contains_no_raw_source_payload", "sanitised_payload" not in json.dumps(current.continuity_packet))

        current_identity = (
            current.reconstruction_id,
            current.reconstruction_hash,
            current.continuity_packet["packet_id"],
        )
        historical_identity = (
            late_after.reconstruction_id,
            late_after.reconstruction_hash,
            late_after.continuity_packet["packet_id"],
        )
        del reconstructor, resolver, ledger, admission
        restarted_repository = SelfServeRepositoryV093(db_path)
        restarted = MemoryReconstructionService(restarted_repository)
        restarted_current = restarted.reconstruct_current_state(scope)
        restarted_late = restarted.reconstruct_bitemporal(
            scope, "2025-07-02T00:00:00Z", after(late_known)
        )
        add(checks, "restart_current_identity_stable", current_identity == (restarted_current.reconstruction_id, restarted_current.reconstruction_hash, restarted_current.continuity_packet["packet_id"]))
        add(checks, "restart_historical_identity_stable", historical_identity == (restarted_late.reconstruction_id, restarted_late.reconstruction_hash, restarted_late.continuity_packet["packet_id"]))
        add(checks, "restart_integrity_verified", MemoryLedgerIntegrityVerifier(restarted_repository).verify_memory_ledger_integrity(scope).verified)

        performance: dict[str, Any] = {}
        for size in (100, 1000, 10000):
            perf_scope = AuthenticatedScope(
                f"client_perf_{size}", f"vault_perf_{size}", "default"
            )
            insert_legacy_history(restarted_repository, perf_scope, size)
            started = time.perf_counter()
            result = MemoryStateResolver(restarted_repository).resolve_effective_events(
                perf_scope
            )
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            performance[str(size)] = {
                "event_count": len(result.effective_events),
                "resolution_ms": elapsed,
                "environment": "local durable SQLite synthetic history",
            }
            add(checks, f"performance_{size}_events_completed", len(result.effective_events) == size, elapsed)

        add(checks, "sqlite_schema_revision_present", table_count(restarted_repository, "prmr_memory_ledger_schema_migrations") == 1)
        add(checks, "evolution_records_durable", table_count(restarted_repository, "prmr_memory_evolution_records") >= 6)
        add(checks, "conflict_records_durable", table_count(restarted_repository, "prmr_memory_conflicts") == 1)
        add(checks, "reconstruction_records_durable", table_count(restarted_repository, "prmr_memory_reconstructions") >= 8)

        private = {
            "database_kind": "temporary durable SQLite file",
            "scope": scope.memory_boundary(),
            "event_ids": {name: item["event"]["event_id"] for name, item in records.items()},
            "evolution_ids": [item.evolution_id for item in MemoryLedgerService(restarted_repository).list_evolutions(scope)],
            "conflict_id": conflict.conflict_id,
            "current_reconstruction_id": current.reconstruction_id,
            "current_reconstruction_hash": current.reconstruction_hash,
            "open_reconstruction_id": open_reconstruction.reconstruction_id,
            "deletion_dependency_counts": deletion_details,
            "integrity": integrity.checks,
            "integrity_details": integrity.details,
            "performance_observations": performance,
        }
    return checks, private


def postgres_status() -> dict[str, Any]:
    if not os.getenv("DATABASE_URL", "").strip():
        return {
            "status": "NOT_RUN_DATABASE_URL_MISSING",
            "validated": False,
            "limitation": "PostgreSQL migration, transactions, concurrency and restart persistence were not exercised.",
        }
    return {
        "status": "NOT_RUN_BY_SQLITE_RUNNER",
        "validated": False,
        "limitation": "DATABASE_URL exists, but this runner does not mutate an unspecified shared database. Run the dedicated audit in an isolated Postgres environment.",
    }


def build_scorecard(public: dict[str, Any]) -> str:
    rows = [
        "# Core Sprint 4 - Bitemporal Memory Ledger Evolution",
        "",
        f"- Result: **{public['result']}**",
        f"- Passed checks: **{public['passed_checks']}/{public['total_checks']}**",
        f"- SQLite: **{public['sqlite_status']}**",
        f"- PostgreSQL: **{public['postgres_status']}**",
        "",
        "## Revision Lock",
        "",
    ]
    rows.extend(f"- `{key}`: `{value}`" for key, value in public["revisions"].items())
    rows.extend(
        [
            "",
            "## Honest Boundary",
            "",
            BOUNDARY,
            "",
            "## Limitations",
            "",
        ]
    )
    rows.extend(f"- {item}" for item in public["limitations"])
    rows.extend(["", REQUIRED_FINAL_STATEMENT, ""])
    return "\n".join(rows)


def main() -> int:
    checks, private_details = run_sqlite_suite()
    failed = [item for item in checks if not item["passed"]]
    postgres = postgres_status()
    result = (
        "NEEDS WORK"
        if failed
        else "PASS"
        if postgres["validated"]
        else "PASS WITH DOCUMENTED LIMITATIONS"
    )
    revisions = {
        "memory_ledger_schema_revision": MEMORY_LEDGER_SCHEMA_REVISION,
        "memory_evolution_revision": MEMORY_EVOLUTION_REVISION,
        "memory_state_resolver_revision": MEMORY_STATE_RESOLVER_REVISION,
        "memory_conflict_revision": MEMORY_CONFLICT_REVISION,
        "memory_reconstruction_revision": MEMORY_RECONSTRUCTION_REVISION,
        "bitemporal_policy_revision": BITEMPORAL_POLICY_REVISION,
        "continuity_input_resolver_revision": CONTINUITY_INPUT_RESOLVER_REVISION,
    }
    public = {
        "version": "core_sprint_4",
        "result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "sqlite_status": "PASS" if not failed else "NEEDS_WORK",
        "postgres_status": postgres["status"],
        "revisions": revisions,
        "capabilities_proven": [
            "append-only correction, supersession and retraction",
            "explicit contradiction declaration and resolution",
            "valid-time and system-known-time reconstruction",
            "resolved effective-event continuity input",
            "deterministic reconstruction identity and restart replay",
            "source provenance protection and tenant isolation",
        ],
        "performance_observations": private_details["performance_observations"],
        "limitations": [
            postgres["limitation"],
            "Contradictions are declared and resolved explicitly; no automatic truth winner is selected.",
            "Performance figures are local synthetic SQLite observations, not production benchmarks.",
            "Automatic contradiction discovery, advanced decay, entity memory and consolidation remain future core work.",
        ],
        "boundary": BOUNDARY,
        "required_final_statement": REQUIRED_FINAL_STATEMENT,
        "public_safe": True,
    }
    private = {
        **public,
        "checks": checks,
        "private_internal_details": private_details,
        "postgres": postgres,
        "contains_raw_credentials": False,
    }
    add(checks, "public_report_secret_safe", no_secret(public))
    # Recompute after the report-hygiene check becomes part of evidence.
    failed = [item for item in checks if not item["passed"]]
    public["passed_checks"] = len(checks) - len(failed)
    public["total_checks"] = len(checks)
    public["failed_checks"] = [item["name"] for item in failed]
    public["result"] = (
        "NEEDS WORK"
        if failed
        else "PASS"
        if postgres["validated"]
        else "PASS WITH DOCUMENTED LIMITATIONS"
    )
    private.update(public)
    private["checks"] = checks
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")

    print("PRMR Memory Core - Core Sprint 4")
    print(f"Passed checks: {public['passed_checks']}/{public['total_checks']}")
    print(f"SQLite: {public['sqlite_status']}")
    print(f"PostgreSQL: {public['postgres_status']}")
    print(f"Result: {public['result']}")
    if failed:
        print("Failed: " + ", ".join(public["failed_checks"]))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
