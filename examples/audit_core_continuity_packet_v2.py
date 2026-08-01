"""Independent evidence audit for Core Sprint 13 Continuity Packet V2."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.continuity_v2_models import (  # noqa: E402
    CONTINUITY_V2_ACCELERATION_REVISION,
    CONTINUITY_V2_COMPARISON_REVISION,
    CONTINUITY_V2_ENTITY_REVISION,
    CONTINUITY_V2_EPISTEMIC_REVISION,
    CONTINUITY_V2_GOVERNANCE_REVISION,
    CONTINUITY_V2_INTEGRITY_REVISION,
    CONTINUITY_V2_PROVENANCE_REVISION,
    CONTINUITY_V2_RELATIONSHIP_REVISION,
    CONTINUITY_V2_SCHEMA_REVISION,
    CONTINUITY_V2_STATE_REVISION,
    CONTINUITY_V2_TEMPORAL_REVISION,
)
from prmr.core.continuity_v2_policy import (  # noqa: E402
    CONTINUITY_V2_POLICY_ID,
    CONTINUITY_V2_POLICY_REVISION,
    ContinuityPacketV2Policy,
    PACKET_MODES,
)
from prmr.core.runtime_migrations import migration_registry  # noqa: E402
from examples.run_core_continuity_packet_v2 import REQUIRED_FINAL_STATEMENT  # noqa: E402


REPORT_DIR = ROOT / "reports/core_continuity_packet_v2"
CORPUS_DIR = ROOT / "benchmarks/continuity_packet_v2"
REQUIRED_DOMAINS = {
    "state_dimension_resolution",
    "epistemic_separation",
    "tentative_overlays",
    "unknown_preservation",
    "open_conflict",
    "resolved_conflict",
    "temporal_phases",
    "re_emergence",
    "entity_isolation",
    "relationship_uncertainty",
    "canonical_signals",
    "governance_erasure",
    "legacy_provenance",
    "acceleration_equivalence",
    "sqlite_postgresql_parity",
}
REQUIRED_MODULES = (
    "continuity_v2_models.py",
    "continuity_v2_policy.py",
    "continuity_v2_state_resolver.py",
    "continuity_v2_epistemic.py",
    "continuity_v2_temporal.py",
    "continuity_v2_entities.py",
    "continuity_v2_relationships.py",
    "continuity_v2_provenance.py",
    "continuity_v2_packet.py",
    "continuity_v2_comparison.py",
    "continuity_v2_integrity.py",
    "continuity_v2_fixtures.py",
)
REQUIRED_MUTATIONS = {f"M{index:02d}" for index in range(1, 13)}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def add(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    public = load(REPORT_DIR / "public_continuity_packet_v2.json")
    private = load(REPORT_DIR / "private_internal_continuity_packet_v2.json")
    parity = load(REPORT_DIR / "backend_parity_continuity_packet_v2.json")
    benchmark = load(REPORT_DIR / "benchmark_continuity_packet_v2.json")
    mutations = load(REPORT_DIR / "mutation_results_continuity_packet_v2.json")
    regressions = load(REPORT_DIR / "regression_results_continuity_packet_v2.json")
    manifest = load(CORPUS_DIR / "corpus_manifest.json")
    cases_payload = json.loads((CORPUS_DIR / "cases.json").read_text(encoding="utf-8")) if (CORPUS_DIR / "cases.json").exists() else []

    for module in REQUIRED_MODULES:
        add(checks, f"module_{module}_exists", (ROOT / "prmr/core" / module).exists())
    for backend in ("sqlite", "postgres"):
        add(
            checks,
            f"migration_{backend}_exists",
            (ROOT / f"migrations/core_continuity_packet_v2_{backend}.sql").exists(),
        )
    for runner in (
        "run_core_continuity_packet_v2.py",
        "audit_core_continuity_packet_v2.py",
        "run_core_continuity_packet_v2_mutations.py",
        "benchmark_core_continuity_packet_v2.py",
    ):
        add(checks, f"runner_{runner}_exists", (ROOT / "examples" / runner).exists())

    policy = ContinuityPacketV2Policy()
    add(checks, "packet_modes_revisioned", set(PACKET_MODES) == {"legacy_continuity_v1", "epistemic_continuity_v2"})
    add(checks, "v2_policy_is_explicit", policy.packet_mode == "epistemic_continuity_v2")
    add(checks, "policy_id_is_epistemic_strict_v1", CONTINUITY_V2_POLICY_ID == "epistemic_strict_v1")
    revisions = {
        CONTINUITY_V2_SCHEMA_REVISION,
        CONTINUITY_V2_POLICY_REVISION,
        CONTINUITY_V2_STATE_REVISION,
        CONTINUITY_V2_EPISTEMIC_REVISION,
        CONTINUITY_V2_TEMPORAL_REVISION,
        CONTINUITY_V2_ENTITY_REVISION,
        CONTINUITY_V2_RELATIONSHIP_REVISION,
        CONTINUITY_V2_PROVENANCE_REVISION,
        CONTINUITY_V2_GOVERNANCE_REVISION,
        CONTINUITY_V2_COMPARISON_REVISION,
        CONTINUITY_V2_INTEGRITY_REVISION,
        CONTINUITY_V2_ACCELERATION_REVISION,
    }
    add(checks, "all_twelve_revisions_present", len(revisions) == 12)
    registry = migration_registry()
    add(checks, "ordered_migration_registry_has_v2", len(registry) == 12 and registry[-1].migration_id == "core_13_continuity_packet_v2")

    sqlite_checks = private.get("sqlite", {}).get("checks", [])
    postgres_checks = private.get("postgres", {}).get("checks", [])
    add(checks, "sqlite_all_runtime_checks_pass", bool(sqlite_checks) and all(item.get("passed") for item in sqlite_checks))
    add(checks, "postgres_all_runtime_checks_pass", bool(postgres_checks) and all(item.get("passed") for item in postgres_checks))
    add(checks, "postgres_guard_verified", private.get("postgres", {}).get("guard") == "VERIFIED_ISOLATED_TEST_DATABASE")
    add(checks, "postgres_guard_preserved", private.get("postgres", {}).get("relation_evidence", {}).get("guard_preserved") is True)
    add(checks, "postgres_all_relations_present", private.get("postgres", {}).get("relation_evidence", {}).get("all_present") is True)
    add(checks, "postgres_migration_replay_idempotent", private.get("postgres", {}).get("migration_replay_applied") == [])

    exact = parity.get("exact_packet_parity", {})
    add(checks, "backend_parity_report_passes", parity.get("result") == "PASS")
    add(checks, "same_ledger_confirmed", exact.get("same_logical_ledger") is True)
    add(checks, "packet_id_backend_parity", exact.get("packet_id_equal") is True)
    add(checks, "packet_hash_backend_parity", exact.get("packet_hash_equal") is True)
    add(checks, "packet_content_backend_parity", exact.get("packet_contents_equal") is True)

    case_count = len(cases_payload)
    assertion_count = sum(len(case.get("assertions", [])) for case in cases_payload)
    domains = Counter(case.get("domain") for case in cases_payload)
    add(checks, "minimum_120_cases_recalculated", case_count >= 120, case_count)
    add(checks, "minimum_500_assertions_recalculated", assertion_count >= 500, assertion_count)
    add(checks, "all_required_domains_present", REQUIRED_DOMAINS.issubset(domains), sorted(domains))
    add(checks, "all_corpus_cases_pass", bool(cases_payload) and all(case.get("passed") for case in cases_payload))
    add(checks, "corpus_manifest_counts_match", manifest.get("case_count") == case_count and manifest.get("assertion_count") == assertion_count)

    mutation_rows = mutations.get("mutations", [])
    add(checks, "all_critical_mutations_present", {item.get("mutation_id") for item in mutation_rows} == REQUIRED_MUTATIONS)
    add(checks, "all_critical_mutations_detected", len(mutation_rows) == 12 and all(item.get("detected") for item in mutation_rows))
    fixtures = benchmark.get("fixtures", [])
    add(checks, "performance_sizes_executed", [item.get("event_count") for item in fixtures] == [100, 1000, 10000])
    add(checks, "accelerated_equivalence_exact", benchmark.get("exact_acceleration_equivalence") is True and all(item.get("exact_equivalence") for item in fixtures))
    add(checks, "verified_acceleration_used", bool(fixtures) and all(item.get("acceleration_used") for item in fixtures))
    add(checks, "two_times_regression_gate_passes", benchmark.get("two_times_regression_gate") is True)
    add(checks, "performance_benchmark_passes", benchmark.get("result") == "PASS")
    specialized = benchmark.get("specialized_workloads", {})
    add(
        checks,
        "specialized_packet_workloads_measured",
        all(
            specialized.get(name, {}).get("median_ms") is not None
            for name in (
                "entity_packet",
                "relationship_heavy_packet",
                "conflict_heavy_packet",
                "packet_comparison",
            )
        ),
    )
    add(checks, "relationship_heavy_fixture_is_real", specialized.get("relationship_count", 0) >= 20)
    add(checks, "conflict_heavy_fixture_is_real", specialized.get("conflict_count", 0) >= 8)

    regression_rows = regressions.get("commands", [])
    add(checks, "all_sprint_1_12_and_secret_regressions_executed", len(regression_rows) == 25)
    add(checks, "all_sprint_1_12_and_secret_regressions_pass", regressions.get("result") == "PASS" and all(item.get("passed") for item in regression_rows))

    public_text = json.dumps(public, sort_keys=True)
    forbidden = re.compile(
        r"postgres(?:ql)?://|prmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}|"
        r"authorization\s*:\s*bearer|-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----",
        re.I,
    )
    add(checks, "public_report_contains_no_secrets", not forbidden.search(public_text))
    add(checks, "public_report_contains_no_source_content", "evidence_preview" not in public_text and "source_content" not in public_text)
    add(checks, "truth_boundaries_present", public.get("boundaries") == {"automatic_truth_determination": False, "production_certification": False, "scientific_validation": False})
    add(checks, "runner_public_result_passes", public.get("result") == "PASS")

    passed = sum(item["passed"] for item in checks)
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    audit = {
        "sprint": "Core Sprint 13",
        "independent_recalculation": True,
        "passed_checks": passed,
        "total_checks": len(checks),
        "failed_checks": [item for item in checks if not item["passed"]],
        "checks": checks,
        "database_url_recorded": False,
        "result": result,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "audit_continuity_packet_v2.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    scorecard = "\n".join(
        (
            "# Core Sprint 13 - Epistemic Continuity Packet V2",
            "",
            f"**Result: {result}**",
            "",
            f"- Independent audit: {passed}/{len(checks)} checks passed",
            f"- Benchmark corpus: {case_count} cases / {assertion_count} assertions",
            f"- Critical mutations detected: {mutations.get('detected_count', 0)}/12",
            f"- SQLite engine matrix: {private.get('sqlite', {}).get('result', 'MISSING')}",
            f"- Guarded PostgreSQL integration: {private.get('postgres', {}).get('result', 'MISSING')}",
            f"- Exact backend packet parity: {parity.get('result', 'MISSING')}",
            f"- Performance gate: {benchmark.get('result', 'MISSING')}",
            f"- Core Sprint 1-12 regressions: {regressions.get('result', 'MISSING')}",
            "",
            "## Boundary",
            "",
            "Internal deterministic synthetic engineering evidence only. This is not automatic truth determination, scientific validation, human-level understanding, production certification, or a completed public product.",
            "",
            "## Required Statement",
            "",
            REQUIRED_FINAL_STATEMENT,
            "",
        )
    )
    (REPORT_DIR / "scorecard_continuity_packet_v2.md").write_text(scorecard, encoding="utf-8")
    print("PRMR Memory Core - Core Sprint 13 Independent Audit")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Corpus: {case_count} cases / {assertion_count} assertions")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
