"""Run Core Sprint 12 against durable SQLite and guarded PostgreSQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.memory_quality_adversarial import adversarial_results  # noqa: E402
from prmr.core.memory_quality_backend_parity import compare_backend_results  # noqa: E402
from prmr.core.memory_quality_corpus import load_corpus, write_corpus  # noqa: E402
from prmr.core.memory_quality_integrity import (  # noqa: E402
    verify_memory_quality_corpus_integrity,
    verify_memory_quality_run_integrity,
)
from prmr.core.memory_quality_mutations import run_mutation_suite  # noqa: E402
from prmr.core.memory_quality_policy import (  # noqa: E402
    MEMORY_QUALITY_REPORT_REVISION,
    PUBLIC_FORBIDDEN_PATTERNS,
)
from prmr.core.memory_quality_reports import build_scorecard, write_json  # noqa: E402
from prmr.core.memory_quality_runner import MemoryQualityBackendRunner  # noqa: E402
from prmr.core.runtime_database import PostgresRuntimeRepository, RuntimeDatabaseConfig  # noqa: E402
from prmr.core.runtime_postgres_validation import (  # noqa: E402
    TEST_DATABASE_ENV,
    reset_postgres_test_application_schema,
    verify_postgres_test_environment,
)
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093  # noqa: E402


CORPUS_DIR = ROOT / "benchmarks" / "memory_quality_v1"
REPORT_DIR = ROOT / "reports" / "core_memory_quality"
SQLITE_PATH = REPORT_DIR / "memory_quality.sqlite"
BOUNDARY = (
    "Internal deterministic engineering evidence from a versioned synthetic corpus. "
    "This is not scientific validation, human-memory equivalence, external peer review, "
    "production certification, legal approval, or universal performance evidence."
)


def main() -> int:
    started = time.perf_counter()
    tracemalloc.start()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    corpus_started = time.perf_counter()
    manifest = write_corpus(CORPUS_DIR)
    corpus_integrity = verify_memory_quality_corpus_integrity(CORPUS_DIR)
    manifest, cases = load_corpus(CORPUS_DIR)
    corpus_ms = round((time.perf_counter() - corpus_started) * 1000, 3)
    write_json(REPORT_DIR / "corpus_manifest_memory_quality.json", manifest)

    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    sqlite_repository = SelfServeRepositoryV093(SQLITE_PATH)
    sqlite_runner = MemoryQualityBackendRunner(
        repository=sqlite_repository,
        backend="sqlite",
        corpus_manifest=manifest,
        cases=cases,
        restart_repository=lambda: SelfServeRepositoryV093(SQLITE_PATH),
    )
    sqlite_result = sqlite_runner.run()
    write_json(REPORT_DIR / "case_results_sqlite.json", sqlite_result)

    database_url = os.getenv(TEST_DATABASE_ENV, "").strip()
    if not database_url:
        return _blocked(
            manifest, corpus_integrity, sqlite_result,
            "POSTGRES_TEST_DATABASE_URL_MISSING", corpus_ms,
        )
    environment = verify_postgres_test_environment(database_url)
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        database_url, autocommit=True, row_factory=dict_row, prepare_threshold=None
    ) as connection:
        reset = reset_postgres_test_application_schema(connection)
    postgres_runner = MemoryQualityBackendRunner(
        repository=PostgresRuntimeRepository(
            database_url,
            config=RuntimeDatabaseConfig(
                pool_minimum=1, pool_maximum=10,
                statement_timeout_ms=300_000,
                lock_timeout_ms=60_000,
                idle_transaction_timeout_ms=300_000,
            ),
        ),
        backend="postgres",
        corpus_manifest=manifest,
        cases=cases,
        restart_repository=lambda: PostgresRuntimeRepository(
            database_url,
            config=RuntimeDatabaseConfig(
                pool_minimum=1, pool_maximum=10,
                statement_timeout_ms=300_000,
                lock_timeout_ms=60_000,
                idle_transaction_timeout_ms=300_000,
            ),
        ),
    )
    postgres_result = postgres_runner.run()
    close = getattr(postgres_runner.repository, "close", None)
    if callable(close):
        close()
    write_json(REPORT_DIR / "case_results_postgres.json", postgres_result)

    parity_started = time.perf_counter()
    parity = compare_backend_results(
        sqlite_result["case_results"], postgres_result["case_results"]
    )
    parity_ms = round((time.perf_counter() - parity_started) * 1000, 3)
    mutations_started = time.perf_counter()
    mutations = run_mutation_suite(
        cases, sqlite_runner.actual_by_case, mutation_test_mode=True
    )
    mutation_ms = round((time.perf_counter() - mutations_started) * 1000, 3)
    adversarial = adversarial_results(
        cases, sqlite_result["case_results"], postgres_result["case_results"]
    )
    sqlite_integrity = verify_memory_quality_run_integrity(
        corpus_manifest=manifest,
        run=sqlite_result["run"],
        case_results=sqlite_result["case_results"],
    )
    postgres_integrity = verify_memory_quality_run_integrity(
        corpus_manifest=manifest,
        run=postgres_result["run"],
        case_results=postgres_result["case_results"],
    )

    metrics = {
        "revision": "memory_quality_metrics_v1",
        "sqlite": sqlite_result["run"]["metric_results"],
        "postgres": postgres_result["run"]["metric_results"],
    }
    gates = {
        "sqlite": sqlite_result["quality_gates"],
        "postgres": postgres_result["quality_gates"],
    }
    all_gates = gates["sqlite"] + gates["postgres"]
    required_pass = all((
        corpus_integrity["verified"],
        sqlite_result["run"]["run_status"] == "passed",
        postgres_result["run"]["run_status"] == "passed",
        all(item["passed"] for item in all_gates),
        parity["verified"],
        mutations["verified"],
        adversarial["verified"],
        sqlite_integrity["verified"],
        postgres_integrity["verified"],
        sqlite_result["restart_reproducibility"]["verified"],
        postgres_result["restart_reproducibility"]["verified"],
        environment.guard_verified,
        reset["guard_preserved"],
    ))
    status = "PASS WITH DOCUMENTED LIMITATIONS" if required_pass else "NEEDS_WORK"
    limitations = [
        "Recorded deterministic interpretation provider used; live-provider quality was not evaluated.",
        "No external expert review or peer review was performed.",
        "The optional extended 10,000-case corpus was not run.",
        "Lifecycle-domain cases reuse one labelled complete fixture per backend; case counts are assertion coverage, not independent customer deployments.",
        "PostgreSQL evidence is limited to the verified isolated test database.",
    ]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    benchmark = {
        "corpus_load_ms": corpus_ms,
        "sqlite_run_ms": sqlite_runner.performance.get("total_ms"),
        "postgres_run_ms": postgres_runner.performance.get("total_ms"),
        "mutation_suite_ms": mutation_ms,
        "parity_comparison_ms": parity_ms,
        "total_ms": round((time.perf_counter() - started) * 1000, 3),
        "sqlite_storage_bytes": SQLITE_PATH.stat().st_size,
        "peak_traced_memory_bytes": peak,
        "observations_only": True,
    }
    public = {
        "version": "core_sprint_12",
        "result": status,
        "corpus_revision": manifest["corpus_revision"],
        "case_count": manifest["case_count"],
        "assertion_count": manifest["assertion_count"],
        "domain_metrics": metrics,
        "quality_gate_summary": {
            "total": len(all_gates),
            "passed": sum(item["passed"] for item in all_gates),
            "failed": sum(not item["passed"] for item in all_gates),
        },
        "critical_mutations": {
            "total": mutations["critical_mutation_count"],
            "detected": mutations["detected_count"],
        },
        "backend_parity": {
            "verified": parity["verified"],
            "compared_case_count": parity["compared_case_count"],
            "mismatch_count": parity["mismatch_count"],
        },
        "adversarial_verified": adversarial["verified"],
        "restart_reproducibility": {
            "sqlite": sqlite_result["restart_reproducibility"]["verified"],
            "postgres": postgres_result["restart_reproducibility"]["verified"],
        },
        "limitations": limitations,
        "boundary": BOUNDARY,
        "database_url_recorded": False,
    }
    private = {
        "version": "core_sprint_12",
        "result": status,
        "corpus_integrity": corpus_integrity,
        "sqlite_integrity": sqlite_integrity,
        "postgres_integrity": postgres_integrity,
        "environment_status": environment.status,
        "guard_preserved": reset["guard_preserved"],
        "baseline_actual_sqlite": sqlite_runner.actual_by_case,
        "database_url_recorded": False,
        "report_revision": MEMORY_QUALITY_REPORT_REVISION,
    }
    public_text = json.dumps(public, sort_keys=True).lower()
    public["public_redaction_verified"] = not any(
        pattern in public_text for pattern in PUBLIC_FORBIDDEN_PATTERNS
    )

    write_json(REPORT_DIR / "metrics_memory_quality.json", metrics)
    write_json(REPORT_DIR / "quality_gates_memory_quality.json", gates)
    write_json(REPORT_DIR / "mutation_results_memory_quality.json", mutations)
    write_json(REPORT_DIR / "backend_parity_memory_quality.json", parity)
    write_json(REPORT_DIR / "adversarial_results_memory_quality.json", adversarial)
    write_json(REPORT_DIR / "public_memory_quality.json", public)
    write_json(REPORT_DIR / "private_internal_memory_quality.json", private)
    write_json(REPORT_DIR / "benchmark_memory_quality.json", benchmark)
    write_json(REPORT_DIR / "audit_memory_quality.json", {"status": "NOT_RUN_RUN_INDEPENDENT_AUDIT"})
    (REPORT_DIR / "scorecard_memory_quality.md").write_text(
        build_scorecard(
            status=status,
            metrics=metrics["postgres"],
            gates=gates["postgres"],
            mutations=mutations,
            parity=parity,
            limitations=limitations,
        ),
        encoding="utf-8",
    )

    print("PRMR Memory Core - Core Sprint 12 Memory Quality Benchmark")
    print(f"Corpus: {manifest['case_count']} cases / {manifest['assertion_count']} assertions")
    print(f"Corpus integrity: {'PASS' if corpus_integrity['verified'] else 'FAIL'}")
    print(f"SQLite: {sqlite_result['run']['passed_case_count']}/{sqlite_result['run']['case_count']} cases")
    print(f"PostgreSQL: {postgres_result['run']['passed_case_count']}/{postgres_result['run']['case_count']} cases")
    print(f"Backend parity: {'PASS' if parity['verified'] else 'FAIL'}")
    print(f"Critical mutations detected: {mutations['detected_count']}/{mutations['critical_mutation_count']}")
    print(f"Result: {status}")
    return 0 if required_pass else 1


def _blocked(
    manifest: dict, corpus_integrity: dict, sqlite_result: dict,
    reason: str, corpus_ms: float,
) -> int:
    public = {
        "version": "core_sprint_12",
        "result": "BLOCKED",
        "reason": reason,
        "case_count": manifest["case_count"],
        "assertion_count": manifest["assertion_count"],
        "sqlite_status": sqlite_result["run"]["run_status"],
        "postgres_status": "NOT_RUN",
        "boundary": BOUNDARY,
        "database_url_recorded": False,
    }
    write_json(REPORT_DIR / "public_memory_quality.json", public)
    write_json(REPORT_DIR / "private_internal_memory_quality.json", {
        "result": "BLOCKED", "reason": reason,
        "corpus_integrity": corpus_integrity,
        "database_url_recorded": False,
    })
    write_json(REPORT_DIR / "benchmark_memory_quality.json", {
        "corpus_load_ms": corpus_ms, "postgres_run": "NOT_RUN"
    })
    print("PRMR Memory Core - Core Sprint 12 Memory Quality Benchmark")
    print(f"Corpus: {manifest['case_count']} cases / {manifest['assertion_count']} assertions")
    print(f"SQLite: {sqlite_result['run']['run_status']}")
    print(f"PostgreSQL: BLOCKED ({reason})")
    print("Result: BLOCKED")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
