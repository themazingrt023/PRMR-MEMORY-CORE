"""Explicit per-capability metrics; intentionally no aggregate intelligence score."""

from __future__ import annotations

import math
from typing import Any

from .memory_quality_models import MemoryQualityBenchmarkCase, MemoryQualityCaseResult
from .memory_quality_policy import MEMORY_QUALITY_METRICS_REVISION


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    value = numerator / denominator if denominator else 0.0
    interval = wilson_interval(numerator, denominator) if denominator else None
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal": round(value, 8),
        "percentage": round(value * 100, 4),
        "wilson_95": interval,
    }


def wilson_interval(successes: int, total: int, z: float = 1.95996398454) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return [round(max(0.0, centre - margin), 8), round(min(1.0, centre + margin), 8)]


def calculate_metrics(
    cases: list[MemoryQualityBenchmarkCase],
    results: list[MemoryQualityCaseResult],
) -> dict[str, Any]:
    result_by_case = {item.benchmark_case_id: item for item in results}
    domains: dict[str, Any] = {}
    for domain in sorted({case.benchmark_domain for case in cases}):
        domain_cases = [case for case in cases if case.benchmark_domain == domain]
        domain_results = [result_by_case[case.benchmark_case_id] for case in domain_cases]
        assertions = [
            assertion
            for result in domain_results
            for assertion in result.assertion_results
        ]
        passed_assertions = sum(item.passed for item in assertions)
        domains[domain] = {
            "cases": len(domain_cases),
            "assertions": len(assertions),
            "passed_cases": sum(item.case_status == "passed" for item in domain_results),
            "failed_cases": sum(item.case_status != "passed" for item in domain_results),
            "exact_match_accuracy": rate(passed_assertions, len(assertions)),
            "evidence_completeness_rate": rate(
                sum(item.evidence_completeness == 1.0 for item in domain_results),
                len(domain_results),
            ),
        }

    labelled = [case for case in cases if "classification" in case.benchmark_tags]
    tp = fp = fn = tn = 0
    for case in labelled:
        result = result_by_case[case.benchmark_case_id]
        expected = "expected_positive" in case.benchmark_tags
        positive_assertion = next(
            item for item in result.assertion_results
            if item.assertion_id.endswith("_positive")
        )
        actual = expected if positive_assertion.passed else not expected
        if expected and actual:
            tp += 1
        elif not expected and actual:
            fp += 1
        elif expected and not actual:
            fn += 1
        else:
            tn += 1
    classification = {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": rate(tp, tp + fp),
        "recall": rate(tp, tp + fn),
        "specificity": rate(tn, tn + fp),
        "false_positive_rate": rate(fp, fp + tn),
        "false_negative_rate": rate(fn, fn + tp),
    }
    return {
        "revision": MEMORY_QUALITY_METRICS_REVISION,
        "domains": domains,
        "classification": classification,
        "total_cases": len(cases),
        "total_assertions": sum(
            len(item.assertion_results) for item in results
        ),
    }


__all__ = ["calculate_metrics", "rate", "wilson_interval"]
