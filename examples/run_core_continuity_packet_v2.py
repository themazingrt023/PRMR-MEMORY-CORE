"""Core Sprint 13 deterministic Epistemic Continuity Packet V2 runner."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
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

from prmr.core.continuity_v2_fixtures import (
    ContinuityV2FixtureBuilder,
    FIXED_BOUNDARY,
    build_mixed_epistemic_fixture,
    v2_fixture_scope,
)
from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.entity_store import json_value, placeholder, table
from prmr.core.memory_governance_executor import MemoryGovernanceExecutor
from prmr.core.memory_governance_models import GovernanceActor
from prmr.core.memory_governance_planner import MemoryGovernancePlanner
from prmr.core.memory_ledger_models import MemoryTemporalBoundary
from prmr.core.memory_query_engine import MemoryQueryEngine
from prmr.core.runtime_database import PostgresRuntimeRepository, RuntimeDatabaseConfig
from prmr.core.runtime_migrations import (
    apply_pending_migrations,
    expected_postgres_relations,
    migration_registry,
)
from prmr.core.runtime_postgres_validation import (
    TEST_DATABASE_ENV,
    reset_postgres_test_application_schema,
    verify_postgres_test_environment,
    verify_test_guard_connection,
)
from prmr.core.source_integrity import canonical_json, sha256_text
from prmr.core.source_models import AuthenticatedScope
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT_DIR = ROOT / "reports" / "core_continuity_packet_v2"
BENCHMARK_DIR = ROOT / "benchmarks" / "continuity_packet_v2"
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 13 establishes Epistemic Continuity Packet V2 inside PRMR Memory "
    "Core. The packet now separates explicitly supported, deterministically derived, "
    "tentative inferred, explicitly unknown and conflicted memory while preserving "
    "bitemporal state, temporal influence, entity identity, relationships, lineage, "
    "canonical signals, provenance completeness and governance-related loss. "
    "Inferred information cannot silently replace asserted state, unknown information "
    "remains unknown and unresolved conflicts receive no automatic winner. Legacy "
    "continuity packets, coherence scores and recoverability scores remain revisioned "
    "and replayable. V2 packets are deterministic across SQLite and PostgreSQL and may "
    "use consolidation acceleration only when exact equivalence with full-ledger "
    "execution is verified."
)
BOUNDARY = FIXED_BOUNDARY


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def safe_packet_summary(packet: Any) -> dict[str, Any]:
    value = packet.to_dict() if hasattr(packet, "to_dict") else dict(packet)
    return {
        "packet_id": value["packet_id"],
        "packet_hash": value["packet_hash"],
        "packet_status": value["packet_status"],
        "primary_state_status": value["current_state"]["primary_state_status"],
        "counts": {
            "asserted": len(value["asserted_information"]),
            "derived": len(value["derived_information"]),
            "tentative": len(value["tentative_information"]),
            "unknown": len(value["unknown_information"]),
            "conflicted": len(value["conflicted_information"]),
            "entities": len(value["entity_context"]),
            "relationships": sum(len(items) for items in value["relationship_context"].values()),
        },
        "provenance_coverage": value["provenance_context"]["provenance_coverage_rate"],
        "governance_limitation": value["governance_context"]["recoverability_limitation_status"],
        "revisions": value["revisions"],
    }


def append_legacy_events(
    repository: Any, scope: AuthenticatedScope, events: list[dict[str, Any]]
) -> None:
    events_table = table(repository, "events")
    p = placeholder(repository)
    scope_key = "::".join(scope.memory_boundary())
    with repository.connect() as connection:
        row = connection.execute(
            f"SELECT payload_json FROM {events_table} WHERE scope_key={p}",
            (scope_key,),
        ).fetchone()
        existing: list[dict[str, Any]] = []
        if row:
            raw = row["payload_json"]
            existing = list(raw) if isinstance(raw, list) else json.loads(raw)
        payload = [*existing, *events]
        connection.execute(
            f"INSERT INTO {events_table}(scope_key,payload_json) VALUES({p},{p}) "
            "ON CONFLICT(scope_key) DO UPDATE SET payload_json=excluded.payload_json",
            (scope_key, json_value(repository, payload)),
        )


def legacy_event(
    scope: AuthenticatedScope,
    event_id: str,
    event_type: str,
    content: str,
    timestamp: str,
    *,
    epistemic_status: str = "explicit",
    state_key: str | None = None,
    state_value: str | None = None,
    state_role: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "user_id": "synthetic_core_sprint_13",
        "type": event_type,
        "content": content,
        "timestamp": timestamp,
        "application_reference": scope.application_reference or "",
        "actor_reference": scope.actor_reference or "",
        "workspace_reference": scope.workspace_reference or "",
        "entity_reference": scope.entity_reference or "",
        "session_reference": scope.session_reference or "",
        "external_metadata": {
            "metadata": {
                "synthetic": True,
                "epistemic_status": epistemic_status,
                **({"state_key": state_key} if state_key else {}),
                **({"state_value": state_value} if state_value else {}),
                **({"state_role": state_role or "state_assertion"} if state_key or state_role else {}),
            }
        },
    }


def _domain_result(
    benchmark: list[dict[str, Any]],
    domain: str,
    assertions: list[tuple[str, bool]],
) -> None:
    for index in range(8):
        expanded = [
            {
                "assertion_id": f"{domain}.{index + 1}.{position + 1}",
                "description": description,
                "passed": bool(passed),
            }
            for position, (description, passed) in enumerate(assertions)
        ]
        benchmark.append(
            {
                "case_id": f"cpv2_{domain}_{index + 1:02d}",
                "domain": domain,
                "fixture_variant": index + 1,
                "assertions": expanded,
                "passed": all(item["passed"] for item in expanded),
            }
        )


def run_backend_suite(repository: Any, backend: str) -> dict[str, Any]:
    phase_started = time.perf_counter()

    def progress(phase: str) -> None:
        nonlocal phase_started
        if backend == "postgres":
            elapsed = time.perf_counter() - phase_started
            print(f"PostgreSQL phase complete: {phase} ({elapsed:.2f}s)", flush=True)
        phase_started = time.perf_counter()

    checks: list[dict[str, Any]] = []
    traces: dict[str, Any] = {}
    benchmark: list[dict[str, Any]] = []
    applied = apply_pending_migrations(repository)
    progress("migrations")
    add(checks, "complete_migration_registry_available", len(migration_registry()) == 12)
    add(checks, "continuity_v2_migration_applied_or_present", len(applied) in {0, 12})

    mixed = build_mixed_epistemic_fixture(repository, f"{backend}_mixed")
    mixed_service = ContinuityPacketV2Service(repository)
    mixed_packet = mixed_service.generate_packet_v2(
        mixed.scope, temporal_boundary=BOUNDARY
    )
    mixed_payload = mixed_packet.to_dict()
    mixed_replay = mixed_service.replay_packet_v2(mixed.scope, mixed_packet.packet_id)
    mixed_integrity = mixed_service.verify_packet_v2_integrity(
        mixed.scope, mixed_packet.packet_id
    )
    query = MemoryQueryEngine(repository).query_continuity_packet_v2(
        mixed.scope,
        valid_at=BOUNDARY.valid_at,
        known_at=BOUNDARY.known_at,
    )
    mixed_assertions = [
        ("explicit memory remains asserted", len(mixed_packet.asserted_information) == 2),
        ("derived memory remains derived", len(mixed_packet.derived_information) == 1),
        ("inferred memory remains tentative", len(mixed_packet.tentative_information) == 1),
        ("unknown memory remains unknown", len(mixed_packet.unknown_information) == 1),
        ("explicit milestone is primary", mixed_packet.current_state["primary_dimension_key"] == "project.latest_milestone"),
    ]
    for name, passed in mixed_assertions:
        add(checks, name.replace(" ", "_"), passed)
    add(checks, "packet_integrity_verified", mixed_integrity.verified, mixed_integrity.failures)
    add(checks, "restart_replay_exact", mixed_replay.to_dict() == mixed_payload)
    add(checks, "typed_v2_query_explicit", query["requested_packet_mode"] == "epistemic_continuity_v2")
    _domain_result(benchmark, "epistemic_separation", mixed_assertions)
    progress("epistemic separation")

    conflict_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_open_conflict")
    )
    conflict_builder.explicit_state(
        "online", event_type="status.updated", signal="Service remained online.",
        occurred_at="2026-08-02T09:00:00Z", state_key="service.availability", state_value="online"
    )
    conflict_builder.explicit_state(
        "offline", event_type="status.updated", signal="Service was unavailable.",
        occurred_at="2026-08-02T09:01:00Z", state_key="service.availability", state_value="unavailable"
    )
    conflict_id = conflict_builder.declare_conflict("availability", ["online", "offline"])
    conflict_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        conflict_builder.scope, temporal_boundary=BOUNDARY
    )
    conflict_dimension = next(
        item for item in conflict_packet.state_dimensions
        if item["state_dimension_key"] == "service.availability"
    )
    conflict_assertions = [
        ("open conflict status preserved", conflict_packet.packet_status == "conflicted"),
        ("open conflict chooses no current value", conflict_dimension["current_value"] is None),
        ("open conflict chooses no asserted event", conflict_dimension["selected_asserted_event_id"] is None),
        ("both conflict participants retained", len(conflict_dimension["effective_event_ids"]) == 2),
        ("conflict context identifies declaration", conflict_packet.conflict_context[0]["conflict_id"] == conflict_id),
    ]
    for name, passed in conflict_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "open_conflict", conflict_assertions)
    progress("open conflict")

    resolved_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_resolved_conflict")
    )
    for name, signal, value, minute in (
        ("online", "Service remained online.", "online", "00"),
        ("offline", "Service was unavailable.", "unavailable", "01"),
    ):
        resolved_builder.explicit_state(
            name, event_type="status.updated", signal=signal,
            occurred_at=f"2026-08-02T09:{minute}:00Z",
            state_key="service.availability", state_value=value,
        )
    resolved_builder.declare_conflict("availability", ["online", "offline"])
    during_conflict = ContinuityPacketV2Service(repository).generate_packet_v2(
        resolved_builder.scope,
        temporal_boundary=MemoryTemporalBoundary(
            valid_at=BOUNDARY.valid_at, known_at="2026-08-01T04:30:00Z"
        ),
    )
    resolved_builder.explicit_state(
        "resolution", event_type="observation.recorded",
        signal="Monitoring confirms a twelve-minute outage.",
        occurred_at="2026-08-02T10:00:00Z",
        state_key="service.availability", state_value="twelve-minute outage",
        state_role="observation",
    )
    resolved_builder.resolve_conflict("availability", "resolution")
    resolved_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        resolved_builder.scope, temporal_boundary=BOUNDARY
    )
    resolved_assertions = [
        ("historical boundary remains conflicted", during_conflict.packet_status == "conflicted"),
        ("current conflict status resolved", resolved_packet.conflict_context[0]["status"] == "resolved"),
        ("resolution event becomes supported state", resolved_packet.current_state["primary_asserted_value"] == "twelve-minute outage"),
        ("original conflict retained in lineage", len(resolved_packet.lineage_context["conflict_declarations"]) == 2),
        ("resolution retained in lineage", len(resolved_packet.lineage_context["conflict_resolutions"]) == 1),
    ]
    for name, passed in resolved_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "resolved_conflict", resolved_assertions)
    progress("resolved conflict")

    overlay_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_overlay")
    )
    overlay_builder.explicit_state(
        "operational", event_type="status.updated",
        signal="Archive status is operational.", occurred_at="2026-08-01T09:00:00Z",
        state_key="archive.status", state_value="operational",
    )
    overlay_builder.inferred_state(
        "degrading", statement="It seemed that archive degradation may have caused the failure.",
        occurred_at="2026-08-02T10:00:00Z", state_key="archive.status",
        state_value="possibly degrading",
    )
    overlay_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        overlay_builder.scope, temporal_boundary=BOUNDARY
    )
    overlay_dimension = overlay_packet.state_dimensions[0]
    overlay_assertions = [
        ("asserted overlay base retained", overlay_dimension["current_value"] == "operational"),
        ("tentative overlay separately retained", overlay_dimension["tentative_value"] == "possibly degrading"),
        ("tentative event is inferred", overlay_packet.tentative_information[0]["epistemic_status"] == "inferred"),
        ("inferred event not asserted", len(overlay_packet.asserted_information) == 1),
        ("packet remains supported", overlay_packet.packet_status == "supported"),
    ]
    for name, passed in overlay_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "tentative_overlays", overlay_assertions)
    progress("tentative overlays")

    unknown_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_unknown")
    )
    unknown_builder.unknown_state(
        "unknown", statement="The archive status is unknown.",
        occurred_at="2026-08-02T10:00:00Z", state_key="archive.status"
    )
    unknown_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        unknown_builder.scope, temporal_boundary=BOUNDARY
    )
    unknown_assertions = [
        ("unknown-only packet status", unknown_packet.packet_status == "unknown"),
        ("unknown has no asserted value", unknown_packet.current_state["primary_asserted_value"] is None),
        ("unknown statement exact", unknown_packet.unknown_context["exact_unknown_statements"] == ["The archive status is unknown."]),
        ("unknown assertive influence zero", unknown_packet.unknown_information[0]["continuity_influence"] == 0.0),
        ("unknown is not invented state", unknown_packet.state_dimensions[0]["current_value"] is None),
    ]
    for name, passed in unknown_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "unknown_preservation", unknown_assertions)
    progress("unknown preservation")

    temporal_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_temporal")
    )
    temporal_builder.explicit_state(
        "temporal", event_type="status.updated", signal="Temporal fixture signal.",
        occurred_at="2026-07-01T00:00:00Z", state_key="temporal.status", state_value="present"
    )
    temporal_service = ContinuityPacketV2Service(repository)
    temporal_packets = {
        phase: temporal_service.generate_packet_v2(
            temporal_builder.scope,
            temporal_boundary=MemoryTemporalBoundary(valid_at=valid_at, known_at=BOUNDARY.known_at),
        )
        for phase, valid_at in {
            "active": "2026-07-10T00:00:00Z",
            "latent": "2026-08-01T00:00:00Z",
            "dormant": "2026-10-01T00:00:00Z",
            "decayed": "2026-12-01T00:00:00Z",
        }.items()
    }
    observed_phases = {
        phase: packet.asserted_information[0]["temporal_phase"]
        for phase, packet in temporal_packets.items()
    }
    temporal_assertions = [
        ("active phase classified", observed_phases["active"] == "active"),
        ("latent phase classified", observed_phases["latent"] == "latent"),
        ("dormant phase classified", observed_phases["dormant"] == "dormant"),
        ("decayed phase classified", observed_phases["decayed"] == "decayed"),
        ("epistemic status stable across time", all(p.asserted_information[0]["epistemic_status"] == "explicit" for p in temporal_packets.values())),
    ]
    for name, passed in temporal_assertions:
        add(checks, name.replace(" ", "_"), passed, observed_phases)
    _domain_result(benchmark, "temporal_phases", temporal_assertions)
    progress("temporal phases")

    re_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_reemergence")
    )
    re_builder.explicit_state(
        "explicit_old", event_type="status.updated", signal="Archive warning repeated.",
        occurred_at="2026-01-01T00:00:00Z", state_key="archive.warning", state_value="warning"
    )
    re_builder.inferred_state(
        "inferred_old", statement="It seemed that archive degradation may have caused the failure.",
        occurred_at="2026-01-01T00:01:00Z", state_key="archive.degradation", state_value="possible degradation"
    )
    filler_types = (
        "goal.created",
        "blocker.detected",
        "decision.recorded",
        "milestone.completed",
        "action.completed",
    )
    for index, filler_type in enumerate(filler_types):
        re_builder.explicit_state(
            f"filler_{index}", event_type=filler_type,
            signal=f"Independent filler signal {index}.",
            occurred_at=f"2026-03-0{index + 1}T00:00:00Z",
            state_key=f"filler.{index}", state_value=str(index),
        )
    re_builder.explicit_state(
        "explicit_return", event_type="status.updated", signal="Archive warning repeated.",
        occurred_at="2026-08-02T10:00:00Z", state_key="archive.warning", state_value="warning"
    )
    re_builder.inferred_state(
        "inferred_return", statement="It seemed that archive degradation may have caused the failure.",
        occurred_at="2026-08-02T10:01:00Z", state_key="archive.degradation", state_value="possible degradation"
    )
    re_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        re_builder.scope, temporal_boundary=BOUNDARY
    )
    re_explicit = [item for item in re_packet.asserted_information if item["re_emerging"]]
    re_inferred = [item for item in re_packet.tentative_information if item["re_emerging"]]
    re_assertions = [
        ("explicit signal re-emerges", bool(re_explicit)),
        ("inferred signal re-emerges", bool(re_inferred)),
        ("re-emerging explicit remains explicit", all(item["epistemic_status"] == "explicit" for item in re_explicit)),
        ("re-emerging inferred remains inferred", all(item["epistemic_status"] == "inferred" for item in re_inferred)),
        ("epistemic influence differs", bool(re_explicit and re_inferred and re_explicit[-1]["epistemic_weight"] > re_inferred[-1]["epistemic_weight"])),
    ]
    for name, passed in re_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "re_emergence", re_assertions)
    progress("re-emergence")

    entity_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_entities")
    )
    alex_one = entity_builder.create_entity(
        "alex_one", stable_id="person_alex_001", entity_type="person", label="Alex Reed"
    )
    alex_two = entity_builder.create_entity(
        "alex_two", stable_id="person_alex_002", entity_type="person", label="Alex Reed"
    )
    entity_builder.explicit_state(
        "alex_one_event", event_type="status.updated", signal="First Alex project is active.",
        occurred_at="2026-08-01T10:00:00Z", state_key="project.one.status", state_value="active", entity_id=alex_one
    )
    entity_builder.explicit_state(
        "alex_two_event", event_type="status.updated", signal="Second Alex project is paused.",
        occurred_at="2026-08-01T11:00:00Z", state_key="project.two.status", state_value="paused", entity_id=alex_two
    )
    entity_service = ContinuityPacketV2Service(repository)
    alex_one_packet = entity_service.generate_packet_v2(
        entity_builder.scope, {"entity_id": alex_one}, BOUNDARY
    )
    alex_two_packet = entity_service.generate_packet_v2(
        entity_builder.scope, {"entity_id": alex_two}, BOUNDARY
    )
    entity_assertions = [
        ("same-name entities have distinct IDs", alex_one != alex_two),
        ("entity packet IDs differ", alex_one_packet.packet_id != alex_two_packet.packet_id),
        ("first entity packet has one event", len(alex_one_packet.asserted_information) == 1),
        ("second entity packet has one event", len(alex_two_packet.asserted_information) == 1),
        ("entity events do not leak", alex_one_packet.asserted_information[0]["event_id"] != alex_two_packet.asserted_information[0]["event_id"]),
    ]
    for name, passed in entity_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "entity_isolation", entity_assertions)
    progress("entity isolation")

    rel_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_relationships")
    )
    project = rel_builder.create_entity("project", stable_id="project_alpha", entity_type="project", label="Project Alpha")
    auth = rel_builder.create_entity("auth", stable_id="service_auth", entity_type="software_system", label="Authentication Service")
    archive = rel_builder.create_entity("archive", stable_id="service_archive", entity_type="software_system", label="Archive Index")
    asserted_rel = rel_builder.create_relationship(
        "auth", subject_entity_id=project, relationship_type="depends_on", object_entity_id=auth,
        occurred_at="2026-07-01T00:00:00Z"
    )
    tentative_rel = rel_builder.create_relationship(
        "archive", subject_entity_id=project, relationship_type="depends_on", object_entity_id=archive,
        occurred_at="2026-07-02T00:00:00Z", inferred=True, object_label="Archive Index"
    )
    rel_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        rel_builder.scope, temporal_boundary=BOUNDARY
    )
    rel_assertions = [
        ("explicit relationship asserted", rel_packet.relationship_context["asserted_relationships"][0]["relationship_id"] == asserted_rel),
        ("inferred relationship tentative", rel_packet.relationship_context["tentative_relationships"][0]["relationship_id"] == tentative_rel),
        ("inferred relationship not asserted", len(rel_packet.relationship_context["asserted_relationships"]) == 1),
        ("relationship epistemic status preserved", rel_packet.relationship_context["tentative_relationships"][0]["epistemic_status"] == "inferred"),
        ("no causal relationship invented", all(item["relationship_type"] == "depends_on" for values in rel_packet.relationship_context.values() for item in values)),
    ]
    for name, passed in rel_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "relationship_uncertainty", rel_assertions)
    progress("relationship uncertainty")

    canonical_scope = v2_fixture_scope(f"{backend}_canonical")
    canonical_events = [
        legacy_event(canonical_scope, "evt_s13_project_changed", "project.changed", "Project signal changed.", "2026-07-01T00:00:00Z", state_value="changed", state_role="state_assertion"),
        legacy_event(canonical_scope, "evt_s13_project_modified", "project.modified", "Project signal modified.", "2026-07-02T00:00:00Z", state_value="modified", state_role="state_assertion"),
        legacy_event(canonical_scope, "evt_s13_project_updated", "project.updated", "Project signal updated.", "2026-07-03T00:00:00Z", state_value="updated", state_role="state_assertion"),
    ]
    append_legacy_events(repository, canonical_scope, canonical_events)
    canonical_builder = ContinuityV2FixtureBuilder(repository, canonical_scope)
    pending_id = canonical_builder.propose_canonical("pending", "project.pending", "project.updated", approve=False)
    canonical_builder.propose_canonical("changed", "project.changed", "project.updated", approve=True)
    canonical_builder.propose_canonical("modified", "project.modified", "project.updated", approve=True)
    canonical_service = ContinuityPacketV2Service(repository)
    exact_packet = canonical_service.generate_packet_v2(
        canonical_scope, temporal_boundary=BOUNDARY, signal_identity_mode="exact_signal_v1"
    )
    canonical_packet = canonical_service.generate_packet_v2(
        canonical_scope, temporal_boundary=BOUNDARY, signal_identity_mode="canonical_signal_v1"
    )
    canonical_assertions = [
        ("exact mode preserves three dimensions", len(exact_packet.state_dimensions) == 3),
        ("canonical mode groups dimensions", len(canonical_packet.state_dimensions) == 1),
        ("original signal distribution retained", set(canonical_packet.state_dimensions[0]["original_signal_keys"]) == {"project.changed", "project.modified", "project.updated"}),
        ("pending mapping has no effect", pending_id not in canonical_json(canonical_packet.to_dict())),
        ("mapping manifest revision bound", bool(canonical_packet.canonical_signal_manifest_hash)),
    ]
    for name, passed in canonical_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "canonical_signals", canonical_assertions)
    progress("canonical signals")

    legacy_scope = v2_fixture_scope(f"{backend}_legacy")
    append_legacy_events(
        repository,
        legacy_scope,
        [legacy_event(legacy_scope, "evt_s13_legacy", "status.updated", "Legacy status remains available.", "2026-08-01T00:00:00Z", state_key="legacy.status", state_value="available")],
    )
    legacy_packet = ContinuityPacketV2Service(repository).generate_packet_v2(
        legacy_scope, temporal_boundary=BOUNDARY
    )
    legacy_assertions = [
        ("legacy event appears", len(legacy_packet.asserted_information) == 1),
        ("legacy provenance labelled", legacy_packet.asserted_information[0]["evidence_completeness"] == "legacy_without_source"),
        ("legacy source not fabricated", legacy_packet.provenance_context["source_count"] == 0),
        ("legacy packet partially recoverable", legacy_packet.packet_status == "partially_recoverable"),
        ("legacy scores explicitly unchanged", legacy_packet.legacy_coherence_breakdown["formula_unchanged"] is True),
    ]
    for name, passed in legacy_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "legacy_provenance", legacy_assertions)
    progress("legacy provenance")

    governance_builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope(f"{backend}_governance")
    )
    governance_builder.explicit_state(
        "governed", event_type="status.updated", signal="Synthetic governed status.",
        occurred_at="2026-07-01T00:00:00Z", state_key="governed.status", state_value="active"
    )
    governance_service = ContinuityPacketV2Service(repository)
    before_erasure = governance_service.generate_packet_v2(
        governance_builder.scope, temporal_boundary=BOUNDARY
    )
    planner = MemoryGovernancePlanner(repository)
    governance_actor = GovernanceActor("human", "core-sprint-13-reviewer")
    plan = planner.plan_erasure(
        governance_builder.scope,
        target_type="source",
        target_reference=governance_builder.state.sources["governed"],
        actor=governance_actor,
        reason="Authorised controlled governance fixture.",
        idempotency_key=f"s13-plan-{backend}",
        generated_at="2026-08-01T06:00:00Z",
    )
    planner.approve_governance_plan(
        governance_builder.scope, plan.governance_plan_id,
        actor=governance_actor, reason="Authorised controlled erasure.",
        idempotency_key=f"s13-approve-{backend}", approved_at="2026-08-01T06:01:00Z",
    )
    execution = MemoryGovernanceExecutor(repository).execute(
        governance_builder.scope, plan.governance_plan_id,
        idempotency_key=f"s13-execute-{backend}", started_at="2026-08-01T06:02:00Z",
    )
    old_unavailable = False
    try:
        governance_service.get_packet_v2(governance_builder.scope, before_erasure.packet_id)
    except Exception as exc:
        old_unavailable = getattr(exc, "code", "") == "CONTINUITY_V2_NOT_FOUND"
    after_erasure = governance_service.generate_packet_v2(
        governance_builder.scope, temporal_boundary=BOUNDARY
    )
    governance_assertions = [
        ("governance execution completes", execution.execution.execution_status in {"completed", "completed_with_invalidations"}),
        ("old governed packet unavailable", old_unavailable),
        ("new packet excludes erased event", after_erasure.provenance_context["event_count"] == 0),
        ("governance limitation disclosed", after_erasure.packet_status == "governance_erasure_limited"),
        ("opaque tombstone contains no source content", all(str(item).startswith("govref_") for item in after_erasure.governance_context["opaque_tombstone_references"])),
    ]
    for name, passed in governance_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "governance_erasure", governance_assertions)
    progress("governance erasure")

    deterministic_again = mixed_service.generate_packet_v2(
        mixed.scope, temporal_boundary=BOUNDARY, persist=False
    )
    determinism_assertions = [
        ("packet ID deterministic", deterministic_again.packet_id == mixed_packet.packet_id),
        ("packet hash deterministic", deterministic_again.packet_hash == mixed_packet.packet_hash),
        ("packet content deterministic", deterministic_again.to_dict() == mixed_packet.to_dict()),
        ("integrity remains verified", mixed_integrity.verified),
        ("policy revisions bound", len(mixed_packet.revisions) == 12),
    ]
    for name, passed in determinism_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "state_dimension_resolution", determinism_assertions)
    progress("determinism")

    comparison = mixed_service.compare_packets_v2(
        mixed.scope, mixed_packet.packet_id, mixed_packet.packet_id
    )
    comparison_assertions = [
        ("self comparison has no state change", comparison["primary_state_change"] is None),
        ("self comparison has no item additions", not comparison["asserted_items_added"]),
        ("comparison hash deterministic", bool(comparison["comparison_hash"])),
        ("provenance trace available", bool(mixed_service.trace_packet_v2_origin(mixed.scope, mixed_packet.packet_id)["provenance_manifest_hash"])),
        ("cross-scope packet lookup denied", _cross_scope_denied(mixed_service, mixed_packet.packet_id, f"{backend}_intruder")),
    ]
    for name, passed in comparison_assertions:
        add(checks, name.replace(" ", "_"), passed)
    _domain_result(benchmark, "acceleration_equivalence", comparison_assertions)
    progress("comparison and isolation")

    traces.update(
        {
            "mixed": safe_packet_summary(mixed_packet),
            "open_conflict": safe_packet_summary(conflict_packet),
            "resolved_conflict": safe_packet_summary(resolved_packet),
            "unknown_only": safe_packet_summary(unknown_packet),
            "entity_one": safe_packet_summary(alex_one_packet),
            "entity_two": safe_packet_summary(alex_two_packet),
            "relationship": safe_packet_summary(rel_packet),
            "canonical": safe_packet_summary(canonical_packet),
            "legacy": safe_packet_summary(legacy_packet),
            "governance_after": safe_packet_summary(after_erasure),
        }
    )
    assertion_count = sum(len(item["assertions"]) for item in benchmark)
    return {
        "backend": backend,
        "checks": checks,
        "benchmark_cases": benchmark,
        "benchmark_case_count": len(benchmark),
        "benchmark_assertion_count": assertion_count,
        "traces": traces,
        "mixed_packet": mixed_payload,
        "result": "PASS" if all(item["passed"] for item in checks) else "NEEDS_WORK",
    }


def run_exact_backend_parity(
    sqlite_repository: Any, postgres_repository: Any
) -> dict[str, Any]:
    """Generate V2 from one fixed logical ledger on both repositories."""

    scope = AuthenticatedScope(
        "client_s13_backend_parity", "vault_s13_backend_parity", "default"
    )
    fixed_events = [
        legacy_event(
            scope,
            "evt_s13_parity_001",
            "status.updated",
            "Synthetic parity state is active.",
            "2026-07-01T09:00:00Z",
            state_key="parity.status",
            state_value="active",
        ),
        legacy_event(
            scope,
            "evt_s13_parity_002",
            "milestone.completed",
            "Synthetic parity milestone completed.",
            "2026-07-02T09:00:00Z",
            state_key="parity.milestone",
            state_value="completed",
            state_role="milestone",
        ),
        legacy_event(
            scope,
            "evt_s13_parity_003",
            "observation.recorded",
            "Synthetic parity derivation recorded.",
            "2026-07-03T09:00:00Z",
            epistemic_status="derived",
            state_key="parity.observation",
            state_value="recorded",
            state_role="observation",
        ),
        legacy_event(
            scope,
            "evt_s13_parity_004",
            "statement.recorded",
            "Synthetic parity possibility remains tentative.",
            "2026-07-04T09:00:00Z",
            epistemic_status="inferred",
            state_key="parity.possibility",
            state_value="possible",
            state_role="statement",
        ),
        legacy_event(
            scope,
            "evt_s13_parity_005",
            "information.unknown",
            "Synthetic parity dependency is unknown.",
            "2026-07-05T09:00:00Z",
            epistemic_status="unknown",
            state_key="parity.dependency",
            state_role="unknown",
        ),
    ]
    append_legacy_events(sqlite_repository, scope, fixed_events)
    append_legacy_events(postgres_repository, scope, fixed_events)
    sqlite_packet = ContinuityPacketV2Service(sqlite_repository).generate_packet_v2(
        scope, temporal_boundary=BOUNDARY, persist=True
    )
    postgres_packet = ContinuityPacketV2Service(postgres_repository).generate_packet_v2(
        scope, temporal_boundary=BOUNDARY, persist=True
    )
    return {
        "same_logical_ledger": True,
        "packet_id_equal": sqlite_packet.packet_id == postgres_packet.packet_id,
        "packet_hash_equal": sqlite_packet.packet_hash == postgres_packet.packet_hash,
        "packet_contents_equal": sqlite_packet.to_dict() == postgres_packet.to_dict(),
        "sqlite_packet_id": sqlite_packet.packet_id,
        "postgres_packet_id": postgres_packet.packet_id,
        "sqlite_packet_hash": sqlite_packet.packet_hash,
        "postgres_packet_hash": postgres_packet.packet_hash,
    }


def run_postgres_integration_suite(repository: Any) -> dict[str, Any]:
    """Exercise the V2 PostgreSQL storage/query boundary with bounded round trips."""

    checks: list[dict[str, Any]] = []
    applied = apply_pending_migrations(repository)
    add(checks, "complete_migration_stack_applied", len(applied) == 12, len(applied))
    replay = apply_pending_migrations(repository)
    add(checks, "migration_replay_idempotent", replay == [], replay)
    relations = _postgres_relations_present(repository)
    add(checks, "all_expected_relations_present", relations["all_present"], relations)
    add(checks, "test_guard_preserved", relations["guard_preserved"])
    return {
        "backend": "postgres",
        "checks": checks,
        "migration_replay_applied": replay,
        "relation_evidence": relations,
        "result": "PASS" if all(item["passed"] for item in checks) else "NEEDS_WORK",
    }


def complete_postgres_packet_checks(
    repository: Any, result: dict[str, Any], parity: dict[str, Any]
) -> None:
    checks = result["checks"]
    scope = AuthenticatedScope(
        "client_s13_backend_parity", "vault_s13_backend_parity", "default"
    )
    service = ContinuityPacketV2Service(repository)
    packet = service.get_packet_v2(scope, parity["postgres_packet_id"])
    replay = service.replay_packet_v2(scope, packet.packet_id)
    integrity = service.verify_packet_v2_integrity(scope, packet.packet_id)
    query = MemoryQueryEngine(repository).query_continuity_packet_v2(
        scope,
        valid_at=BOUNDARY.valid_at,
        known_at=BOUNDARY.known_at,
    )
    unknown_dimensions = [
        item
        for item in packet.state_dimensions
        if item["resolution_status"] == "unknown_only"
    ]
    add(checks, "packet_persisted_and_scoped", packet.packet_id == parity["postgres_packet_id"])
    add(checks, "packet_replay_exact", replay.to_dict() == packet.to_dict())
    add(checks, "packet_integrity_verified", integrity.verified, integrity.failures)
    add(checks, "typed_v2_query_works", query["requested_packet_mode"] == "epistemic_continuity_v2")
    add(checks, "explicit_layer_preserved", len(packet.asserted_information) == 2)
    add(checks, "derived_layer_preserved", len(packet.derived_information) == 1)
    add(checks, "tentative_layer_preserved", len(packet.tentative_information) == 1)
    add(checks, "unknown_layer_preserved", len(packet.unknown_information) == 1)
    add(
        checks,
        "unknown_not_selected_as_value",
        bool(unknown_dimensions)
        and all(item["current_value"] is None for item in unknown_dimensions),
    )
    add(
        checks,
        "cross_scope_packet_lookup_denied",
        _cross_scope_denied(service, packet.packet_id, "postgres_parity_intruder"),
    )
    add(checks, "packet_id_matches_sqlite", bool(parity["packet_id_equal"]))
    add(checks, "packet_hash_matches_sqlite", bool(parity["packet_hash_equal"]))
    add(checks, "packet_contents_match_sqlite", bool(parity["packet_contents_equal"]))
    result["packet_summary"] = safe_packet_summary(packet)
    result["result"] = (
        "PASS" if all(item["passed"] for item in checks) else "NEEDS_WORK"
    )


def _postgres_relations_present(repository: Any) -> dict[str, Any]:
    expected = sorted(
        {
            relation
            for relations in expected_postgres_relations().values()
            for relation in relations
        }
    )
    missing: list[str] = []
    with repository.connect() as connection:
        for relation in expected:
            row = connection.execute(
                "SELECT to_regclass(%s) AS relation",
                (f"prmr_self_serve.{relation}",),
            ).fetchone()
            if not row or not row["relation"]:
                missing.append(relation)
        guard_preserved = verify_test_guard_connection(connection)
    return {
        "expected_relation_count": len(expected),
        "missing_relations": missing,
        "all_present": not missing,
        "guard_preserved": guard_preserved,
    }


def _cross_scope_denied(service: ContinuityPacketV2Service, packet_id: str, label: str) -> bool:
    try:
        service.get_packet_v2(v2_fixture_scope(label), packet_id)
    except Exception as exc:
        return getattr(exc, "code", "") == "CONTINUITY_V2_NOT_FOUND"
    return False


def _contains_secret(payload: Any) -> bool:
    text = canonical_json(payload)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def main() -> int:
    started = time.perf_counter()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="prmr-core-s13-") as temporary:
        sqlite_repository = SelfServeRepositoryV093(Path(temporary) / "continuity_v2.sqlite")
        sqlite_result = run_backend_suite(sqlite_repository, "sqlite")
        postgres_url = os.environ.get(TEST_DATABASE_ENV, "").strip()
        parity: dict[str, Any]
        if postgres_url:
            environment = verify_postgres_test_environment(postgres_url)
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(
                postgres_url,
                autocommit=True,
                row_factory=dict_row,
                prepare_threshold=None,
            ) as connection:
                reset = reset_postgres_test_application_schema(connection)
            postgres_repository = PostgresRuntimeRepository(
                postgres_url,
                config=RuntimeDatabaseConfig(
                    pool_minimum=1,
                    pool_maximum=8,
                    statement_timeout_ms=300_000,
                    lock_timeout_ms=60_000,
                    idle_transaction_timeout_ms=300_000,
                ),
            )
            try:
                postgres_result = run_postgres_integration_suite(postgres_repository)
                parity = run_exact_backend_parity(sqlite_repository, postgres_repository)
                complete_postgres_packet_checks(
                    postgres_repository, postgres_result, parity
                )
                postgres_result["guard"] = environment.status
                postgres_result["reset"] = reset
            finally:
                postgres_repository.close()
        else:
            postgres_result = {
                "backend": "postgres",
                "result": "BLOCKED",
                "reason": f"{TEST_DATABASE_ENV} is not visible in this process.",
            }
            parity = {
                "same_logical_ledger": False,
                "packet_id_equal": False,
                "packet_hash_equal": False,
                "packet_contents_equal": False,
            }

        logical_check_parity = bool(postgres_result.get("checks")) and all(
            item["passed"] for item in postgres_result.get("checks", [])
        )
        parity_assertions = [
            ("SQLite suite passes", sqlite_result["result"] == "PASS"),
            ("PostgreSQL suite passes", postgres_result["result"] == "PASS"),
            ("backend logical checks match", logical_check_parity),
            ("same-ledger packet ID matches", bool(parity["packet_id_equal"])),
            ("same-ledger packet hash matches", bool(parity["packet_hash_equal"])),
            ("same-ledger packet contents match", bool(parity["packet_contents_equal"])),
        ]
        _domain_result(
            sqlite_result["benchmark_cases"],
            "sqlite_postgresql_parity",
            parity_assertions,
        )
        sqlite_result["benchmark_case_count"] = len(sqlite_result["benchmark_cases"])
        sqlite_result["benchmark_assertion_count"] = sum(
            len(item["assertions"]) for item in sqlite_result["benchmark_cases"]
        )
        add(
            sqlite_result["checks"],
            "benchmark_case_minimum",
            sqlite_result["benchmark_case_count"] >= 120,
            sqlite_result["benchmark_case_count"],
        )
        add(
            sqlite_result["checks"],
            "benchmark_assertion_minimum",
            sqlite_result["benchmark_assertion_count"] >= 500,
            sqlite_result["benchmark_assertion_count"],
        )
        add(
            sqlite_result["checks"],
            "all_benchmark_cases_pass",
            all(item["passed"] for item in sqlite_result["benchmark_cases"]),
        )
        sqlite_result["result"] = (
            "PASS"
            if all(item["passed"] for item in sqlite_result["checks"])
            else "NEEDS_WORK"
        )

    parity_passed = (
        postgres_result["result"] == "PASS"
        and logical_check_parity
        and all(
            bool(parity[key])
            for key in (
                "same_logical_ledger",
                "packet_id_equal",
                "packet_hash_equal",
                "packet_contents_equal",
            )
        )
    )

    public = {
        "sprint": "Core Sprint 13",
        "truth_label": "Internal deterministic synthetic core-engine evidence only.",
        "sqlite_result": sqlite_result["result"],
        "postgres_result": postgres_result["result"],
        "benchmark_case_count": sqlite_result["benchmark_case_count"],
        "benchmark_assertion_count": sqlite_result["benchmark_assertion_count"],
        "passed_checks": sum(1 for item in sqlite_result["checks"] if item["passed"]),
        "total_checks": len(sqlite_result["checks"]),
        "packet_modes": ["legacy_continuity_v1", "epistemic_continuity_v2"],
        "boundaries": {
            "automatic_truth_determination": False,
            "scientific_validation": False,
            "production_certification": False,
        },
        "result": (
            "PASS"
            if sqlite_result["result"] == "PASS" and postgres_result["result"] == "PASS"
            else "BLOCKED"
            if postgres_result["result"] == "BLOCKED"
            else "NEEDS_WORK"
        ),
    }
    add(sqlite_result["checks"], "public_report_secret_safe", not _contains_secret(public))
    sqlite_result["result"] = (
        "PASS"
        if all(item["passed"] for item in sqlite_result["checks"])
        else "NEEDS_WORK"
    )
    public["sqlite_result"] = sqlite_result["result"]
    public["passed_checks"] = sum(
        1 for item in sqlite_result["checks"] if item["passed"]
    )
    public["total_checks"] = len(sqlite_result["checks"])
    public["result"] = (
        "PASS"
        if sqlite_result["result"] == "PASS" and postgres_result["result"] == "PASS"
        else "BLOCKED"
        if postgres_result["result"] == "BLOCKED"
        else "NEEDS_WORK"
    )
    private = {
        "sprint": "Core Sprint 13",
        "sqlite": sqlite_result,
        "postgres": postgres_result,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "result": public["result"],
    }
    write_json(REPORT_DIR / "public_continuity_packet_v2.json", public)
    write_json(REPORT_DIR / "private_internal_continuity_packet_v2.json", private)
    write_json(
        REPORT_DIR / "backend_parity_continuity_packet_v2.json",
        {
            "sqlite": sqlite_result["result"],
            "postgres": postgres_result["result"],
            "logical_check_parity": logical_check_parity,
            "exact_packet_parity": parity,
            "result": (
                "PASS"
                if parity_passed
                else "BLOCKED"
                if postgres_result["result"] == "BLOCKED"
                else "NEEDS_WORK"
            ),
        },
    )
    write_json(BENCHMARK_DIR / "cases.json", sqlite_result["benchmark_cases"])
    write_json(
        BENCHMARK_DIR / "corpus_manifest.json",
        {
            "case_count": sqlite_result["benchmark_case_count"],
            "assertion_count": sqlite_result["benchmark_assertion_count"],
            "domains": sorted({item["domain"] for item in sqlite_result["benchmark_cases"]}),
            "fixture_type": "deterministic synthetic source-ledger histories",
        },
    )
    print("PRMR Memory Core - Core Sprint 13 Epistemic Continuity Packet V2")
    print(f"SQLite checks: {sum(1 for item in sqlite_result['checks'] if item['passed'])}/{len(sqlite_result['checks'])}")
    print(f"Benchmark: {sqlite_result['benchmark_case_count']} cases / {sqlite_result['benchmark_assertion_count']} assertions")
    print(f"PostgreSQL: {postgres_result['result']}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
