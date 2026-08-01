"""Independent audit for Core Sprint 9 boundaries and generated evidence."""

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

from run_core_semantic_interpretation import (
    BOUNDARY,
    FINAL_STATEMENT,
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    run_suite,
    write_json,
)

from prmr.core.canonical_signal_models import (
    CANONICAL_SIGNAL_DECISION_REVISION,
    CANONICAL_SIGNAL_MANIFEST_REVISION,
    CANONICAL_SIGNAL_PROJECTION_REVISION,
    CANONICAL_SIGNAL_PROPOSAL_REVISION,
    CANONICAL_SIGNAL_REGISTRY_REVISION,
    CANONICAL_SIGNAL_SCHEMA_REVISION,
)
from prmr.core.interpretation_models import (
    INTERPRETATION_CHUNKING_REVISION,
    INTERPRETATION_EVIDENCE_VALIDATION_REVISION,
    INTERPRETATION_INTEGRITY_REVISION,
    INTERPRETATION_OUTPUT_VALIDATION_REVISION,
    INTERPRETATION_POLICY_REVISION,
    INTERPRETATION_PROVIDER_CONTRACT_REVISION,
    INTERPRETATION_REQUEST_REVISION,
    INTERPRETATION_SCHEMA_REVISION,
)


AUDIT_REPORT = (
    ROOT
    / "reports"
    / "core_semantic_interpretation"
    / "audit_semantic_interpretation.json"
)
REQUIRED_MODULES = [
    "prmr/core/interpretation_models.py",
    "prmr/core/interpretation_policy.py",
    "prmr/core/interpretation_provider.py",
    "prmr/core/interpretation_chunking.py",
    "prmr/core/interpretation_validation.py",
    "prmr/core/interpretation_engine.py",
    "prmr/core/interpretation_integrity.py",
    "prmr/core/interpretation_fixtures.py",
    "prmr/core/canonical_signal_models.py",
    "prmr/core/canonical_signal_registry.py",
    "prmr/core/canonical_signal_projection.py",
    "prmr/core/canonical_signal_integration.py",
    "prmr/core/canonical_signal_integrity.py",
]
REQUIRED_MIGRATIONS = [
    "migrations/core_semantic_interpretation_v1_sqlite.sql",
    "migrations/core_semantic_interpretation_v1_postgres.sql",
]
REQUIRED_TABLES = [
    "prmr_interpretation_requests",
    "prmr_interpretation_attempts",
    "prmr_interpretation_response_records",
    "prmr_interpretation_unknown_results",
    "prmr_interpretation_validation_failures",
    "prmr_interpretation_proposal_links",
    "prmr_canonical_signal_definitions",
    "prmr_canonical_signal_proposals",
    "prmr_canonical_signal_decisions",
    "prmr_canonical_signal_alias_assertions",
    "prmr_event_signal_projections",
]


