"""Independent audit for Core Sprint 5 Temporal Memory Dynamics."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "core_temporal_memory_dynamics"
RUNNER_PUBLIC = REPORT_DIR / "public_temporal_memory_dynamics.json"
AUDIT_REPORT = REPORT_DIR / "audit_temporal_memory_dynamics.json"
SCORECARD = REPORT_DIR / "scorecard_temporal_memory_dynamics.md"
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 5 establishes Temporal Memory Dynamics inside PRMR Memory Core. "
    "Effective admitted memory can now evolve through deterministic time-based influence, "
    "immediate-to-historical horizons, active, latent, dormant and decayed phases, "
    "recurrence reinforcement, explicit importance and genuine re-emergence after absence. "
    "Decay reduces current influence without deleting history or provenance. The bitemporal "
    "ledger remains authoritative, existing coherence and recoverability formulas remain "
    "unchanged, and the legacy five-event behaviour remains revisioned for replay "
    "compatibility. Semantic signal equivalence, entity memory, relationship memory and "
    "memory consolidation remain later core-engine milestones."
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def has_all(path: Path, tokens: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(token in text for token in tokens)


def run(command: list[str], *, timeout: int = 600) -> dict[str, Any]:
    try:
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
            "output_tail": output.splitlines()[-16:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "returncode": -1,
            "output_tail": [f"Timed out after {exc.timeout} seconds."],
        }


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
    commands: list[dict[str, Any]] = []
    required_files = [
        ROOT / "prmr/core/memory_temporal_models.py",
        ROOT / "prmr/core/memory_temporal_policy.py",
        ROOT / "prmr/core/memory_dynamics_engine.py",
        ROOT / "prmr/core/memory_recurrence.py",
        ROOT / "prmr/core/memory_importance.py",
        ROOT / "prmr/core/memory_dynamics_integrity.py",
        ROOT / "prmr/core/memory_temporal_fixtures.py",
        ROOT / "migrations/core_temporal_memory_v1_sqlite.sql",
        ROOT / "migrations/core_temporal_memory_v1_postgres.sql",
        ROOT / "examples/run_core_temporal_memory_dynamics.py",
    ]
    add(checks, "required_files_exist", all(path.exists() for path in required_files))
    add(
        checks,
        "revision_identifiers_locked",
        has_all(
            required_files[0],
            (
                "memory_temporal_v1",
                "temporal_memory_policy_v1",
                "memory_horizons_v1",
                "memory_influence_v1",
                "memory_recurrence_v1",
                "memory_reemergence_v1",
                "memory_importance_v1",
                "memory_dynamics_snapshot_v1",
                "continuity_temporal_adapter_v1",
                "signal_identity_v1",
            ),
        ),
    )
    add(
        checks,
        "memory_dynamics_modes_exist",
        has_all(required_files[0], ("legacy_recent5_v1", "temporal_memory_v1")),
    )
    add(
        checks,
        "horizon_and_phase_models_complete",
        has_all(
            required_files[0],
            (
                "IMMEDIATE",
                "SHORT",
                "MEDIUM",
                "LONG",
                "HISTORICAL",
                "ACTIVE",
                "LATENT",
                "DORMANT",
                "DECAYED",
            ),
        ),
    )
    add(
        checks,
        "importance_model_complete",
        has_all(
            required_files[0],
            (
                "MemoryImportanceAnnotation",
                "importance_annotation_id",
                "system_effective_at",
                "idempotency_digest",
            ),
        ),
    )
    add(
        checks,
        "signal_dynamics_model_complete",
        has_all(
            required_files[0],
            (
                "MemorySignalDynamics",
                "occurrences_by_horizon",
                "recurrence_boost",
                "cross_horizon_boost",
                "re_emerging",
                "open_conflict_ids",
            ),
        ),
    )
    add(
        checks,
        "snapshot_model_complete",
        has_all(
            required_files[0],
            (
                "MemoryDynamicsSnapshot",
                "resolved_event_manifest_hash",
                "importance_annotation_manifest_hash",
                "signal_dynamics_manifest_hash",
                "temporal_packet_hash",
            ),
        ),
    )
    add(
        checks,
        "policy_formula_present",
        has_all(
            required_files[1],
            (
                "math.pow(2.0",
                "math.log1p",
                "ROUND_HALF_EVEN",
                "QUANTUM_8",
                "classify_phase",
            ),
        ),
    )
    add(
        checks,
        "signal_identity_never_uses_free_text",
        has_all(
            required_files[3],
            (
                'metadata.get("canonical_signal")',
                'event.get("type") or event.get("event_type")',
            ),
        )
        and "event.get(\"content\")" not in required_files[3].read_text(encoding="utf-8"),
    )
    add(
        checks,
        "resolver_is_authoritative",
        has_all(
            required_files[2],
            (
                "resolve_effective_events",
                "include_conflicted=True",
                "MemoryTemporalBoundary",
            ),
        ),
    )
    add(
        checks,
        "event_time_fallback_chain_present",
        has_all(
            required_files[2],
            (
                "event_occurred_at",
                "candidate_occurred_at",
                "segment_occurred_at",
                "source_occurred_at",
                "source_ingested_at",
                "event_stored_at",
            ),
        ),
    )
    add(
        checks,
        "recurrence_formula_present",
        has_all(
            required_files[2],
            (
                "occurrence_count",
                "maximum_gap_seconds",
                "maximum_gap_event_count",
                "recurrence_span_seconds",
                "max_effective_event_importance_v1",
            ),
        ),
    )
    add(
        checks,
        "reemergence_requires_absence",
        has_all(
            required_files[2],
            (
                "minimum_reemergence_gap_seconds",
                "minimum_reemergence_gap_events",
                'prior_phase in {"latent", "dormant", "decayed"}',
            ),
        ),
    )
    add(
        checks,
        "packet_adapter_fields_present",
        has_all(
            required_files[2],
            (
                'packet["dormant_information"]',
                'packet["decayed_signals"]',
                'packet["reinforced_signals"]',
                'packet["re_emergence_signals"]',
                'packet["memory_dynamics_context"]',
                'packet["current_state_age_seconds"]',
            ),
        ),
    )
    add(
        checks,
        "coherence_and_recoverability_not_recomputed",
        "coherence_score" not in required_files[2].read_text(encoding="utf-8").split(
            "def build_continuity_packet", 1
        )[1].split("def verify_memory_dynamics_integrity", 1)[0].replace(
            'packet["coherence_score"]', ""
        )
        and "recoverability_score" not in required_files[2].read_text(
            encoding="utf-8"
        ).split("def build_continuity_packet", 1)[1].split(
            "def verify_memory_dynamics_integrity", 1
        )[0].replace(
            'packet["recoverability_score"]', ""
        ),
    )
    add(
        checks,
        "integrity_contract_complete",
        has_all(
            required_files[2],
            (
                "snapshot_identity_reproduces",
                "resolved_event_manifest_reproduces",
                "importance_manifest_reproduces",
                "signal_manifest_reproduces",
                "occurrence_events_exist_and_scoped",
                "no_future_leakage",
                "temporal_packet_hash_reproduces",
            ),
        ),
    )
    add(
        checks,
        "safe_structured_logs_present",
        has_all(
            required_files[2],
            (
                "memory_dynamics_started",
                "memory_dynamics_completed",
                "memory_dynamics_replayed",
                "memory_dynamics_failed",
                "memory_signal_reinforced",
                "memory_signal_reemerged",
                "memory_signal_became_dormant",
                "memory_signal_decayed",
                "memory_dynamics_integrity_verified",
            ),
        )
        and has_all(required_files[4], ("memory_importance_annotated",)),
    )
    add(
        checks,
        "sqlite_constraints_and_indexes_present",
        has_all(
            required_files[7],
            (
                "UNIQUE(client_id, vault_id, namespace, idempotency_digest)",
                "UNIQUE(dynamics_snapshot_id, signal_key)",
                "FOREIGN KEY(dynamics_snapshot_id)",
                "prmr_dynamics_scope_idx",
                "prmr_signal_phase_idx",
            ),
        ),
    )
    add(
        checks,
        "postgres_constraints_and_indexes_present",
        has_all(
            required_files[8],
            (
                "prmr_self_serve.prmr_memory_importance_annotations",
                "prmr_self_serve.prmr_memory_dynamics_snapshots",
                "prmr_self_serve.prmr_memory_signal_dynamics",
                "JSONB",
                "UNIQUE(dynamics_snapshot_id, signal_key)",
            ),
        ),
    )
    sqlite_repository = ROOT / "prmr/product/self_serve_repository_v093.py"
    postgres_repository = ROOT / "prmr/product/self_serve_repository_postgres_v0941.py"
    add(
        checks,
        "repositories_register_temporal_schema",
        has_all(
            sqlite_repository,
            (
                "prmr_memory_importance_annotations",
                "prmr_memory_dynamics_snapshots",
                "initialize_sqlite_temporal_schema",
            ),
        )
        and has_all(
            postgres_repository,
            (
                "prmr_memory_importance_annotations",
                "prmr_memory_dynamics_snapshots",
                "initialize_postgres_temporal_schema",
            ),
        ),
    )

    runner = run([sys.executable, "examples/run_core_temporal_memory_dynamics.py"])
    commands.append(runner)
    add(checks, "sqlite_runner_passes", runner["returncode"] == 0, runner["output_tail"])
    runner_report = (
        json.loads(RUNNER_PUBLIC.read_text(encoding="utf-8"))
        if RUNNER_PUBLIC.exists()
        else {}
    )
    add(
        checks,
        "runner_dynamic_checks_all_pass",
        runner_report.get("passed_checks") == runner_report.get("total_checks")
        and not runner_report.get("failed_checks"),
        {
            "passed": runner_report.get("passed_checks"),
            "total": runner_report.get("total_checks"),
        },
    )
    add(
        checks,
        "runner_covers_required_behaviour",
        int(runner_report.get("total_checks", 0)) >= 80,
        runner_report.get("total_checks"),
    )
    add(checks, "public_report_secret_safe", secret_safe(runner_report))
    add(
        checks,
        "required_final_statement_present",
        runner_report.get("required_final_statement") == REQUIRED_FINAL_STATEMENT
        and has_all(SCORECARD, (REQUIRED_FINAL_STATEMENT,)),
    )

    regression_commands = [
        (
            "core_sprint_4_audit",
            [sys.executable, "examples/audit_core_memory_ledger_evolution.py"],
        ),
        (
            "v084_multi_client_isolation",
            [sys.executable, "examples/run_multi_client_isolation_v084.py"],
        ),
        (
            "v093_durable_storage",
            [sys.executable, "examples/run_durable_self_serve_storage_v093.py"],
        ),
        (
            "v098_event_contract",
            [sys.executable, "examples/run_external_event_contract_smoke_v098.py"],
        ),
        (
            "v099_continuity_runtime",
            [sys.executable, "examples/run_v099_theory_to_product_packet.py"],
        ),
        (
            "secret_hygiene",
            [sys.executable, "examples/audit_v0782_secret_cleanup.py"],
        ),
    ]
    for name, command in regression_commands:
        result = run(
            command,
            timeout=1800 if name == "core_sprint_4_audit" else 600,
        )
        commands.append(result)
        add(checks, f"regression_{name}", result["returncode"] == 0, result["output_tail"])

    compilation = run(
        [
            sys.executable,
            "-c",
            (
                "import pathlib,py_compile;"
                "[py_compile.compile(str(p),doraise=True) "
                "for p in pathlib.Path('prmr/core').glob('*.py')];"
                "py_compile.compile('examples/run_core_temporal_memory_dynamics.py',doraise=True);"
                "py_compile.compile('examples/audit_core_temporal_memory_dynamics.py',doraise=True)"
            ),
        ]
    )
    commands.append(compilation)
    add(checks, "python_compilation_passes", compilation["returncode"] == 0, compilation["output_tail"])
    diff_check = run(["git", "diff", "--check"], timeout=120)
    commands.append(diff_check)
    add(checks, "git_diff_check_passes", diff_check["returncode"] == 0, diff_check["output_tail"])

    postgres_available = bool(os.environ.get("DATABASE_URL", "").strip())
    add(
        checks,
        "postgresql_status_honest",
        postgres_available
        or runner_report.get("result") == "PASS WITH DOCUMENTED LIMITATIONS",
        "DATABASE_URL available" if postgres_available else "DATABASE_URL unavailable",
    )
    failed = [item["name"] for item in checks if not item["passed"]]
    status = (
        "NEEDS WORK"
        if failed
        else ("PASS" if postgres_available else "PASS WITH DOCUMENTED LIMITATIONS")
    )
    report = {
        "version": "Core Sprint 5 independent audit",
        "result": status,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "commands": commands,
        "postgresql": (
            "DATABASE_URL detected"
            if postgres_available
            else "not exercised because DATABASE_URL is unavailable"
        ),
        "boundary": (
            "Independent internal deterministic audit only. This is not production "
            "readiness, scientific validation, external validation, or security certification."
        ),
        "required_final_statement": REQUIRED_FINAL_STATEMENT,
    }
    AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 5 Independent Audit")
    print(f"Result: {status}")
    print(f"Passed checks: {report['passed_checks']}/{report['total_checks']}")
    print(f"PostgreSQL: {report['postgresql']}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
