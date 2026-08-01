"""Bounded RC1 operational observations, not production benchmarks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.job_handlers import MemoryJobHandlerRegistry
from prmr.core.job_queue import MemoryJobQueue
from prmr.core.job_worker import MemoryJobWorker
from prmr.core.runtime_migrations import get_migration_status
from prmr.release.diagnostics import collect_diagnostics
from prmr.release.self_test import run_release_integrity, run_release_self_test
from prmr.runtime_bootstrap import bootstrap_runtime
from prmr.runtime_config import example_configuration, load_runtime_configuration
from prmr.runtime_health import runtime_readiness

REPORT = ROOT / "reports/core_release_candidate/performance_smoke.json"


def measure(operation: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    value = operation()
    return value, round((time.perf_counter() - started) * 1000, 3)


def main() -> int:
    with TemporaryDirectory(prefix="prmr-rc1-benchmark-") as temporary:
        root = Path(temporary)
        config_path = root / "prmr.toml"
        config_path.write_text(example_configuration("sqlite_local").replace("data/prmr-memory-core.sqlite3", (root / "core.sqlite3").as_posix()), encoding="utf-8")
        config, load_ms = measure(lambda: load_runtime_configuration(config_path=config_path))
        bootstrap, init_ms = measure(lambda: bootstrap_runtime(config, migrate=True))
        context = bootstrap.context
        try:
            readiness, readiness_ms = measure(lambda: runtime_readiness(context).to_dict())
            migration_rows, migration_ms = measure(lambda: get_migration_status(context.repository))
            self_test, self_test_ms = measure(lambda: run_release_self_test(context.repository, label="release_benchmark"))
            worker, worker_ms = measure(lambda: MemoryJobWorker(MemoryJobQueue(context.repository, initialize=False), MemoryJobHandlerRegistry(), worker_id="worker_release_benchmark").run_once())
            integrity, integrity_ms = measure(lambda: run_release_integrity(context.repository, mode="release-smoke"))
            diagnostics, diagnostics_ms = measure(lambda: collect_diagnostics(context, root / "diagnostics.zip"))
        finally:
            context.close()
    timings = {
        "configuration_load_ms": load_ms,
        "sqlite_initialisation_ms": init_ms,
        "readiness_ms": readiness_ms,
        "migration_status_ms": migration_ms,
        "self_test_ms": self_test_ms,
        "worker_startup_ms": worker_ms,
        "small_v2_packet_included_in_self_test_ms": self_test_ms,
        "integrity_smoke_ms": integrity_ms,
        "diagnostics_generation_ms": diagnostics_ms,
    }
    checks = {
        "readiness": readiness["ready"],
        "migration_count": len(migration_rows) == 12,
        "self_test": self_test["result"] == "PASS",
        "worker_startup": worker["status"] == "idle",
        "integrity": integrity["result"] == "PASS",
        "diagnostics": diagnostics["status"] == "created",
    }
    passed = all(checks.values())
    payload = {
        "result": "PASS" if passed else "NEEDS_WORK",
        "truth_label": "Bounded release observations; not production benchmarks.",
        "machine_context": {"python": platform.python_version(), "os": platform.platform(), "processor": platform.processor() or "not_reported"},
        "fixture": "isolated synthetic RC1 lifecycle",
        "timings": timings,
        "checks": checks,
        "postgres_initialisation": "NOT_MEASURED_IN_BOUNDED_LOCAL_SMOKE" if not os.getenv("PRMR_POSTGRES_TEST_DATABASE_URL") else "MEASURED_BY_GUARDED_RELEASE_PROOF",
        "memory_content_recorded": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PRMR Memory Core - RC1 Performance Smoke")
    for name, value in timings.items():
        print(f"{name}: {value:.3f}")
    print(f"Result: {payload['result']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
