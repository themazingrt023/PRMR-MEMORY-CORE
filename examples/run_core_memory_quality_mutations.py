"""Run the explicit test-only Core Sprint 12 critical mutation suite."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.memory_quality_corpus import load_corpus  # noqa: E402
from prmr.core.memory_quality_mutations import run_mutation_suite  # noqa: E402
from prmr.core.memory_quality_reports import write_json  # noqa: E402


CORPUS_DIR = ROOT / "benchmarks/memory_quality_v1"
REPORT_DIR = ROOT / "reports/core_memory_quality"


def main() -> int:
    _, cases = load_corpus(CORPUS_DIR)
    private_path = REPORT_DIR / "private_internal_memory_quality.json"
    if not private_path.exists():
        print("PRMR Core Sprint 12 Mutations: BLOCKED (baseline report missing)")
        return 2
    private = json.loads(private_path.read_text(encoding="utf-8"))
    actual = private.get("baseline_actual_sqlite")
    if not actual:
        print("PRMR Core Sprint 12 Mutations: BLOCKED (SQLite actual manifests missing)")
        return 2
    result = run_mutation_suite(cases, actual, mutation_test_mode=True)
    write_json(REPORT_DIR / "mutation_results_memory_quality.json", result)
    print("PRMR Memory Core - Core Sprint 12 Mutation Sensitivity")
    print(f"Critical mutations detected: {result['detected_count']}/{result['critical_mutation_count']}")
    print(f"Result: {'PASS' if result['verified'] else 'NEEDS_WORK'}")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
