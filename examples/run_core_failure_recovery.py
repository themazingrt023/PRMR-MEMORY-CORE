"""Report Core Sprint 11 recovery evidence without overstating PostgreSQL proof."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.runtime_failure_injection import INJECTION_POINTS  # noqa: E402
from prmr.core.runtime_postgres_validation import TEST_DATABASE_ENV  # noqa: E402


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
FAILURE_REPORT = REPORT_DIR / "failure_recovery.json"


def main() -> int:
    durable_path = REPORT_DIR / "durable_jobs.json"
    durable = (
        json.loads(durable_path.read_text(encoding="utf-8"))
        if durable_path.exists()
        else {}
    )
    checks = {
        "sqlite_durable_runner_passed": durable.get("sqlite_result") == "PASS",
        "post_effect_crash_injected": _check(
            durable, "post_effect_completion_crash_injected"
        ),
        "lease_recovered_after_restart": _check(
            durable, "expired_lease_recovered_after_restart"
        ),
        "effect_replayed_without_duplicate": _check(
            durable, "post_effect_recovery_has_no_duplicate_service_call"
        ),
        "governance_restart_proof_retained": (
            ROOT / "reports/core_memory_governance/erasure_verification_memory_governance.json"
        ).exists(),
        "failure_injection_points_complete": len(INJECTION_POINTS) == 15,
    }
    postgres_available = bool(os.getenv(TEST_DATABASE_ENV))
    postgres_proofs = {
        "application_restart": "NOT_RUN",
        "database_connection_reset": "NOT_RUN",
        "serialization_failure": "NOT_RUN",
        "lock_timeout": "NOT_RUN",
        "eight_worker_concurrency": "NOT_RUN",
        "partial_consolidation": "NOT_RUN",
        "partial_governance": "NOT_RUN",
        "partial_export": "NOT_RUN",
    }
    local_pass = all(checks.values())
    result = (
        "NEEDS_WORK"
        if not local_pass
        else ("NEEDS_WORK" if postgres_available else "BLOCKED")
    )
    report = {
        "version": "core_sprint_11",
        "result": result,
        "local_failure_recovery": "PASS" if local_pass else "NEEDS_WORK",
        "checks": checks,
        "postgres_runtime_available": postgres_available,
        "postgres_proofs": postgres_proofs,
        "duplicate_effect_count_local_fixture": 0 if local_pass else None,
        "boundary": (
            "SQLite restart and idempotent effect recovery evidence does not "
            "prove PostgreSQL process concurrency or database outage recovery."
        ),
    }
    FAILURE_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 11 Failure Recovery")
    print(f"Local injected recovery: {report['local_failure_recovery']}")
    print("PostgreSQL failure recovery: NOT RUN")
    print(f"Result: {result}")
    return 1 if not local_pass else 0


def _check(report: dict[str, Any], name: str) -> bool:
    return any(
        item.get("name") == name and item.get("passed")
        for item in report.get("checks", [])
    )


if __name__ == "__main__":
    raise SystemExit(main())
