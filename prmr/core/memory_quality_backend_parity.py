"""Logical SQLite/PostgreSQL parity for memory-quality results."""

from __future__ import annotations

from typing import Any

from .memory_quality_policy import MEMORY_QUALITY_BACKEND_PARITY_REVISION


def compare_backend_results(
    sqlite_results: list[dict[str, Any]], postgres_results: list[dict[str, Any]]
) -> dict[str, Any]:
    sqlite = {item["benchmark_case_id"]: item for item in sqlite_results}
    postgres = {item["benchmark_case_id"]: item for item in postgres_results}
    all_ids = sorted(set(sqlite) | set(postgres))
    cases = []
    for case_id in all_ids:
        left = sqlite.get(case_id)
        right = postgres.get(case_id)
        equivalent = bool(
            left and right
            and left["case_status"] == right["case_status"]
            and left["result_hash"] == right["result_hash"]
            and [item["passed"] for item in left["assertion_results"]]
            == [item["passed"] for item in right["assertion_results"]]
        )
        cases.append({"benchmark_case_id": case_id, "equivalent": equivalent})
    return {
        "verified": bool(cases) and all(item["equivalent"] for item in cases),
        "compared_case_count": len(cases),
        "mismatch_count": sum(not item["equivalent"] for item in cases),
        "mismatched_case_ids": [item["benchmark_case_id"] for item in cases if not item["equivalent"]],
        "comparison_basis": [
            "case status", "assertion outcomes", "logical result hash"
        ],
        "excluded_backend_metadata": [
            "database version", "storage identities", "connection metadata", "duration"
        ],
        "revision": MEMORY_QUALITY_BACKEND_PARITY_REVISION,
    }


__all__ = ["compare_backend_results"]
