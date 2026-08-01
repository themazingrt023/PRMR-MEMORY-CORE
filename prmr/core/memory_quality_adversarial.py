"""Adversarial-result extraction from the independently versioned corpus."""

from __future__ import annotations

from typing import Any

from .memory_quality_models import MemoryQualityBenchmarkCase
from .memory_quality_policy import MEMORY_QUALITY_ADVERSARIAL_REVISION


def adversarial_results(
    cases: list[MemoryQualityBenchmarkCase],
    sqlite_results: list[dict[str, Any]],
    postgres_results: list[dict[str, Any]],
) -> dict[str, Any]:
    adversarial_ids = {
        case.benchmark_case_id for case in cases
        if "adversarial" in case.benchmark_tags
    }
    by_backend = {}
    for backend, results in (("sqlite", sqlite_results), ("postgres", postgres_results)):
        selected = [item for item in results if item["benchmark_case_id"] in adversarial_ids]
        by_backend[backend] = {
            "case_count": len(selected),
            "passed": sum(item["case_status"] == "passed" for item in selected),
            "failed": sum(item["case_status"] != "passed" for item in selected),
            "critical_failure_count": sum(item["case_status"] != "passed" for item in selected),
        }
    return {
        "verified": bool(adversarial_ids) and all(value["failed"] == 0 for value in by_backend.values()),
        "case_ids": sorted(adversarial_ids),
        "backends": by_backend,
        "revision": MEMORY_QUALITY_ADVERSARIAL_REVISION,
    }


__all__ = ["adversarial_results"]
