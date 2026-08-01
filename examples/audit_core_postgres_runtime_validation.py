"""Audit Core Sprint 11 PostgreSQL evidence without inventing runtime proof."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.runtime_migrations import (  # noqa: E402
    expected_postgres_relations,
    migration_registry,
    validate_postgres_relation_order,
)
from prmr.core.runtime_models import RuntimeErrorCode  # noqa: E402
from prmr.core.runtime_postgres_matrix import PostgresRuntimeMatrix  # noqa: E402
from prmr.core.runtime_postgres_validation import (  # noqa: E402
    TEST_DATABASE_ENV,
    safe_postgres_exception_diagnostics,
    verify_postgres_test_environment,
)


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
AUDIT_REPORT = REPORT_DIR / "audit_postgres_runtime_validation.json"


def add(checks: list[dict[str, Any]], name: str, passed: bool) -> None:
    checks.append({"name": name, "passed": bool(passed)})


def main() -> int:
    checks: list[dict[str, Any]] = []
    required_modules = [
        "runtime_models.py",
        "runtime_database.py",
        "runtime_migrations.py",
        "runtime_postgres_validation.py",
        "runtime_repository_parity.py",
        "job_models.py",
        "job_policy.py",
        "job_store.py",
        "job_queue.py",
        "job_worker.py",
        "job_handlers.py",
        "job_scheduler.py",
        "job_recovery.py",
        "job_integrity.py",
        "job_fixtures.py",
        "runtime_integrity_sweep.py",
        "runtime_failure_injection.py",
        "runtime_performance.py",
        "runtime_postgres_matrix.py",
        "runtime_core_lifecycle.py",
    ]
    for name in required_modules:
        path = ROOT / "prmr" / "core" / name
        add(checks, f"module_{name}_exists", path.exists())
    registry = migration_registry()
    required_runtime_migrations = [
        f"core_{index:02d}_" for index in range(1, 12)
    ]
    add(
        checks,
        "migration_registry_covers_sprints_1_to_11",
        len(registry) >= 11
        and all(
            any(item.migration_id.startswith(prefix) for item in registry)
            for prefix in required_runtime_migrations
        ),
    )
    add(
        checks,
        "migration_dependencies_are_ordered",
        all(
            not item.dependencies
            or item.dependencies[-1]
            in [prior.migration_id for prior in registry[:index]]
            for index, item in enumerate(registry)
        ),
    )
    relation_order = validate_postgres_relation_order(registry)
    relation_map = expected_postgres_relations(registry)
    add(checks, "postgres_relation_order_is_valid", relation_order["verified"])
    add(
        checks,
        "postgres_registry_declares_complete_relation_set",
        relation_order["relation_count"]
        == len({item for values in relation_map.values() for item in values})
        and relation_order["relation_count"] >= 80,
    )
    postgres_source = (ROOT / "prmr/core/runtime_postgres_validation.py").read_text(
        encoding="utf-8"
    )
    add(checks, "dedicated_test_url_required", "PRMR_POSTGRES_TEST_DATABASE_URL" in postgres_source)
    add(checks, "destructive_permission_required", "PRMR_ALLOW_DESTRUCTIVE_POSTGRES_TESTS" in postgres_source)
    add(checks, "test_guard_row_required", "prmr_test_environment_guard" in postgres_source)
    add(checks, "production_database_fallback_absent", 'os.getenv("DATABASE_URL"' not in postgres_source)
    add(checks, "safe_sqlstate_diagnostics_present", "safe_postgres_exception_diagnostics" in postgres_source)
    add(checks, "guard_preserving_reset_present", "reset_postgres_test_application_schema" in postgres_source)
    add(checks, "guard_schema_not_dropped", "DROP SCHEMA IF EXISTS public" not in postgres_source)
    migration_source = (ROOT / "prmr/core/runtime_migrations.py").read_text(encoding="utf-8")
    add(checks, "registry_bootstraps_application_schema", "CREATE SCHEMA IF NOT EXISTS" in migration_source)
    runner_source = (ROOT / "examples/run_core_postgres_runtime_validation.py").read_text(encoding="utf-8")
    add(checks, "ad_hoc_repository_initializer_removed", "SelfServeRepositoryPostgresV0941" not in runner_source)
    add(
        checks,
        "migration_stack_precedes_repository_smoke",
        runner_source.index('execution_phase = "complete_migration_stack"')
        < runner_source.index('execution_phase = "repository_smoke"'),
    )
    add(
        checks,
        "runtime_submatrix_runs_after_migration_smoke",
        'execution_phase = "guarded_postgres_runtime_submatrix"' in runner_source
        and runner_source.index('execution_phase = "repository_smoke"')
        < runner_source.index(
            'execution_phase = "guarded_postgres_runtime_submatrix"'
        ),
    )
    matrix_source = (ROOT / "prmr/core/runtime_postgres_matrix.py").read_text(
        encoding="utf-8"
    )
    add(
        checks,
        "runtime_matrix_uses_bounded_full_matrix_status",
        '"PASS_FULL_POSTGRES_MATRIX"' in matrix_source
        and '"result": "PASS"' not in matrix_source,
    )
    for proof in (
        "historical_migration_upgrade_paths",
        "failed_migration_rolls_back_atomically",
        "concurrent_migration_registry_lock",
        "postgres_transaction_rollback",
        "postgres_serialization_retry",
        "postgres_lock_timeout_recovery",
        "postgres_deadlock_recovery",
        "skip_locked_eight_unique_leases",
        "eight_worker_postgres_execution",
        "all_job_types_executed",
        "postgres_heartbeat_extends_lease",
        "dead_letter_and_explicit_replay",
        "post_effect_recovery_consolidation_governance_export",
        "connection_pool_restart_preserves_jobs",
        "three_tenant_core_isolation",
        "governance_execution_single_winner",
        "same_consolidation_build_race",
        "same_export_generation_race",
        "governance_planner_three_x_improvement",
        "postgres_data_type_validation",
        "postgres_canonical_signal_batch",
        "postgres_explain_audit_completed",
        "sqlite_postgres_repository_parity",
        "end_to_end_core_sprint_1_to_10_lifecycle_postgres",
        "partial_consolidation_recovery",
        "partial_governance_recovery",
        "partial_export_recovery",
        "full_postgres_integrity_sweep",
    ):
        add(checks, f"matrix_proof_{proof}", proof in matrix_source)
    add(
        checks,
        "mandatory_matrix_is_fail_closed",
        "MANDATORY_CHECKS" in matrix_source
        and "mandatory_matrix_coverage_complete" in matrix_source
        and len(PostgresRuntimeMatrix.MANDATORY_CHECKS) >= 50
        and all(
            proof in matrix_source
            for proof in PostgresRuntimeMatrix.MANDATORY_CHECKS
        ),
    )
    add(checks, "undefined_table_diagnostic_regression", _undefined_table_diagnostic_works())
    queue_source = (ROOT / "prmr/core/job_queue.py").read_text(encoding="utf-8")
    add(checks, "postgres_skip_locked_implemented", "FOR UPDATE SKIP LOCKED" in queue_source)
    add(checks, "lease_tokens_stored_as_digest", "lease_token_digest" in queue_source and "sha256_text(lease_token)" in queue_source)
    add(checks, "payload_content_keys_rejected", "FORBIDDEN_PAYLOAD_KEYS" in queue_source)
    environment_path = REPORT_DIR / "postgres_environment_validation.json"
    add(checks, "environment_report_exists", environment_path.exists())
    environment = (
        json.loads(environment_path.read_text(encoding="utf-8"))
        if environment_path.exists()
        else {}
    )
    postgres_available = bool(os.getenv(TEST_DATABASE_ENV))
    environment_status = environment.get("status")
    postgres_was_exercised = environment_status in {
        "VERIFIED_BUT_RUNTIME_FAILED",
        "VERIFIED_ISOLATED_TEST_DATABASE",
    }
    migration_path = REPORT_DIR / "postgres_migration_validation.json"
    migration = (
        json.loads(migration_path.read_text(encoding="utf-8"))
        if migration_path.exists()
        else {}
    )
    add(checks, "migration_report_exists", migration_path.exists())
    runtime_matrix_path = REPORT_DIR / "postgres_runtime_matrix.json"
    runtime_matrix = (
        json.loads(runtime_matrix_path.read_text(encoding="utf-8"))
        if runtime_matrix_path.exists()
        else {}
    )
    if not postgres_available and not postgres_was_exercised:
        add(checks, "missing_postgres_status_is_blocked", environment.get("status") == "BLOCKED")
        add(
            checks,
            "guard_rejects_missing_url",
            _missing_guard_rejected(),
        )
        expected_result = "BLOCKED"
    else:
        add(checks, "configured_postgres_not_claimed_without_guard", environment.get("status") != "PASS")
        if migration.get("status") in {"PARTIAL_PASS", "PASS"}:
            migration_checks = migration.get("checks", {})
            add(checks, "empty_guarded_database_migrated", bool(migration_checks.get("empty_migration_stack")))
            add(checks, "all_expected_postgres_tables_exist", bool(migration_checks.get("all_expected_core_tables_present")))
            add(checks, "migration_replay_idempotent", bool(migration_checks.get("migration_replay_idempotent")))
            add(checks, "guard_preserved_after_reset_and_migrations", bool(migration.get("guard_preserved")))
            add(checks, "repository_smoke_after_migrations", bool(migration_checks.get("repository_smoke_after_migrations")))
            add(checks, "undefined_table_failure_cleared", migration.get("undefined_table_failure") is False)
            add(checks, "postgres_runtime_matrix_report_exists", runtime_matrix_path.exists())
            add(
                checks,
                "postgres_runtime_matrix_status_is_bounded",
                runtime_matrix.get("result")
                in {"PASS_FULL_POSTGRES_MATRIX", "NEEDS_WORK"},
            )
            add(
                checks,
                "postgres_runtime_matrix_does_not_record_url",
                runtime_matrix.get("database_url_recorded") is False,
            )
            matrix_checks = {
                item.get("name"): bool(item.get("passed"))
                for item in runtime_matrix.get("checks", [])
            }
            add(
                checks,
                "runtime_matrix_mandatory_coverage_is_complete",
                runtime_matrix.get("result") != "PASS_FULL_POSTGRES_MATRIX"
                or matrix_checks.get("mandatory_matrix_coverage_complete") is True,
            )
        else:
            diagnostics = migration.get("failure_diagnostics", {})
            add(checks, "failed_runtime_records_execution_phase", bool(diagnostics.get("execution_phase")))
            add(checks, "failed_runtime_records_sqlstate_field", "sqlstate" in diagnostics)
            add(checks, "failed_runtime_records_relation_field", "missing_relation" in diagnostics)
        expected_result = (
            "PASS"
            if migration.get("status") == "PASS"
            and runtime_matrix.get("result") == "PASS_FULL_POSTGRES_MATRIX"
            else "NEEDS_WORK"
        )
    report_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in REPORT_DIR.glob("*.json")
    )
    add(
        checks,
        "reports_have_no_database_urls",
        not bool(re.search(r"postgres(?:ql)?://[^\\s\"']+", report_text, re.I)),
    )
    add(
        checks,
        "reports_have_no_raw_tokens",
        not bool(re.search(r"(?:api[_-]?key|lease[_-]?token)\\s*[\"':=]+\\s*[A-Za-z0-9_-]{20,}", report_text, re.I)),
    )
    failed = [item for item in checks if not item["passed"]]
    result = "NEEDS_WORK" if failed else expected_result
    report = {
        "version": "core_sprint_11",
        "result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "postgres_environment_available": postgres_available,
        "postgres_was_exercised": postgres_was_exercised,
    }
    AUDIT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 11 PostgreSQL Audit")
    print(f"Passed checks: {report['passed_checks']}/{report['total_checks']}")
    print(f"PostgreSQL environment available: {postgres_available}")
    print(f"Result: {result}")
    return 1 if failed else 0


def _missing_guard_rejected() -> bool:
    try:
        verify_postgres_test_environment(database_url="")
    except RuntimeErrorCode as exc:
        return exc.code == "POSTGRES_TEST_DATABASE_URL_MISSING"
    return False


def _undefined_table_diagnostic_works() -> bool:
    class Diagnostic:
        table_name = "prmr_self_serve.synthetic_missing_relation"
        message_primary = 'relation "prmr_self_serve.synthetic_missing_relation" does not exist'

    class UndefinedTableForAudit(RuntimeError):
        sqlstate = "42P01"
        diag = Diagnostic()

    diagnostic = safe_postgres_exception_diagnostics(
        UndefinedTableForAudit(),
        execution_phase="audit_fixture",
        migration_id="core_audit_fixture",
    )
    return diagnostic == {
        "safe_error_code": "POSTGRES_UNDEFINED_TABLE",
        "sqlstate": "42P01",
        "missing_relation": "prmr_self_serve.synthetic_missing_relation",
        "migration_id": "core_audit_fixture",
        "execution_phase": "audit_fixture",
        "database_url_recorded": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
