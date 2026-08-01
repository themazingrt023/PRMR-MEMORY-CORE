"""Guarded Core Sprint 11 PostgreSQL runtime validation entrypoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.runtime_migrations import (  # noqa: E402
    apply_pending_migrations,
    detect_migration_drift,
    expected_postgres_relations,
    get_migration_status,
    migration_registry,
    validate_postgres_relation_order,
)
from prmr.core.runtime_models import RuntimeErrorCode  # noqa: E402
from prmr.core.runtime_postgres_validation import (  # noqa: E402
    DESTRUCTIVE_PERMISSION_ENV,
    TEST_DATABASE_ENV,
    reset_postgres_test_application_schema,
    safe_postgres_exception_diagnostics,
    verify_test_guard_connection,
    verify_postgres_test_environment,
)
from prmr.core.runtime_repository_parity import (  # noqa: E402
    compare_runtime_migration_contracts,
)
from prmr.core.runtime_postgres_matrix import PostgresRuntimeMatrix  # noqa: E402


REPORT_DIR = ROOT / "reports" / "core_runtime_hardening"
ENVIRONMENT_REPORT = REPORT_DIR / "postgres_environment_validation.json"
MIGRATION_REPORT = REPORT_DIR / "postgres_migration_validation.json"
PARITY_REPORT = REPORT_DIR / "repository_parity.json"
INDEX_REPORT = REPORT_DIR / "index_audit.json"
INTEGRITY_REPORT = REPORT_DIR / "integrity_sweep.json"
RUNTIME_MATRIX_REPORT = REPORT_DIR / "postgres_runtime_matrix.json"
CONCURRENCY_REPORT = REPORT_DIR / "concurrency_results.json"
RECOVERY_REPORT = REPORT_DIR / "failure_recovery.json"
RUNTIME_BENCHMARK_REPORT = REPORT_DIR / "runtime_benchmark.json"
PUBLIC_REPORT = REPORT_DIR / "public_runtime_hardening.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_runtime_hardening.json"
SCORECARD = REPORT_DIR / "scorecard_runtime_hardening.md"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def blocked_reports(code: str, detail: str) -> int:
    registry = migration_registry()
    sqlite_sql = (ROOT / registry[-1].sqlite_path).read_text(encoding="utf-8")
    postgres_sql = (ROOT / registry[-1].postgres_path).read_text(encoding="utf-8")
    parity = compare_runtime_migration_contracts(sqlite_sql, postgres_sql)
    environment = {
        "status": "BLOCKED",
        "safe_error_code": code,
        "safe_detail": detail,
        "database_url_present": bool(os.getenv(TEST_DATABASE_ENV)),
        "destructive_permission_present": (
            os.getenv(DESTRUCTIVE_PERMISSION_ENV, "").lower() == "true"
        ),
        "database_url_value_recorded": False,
    }
    migration = {
        "status": "NOT_RUN",
        "reason": code,
        "registered_migrations": len(registry),
        "migration_ids": [item.migration_id for item in registry],
        "empty_database_proof": "NOT_RUN",
        "migration_replay": "NOT_RUN",
        "upgrade_paths": "NOT_RUN",
    }
    repository_parity = {
        "status": "STATIC_RUNTIME_DDL_ONLY",
        "runtime_migration_contract": parity,
        "full_repository_parity": "NOT_RUN_REQUIRES_POSTGRES",
    }
    index = {
        "status": "NOT_RUN_REQUIRES_POSTGRES",
        "explain_plans": [],
        "source_values_recorded": False,
    }
    integrity = {
        "status": "NOT_RUN_REQUIRES_POSTGRES",
        "full_postgres_integrity_sweep": False,
    }
    write_json(ENVIRONMENT_REPORT, environment)
    write_json(MIGRATION_REPORT, migration)
    write_json(PARITY_REPORT, repository_parity)
    write_json(INDEX_REPORT, index)
    write_json(INTEGRITY_REPORT, integrity)
    _write_scorecard("BLOCKED", code)
    print("PRMR Memory Core - Core Sprint 11 PostgreSQL Runtime Validation")
    print(f"PostgreSQL environment: BLOCKED ({code})")
    print("Destructive database operations: NOT RUN")
    print("Result: BLOCKED")
    return 0


def _write_scorecard(status: str, reason: str) -> None:
    durable = REPORT_DIR / "durable_jobs.json"
    sqlite = "NOT RUN"
    checks = "NOT RUN"
    if durable.exists():
        durable_evidence = json.loads(durable.read_text(encoding="utf-8"))
        sqlite = durable_evidence.get("sqlite_result", "UNKNOWN")
        checks = (
            f"{durable_evidence.get('passed_checks', 0)}/"
            f"{durable_evidence.get('total_checks', 0)}"
        )
    benchmark = REPORT_DIR / "runtime_benchmark.json"
    governance = "NOT RUN"
    postgres_queue = "NOT RUN"
    if benchmark.exists():
        benchmark_evidence = json.loads(benchmark.read_text(encoding="utf-8"))
        planner = benchmark_evidence.get("governance_planner", {})
        queue = benchmark_evidence.get("postgres_job_matrix", {})
        if planner:
            governance = (
                f"{planner.get('dry_run_plan_ms')} ms "
                f"({planner.get('measured_speedup')}x versus the Sprint 10 fixture; "
                f"dependency graph median: "
                f"{planner.get('dependency_graph_median_ms')} ms)"
            )
        if queue:
            performance = queue.get("performance", {})
            fixture_jobs = performance.get("fixture_jobs", 0)
            postgres_queue = (
                f"{queue.get('eight_worker_processed')}/{fixture_jobs} completed; "
                f"duplicate effects: {queue.get('duplicate_effect_count')}"
            )
    matrix_path = REPORT_DIR / "postgres_runtime_matrix.json"
    matrix = (
        json.loads(matrix_path.read_text(encoding="utf-8"))
        if matrix_path.exists()
        else {}
    )
    postgres_proof = (
        "Guarded migrations, historical upgrades, repository parity, transactions, "
        "concurrency, durable jobs, recovery, integrity, query plans and the Core "
        "Sprint 1-10 lifecycle all executed successfully."
        if status == "PASS"
        else (
            f"PostgreSQL matrix remains incomplete: {matrix.get('result', 'NOT_RUN')}; "
            f"failed checks: {len(matrix.get('failed_checks', []))}."
        )
    )
    SCORECARD.write_text(
        "# Core Sprint 11 - Runtime Hardening\n\n"
        f"**Result:** {status}\n\n"
        f"**SQLite durable jobs:** {sqlite}\n\n"
        f"**SQLite durable-job checks:** {checks}\n\n"
        f"**Governance planning fixture:** {governance}\n\n"
        f"**PostgreSQL eight-worker fixture:** {postgres_queue}\n\n"
        f"**PostgreSQL:** {reason}\n\n"
        f"**PostgreSQL proof:** {postgres_proof}\n\n"
        "**Logical backup/restore:** NOT_RUN_TOOLING_UNAVAILABLE\n\n"
        + (
            "All claims are limited to the isolated guarded PostgreSQL test "
            "environment. No production or external certification claim is made.\n"
            if status == "PASS"
            else "A complete successful isolated PostgreSQL matrix is mandatory "
            "before this sprint can pass.\n"
        ),
        encoding="utf-8",
    )


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    execution_phase = "environment_guard"
    try:
        evidence = verify_postgres_test_environment()
    except RuntimeErrorCode as exc:
        return blocked_reports(exc.code, exc.safe_detail)

    database_url = os.environ[TEST_DATABASE_ENV]
    repository: Any | None = None
    try:
        from prmr.core.runtime_database import (
            PostgresRuntimeRepository,
            RuntimeDatabaseConfig,
        )
        import psycopg
        from psycopg.rows import dict_row

        execution_phase = "guard_preserving_application_reset"
        with psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            prepare_threshold=None,
        ) as connection:
            reset_evidence = reset_postgres_test_application_schema(connection)

        execution_phase = "migration_registry_bootstrap"
        repository = PostgresRuntimeRepository(
            database_url,
            config=RuntimeDatabaseConfig(),
        )
        relation_order = validate_postgres_relation_order()
        execution_phase = "complete_migration_stack"
        first = apply_pending_migrations(repository)
        migration_status = get_migration_status(repository)
        execution_phase = "migration_replay"
        second = apply_pending_migrations(repository)
        drift = detect_migration_drift(repository)

        execution_phase = "post_migration_guard_verification"
        with repository.connect() as connection:
            guard_preserved_after_migrations = verify_test_guard_connection(connection)

        execution_phase = "repository_smoke"
        pool_health = repository.health_check()
        pool_stats = repository.pool_stats()
        relation_map = expected_postgres_relations()
        expected_tables = {
            relation for relations in relation_map.values() for relation in relations
        }
        with repository.connect() as connection:
            table_rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='prmr_self_serve'
                ORDER BY table_name
                """
            ).fetchall()
            index_rows = connection.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname='prmr_self_serve'
                ORDER BY indexname
                """
            ).fetchall()
            for relation in sorted(expected_tables):
                connection.execute(
                    f"SELECT 1 FROM prmr_self_serve.{relation} LIMIT 0"
                )
        repository.close()
        repository = None

        execution_phase = "guarded_postgres_runtime_submatrix"
        runtime_matrix = PostgresRuntimeMatrix(database_url).run()
        write_json(RUNTIME_MATRIX_REPORT, runtime_matrix)
        write_json(
            CONCURRENCY_REPORT,
            {
                "status": runtime_matrix["result"],
                "transaction_matrix": runtime_matrix.get("safe_details", {}).get(
                    "transaction_matrix", {}
                ),
                "job_matrix": runtime_matrix.get("safe_details", {}).get(
                    "job_matrix", {}
                ),
                "database_url_recorded": False,
            },
        )
        write_json(
            RECOVERY_REPORT,
            {
                "status": runtime_matrix["result"],
                "recovery_results": runtime_matrix.get("safe_details", {})
                .get("job_matrix", {})
                .get("recovery_results", {}),
                "service_recovery": runtime_matrix.get("safe_details", {}).get(
                    "service_recovery", {}
                ),
                "database_url_recorded": False,
            },
        )
        write_json(
            RUNTIME_BENCHMARK_REPORT,
            {
                "status": runtime_matrix["result"],
                "governance_planner": runtime_matrix.get(
                    "safe_details", {}
                ).get("governance_performance", {}),
                "postgres_job_matrix": runtime_matrix.get(
                    "safe_details", {}
                ).get("job_matrix", {}),
                "logical_backup_restore": "NOT_RUN_TOOLING_UNAVAILABLE",
                "database_url_recorded": False,
            },
        )
        registry = migration_registry()
        expected_runtime_tables = {
            "prmr_memory_jobs",
            "prmr_memory_job_attempts",
            "prmr_memory_job_events",
            "prmr_memory_job_dependencies",
            "prmr_memory_job_effects",
            "prmr_memory_job_schedules",
        }
        actual_tables = {str(row["table_name"]) for row in table_rows}
        missing_tables = sorted(expected_tables - actual_tables)
        checks = {
            "environment_guard": evidence.guard_verified,
            "guard_preserved_after_reset": bool(reset_evidence["guard_preserved"]),
            "guard_preserved_after_migrations": guard_preserved_after_migrations,
            "registry_relation_order_valid": relation_order["verified"],
            "empty_migration_stack": len(first) == len(registry),
            "migration_registry_complete": len(migration_status) == len(registry),
            "migration_replay_idempotent": second == [],
            "migration_drift_absent": not drift["drift_detected"],
            "all_expected_core_tables_present": not missing_tables,
            "runtime_tables_present": expected_runtime_tables.issubset(actual_tables),
            "runtime_indexes_present": len(index_rows) >= 6,
            "repository_smoke_after_migrations": True,
            "pool_health": pool_health,
        }
        full_matrix_passed = (
            runtime_matrix["result"] == "PASS_FULL_POSTGRES_MATRIX"
        )
        complete_runtime = full_matrix_passed
        status = "PASS" if complete_runtime else "NEEDS_WORK"
        write_json(
            ENVIRONMENT_REPORT,
            {
                **evidence.to_dict(),
                "database_url_value_recorded": False,
                "pool_stats": pool_stats,
            },
        )
        write_json(
            MIGRATION_REPORT,
            {
                "status": (
                    "PASS"
                    if all(checks.values()) and complete_runtime
                    else "PARTIAL_PASS"
                    if all(checks.values())
                    else "NEEDS_WORK"
                ),
                "checks": checks,
                "applied_migrations": first,
                "replay_applied_migrations": second,
                "expected_table_count": len(expected_tables),
                "actual_expected_table_count": len(expected_tables - set(missing_tables)),
                "missing_tables": missing_tables,
                "guard_preserved": (
                    reset_evidence["guard_preserved"]
                    and guard_preserved_after_migrations
                ),
                "phase_order": [
                    "environment_guard",
                    "guard_preserving_application_reset",
                    "migration_registry_bootstrap",
                    "complete_migration_stack",
                    "migration_replay",
                    "post_migration_guard_verification",
                    "repository_smoke",
                ],
                "undefined_table_failure": False,
                "upgrade_paths": (
                    "PASS"
                    if any(
                        item.get("name") == "historical_migration_upgrade_paths"
                        and item.get("passed")
                        for item in runtime_matrix.get("checks", [])
                    )
                    else "NEEDS_WORK"
                ),
                "runtime_submatrix": runtime_matrix["result"],
            },
        )
        write_json(
            PARITY_REPORT,
            {
                "status": "PASS" if complete_runtime else "NEEDS_WORK",
                "full_repository_parity": (
                    "PASS" if complete_runtime else "NEEDS_WORK"
                ),
                "runtime_matrix_result": runtime_matrix["result"],
                "repository_parity": runtime_matrix.get(
                    "safe_details", {}
                ).get("repository_parity", {}),
            },
        )
        write_json(
            INDEX_REPORT,
            {
                "status": (
                    "PASS" if complete_runtime else "NEEDS_WORK"
                ),
                "index_count": len(index_rows),
                "explain_analyze_hot_paths": runtime_matrix.get(
                    "safe_details", {}
                ).get("index_audit", []),
            },
        )
        write_json(
            INTEGRITY_REPORT,
            {
                "status": "PASS" if complete_runtime else "NEEDS_WORK",
                "full_postgres_integrity_sweep": complete_runtime,
                "runtime_submatrix_result": runtime_matrix["result"],
                "orphan_counts": runtime_matrix.get("safe_details", {}).get(
                    "orphan_counts", {}
                ),
                "integrity_sweep": runtime_matrix.get(
                    "safe_details", {}
                ).get("integrity_sweep", {}),
            },
        )
        write_json(
            PUBLIC_REPORT,
            {
                "version": "core_sprint_11",
                "result": status,
                "postgres_matrix": runtime_matrix["result"],
                "passed_checks": runtime_matrix.get("passed_checks", 0),
                "total_checks": runtime_matrix.get("total_checks", 0),
                "database_url_recorded": False,
                "boundary": (
                    "Internal synthetic evidence from one guarded isolated "
                    "PostgreSQL test database. This is not production readiness "
                    "or external certification."
                ),
            },
        )
        write_json(
            PRIVATE_REPORT,
            {
                "version": "core_sprint_11",
                "result": status,
                "postgres_matrix": runtime_matrix,
                "environment_status": evidence.status,
                "database_url_recorded": False,
                "logical_backup_restore": "NOT_RUN_TOOLING_UNAVAILABLE",
            },
        )
        _write_scorecard(
            status,
            (
                "FULL GUARDED POSTGRESQL MATRIX EXECUTED"
                if complete_runtime
                else "PARTIAL RUNTIME EXECUTION; REQUIRED MATRIX INCOMPLETE"
            ),
        )
        print("PRMR Memory Core - Core Sprint 11 PostgreSQL Runtime Validation")
        print(f"Guard: {evidence.status}")
        print(f"Migrations applied: {len(first)}/{len(registry)}")
        print(f"Migration replay applied: {len(second)}")
        print(f"Expected Core tables present: {len(expected_tables) - len(missing_tables)}/{len(expected_tables)}")
        print(f"Guard preserved: {checks['guard_preserved_after_migrations']}")
        print("Undefined-table failure: CLEARED")
        print(f"Full PostgreSQL matrix: {runtime_matrix['result']}")
        print(
            "Repository parity and Core 1-10 lifecycle: "
            + ("PASS" if complete_runtime else "NEEDS_WORK")
        )
        print(f"Result: {status}")
        return 0 if complete_runtime else 1
    except Exception as exc:
        if repository is not None:
            try:
                repository.close()
            except Exception:
                pass
        diagnostics = safe_postgres_exception_diagnostics(
            exc,
            execution_phase=execution_phase,
        )
        code = diagnostics["safe_error_code"]
        write_json(
            ENVIRONMENT_REPORT,
            {
                **evidence.to_dict(),
                "status": "VERIFIED_BUT_RUNTIME_FAILED",
                "safe_error_code": code,
                "failure_diagnostics": diagnostics,
                "database_url_value_recorded": False,
            },
        )
        write_json(
            MIGRATION_REPORT,
            {
                "status": "NEEDS_WORK",
                "failure_diagnostics": diagnostics,
                "empty_database_proof": "FAILED",
                "migration_replay": "NOT_RUN",
                "guard_preservation": "PRESERVED_BEFORE_FAILURE",
            },
        )
        _write_scorecard("NEEDS_WORK", str(code))
        print("PRMR Memory Core - Core Sprint 11 PostgreSQL Runtime Validation")
        print(f"Guard: {evidence.status}")
        print(f"Safe failure code: {code}")
        print(f"SQLSTATE: {diagnostics['sqlstate'] or 'UNAVAILABLE'}")
        print(f"Missing relation: {diagnostics['missing_relation'] or 'UNAVAILABLE'}")
        print(f"Migration ID: {diagnostics['migration_id'] or 'NOT_IN_MIGRATION_PHASE'}")
        print(f"Execution phase: {diagnostics['execution_phase']}")
        print("Result: NEEDS_WORK")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