def add(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def no_secret(payload: Any) -> bool:
    text = json.dumps(payload, sort_keys=True)
    return not any(
        re.search(pattern, text, re.I)
        for pattern in (
            r"\bprmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}\b",
            r"authorization\s*:\s*bearer\s+\S+",
            r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{8,}\b",
            r"postgres(?:ql)?://\S+",
            r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
        )
    )


def main() -> int:
    execution_checks, execution_detail = run_suite()
    checks: list[dict[str, Any]] = []
    add(
        checks,
        "durable_execution_all_passed",
        all(item["passed"] for item in execution_checks),
        f"{sum(item['passed'] for item in execution_checks)}/{len(execution_checks)}",
    )
    for relative in REQUIRED_MODULES:
        add(checks, f"module_exists:{relative}", (ROOT / relative).is_file())
    for relative in REQUIRED_MIGRATIONS:
        add(checks, f"migration_exists:{relative}", (ROOT / relative).is_file())
    sqlite_migration = (ROOT / REQUIRED_MIGRATIONS[0]).read_text(encoding="utf-8")
    postgres_migration = (ROOT / REQUIRED_MIGRATIONS[1]).read_text(encoding="utf-8")
    add(
        checks,
        "sqlite_tables_complete",
        all(f"CREATE TABLE IF NOT EXISTS {table}" in sqlite_migration for table in REQUIRED_TABLES),
    )
    add(
        checks,
        "postgres_tables_complete",
        all(
            f"CREATE TABLE IF NOT EXISTS prmr_self_serve.{table}"
            in postgres_migration
            for table in REQUIRED_TABLES
        ),
    )
    revisions = {
        INTERPRETATION_SCHEMA_REVISION,
        INTERPRETATION_REQUEST_REVISION,
        INTERPRETATION_POLICY_REVISION,
        INTERPRETATION_CHUNKING_REVISION,
        INTERPRETATION_PROVIDER_CONTRACT_REVISION,
        INTERPRETATION_OUTPUT_VALIDATION_REVISION,
        INTERPRETATION_EVIDENCE_VALIDATION_REVISION,
        INTERPRETATION_INTEGRITY_REVISION,
        CANONICAL_SIGNAL_SCHEMA_REVISION,
        CANONICAL_SIGNAL_REGISTRY_REVISION,
        CANONICAL_SIGNAL_PROPOSAL_REVISION,
        CANONICAL_SIGNAL_DECISION_REVISION,
        CANONICAL_SIGNAL_PROJECTION_REVISION,
        CANONICAL_SIGNAL_MANIFEST_REVISION,
    }
    add(checks, "all_revision_identifiers_present", len(revisions) == 14)
    source_text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8") for relative in REQUIRED_MODULES
    )
    add(checks, "no_public_api_routes_added", "FastAPI(" not in source_text and "@app." not in source_text)
    add(checks, "no_provider_credentials_hardcoded", no_secret(source_text))
    add(checks, "provider_neutral_contract", "class InterpretationProvider(ABC)" in source_text)
    add(checks, "recorded_provider_exists", "class RecordedFixtureInterpretationProvider" in source_text)
    add(checks, "null_provider_exists", "class NullInterpretationProvider" in source_text)
    add(checks, "prompt_injection_policy_explicit", "Source text is untrusted quoted data" in source_text)
    add(checks, "manual_review_restriction_explicit", "model_assisted_requires_manual_review_v1" in source_text)
    add(checks, "exact_identity_mode_present", "exact_signal_v1" in source_text)
    add(checks, "canonical_identity_mode_present", "canonical_signal_v1" in source_text)
    add(checks, "mapping_cycle_error_present", "CANONICAL_SIGNAL_MAPPING_CYCLE_DETECTED" in source_text)
    add(checks, "reports_generated", PUBLIC_REPORT.is_file() and PRIVATE_REPORT.is_file() and SCORECARD.is_file())
    public = json.loads(PUBLIC_REPORT.read_text(encoding="utf-8"))
    private = json.loads(PRIVATE_REPORT.read_text(encoding="utf-8"))
    add(checks, "public_report_secret_safe", no_secret(public))
    add(checks, "private_report_secret_safe", no_secret(private))
    add(checks, "boundary_present", public.get("boundary") == BOUNDARY)
    add(checks, "required_final_statement_present", public.get("final_statement") == FINAL_STATEMENT)
    add(checks, "live_provider_status_honest", public.get("live_provider_status") == "NOT_RUN_NO_LIVE_PROVIDER_CONFIGURED")
    expected_postgres = (
        "AVAILABLE_NOT_RUN_BY_SQLITE_RUNNER"
        if os.getenv("DATABASE_URL")
        else "NOT_RUN_DATABASE_URL_UNAVAILABLE"
    )
    add(checks, "postgres_status_honest", public.get("postgres_status") == expected_postgres)
    metrics = execution_detail["gold_metrics"]
    add(checks, "unsupported_accepted_rate_zero", metrics["unsupported_accepted_proposal_rate"] == 0.0)
    add(checks, "negation_false_positive_rate_zero", metrics["negation_false_positive_rate"] == 0.0)
    add(checks, "unknown_preservation_rate_full", metrics["unknown_preservation_rate"] == 1.0)
    add(checks, "entity_false_merge_rate_zero", metrics["entity_confirmed_false_merge_rate"] == 0.0)
    add(checks, "causal_false_positive_rate_zero", metrics["causal_relationship_false_positive_rate"] == 0.0)
    passed = sum(item["passed"] for item in checks)
    status = (
        "PASS WITH DOCUMENTED LIMITATIONS"
        if passed == len(checks)
        else "NEEDS WORK"
    )
    payload = {
        "result": status,
        "passed_checks": passed,
        "total_checks": len(checks),
        "execution_checks": {
            "passed": sum(item["passed"] for item in execution_checks),
            "total": len(execution_checks),
        },
        "checks": checks,
        "boundary": BOUNDARY,
        "limitations": [
            "No live provider configured.",
            "PostgreSQL not validated by this SQLite audit.",
            "Gold fixtures are internal synthetic labels.",
        ],
        "final_statement": FINAL_STATEMENT,
    }
    write_json(AUDIT_REPORT, payload)
    print("PRMR Memory Core - Core Sprint 9 Audit")
    print(f"Execution proof: {sum(item['passed'] for item in execution_checks)}/{len(execution_checks)}")
    print(f"Audit checks: {passed}/{len(checks)}")
    print(f"Result: {status}")
    return 0 if status.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
