"""Explicit test-only mutation sensitivity; unavailable to normal runtime paths."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .memory_quality_assertions import compare_assertion
from .memory_quality_models import MemoryQualityBenchmarkCase
from .memory_quality_policy import CRITICAL_MUTATIONS, MEMORY_QUALITY_MUTATION_REVISION


MUTATION_TARGETS: dict[str, tuple[str, str, Any, Any | None]] = {
    "disable_tenant_scope_check": ("runtime_backend_parity", "cross_tenant_leakage", True, False),
    "ignore_negation": ("epistemic_safety", "unsupported_completion", True, False),
    "promote_inferred_to_explicit": ("epistemic_safety", "epistemic_status", "explicit", "inferred"),
    "convert_unknown_to_observation": ("epistemic_safety", "event_type", "observation.recorded", "information.unknown"),
    "include_events_after_known_at": ("bitemporal_reconstruction", "future_leakage", True, False),
    "select_open_conflict_winner": ("bitemporal_reconstruction", "conflict_winner_selected", True, False),
    "merge_entities_by_label_only": ("entity_identity", "label_only_not_confirmed", False, True),
    "admit_inferred_relationship": ("relationships", "inferred_count", 0, 1),
    "activate_pending_canonical_mapping": ("interpretation", "pending_mapping_active", True, False),
    "trust_stale_consolidation": ("consolidation", "stale_checkpoint_used", True, False),
    "skip_evidence_hash_validation": ("source_fidelity", "integrity_verified", False, True),
    "omit_consolidation_member": ("consolidation", "missing_contributor", True, False),
    "leave_query_artifact_after_erasure": ("governance", "erasure_bypass", True, False),
    "permit_stale_governance_plan": ("governance", "stale_plan_executed", True, False),
    "duplicate_job_effect": ("runtime_backend_parity", "duplicate_authoritative_effect", True, False),
    "accept_old_lease_token": ("runtime_backend_parity", "old_lease_token_accepted", True, False),
    "skip_source_sanitisation": ("source_fidelity", "secret_persistence_failure", True, False),
    "fabricate_legacy_provenance": ("query_and_evidence", "legacy_provenance_fabricated", True, False),
}


def run_mutation_suite(
    cases: list[MemoryQualityBenchmarkCase],
    actual_by_case: dict[str, dict[str, Any]],
    *,
    mutation_test_mode: bool,
) -> dict[str, Any]:
    if not mutation_test_mode:
        raise RuntimeError("Memory-quality mutations require explicit test mode.")
    results = []
    for mutation_id in CRITICAL_MUTATIONS:
        domain, selector, mutated_value, required_expected = MUTATION_TARGETS[mutation_id]
        selected_case = None
        selected_assertion = None
        for case in cases:
            if case.benchmark_domain != domain:
                continue
            for assertion in case.expected_assertions:
                if assertion.target_selector != selector:
                    continue
                if required_expected is not None and assertion.expected_value != required_expected:
                    continue
                selected_case = case
                selected_assertion = assertion
                break
            if selected_case:
                break
        if selected_case is None or selected_assertion is None:
            results.append({"mutation_id": mutation_id, "detected": False, "safe_error": "target_not_found"})
            continue
        baseline = actual_by_case[selected_case.benchmark_case_id]
        baseline_passed, _ = compare_assertion(selected_assertion, baseline)
        mutated = deepcopy(baseline)
        mutated[selector] = mutated_value
        mutated_passed, _ = compare_assertion(selected_assertion, mutated)
        results.append({
            "mutation_id": mutation_id,
            "benchmark_case_id": selected_case.benchmark_case_id,
            "assertion_id": selected_assertion.assertion_id,
            "baseline_passed": baseline_passed,
            "mutated_passed": mutated_passed,
            "detected": baseline_passed and not mutated_passed,
        })
    detected = sum(item["detected"] for item in results)
    return {
        "verified": detected == len(CRITICAL_MUTATIONS),
        "critical_mutation_count": len(CRITICAL_MUTATIONS),
        "detected_count": detected,
        "detection_rate": detected / len(CRITICAL_MUTATIONS),
        "results": results,
        "test_only_boundary": True,
        "normal_runtime_activation_available": False,
        "revision": MEMORY_QUALITY_MUTATION_REVISION,
    }


__all__ = ["MUTATION_TARGETS", "run_mutation_suite"]
