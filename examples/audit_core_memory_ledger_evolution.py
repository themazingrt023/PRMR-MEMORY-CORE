"""Independent audit for Core Sprint 4 bitemporal memory-ledger evolution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "core_memory_ledger_evolution"
RUNNER_PUBLIC = REPORT_DIR / "public_memory_ledger_evolution.json"
AUDIT_REPORT = REPORT_DIR / "audit_memory_ledger_evolution.json"
SCORECARD = REPORT_DIR / "scorecard_memory_ledger_evolution.md"
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 4 establishes Bitemporal Memory Ledger Evolution inside PRMR Memory Core. "
    "Admitted memories can now be corrected, superseded, retracted, placed into unresolved "
    "contradictions and explicitly resolved without erasing their history or provenance. "
    "Memory state can be reconstructed by valid time and system-known time, and the existing "
    "continuity engine can operate on the deterministically resolved effective ledger. "
    "Automatic contradiction discovery, advanced temporal decay, entity memory and memory "
    "consolidation remain later core-engine milestones."
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run(command: list[str], *, timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "output_tail": output.splitlines()[-12:],
    }


def has_all(path: Path, tokens: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(token in text for token in tokens)


def secret_safe(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return not any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in (
            r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
            r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
            r"postgres(?:ql)?://[^\s\"']+",
            r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
        )
    )


def main() -> int:
    checks: list[dict[str, Any]] = []
    command_results: list[dict[str, Any]] = []
    required_files = [
        ROOT / "prmr/core/memory_ledger_models.py",
        ROOT / "prmr/core/memory_ledger_service.py",
        ROOT / "prmr/core/memory_evolution.py",
        ROOT / "prmr/core/memory_conflicts.py",
        ROOT / "prmr/core/memory_state_resolver.py",
        ROOT / "prmr/core/memory_reconstruction.py",
        ROOT / "prmr/core/memory_ledger_integrity.py",
        ROOT / "prmr/core/memory_ledger_fixtures.py",
        ROOT / "migrations/core_memory_ledger_v2_sqlite.sql",
        ROOT / "migrations/core_memory_ledger_v2_postgres.sql",
        ROOT / "examples/run_core_memory_ledger_evolution.py",
    ]
    add(checks, "required_files_exist", all(path.exists() for path in required_files))
    add(
        checks,
        "revision_identifiers_locked",
        has_all(
            required_files[0],
            (
                "memory_ledger_v2",
                "memory_evolution_v1",
                "memory_state_resolver_v1",
                "memory_conflict_v1",
                "memory_reconstruction_v1",
                "memory_bitemporal_v1",
                "continuity_input_resolver_v1",
            ),
        ),
    )
    add(
        checks,
        "event_state_model_complete",
        has_all(
            required_files[0],
            ("ACTIVE", "SUPERSEDED", "RETRACTED", "CONFLICTED", "RESOLVED", "INVALIDATED"),
        ),
    )
    add(
        checks,
        "evolution_operations_present",
        has_all(
            required_files[1],
            (
                "correct_admitted_memory",
                "supersede_admitted_memory",
                "retract_admitted_memory",
                "declare_memory_contradiction",
                "resolve_memory_contradiction",
                "invalidate_admitted_memory",
                "trace_memory_evolution",
            ),
        ),
    )
    add(
        checks,
        "resolver_contract_present",
        has_all(
            required_files[4],
            (
                "resolve_effective_events",
                "not_yet_known",
                "outside_valid_time",
                "outside_subject_scope",
                "include_conflicted",
            ),
        ),
    )
    add(
        checks,
        "reconstruction_contract_present",
        has_all(
            required_files[5],
            (
                "reconstruct_current_state",
                "reconstruct_at_valid_time",
                "reconstruct_as_known_at",
                "reconstruct_bitemporal",
                "compare_reconstructions",
                "legacy_all_events",
                "resolved_memory_events_v1",
            ),
        ),
    )
    add(
        checks,
        "integrity_contract_present",
        has_all(
            required_files[6],
            (
                "admitted_provenance",
                "evolution_hashes_match",
                "no_evolution_cycles",
                "reconstruction_hashes_reproduce",
                "packet_exclusions_match",
            ),
        ),
    )
    add(
        checks,
        "sqlite_constraints_present",
        has_all(
            required_files[8],
            (
                "UNIQUE(client_id, vault_id, namespace, idempotency_digest)",
                "prmr_evolution_terminal_unique_idx",
                "prmr_evolution_conflict_resolution_unique_idx",
                "reconstruction_identity TEXT NOT NULL UNIQUE",
            ),
        ),
    )
    add(
        checks,
        "postgres_constraints_present",
        has_all(
            required_files[9],
            (
                "JSONB",
                "prmr_evolution_terminal_unique_idx",
                "ON CONFLICT(revision) DO NOTHING",
                "prmr_reconstruction_hash_idx",
            ),
        ),
    )
    add(
        checks,
        "repositories_initialize_ledger_schema",
        has_all(
            ROOT / "prmr/product/self_serve_repository_v093.py",
            ("initialize_sqlite_memory_ledger_schema", "prmr_memory_evolution_records"),
        )
        and has_all(
            ROOT / "prmr/product/self_serve_repository_postgres_v0941.py",
            ("initialize_postgres_memory_ledger_schema", "prmr_memory_reconstructions"),
        ),
    )
    add(
        checks,
        "source_deletion_counts_extended",
        has_all(
            ROOT / "prmr/core/source_ledger.py",
            (
                "accepted_memory_count",
                "evolution_link_count",
                "conflict_count",
                "reconstruction_count",
            ),
        ),
    )
    core_text = "\n".join(path.read_text(encoding="utf-8") for path in required_files[:8])
    add(checks, "no_http_calls_in_core_modules", "requests." not in core_text and "httpx." not in core_text and "urllib.request" not in core_text)
    add(checks, "no_llm_embedding_or_vector_dependency", not re.search(r"\b(openai|anthropic|embedding|vector database)\b", core_text, re.IGNORECASE))
    add(
        checks,
        "continuity_formula_file_unmodified",
        subprocess.run(
            ["git", "diff", "--quiet", "--", "prmr/product/controlled_alpha_api_v071.py"],
            cwd=ROOT,
        ).returncode
        == 0,
    )

    runner = run([sys.executable, "examples/run_core_memory_ledger_evolution.py"])
    command_results.append(runner)
    add(checks, "durable_sqlite_runner_passes", runner["returncode"] == 0, runner["output_tail"])
    runner_public = (
        json.loads(RUNNER_PUBLIC.read_text(encoding="utf-8"))
        if RUNNER_PUBLIC.exists()
        else {}
    )
    add(checks, "runner_reports_69_checks", runner_public.get("passed_checks") == runner_public.get("total_checks") == 69)
    add(checks, "runner_status_honest", runner_public.get("result") in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"})
    add(checks, "runner_public_report_secret_safe", secret_safe(runner_public))
    add(checks, "required_final_statement_present", runner_public.get("required_final_statement") == REQUIRED_FINAL_STATEMENT)

    compile_files = [str(path.relative_to(ROOT)) for path in required_files if path.suffix == ".py"]
    compilation = run([sys.executable, "-m", "py_compile", *compile_files])
    command_results.append(compilation)
    add(checks, "python_compilation_passes", compilation["returncode"] == 0, compilation["output_tail"])

    regressions = [
        ("core_source_runner", [sys.executable, "examples/run_core_source_ledger_provenance.py"]),
        ("core_source_audit", [sys.executable, "examples/audit_core_source_ledger_provenance.py"]),
        ("core_candidate_runner", [sys.executable, "examples/run_core_candidate_memory_engine.py"]),
        ("core_candidate_audit", [sys.executable, "examples/audit_core_candidate_memory_engine.py"]),
        ("core_admission_runner", [sys.executable, "examples/run_core_memory_admission.py"]),
        ("core_admission_audit", [sys.executable, "examples/audit_core_memory_admission.py"]),
        ("v084_isolation", [sys.executable, "examples/run_multi_client_isolation_v084.py"]),
        ("v093_persistence", [sys.executable, "examples/run_durable_self_serve_storage_v093.py"]),
        ("v098_event_contract", [sys.executable, "examples/run_external_event_contract_smoke_v098.py"]),
        ("v099_continuity_runtime", [sys.executable, "examples/run_v099_theory_to_product_packet.py"]),
        ("entity_scope_isolation", [sys.executable, "examples/benchmark_entity_scoped_packets.py"]),
        ("secret_hygiene", [sys.executable, "examples/audit_v0782_secret_cleanup.py"]),
    ]
    for name, command in regressions:
        # Earlier core audits now cover larger cumulative regression matrices.
        result = run(command, timeout=600)
        command_results.append(result)
        add(checks, f"regression_{name}_passes", result["returncode"] == 0, result["output_tail"])

    diff_check = run(["git", "diff", "--check"])
    command_results.append(diff_check)
    add(checks, "git_diff_check_passes", diff_check["returncode"] == 0, diff_check["output_tail"])

    postgres_validated = bool(
        os.getenv("DATABASE_URL", "").strip()
        and runner_public.get("postgres_status") == "PASS"
    )
    add(
        checks,
        "postgres_status_reported_honestly",
        (
            postgres_validated
            or runner_public.get("postgres_status") == "NOT_RUN_DATABASE_URL_MISSING"
        ),
        runner_public.get("postgres_status"),
    )
    failed = [item for item in checks if not item["passed"]]
    status = (
        "NEEDS WORK"
        if failed
        else "PASS"
        if postgres_validated
        else "PASS WITH DOCUMENTED LIMITATIONS"
    )
    report = {
        "version": "core_sprint_4_audit",
        "result": status,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": [item["name"] for item in failed],
        "checks": checks,
        "commands": command_results,
        "postgres_validated": postgres_validated,
        "postgres_status": runner_public.get("postgres_status"),
        "boundary": runner_public.get("boundary"),
        "required_final_statement": REQUIRED_FINAL_STATEMENT,
        "contains_raw_credentials": False,
    }
    AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with SCORECARD.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## Independent Audit\n\n"
            f"- Result: **{status}**\n"
            f"- Passed checks: **{report['passed_checks']}/{report['total_checks']}**\n"
        )
    print("PRMR Memory Core - Core Sprint 4 Audit")
    print(f"Passed checks: {report['passed_checks']}/{report['total_checks']}")
    print(f"PostgreSQL: {report['postgres_status']}")
    print(f"Result: {status}")
    if failed:
        print("Failed: " + ", ".join(report["failed_checks"]))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
