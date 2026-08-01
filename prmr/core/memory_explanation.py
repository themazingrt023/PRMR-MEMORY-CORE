"""Versioned structural explanations for deterministic memory query results."""

from __future__ import annotations

from typing import Any

from .memory_query_models import (
    MEMORY_EXPLANATION_REVISION,
    MemoryEvidenceBundle,
    MemoryExplanation,
    MemoryQueryPlan,
    MemoryQueryResultStatus,
)
from .memory_query_planner import utc
from .source_integrity import canonical_json, sha256_text


TEMPLATES = {
    "current_state": "current_state_selection_v1",
    "memory_by_phase": "memory_phase_filter_v1",
    "changes_between": "bitemporal_change_projection_v1",
    "event_timeline": "event_timeline_ordering_v1",
    "signal_history": "exact_signal_history_v1",
    "recurrence": "recurrence_projection_v1",
    "re_emergence": "reemergence_projection_v1",
    "open_conflicts": "open_conflict_projection_v1",
    "resolved_conflicts": "resolved_conflict_projection_v1",
    "recoverability_explanation": "recoverability_factors_v1",
}


def build_memory_explanation(
    *,
    query_run_id: str,
    query_result_id: str,
    query_type: str,
    result_status: str,
    answer_payload: dict[str, Any],
    plan: MemoryQueryPlan,
    evidence_bundle: MemoryEvidenceBundle | None,
    excluded_counts: dict[str, int],
) -> MemoryExplanation:
    template = TEMPLATES.get(query_type, "deterministic_projection_v1")
    summary = _summary(query_type, result_status, answer_payload)
    basis = _basis(answer_payload, evidence_bundle)
    exclusions = [
        {"reason": reason, "count": count}
        for reason, count in sorted(excluded_counts.items())
        if count
    ]
    epistemic_warnings = []
    if _contains_status(answer_payload, "inferred"):
        epistemic_warnings.append(
            "Inferred information remains labelled inferred and is not confirmed fact."
        )
    if _contains_status(answer_payload, "derived"):
        epistemic_warnings.append(
            "Derived information remains labelled derived."
        )
    conflict_warnings = (
        ["No automatic winner was selected for unresolved conflicting memory."]
        if result_status == MemoryQueryResultStatus.CONFLICTED.value
        else []
    )
    unknown_warnings = (
        ["Missing information remains unknown; the query did not fill the gap."]
        if result_status == MemoryQueryResultStatus.UNKNOWN.value
        else []
    )
    material = {
        "query_run_id": query_run_id,
        "query_result_id": query_result_id,
        "query_type": query_type,
        "status": result_status,
        "template": template,
        "summary": summary,
        "basis": basis,
        "steps": plan.plan_steps,
        "exclusions": exclusions,
        "epistemic_warnings": epistemic_warnings,
        "conflict_warnings": conflict_warnings,
        "unknown_warnings": unknown_warnings,
        "policy_references": [plan.query_policy_id],
        "revision_references": [
            MEMORY_EXPLANATION_REVISION,
            plan.memory_query_planner_revision,
        ],
    }
    digest = sha256_text(canonical_json(material))
    return MemoryExplanation(
        explanation_id=f"xpln_{digest[:24]}",
        query_run_id=query_run_id,
        query_result_id=query_result_id,
        explanation_type=query_type,
        explanation_status=(
            "not_applicable"
            if result_status == MemoryQueryResultStatus.NOT_APPLICABLE.value
            else result_status
        ),
        summary_template_id=template,
        summary_text=summary,
        basis_items=basis,
        selection_steps=list(plan.plan_steps),
        exclusions=exclusions,
        epistemic_warnings=epistemic_warnings,
        conflict_warnings=conflict_warnings,
        unknown_warnings=unknown_warnings,
        policy_references=[plan.query_policy_id],
        revision_references=[
            MEMORY_EXPLANATION_REVISION,
            plan.memory_query_planner_revision,
        ],
        explanation_hash_sha256=digest,
        memory_explanation_revision=MEMORY_EXPLANATION_REVISION,
        created_at=utc(None),
    )


def _summary(query_type: str, status: str, payload: dict[str, Any]) -> str:
    if status == MemoryQueryResultStatus.CONFLICTED.value:
        return (
            "The result remains conflicted because incompatible effective memories "
            "are linked by an unresolved conflict. No winner was selected."
        )
    if status == MemoryQueryResultStatus.UNKNOWN.value:
        return "The available admitted memory records the requested information as unknown."
    if status == MemoryQueryResultStatus.NO_DATA.value:
        return "No eligible memory existed at the requested temporal boundary."
    if query_type == "current_state":
        event_id = payload.get("current_state_event_id")
        return (
            f"PRMR selected event {event_id} as current state because it is the "
            "latest effective event at the requested temporal boundary."
        )
    if query_type == "memory_by_phase":
        return "Signals were filtered by the requested deterministic memory phase."
    if query_type == "recurrence":
        return (
            "Repetition increases continuity influence under the configured policy. "
            "It does not prove factual truth."
        )
    if query_type == "re_emergence":
        return (
            "Re-emergence records a signal returning after the configured time and "
            "intervening-event gap; immediate repetition is excluded."
        )
    if query_type == "recoverability_explanation":
        return (
            "This score measures structural support for reconstructing memory under "
            "the existing deterministic policy. It is not a probability that the "
            "memory is true."
        )
    return "The answer is a deterministic projection of authorised memory objects."


def _basis(
    payload: dict[str, Any], evidence_bundle: MemoryEvidenceBundle | None
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for key in (
        "current_state_event_id",
        "packet_id",
        "reconstruction_id",
        "dynamics_snapshot_id",
        "canonical_entity_id",
        "relationship_id",
        "conflict_id",
    ):
        value = payload.get(key)
        if value:
            output.append({"basis_type": key, "identifier": value})
    if evidence_bundle:
        output.append(
            {
                "basis_type": "evidence_bundle",
                "identifier": evidence_bundle.evidence_bundle_id,
                "completeness_status": evidence_bundle.completeness_status,
            }
        )
    return output


def _contains_status(payload: Any, wanted: str) -> bool:
    if isinstance(payload, dict):
        if payload.get("epistemic_status") == wanted:
            return True
        counts = payload.get("epistemic_status_counts")
        if isinstance(counts, dict) and int(counts.get(wanted, 0)) > 0:
            return True
        return any(_contains_status(value, wanted) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_status(value, wanted) for value in payload)
    return False


__all__ = ["TEMPLATES", "build_memory_explanation"]
