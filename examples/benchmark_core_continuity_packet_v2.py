"""Internal performance observations for Epistemic Continuity Packet V2."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.continuity_v2_comparison import compare_packet_payloads
from prmr.core.continuity_v2_fixtures import ContinuityV2FixtureBuilder, v2_fixture_scope
from prmr.core.continuity_v2_policy import ContinuityPacketV2Policy
from prmr.core.continuity_v2_integrity import verify_packet_v2_integrity
from prmr.core.memory_consolidation_engine import MemoryConsolidationEngine
from prmr.core.memory_dynamics_engine import MemoryDynamicsEngine
from prmr.core.memory_ledger_models import MemoryTemporalBoundary
from prmr.core.runtime_migrations import apply_pending_migrations
from prmr.core.source_models import AuthenticatedScope
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093

from examples.run_core_continuity_packet_v2 import append_legacy_events, legacy_event


REPORT = ROOT / "reports" / "core_continuity_packet_v2" / "benchmark_continuity_packet_v2.json"
BOUNDARY = MemoryTemporalBoundary(
    valid_at="2026-08-02T12:00:00Z", known_at="2099-01-01T00:00:00Z"
)


def timed(call: Callable[[], Any], repetitions: int = 3) -> tuple[Any, dict[str, float]]:
    samples: list[float] = []
    result: Any = None
    for _ in range(repetitions):
        started = time.perf_counter()
        result = call()
        samples.append((time.perf_counter() - started) * 1000.0)
    ordered = sorted(samples)
    p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return result, {
        "cold_ms": round(samples[0], 3),
        "median_ms": round(median(samples), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "samples_ms": [round(value, 3) for value in samples],
    }


def events(scope: AuthenticatedScope, count: int) -> list[dict[str, Any]]:
    result = []
    for index in range(count):
        day = 1 + (index % 28)
        hour = index % 24
        event_type = f"memory.signal_{index % 17}"
        status = "explicit" if index % 11 else "inferred" if index % 5 else "unknown"
        result.append(
            legacy_event(
                scope,
                f"evt_s13_perf_{count}_{index:05d}",
                event_type,
                f"Synthetic V2 performance event {index}.",
                f"2026-07-{day:02d}T{hour:02d}:00:00Z",
                epistemic_status=status,
                state_role="observation",
            )
        )
    return result


def benchmark_size(count: int, root: Path) -> dict[str, Any]:
    repository = SelfServeRepositoryV093(root / f"v2_{count}.sqlite")
    apply_pending_migrations(repository)
    scope = AuthenticatedScope(
        f"client_s13_perf_{count}", f"vault_s13_perf_{count}", "default"
    )
    append_legacy_events(repository, scope, events(scope, count))
    service = ContinuityPacketV2Service(repository)
    policy = replace(
        ContinuityPacketV2Policy(),
        maximum_packet_items=max(500, count + 50),
    )
    full, full_timing = timed(
        lambda: service.generate_packet_v2(
            scope,
            temporal_boundary=BOUNDARY,
            persist=False,
            policy_override=policy,
        )
    )
    _, canonical_timing = timed(
        lambda: service.generate_packet_v2(
            scope,
            temporal_boundary=BOUNDARY,
            signal_identity_mode="canonical_signal_v1",
            persist=False,
            policy_override=replace(policy, signal_identity_mode="canonical_signal_v1"),
        ),
        repetitions=2,
    )
    _, integrity_timing = timed(
        lambda: verify_packet_v2_integrity(scope, full.to_dict()),
        repetitions=3,
    )

    started = time.perf_counter()
    v1_packet = MemoryDynamicsEngine(repository).build_continuity_packet(
        scope,
        temporal_boundary=BOUNDARY,
        persist_dynamics=False,
    )
    v1_ms = (time.perf_counter() - started) * 1000.0
    consolidation_started = time.perf_counter()
    consolidation = MemoryConsolidationEngine(repository).consolidate_memory(
        scope,
        subject_scope=None,
        temporal_boundary=BOUNDARY,
    )
    consolidation_ms = (time.perf_counter() - consolidation_started) * 1000.0
    accelerated_started = time.perf_counter()
    accelerated = service.generate_verified_accelerated_packet_v2(
        scope,
        str(consolidation.checkpoint_id),
        persist=False,
        policy_override=policy,
    )
    accelerated_ms = (time.perf_counter() - accelerated_started) * 1000.0
    accelerated_packet = accelerated["packet"]
    ratio = accelerated_ms / consolidation_ms if consolidation_ms else None
    return {
        "event_count": count,
        "full_v2": full_timing,
        "canonical_v2": canonical_timing,
        "integrity": integrity_timing,
        "legacy_v1_packet_ms": round(v1_ms, 3),
        "sprint8_consolidation_ms": round(consolidation_ms, 3),
        "verified_accelerated_v2_ms": round(accelerated_ms, 3),
        "v2_to_sprint8_accelerated_ratio": round(ratio, 3) if ratio is not None else None,
        "within_two_times_sprint8_path": bool(ratio is not None and ratio <= 2.0),
        "acceleration_used": bool(accelerated.get("acceleration_used")),
        "fallback_reason": accelerated.get("fallback_reason"),
        "exact_equivalence": (
            full.packet_id == accelerated_packet.packet_id
            and full.packet_hash == accelerated_packet.packet_hash
            and full.to_dict() == accelerated_packet.to_dict()
        ),
        "legacy_packet_revision": v1_packet.get("algorithm_revision"),
        "packet_item_count": (
            len(full.asserted_information)
            + len(full.derived_information)
            + len(full.tentative_information)
            + len(full.unknown_information)
        ),
    }


def specialized_workloads(root: Path) -> dict[str, Any]:
    """Measure real entity, relationship, conflict, and comparison projections."""

    repository = SelfServeRepositoryV093(root / "v2_specialized.sqlite")
    apply_pending_migrations(repository)
    builder = ContinuityV2FixtureBuilder(
        repository, v2_fixture_scope("performance_specialized")
    )
    entity_ids = [
        builder.create_entity(
            f"entity_{index}",
            stable_id=f"synthetic_entity_{index:02d}",
            entity_type="software_system",
            label=f"Synthetic Entity {index}",
        )
        for index in range(8)
    ]
    for index, entity_id in enumerate(entity_ids):
        builder.explicit_state(
            f"entity_event_{index}",
            event_type="status.updated",
            signal=f"Synthetic entity status {index}.",
            occurred_at=f"2026-07-{index + 1:02d}T09:00:00Z",
            state_key=f"entity.{index}.status",
            state_value="active",
            entity_id=entity_id,
        )
    for index in range(24):
        builder.create_relationship(
            f"relationship_{index}",
            subject_entity_id=entity_ids[index % len(entity_ids)],
            relationship_type="depends_on",
            object_entity_id=entity_ids[(index + 1) % len(entity_ids)],
            occurred_at=f"2026-07-{(index % 8) + 1:02d}T10:{index:02d}:00Z",
            inferred=index % 4 == 0,
            object_label=f"Synthetic Entity {(index + 1) % len(entity_ids)}",
        )
    for index in range(8):
        left = f"conflict_{index}_left"
        right = f"conflict_{index}_right"
        builder.explicit_state(
            left,
            event_type="status.updated",
            signal=f"Synthetic conflict {index} left.",
            occurred_at=f"2026-07-{index + 10:02d}T09:00:00Z",
            state_key=f"conflict.{index}.status",
            state_value="left",
        )
        builder.explicit_state(
            right,
            event_type="status.updated",
            signal=f"Synthetic conflict {index} right.",
            occurred_at=f"2026-07-{index + 10:02d}T09:01:00Z",
            state_key=f"conflict.{index}.status",
            state_value="right",
        )
        builder.declare_conflict(f"conflict_{index}", [left, right])
    service = ContinuityPacketV2Service(repository)
    base_packet, relationship_timing = timed(
        lambda: service.generate_packet_v2(
            builder.scope, temporal_boundary=BOUNDARY, persist=False
        ),
        repetitions=2,
    )
    entity_packet, entity_timing = timed(
        lambda: service.generate_packet_v2(
            builder.scope,
            {"entity_id": entity_ids[0]},
            BOUNDARY,
            persist=False,
        ),
        repetitions=2,
    )
    conflict_packet, conflict_timing = timed(
        lambda: service.generate_packet_v2(
            builder.scope, temporal_boundary=BOUNDARY, persist=False
        ),
        repetitions=2,
    )
    comparison, comparison_timing = timed(
        lambda: compare_packet_payloads(
            base_packet.to_dict(), conflict_packet.to_dict()
        ),
        repetitions=3,
    )
    return {
        "entity_packet": entity_timing,
        "relationship_heavy_packet": relationship_timing,
        "conflict_heavy_packet": conflict_timing,
        "packet_comparison": comparison_timing,
        "entity_count": len(entity_packet.entity_context),
        "relationship_count": sum(
            len(items) for items in base_packet.relationship_context.values()
        ),
        "conflict_count": len(conflict_packet.conflict_context),
        "comparison_hash_present": bool(comparison.comparison_hash),
    }


def main() -> int:
    started = time.perf_counter()
    with TemporaryDirectory(prefix="prmr-core-s13-benchmark-") as temporary:
        root = Path(temporary)
        results = [benchmark_size(count, root) for count in (100, 1_000, 10_000)]
        specialized = specialized_workloads(root)
    exact = all(item["exact_equivalence"] for item in results)
    limits = all(item["within_two_times_sprint8_path"] for item in results)
    result = "PASS" if exact and limits else "NEEDS_WORK"
    payload = {
        "sprint": "Core Sprint 13",
        "truth_label": "Internal synthetic performance observations on this machine.",
        "fixtures": results,
        "specialized_workloads": specialized,
        "exact_acceleration_equivalence": exact,
        "two_times_regression_gate": limits,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "result": result,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PRMR Memory Core - Core Sprint 13 Performance Benchmark")
    for item in results:
        print(
            f"{item['event_count']:>5} events: full {item['full_v2']['median_ms']:.3f} ms, "
            f"verified accelerated {item['verified_accelerated_v2_ms']:.3f} ms, "
            f"exact={item['exact_equivalence']}"
        )
    print(f"Two-times regression gate: {'PASS' if limits else 'FAIL'}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
