"""Honest bounded benchmark for Core Sprint 10 dependency planning."""

from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.memory_governance_models import GovernanceActor
from prmr.core.memory_governance_planner import MemoryGovernancePlanner
from prmr.core.source_ledger import SourceLedger
from prmr.core.source_models import AuthenticatedScope, SourceInput
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093


REPORT = ROOT / "reports" / "core_memory_governance" / "benchmark_memory_governance.json"


def main() -> int:
    source_count = 100
    graph_timings: list[float] = []
    with TemporaryDirectory(prefix="prmr-governance-benchmark-") as temporary:
        repository = SelfServeRepositoryV093(Path(temporary) / "benchmark.sqlite")
        scoped = AuthenticatedScope("client_gov_benchmark", "vault_gov_benchmark", "memory")
        ledger = SourceLedger(repository)
        ingest_started = time.perf_counter()
        for index in range(source_count):
            ledger.ingest_source(
                scoped,
                SourceInput(
                    "json",
                    {
                        "event_type": "benchmark.updated",
                        "signal": f"Synthetic benchmark signal {index}.",
                        "occurred_at": "2026-07-22T00:00:00Z",
                    },
                    actor_reference=f"actor_{index % 10}",
                    workspace_reference=f"workspace_{index % 5}",
                    application_reference=f"application_{index % 3}",
                    idempotency_key=f"governance-benchmark:{index}",
                ),
            )
        ingest_ms = (time.perf_counter() - ingest_started) * 1000
        planner = MemoryGovernancePlanner(repository)
        request = planner.create_request(
            scoped,
            action_type="erase_tenant_memory",
            target_type="tenant_memory_boundary",
            target_reference="::".join(scoped.memory_boundary()),
            actor=GovernanceActor("test_runner", "benchmark"),
            reason="Bounded synthetic planning benchmark.",
            idempotency_key="benchmark-plan",
            governance_policy_id="full_tenant_erasure_v1",
            requested_at="2026-07-22T00:00:00Z",
        )
        graph = None
        for iteration in range(3):
            started = time.perf_counter()
            graph = planner.graphs.build(
                scoped,
                request,
                generated_at="2026-07-22T00:00:00Z",
                persist=iteration == 0,
            )
            graph_timings.append((time.perf_counter() - started) * 1000)
        plan_started = time.perf_counter()
        plan = planner.plan(
            scoped,
            request.governance_request_id,
            generated_at="2026-07-22T00:00:00Z",
        )
        plan_ms = (time.perf_counter() - plan_started) * 1000

    report = {
        "version": "core_sprint_10",
        "result": "COMPLETED",
        "dataset": {
            "synthetic_sources": source_count,
            "discovered_nodes": len(graph.discovered_nodes) if graph else 0,
            "discovered_edges": len(graph.discovered_edges) if graph else 0,
            "planned_objects": sum(plan.estimated_counts_by_type.values()),
        },
        "timings_ms": {
            "source_ingest_total": round(ingest_ms, 2),
            "dependency_graph_runs": [round(value, 2) for value in graph_timings],
            "dependency_graph_median": round(statistics.median(graph_timings), 2),
            "dry_run_plan": round(plan_ms, 2),
        },
        "claims": {
            "production_scale_validated": False,
            "postgres_exercised": False,
            "concurrent_multi_process_execution_validated": False,
        },
        "postgres": (
            "NOT_RUN_DATABASE_URL_PRESENT"
            if os.getenv("DATABASE_URL")
            else "NOT_RUN_DATABASE_URL_UNAVAILABLE"
        ),
        "boundary": (
            "This is a bounded local SQLite planning benchmark over synthetic data. "
            "It is not a production throughput, latency, or scale claim."
        ),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PRMR Memory Core - Core Sprint 10 Benchmark")
    print(f"Synthetic sources: {source_count}")
    print(f"Discovered nodes: {report['dataset']['discovered_nodes']}")
    print(f"Dependency graph median: {report['timings_ms']['dependency_graph_median']} ms")
    print(f"Dry-run plan: {report['timings_ms']['dry_run_plan']} ms")
    print("Result: COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
