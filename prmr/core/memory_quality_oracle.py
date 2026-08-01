"""Independent gold-oracle validation; this module never calls the engine."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .memory_quality_models import MemoryQualityBenchmarkCase
from .memory_quality_policy import DOMAIN_MINIMUMS, MEMORY_QUALITY_CORPUS_REVISION


MEMORY_QUALITY_ORACLE_REVISION = "memory_quality_oracle_v1"


def validate_gold_oracle(cases: list[MemoryQualityBenchmarkCase]) -> dict[str, Any]:
    domains = Counter(case.benchmark_domain for case in cases)
    assertion_ids = [
        assertion.assertion_id
        for case in cases
        for assertion in case.expected_assertions
    ]
    case_ids = [case.benchmark_case_id for case in cases]
    checks = {
        "minimum_case_count": len(cases) >= 250,
        "minimum_assertion_count": len(assertion_ids) >= 1_000,
        "domain_minimums": all(domains[name] >= count for name, count in DOMAIN_MINIMUMS.items()),
        "unique_case_ids": len(case_ids) == len(set(case_ids)),
        "unique_assertion_ids": len(assertion_ids) == len(set(assertion_ids)),
        "fixed_corpus_revision": all(case.corpus_revision == MEMORY_QUALITY_CORPUS_REVISION for case in cases),
        "explicit_operations": all(case.operation_sequence for case in cases),
        "explicit_assertions": all(case.expected_assertions for case in cases),
        "no_executable_assertions": all(
            assertion.comparison_operator != "eval"
            for case in cases for assertion in case.expected_assertions
        ),
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "case_count": len(cases),
        "assertion_count": len(assertion_ids),
        "domain_distribution": dict(sorted(domains.items())),
        "revision": MEMORY_QUALITY_ORACLE_REVISION,
    }


__all__ = ["MEMORY_QUALITY_ORACLE_REVISION", "validate_gold_oracle"]
