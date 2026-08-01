"""Independent audit for Core Sprint 7 deterministic memory querying."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.memory_query_models import (
    MEMORY_CHANGE_PROJECTION_REVISION,
    MEMORY_EVIDENCE_BUNDLE_REVISION,
    MEMORY_EXPLANATION_REVISION,
    MEMORY_QUERY_INTEGRITY_REVISION,
    MEMORY_QUERY_PAGINATION_REVISION,
    MEMORY_QUERY_PLANNER_REVISION,
    MEMORY_QUERY_POLICY_REVISION,
    MEMORY_QUERY_RESULT_REVISION,
    MEMORY_QUERY_SCHEMA_REVISION,
    MEMORY_TIMELINE_REVISION,
    EvidenceCompletenessStatus,
    MemoryEvidenceBundle,
    MemoryEvidenceItem,
    MemoryExplanation,
    MemoryQueryMode,
    MemoryQueryPlan,
    MemoryQueryRequest,
    MemoryQueryResult,
    MemoryQueryResultStatus,
    MemoryQueryRun,
    MemoryQueryType,
)


REPORT_DIR = ROOT / "reports" / "core_memory_query"
PUBLIC_REPORT = REPORT_DIR / "public_memory_query.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_query.json"
SCORECARD = REPORT_DIR / "scorecard_memory_query.md"


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def no_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def main() -> int:
    checks: list[dict[str, Any]] = []
    runner = subprocess.run(
        [sys.executable, "examples/run_core_memory_query.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    add(
        checks,
        "durable_runner_passes",
        runner.returncode == 0
        and "Passed checks: 54/54" in runner.stdout
        and "PASS WITH DOCUMENTED LIMITATIONS" in runner.stdout,
        {
            "return_code": runner.returncode,
            "stdout_tail": runner.stdout.strip().splitlines()[-5:],
            "stderr_tail": runner.stderr.strip().splitlines()[-5:],
        },
    )

    required_files = (
        "prmr/core/memory_query_models.py",
        "prmr/core/memory_query_policy.py",
        "prmr/core/memory_query_planner.py",
        "prmr/core/memory_query_engine.py",
        "prmr/core/memory_query_results.py",
        "prmr/core/memory_evidence_bundle.py",
        "prmr/core/memory_explanation.py",
        "prmr/core/memory_query_integrity.py",
        "prmr/core/memory_query_fixtures.py",
        "migrations/core_memory_query_v1_sqlite.sql",
        "migrations/core_memory_query_v1_postgres.sql",
        "examples/run_core_memory_query.py",
        "examples/audit_core_memory_query.py",
    )
    add(
        checks,
        "required_files_exist",
        all((ROOT / path).is_file() for path in required_files),
    )
    add(
        checks,
        "typed_models_exist",
        all(
            item is not None
            for item in (
                MemoryQueryRequest,
                MemoryQueryPlan,
                MemoryQueryRun,
                MemoryQueryResult,
                MemoryEvidenceBundle,
                MemoryEvidenceItem,
                MemoryExplanation,
            )
        ),
    )
    add(
        checks,
        "query_types_complete",
        len(MemoryQueryType) == 22
        and all(
            value in {item.value for item in MemoryQueryType}
            for value in (
                "current_state",
                "memory_by_phase",
                "changes_between",
                "event_timeline",
                "signal_history",
                "recurrence",
                "re_emergence",
                "open_conflicts",
                "resolved_conflicts",
                "evidence_for_event",
                "evidence_for_current_state",
                "provenance_trace",
                "state_as_known_at",
                "state_at_valid_time",
                "bitemporal_state",
                "entity_state",
                "entity_history",
                "relationship_state",
                "relationship_history",
                "recoverability_explanation",
                "continuity_packet",
                "unknown_information",
            )
        ),
    )
    add(
        checks,
        "result_statuses_complete",
        {item.value for item in MemoryQueryResultStatus}
        == {
            "answered",
            "partial",
            "unknown",
            "conflicted",
            "no_data",
            "not_applicable",
            "truncated",
        },
    )
    add(
        checks,
        "evidence_statuses_complete",
        {item.value for item in EvidenceCompletenessStatus}
        == {
            "complete",
            "partial",
            "unavailable",
            "legacy_without_source",
            "integrity_failed",
            "truncated",
        },
    )
    add(
        checks,
        "strict_mode_only_active",
        MemoryQueryMode.DETERMINISTIC_STRICT_V1.value
        == "deterministic_strict_v1",
    )
    revisions = (
        MEMORY_QUERY_SCHEMA_REVISION,
        MEMORY_QUERY_POLICY_REVISION,
        MEMORY_QUERY_PLANNER_REVISION,
        MEMORY_QUERY_RESULT_REVISION,
        MEMORY_EVIDENCE_BUNDLE_REVISION,
        MEMORY_EXPLANATION_REVISION,
        MEMORY_TIMELINE_REVISION,
        MEMORY_CHANGE_PROJECTION_REVISION,
        MEMORY_QUERY_INTEGRITY_REVISION,
        MEMORY_QUERY_PAGINATION_REVISION,
    )
    add(checks, "revision_identifiers_exact", all(item.endswith("_v1") for item in revisions))

    engine_source = read("prmr/core/memory_query_engine.py")
    handlers = {
        f"_query_{item.value}" for item in MemoryQueryType
    }
    add(
        checks,
        "every_query_type_has_handler",
        all(f"def {handler}" in engine_source for handler in handlers),
    )
    policy_source = read("prmr/core/memory_query_policy.py")
    add(
        checks,
        "query_policy_limits_enforced",
        all(
            token in policy_source
            for token in (
                "HARD_MAXIMUM_RESULTS = 5_000",
                "HARD_MAXIMUM_EVIDENCE_ITEMS = 1_000",
                "HARD_MAXIMUM_PREVIEW_CHARACTERS = 2_000",
            )
        ),
    )
    planner_source = read("prmr/core/memory_query_planner.py")
    add(
        checks,
        "planner_scope_and_cursor_checks_present",
        all(
            token in planner_source
            for token in (
                "MEMORY_QUERY_SCOPE_DENIED",
                "MEMORY_QUERY_CURSOR_SCOPE_MISMATCH",
                "MEMORY_QUERY_SEMANTIC_MODE_UNAVAILABLE",
                "scope_fingerprint",
            )
        ),
    )
    add(
        checks,
        "no_external_or_model_dependency",
        not any(
            token in (engine_source + planner_source).lower()
            for token in (
                "import openai",
                "import langchain",
                "import requests",
                "import httpx",
                "embedding",
                "vector_search",
            )
        ),
    )
    add(
        checks,
        "no_public_route_added",
        "/v1/query" not in engine_source
        and "fastapi" not in engine_source.lower(),
    )

    sqlite_migration = read("migrations/core_memory_query_v1_sqlite.sql")
    postgres_migration = read("migrations/core_memory_query_v1_postgres.sql")
    required_tables = (
        "prmr_memory_query_runs",
        "prmr_memory_query_results",
        "prmr_memory_evidence_bundles",
        "prmr_memory_query_evidence_items",
        "prmr_memory_explanations",
        "prmr_memory_query_result_comparisons",
    )
    add(
        checks,
        "sqlite_migration_complete",
        all(name in sqlite_migration for name in required_tables),
    )
    add(
        checks,
        "postgres_migration_complete",
        all(name in postgres_migration for name in required_tables),
    )
    add(
        checks,
        "repositories_initialize_query_schema",
        "initialize_sqlite_memory_query_schema" in read(
            "prmr/product/self_serve_repository_v093.py"
        )
        and "initialize_postgres_memory_query_schema" in read(
            "prmr/product/self_serve_repository_postgres_v0941.py"
        ),
    )
    add(
        checks,
        "query_store_uses_transactions",
        "BEGIN IMMEDIATE" in engine_source
        and "_persist_completed" in engine_source,
    )
    add(
        checks,
        "query_read_mode_preserved",
        "persist_dynamics=False" in engine_source
        and "persist=False" in engine_source,
    )
    add(
        checks,
        "historical_visibility_guard_present",
        "_require_event_visible_at_boundary" in engine_source
        and "projection.system_known_from > plan.known_at" in engine_source,
    )

    public = json.loads(PUBLIC_REPORT.read_text(encoding="utf-8"))
    private = json.loads(PRIVATE_REPORT.read_text(encoding="utf-8"))
    scorecard = SCORECARD.read_text(encoding="utf-8")
    add(
        checks,
        "runner_checks_all_pass",
        private["passed_checks"] == private["total_checks"] == 54
        and not private["failed_checks"],
    )
    add(
        checks,
        "restart_and_integrity_proven",
        private["private_execution_trace"]["database_close_reopen"]
        and private["private_execution_trace"]["integrity_checks"]["verified"],
    )
    add(
        checks,
        "authoritative_memory_unchanged_by_queries",
        private["private_execution_trace"][
            "authoritative_counts_before_queries"
        ]
        == private["private_execution_trace"][
            "authoritative_counts_after_queries"
        ],
    )
    add(
        checks,
        "performance_observations_present",
        set(public["performance_observations"]) == {"100", "1000", "10000"}
        and all(
            item["scope"] == "local_synthetic_sqlite"
            for item in public["performance_observations"].values()
        ),
    )
    add(
        checks,
        "postgres_status_honest",
        (
            public["postgresql"] == "not_exercised_database_url_unavailable"
            if not os.getenv("DATABASE_URL")
            else public["postgresql"]
            != "not_exercised_database_url_unavailable"
        ),
    )
    add(checks, "public_report_secret_safe", no_secret(public))
    add(
        checks,
        "boundary_and_limitations_present",
        "Internal deterministic synthetic" in public["boundary"]
        and "Natural-language" in " ".join(public["limitations"])
        and "PASS WITH DOCUMENTED LIMITATIONS" in scorecard,
    )

    failed = [item for item in checks if not item["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failed else "NEEDS WORK"
    audit = {
        "result": result,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "checks": checks,
    }
    public["audit"] = {
        key: value for key, value in audit.items() if key != "checks"
    }
    private["audit"] = audit
    PUBLIC_REPORT.write_text(
        json.dumps(public, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    PRIVATE_REPORT.write_text(
        json.dumps(private, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with SCORECARD.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## Independent Audit\n\n"
            f"- Result: **{result}**\n"
            f"- Checks: **{len(checks) - len(failed)}/{len(checks)}**\n"
        )
    print("PRMR Memory Core - Core Sprint 7 Memory Query Audit")
    print(f"Result: {result}")
    print(f"Passed checks: {len(checks) - len(failed)}/{len(checks)}")
    print(
        "PostgreSQL:",
        public["postgresql"],
    )
    if failed:
        print("Failed:", ", ".join(item["name"] for item in failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
