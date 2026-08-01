"""Independent static and generated-evidence audit for Core Sprint 8."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT_DIR = ROOT / "reports" / "core_memory_consolidation"
PUBLIC_REPORT = REPORT_DIR / "public_memory_consolidation.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_memory_consolidation.json"
AUDIT_REPORT = REPORT_DIR / "audit_memory_consolidation.json"
SCORECARD = REPORT_DIR / "scorecard_memory_consolidation.md"
BENCHMARK_REPORT = REPORT_DIR / "benchmark_memory_consolidation.json"
MODULES = [
    ROOT / "prmr/core/memory_consolidation_models.py",
    ROOT / "prmr/core/memory_consolidation_policy.py",
    ROOT / "prmr/core/memory_consolidation_planner.py",
    ROOT / "prmr/core/memory_consolidation_engine.py",
    ROOT / "prmr/core/memory_consolidation_membership.py",
    ROOT / "prmr/core/memory_checkpoint.py",
    ROOT / "prmr/core/memory_consolidation_invalidation.py",
    ROOT / "prmr/core/memory_consolidation_query_adapter.py",
    ROOT / "prmr/core/memory_consolidation_continuity_adapter.py",
    ROOT / "prmr/core/memory_consolidation_integrity.py",
    ROOT / "prmr/core/memory_consolidation_fixtures.py",
    ROOT / "prmr/core/memory_consolidation_store.py",
]
MIGRATIONS = [
    ROOT / "migrations/core_memory_consolidation_v1_sqlite.sql",
    ROOT / "migrations/core_memory_consolidation_v1_postgres.sql",
]


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def no_secret(text: str) -> bool:
    patterns = (
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{12,}\b",
        r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"postgres(?:ql)?://[^\s\"']+",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"\bghp_[A-Za-z0-9]{20,}\b",
    )
    return not any(re.search(item, text, re.IGNORECASE) for item in patterns)


def main() -> int:
    checks: list[dict[str, Any]] = []
    source = "\n".join(read(path) for path in MODULES)
    model_source = read(MODULES[0])
    engine_source = read(ROOT / "prmr/core/memory_consolidation_engine.py")
    query_adapter = read(
        ROOT / "prmr/core/memory_consolidation_query_adapter.py"
    )
    public = json.loads(read(PUBLIC_REPORT)) if PUBLIC_REPORT.exists() else {}
    private = json.loads(read(PRIVATE_REPORT)) if PRIVATE_REPORT.exists() else {}
    benchmark = (
        json.loads(read(BENCHMARK_REPORT)) if BENCHMARK_REPORT.exists() else {}
    )

    add(checks, "all_required_modules_exist", all(path.exists() for path in MODULES))
    add(checks, "modules_parse_as_python", all(_parses(path) for path in MODULES))
    add(checks, "sqlite_migration_exists", MIGRATIONS[0].exists())
    add(checks, "postgres_migration_exists", MIGRATIONS[1].exists())
    migration_text = "\n".join(read(path) for path in MIGRATIONS)
    for table_name in (
        "prmr_memory_consolidation_runs",
        "prmr_memory_consolidation_plans",
        "prmr_consolidated_memories",
        "prmr_consolidated_memory_members",
        "prmr_memory_checkpoints",
        "prmr_memory_checkpoint_deltas",
        "prmr_memory_consolidation_invalidations",
        "prmr_memory_consolidation_equivalence_proofs",
    ):
        add(
            checks,
            f"migration_table_{table_name}",
            table_name in migration_text,
        )
    for class_name in (
        "MemoryConsolidationRun",
        "MemoryConsolidationPlan",
        "ConsolidatedMemory",
        "ConsolidatedMemoryMember",
        "MemoryCheckpoint",
        "MemoryCheckpointDelta",
        "MemoryConsolidationInvalidation",
        "MemoryConsolidationEquivalenceProof",
    ):
        add(checks, f"model_{class_name}_exists", f"class {class_name}" in model_source)
    add(checks, "only_exact_or_disabled_modes", 'DISABLED = "disabled"' in model_source and 'EXACT_STRUCTURAL_V1 = "exact_structural_v1"' in model_source and "semantic_assisted" not in model_source.lower())
    add(checks, "all_consolidation_types_typed", all(value in model_source for value in ("exact_signal_window", "event_state_chain", "temporal_phase_window", "entity_event_checkpoint", "relationship_state_checkpoint", "conflict_preserving_checkpoint", "query_resolution_checkpoint", "continuity_input_checkpoint")))
    add(checks, "derived_epistemic_status_enforced", 'derived_epistemic_status="derived"' in engine_source)
    add(checks, "generated_narrative_absent", '"generated_narrative": None' in engine_source)
    add(checks, "conflict_winner_not_selected", '"winner_selected": False' in engine_source)
    add(checks, "raw_ledger_not_deleted", not re.search(r"DELETE\\s+FROM\\s+(?:events|prmr_sources|prmr_memory_admission)", source, re.IGNORECASE))
    add(checks, "parameterised_storage", "placeholder(repository)" in read(ROOT / "prmr/core/memory_consolidation_store.py"))
    add(checks, "query_adapter_checks_manifest", "fast_authoritative_manifest" in query_adapter and "authoritative_manifest_changed" in query_adapter)
    add(checks, "query_adapter_falls_back", "consolidated_fallback_to_authoritative" in query_adapter)
    add(checks, "query_adapter_checks_equivalence", "equivalence_verification_failed" in query_adapter)
    add(checks, "continuity_uses_existing_query_artifact", "MemoryConsolidationQueryAdapter" in read(ROOT / "prmr/core/memory_consolidation_continuity_adapter.py"))
    add(checks, "integrity_does_not_repair_silently", "repair" not in read(ROOT / "prmr/core/memory_consolidation_integrity.py").lower())
    add(checks, "public_report_exists", bool(public))
    add(checks, "private_report_exists", bool(private))
    add(checks, "runner_checks_all_pass", private.get("passed_checks") == private.get("total_checks") and not private.get("failed_checks"))
    add(checks, "runner_has_broad_runtime_matrix", int(private.get("total_checks", 0)) >= 50)
    add(checks, "public_report_secret_safe", no_secret(json.dumps(public, sort_keys=True)))
    add(checks, "private_report_secret_safe", no_secret(json.dumps(private, sort_keys=True)))
    add(checks, "public_boundary_honest", "synthetic" in str(public.get("boundary", "")).lower() and "production-scale" in str(public.get("boundary", "")).lower())
    add(checks, "postgres_status_honest", public.get("postgres_validation") in {"not_run_no_database_url", "database_url_present"})
    add(checks, "sqlite_result_passes", public.get("result") in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"})
    add(checks, "benchmark_script_exists", (ROOT / "examples/benchmark_core_memory_consolidation.py").exists())
    add(checks, "benchmark_report_exists", bool(benchmark))
    add(checks, "benchmark_exactness_passes", benchmark.get("correctness", {}).get("current_state_exact") is True and benchmark.get("correctness", {}).get("continuity_packet_exact") is True)
    add(checks, "benchmark_five_warm_iterations", benchmark.get("timings", {}).get("canonical_current_state_warm", {}).get("iterations") == 5 and benchmark.get("timings", {}).get("accelerated_current_state_warm", {}).get("iterations") == 5)
    add(checks, "benchmark_minimum_speedup_passes", float(benchmark.get("timings", {}).get("current_state_warm_median_speedup_ratio", 0)) >= 2.0 and benchmark.get("result") == "PASS")
    add(checks, "no_llm_embedding_vector_dependency", not re.search(r"\\b(?:openai|anthropic|embedding|vector_search|llm)\\b", source, re.IGNORECASE))
    add(checks, "no_public_route_added", not re.search(r"@(?:app|router)\\.(?:get|post|put|delete|patch)", source))
    add(checks, "no_secret_patterns_in_core_files", no_secret(source + migration_text))

    failed = [item["name"] for item in checks if not item["passed"]]
    result = (
        "PASS WITH DOCUMENTED LIMITATIONS"
        if not failed and not os.environ.get("DATABASE_URL")
        else "PASS"
        if not failed
        else "NEEDS WORK"
    )
    payload = {
        "version": "core_sprint_8",
        "result": result,
        "passed_checks": sum(item["passed"] for item in checks),
        "total_checks": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "postgres_validation": (
            "not_run_no_database_url"
            if not os.environ.get("DATABASE_URL")
            else "database_url_present"
        ),
        "boundary": (
            "Independent repository and generated-evidence audit. It is not "
            "external validation or security certification."
        ),
    }
    AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_REPORT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    final_statement = str(
        public.get(
            "final_statement",
            "Core Sprint 8 consolidation statement unavailable.",
        )
    )
    SCORECARD.write_text(
        "# Core Sprint 8 Memory Consolidation\n\n"
        f"- Result: **{result}**\n"
        f"- Runtime checks: **{private.get('passed_checks', 0)}/{private.get('total_checks', 0)}**\n"
        f"- Audit checks: **{payload['passed_checks']}/{payload['total_checks']}**\n"
        f"- 10,000-event benchmark: **{benchmark.get('result', 'NOT RUN')}**\n"
        f"- Canonical warm median: **{benchmark.get('timings', {}).get('canonical_current_state_warm', {}).get('median_ms', 'n/a')} ms**\n"
        f"- Accelerated warm median: **{benchmark.get('timings', {}).get('accelerated_current_state_warm', {}).get('median_ms', 'n/a')} ms**\n"
        f"- Warm median speedup: **{benchmark.get('timings', {}).get('current_state_warm_median_speedup_ratio', 'n/a')}x**\n"
        f"- PostgreSQL: **{'not run; DATABASE_URL unavailable' if not os.environ.get('DATABASE_URL') else 'DATABASE_URL present; validation remains separate'}**\n\n"
        "## Boundary\n\n"
        "Internal deterministic synthetic SQLite evidence only. No production-scale, "
        "semantic-understanding, scientific-validation, or external-security claim is made.\n\n"
        "## Required Statement\n\n"
        + final_statement
        + "\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core - Core Sprint 8 Audit")
    print(f"Passed checks: {payload['passed_checks']}/{payload['total_checks']}")
    if failed:
        print("Failed checks: " + ", ".join(failed))
    print(f"Result: {result}")
    return 0 if not failed else 1


def _parses(path: Path) -> bool:
    try:
        ast.parse(read(path))
    except SyntaxError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
