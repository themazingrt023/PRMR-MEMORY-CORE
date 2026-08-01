"""Independent structure, evidence, privacy, and claim audit for Core Sprint 10."""

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

from prmr.core.memory_dependency_graph import STORAGE_CATALOG
from prmr.core.memory_governance_models import (
    MEMORY_CORRECTION_REQUEST_REVISION,
    MEMORY_DEPENDENCY_GRAPH_REVISION,
    MEMORY_ERASURE_TOMBSTONE_REVISION,
    MEMORY_EXPORT_MANIFEST_REVISION,
    MEMORY_EXPORT_SCHEMA_REVISION,
    MEMORY_GOVERNANCE_EXECUTION_REVISION,
    MEMORY_GOVERNANCE_PLAN_REVISION,
    MEMORY_GOVERNANCE_POLICY_REVISION,
    MEMORY_GOVERNANCE_SCHEMA_REVISION,
    MEMORY_GOVERNANCE_VERIFICATION_REVISION,
    MEMORY_PRESERVATION_HOLD_REVISION,
    MEMORY_RETENTION_POLICY_REVISION,
    MemoryGovernanceActionType,
    MemoryGovernanceTargetType,
)
from prmr.core.memory_governance_store import GOVERNANCE_TABLES


REPORT_DIR = ROOT / "reports" / "core_memory_governance"
AUDIT_REPORT = REPORT_DIR / "audit_memory_governance.json"
RUNNER_REPORT = REPORT_DIR / "public_memory_governance.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_governance.json"
ERASURE_REPORT = REPORT_DIR / "erasure_verification_memory_governance.json"
EXPORT_REPORT = REPORT_DIR / "export_integrity_memory_governance.json"
SECRET = re.compile(
    r"(?:prmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}|Authorization\s*:\s*Bearer\s+"
    r"[A-Za-z0-9._~+/=-]{8,}|github_pat_|ghp_|sk-|postgres(?:ql)?://)",
    re.I,
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    required_modules = [
        "memory_governance_models.py",
        "memory_governance_policy.py",
        "memory_governance_store.py",
        "memory_dependency_graph.py",
        "memory_governance_planner.py",
        "memory_governance_executor.py",
        "memory_governance_verifier.py",
        "memory_retention_service.py",
        "memory_preservation_hold.py",
        "memory_export_service.py",
        "memory_correction_requests.py",
        "memory_governance_integrity.py",
        "memory_governance_fixtures.py",
    ]
    for name in required_modules:
        add(checks, f"module_exists:{name}", (ROOT / "prmr" / "core" / name).is_file())

    required_runtime = [
        ROOT / "examples" / "run_core_memory_governance.py",
        ROOT / "examples" / "audit_core_memory_governance.py",
        ROOT / "examples" / "benchmark_core_memory_governance.py",
        ROOT / "migrations" / "core_memory_governance_v1_sqlite.sql",
        ROOT / "migrations" / "core_memory_governance_v1_postgres.sql",
    ]
    add(checks, "runners_and_migrations_exist", all(path.is_file() for path in required_runtime))
    add(
        checks,
        "required_governance_tables_declared",
        len(GOVERNANCE_TABLES) == 13
        and {
            "request",
            "graph",
            "plan",
            "plan_item",
            "execution",
            "execution_item",
            "verification",
            "tombstone",
            "hold",
            "retention",
            "export_request",
            "export_bundle",
            "correction",
        }
        == set(GOVERNANCE_TABLES),
    )
    revisions = {
        MEMORY_GOVERNANCE_SCHEMA_REVISION,
        MEMORY_GOVERNANCE_POLICY_REVISION,
        MEMORY_DEPENDENCY_GRAPH_REVISION,
        MEMORY_GOVERNANCE_PLAN_REVISION,
        MEMORY_GOVERNANCE_EXECUTION_REVISION,
        MEMORY_GOVERNANCE_VERIFICATION_REVISION,
        MEMORY_RETENTION_POLICY_REVISION,
        MEMORY_PRESERVATION_HOLD_REVISION,
        MEMORY_EXPORT_SCHEMA_REVISION,
        MEMORY_EXPORT_MANIFEST_REVISION,
        MEMORY_CORRECTION_REQUEST_REVISION,
        MEMORY_ERASURE_TOMBSTONE_REVISION,
    }
    add(checks, "all_revision_identifiers_are_explicit", len(revisions) == 12 and all(value.endswith("_v1") for value in revisions))
    add(checks, "all_required_action_types_exist", len(MemoryGovernanceActionType) == 13)
    add(checks, "all_required_target_types_exist", len(MemoryGovernanceTargetType) == 14)

    catalog_types = {item.node_type for item in STORAGE_CATALOG}
    for required in (
        "source",
        "segment",
        "candidate_memory",
        "admission",
        "event",
        "event_evolution",
        "entity",
        "relationship",
        "query_result",
        "consolidated_memory",
        "checkpoint",
        "interpretation_request",
        "canonical_signal_proposal",
        "event_signal_projection",
        "export_bundle",
        "export_request",
    ):
        add(checks, f"dependency_catalog_covers:{required}", required in catalog_types)

    reports_exist = all(
        path.is_file()
        for path in (RUNNER_REPORT, PRIVATE_REPORT, ERASURE_REPORT, EXPORT_REPORT)
    )
    add(checks, "runner_reports_exist", reports_exist)
    runner = read_json(RUNNER_REPORT) if reports_exist else {}
    private = read_json(PRIVATE_REPORT) if reports_exist else {}
    erasure = read_json(ERASURE_REPORT) if reports_exist else {}
    export = read_json(EXPORT_REPORT) if reports_exist else {}
    add(checks, "sqlite_runner_passed", runner.get("sqlite") == "PASS")
    add(checks, "runner_passed_all_checks", runner.get("passed_checks") == runner.get("total_checks") == 58)
    add(checks, "erasure_verification_evidence_passed", erasure.get("result") == "PASS" and erasure.get("verification_count", 0) >= 3)
    add(checks, "export_integrity_evidence_passed", export.get("result") == "PASS" and export.get("verification_count", 0) >= 1)
    add(checks, "postgres_is_not_falsely_claimed", runner.get("postgres") == "NOT_EXERCISED")
    add(checks, "external_backup_boundary_is_explicit", "unmanaged backups" in runner.get("boundary", ""))
    add(checks, "public_report_contains_no_secret_pattern", not SECRET.search(json.dumps(runner, sort_keys=True)))
    add(checks, "erasure_report_contains_no_secret_pattern", not SECRET.search(json.dumps(erasure, sort_keys=True)))
    add(checks, "export_report_contains_no_secret_pattern", not SECRET.search(json.dumps(export, sort_keys=True)))
    add(
        checks,
        "required_final_statement_recorded",
        "Core Sprint 10 establishes Memory Governance" in private.get("required_final_statement", "")
        and "formal compliance certification remain outside this sprint"
        in private.get("required_final_statement", ""),
    )

    executor_source = (ROOT / "prmr" / "core" / "memory_governance_executor.py").read_text(encoding="utf-8")
    graph_source = (ROOT / "prmr" / "core" / "memory_dependency_graph.py").read_text(encoding="utf-8")
    correction_source = (ROOT / "prmr" / "core" / "memory_correction_requests.py").read_text(encoding="utf-8")
    add(checks, "physical_delete_is_implemented", "DELETE FROM" in executor_source)
    add(checks, "restart_recovery_is_implemented", "recover_incomplete_governance_executions" in executor_source)
    add(checks, "shared_evidence_recompute_is_implemented", "_recompute_surviving_evidence" in executor_source)
    add(checks, "unscoped_children_require_owned_parent", "owned_keys" in graph_source and "unscoped" in graph_source)
    add(checks, "correction_routes_existing_operations", all(name in correction_source for name in ("correct_candidate", "correct_admitted_memory", "retract_relationship", "retract_signal_mapping", "retract_alias")))
    add(checks, "no_frontend_or_public_route_created_by_sprint", not any("frontend" in str(path) or "api_server" in path.name for path in required_runtime))

    failed = [item for item in checks if not item["passed"]]
    status = "NEEDS WORK" if failed else "PASS WITH DOCUMENTED LIMITATIONS"
    report = {
        "version": "core_sprint_10",
        "result": status,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "sqlite_runtime": "PASS" if not failed else "NEEDS_WORK",
        "postgres_runtime": (
            "DATABASE_URL_PRESENT_BUT_NOT_EXERCISED_BY_THIS_AUDIT"
            if os.getenv("DATABASE_URL")
            else "NOT_EXERCISED_DATABASE_URL_UNAVAILABLE"
        ),
        "limitations": [
            "PostgreSQL runtime proof is absent.",
            "External backup and provider erasure is outside the active database boundary.",
            "Multi-process and production-scale cascade validation remains future work.",
        ],
    }
    AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PRMR Memory Core - Core Sprint 10 Audit")
    print(f"Passed checks: {report['passed_checks']}/{report['total_checks']}")
    print(f"Result: {status}")
    if failed:
        for item in failed:
            print(f"FAIL: {item['name']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
