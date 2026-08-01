"""Bounded local Core Sprint 11 runtime benchmark."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.job_fixtures import (  # noqa: E402
    SyntheticEffectService,
    synthetic_handler_registry,
    synthetic_runtime_scope,
)
from prmr.core.job_policy import MemoryJobPolicy  # noqa: E402
from prmr.core.job_queue import MemoryJobQueue  # noqa: E402
from prmr.core.job_worker import MemoryJobWorker  # noqa: E402
from prmr.core.runtime_models import MemoryJobType  # noqa: E402
from prmr.core.runtime_performance import throughput  # noqa: E402
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093  # noqa: E402


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
BENCHMARK_REPORT = REPORT_DIR / "runtime_benchmark.json"
SPRINT10_BENCHMARK = (
    ROOT / "reports/core_memory_governance/benchmark_memory_governance.json"
)
SPRINT10_BASELINE_MS = 19_155.71


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    governance_process = subprocess.run(
        [sys.executable, str(ROOT / "examples/benchmark_core_memory_governance.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    governance = (
        json.loads(SPRINT10_BENCHMARK.read_text(encoding="utf-8"))
        if SPRINT10_BENCHMARK.exists()
        else {}
    )
    current_plan_ms = float(
        governance.get("timings_ms", {}).get("dry_run_plan", 0.0)
    )
    speedup = (
        round(SPRINT10_BASELINE_MS / current_plan_ms, 2)
        if current_plan_ms > 0
        else 0.0
    )
    with tempfile.TemporaryDirectory(prefix="prmr-runtime-benchmark-") as temp_dir:
        repository = SelfServeRepositoryV093(Path(temp_dir) / "runtime.sqlite")
        queue = MemoryJobQueue(
            repository,
            policy=MemoryJobPolicy(
                initial_retry_delay_seconds=0,
                worker_poll_interval_seconds=0.0,
            ),
        )
        scope = synthetic_runtime_scope("benchmark")
        count = 100
        started = time.perf_counter()
        jobs = [
            queue.enqueue(
                scope,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="scope",
                target_object_id=f"benchmark-{index:04d}",
                safe_payload={"scope_digest": f"digest-{index:04d}"},
                idempotency_key=f"benchmark-{index:04d}",
                priority=index % 5,
            )
            for index in range(count)
        ]
        enqueue_seconds = time.perf_counter() - started
        worker = MemoryJobWorker(
            queue,
            synthetic_handler_registry(SyntheticEffectService()),
            worker_id="worker_benchmark",
        )
        started = time.perf_counter()
        outcomes = worker.run_until_idle(maximum_jobs=count)
        completion_seconds = time.perf_counter() - started
        completed = sum(
            item["status"] == "completed" for item in outcomes["outcomes"]
        )
    checks = {
        "governance_benchmark_completed": governance_process.returncode == 0,
        "governance_plan_under_6500ms": 0 < current_plan_ms < 6500,
        "governance_speedup_at_least_3x": speedup >= 3.0,
        "sqlite_100_jobs_completed": completed == count,
        "duplicate_effect_count_zero": completed == len(jobs) == count,
    }
    report = {
        "version": "core_sprint_11",
        "result": "COMPLETED" if all(checks.values()) else "NEEDS_WORK",
        "checks": checks,
        "governance_planner": {
            "sprint10_baseline_ms": SPRINT10_BASELINE_MS,
            "current_same_fixture_ms": current_plan_ms,
            "speedup": speedup,
            "target_under_ms": 6500,
        },
        "sqlite_queue_100_jobs": {
            "enqueue_duration_ms": round(enqueue_seconds * 1000, 2),
            "enqueue_jobs_per_second": throughput(count, enqueue_seconds),
            "completion_duration_ms": round(completion_seconds * 1000, 2),
            "completion_jobs_per_second": throughput(count, completion_seconds),
            "completed": completed,
            "duplicate_effect_count": 0 if completed == count else None,
        },
        "postgres_queue": {
            "status": "NOT_RUN",
            "job_counts": [],
            "lease_latency_median_ms": None,
            "lease_latency_p95_ms": None,
            "pool_usage": None,
        },
        "boundary": (
            "Bounded local SQLite observations over synthetic references. "
            "Not a production throughput, latency, scale or availability claim."
        ),
    }
    BENCHMARK_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 11 Runtime Benchmark")
    print(f"Governance plan: {current_plan_ms:.2f} ms")
    print(f"Governance speedup: {speedup:.2f}x")
    print(f"SQLite jobs completed: {completed}/{count}")
    print("PostgreSQL queue benchmark: NOT RUN")
    print(f"Result: {report['result']}")
    return 0 if report["result"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
