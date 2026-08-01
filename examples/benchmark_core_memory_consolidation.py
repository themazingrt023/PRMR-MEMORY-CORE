"""Local 10,000-event exact consolidation acceleration benchmark."""

from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.memory_consolidation_continuity_adapter import (
    MemoryConsolidationContinuityAdapter,
)
from prmr.core.memory_consolidation_engine import (
    MemoryConsolidationEngine,
    consolidation_query_key,
)
from prmr.core.memory_consolidation_fixtures import (
    consolidation_fixture_scope,
    synthetic_consolidation_events,
    write_fixture_events,
)
from prmr.core.memory_consolidation_query_adapter import (
    MemoryConsolidationQueryAdapter,
)
from prmr.core.memory_consolidation_store import MemoryConsolidationStore
from prmr.core.memory_ledger_models import MemoryTemporalBoundary
from prmr.core.memory_query_engine import MemoryQueryEngine
from prmr.core.memory_query_models import MemoryQueryRequest, MemoryQueryType
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT = ROOT / "reports/core_memory_consolidation/benchmark_memory_consolidation.json"
EVENT_COUNT = 10_000
BOUNDARY = MemoryTemporalBoundary(
    valid_at="2026-01-01T00:00:00Z",
    known_at="2026-01-01T00:00:00Z",
)
BENCHMARK_BOUNDARY = (
    "Local synthetic SQLite observation on this machine and process only. "
    "This is not production-scale performance or external validation."
)


def timed(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = call()
    return result, round((time.perf_counter() - started) * 1000, 3)


def summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "iterations": len(values),
        "values_ms": values,
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "minimum_ms": round(min(values), 3),
        "maximum_ms": round(max(values), 3),
    }


def request(query_type: str, **kwargs: Any) -> MemoryQueryRequest:
    return MemoryQueryRequest(
        query_type=query_type,
        valid_at=BOUNDARY.valid_at,
        known_at=BOUNDARY.known_at,
        include_evidence=False,
        include_explanation=False,
        **kwargs,
    )


