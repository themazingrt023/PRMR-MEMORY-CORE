"""Audit durable-job implementation and SQLite runtime evidence."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.runtime_models import MemoryJobStatus, MemoryJobType  # noqa: E402
from prmr.core.runtime_migrations import (  # noqa: E402
    apply_pending_migrations,
    get_migration_status,
    migration_registry,
)
from prmr.product.self_serve_repository_v093 import (  # noqa: E402
    SelfServeRepositoryV093,
)


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
AUDIT_REPORT = REPORT_DIR / "audit_durable_jobs.json"


def add(checks: list[dict[str, Any]], name: str, passed: bool) -> None:
    checks.append({"name": name, "passed": bool(passed)})


def main() -> int:
    durable_path = REPORT_DIR / "durable_jobs.json"
    durable = (
        json.loads(durable_path.read_text(encoding="utf-8"))
        if durable_path.exists()
        else {}
    )
    checks: list[dict[str, Any]] = []
    add(checks, "durable_report_exists", durable_path.exists())
    add(checks, "sqlite_checks_all_pass", durable.get("passed_checks") == durable.get("total_checks") == 34)
    add(checks, "sqlite_result_pass", durable.get("sqlite_result") == "PASS")
    add(checks, "overall_blocked_without_postgres", durable.get("result") == "BLOCKED")
    add(checks, "all_required_job_types_typed", len(MemoryJobType) == 15)
    add(checks, "all_required_job_statuses_typed", len(MemoryJobStatus) == 10)
    with TemporaryDirectory(prefix="prmr-runtime-migrations-") as temp_dir:
        repository = SelfServeRepositoryV093(Path(temp_dir) / "runtime.sqlite3")
        expected_migrations = [item.migration_id for item in migration_registry()]
        first_apply = apply_pending_migrations(repository)
        replay_apply = apply_pending_migrations(repository)
        applied_status = get_migration_status(repository)
    add(
        checks,
        "sqlite_full_migration_registry_applies",
        first_apply == expected_migrations and len(applied_status) == len(expected_migrations) == 11,
    )
    add(checks, "sqlite_migration_replay_is_idempotent", replay_apply == [])
    migration = (ROOT / "migrations/core_memory_runtime_v1_sqlite.sql").read_text(encoding="utf-8")
    for table_name in (
        "prmr_memory_jobs",
        "prmr_memory_job_attempts",
        "prmr_memory_job_events",
        "prmr_memory_job_dependencies",
        "prmr_memory_job_effects",
        "prmr_memory_job_schedules",
    ):
        add(checks, f"sqlite_table_{table_name}", table_name in migration)
    queue_source = (ROOT / "prmr/core/job_queue.py").read_text(encoding="utf-8")
    worker_source = (ROOT / "prmr/core/job_worker.py").read_text(encoding="utf-8")
    add(checks, "at_least_once_wording_present", "idempotent_effect_receipts" in json.dumps(durable))
    add(checks, "lease_ownership_checks_present", "_assert_lease" in queue_source)
    add(checks, "heartbeat_present", "def heartbeat" in queue_source)
    add(checks, "retry_wait_present", "RETRY_WAIT" in queue_source)
    add(checks, "dead_letter_present", "DEAD_LETTER" in queue_source)
    add(checks, "cancellation_present", "request_cancellation" in queue_source)
    add(checks, "dependency_gate_present", "prmr_memory_job_dependencies" in migration)
    add(checks, "scheduler_module_present", (ROOT / "prmr/core/job_scheduler.py").exists())
    add(checks, "effect_recovery_present", "existing_effect" in worker_source)
    add(checks, "failure_injection_test_only", "enabled_for_tests" in (ROOT / "prmr/core/runtime_failure_injection.py").read_text(encoding="utf-8"))
    public_path = REPORT_DIR / "public_runtime_hardening.json"
    public_text = public_path.read_text(encoding="utf-8") if public_path.exists() else ""
    add(checks, "public_report_exists", public_path.exists())
    add(checks, "public_report_has_no_database_url", not bool(re.search(r"postgres(?:ql)?://", public_text, re.I)))
    add(checks, "public_report_has_no_raw_key", not bool(re.search(r"prmr_(?:live|alpha)_[A-Za-z0-9_-]+", public_text)))
    add(checks, "public_report_has_no_raw_lease_token", "lease_token" not in public_text)
    failed = [item for item in checks if not item["passed"]]
    result = "NEEDS_WORK" if failed else "BLOCKED"
    report = {
        "version": "core_sprint_11",
        "result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "sqlite_durable_jobs": durable.get("sqlite_result"),
        "postgres_runtime": durable.get("postgres_status"),
    }
    AUDIT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 11 Durable Jobs Audit")
    print(f"Passed checks: {report['passed_checks']}/{report['total_checks']}")
    print(f"SQLite durable jobs: {report['sqlite_durable_jobs']}")
    print(f"Result: {result}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
