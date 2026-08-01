"""Independent bounded assertion evaluation for memory-quality evidence."""

from __future__ import annotations

from typing import Any

from .memory_quality_models import (
    MemoryQualityAssertionResult,
    MemoryQualityExpectedAssertion,
    deterministic_id,
)
from .source_integrity import canonical_json, sha256_text


MEMORY_QUALITY_ASSERTION_REVISION = "memory_quality_assertion_v1"


def select_path(value: Any, selector: str) -> tuple[bool, Any]:
    current = value
    if selector in {"", "$"}:
        return True, current
    for token in selector.removeprefix("$.").split("."):
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False, None
    return True, current


def compare_assertion(
    assertion: MemoryQualityExpectedAssertion, actual_manifest: dict[str, Any]
) -> tuple[bool, Any]:
    exists, actual = select_path(actual_manifest, assertion.target_selector)
    expected = assertion.expected_value
    operator = assertion.comparison_operator
    if operator == "exists":
        return exists, actual
    if operator == "does_not_exist":
        return not exists, actual
    if not exists:
        return False, None
    if operator in {"equals", "status_equals", "count_equals"}:
        passed = actual == expected
    elif operator == "not_equals":
        passed = actual != expected
    elif operator == "contains":
        passed = expected in actual
    elif operator == "does_not_contain":
        passed = expected not in actual
    elif operator == "set_equals":
        passed = set(actual) == set(expected)
    elif operator == "ordered_equals":
        passed = list(actual) == list(expected)
    elif operator == "greater_than_or_equal":
        passed = float(actual) >= float(expected)
    elif operator == "less_than_or_equal":
        passed = float(actual) <= float(expected)
    elif operator == "hash_equals":
        passed = sha256_text(canonical_json(actual)) == str(expected)
    else:
        raise ValueError(f"Unsupported comparison operator: {operator}")
    if assertion.tolerance is not None and isinstance(actual, (int, float)):
        passed = abs(float(actual) - float(expected)) <= assertion.tolerance
    return passed, actual


def safe_summary(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str) and len(value) <= 80:
        return value
    return f"sha256:{sha256_text(canonical_json(value))[:16]}"


def evaluate_assertions(
    *,
    case_result_id: str,
    assertions: list[MemoryQualityExpectedAssertion],
    actual_manifest: dict[str, Any],
    created_at: str,
) -> list[MemoryQualityAssertionResult]:
    results: list[MemoryQualityAssertionResult] = []
    for assertion in assertions:
        passed, actual = compare_assertion(assertion, actual_manifest)
        results.append(
            MemoryQualityAssertionResult(
                assertion_result_id=deterministic_id(
                    "mqares", [case_result_id, assertion.assertion_id]
                ),
                case_result_id=case_result_id,
                assertion_id=assertion.assertion_id,
                passed=passed,
                expected_value_digest=sha256_text(
                    canonical_json(assertion.expected_value)
                ),
                actual_value_digest=sha256_text(canonical_json(actual)),
                safe_expected_summary=safe_summary(assertion.expected_value),
                safe_actual_summary=safe_summary(actual),
                severity=assertion.severity,
                failure_category=None if passed else "assertion_mismatch",
                created_at=created_at,
            )
        )
    return results


__all__ = [
    "MEMORY_QUALITY_ASSERTION_REVISION", "compare_assertion",
    "evaluate_assertions", "select_path",
]
