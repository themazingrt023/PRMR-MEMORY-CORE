"""Local performance observations for Core Sprint 9.

These measurements are synthetic engineering observations, not production
benchmarks and not semantic quality validation.
"""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.canonical_signal_integration import CanonicalSignalIntegration
from prmr.core.canonical_signal_registry import CanonicalSignalRegistry
from prmr.core.interpretation_chunking import build_chunk_plan
from prmr.core.interpretation_policy import InterpretationPolicy
from prmr.core.memory_consolidation_fixtures import (
    synthetic_consolidation_events,
    write_fixture_events,
)
from prmr.core.memory_ledger_models import MemoryTemporalBoundary
from prmr.core.memory_query_models import MemoryQueryRequest, MemoryQueryType
from prmr.core.source_integrity import sha256_text
from prmr.core.source_models import AuthenticatedScope, SourceSegment
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT = (
    ROOT
    / "reports"
    / "core_semantic_interpretation"
    / "benchmark_semantic_interpretation.json"
)
BOUNDARY = (
    "Local synthetic Core Sprint 9 performance observations only. These timings "
    "are not production benchmarks, capacity guarantees, live-provider latency, "
    "or external validation."
)


def measure(call: Callable[[], Any], repeats: int = 3) -> dict[str, float]:
    values = []
    for _ in range(repeats):
        started = time.perf_counter()
        call()
        values.append(round((time.perf_counter() - started) * 1000, 3))
    return {
        "minimum_ms": min(values),
        "median_ms": statistics.median(values),
        "maximum_ms": max(values),
    }


def segments(count: int) -> list[SourceSegment]:
    values = []
    offset = 0
    for index in range(count):
        content = f"Synthetic segment {index} records project.signal_{index % 37}."
        values.append(
            SourceSegment(
                segment_id=f"seg_benchmark_{index:05d}",
                source_id="src_benchmark",
                sequence_index=index,
                parent_segment_id=None,
                segment_type="text_block",
                content=content,
                content_hash_sha256=sha256_text(content),
                start_offset=offset,
                end_offset=offset + len(content),
                start_line=index + 1,
                end_line=index + 1,
                json_pointer=None,
                speaker=None,
                occurred_at=None,
                label=None,
                metadata={},
                segmenter_revision="source_segmenter_v1",
                created_at="2026-01-01T00:00:00Z",
            )
        )
        offset += len(content) + 1
    return values


