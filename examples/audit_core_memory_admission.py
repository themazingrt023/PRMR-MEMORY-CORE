"""Independent runtime, storage, and regression audit for Core Sprint 3."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_core_memory_admission import (
    BOUNDARY,
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    REQUIRED_FINAL_STATEMENT,
    SCORECARD,
    build_scorecard,
    run_all,
    write_json,
)


CORE_FILES = [
    ROOT / "prmr" / "core" / "admission_models.py",
    ROOT / "prmr" / "core" / "admission_policy.py",
    ROOT / "prmr" / "core" / "admission_bridge.py",
    ROOT / "prmr" / "core" / "admission_service.py",
    ROOT / "prmr" / "core" / "admission_integrity.py",
    ROOT / "prmr" / "core" / "admission_fixtures.py",
]
MIGRATIONS = [
    ROOT / "migrations" / "core_memory_admission_v1_sqlite.sql",
    ROOT / "migrations" / "core_memory_admission_v1_postgres.sql",
]


def add(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def command(args: list[str], timeout: int = 420) -> tuple[bool, str]:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return completed.returncode == 0, output[-3000:]


def report_contains_secret(value: Any) -> bool:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, ensure_ascii=False)
    )
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+(?!\[REDACTED)[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def main() -> int:
    public, private, runner_checks = run_all()
    checks = list(runner_checks)
    add(
        checks,
        "all_admission_core_modules_exist",
        all(path.exists() for path in CORE_FILES),
    )
    add(
        checks,
        "sqlite_and_postgres_admission_migrations_exist",
        all(path.exists() for path in MIGRATIONS),
    )
    texts = {path.name: path.read_text(encoding="utf-8") for path in CORE_FILES}
    models = texts["admission_models.py"]
    policy = texts["admission_policy.py"]
    bridge = texts["admission_bridge.py"]
    service = texts["admission_service.py"]
    integrity = texts["admission_integrity.py"]
    candidate_models = (
        ROOT / "prmr" / "core" / "candidate_models.py"
    ).read_text(encoding="utf-8")
    source_ledger = (ROOT / "prmr" / "core" / "source_ledger.py").read_text(
        encoding="utf-8"
    )
    api_server = (ROOT / "prmr" / "product" / "api_server_v094.py").read_text(
        encoding="utf-8"
    )

    add(
        checks,
        "typed_memory_admission_decision_exists",
        "class MemoryAdmissionDecision" in models,
    )
    add(
        checks,
        "typed_admitted_memory_link_exists",
        "class AdmittedMemoryLink" in models,
    )
    add(
        checks,
        "typed_memory_admission_policy_exists",
        "class MemoryAdmissionPolicy" in policy,
    )
    add(
        checks,
        "four_decision_types_exist",
        all(f'= "{value}"' in models for value in ("accept", "reject", "defer", "correct")),
    )
    add(
        checks,
        "candidate_status_expansion_exists",
        all(
            f'= "{value}"' in candidate_models
            for value in (
                "pending_review",
                "deferred",
                "rejected",
                "accepted",
                "corrected",
                "duplicate",
                "invalidated",
            )
        ),
    )
    revisions = (
        "memory_admission_v1",
        "memory_admission_policy_v1",
        "candidate_event_bridge_v1",
        "memory_admission_integrity_v1",
        "admitted_event_metadata_v1",
        "candidate_correction_v1",
    )
    add(
        checks,
        "all_admission_revisions_are_explicit",
        all(revision in models for revision in revisions),
    )
    required_methods = (
        "accept_candidate",
        "reject_candidate",
        "defer_candidate",
        "correct_candidate",
        "run_admission_policy",
        "get_admission",
        "list_admissions",
        "get_admitted_memory_link",
        "get_admitted_event",
        "build_continuity_packet",
        "verify_admission_integrity",
        "trace_admitted_memory_origin",
        "recover_incomplete_admissions",
    )
    add(
        checks,
        "required_admission_service_methods_exist",
        all(f"def {name}" in service for name in required_methods),
    )
    add(
        checks,
        "manual_and_safe_auto_policies_exist",
        "manual_strict_v1" in policy and "safe_explicit_auto_v1" in policy,
    )
    add(
        checks,
        "auto_policy_threshold_is_095",
        "minimum_extraction_confidence: float = 0.95" in policy,
    )
    add(
        checks,
        "auto_policy_blocks_inferred_unknown_and_quotes",
        all(
            token in policy
            for token in (
                '{"inferred", "unknown"}',
                "quoted_statement_requires_manual_review",
                "source_retention_not_standard",
            )
        ),
    )
    add(
        checks,
        "bridge_uses_existing_canonical_normalizer",
        "PRMRControlledAlphaAPI" in bridge
        and ".normalize_event(" in bridge
        and ".build_theory_packet(" in bridge
        and ".deterministic_packet_id(" in bridge,
    )
    add(
        checks,
        "bridge_uses_stable_sha256_event_identity",
        "deterministic_event_id" in bridge
        and "sha256_text" in bridge
        and "evt_mem_" in bridge
        and "uuid4" not in bridge,
    )
    add(
        checks,
        "source_time_precedes_ingest_fallback",
        bridge.index("candidate.proposed_occurred_at")
        < bridge.index("source.occurred_at or source.ingested_at"),
    )
    add(
        checks,
        "event_metadata_excludes_source_content",
        '"source_id": source.source_id' in bridge
        and not re.search(r'"source_content"\s*:', bridge)
        and not re.search(r'"evidence_text"\s*:', bridge),
    )
    add(
        checks,
        "engine_contains_no_http_calls",
        all(
            token not in (service + bridge + policy + integrity)
            for token in ("requests.", "httpx.", "urllib.request", "aiohttp")
        ),
    )
    add(
        checks,
        "no_public_admission_routes_added",
        "/v1/admission" not in api_server
        and "/v1/candidates" not in api_server
        and "/v1/sources" not in api_server,
    )
    add(
        checks,
        "source_deletion_protection_exists",
        "SOURCE_HAS_ADMITTED_MEMORY" in source_ledger
        and "skipped_admitted_source_count" in source_ledger,
    )
    add(
        checks,
        "accepted_event_supersession_not_falsely_implemented",
        "ADMISSION_ACCEPTED_CANDIDATE_REQUIRES_SUPERSESSION" in service
        and "supersede_event" not in service,
    )

    sqlite_migration = MIGRATIONS[0].read_text(encoding="utf-8")
    postgres_migration = MIGRATIONS[1].read_text(encoding="utf-8")
    for table in (
        "prmr_memory_admission_decisions",
        "prmr_admitted_memory_links",
    ):
        add(
            checks,
            f"sqlite_migration_contains_{table}",
            table in sqlite_migration,
        )
        add(
            checks,
            f"postgres_migration_contains_{table}",
            table in postgres_migration,
        )
    add(
        checks,
        "link_uniqueness_constraints_exist",
        all(
            token in sqlite_migration and token in postgres_migration
            for token in (
                "admission_id TEXT NOT NULL UNIQUE",
                "candidate_id TEXT NOT NULL UNIQUE",
                "admitted_event_id TEXT NOT NULL UNIQUE",
            )
        ),
    )
    add(
        checks,
        "decision_idempotency_is_scope_unique",
        "UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest)"
        in sqlite_migration
        and "UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest)"
        in postgres_migration,
    )

    syntax_files = [
        str(path)
        for path in CORE_FILES
        + MIGRATIONS[:0]
        + [
            ROOT / "examples" / "run_core_memory_admission.py",
            ROOT / "examples" / "audit_core_memory_admission.py",
            ROOT / "prmr" / "core" / "candidate_engine.py",
            ROOT / "prmr" / "core" / "source_ledger.py",
            ROOT / "prmr" / "product" / "self_serve_repository_v093.py",
            ROOT
            / "prmr"
            / "product"
            / "self_serve_repository_postgres_v0941.py",
        ]
    ]
    syntax_ok, syntax_output = command(
        [sys.executable, "-m", "py_compile", *syntax_files]
    )
    add(checks, "python_syntax_and_import_validation", syntax_ok, syntax_output)

    regression_commands = {
        "core_sprint_1_runner": [
            sys.executable,
            "examples/run_core_source_ledger_provenance.py",
        ],
        "core_sprint_1_audit": [
            sys.executable,
            "examples/audit_core_source_ledger_provenance.py",
        ],
        "core_sprint_2_runner": [
            sys.executable,
            "examples/run_core_candidate_memory_engine.py",
        ],
        "core_sprint_2_audit": [
            sys.executable,
            "examples/audit_core_candidate_memory_engine.py",
        ],
        "v084_multi_client_isolation": [
            sys.executable,
            "examples/audit_v084_multi_client_isolation.py",
        ],
        "v093_durable_storage": [
            sys.executable,
            "examples/audit_v093_durable_self_serve_storage.py",
        ],
        "v098_external_event_contract": [
            sys.executable,
            "examples/audit_v098_external_event_contract.py",
        ],
        "v099_continuity_runtime_and_packet_privacy": [
            sys.executable,
            "examples/audit_v099_theory_to_product_packet.py",
        ],
        "entity_scope_packet_benchmark": [
            sys.executable,
            "examples/benchmark_entity_scoped_packets.py",
        ],
    }
    regression_outputs: dict[str, str] = {}
    for name, args in regression_commands.items():
        ok, output = command(args)
        regression_outputs[name] = output
        add(checks, f"existing_{name}_regression", ok, output)

    public = {
        **public,
        "files": {
            "core_modules": [
                str(path.relative_to(ROOT)).replace("\\", "/")
                for path in CORE_FILES
            ],
            "migrations": [
                str(path.relative_to(ROOT)).replace("\\", "/")
                for path in MIGRATIONS
            ],
            "runner": "examples/run_core_memory_admission.py",
            "audit": "examples/audit_core_memory_admission.py",
        },
        "audit_scope": {
            "durable_sqlite_restart_exercised": True,
            "accept_reject_defer_correct_exercised": True,
            "atomic_rollback_exercised": True,
            "concurrent_idempotency_exercised": True,
            "review_order_determinism_exercised": True,
            "source_deletion_protection_exercised": True,
            "full_origin_trace_exercised": True,
            "existing_engine_regressions_exercised": True,
        },
    }
    private = {
        **private,
        **public,
        "public_safe": False,
        "checks": checks,
        "command_outputs": regression_outputs,
    }
    add(
        checks,
        "public_report_contains_no_secret_patterns",
        not report_contains_secret(public),
    )
    add(
        checks,
        "private_report_contains_no_secret_patterns",
        not report_contains_secret(private),
    )
    failures = [item for item in checks if not item["passed"]]
    if failures or public["postgres_result"] == "NEEDS_WORK":
        result = "NEEDS_WORK"
    elif public["postgres_result"] == "PASS":
        result = "PASS"
    else:
        result = "PASS WITH DOCUMENTED LIMITATIONS"
    public["result"] = private["result"] = result
    public["checks_passed"] = private["checks_passed"] = len(checks) - len(
        failures
    )
    public["checks_total"] = private["checks_total"] = len(checks)
    public["boundary"] = private["boundary"] = BOUNDARY
    public["required_final_statement"] = private[
        "required_final_statement"
    ] = REQUIRED_FINAL_STATEMENT
    private["checks"] = checks
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")
    print("PRMR Memory Core - Memory Admission Audit")
    print(f"SQLite result: {public['sqlite_result']}")
    print(f"PostgreSQL result: {public['postgres_result']}")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    return (
        0 if result in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"} else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
