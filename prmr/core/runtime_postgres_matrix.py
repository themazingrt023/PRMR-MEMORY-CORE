"""Guarded PostgreSQL runtime, concurrency, recovery, and index proof matrix."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import statistics
import threading
import time
from tempfile import TemporaryDirectory
from typing import Any, Callable

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .candidate_engine import CandidateMemoryEngine
from .canonical_signal_registry import CanonicalSignalRegistry
from .job_fixtures import (
    SyntheticEffectService,
    synthetic_handler_registry,
    synthetic_runtime_scope,
)
from .job_policy import MemoryJobPolicy
from .job_queue import MemoryJobQueue
from .job_scheduler import MemoryJobScheduler
from .job_worker import MemoryJobWorker
from .memory_ledger_service import MemoryLedgerService
from .relationship_admission import RelationshipAdmissionService
from .runtime_database import PostgresRuntimeRepository, RuntimeDatabaseConfig
from .runtime_failure_injection import RuntimeFailureInjector
from .runtime_core_lifecycle import (
    FIXED_BOUNDARY,
    lifecycle_scope,
    prepare_export_plan,
    run_consolidation_recovery,
    run_core_lifecycle,
    run_export_atomic_recovery,
    run_governance_recovery,
)
from .runtime_integrity import verify_runtime_job_scope_isolation, verify_runtime_jobs
from .runtime_migrations import (
    apply_pending_migrations,
    detect_migration_drift,
    expected_postgres_relations,
    get_migration_status,
    migration_registry,
)
from .runtime_models import (
    MemoryJobStatus,
    MemoryJobType,
    MigrationDefinition,
    RuntimeErrorCode,
    RuntimeTransactionPolicy,
)
from .runtime_postgres_validation import (
    reset_postgres_test_application_schema,
    safe_postgres_exception_diagnostics,
    verify_postgres_test_environment,
    verify_test_guard_connection,
)
from .source_ledger import SourceLedger
from .source_models import AuthenticatedScope, SourceInput


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def shifted(seconds: float) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).isoformat().replace("+00:00", "Z")


class PostgresRuntimeMatrix:
    """Execute destructive tests only after the isolated guard is verified."""

    MANDATORY_CHECKS = frozenset(
        {
            "historical_migration_upgrade_paths",
            "failed_migration_rolls_back_atomically",
            "concurrent_migration_registry_lock",
            "source_idempotency",
            "concurrent_source_ingestion_one_effect",
            "candidate_persistence",
            "real_concurrent_admission_one_effect",
            "real_concurrent_evolution_one_effect",
            "temporal_snapshot_uniqueness",
            "entity_identifier_uniqueness",
            "entity_merge_cycle_protection",
            "relationship_admission_concurrency",
            "query_replay_uniqueness",
            "consolidation_uniqueness",
            "checkpoint_replacement",
            "interpretation_request_uniqueness",
            "real_concurrent_canonical_signal_decisions",
            "governance_plan_staleness",
            "governance_execution_single_winner",
            "export_uniqueness",
            "tombstone_uniqueness",
            "sqlite_postgres_repository_parity",
            "postgres_transaction_rollback",
            "postgres_read_committed_isolation",
            "postgres_serialization_retry",
            "postgres_lock_timeout_recovery",
            "postgres_deadlock_recovery",
            "postgres_database_connection_interruption_recovery",
            "job_enqueue_idempotency_and_validation",
            "job_priority_and_dependency_ordering",
            "skip_locked_eight_unique_leases",
            "eight_worker_postgres_execution",
            "all_job_types_executed",
            "job_retry_classification_and_backoff",
            "postgres_heartbeat_extends_lease",
            "postgres_scheduled_execution_respects_due_time",
            "dead_letter_and_explicit_replay",
            "postgres_queued_cancellation",
            "postgres_running_cancellation",
            "post_effect_recovery_consolidation_governance_export",
            "partial_consolidation_recovery",
            "partial_governance_recovery",
            "partial_export_recovery",
            "connection_pool_restart_preserves_jobs",
            "three_tenant_core_isolation",
            "postgres_multi_tenant_job_isolation",
            "postgres_job_integrity_sweep",
            "full_postgres_integrity_sweep",
            "postgres_expected_indexes_present_and_valid",
            "postgres_explain_audit_completed",
            "postgres_data_type_validation",
            "governance_planner_three_x_improvement",
            "postgres_canonical_signal_batch",
            "exact_query_equivalence",
            "exact_packet_equivalence",
            "end_to_end_core_sprint_1_to_10_lifecycle_postgres",
            "sqlite_core_sprint_1_to_10_lifecycle_regression",
        }
    )

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self.environment = verify_postgres_test_environment(database_url)
        self.repository: PostgresRuntimeRepository | None = None
        self.checks: list[dict[str, Any]] = []
        self.safe_details: dict[str, Any] = {}
        self._postgres_lifecycle_evidence: dict[str, Any] = {}
        self._job_ids: list[str] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.checks.append(
            {"name": name, "passed": bool(passed), "detail": detail}
        )

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        phase = "upgrade_paths"
        try:
            self._run_upgrade_paths()
            phase = "core_concurrency"
            self._run_core_concurrency()
            phase = "repository_parity_and_lifecycle"
            self._run_repository_parity_and_lifecycle()
            phase = "service_recovery"
            self._run_service_recovery()
            phase = "governance_matrix"
            self._run_governance_matrix()
            phase = "authoritative_operation_races"
            self._run_authoritative_operation_races()
            phase = "transaction_matrix"
            self._run_transaction_matrix()
            phase = "durable_job_matrix"
            self._run_job_matrix()
            phase = "canonical_signal_batch"
            self._run_canonical_batch()
            phase = "postgres_data_types"
            self._run_data_type_validation()
            phase = "governance_performance"
            self._run_governance_benchmark()
            phase = "index_and_integrity"
            self._run_index_and_integrity()
            observed = {item["name"] for item in self.checks}
            missing = sorted(self.MANDATORY_CHECKS - observed)
            self.add(
                "mandatory_matrix_coverage_complete",
                not missing,
                {"required": len(self.MANDATORY_CHECKS), "missing": missing},
            )
            failures = [item for item in self.checks if not item["passed"]]
            return {
                "result": (
                    "PASS_FULL_POSTGRES_MATRIX"
                    if not failures
                    else "NEEDS_WORK"
                ),
                "passed_checks": len(self.checks) - len(failures),
                "total_checks": len(self.checks),
                "failed_checks": failures,
                "checks": self.checks,
                "safe_details": self.safe_details,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "database_url_recorded": False,
            }
        except Exception as exc:
            diagnostics = safe_postgres_exception_diagnostics(
                exc, execution_phase=phase
            )
            self.add(f"phase_{phase}_completed", False, diagnostics)
            return {
                "result": "NEEDS_WORK",
                "passed_checks": sum(1 for item in self.checks if item["passed"]),
                "total_checks": len(self.checks),
                "failed_checks": [item for item in self.checks if not item["passed"]],
                "checks": self.checks,
                "safe_details": self.safe_details,
                "failure_diagnostics": diagnostics,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "database_url_recorded": False,
            }
        finally:
            self._close_repository()

    def _open_repository(self) -> PostgresRuntimeRepository:
        self._close_repository()
        self.repository = PostgresRuntimeRepository(
            self._database_url,
            config=RuntimeDatabaseConfig(pool_minimum=1, pool_maximum=10),
        )
        return self.repository

    def _close_repository(self) -> None:
        if self.repository is not None:
            self.repository.close()
            self.repository = None

    def _reset_schema(self) -> None:
        self._close_repository()
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(
            self._database_url,
            autocommit=True,
            row_factory=dict_row,
            prepare_threshold=None,
        ) as connection:
            evidence = reset_postgres_test_application_schema(connection)
        if not evidence["guard_preserved"]:
            raise RuntimeErrorCode(
                "POSTGRES_TEST_ENVIRONMENT_NOT_CONFIRMED",
                "Test guard was not preserved during application reset.",
            )

    def _run_upgrade_paths(self) -> None:
        definitions = migration_registry()
        paths: list[dict[str, Any]] = []
        for depth in (0, 3, 5, 8, 10):
            self._reset_schema()
            repository = self._open_repository()
            prefix = definitions[:depth]
            suffix = definitions[depth:]
            prefix_applied = apply_pending_migrations(
                repository, definitions=prefix
            )
            source_id: str | None = None
            source_scope: AuthenticatedScope | None = None
            if depth >= 1:
                source_scope = AuthenticatedScope(
                    f"client_upgrade_{depth}", f"vault_upgrade_{depth}", "default"
                )
                source_id = SourceLedger(repository, initialize=False).ingest_source(
                    source_scope,
                    SourceInput(
                        "plain_text",
                        "Decision: retain synthetic migration evidence.",
                        occurred_at="2026-01-01T00:00:00Z",
                        idempotency_key=f"upgrade-path-{depth}",
                    ),
                ).source.source_id
            suffix_applied = apply_pending_migrations(
                repository, definitions=suffix
            )
            source_survived = True
            if source_id and source_scope:
                source_survived = (
                    SourceLedger(repository, initialize=False)
                    .get_source(source_scope, source_id)
                    .source_id
                    == source_id
                )
            replay = apply_pending_migrations(repository)
            drift = detect_migration_drift(repository)
            with repository.connect() as connection:
                guard_preserved = verify_test_guard_connection(connection)
            path = {
                "starting_depth": depth,
                "prefix_applied": len(prefix_applied),
                "suffix_applied": len(suffix_applied),
                "source_survived": source_survived,
                "replay_count": len(replay),
                "drift_absent": not drift["drift_detected"],
                "guard_preserved": guard_preserved,
            }
            path["passed"] = all(
                (
                    len(prefix_applied) == depth,
                    len(suffix_applied) == len(definitions) - depth,
                    source_survived,
                    not replay,
                    not drift["drift_detected"],
                    guard_preserved,
                )
            )
            paths.append(path)
        self.safe_details["upgrade_paths"] = paths
        self.add(
            "historical_migration_upgrade_paths",
            len(paths) == 5 and all(item["passed"] for item in paths),
            {"paths": len(paths)},
        )
        repository = self.repository
        assert repository is not None
        expected = {
            item for values in expected_postgres_relations().values() for item in values
        }
        with repository.connect() as connection:
            rows = connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='prmr_self_serve'"
            ).fetchall()
        actual = {str(row["table_name"]) for row in rows}
        self.add(
            "upgrade_final_schema_complete",
            expected.issubset(actual),
            {"expected": len(expected), "present": len(expected & actual)},
        )

        with TemporaryDirectory(prefix="prmr-migration-rollback-") as temporary:
            fixture_sql = (
                "CREATE TABLE prmr_self_serve.prmr_failed_migration_probe "
                "(probe_id TEXT PRIMARY KEY); "
                "SELECT * FROM prmr_self_serve.prmr_missing_rollback_probe;"
            )
            sqlite_path = Path(temporary) / "fixture_sqlite.sql"
            postgres_path = Path(temporary) / "fixture_postgres.sql"
            sqlite_path.write_text("SELECT 1;", encoding="utf-8")
            postgres_path.write_text(fixture_sql, encoding="utf-8")
            checksum = hashlib.sha256(
                sqlite_path.read_bytes() + b"\0" + postgres_path.read_bytes()
            ).hexdigest()
            fixture = MigrationDefinition(
                migration_id="core_11_rollback_probe",
                sprint="Core Sprint 11 test fixture",
                sqlite_path=str(sqlite_path),
                postgres_path=str(postgres_path),
                checksum_sha256=checksum,
                dependencies=(definitions[-1].migration_id,),
                transactional=True,
                destructive=False,
                minimum_schema_state=definitions[-1].migration_id,
                resulting_schema_state="rollback_probe_must_not_persist",
            )
            rollback_failure_observed = False
            try:
                apply_pending_migrations(repository, definitions=(fixture,))
            except Exception as exc:
                diagnostics = safe_postgres_exception_diagnostics(
                    exc,
                    execution_phase="migration_rollback_fixture",
                    migration_id=fixture.migration_id,
                )
                rollback_failure_observed = diagnostics["sqlstate"] == "42P01"
            with repository.connect() as connection:
                probe_absent = (
                    connection.execute(
                        "SELECT to_regclass("
                        "'prmr_self_serve.prmr_failed_migration_probe') AS value"
                    ).fetchone()["value"]
                    is None
                )
                registry_absent = (
                    connection.execute(
                        "SELECT migration_id FROM "
                        "prmr_self_serve.prmr_runtime_schema_migrations "
                        "WHERE migration_id=%s",
                        (fixture.migration_id,),
                    ).fetchone()
                    is None
                )
                guard_after_rollback = verify_test_guard_connection(connection)
        self.add(
            "failed_migration_rolls_back_atomically",
            rollback_failure_observed
            and probe_absent
            and registry_absent
            and guard_after_rollback,
        )

        self._reset_schema()
        repository = self._open_repository()
        migration_barrier = threading.Barrier(2)

        def migrate_concurrently(_: int) -> int:
            contender = PostgresRuntimeRepository(
                self._database_url,
                config=RuntimeDatabaseConfig(pool_minimum=1, pool_maximum=2),
            )
            try:
                migration_barrier.wait(timeout=10)
                return len(apply_pending_migrations(contender))
            finally:
                contender.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_counts = list(pool.map(migrate_concurrently, range(2)))
        migration_status = get_migration_status(repository)
        self.add(
            "concurrent_migration_registry_lock",
            sum(concurrent_counts) == len(definitions)
            and len(migration_status) == len(definitions)
            and len({str(item["migration_id"]) for item in migration_status})
            == len(definitions),
            {"applied_by_contenders": concurrent_counts},
        )

    def _run_transaction_matrix(self) -> None:
        repository = self.repository
        assert repository is not None
        self._truncate_jobs(repository)
        queue = MemoryJobQueue(repository, initialize=False)
        scope = synthetic_runtime_scope("transaction")
        probe = queue.enqueue(
            scope,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="transaction-probe",
            safe_payload={"scope_digest": "transaction_probe"},
            idempotency_key="transaction-probe",
            priority=5,
        )
        try:
            with repository.connect() as connection:
                connection.execute(
                    "UPDATE prmr_self_serve.prmr_memory_jobs SET priority=99 "
                    "WHERE job_id=%s",
                    (probe.job_id,),
                )
                raise RuntimeError("rollback fixture")
        except RuntimeError:
            pass
        rolled_back = queue.store.get_job(probe.job_id).priority == 5
        self.add("postgres_transaction_rollback", rolled_back)

        with repository.connect() as holder:
            holder.execute(
                "UPDATE prmr_self_serve.prmr_memory_jobs SET priority=6 WHERE job_id=%s",
                (probe.job_id,),
            )
            with repository.connect() as observer:
                observed = observer.execute(
                    "SELECT priority FROM prmr_self_serve.prmr_memory_jobs WHERE job_id=%s",
                    (probe.job_id,),
                ).fetchone()["priority"]
        self.add("postgres_read_committed_isolation", int(observed) == 5)

        serial_barrier = threading.Barrier(2)

        def serial_worker() -> int:
            first_attempt = True

            def operation(connection: Any) -> int:
                nonlocal first_attempt
                row = connection.execute(
                    "SELECT priority FROM prmr_self_serve.prmr_memory_jobs WHERE job_id=%s",
                    (probe.job_id,),
                ).fetchone()
                if first_attempt:
                    first_attempt = False
                    serial_barrier.wait(timeout=10)
                value = int(row["priority"]) + 1
                connection.execute(
                    "UPDATE prmr_self_serve.prmr_memory_jobs SET priority=%s WHERE job_id=%s",
                    (value, probe.job_id),
                )
                return value

            _, retries = repository.run_transaction(
                operation,
                policy=RuntimeTransactionPolicy.SERIALIZABLE_RETRY_V1,
            )
            return retries

        with ThreadPoolExecutor(max_workers=2) as pool:
            retry_counts = list(pool.map(lambda _: serial_worker(), range(2)))
        self.add(
            "postgres_serialization_retry",
            sum(retry_counts) >= 1,
            {"retry_counts": retry_counts},
        )

        lock_sqlstate: str | None = None
        with repository.connect() as holder:
            holder.execute(
                "SELECT job_id FROM prmr_self_serve.prmr_memory_jobs "
                "WHERE job_id=%s FOR UPDATE",
                (probe.job_id,),
            )
            try:
                with repository.connect() as contender:
                    contender.execute("SET LOCAL lock_timeout='100ms'")
                    contender.execute(
                        "UPDATE prmr_self_serve.prmr_memory_jobs SET priority=priority+1 "
                        "WHERE job_id=%s",
                        (probe.job_id,),
                    )
            except Exception as exc:
                lock_sqlstate = getattr(exc, "sqlstate", None)
        self.add("postgres_lock_timeout_recovery", lock_sqlstate == "55P03")

        second = queue.enqueue(
            scope,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="deadlock-probe",
            safe_payload={"scope_digest": "deadlock_probe"},
            idempotency_key="deadlock-probe",
        )
        deadlock_barrier = threading.Barrier(2)

        def deadlock_worker(first_id: str, second_id: str) -> str:
            try:
                with repository.connect() as connection:
                    connection.execute(
                        "SELECT job_id FROM prmr_self_serve.prmr_memory_jobs "
                        "WHERE job_id=%s FOR UPDATE",
                        (first_id,),
                    )
                    deadlock_barrier.wait(timeout=10)
                    connection.execute(
                        "SELECT job_id FROM prmr_self_serve.prmr_memory_jobs "
                        "WHERE job_id=%s FOR UPDATE",
                        (second_id,),
                    )
                return "committed"
            except Exception as exc:
                return str(getattr(exc, "sqlstate", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            deadlock_results = list(
                pool.map(
                    lambda pair: deadlock_worker(*pair),
                    ((probe.job_id, second.job_id), (second.job_id, probe.job_id)),
                )
            )
        self.add(
            "postgres_deadlock_recovery",
            "40P01" in deadlock_results and "committed" in deadlock_results,
            {"outcomes": sorted(deadlock_results)},
        )
        with repository.connect() as connection:
            connection.execute(
                "UPDATE prmr_self_serve.prmr_memory_jobs "
                "SET priority=priority+1 WHERE job_id=%s",
                (probe.job_id,),
            )
        self.add(
            "connection_recovers_after_lock_and_deadlock_failures",
            repository.health_check(),
        )
        self.safe_details["transaction_matrix"] = {
            "serializable_retry_counts": retry_counts,
            "lock_timeout_sqlstate": lock_sqlstate,
            "deadlock_outcomes": sorted(deadlock_results),
        }

    def _run_repository_parity_and_lifecycle(self) -> None:
        repository = self.repository
        assert repository is not None
        from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093

        with TemporaryDirectory(prefix="prmr-postgres-parity-") as temporary:
            sqlite_repository = SelfServeRepositoryV093(
                Path(temporary) / "repository_parity.sqlite"
            )
            sqlite_applied = apply_pending_migrations(sqlite_repository)
            sqlite_evidence = run_core_lifecycle(sqlite_repository, "parity")
            expected_tables = {
                table_name
                for values in expected_postgres_relations().values()
                for table_name in values
            }
            sqlite_columns: dict[str, list[str]] = {}
            with sqlite_repository.connect() as connection:
                for table_name in sorted(expected_tables):
                    sqlite_columns[table_name] = sorted(
                        str(row["name"])
                        for row in connection.execute(
                            f"PRAGMA table_info('{table_name}')"
                        ).fetchall()
                    )
        postgres_evidence = run_core_lifecycle(repository, "parity")
        postgres_replay = run_core_lifecycle(repository, "parity")
        postgres_columns: dict[str, list[str]] = {}
        with repository.connect() as connection:
            rows = connection.execute(
                "SELECT table_name,column_name FROM information_schema.columns "
                "WHERE table_schema='prmr_self_serve' "
                "ORDER BY table_name,ordinal_position"
            ).fetchall()
        for row in rows:
            postgres_columns.setdefault(str(row["table_name"]), []).append(
                str(row["column_name"])
            )
        postgres_columns = {
            key: sorted(value)
            for key, value in postgres_columns.items()
            if key in expected_tables
        }
        schema_mismatches = sorted(
            table_name
            for table_name in expected_tables
            if sqlite_columns.get(table_name) != postgres_columns.get(table_name)
        )
        self.add(
            "sqlite_postgres_schema_table_column_parity",
            not schema_mismatches
            and len(sqlite_columns) == len(postgres_columns) == len(expected_tables),
            {
                "expected_tables": len(expected_tables),
                "sqlite_tables": len(sqlite_columns),
                "postgres_tables": len(postgres_columns),
                "mismatch_count": len(schema_mismatches),
                "mismatched_tables": schema_mismatches,
            },
        )
        self._postgres_lifecycle_evidence = postgres_evidence
        self.add(
            "sqlite_core_sprint_1_to_10_lifecycle_regression",
            sqlite_evidence["export_integrity"]
            and bool(sqlite_evidence["packet_hash"])
            and bool(sqlite_evidence["current_result_hash"]),
        )

        self.add(
            "temporal_snapshot_uniqueness",
            postgres_evidence["dynamics_snapshot_id"]
            == postgres_replay["dynamics_snapshot_id"],
        )
        self.add(
            "entity_identifier_uniqueness",
            postgres_evidence["entity_ids"] == postgres_replay["entity_ids"],
        )
        self.add(
            "query_replay_uniqueness",
            postgres_evidence["current_query_run_id"]
            == postgres_replay["current_query_run_id"]
            and postgres_evidence["current_result_id"]
            == postgres_replay["current_result_id"],
        )
        self.add(
            "consolidation_uniqueness",
            postgres_evidence["consolidation_run_id"]
            == postgres_replay["consolidation_run_id"],
        )
        self.add(
            "interpretation_request_uniqueness",
            postgres_evidence["interpretation_request_id"]
            == postgres_replay["interpretation_request_id"],
        )
        self.add(
            "export_uniqueness",
            postgres_evidence["export_bundle_id"]
            == postgres_replay["export_bundle_id"],
        )
        with repository.connect() as connection:
            current_checkpoint_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_checkpoints "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s "
                    "AND checkpoint_status='current'",
                    lifecycle_scope("parity").memory_boundary(),
                ).fetchone()["count"]
            )
        self.add(
            "checkpoint_replacement",
            postgres_evidence["checkpoint_id"]
            == postgres_replay["checkpoint_id"]
            and current_checkpoint_count == 1,
            {"current_checkpoint_count": current_checkpoint_count},
        )

        from .interpretation_engine import InterpretationEngine
        from .interpretation_fixtures import RICH_STORY, recorded_fixture_items
        from .interpretation_provider import RecordedFixtureInterpretationProvider

        interpretation_scope = lifecycle_scope("interpretation_race_pg")
        interpretation_ledger = SourceLedger(repository, initialize=False)
        interpretation_source = interpretation_ledger.ingest_source(
            interpretation_scope,
            SourceInput(
                "plain_text",
                RICH_STORY,
                occurred_at="2025-01-01T00:00:00Z",
                idempotency_key="interpretation-race-source",
            ),
        ).source
        interpretation_segments = interpretation_ledger.list_source_segments(
            interpretation_scope, interpretation_source.source_id, limit=1000
        ).items
        interpretation_provider = RecordedFixtureInterpretationProvider(
            {
                "*": recorded_fixture_items(
                    interpretation_source, interpretation_segments
                )
            }
        )
        interpretation_barrier = threading.Barrier(2)

        def interpret_same_source(_: int) -> tuple[str | None, str | None]:
            interpretation_barrier.wait(timeout=10)
            try:
                result = InterpretationEngine(
                    repository,
                    providers={
                        interpretation_provider.metadata.provider_id: (
                            interpretation_provider
                        )
                    },
                    initialize=False,
                ).run_interpretation(
                    interpretation_scope,
                    interpretation_source.source_id,
                    "model_assisted_review_v1",
                    "interpretation_policy_v1",
                    [
                        "candidate_memory",
                        "entity_candidate",
                        "relationship_candidate",
                        "canonical_signal_proposal",
                        "unknown_result",
                    ],
                    interpretation_provider.metadata.provider_id,
                )
                return result.request.interpretation_request_id, None
            except Exception as exc:
                return None, str(getattr(exc, "code", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            interpretation_outcomes = list(
                pool.map(interpret_same_source, range(2))
            )
        interpretation_ids = {
            item[0] for item in interpretation_outcomes if item[0] is not None
        }
        with repository.connect() as connection:
            interpretation_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_interpretation_requests "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s "
                    "AND source_id=%s",
                    (
                        *interpretation_scope.memory_boundary(),
                        interpretation_source.source_id,
                    ),
                ).fetchone()["count"]
            )
        self.add(
            "concurrent_interpretation_request_one_identity",
            len(interpretation_ids) == 1
            and all(item[1] is None for item in interpretation_outcomes)
            and interpretation_rows == 1,
            {"request_rows": interpretation_rows},
        )

        parity_fields = (
            "current_semantic_hash",
            "packet_semantic_hash",
            "export_integrity",
        )
        equivalent_fields = {
            key: sqlite_evidence.get(key) == postgres_evidence.get(key)
            for key in parity_fields
        }
        self.add(
            "sqlite_postgres_repository_parity",
            len(sqlite_applied) == len(migration_registry())
            and all(equivalent_fields.values()),
            {
                "equivalent_fields": sum(equivalent_fields.values()),
                "total_fields": len(equivalent_fields),
                "mismatched_fields": sorted(
                    key for key, value in equivalent_fields.items() if not value
                ),
            },
        )
        self.add(
            "exact_query_equivalence",
            sqlite_evidence["current_semantic_hash"]
            == postgres_evidence["current_semantic_hash"],
        )
        self.add(
            "exact_packet_equivalence",
            sqlite_evidence["packet_semantic_hash"]
            == postgres_evidence["packet_semantic_hash"],
        )
        self.add(
            "postgres_authoritative_and_accelerated_packet_equivalence",
            postgres_evidence["packet_id"]
            == postgres_evidence["accelerated_packet_id"]
            and postgres_evidence["packet_hash"]
            == postgres_evidence["accelerated_packet_hash"],
        )
        required_lifecycle = (
            "source_ids",
            "interpretation_request_id",
            "candidate_ids",
            "admission_ids",
            "event_ids",
            "evolution_id",
            "dynamics_snapshot_id",
            "entity_ids",
            "relationship_id",
            "current_result_hash",
            "consolidation_run_id",
            "checkpoint_id",
            "export_bundle_id",
        )
        self.add(
            "end_to_end_core_sprint_1_to_10_lifecycle_postgres",
            all(postgres_evidence.get(key) for key in required_lifecycle)
            and postgres_evidence["export_integrity"],
            {"stages": len(required_lifecycle)},
        )

        tenant_labels = ("tenant_alpha", "tenant_beta", "tenant_gamma")
        tenant_evidence = {
            label: run_core_lifecycle(repository, label) for label in tenant_labels
        }
        tenant_scopes = {label: lifecycle_scope(label) for label in tenant_labels}
        identifiers_disjoint = all(
            set(tenant_evidence[left]["source_ids"]).isdisjoint(
                tenant_evidence[right]["source_ids"]
            )
            and set(tenant_evidence[left]["event_ids"]).isdisjoint(
                tenant_evidence[right]["event_ids"]
            )
            and tenant_evidence[left]["packet_id"]
            != tenant_evidence[right]["packet_id"]
            for index, left in enumerate(tenant_labels)
            for right in tenant_labels[index + 1 :]
        )
        from .memory_consolidation_engine import MemoryConsolidationEngine
        from .memory_export_service import MemoryExportService
        from .memory_governance_planner import MemoryGovernancePlanner
        from .memory_query_engine import MemoryQueryEngine

        cross_tenant_denials: list[bool] = []
        cross_tenant_categories: dict[str, int] = {
            "source": 0,
            "query": 0,
            "checkpoint": 0,
            "governance": 0,
            "export": 0,
        }
        for owner in tenant_labels:
            for foreign in tenant_labels:
                if owner == foreign:
                    continue
                probes = {
                    "source": lambda owner=owner, foreign=foreign: SourceLedger(
                        repository, initialize=False
                    ).get_source(
                        tenant_scopes[foreign],
                        tenant_evidence[owner]["source_ids"][0],
                    ),
                    "query": lambda owner=owner, foreign=foreign: MemoryQueryEngine(
                        repository, initialize=False
                    ).get_query_result(
                        tenant_scopes[foreign],
                        tenant_evidence[owner]["current_result_id"],
                    ),
                    "checkpoint": lambda owner=owner, foreign=foreign: MemoryConsolidationEngine(
                        repository, initialize=False
                    ).get_checkpoint(
                        tenant_scopes[foreign],
                        tenant_evidence[owner]["checkpoint_id"],
                    ),
                    "governance": lambda owner=owner, foreign=foreign: MemoryGovernancePlanner(
                        repository, initialize=False
                    ).get_plan(
                        tenant_scopes[foreign],
                        tenant_evidence[owner]["governance_plan_id"],
                    ),
                    "export": lambda owner=owner, foreign=foreign: MemoryExportService(
                        repository, initialize=False
                    ).verify_export_integrity(
                        tenant_scopes[foreign],
                        tenant_evidence[owner]["export_bundle_id"],
                    ),
                }
                for category, operation in probes.items():
                    try:
                        operation()
                        cross_tenant_denials.append(False)
                    except Exception:
                        cross_tenant_denials.append(True)
                        cross_tenant_categories[category] += 1
        self.add(
            "three_tenant_core_isolation",
            identifiers_disjoint
            and len(cross_tenant_denials) == 30
            and all(cross_tenant_denials),
            {
                "tenant_count": 3,
                "cross_scope_denials": sum(cross_tenant_denials),
                "categories": cross_tenant_categories,
            },
        )

        from .entity_identity_service import EntityIdentityService

        merge_scope = tenant_scopes["tenant_alpha"]
        merge_entities = tenant_evidence["tenant_alpha"]["entity_ids"]
        identities = EntityIdentityService(repository, initialize=False)
        merge_actor = AdmissionDecisionActor(
            "test_runner", "postgres-runtime-matrix"
        )
        identities.merge_entities(
            merge_scope,
            merge_entities[0],
            merge_entities[1],
            merge_actor,
            "Synthetic PostgreSQL merge-cycle proof.",
            idempotency_key="postgres-merge-cycle-forward",
        )
        merge_cycle_rejected = False
        try:
            identities.merge_entities(
                merge_scope,
                merge_entities[1],
                merge_entities[0],
                merge_actor,
                "Synthetic PostgreSQL reverse merge must be rejected.",
                idempotency_key="postgres-merge-cycle-reverse",
            )
        except Exception as exc:
            merge_cycle_rejected = (
                getattr(exc, "code", None) == "ENTITY_MERGE_CYCLE_DETECTED"
            )
        self.add("entity_merge_cycle_protection", merge_cycle_rejected)

        relationship_scope = tenant_scopes["tenant_beta"]
        relationship_evidence = tenant_evidence["tenant_beta"]
        relationship_barrier = threading.Barrier(2)

        def replay_relationship(_: int) -> tuple[str | None, str | None]:
            relationship_barrier.wait(timeout=10)
            try:
                result = RelationshipAdmissionService(
                    repository, initialize=False
                ).admit_relationship_candidate(
                    relationship_scope,
                    relationship_evidence["relationship_candidate_id"],
                    merge_actor,
                    subject_entity_id=relationship_evidence["entity_ids"][0],
                    object_entity_id=relationship_evidence["entity_ids"][1],
                    reason="Concurrent PostgreSQL relationship replay.",
                    idempotency_key="postgres-relationship-race",
                )
                return result["relationship"].relationship_id, None
            except Exception as exc:
                return None, str(getattr(exc, "code", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            relationship_outcomes = list(pool.map(replay_relationship, range(2)))
        with repository.connect() as connection:
            relationship_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM prmr_self_serve.prmr_relationships "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s "
                    "AND relationship_id=%s",
                    (
                        *relationship_scope.memory_boundary(),
                        relationship_evidence["relationship_id"],
                    ),
                ).fetchone()["count"]
            )
        self.add(
            "relationship_admission_concurrency",
            {item[0] for item in relationship_outcomes}
            == {relationship_evidence["relationship_id"]}
            and all(item[1] is None for item in relationship_outcomes)
            and relationship_rows == 1,
            {"row_count": relationship_rows},
        )

        foreign = lifecycle_scope("foreign")
        source_denied = query_denied = consolidation_denied = False
        try:
            SourceLedger(repository, initialize=False).get_source(
                foreign, postgres_evidence["source_ids"][0]
            )
        except Exception:
            source_denied = True
        try:
            from .memory_query_engine import MemoryQueryEngine

            MemoryQueryEngine(repository, initialize=False).get_query_result(
                foreign, postgres_evidence["current_result_id"]
            )
        except Exception:
            query_denied = True
        try:
            from .memory_consolidation_engine import MemoryConsolidationEngine

            MemoryConsolidationEngine(
                repository, initialize=False
            ).get_consolidation_run(
                foreign, postgres_evidence["consolidation_run_id"]
            )
        except Exception:
            consolidation_denied = True
        self.add(
            "postgres_core_multi_tenant_isolation",
            source_denied and query_denied and consolidation_denied,
        )
        self.safe_details["repository_parity"] = {
            "equivalent_fields": equivalent_fields,
            "sqlite_lifecycle_hash": sqlite_evidence["lifecycle_hash"],
            "postgres_lifecycle_hash": postgres_evidence["lifecycle_hash"],
            "postgres_stage_count": len(required_lifecycle),
            "intentional_parity_exclusions": [
                "Backend-generated record IDs, hashes, and operational timestamps are "
                "verified for replay stability within each backend; cross-backend "
                "equivalence compares the exact canonical memory meaning."
            ],
            "schema_table_count": len(expected_tables),
            "schema_mismatches": schema_mismatches,
            "scope_isolation": {
                "source": source_denied,
                "query": query_denied,
                "consolidation": consolidation_denied,
            },
        }

    def _run_service_recovery(self) -> None:
        repository = self.repository
        assert repository is not None
        from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093

        with TemporaryDirectory(prefix="prmr-recovery-parity-") as temporary:
            sqlite_repository = SelfServeRepositoryV093(
                Path(temporary) / "recovery_parity.sqlite"
            )
            apply_pending_migrations(sqlite_repository)
            sqlite_results = {
                "consolidation": run_consolidation_recovery(sqlite_repository),
                "governance": run_governance_recovery(sqlite_repository),
                "export": run_export_atomic_recovery(sqlite_repository),
            }
        consolidation = run_consolidation_recovery(repository)
        governance = run_governance_recovery(repository)
        export = run_export_atomic_recovery(repository)
        postgres_results = {
            "consolidation": consolidation,
            "governance": governance,
            "export": export,
        }
        self.add(
            "partial_consolidation_recovery",
            consolidation["passed"],
            consolidation,
        )
        self.add(
            "partial_governance_recovery", governance["passed"], governance
        )
        self.add("partial_export_recovery", export["passed"], export)
        self.add(
            "sqlite_postgres_recovery_semantics_parity",
            sqlite_results == postgres_results,
            {
                "equivalent_categories": sum(
                    sqlite_results[key] == postgres_results[key]
                    for key in sqlite_results
                ),
                "total_categories": len(sqlite_results),
            },
        )
        self.safe_details["service_recovery"] = {
            "sqlite": sqlite_results,
            "postgres": postgres_results,
        }

    def _run_governance_matrix(self) -> None:
        repository = self.repository
        assert repository is not None
        from .memory_governance_executor import MemoryGovernanceExecutor
        from .memory_governance_models import GovernanceActor
        from .memory_governance_planner import MemoryGovernancePlanner

        governance_actor = GovernanceActor(
            "test_runner", "postgres-runtime-matrix"
        )
        admission_actor = AdmissionDecisionActor(
            "test_runner", "postgres-runtime-matrix"
        )

        stale_scope = lifecycle_scope("governance_stale_pg")
        stale_source = SourceLedger(repository, initialize=False).ingest_source(
            stale_scope,
            SourceInput(
                "json",
                {
                    "event_type": "governance.stale",
                    "signal": "Synthetic governance staleness proof.",
                    "previous_state": "planned",
                    "current_state": "changed",
                    "occurred_at": "2026-07-21T10:00:00Z",
                },
                occurred_at="2026-07-21T10:00:00Z",
                idempotency_key="governance-stale-source",
            ),
        ).source
        planner = MemoryGovernancePlanner(repository, initialize=False)
        stale_plan = planner.plan_erasure(
            stale_scope,
            target_type="source",
            target_reference=stale_source.source_id,
            actor=governance_actor,
            reason="Synthetic governance plan staleness proof.",
            idempotency_key="governance-stale-plan",
            generated_at="2099-01-01T00:00:00Z",
        )
        stale_candidate = CandidateMemoryEngine(
            repository, initialize=False
        ).extract_candidates(stale_scope, stale_source.source_id).candidates[0]
        MemoryAdmissionService(repository, initialize=False).accept_candidate(
            stale_scope,
            stale_candidate.candidate_id,
            admission_actor,
            "Change dependency graph after plan creation.",
            "governance-stale-admission",
        )
        staleness_rejected = False
        try:
            planner.approve_governance_plan(
                stale_scope,
                stale_plan.governance_plan_id,
                actor=governance_actor,
                reason="Stale plan must not be approved.",
                idempotency_key="governance-stale-approval",
                approved_at="2099-01-02T00:00:00Z",
            )
        except Exception as exc:
            staleness_rejected = (
                getattr(exc, "code", None) == "GOVERNANCE_PLAN_STALE"
            )
        self.add("governance_plan_staleness", staleness_rejected)

        race_scope = lifecycle_scope("governance_race_pg")
        race_source = SourceLedger(repository, initialize=False).ingest_source(
            race_scope,
            SourceInput(
                "plain_text",
                "Synthetic governance execution race evidence.",
                occurred_at="2026-07-21T11:00:00Z",
                idempotency_key="governance-race-source",
            ),
        ).source
        race_planner = MemoryGovernancePlanner(repository, initialize=False)
        race_plan = race_planner.plan_erasure(
            race_scope,
            target_type="source",
            target_reference=race_source.source_id,
            actor=governance_actor,
            reason="Synthetic governance execution single-winner proof.",
            idempotency_key="governance-race-plan",
            generated_at="2099-01-01T00:00:00Z",
        )
        race_planner.approve_governance_plan(
            race_scope,
            race_plan.governance_plan_id,
            actor=governance_actor,
            reason="Approve guarded synthetic governance race.",
            idempotency_key="governance-race-approval",
            approved_at="2099-01-01T00:00:00Z",
        )
        governance_barrier = threading.Barrier(2)

        def execute_governance(label: str) -> tuple[str, str | None]:
            governance_barrier.wait(timeout=10)
            try:
                result = MemoryGovernanceExecutor(
                    repository, initialize=False
                ).execute(
                    race_scope,
                    race_plan.governance_plan_id,
                    idempotency_key=f"governance-race-execute:{label}",
                    started_at="2099-01-01T00:00:00Z",
                )
                return result.execution.execution_status, None
            except Exception as exc:
                return "blocked", str(
                    getattr(exc, "code", type(exc).__name__)
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            governance_outcomes = list(
                pool.map(execute_governance, ("alpha", "beta"))
            )
        completed_count = sum(
            status in {"completed", "completed_with_invalidations"}
            for status, _ in governance_outcomes
        )
        safely_blocked_count = sum(
            code == "GOVERNANCE_EXECUTION_CONFLICT"
            for _, code in governance_outcomes
        )
        with repository.connect() as connection:
            execution_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_governance_executions "
                    "WHERE governance_plan_id=%s",
                    (race_plan.governance_plan_id,),
                ).fetchone()["count"]
            )
            tombstone_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_erasure_tombstones t "
                    "JOIN prmr_self_serve.prmr_memory_governance_executions e "
                    "ON e.governance_execution_id=t.governance_execution_id "
                    "WHERE e.governance_plan_id=%s",
                    (race_plan.governance_plan_id,),
                ).fetchone()["count"]
            )
        self.add(
            "governance_execution_single_winner",
            completed_count == 1
            and safely_blocked_count == 1
            and execution_count == 1,
            {
                "completed": completed_count,
                "blocked": safely_blocked_count,
                "execution_rows": execution_count,
            },
        )
        self.add(
            "tombstone_uniqueness",
            tombstone_count == 1,
            {"tombstone_rows": tombstone_count},
        )
        self.safe_details["governance_matrix"] = {
            "stale_plan_rejected": staleness_rejected,
            "race_outcomes": governance_outcomes,
            "execution_rows": execution_count,
            "tombstone_rows": tombstone_count,
        }

    def _run_authoritative_operation_races(self) -> None:
        repository = self.repository
        assert repository is not None
        from .memory_consolidation_engine import MemoryConsolidationEngine
        from .memory_export_service import MemoryExportService

        actor = AdmissionDecisionActor("test_runner", "postgres-runtime-matrix")
        consolidation_scope = lifecycle_scope("consolidation_race_pg")
        for index in range(3):
            source = SourceLedger(repository, initialize=False).ingest_source(
                consolidation_scope,
                SourceInput(
                    "json",
                    {
                        "event_type": "consolidation.race",
                        "signal": "Synthetic consolidation race signal.",
                        "previous_state": f"state_{index}",
                        "current_state": f"state_{index + 1}",
                        "occurred_at": f"2026-07-2{index + 1}T10:00:00Z",
                    },
                    occurred_at=f"2026-07-2{index + 1}T10:00:00Z",
                    idempotency_key=f"consolidation-race-source:{index}",
                ),
            ).source
            candidate = CandidateMemoryEngine(
                repository, initialize=False
            ).extract_candidates(
                consolidation_scope, source.source_id
            ).candidates[0]
            MemoryAdmissionService(repository, initialize=False).accept_candidate(
                consolidation_scope,
                candidate.candidate_id,
                actor,
                "Synthetic consolidation race admission.",
                f"consolidation-race-admission:{index}",
            )
        consolidation_barrier = threading.Barrier(2)

        def consolidate_same_scope(_: int) -> tuple[str | None, str | None]:
            consolidation_barrier.wait(timeout=10)
            try:
                run = MemoryConsolidationEngine(
                    repository, initialize=False
                ).consolidate_memory(
                    consolidation_scope, {}, FIXED_BOUNDARY
                )
                return run.consolidation_run_id, None
            except Exception as exc:
                return None, str(getattr(exc, "code", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            consolidation_outcomes = list(
                pool.map(consolidate_same_scope, range(2))
            )
        consolidation_ids = {
            item[0] for item in consolidation_outcomes if item[0] is not None
        }
        with repository.connect() as connection:
            consolidation_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_consolidation_runs "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s",
                    consolidation_scope.memory_boundary(),
                ).fetchone()["count"]
            )
        self.add(
            "same_consolidation_build_race",
            len(consolidation_ids) == 1
            and all(item[1] is None for item in consolidation_outcomes)
            and consolidation_rows == 1,
            {"run_rows": consolidation_rows},
        )

        export_scope = lifecycle_scope("export_race_pg")
        export_plan_id = prepare_export_plan(repository, export_scope, "race")
        export_barrier = threading.Barrier(2)

        def export_same_plan(_: int) -> tuple[str | None, str | None]:
            export_barrier.wait(timeout=10)
            try:
                bundle = MemoryExportService(
                    repository, initialize=False
                ).create_export(
                    export_scope,
                    export_plan_id,
                    valid_at=FIXED_BOUNDARY.valid_at,
                    known_at=FIXED_BOUNDARY.known_at,
                    include_raw_sources=False,
                    generated_at="2099-01-01T00:00:00Z",
                )
                return bundle.memory_export_bundle_id, None
            except Exception as exc:
                return None, str(getattr(exc, "code", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            export_outcomes = list(pool.map(export_same_plan, range(2)))
        export_ids = {item[0] for item in export_outcomes if item[0] is not None}
        with repository.connect() as connection:
            export_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_export_bundles "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s",
                    export_scope.memory_boundary(),
                ).fetchone()["count"]
            )
        self.add(
            "same_export_generation_race",
            len(export_ids) == 1
            and all(item[1] is None for item in export_outcomes)
            and export_rows == 1,
            {"bundle_rows": export_rows},
        )
        self.safe_details["authoritative_operation_races"] = {
            "consolidation": consolidation_outcomes,
            "export": export_outcomes,
        }

    def _run_core_concurrency(self) -> None:
        repository = self.repository
        assert repository is not None
        scope = AuthenticatedScope(
            "client_core_race_pg", "vault_core_race_pg", "runtime_test"
        )
        actor = AdmissionDecisionActor("test_runner", "postgres-runtime-matrix")

        idempotent_input = SourceInput(
            "json",
            {
                "event_type": "project.updated",
                "signal": "Synthetic PostgreSQL source idempotency proof.",
                "previous_state": "queued",
                "current_state": "active",
                "occurred_at": "2026-07-20T09:00:00Z",
            },
            occurred_at="2026-07-20T09:00:00Z",
            idempotency_key="postgres-source-idempotency",
        )
        source_ledger = SourceLedger(repository, initialize=False)
        first_source = source_ledger.ingest_source(scope, idempotent_input).source
        replayed_source = source_ledger.ingest_source(scope, idempotent_input).source
        self.add(
            "source_idempotency",
            first_source.source_id == replayed_source.source_id,
        )

        source_barrier = threading.Barrier(4)

        def ingest_same_source(_: int) -> tuple[str, str]:
            source_barrier.wait(timeout=10)
            result = SourceLedger(repository, initialize=False).ingest_source(
                scope,
                SourceInput(
                    "plain_text",
                    "Synthetic concurrent source ingestion proof.",
                    occurred_at="2026-07-20T09:30:00Z",
                    idempotency_key="postgres-concurrent-source",
                ),
            )
            return result.source.source_id, (
                "created" if result.created else "replayed"
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            source_outcomes = list(pool.map(ingest_same_source, range(4)))
        concurrent_source_ids = {item[0] for item in source_outcomes}
        with repository.connect() as connection:
            concurrent_source_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM prmr_self_serve.prmr_sources "
                    "WHERE client_id=%s AND vault_id=%s AND namespace=%s "
                    "AND source_id=%s",
                    (*scope.memory_boundary(), next(iter(concurrent_source_ids))),
                ).fetchone()["count"]
            )
        self.add(
            "concurrent_source_ingestion_one_effect",
            len(concurrent_source_ids) == 1 and concurrent_source_rows == 1,
            {"outcomes": len(source_outcomes), "row_count": concurrent_source_rows},
        )

        candidate_engine = CandidateMemoryEngine(repository, initialize=False)
        candidate_first = candidate_engine.extract_candidates(
            scope, first_source.source_id
        )
        candidate_replay = candidate_engine.extract_candidates(
            scope, first_source.source_id
        )
        self.add(
            "candidate_persistence",
            bool(candidate_first.candidates)
            and [item.candidate_id for item in candidate_first.candidates]
            == [item.candidate_id for item in candidate_replay.candidates],
        )

        def candidate(label: str, state: str) -> Any:
            source = SourceLedger(repository, initialize=False).ingest_source(
                scope,
                SourceInput(
                    "json",
                    {
                        "event_type": "project.updated",
                        "signal": f"Synthetic PostgreSQL race state {state}.",
                        "previous_state": "queued",
                        "current_state": state,
                        "occurred_at": "2026-07-20T10:00:00Z",
                    },
                    occurred_at="2026-07-20T10:00:00Z",
                    idempotency_key=f"postgres-race-source:{label}",
                ),
            ).source
            return CandidateMemoryEngine(
                repository, initialize=False
            ).extract_candidates(scope, source.source_id).candidates[0]

        raced_candidate = candidate("admission", "active")
        admission_barrier = threading.Barrier(2)

        def admit_raced_candidate(_: int) -> tuple[str, str]:
            admission_barrier.wait(timeout=10)
            result = MemoryAdmissionService(
                repository, initialize=False
            ).accept_candidate(
                scope,
                raced_candidate.candidate_id,
                actor,
                "Synthetic concurrent PostgreSQL admission.",
                "postgres-race-admission",
            )
            assert result.admitted_event is not None
            return result.admission.admission_id, result.admitted_event["event_id"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            admission_outcomes = list(pool.map(admit_raced_candidate, range(2)))
        with repository.connect() as connection:
            admission_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_admission_decisions "
                    "WHERE candidate_id=%s",
                    (raced_candidate.candidate_id,),
                ).fetchone()["count"]
            )
        self.add(
            "real_concurrent_admission_one_effect",
            len(set(admission_outcomes)) == 1 and admission_count == 1,
            {"outcome_count": len(admission_outcomes), "row_count": admission_count},
        )

        original_candidate = candidate("evolution-original", "blocked")
        successor_candidate = candidate("evolution-successor", "resolved")
        admission = MemoryAdmissionService(repository, initialize=False)
        original = admission.accept_candidate(
            scope,
            original_candidate.candidate_id,
            actor,
            "Synthetic original memory.",
            "postgres-race-original",
        )
        successor = admission.accept_candidate(
            scope,
            successor_candidate.candidate_id,
            actor,
            "Synthetic successor memory.",
            "postgres-race-successor",
        )
        assert original.admitted_event is not None
        assert successor.admitted_event is not None
        evolution_barrier = threading.Barrier(2)

        def evolve_once(_: int) -> str:
            evolution_barrier.wait(timeout=10)
            value = MemoryLedgerService(
                repository, initialize=False
            ).supersede_admitted_memory(
                scope,
                original.admitted_event["event_id"],
                successor.admitted_event["event_id"],
                actor,
                "Synthetic concurrent PostgreSQL evolution.",
                valid_from="2026-07-20T10:00:00Z",
                system_effective_at="2099-01-01T00:00:00Z",
                idempotency_key="postgres-race-evolution",
            )
            return value.evolution_id

        with ThreadPoolExecutor(max_workers=2) as pool:
            evolution_outcomes = list(pool.map(evolve_once, range(2)))
        with repository.connect() as connection:
            evolution_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_memory_evolution_records "
                    "WHERE source_event_id=%s AND evolution_type='supersede'",
                    (original.admitted_event["event_id"],),
                ).fetchone()["count"]
            )
        self.add(
            "real_concurrent_evolution_one_effect",
            len(set(evolution_outcomes)) == 1 and evolution_count == 1,
            {"outcome_count": len(evolution_outcomes), "row_count": evolution_count},
        )
        self.safe_details["core_concurrency"] = {
            "source_outcomes": len(source_outcomes),
            "source_rows": concurrent_source_rows,
            "admission_outcomes": len(admission_outcomes),
            "admission_rows": admission_count,
            "evolution_outcomes": len(evolution_outcomes),
            "evolution_rows": evolution_count,
        }

    def _run_job_matrix(self) -> None:
        repository = self.repository
        assert repository is not None
        self._truncate_jobs(repository)
        policy = MemoryJobPolicy(
            lease_duration_seconds=2,
            stale_lease_grace_seconds=0,
            initial_retry_delay_seconds=0,
            worker_poll_interval_seconds=0.01,
        )
        queue = MemoryJobQueue(repository, policy=policy, initialize=False)
        service = SyntheticEffectService()
        handlers = synthetic_handler_registry(service)
        alpha = synthetic_runtime_scope("alpha_pg")
        beta = synthetic_runtime_scope("beta_pg")

        def has_code(operation: Callable[[], Any], code: str) -> bool:
            try:
                operation()
            except Exception as exc:
                return getattr(exc, "code", None) == code
            return False

        contract = queue.enqueue(
            alpha,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="job-contract",
            safe_payload={"scope_digest": "job_contract"},
            idempotency_key="job-contract",
            priority=3,
        )
        replay = queue.enqueue(
            alpha,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="job-contract",
            safe_payload={"scope_digest": "job_contract"},
            idempotency_key="job-contract",
            priority=3,
        )
        changed_conflict = has_code(
            lambda: queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="runtime_probe",
                target_object_id="job-contract",
                safe_payload={"scope_digest": "changed"},
                idempotency_key="job-contract",
            ),
            "MEMORY_JOB_IDEMPOTENCY_CONFLICT",
        )
        unsupported_rejected = has_code(
            lambda: queue.enqueue(
                alpha,
                job_type="not_a_memory_job",
                target_object_type="runtime_probe",
                target_object_id="unsupported",
                safe_payload={"scope_digest": "unsupported"},
                idempotency_key="unsupported",
            ),
            "MEMORY_JOB_TYPE_INVALID",
        )
        unsafe_payload_rejected = has_code(
            lambda: queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="runtime_probe",
                target_object_id="unsafe-payload",
                safe_payload={"source_content": "must never enter a job"},
                idempotency_key="unsafe-payload",
            ),
            "MEMORY_JOB_PAYLOAD_INVALID",
        )
        oversized_payload_rejected = has_code(
            lambda: queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="runtime_probe",
                target_object_id="oversized-payload",
                safe_payload={"scope_digest": "x" * 40_000},
                idempotency_key="oversized-payload",
            ),
            "MEMORY_JOB_PAYLOAD_INVALID",
        )
        contract_outcome = MemoryJobWorker(
            queue, handlers, worker_id="worker_contract_pg"
        ).run_once()
        self.add(
            "job_enqueue_idempotency_and_validation",
            replay.job_id == contract.job_id
            and changed_conflict
            and unsupported_rejected
            and unsafe_payload_rejected
            and oversized_payload_rejected
            and contract_outcome.get("job_id") == contract.job_id,
        )

        parent = queue.enqueue(
            alpha,
            job_type=MemoryJobType.GOVERNANCE_EXECUTION.value,
            target_object_type="governance_plan",
            target_object_id="dependency-parent",
            safe_payload={"governance_plan_id": "dependency-parent"},
            idempotency_key="dependency-parent",
            priority=20,
        )
        child = queue.enqueue(
            alpha,
            job_type=MemoryJobType.POST_ERASURE_RECOMPUTE.value,
            target_object_type="governance_execution",
            target_object_id="dependency-parent",
            safe_payload={"governance_plan_id": "dependency-parent"},
            idempotency_key="dependency-child",
            parent_job_id=parent.job_id,
            priority=100,
        )
        low = queue.enqueue(
            alpha,
            job_type=MemoryJobType.QUERY_PRECOMPUTE.value,
            target_object_type="query",
            target_object_id="priority-low",
            safe_payload={"query_digest": "priority_low"},
            idempotency_key="priority-low",
            priority=1,
        )
        dependency_worker = MemoryJobWorker(
            queue, handlers, worker_id="worker_dependency_pg"
        )
        first_ordered = dependency_worker.run_once()
        second_ordered = dependency_worker.run_once()
        third_ordered = dependency_worker.run_once()
        self.add(
            "job_priority_and_dependency_ordering",
            first_ordered.get("job_id") == parent.job_id
            and second_ordered.get("job_id") == child.job_id
            and third_ordered.get("job_id") == low.job_id,
        )

        scheduler = MemoryJobScheduler(queue)
        schedule_id = scheduler.create_schedule(
            alpha,
            schedule_type="one_time",
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="scheduler-contract",
            safe_payload={"scope_digest": "scheduler_contract"},
            next_run_at=utc_now(),
            created_at=utc_now(),
        )
        scheduled_ids = scheduler.enqueue_due(now=shifted(1))
        scheduler_outcome = MemoryJobWorker(
            queue, handlers, worker_id="worker_scheduler_pg"
        ).run_once()
        self.add(
            "job_scheduler_persists_and_enqueues_once",
            schedule_id.startswith("msched_")
            and len(scheduled_ids) == 1
            and scheduler_outcome.get("job_id") == scheduled_ids[0],
        )

        leased_jobs = [
            queue.enqueue(
                alpha,
                job_type=MemoryJobType.INTEGRITY_SWEEP.value,
                target_object_type="runtime_probe",
                target_object_id=f"skip-locked-{index}",
                safe_payload={"scope_digest": f"skip_{index}"},
                idempotency_key=f"skip-locked-{index}",
            )
            for index in range(8)
        ]
        lease_barrier = threading.Barrier(8)

        def lease_and_run(index: int) -> str | None:
            lease_barrier.wait(timeout=10)
            leased = queue.lease_next_job(f"worker_skip_{index}")
            if not leased:
                return None
            MemoryJobWorker(
                queue, handlers, worker_id=f"worker_skip_{index}"
            ).execute_job(leased)
            return leased.job.job_id

        with ThreadPoolExecutor(max_workers=8) as pool:
            leased_ids = list(pool.map(lease_and_run, range(8)))
        self.add(
            "skip_locked_eight_unique_leases",
            None not in leased_ids
            and len(set(leased_ids)) == len(leased_jobs) == 8,
        )

        mixed_job_types = tuple(item.value for item in MemoryJobType)
        bulk_enqueue_started = time.perf_counter()
        bulk_jobs = [
            queue.enqueue(
                alpha if index % 2 == 0 else beta,
                job_type=mixed_job_types[index % len(mixed_job_types)],
                target_object_type="synthetic_authoritative_target",
                target_object_id=f"bulk-{index}",
                safe_payload={"scope_digest": f"bulk_{index}"},
                idempotency_key=f"bulk-{index}",
            )
            for index in range(100)
        ]
        bulk_enqueue_ms = (time.perf_counter() - bulk_enqueue_started) * 1000

        def run_worker(index: int) -> int:
            result = MemoryJobWorker(
                queue, handlers, worker_id=f"worker_pool_{index}"
            ).run_until_idle(maximum_jobs=100)
            return int(result["processed"])

        bulk_execution_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            processed = list(pool.map(run_worker, range(8)))
        bulk_execution_ms = (time.perf_counter() - bulk_execution_started) * 1000
        completed = [queue.store.get_job(job.job_id) for job in bulk_jobs]
        effect_count = sum(
            1 for job in bulk_jobs if queue.store.get_effect(job.job_id) is not None
        )
        self.add(
            "eight_worker_postgres_execution",
            all(job.job_status == MemoryJobStatus.COMPLETED.value for job in completed)
            and sum(processed) == 100,
            {"processed": sum(processed)},
        )
        self.add(
            "concurrent_jobs_have_one_effect_each",
            effect_count == 100
            and all(service.calls[job.job_id] == 1 for job in bulk_jobs),
            {"effect_count": effect_count},
        )
        executed_types = {
            job.job_type
            for job in completed
            if job.job_status == MemoryJobStatus.COMPLETED.value
        }
        self.add(
            "all_job_types_executed",
            executed_types == set(mixed_job_types),
            {
                "executed_type_count": len(executed_types),
                "required_type_count": len(mixed_job_types),
            },
        )
        with repository.connect() as connection:
            latency_rows = connection.execute(
                "SELECT EXTRACT(EPOCH FROM (started_at-created_at))*1000 "
                "AS lease_latency_ms,"
                "EXTRACT(EPOCH FROM (completed_at-created_at))*1000 "
                "AS completion_latency_ms FROM "
                "prmr_self_serve.prmr_memory_jobs WHERE job_id=ANY(%s) "
                "AND completed_at IS NOT NULL",
                ([job.job_id for job in bulk_jobs],),
            ).fetchall()
        lease_latencies = sorted(
            float(row["lease_latency_ms"]) for row in latency_rows
        )
        completion_latencies = sorted(
            float(row["completion_latency_ms"]) for row in latency_rows
        )

        def percentile(values: list[float], fraction: float) -> float | None:
            if not values:
                return None
            index = min(len(values) - 1, max(0, int(len(values) * fraction) - 1))
            return round(values[index], 3)

        queue_performance = {
            "fixture_jobs": len(bulk_jobs),
            "mixed_job_types": len(executed_types),
            "enqueue_ms": round(bulk_enqueue_ms, 3),
            "enqueue_jobs_per_second": round(
                len(bulk_jobs) / max(bulk_enqueue_ms / 1000, 0.000001), 3
            ),
            "execution_ms": round(bulk_execution_ms, 3),
            "execution_jobs_per_second": round(
                len(bulk_jobs) / max(bulk_execution_ms / 1000, 0.000001), 3
            ),
            "lease_latency_median_ms": (
                round(statistics.median(lease_latencies), 3)
                if lease_latencies
                else None
            ),
            "lease_latency_p95_ms": percentile(lease_latencies, 0.95),
            "completion_latency_median_ms": (
                round(statistics.median(completion_latencies), 3)
                if completion_latencies
                else None
            ),
            "completion_latency_p95_ms": percentile(
                completion_latencies, 0.95
            ),
            "pool_stats": repository.pool_stats(),
            "one_thousand_job_fixture": "NOT_RUN_BOUNDED_MATRIX",
            "ten_thousand_job_fixture": "NOT_RUN_NOT_PRACTICAL_FOR_GUARDED_CI",
        }
        self.add(
            "postgres_queue_performance_measured",
            len(lease_latencies) == len(completion_latencies) == 100
            and queue_performance["enqueue_jobs_per_second"] > 0
            and queue_performance["execution_jobs_per_second"] > 0,
            queue_performance,
        )

        retry_target = "retry-once-pg"
        service.configure_failures(retry_target, 1)
        retry_job = queue.enqueue(
            alpha,
            job_type=MemoryJobType.CONSOLIDATION_REFRESH.value,
            target_object_type="consolidation",
            target_object_id=retry_target,
            safe_payload={"consolidation_id": retry_target},
            idempotency_key=retry_target,
            maximum_attempts=3,
        )
        retry_worker = MemoryJobWorker(
            queue, handlers, worker_id="worker_retry_pg"
        )
        retry_first = retry_worker.run_once()
        retry_second = retry_worker.run_once()
        retry_final = queue.store.get_job(retry_job.job_id)
        self.add(
            "job_retry_classification_and_backoff",
            retry_first.get("status") == MemoryJobStatus.RETRY_WAIT.value
            and retry_second.get("status") == MemoryJobStatus.COMPLETED.value
            and retry_final.attempt_count == 2
            and service.calls[retry_job.job_id] == 2,
            {"attempt_count": retry_final.attempt_count},
        )

        heartbeat_job = queue.enqueue(
            alpha,
            job_type=MemoryJobType.TEMPORAL_DYNAMICS_REFRESH.value,
            target_object_type="memory_scope",
            target_object_id="heartbeat",
            safe_payload={"scope_digest": "heartbeat"},
            idempotency_key="heartbeat",
        )
        leased = queue.lease_next_job("worker_heartbeat_pg")
        if not leased or leased.job.job_id != heartbeat_job.job_id:
            raise RuntimeErrorCode(
                "MEMORY_JOB_LEASE_FAILED", "Heartbeat fixture lease failed."
            )
        running, attempt_id = queue.start_job(
            leased,
            worker_id="worker_heartbeat_pg",
            transaction_mode=RuntimeTransactionPolicy.READ_COMMITTED_V1.value,
        )
        original_expiry = running.lease_expires_at
        extended = queue.heartbeat(
            running.job_id,
            worker_id="worker_heartbeat_pg",
            lease_token=leased.lease_token,
            attempt_id=attempt_id,
            now=shifted(1),
        )
        result = handlers.resolve(running.job_type).execute(running)
        queue.complete(
            running,
            worker_id="worker_heartbeat_pg",
            lease_token=leased.lease_token,
            attempt_id=attempt_id,
            result=result,
            duration_ms=1.0,
        )
        self.add(
            "postgres_heartbeat_extends_lease",
            bool(extended.lease_expires_at and extended.lease_expires_at > original_expiry),
        )

        queued_cancel = queue.enqueue(
            beta,
            job_type=MemoryJobType.EXPORT_GENERATION.value,
            target_object_type="export",
            target_object_id="cancelled-export",
            safe_payload={"scope_digest": "cancelled_export"},
            idempotency_key="cancelled-export",
        )
        cancelled = queue.request_cancellation(beta, queued_cancel.job_id)
        self.add(
            "postgres_queued_cancellation",
            cancelled.job_status == MemoryJobStatus.CANCELLED.value,
        )

        running_cancel = queue.enqueue(
            beta,
            job_type=MemoryJobType.QUERY_PRECOMPUTE.value,
            target_object_type="query",
            target_object_id="running-cancel",
            safe_payload={"scope_digest": "running_cancel"},
            idempotency_key="running-cancel",
        )
        running_lease = queue.lease_next_job("worker_running_cancel_pg")
        if not running_lease or running_lease.job.job_id != running_cancel.job_id:
            raise RuntimeErrorCode(
                "MEMORY_JOB_LEASE_FAILED",
                "Running cancellation fixture did not lease its target job.",
            )
        running_job, running_attempt = queue.start_job(
            running_lease,
            worker_id="worker_running_cancel_pg",
            transaction_mode=RuntimeTransactionPolicy.READ_COMMITTED_V1.value,
        )
        requested = queue.request_cancellation(
            beta, running_job.job_id, reason="Synthetic running cancellation."
        )
        running_cancelled = queue.cancel_running(
            running_job,
            worker_id="worker_running_cancel_pg",
            lease_token=running_lease.lease_token,
            attempt_id=running_attempt,
            reason="Synthetic running cancellation acknowledged.",
            duration_ms=1.0,
        )
        self.add(
            "postgres_running_cancellation",
            requested.job_status == MemoryJobStatus.CANCEL_REQUESTED.value
            and running_cancelled.job_status == MemoryJobStatus.CANCELLED.value,
        )

        scheduled_for = shifted(60)
        scheduled = queue.enqueue(
            alpha,
            job_type=MemoryJobType.CHECKPOINT_REFRESH.value,
            target_object_type="checkpoint",
            target_object_id="scheduled-checkpoint",
            safe_payload={"scope_digest": "scheduled_checkpoint"},
            idempotency_key="scheduled-checkpoint",
            scheduled_for=scheduled_for,
            priority=1000,
        )
        early_lease = queue.lease_next_job(
            "worker_scheduled_early_pg", now=shifted(0)
        )
        not_early = (
            early_lease is None or early_lease.job.job_id != scheduled.job_id
        ) and queue.store.get_job(scheduled.job_id).attempt_count == 0
        if early_lease is not None:
            MemoryJobWorker(
                queue, handlers, worker_id="worker_scheduled_early_pg"
            ).execute_job(early_lease)
        scheduled_lease = queue.lease_next_job(
            "worker_scheduled_due_pg", now=shifted(61)
        )
        scheduled_completed = False
        if scheduled_lease and scheduled_lease.job.job_id == scheduled.job_id:
            scheduled_outcome = MemoryJobWorker(
                queue, handlers, worker_id="worker_scheduled_due_pg"
            ).execute_job(scheduled_lease)
            scheduled_completed = (
                scheduled_outcome["status"] == MemoryJobStatus.COMPLETED.value
            )
        self.add(
            "postgres_scheduled_execution_respects_due_time",
            not_early and scheduled_completed,
        )

        dead = queue.enqueue(
            alpha,
            job_type=MemoryJobType.CONSOLIDATION_BUILD.value,
            target_object_type="consolidation",
            target_object_id="dead-letter",
            safe_payload={"scope_digest": "dead_letter"},
            idempotency_key="dead-letter",
            maximum_attempts=1,
        )
        service.configure_failures("dead-letter", 1)
        MemoryJobWorker(queue, handlers, worker_id="worker_dead_pg").run_once()
        dead_state = queue.store.get_job(dead.job_id)
        replayed = queue.replay_dead_letter(alpha, dead.job_id)
        MemoryJobWorker(queue, handlers, worker_id="worker_replay_pg").run_once()
        self.add(
            "dead_letter_and_explicit_replay",
            dead_state.job_status == MemoryJobStatus.DEAD_LETTER.value
            and replayed.job_status == MemoryJobStatus.QUEUED.value
            and queue.store.get_job(dead.job_id).job_status
            == MemoryJobStatus.COMPLETED.value,
        )

        recovered_types = (
            MemoryJobType.CONSOLIDATION_BUILD.value,
            MemoryJobType.GOVERNANCE_EXECUTION.value,
            MemoryJobType.EXPORT_GENERATION.value,
        )
        recovery_results: dict[str, bool] = {}
        stale_owner_rejections: dict[str, bool] = {}
        for index, job_type in enumerate(recovered_types):
            old = shifted(-120 - index)
            target = f"effect-recovery-{index}"
            job = queue.enqueue(
                alpha,
                job_type=job_type,
                target_object_type="authoritative_operation",
                target_object_id=target,
                safe_payload={"scope_digest": f"recovery_{index}"},
                idempotency_key=target,
                scheduled_for=old,
                created_at=old,
                priority=1000,
            )
            injector = RuntimeFailureInjector(
                enabled_for_tests=True,
                fail_counts={"after_effect_commit_before_job_completion": 1},
                crash_points={"after_effect_commit_before_job_completion"},
            )
            crashed_worker = MemoryJobWorker(
                queue,
                handlers,
                worker_id=f"worker_crash_{index}",
                failure_injector=injector,
            )
            leased_for_crash = queue.lease_next_job(
                f"worker_crash_{index}", now=old
            )
            if not leased_for_crash or leased_for_crash.job.job_id != job.job_id:
                raise RuntimeErrorCode(
                    "MEMORY_JOB_LEASE_FAILED",
                    "Crash-recovery fixture did not lease its target job.",
                )
            outcome = crashed_worker.execute_job(leased_for_crash)
            recovered_ids = queue.recover_expired_leases(now=utc_now())
            stale_owner_rejections[job_type] = has_code(
                lambda leased_for_crash=leased_for_crash, index=index: queue.heartbeat(
                    leased_for_crash.job.job_id,
                    worker_id=f"worker_crash_{index}",
                    lease_token=leased_for_crash.lease_token,
                ),
                "MEMORY_JOB_LEASE_LOST",
            )
            MemoryJobWorker(
                queue, handlers, worker_id=f"worker_recover_{index}"
            ).run_once()
            final = queue.store.get_job(job.job_id)
            recovery_results[job_type] = (
                outcome["status"] == "worker_crashed"
                and job.job_id in recovered_ids
                and final.job_status == MemoryJobStatus.COMPLETED.value
                and service.calls[job.job_id] == 1
            )
        self.add(
            "post_effect_recovery_consolidation_governance_export",
            all(recovery_results.values()),
            recovery_results,
        )
        self.add(
            "stale_lease_recovery_rejects_old_owner",
            all(stale_owner_rejections.values()),
            stale_owner_rejections,
        )

        beta_job = next(job for job in bulk_jobs if job.client_id == beta.client_id)
        isolation = verify_runtime_job_scope_isolation(
            queue.store,
            scope=alpha.boundary(),
            foreign_job_id=beta_job.job_id,
        )
        self.add("postgres_multi_tenant_job_isolation", isolation["verified"])

        with repository.connect() as connection:
            all_ids = [
                str(row["job_id"])
                for row in connection.execute(
                    "SELECT job_id FROM prmr_self_serve.prmr_memory_jobs "
                    "ORDER BY job_id"
                ).fetchall()
            ]
        integrity = verify_runtime_jobs(queue.store, all_ids)
        self.add("postgres_job_integrity_sweep", integrity["verified"])
        self._job_ids = all_ids

        outage_target = "database-interruption-recovery"
        service.configure_failures(outage_target, 1)
        outage_job = queue.enqueue(
            alpha,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id=outage_target,
            safe_payload={"scope_digest": "database_interruption"},
            idempotency_key=outage_target,
            maximum_attempts=3,
            priority=1000,
        )
        outage_first = MemoryJobWorker(
            queue, handlers, worker_id="worker_outage_before_pg"
        ).run_once()
        outage_false_completion = (
            queue.store.get_job(outage_job.job_id).job_status
            == MemoryJobStatus.RETRY_WAIT.value
            and queue.store.get_effect(outage_job.job_id) is None
        )
        before_restart_count = queue.store.count_jobs()
        self._close_repository()
        repository = self._open_repository()
        queue = MemoryJobQueue(repository, policy=policy, initialize=False)
        after_restart_count = queue.store.count_jobs()
        outage_second_lease = queue.lease_next_job(
            "worker_outage_after_pg", now=shifted(5)
        )
        outage_second = (
            MemoryJobWorker(
                queue, handlers, worker_id="worker_outage_after_pg"
            ).execute_job(outage_second_lease)
            if outage_second_lease is not None
            else {"status": "idle"}
        )
        outage_final = queue.store.get_job(outage_job.job_id)
        outage_integrity = verify_runtime_jobs(queue.store, [outage_job.job_id])
        self.add(
            "postgres_database_connection_interruption_recovery",
            outage_first.get("status") == MemoryJobStatus.RETRY_WAIT.value
            and outage_false_completion
            and outage_second.get("status") == MemoryJobStatus.COMPLETED.value
            and outage_final.job_status == MemoryJobStatus.COMPLETED.value
            and queue.store.get_effect(outage_job.job_id) is not None
            and service.calls[outage_job.job_id] == 2
            and outage_integrity["verified"],
        )
        self.add(
            "connection_pool_restart_preserves_jobs",
            before_restart_count == after_restart_count
            and queue.store.get_job(queued_cancel.job_id).job_status
            == MemoryJobStatus.CANCELLED.value,
            {"job_count": after_restart_count},
        )
        self.safe_details["job_matrix"] = {
            "skip_locked_unique_leases": len(set(leased_ids)),
            "eight_worker_processed": sum(processed),
            "effect_count": effect_count,
            "duplicate_effect_count": sum(
                max(0, service.calls[job.job_id] - 1) for job in bulk_jobs
            ),
            "recovery_results": recovery_results,
            "stale_owner_rejections": stale_owner_rejections,
            "pool_restart_job_count": after_restart_count,
            "database_interruption_recovered": (
                outage_final.job_status == MemoryJobStatus.COMPLETED.value
            ),
            "performance": queue_performance,
        }

    def _run_canonical_batch(self) -> None:
        repository = self.repository
        assert repository is not None
        scope = AuthenticatedScope(
            "client_runtime_canonical_pg", "vault_runtime_canonical_pg", "default"
        )
        registry = CanonicalSignalRegistry(repository, initialize=False)
        now = utc_now()
        proposals = [
            registry.propose_signal_mapping(
                scope,
                original_signal_key=f"runtime.pg_signal_{index}",
                proposed_canonical_signal_key=f"memory.pg_signal_{index}",
                proposal_basis="Synthetic reviewed PostgreSQL matrix fixture.",
                proposal_method="deterministic_alias_rule",
                created_at=now,
            )
            for index in range(8)
        ]
        reviewed = [
                {
                    "proposal_id": proposal.canonical_signal_proposal_id,
                    "actor_type": "test_runner",
                    "actor_reference": "postgres_matrix_reviewer",
                    "reason": "Synthetic reviewed mapping.",
                    "idempotency_key": f"postgres-matrix-{index}",
                    "valid_from": now,
                    "system_effective_at": now,
                }
                for index, proposal in enumerate(proposals)
            ]
        batch_barrier = threading.Barrier(4)

        def decide_batch(index: int) -> list[Any]:
            batch_barrier.wait(timeout=10)
            return CanonicalSignalRegistry(
                repository, initialize=False
            ).apply_canonical_signal_decisions_batch(
                scope, reviewed[index * 2 : index * 2 + 2]
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            decision_batches = list(pool.map(decide_batch, range(4)))
        decisions = [item for batch in decision_batches for item in batch]
        self.add(
            "postgres_canonical_signal_batch",
            len(decisions) == 8
            and all(item.decision_type == "approve" for item in decisions),
        )
        race_proposal = registry.propose_signal_mapping(
            scope,
            original_signal_key="runtime.pg_race_alias",
            proposed_canonical_signal_key="memory.pg_race_canonical",
            proposal_basis="Synthetic concurrent canonical decision proof.",
            proposal_method="deterministic_alias_rule",
            created_at=now,
        )
        canonical_barrier = threading.Barrier(2)

        def approve_same_proposal(_: int) -> tuple[str | None, str | None]:
            canonical_barrier.wait(timeout=10)
            try:
                decision = CanonicalSignalRegistry(
                    repository, initialize=False
                ).approve_signal_mapping(
                    scope,
                    race_proposal.canonical_signal_proposal_id,
                    actor_type="test_runner",
                    actor_reference="postgres_matrix_reviewer",
                    reason="Synthetic concurrent canonical approval.",
                    idempotency_key="postgres-canonical-race",
                    valid_from=now,
                    system_effective_at=now,
                )
                return decision.canonical_signal_decision_id, None
            except Exception as exc:
                return None, str(getattr(exc, "code", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            canonical_race = list(pool.map(approve_same_proposal, range(2)))
        with repository.connect() as connection:
            canonical_race_rows = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM "
                    "prmr_self_serve.prmr_canonical_signal_decisions "
                    "WHERE canonical_signal_proposal_id=%s AND decision_type='approve'",
                    (race_proposal.canonical_signal_proposal_id,),
                ).fetchone()["count"]
            )
        self.add(
            "real_concurrent_canonical_signal_decisions",
            len(decision_batches) == 4
            and all(len(batch) == 2 for batch in decision_batches),
            {
                "batch_count": len(decision_batches),
                "same_proposal_outcomes": canonical_race,
                "same_proposal_rows": canonical_race_rows,
            },
        )
        same_ids = {item[0] for item in canonical_race if item[0] is not None}
        same_proposal_safe = (
            len(same_ids) == 1
            and all(item[1] is None for item in canonical_race)
            and canonical_race_rows == 1
        )
        self.add(
            "same_canonical_mapping_approval_race",
            same_proposal_safe,
            {"row_count": canonical_race_rows},
        )

    def _run_data_type_validation(self) -> None:
        repository = self.repository
        assert repository is not None
        unicode_scope = AuthenticatedScope(
            "client_runtime_types_pg", "vault_runtime_types_pg", "default"
        )
        unicode_source = SourceLedger(repository, initialize=False).ingest_source(
            unicode_scope,
            SourceInput(
                "plain_text",
                "Unicode memory proof: \u03a9 and \u65e5.",
                occurred_at="2026-01-01T00:00:00Z",
                metadata={"labels": ["alpha", "beta"], "enabled": True},
                idempotency_key="postgres-data-types-unicode",
            ),
        ).source
        unicode_round_trip = (
            SourceLedger(repository, initialize=False)
            .get_source(unicode_scope, unicode_source.source_id)
            .sanitised_payload
            == unicode_source.sanitised_payload
        )

        queue = MemoryJobQueue(repository, initialize=False)
        service = SyntheticEffectService()
        handlers = synthetic_handler_registry(service)
        cascade_scope = synthetic_runtime_scope("cascade_pg")
        cascade_job = queue.enqueue(
            cascade_scope,
            job_type=MemoryJobType.INTEGRITY_SWEEP.value,
            target_object_type="runtime_probe",
            target_object_id="cascade-proof",
            safe_payload={"references": ["one", "two"], "enabled": True},
            idempotency_key="cascade-proof",
        )
        MemoryJobWorker(
            queue, handlers, worker_id="worker_cascade_pg"
        ).run_once()
        with repository.connect() as connection:
            type_row = connection.execute(
                "SELECT "
                "pg_typeof(TIMESTAMPTZ '2026-01-01T00:00:00Z')::text AS timestamp_type,"
                "pg_typeof('{\"items\":[1,2]}'::jsonb)::text AS json_type,"
                "pg_typeof(2147483647::integer)::text AS integer_type,"
                "pg_typeof(TRUE)::text AS boolean_type,"
                "pg_typeof(NULL::text)::text AS null_type,"
                "EXTRACT(TIMEZONE FROM TIMESTAMPTZ '2026-01-01T00:00:00Z') "
                "AS timezone_offset"
            ).fetchone()
            job_row = connection.execute(
                "SELECT safe_payload_json,payload_hash_sha256,lease_owner "
                "FROM prmr_self_serve.prmr_memory_jobs WHERE job_id=%s",
                (cascade_job.job_id,),
            ).fetchone()
            partial_indexes = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM pg_indexes "
                    "WHERE schemaname='prmr_self_serve' AND indexdef ILIKE '% WHERE %'"
                ).fetchone()["count"]
            )
            connection.execute(
                "DELETE FROM prmr_self_serve.prmr_memory_jobs WHERE job_id=%s",
                (cascade_job.job_id,),
            )
            cascade_orphans = {
                "attempts": int(
                    connection.execute(
                        "SELECT COUNT(*) AS count FROM "
                        "prmr_self_serve.prmr_memory_job_attempts WHERE job_id=%s",
                        (cascade_job.job_id,),
                    ).fetchone()["count"]
                ),
                "events": int(
                    connection.execute(
                        "SELECT COUNT(*) AS count FROM "
                        "prmr_self_serve.prmr_memory_job_events WHERE job_id=%s",
                        (cascade_job.job_id,),
                    ).fetchone()["count"]
                ),
                "effects": int(
                    connection.execute(
                        "SELECT COUNT(*) AS count FROM "
                        "prmr_self_serve.prmr_memory_job_effects WHERE job_id=%s",
                        (cascade_job.job_id,),
                    ).fetchone()["count"]
                ),
            }
        type_checks = {
            "timestamptz": type_row["timestamp_type"]
            == "timestamp with time zone",
            "utc": float(type_row["timezone_offset"]) == 0.0,
            "jsonb": type_row["json_type"] == "jsonb"
            and isinstance(job_row["safe_payload_json"], dict),
            "integer": type_row["integer_type"] == "integer",
            "boolean": type_row["boolean_type"] == "boolean"
            and job_row["safe_payload_json"].get("enabled") is True,
            "null": type_row["null_type"] == "text"
            and job_row["lease_owner"] is None,
            "unicode": unicode_round_trip,
            "digest_length": len(str(job_row["payload_hash_sha256"])) == 64,
            "list_strategy": job_row["safe_payload_json"].get("references")
            == ["one", "two"],
            "partial_indexes": partial_indexes > 0,
            "cascade_foreign_keys": all(
                value == 0 for value in cascade_orphans.values()
            ),
        }
        self.add(
            "postgres_data_type_validation",
            all(type_checks.values()),
            {
                "checks": type_checks,
                "partial_index_count": partial_indexes,
                "cascade_orphans": cascade_orphans,
            },
        )
        self.safe_details["postgres_data_types"] = type_checks

    def _run_governance_benchmark(self) -> None:
        repository = self.repository
        assert repository is not None
        from .memory_governance_models import GovernanceActor
        from .memory_governance_planner import MemoryGovernancePlanner

        source_count = 100
        scope = AuthenticatedScope(
            "client_governance_benchmark_pg",
            "vault_governance_benchmark_pg",
            "runtime_test",
        )
        ledger = SourceLedger(repository, initialize=False)
        ingest_started = time.perf_counter()
        for index in range(source_count):
            ledger.ingest_source(
                scope,
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
                    idempotency_key=f"governance-pg-benchmark:{index}",
                ),
            )
        ingest_ms = (time.perf_counter() - ingest_started) * 1000
        planner = MemoryGovernancePlanner(repository, initialize=False)
        request = planner.create_request(
            scope,
            action_type="erase_tenant_memory",
            target_type="tenant_memory_boundary",
            target_reference="::".join(scope.memory_boundary()),
            actor=GovernanceActor("test_runner", "postgres-runtime-matrix"),
            reason="Bounded synthetic PostgreSQL planning benchmark.",
            idempotency_key="governance-pg-benchmark-plan",
            governance_policy_id="full_tenant_erasure_v1",
            requested_at="2026-07-22T00:00:00Z",
        )
        graph_timings: list[float] = []
        graph = None
        for iteration in range(3):
            started = time.perf_counter()
            graph = planner.graphs.build(
                scope,
                request,
                generated_at="2026-07-22T00:00:00Z",
                persist=iteration == 0,
            )
            graph_timings.append((time.perf_counter() - started) * 1000)
        plan_started = time.perf_counter()
        plan = planner.plan(
            scope,
            request.governance_request_id,
            generated_at="2026-07-22T00:00:00Z",
        )
        plan_ms = (time.perf_counter() - plan_started) * 1000
        sprint_10_baseline_ms = 19_155.71
        speedup = sprint_10_baseline_ms / max(plan_ms, 0.001)
        performance = {
            "synthetic_sources": source_count,
            "discovered_nodes": len(graph.discovered_nodes) if graph else 0,
            "discovered_edges": len(graph.discovered_edges) if graph else 0,
            "planned_objects": sum(plan.estimated_counts_by_type.values()),
            "source_ingest_ms": round(ingest_ms, 3),
            "dependency_graph_median_ms": round(
                statistics.median(graph_timings), 3
            ),
            "dry_run_plan_ms": round(plan_ms, 3),
            "sprint_10_baseline_ms": sprint_10_baseline_ms,
            "measured_speedup": round(speedup, 3),
            "target_under_ms": 6_500,
        }
        self.add(
            "governance_planner_three_x_improvement",
            speedup >= 3.0 and plan_ms < 6_500,
            performance,
        )
        self.safe_details["governance_performance"] = performance

    def _run_index_and_integrity(self) -> None:
        repository = self.repository
        assert repository is not None
        integrity_sweep = self._run_full_integrity_sweep(repository)
        self.add(
            "full_postgres_integrity_sweep",
            integrity_sweep["verified"]
            and integrity_sweep["configured_categories"] == 13,
            {
                "configured_categories": integrity_sweep[
                    "configured_categories"
                ]
            },
        )
        plans: list[dict[str, Any]] = []
        queries = (
            (
                "job_lease",
                "SELECT job_id FROM prmr_self_serve.prmr_memory_jobs "
                "WHERE job_status IN ('queued','retry_wait') "
                "ORDER BY priority DESC,available_after,created_at,job_id LIMIT 1",
            ),
            (
                "source_scope",
                "SELECT source_id FROM prmr_self_serve.prmr_sources "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' ORDER BY ingested_at,source_id LIMIT 10",
            ),
            (
                "source_dependency_graph",
                "SELECT plan_item_id FROM "
                "prmr_self_serve.prmr_memory_governance_plan_items "
                "WHERE governance_plan_id='gplan_index_probe' "
                "ORDER BY sequence_index LIMIT 10",
            ),
            (
                "candidate_lookup",
                "SELECT candidate_id FROM prmr_self_serve.prmr_candidate_memories "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND source_id='src_index_probe' LIMIT 10",
            ),
            (
                "admission_uniqueness",
                "SELECT admission_id FROM "
                "prmr_self_serve.prmr_memory_admission_decisions "
                "WHERE candidate_id='cand_index_probe' LIMIT 1",
            ),
            (
                "evolution_resolution",
                "SELECT evolution_id FROM "
                "prmr_self_serve.prmr_memory_evolution_records "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND source_event_id='evt_index_probe' LIMIT 10",
            ),
            (
                "dynamics_signal_grouping",
                "SELECT d.signal_key FROM "
                "prmr_self_serve.prmr_memory_signal_dynamics d JOIN "
                "prmr_self_serve.prmr_memory_dynamics_snapshots s "
                "ON s.dynamics_snapshot_id=d.dynamics_snapshot_id "
                "WHERE s.client_id='client_index_probe' "
                "AND s.vault_id='vault_index_probe' AND s.namespace='default' "
                "ORDER BY d.signal_key LIMIT 10",
            ),
            (
                "entity_identifier_resolution",
                "SELECT entity_id FROM prmr_self_serve.prmr_entity_identifiers "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND identifier_namespace='email' "
                "AND identifier_value_digest='digest_index_probe' LIMIT 1",
            ),
            (
                "relationship_endpoint_lookup",
                "SELECT relationship_id FROM prmr_self_serve.prmr_relationships "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND subject_entity_id='ent_index_probe' "
                "ORDER BY valid_from LIMIT 10",
            ),
            (
                "query_replay_fingerprint",
                "SELECT query_run_id FROM prmr_self_serve.prmr_memory_query_runs "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' "
                "AND query_fingerprint_sha256='fingerprint_index_probe' LIMIT 1",
            ),
            (
                "checkpoint_lookup",
                "SELECT memory_checkpoint_id FROM "
                "prmr_self_serve.prmr_memory_checkpoints "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND checkpoint_status='current' "
                "ORDER BY created_at DESC LIMIT 1",
            ),
            (
                "canonical_mapping",
                "SELECT canonical_signal_proposal_id FROM "
                "prmr_self_serve.prmr_canonical_signal_proposals "
                "WHERE client_id='client_runtime_canonical_pg' "
                "AND vault_id='vault_runtime_canonical_pg' AND namespace='default' "
                "AND proposal_status='approved'",
            ),
            (
                "governance_plan_items",
                "SELECT plan_item_id FROM "
                "prmr_self_serve.prmr_memory_governance_plan_items "
                "WHERE client_id='client_index_probe' AND vault_id='vault_index_probe' "
                "AND namespace='default' AND node_type='source' "
                "ORDER BY sequence_index LIMIT 10",
            ),
        )
        with repository.connect() as connection:
            for name, query in queries:
                value = connection.execute(
                    f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                ).fetchone()["QUERY PLAN"]
                plan = value[0] if isinstance(value, list) else value
                plans.append(
                    {
                        "name": name,
                        "planning_time_ms": plan.get("Planning Time"),
                        "execution_time_ms": plan.get("Execution Time"),
                        "nodes": self._plan_nodes(plan.get("Plan", {})),
                    }
                )
            orphan_counts = {
                "attempts": connection.execute(
                    "SELECT COUNT(*) AS count FROM prmr_self_serve.prmr_memory_job_attempts a "
                    "LEFT JOIN prmr_self_serve.prmr_memory_jobs j ON j.job_id=a.job_id "
                    "WHERE j.job_id IS NULL"
                ).fetchone()["count"],
                "events": connection.execute(
                    "SELECT COUNT(*) AS count FROM prmr_self_serve.prmr_memory_job_events e "
                    "LEFT JOIN prmr_self_serve.prmr_memory_jobs j ON j.job_id=e.job_id "
                    "WHERE j.job_id IS NULL"
                ).fetchone()["count"],
                "effects": connection.execute(
                    "SELECT COUNT(*) AS count FROM prmr_self_serve.prmr_memory_job_effects e "
                    "LEFT JOIN prmr_self_serve.prmr_memory_jobs j ON j.job_id=e.job_id "
                    "WHERE j.job_id IS NULL"
                ).fetchone()["count"],
            }
            index_rows = connection.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='prmr_self_serve' ORDER BY indexname"
            ).fetchall()
            invalid_index_rows = connection.execute(
                "SELECT c.relname AS index_name FROM pg_index i "
                "JOIN pg_class c ON c.oid=i.indexrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='prmr_self_serve' AND NOT i.indisvalid"
            ).fetchall()
            constraint_rows = connection.execute(
                "SELECT contype,COUNT(*) AS count FROM pg_constraint c "
                "JOIN pg_namespace n ON n.oid=c.connamespace "
                "WHERE n.nspname='prmr_self_serve' GROUP BY contype"
            ).fetchall()
            guard_preserved = verify_test_guard_connection(connection)
        expected_indexes: set[str] = set()
        for definition in migration_registry():
            sql = Path(definition.postgres_path)
            if not sql.is_absolute():
                sql = Path(__file__).resolve().parents[2] / sql
            expected_indexes.update(
                re.findall(
                    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_]+)",
                    sql.read_text(encoding="utf-8"),
                    flags=re.IGNORECASE,
                )
            )
        actual_indexes = {str(row["indexname"]) for row in index_rows}
        missing_indexes = sorted(expected_indexes - actual_indexes)
        self.add(
            "postgres_expected_indexes_present_and_valid",
            not missing_indexes and not invalid_index_rows,
            {
                "expected_count": len(expected_indexes),
                "actual_count": len(actual_indexes),
                "missing_count": len(missing_indexes),
                "invalid_count": len(invalid_index_rows),
            },
        )
        drift = detect_migration_drift(repository)
        self.add("postgres_explain_audit_completed", len(plans) == 13)
        self.add(
            "postgres_runtime_has_no_job_orphans",
            all(int(value) == 0 for value in orphan_counts.values()),
            orphan_counts,
        )
        self.add(
            "postgres_final_migration_integrity",
            not drift["drift_detected"]
            and len(get_migration_status(repository)) == len(migration_registry())
            and guard_preserved,
        )
        self.safe_details["index_audit"] = plans
        self.safe_details["orphan_counts"] = orphan_counts
        self.safe_details["integrity_sweep"] = integrity_sweep
        self.safe_details["schema_integrity"] = {
            "expected_index_count": len(expected_indexes),
            "actual_index_count": len(actual_indexes),
            "missing_indexes": missing_indexes,
            "invalid_index_count": len(invalid_index_rows),
            "constraint_counts_by_type": {
                str(row["contype"]): int(row["count"])
                for row in constraint_rows
            },
        }

    def _run_full_integrity_sweep(
        self, repository: PostgresRuntimeRepository
    ) -> dict[str, Any]:
        from .admission_integrity import MemoryAdmissionIntegrityVerifier
        from .canonical_signal_integrity import CanonicalSignalIntegrityVerifier
        from .entity_integrity import EntityIntegrityVerifier
        from .interpretation_integrity import InterpretationIntegrityVerifier
        from .memory_consolidation_integrity import (
            MemoryConsolidationIntegrityVerifier,
        )
        from .memory_dynamics_engine import MemoryDynamicsEngine
        from .memory_governance_integrity import MemoryGovernanceIntegrityVerifier
        from .memory_ledger_integrity import MemoryLedgerIntegrityVerifier
        from .memory_query_engine import MemoryQueryEngine
        from .memory_query_integrity import MemoryQueryIntegrityVerifier
        from .relationship_integrity import RelationshipIntegrityVerifier
        from .runtime_integrity_sweep import IntegrityCheckAdapter, RuntimeIntegritySweep

        evidence = self._postgres_lifecycle_evidence
        scope = lifecycle_scope("parity")
        sources = SourceLedger(repository, initialize=False)
        candidates = CandidateMemoryEngine(repository, initialize=False)
        admissions = MemoryAdmissionService(repository, initialize=False)

        def source_check() -> dict[str, Any]:
            values = [
                sources.verify_source_integrity(scope, source_id).verified
                for source_id in evidence["source_ids"]
            ]
            return {"verified": all(values), "checked_count": len(values)}

        def candidate_check() -> dict[str, Any]:
            values = []
            for candidate_id in evidence["candidate_ids"]:
                candidate = candidates.get_candidate(scope, candidate_id)
                candidate_evidence = candidates.get_candidate_evidence(
                    scope, candidate_id
                )
                values.append(
                    bool(candidate.candidate_fingerprint_sha256)
                    and bool(candidate_evidence)
                )
            return {"verified": all(values), "checked_count": len(values)}

        def admission_check() -> dict[str, Any]:
            verifier = MemoryAdmissionIntegrityVerifier(admissions)
            values = [
                verifier.verify(scope, admission_id).verified
                for admission_id in evidence["admission_ids"]
            ]
            return {"verified": all(values), "checked_count": len(values)}

        query_engine = MemoryQueryEngine(repository, initialize=False)
        adapters = [
            IntegrityCheckAdapter("source", source_check),
            IntegrityCheckAdapter("candidate", candidate_check),
            IntegrityCheckAdapter("admission", admission_check),
            IntegrityCheckAdapter(
                "ledger",
                lambda: MemoryLedgerIntegrityVerifier(
                    repository, initialize=False
                ).verify_memory_ledger_integrity(scope).verified,
            ),
            IntegrityCheckAdapter(
                "temporal_dynamics",
                lambda: MemoryDynamicsEngine(
                    repository, initialize=False
                ).verify_memory_dynamics_integrity(
                    scope, evidence["dynamics_snapshot_id"]
                ).verified,
            ),
            IntegrityCheckAdapter(
                "entity",
                lambda: all(
                    EntityIntegrityVerifier(
                        repository, initialize=False
                    ).verify_entity_integrity(scope, entity_id)["verified"]
                    for entity_id in evidence["entity_ids"]
                ),
            ),
            IntegrityCheckAdapter(
                "relationship",
                lambda: RelationshipIntegrityVerifier(
                    repository, initialize=False
                ).verify_relationship_integrity(
                    scope, evidence["relationship_id"]
                )["verified"],
            ),
            IntegrityCheckAdapter(
                "query",
                lambda: MemoryQueryIntegrityVerifier(query_engine).verify(
                    scope, evidence["current_query_run_id"]
                ).verified,
            ),
            IntegrityCheckAdapter(
                "consolidation",
                lambda: MemoryConsolidationIntegrityVerifier(
                    repository, initialize=False
                ).verify_consolidation_integrity(
                    scope, evidence["consolidation_run_id"]
                ).verified,
            ),
            IntegrityCheckAdapter(
                "interpretation",
                lambda: InterpretationIntegrityVerifier(
                    repository, initialize=False
                ).verify_interpretation_integrity(
                    scope, evidence["interpretation_request_id"]
                ).verified,
            ),
            IntegrityCheckAdapter(
                "canonical_signal",
                lambda: CanonicalSignalIntegrityVerifier(
                    repository, initialize=False
                ).verify_canonical_signal_integrity(scope).verified,
            ),
            IntegrityCheckAdapter(
                "governance",
                lambda: MemoryGovernanceIntegrityVerifier(
                    repository, initialize=False
                ).verify(scope)["verified"],
            ),
            IntegrityCheckAdapter(
                "job",
                lambda: verify_runtime_jobs(
                    MemoryJobQueue(repository, initialize=False).store,
                    self._job_ids,
                ),
            ),
        ]
        return RuntimeIntegritySweep(adapters).run(mode="full_scope")

    @staticmethod
    def _plan_nodes(plan: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []

        def visit(node: dict[str, Any]) -> None:
            values.append(
                {
                    "node_type": node.get("Node Type"),
                    "relation_name": node.get("Relation Name"),
                    "index_name": node.get("Index Name"),
                    "actual_rows": node.get("Actual Rows"),
                    "plan_rows": node.get("Plan Rows"),
                }
            )
            for child in node.get("Plans", []):
                visit(child)

        if plan:
            visit(plan)
        return values

    @staticmethod
    def _truncate_jobs(repository: PostgresRuntimeRepository) -> None:
        with repository.connect() as connection:
            connection.execute(
                "TRUNCATE TABLE prmr_self_serve.prmr_memory_jobs CASCADE"
            )


__all__ = ["PostgresRuntimeMatrix"]