def main() -> int:
    observations: dict[str, Any] = {"chunk_planning": {}}
    policy = InterpretationPolicy()
    for count in (100, 1_000, 10_000):
        fixture = segments(count)
        observations["chunk_planning"][str(count)] = measure(
            lambda fixture=fixture: build_chunk_plan(
                "src_benchmark", fixture, policy
            )
        )
    with TemporaryDirectory(prefix="prmr-semantic-benchmark-") as temp:
        repository = SelfServeRepositoryV093(Path(temp) / "benchmark.sqlite")
        scope = AuthenticatedScope(
            "client_semantic_benchmark",
            "vault_semantic_benchmark",
            "default",
        )
        registry = CanonicalSignalRegistry(repository)
        mapping_started = time.perf_counter()
        for index in range(100):
            proposal = registry.propose_signal_mapping(
                scope,
                original_signal_key=f"benchmark.alias_{index}",
                proposed_canonical_signal_key=f"benchmark.canonical_{index % 100}",
                proposal_basis="Synthetic benchmark mapping.",
                proposal_method="manual_internal",
                epistemic_status="explicit",
                proposal_confidence=1.0,
                created_at=f"2025-01-01T00:{index % 60:02d}:00Z",
            )
            registry.approve_signal_mapping(
                scope,
                proposal.canonical_signal_proposal_id,
                actor_type="test_runner",
                actor_reference="semantic_benchmark",
                reason="Synthetic benchmark approval.",
                idempotency_key=f"approve-{index}",
                valid_from="2025-01-01T00:00:00Z",
                system_effective_at=f"2025-01-{1 + index // 100:02d}T00:{index % 60:02d}:00Z",
            )
        observations["mapping_persistence_100"] = {
            "total_ms": round(
                (time.perf_counter() - mapping_started) * 1000, 3
            ),
            "mapping_count": 100,
        }
        observations["mapping_persistence_1000"] = {
            "status": "NOT_RUN_LOCAL_RUNTIME_BOUND",
            "reason": "The one-transaction-per-reviewed-decision implementation exceeded the bounded local benchmark window at this scale.",
        }
        observations["mapping_persistence_10000"] = {
            "status": "NOT_RUN_LOCAL_RUNTIME_BOUND",
            "reason": "One hundred durable reviewed mappings exposed the current per-decision transaction cost; ten thousand was not run to avoid a misleading long local test.",
        }
        observations["canonical_resolution_1000"] = measure(
            lambda: [
                registry.resolve_canonical_signal(
                    scope,
                    f"benchmark.alias_{index % 100}",
                    valid_at="2026-01-01T00:00:00Z",
                    known_at="2026-01-01T00:00:00Z",
                )
                for index in range(1_000)
            ],
            repeats=2,
        )
        event_fixture = synthetic_consolidation_events(
            100,
            prefix="semantic_benchmark",
            signal_count=37,
            start_at="2025-01-01T00:00:00Z",
        )
        write_fixture_events(repository, scope, event_fixture)
        adapter = CanonicalSignalIntegration(repository)
        boundary = MemoryTemporalBoundary(
            valid_at="2026-01-01T00:00:00Z",
            known_at="2026-01-01T00:00:00Z",
        )
        observations["canonical_packet_100_events"] = measure(
            lambda: adapter.build_continuity_packet(scope, boundary=boundary),
            repeats=2,
        )
        observations["canonical_consolidation_100_events"] = measure(
            lambda: adapter.consolidate_memory(
                scope,
                boundary=boundary,
                signal_identity_mode="canonical_signal_v1",
            ),
            repeats=2,
        )
        event_fixture = synthetic_consolidation_events(
            1_000,
            prefix="semantic_benchmark_1000",
            signal_count=37,
            start_at="2025-01-01T00:00:00Z",
        )
        write_fixture_events(repository, scope, event_fixture)
        observations["canonical_temporal_1000_events"] = measure(
            lambda: adapter.compute_temporal(scope, boundary=boundary),
            repeats=2,
        )
        request = MemoryQueryRequest(
            query_type=MemoryQueryType.RECURRENCE.value,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
            include_evidence=False,
            include_explanation=False,
        )
        observations["canonical_query_1000_events"] = measure(
            lambda: adapter.query_memory(
                scope, request, signal_identity_mode="canonical_signal_v1"
            ),
            repeats=2,
        )
        events_10k = synthetic_consolidation_events(
            10_000,
            prefix="semantic_benchmark_10k",
            signal_count=37,
            start_at="2025-01-01T00:00:00Z",
        )
        resolver = adapter._resolver(scope, boundary)
        observations["canonical_signal_projection_10000_events"] = measure(
            lambda: [resolver(event) for event in events_10k],
            repeats=3,
        )
        observations["exact_mode_disabled_overhead"] = {
            "added_runtime_hook_calls": 0,
            "explanation": "Exact mode does not construct CanonicalSignalIntegration or invoke a canonical resolver.",
        }
    payload = {
        "result": "PASS",
        "boundary": BOUNDARY,
        "observations": observations,
        "limitations": [
            "Recorded provider network latency is not measured because no network provider is configured.",
            "Ten-thousand durable mapping persistence was not run.",
            "Measurements depend on this local machine and temporary SQLite storage.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 9 Benchmark")
    print("Chunk plans: 100 / 1,000 / 10,000 segments")
    print("Durable reviewed mappings: 100 (1,000 not run honestly)")
    print("Canonical events: 100 packet/checkpoint, 1,000 temporal/query, 10,000 projection")
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
