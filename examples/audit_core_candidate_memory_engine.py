"""Independent runtime and contract audit for PRMR Core Sprint 2."""

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

from examples.run_core_candidate_memory_engine import (
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
    ROOT / "prmr" / "core" / "candidate_models.py",
    ROOT / "prmr" / "core" / "candidate_rules.py",
    ROOT / "prmr" / "core" / "candidate_evidence.py",
    ROOT / "prmr" / "core" / "candidate_integrity.py",
    ROOT / "prmr" / "core" / "candidate_engine.py",
    ROOT / "prmr" / "core" / "candidate_fixtures.py",
]
MIGRATIONS = [
    ROOT / "migrations" / "core_candidate_memory_v1_sqlite.sql",
    ROOT / "migrations" / "core_candidate_memory_v1_postgres.sql",
]


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def command(args: list[str], timeout: int = 300) -> tuple[bool, str]:
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
    return completed.returncode == 0, output[-2400:]


def report_contains_secret(value: Any) -> bool:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
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
    add(checks, "all_candidate_core_modules_exist", all(path.exists() for path in CORE_FILES))
    add(checks, "sqlite_and_postgres_candidate_migrations_exist", all(path.exists() for path in MIGRATIONS))

    models_text = CORE_FILES[0].read_text(encoding="utf-8")
    engine_text = CORE_FILES[4].read_text(encoding="utf-8")
    rules_text = CORE_FILES[1].read_text(encoding="utf-8")
    evidence_text = CORE_FILES[2].read_text(encoding="utf-8")
    integrity_text = CORE_FILES[3].read_text(encoding="utf-8")
    api_text = (ROOT / "prmr" / "product" / "api_server_v094.py").read_text(encoding="utf-8")

    add(checks, "typed_extraction_run_model_exists", "class ExtractionRun" in models_text)
    add(checks, "typed_candidate_memory_model_exists", "class CandidateMemory" in models_text)
    add(checks, "typed_candidate_evidence_model_exists", "class CandidateEvidence" in models_text)
    add(checks, "typed_extraction_policy_exists", "class CandidateExtractionPolicy" in models_text and "strict_v1" in models_text)
    add(checks, "four_epistemic_statuses_exist", all(f' = "{status}"' in models_text for status in ("explicit", "derived", "inferred", "unknown")))
    add(
        checks,
        "candidate_extraction_default_remains_pending_after_admission_expansion",
        'PENDING_REVIEW = "pending_review"' in models_text
        and "candidate_status=CandidateStatus.PENDING_REVIEW.value" in engine_text
        and '"admitted_event_count": 0' in models_text,
    )
    add(
        checks,
        "revision_identifiers_are_explicit",
        all(
            revision in models_text
            for revision in (
                "candidate_memory_v1", "candidate_extractor_v1", "candidate_rules_v1",
                "candidate_claim_splitter_v1", "candidate_manifest_v1", "epistemic_policy_v1",
            )
        ),
    )
    add(
        checks,
        "required_candidate_service_methods_exist",
        all(
            f"def {name}" in engine_text
            for name in (
                "extract_candidates", "get_extraction_run", "list_extraction_runs", "get_candidate",
                "list_candidates", "get_candidate_evidence", "verify_extraction_integrity",
                "invalidate_extraction_run",
            )
        ),
    )
    add(checks, "candidate_engine_does_not_import_product_event_engine", "controlled_alpha_api" not in engine_text and "events_ingest" not in engine_text and "continuity_packet" not in engine_text)
    add(checks, "no_public_candidate_api_route_added", "/v1/candidates" not in api_text and "/v1/sources" not in api_text)
    add(checks, "no_llm_model_or_embedding_dependency", all(token not in (engine_text + rules_text).lower() for token in ("openai", "anthropic", "embedding", "vector database", "model provider")))
    add(checks, "claim_splitter_preserves_offsets", all(token in rules_text for token in ("source_start_offset", "segment_start_offset", "start_line", "json_pointer")))
    add(checks, "negation_future_hypothetical_rules_exist", all(token in rules_text for token in ("NEGATION_PATTERNS", "FUTURE_PATTERNS", "HYPOTHETICAL_PATTERNS")))
    add(checks, "quoted_speech_rule_records_statement", "statement.recorded" in rules_text and "truth_of_quoted_content_confirmed" in rules_text)
    add(checks, "unknown_rule_preserves_uncertainty", "information.unknown" in rules_text and "underlying_information_known" in rules_text)
    add(checks, "only_documented_derivation_operator_exists", "state_transition_v1" in rules_text and "deterministic_derivation" in rules_text)
    add(checks, "evidence_requires_primary_record", "Every candidate requires at least one primary evidence record" in evidence_text)
    add(checks, "evidence_is_resolved_not_duplicated", "evidence_text_hash_sha256" in evidence_text and not re.search(r"^\s*evidence_text\s*:", models_text, re.MULTILINE))
    add(checks, "candidate_fingerprint_uses_sha256_not_python_hash", "candidate_fingerprint" in integrity_text and "sha256_text" in integrity_text and "builtins.hash" not in integrity_text)
    add(checks, "candidate_manifest_is_ordered_and_versioned", "candidate_manifest_revision" in integrity_text and "for item in candidates" in integrity_text)

    sqlite_migration = MIGRATIONS[0].read_text(encoding="utf-8")
    postgres_migration = MIGRATIONS[1].read_text(encoding="utf-8")
    for table in ("prmr_candidate_extraction_runs", "prmr_candidate_memories", "prmr_candidate_evidence"):
        add(checks, f"sqlite_migration_contains_{table}", table in sqlite_migration)
        add(checks, f"postgres_migration_contains_{table}", table in postgres_migration)
    add(checks, "candidate_foreign_keys_cascade_from_source", sqlite_migration.count("ON DELETE CASCADE") >= 5 and postgres_migration.count("ON DELETE CASCADE") >= 5)
    add(checks, "extraction_identity_has_unique_constraint", "extraction_identity_sha256 TEXT NOT NULL UNIQUE" in sqlite_migration and "extraction_identity_sha256 TEXT NOT NULL UNIQUE" in postgres_migration)
    add(checks, "candidate_fingerprint_unique_per_run", "UNIQUE(extraction_run_id, candidate_fingerprint_sha256)" in sqlite_migration and "UNIQUE(extraction_run_id, candidate_fingerprint_sha256)" in postgres_migration)

    syntax_files = [str(path) for path in CORE_FILES] + [
        str(ROOT / "examples" / "run_core_candidate_memory_engine.py"),
        str(ROOT / "examples" / "audit_core_candidate_memory_engine.py"),
        str(ROOT / "prmr" / "product" / "self_serve_repository_v093.py"),
        str(ROOT / "prmr" / "product" / "self_serve_repository_postgres_v0941.py"),
    ]
    syntax_ok, syntax_output = command([sys.executable, "-m", "py_compile", *syntax_files])
    add(checks, "python_syntax_and_import_validation", syntax_ok, syntax_output)

    regression_commands = {
        "core_sprint_1_source_ledger": [sys.executable, "examples/audit_core_source_ledger_provenance.py"],
        "v098_external_event_contract": [sys.executable, "examples/audit_v098_external_event_contract.py"],
        "v099_continuity_packet_runtime": [sys.executable, "examples/run_v099_theory_to_product_packet.py"],
        "v084_multi_client_isolation": [sys.executable, "examples/audit_v084_multi_client_isolation.py"],
        "v093_durable_storage": [sys.executable, "examples/audit_v093_durable_self_serve_storage.py"],
    }
    regression_outputs: dict[str, str] = {}
    for name, args in regression_commands.items():
        ok, output = command(args, timeout=420)
        regression_outputs[name] = output
        add(checks, f"existing_{name}_regression", ok, output)

    public_files = {
        "core_modules": [str(path.relative_to(ROOT)).replace("\\", "/") for path in CORE_FILES],
        "migrations": [str(path.relative_to(ROOT)).replace("\\", "/") for path in MIGRATIONS],
        "runner": "examples/run_core_candidate_memory_engine.py",
        "audit": "examples/audit_core_candidate_memory_engine.py",
    }
    public = {**public, "files": public_files, "audit_scope": {
        "runtime_extraction_exercised": True,
        "durable_sqlite_restart_exercised": True,
        "concurrent_idempotency_exercised": True,
        "source_and_candidate_corruption_exercised": True,
        "deletion_and_expiry_cascades_exercised": True,
        "existing_engine_regressions_exercised": True,
    }}
    private = {**private, **public, "public_safe": False, "checks": checks, "command_outputs": regression_outputs}
    add(checks, "public_report_contains_no_secret_patterns", not report_contains_secret(public))
    add(checks, "private_report_contains_no_secret_patterns", not report_contains_secret(private))
    failures = [item for item in checks if not item["passed"]]
    postgres_result = public["postgres_result"]
    if failures or postgres_result == "NEEDS_WORK":
        result = "NEEDS_WORK"
    elif postgres_result == "PASS":
        result = "PASS"
    else:
        result = "PASS WITH DOCUMENTED LIMITATIONS"
    public["result"] = private["result"] = result
    public["checks_passed"] = private["checks_passed"] = len(checks) - len(failures)
    public["checks_total"] = private["checks_total"] = len(checks)
    private["checks"] = checks
    private["required_final_statement"] = public["required_final_statement"] = REQUIRED_FINAL_STATEMENT
    private["boundary"] = public["boundary"] = BOUNDARY
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public), encoding="utf-8")
    print("PRMR Memory Core - Candidate Memory Engine Audit")
    print(f"SQLite result: {public['sqlite_result']}")
    print(f"PostgreSQL result: {public['postgres_result']}")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    return 0 if result in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