def main() -> int:
    with TemporaryDirectory(prefix="prmr-consolidation-benchmark-") as temp:
        database = Path(temp) / "benchmark.sqlite"
        repository = SelfServeRepositoryV093(database)
        scope = consolidation_fixture_scope("benchmark_10000")
        write_fixture_events(
            repository,
            scope,
            synthetic_consolidation_events(
                EVENT_COUNT,
                prefix="benchmark",
                signal_count=31,
            ),
        )
        storage_before = database.stat().st_size
        canonical = MemoryQueryEngine(repository)
        current_request = request(MemoryQueryType.CURRENT_STATE.value)
        phase_request = request(
            MemoryQueryType.MEMORY_BY_PHASE.value,
            memory_phase_filter=("active",),
        )
        signal_request = request(
            MemoryQueryType.SIGNAL_HISTORY.value,
            signal_key="memory.signal_0",
        )
        recurrence_request = request(MemoryQueryType.RECURRENCE.value)
        packet_request = request(MemoryQueryType.CONTINUITY_PACKET.value)
        requests = [
            current_request,
            phase_request,
            signal_request,
            recurrence_request,
            packet_request,
        ]
        requests = [
            replace(
                item,
                application_reference=scope.application_reference,
                actor_reference=scope.actor_reference,
                workspace_reference=scope.workspace_reference,
                session_reference=scope.session_reference,
            )
            for item in requests
        ]
        (
            current_request,
            phase_request,
            signal_request,
            recurrence_request,
            packet_request,
        ) = requests

        cold_result, canonical_cold = timed(
            lambda: canonical.query_memory(scope, current_request)
        )
        canonical_warm: list[float] = []
        for _ in range(5):
            result, duration = timed(
                lambda: canonical.query_memory(scope, current_request)
            )
            if result.result_hash_sha256 != cold_result.result_hash_sha256:
                raise RuntimeError("Canonical current-state hash changed.")
            canonical_warm.append(duration)
        canonical_other: dict[str, dict[str, Any]] = {}
        canonical_results = {
            MemoryQueryType.CURRENT_STATE.value: cold_result
        }
        for item in requests[1:]:
            result, duration = timed(lambda item=item: canonical.query_memory(scope, item))
            canonical_results[item.query_type] = result
            canonical_other[item.query_type] = {
                "duration_ms": duration,
                "result_hash_sha256": result.result_hash_sha256,
            }

        engine = MemoryConsolidationEngine(repository)
        run, build_duration = timed(
            lambda: engine.consolidate_memory(
                scope,
                {},
                BOUNDARY,
                query_requests=[
                    replace(item, valid_at=None, known_at=None) for item in requests
                ],
                precomputed_query_results={
                    consolidation_query_key(item): canonical_results[item.query_type]
                    for item in requests
                },
            )
        )
        checkpoint, checkpoint_load_cold = timed(
            lambda: engine.get_checkpoint(scope, str(run.checkpoint_id))
        )
        checkpoint_load_warm = [
            timed(lambda: engine.get_checkpoint(scope, str(run.checkpoint_id)))[1]
            for _ in range(5)
        ]
        integrity, integrity_duration = timed(
            lambda: engine.verify_consolidation_integrity(
                scope, run.consolidation_run_id
            )
        )

        adapter = MemoryConsolidationQueryAdapter(repository)
        accelerated_cold_result, accelerated_cold = timed(
            lambda: adapter.query_memory(scope, current_request)
        )
        accelerated_warm: list[float] = []
        for _ in range(5):
            result, duration = timed(
                lambda: adapter.query_memory(scope, current_request)
            )
            if result.result.result_hash_sha256 != cold_result.result_hash_sha256:
                raise RuntimeError("Accelerated current-state hash changed.")
            accelerated_warm.append(duration)
        accelerated_other: dict[str, dict[str, Any]] = {}
        exact_other = True
        for item in requests[1:-1]:
            result, duration = timed(lambda item=item: adapter.query_memory(scope, item))
            expected = canonical_results[item.query_type]
            exact = (
                result.metadata.acceleration_used
                and result.result.result_hash_sha256
                == expected.result_hash_sha256
                and result.result.answer_payload == expected.answer_payload
                and result.result.epistemic_summary == expected.epistemic_summary
                and result.result.evidence_bundle_id == expected.evidence_bundle_id
                and result.result.explanation_id == expected.explanation_id
            )
            exact_other &= exact
            accelerated_other[item.query_type] = {
                "duration_ms": duration,
                "result_hash_sha256": result.result.result_hash_sha256,
                "exact": exact,
                "execution_path": result.metadata.execution_path,
            }
        accelerated_packet, packet_duration = timed(
            lambda: MemoryConsolidationContinuityAdapter(
                repository
            ).build_continuity_packet(
                scope,
                {},
                valid_at=BOUNDARY.valid_at,
                known_at=BOUNDARY.known_at,
            )
        )
        canonical_packet = canonical_results[
            MemoryQueryType.CONTINUITY_PACKET.value
        ].answer_payload["packet"]
        packet_exact = (
            accelerated_packet.metadata.acceleration_used
            and accelerated_packet.packet == canonical_packet
            and accelerated_packet.packet["packet_id"]
            == canonical_packet["packet_id"]
            and accelerated_packet.packet["provenance"][
                "deterministic_packet_hash"
            ]
            == canonical_packet["provenance"]["deterministic_packet_hash"]
        )

        current_exact = (
            accelerated_cold_result.metadata.acceleration_used
            and accelerated_cold_result.result.result_hash_sha256
            == cold_result.result_hash_sha256
            and accelerated_cold_result.result.answer_payload
            == cold_result.answer_payload
            and accelerated_cold_result.result.epistemic_summary
            == cold_result.epistemic_summary
            and accelerated_cold_result.result.evidence_bundle_id
            == cold_result.evidence_bundle_id
            and accelerated_cold_result.result.explanation_id
            == cold_result.explanation_id
        )
        canonical_stats = summary(canonical_warm)
        accelerated_stats = summary(accelerated_warm)
        speedup = round(
            canonical_stats["median_ms"] / accelerated_stats["median_ms"], 3
        )

        storage_after = database.stat().st_size

        # Delta timing uses a separate sub-limit fixture. The policy cap is
        # 10,000 events, so appending to the 10,000-event fixture would be an
        # invalid benchmark rather than an incremental proof.
        with TemporaryDirectory(prefix="prmr-consolidation-delta-benchmark-") as delta_temp:
            delta_repository = SelfServeRepositoryV093(
                Path(delta_temp) / "delta.sqlite"
            )
            delta_scope = consolidation_fixture_scope("benchmark_delta")
            write_fixture_events(
                delta_repository,
                delta_scope,
                synthetic_consolidation_events(
                    1_000, prefix="delta_base", signal_count=17
                ),
            )
            delta_engine = MemoryConsolidationEngine(delta_repository)
            delta_request = MemoryQueryRequest(
                query_type=MemoryQueryType.CURRENT_STATE.value,
                include_evidence=False,
                include_explanation=False,
            )
            delta_engine.consolidate_memory(
                delta_scope,
                {},
                BOUNDARY,
                query_requests=[delta_request],
            )
            write_fixture_events(
                delta_repository,
                delta_scope,
                synthetic_consolidation_events(
                    10,
                    prefix="delta_append",
                    start_index=1_000,
                    signal_count=10_000,
                ),
                append=True,
            )
            next_boundary = BOUNDARY
            incremental_run, checkpoint_plus_delta_duration = timed(
                lambda: delta_engine.consolidate_memory(
                    delta_scope,
                    {},
                    next_boundary,
                    query_requests=[delta_request],
                )
            )
            incremental_checkpoint = delta_engine.get_checkpoint(
                delta_scope, str(incremental_run.checkpoint_id)
            )
            deltas = MemoryConsolidationStore(delta_repository).list_deltas(
                delta_scope,
                target_checkpoint_id=incremental_checkpoint.memory_checkpoint_id,
            )

        hard_gate = (
            current_exact
            and exact_other
            and packet_exact
            and integrity.verified
            and speedup >= 2.0
        )
        result = "PASS" if hard_gate else "NEEDS WORK"
        report = {
            "version": "core_sprint_8",
            "result": result,
            "fixture": {
                "event_count": EVENT_COUNT,
                "signal_count": 31,
                "storage": "temporary_durable_sqlite",
                "synthetic": True,
            },
            "correctness": {
                "current_state_exact": current_exact,
                "other_query_types_exact": exact_other,
                "continuity_packet_exact": packet_exact,
                "checkpoint_integrity_verified": integrity.verified,
                "canonical_result_hash": cold_result.result_hash_sha256,
                "accelerated_result_hash": (
                    accelerated_cold_result.result.result_hash_sha256
                ),
                "canonical_packet_id": canonical_packet["packet_id"],
                "accelerated_packet_id": accelerated_packet.packet["packet_id"],
                "canonical_packet_hash": canonical_packet["provenance"][
                    "deterministic_packet_hash"
                ],
                "accelerated_packet_hash": accelerated_packet.packet[
                    "provenance"
                ]["deterministic_packet_hash"],
            },
            "timings": {
                "canonical_current_state_cold_ms": canonical_cold,
                "canonical_current_state_warm": canonical_stats,
                "accelerated_current_state_cold_ms": accelerated_cold,
                "accelerated_current_state_warm": accelerated_stats,
                "current_state_warm_median_speedup_ratio": speedup,
                "consolidation_full_build_ms": build_duration,
                "checkpoint_load_cold_ms": checkpoint_load_cold,
                "checkpoint_load_warm": summary(checkpoint_load_warm),
                "checkpoint_plus_delta_ms": checkpoint_plus_delta_duration,
                "integrity_verification_ms": integrity_duration,
                "canonical_queries": canonical_other,
                "accelerated_queries": accelerated_other,
                "canonical_continuity_packet_ms": canonical_other[
                    MemoryQueryType.CONTINUITY_PACKET.value
                ]["duration_ms"],
                "accelerated_continuity_packet_ms": packet_duration,
                "entity_state": "not_measured_fixture_has_no_canonical_entities",
                "relationship_state": (
                    "not_measured_fixture_has_no_canonical_relationships"
                ),
            },
            "incremental": {
                "delta_created": bool(deltas),
                "delta_event_count": len(deltas[0].events_added) if deltas else 0,
                "created_item_count": incremental_run.created_item_count,
                "reused_item_count": incremental_run.reused_item_count,
            },
            "resources": {
                "storage_before_bytes": storage_before,
                "storage_after_bytes": storage_after,
                "storage_growth_bytes": storage_after - storage_before,
                "peak_memory": "not_measured_to_avoid_distorting_query_timings",
            },
            "gates": {
                "minimum_speedup_ratio": 2.0,
                "target_speedup_ratio": 3.0,
                "preferred_accelerated_median_ms": 6000.0,
                "minimum_speedup_passed": speedup >= 2.0,
                "target_speedup_passed": speedup >= 3.0,
                "preferred_latency_passed": (
                    accelerated_stats["median_ms"] < 6000.0
                ),
            },
            "postgres_validation": (
                "not_run_no_database_url"
                if not os.environ.get("DATABASE_URL")
                else "database_url_present_not_executed_by_local_benchmark"
            ),
            "boundary": BENCHMARK_BOUNDARY,
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("PRMR Memory Core - Core Sprint 8 Benchmark")
        print(f"Events: {EVENT_COUNT}")
        print(
            "Canonical current-state warm median: "
            f"{canonical_stats['median_ms']} ms"
        )
        print(
            "Accelerated current-state warm median: "
            f"{accelerated_stats['median_ms']} ms"
        )
        print(f"Speedup: {speedup}x")
        print(f"Exact current-state result: {current_exact}")
        print(f"Exact continuity packet: {packet_exact}")
        print(f"Result: {result}")
        return 0 if hard_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
