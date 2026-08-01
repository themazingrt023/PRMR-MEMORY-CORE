"""Print bounded performance observations for the memory-quality suite."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/core_memory_quality/benchmark_memory_quality.json"


def main() -> int:
    if not REPORT.exists():
        print("PRMR Core Sprint 12 Benchmark Observations: BLOCKED")
        return 2
    value = json.loads(REPORT.read_text(encoding="utf-8"))
    required = ("corpus_load_ms", "sqlite_run_ms", "postgres_run_ms", "total_ms")
    complete = all(value.get(key) is not None for key in required)
    print("PRMR Memory Core - Core Sprint 12 Performance Observations")
    print(f"Corpus load: {value.get('corpus_load_ms')} ms")
    print(f"SQLite run: {value.get('sqlite_run_ms')} ms")
    print(f"PostgreSQL run: {value.get('postgres_run_ms')} ms")
    print(f"Mutation suite: {value.get('mutation_suite_ms')} ms")
    print(f"Parity comparison: {value.get('parity_comparison_ms')} ms")
    print(f"Peak traced memory: {value.get('peak_traced_memory_bytes')} bytes")
    print(f"Result: {'PASS_OBSERVATIONS_RECORDED' if complete else 'BLOCKED'}")
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
