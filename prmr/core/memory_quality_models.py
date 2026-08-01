"""Versioned contracts for the PRMR Memory Quality Benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .source_integrity import canonical_json, sha256_text


MEMORY_QUALITY_SCHEMA_REVISION = "memory_quality_v1"
MEMORY_QUALITY_ORACLE_REVISION = "memory_quality_oracle_v1"
MEMORY_QUALITY_ASSERTION_REVISION = "memory_quality_assertion_v1"

COMPARISON_OPERATORS = {
    "equals", "not_equals", "contains", "does_not_contain", "set_equals",
    "ordered_equals", "greater_than_or_equal", "less_than_or_equal", "exists",
    "does_not_exist", "hash_equals", "status_equals", "count_equals",
}
SEVERITIES = {"critical", "major", "minor", "informational"}
CASE_STATUSES = {"passed", "failed", "blocked", "skipped_with_reason"}
RUN_STATUSES = {"running", "passed", "failed", "blocked", "invalidated"}


def deterministic_id(prefix: str, payload: Any) -> str:
    return f"{prefix}_{sha256_text(canonical_json(payload))[:24]}"


@dataclass(frozen=True)
class MemoryQualityExpectedAssertion:
    assertion_id: str
    assertion_type: str
    target_type: str
    target_selector: str
    expected_value: Any
    comparison_operator: str
    tolerance: float | None
    required: bool
    severity: str
    rationale: str
    oracle_revision: str = MEMORY_QUALITY_ORACLE_REVISION

    def __post_init__(self) -> None:
        if self.comparison_operator not in COMPARISON_OPERATORS:
            raise ValueError("Unsupported memory-quality comparison operator.")
        if self.severity not in SEVERITIES:
            raise ValueError("Unsupported memory-quality assertion severity.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryQualityExpectedAssertion":
        return cls(**value)


@dataclass(frozen=True)
class MemoryQualityBenchmarkCase:
    benchmark_case_id: str
    benchmark_domain: str
    case_name: str
    case_description: str
    severity: str
    fixture_seed: int
    source_inputs: list[dict[str, Any]]
    operation_sequence: list[dict[str, Any]]
    temporal_boundaries: dict[str, str | None]
    authenticated_scope: dict[str, str]
    expected_assertions: list[MemoryQualityExpectedAssertion]
    prohibited_assertions: list[dict[str, Any]]
    expected_evidence: dict[str, Any]
    expected_epistemic_status: str | None
    expected_result_status: str
    expected_error_code: str | None
    backend_requirements: list[str]
    benchmark_tags: list[str]
    corpus_revision: str
    created_at: str

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError("Unsupported memory-quality case severity.")
        if not self.operation_sequence or not self.expected_assertions:
            raise ValueError("Benchmark cases require operations and assertions.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["expected_assertions"] = [
            item.to_dict() for item in self.expected_assertions
        ]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryQualityBenchmarkCase":
        payload = dict(value)
        payload["expected_assertions"] = [
            MemoryQualityExpectedAssertion.from_dict(item)
            for item in payload["expected_assertions"]
        ]
        return cls(**payload)


@dataclass(frozen=True)
class MemoryQualityAssertionResult:
    assertion_result_id: str
    case_result_id: str
    assertion_id: str
    passed: bool
    expected_value_digest: str
    actual_value_digest: str
    safe_expected_summary: str
    safe_actual_summary: str
    severity: str
    failure_category: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQualityCaseResult:
    case_result_id: str
    benchmark_run_id: str
    benchmark_case_id: str
    backend: str
    case_status: str
    assertion_results: list[MemoryQualityAssertionResult]
    expected_output_manifest: str
    actual_output_manifest: str
    prohibited_output_hits: list[str]
    evidence_completeness: float
    epistemic_result: str
    duration_ms: float
    safe_failure_details: dict[str, Any] | None
    result_hash: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["assertion_results"] = [
            item.to_dict() for item in self.assertion_results
        ]
        return value


@dataclass(frozen=True)
class MemoryQualityGateResult:
    gate_id: str
    domain: str
    metric: str
    threshold: str
    actual: float
    passed: bool
    severity: str
    failure_count: int
    affected_case_ids: list[str]
    revision: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryQualityBenchmarkRun:
    benchmark_run_id: str
    corpus_manifest_hash: str
    backend: str
    database_version: str
    engine_revision_manifest: dict[str, str]
    policy_revision: str
    started_at: str
    completed_at: str | None
    case_count: int
    assertion_count: int
    passed_case_count: int
    failed_case_count: int
    critical_failure_count: int
    metric_results: dict[str, Any]
    mutation_results: dict[str, Any]
    parity_result: dict[str, Any]
    result_manifest_hash: str
    run_status: str
    created_at: str

    def __post_init__(self) -> None:
        if self.run_status not in RUN_STATUSES:
            raise ValueError("Unsupported memory-quality run status.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "CASE_STATUSES", "COMPARISON_OPERATORS", "MEMORY_QUALITY_ASSERTION_REVISION",
    "MEMORY_QUALITY_ORACLE_REVISION", "MEMORY_QUALITY_SCHEMA_REVISION",
    "MemoryQualityAssertionResult", "MemoryQualityBenchmarkCase",
    "MemoryQualityBenchmarkRun", "MemoryQualityCaseResult",
    "MemoryQualityExpectedAssertion", "MemoryQualityGateResult", "deterministic_id",
]
