"""Independent Core Sprint 12 evidence audit; summaries are not trusted."""

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

from prmr.core.memory_quality_corpus import load_corpus  # noqa: E402
from prmr.core.memory_quality_integrity import verify_memory_quality_corpus_integrity  # noqa: E402
from prmr.core.memory_quality_policy import CRITICAL_MUTATIONS, DOMAIN_MINIMUMS  # noqa: E402
from prmr.core.memory_quality_reports import REPORT_NAMES, write_json  # noqa: E402


CORPUS_DIR = ROOT / "benchmarks/memory_quality_v1"
REPORT_DIR = ROOT / "reports/core_memory_quality"


def add(checks: list[dict[str, Any]], name: str, passed: bool) -> None:
    checks.append({"name": name, "passed": bool(passed)})


def main() -> int:
    checks: list[dict[str, Any]] = []
    corpus_integrity = verify_memory_quality_corpus_integrity(CORPUS_DIR)
    manifest, cases = load_corpus(CORPUS_DIR)
    add(checks, "corpus_integrity_recalculated", corpus_integrity["verified"])
    add(checks, "minimum_250_cases", len(cases) >= 250)
    assertion_count = sum(len(case.expected_assertions) for case in cases)
    add(checks, "minimum_1000_assertions", assertion_count >= 1_000)
    distribution = Counter(case.benchmark_domain for case in cases)
    add(checks, "all_domain_minimums_met", all(distribution[name] >= count for name, count in DOMAIN_MINIMUMS.items()))
    for name in REPORT_NAMES:
        add(checks, f"report_{name}_exists", (REPORT_DIR / name).exists())

    sqlite = _load("case_results_sqlite.json")
    postgres = _load("case_results_postgres.json")
    metrics = _load("metrics_memory_quality.json")
    gates = _load("quality_gates_memory_quality.json")
    mutations = _load("mutation_results_memory_quality.json")
    parity = _load("backend_parity_memory_quality.json")
    adversarial = _load("adversarial_results_memory_quality.json")
    public = _load("public_memory_quality.json")
    private = _load("private_internal_memory_quality.json")

    for backend, evidence in (("sqlite", sqlite), ("postgres", postgres)):
        results = evidence.get("case_results", [])
        add(checks, f"{backend}_all_cases_executed", len(results) == len(cases))
        add(checks, f"{backend}_no_required_skip", all(item.get("case_status") != "skipped_with_reason" for item in results))
        add(checks, f"{backend}_all_cases_passed", all(item.get("case_status") == "passed" for item in results))
        add(checks, f"{backend}_restart_reproducible", evidence.get("restart_reproducibility", {}).get("verified") is True)
        recalculated = _metrics(results, cases)
        reported = metrics.get(backend, {}).get("domains", {})
        add(checks, f"{backend}_metrics_recalculated", all(
            reported.get(domain, {}).get("cases") == value["cases"]
            and reported.get(domain, {}).get("assertions") == value["assertions"]
            and reported.get(domain, {}).get("failed_cases") == value["failed_cases"]
            for domain, value in recalculated.items()
        ))
        add(checks, f"{backend}_quality_gates_recalculated", _gates_pass(recalculated, gates.get(backend, [])))

    sqlite_by_id = {item["benchmark_case_id"]: item for item in sqlite.get("case_results", [])}
    postgres_by_id = {item["benchmark_case_id"]: item for item in postgres.get("case_results", [])}
    parity_recalculated = (
        set(sqlite_by_id) == set(postgres_by_id)
        and all(
            sqlite_by_id[case_id]["result_hash"] == postgres_by_id[case_id]["result_hash"]
            and sqlite_by_id[case_id]["case_status"] == postgres_by_id[case_id]["case_status"]
            for case_id in sqlite_by_id
        )
    )
    add(checks, "backend_parity_recalculated", parity_recalculated and parity.get("verified") is True)
    mutation_rows = mutations.get("results", [])
    add(checks, "all_critical_mutations_present", {item.get("mutation_id") for item in mutation_rows} == set(CRITICAL_MUTATIONS))
    add(checks, "all_critical_mutations_detected", len(mutation_rows) == len(CRITICAL_MUTATIONS) and all(item.get("detected") for item in mutation_rows))
    add(checks, "adversarial_results_pass", adversarial.get("verified") is True)
    add(checks, "postgres_guard_was_verified", private.get("environment_status") == "VERIFIED_ISOLATED_TEST_DATABASE" and private.get("guard_preserved") is True)
    add(checks, "postgres_url_not_recorded", private.get("database_url_recorded") is False)
    public_text = json.dumps(public, sort_keys=True).lower()
    add(checks, "public_report_has_no_secret_patterns", not bool(re.search(
        r"postgres(?:ql)?://|prmr_(?:live|alpha)_[a-z0-9_-]{8,}|ghp_|github_pat_|authorization:\s*bearer",
        public_text, re.I,
    )))
    add(checks, "public_report_has_boundary", "internal" in public_text and "not scientific validation" in public_text)
    add(checks, "no_single_intelligence_score", "intelligence_score" not in public_text and "agi_score" not in public_text)
    add(checks, "runner_command_output_is_complete", public.get("result") in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"})

    passed = sum(item["passed"] for item in checks)
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    payload = {
        "result": result,
        "passed_checks": passed,
        "total_checks": len(checks),
        "failed_checks": [item for item in checks if not item["passed"]],
        "checks": checks,
        "independent_recalculation": True,
        "database_url_recorded": False,
    }
    write_json(REPORT_DIR / "audit_memory_quality.json", payload)
    print("PRMR Memory Core - Core Sprint 12 Independent Audit")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Corpus: {len(cases)} cases / {assertion_count} assertions")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


def _load(name: str) -> dict[str, Any]:
    path = REPORT_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _metrics(results: list[dict[str, Any]], cases: list[Any]) -> dict[str, dict[str, int]]:
    by_case = {item["benchmark_case_id"]: item for item in results}
    output = {}
    for domain in DOMAIN_MINIMUMS:
        selected = [case for case in cases if case.benchmark_domain == domain]
        selected_results = [by_case.get(case.benchmark_case_id, {}) for case in selected]
        output[domain] = {
            "cases": len(selected),
            "assertions": sum(len(item.get("assertion_results", [])) for item in selected_results),
            "failed_cases": sum(item.get("case_status") != "passed" for item in selected_results),
        }
    return output


def _gates_pass(recalculated: dict[str, dict[str, int]], gates: list[dict[str, Any]]) -> bool:
    required = [item for item in gates if item.get("metric") == "required_assertion_exactness"]
    return len(required) == len(DOMAIN_MINIMUMS) and all(
        item.get("passed") is (recalculated[item["domain"]]["failed_cases"] == 0)
        for item in required
    ) and all(item.get("passed") for item in gates)


if __name__ == "__main__":
    raise SystemExit(main())
