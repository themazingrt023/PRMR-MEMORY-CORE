"""Strict policy validation for deterministic Memory Query V1."""

from __future__ import annotations

from dataclasses import replace

from .memory_query_models import MemoryQueryError, MemoryQueryPolicy, MemoryQueryRequest


HARD_MAXIMUM_RESULTS = 5_000
HARD_MAXIMUM_EVIDENCE_ITEMS = 1_000
HARD_MAXIMUM_PREVIEW_CHARACTERS = 2_000


def strict_query_policy(
    request: MemoryQueryRequest, policy: MemoryQueryPolicy | None = None
) -> MemoryQueryPolicy:
    selected = policy or MemoryQueryPolicy()
    if selected.policy_id != "strict_query_v1":
        raise MemoryQueryError(
            "MEMORY_QUERY_POLICY_INVALID", "The query policy is not available."
        )
    maximum_results = (
        request.maximum_results
        if request.maximum_results is not None
        else selected.maximum_results
    )
    maximum_evidence = (
        request.maximum_evidence_items
        if request.maximum_evidence_items is not None
        else selected.maximum_evidence_items
    )
    if not 1 <= maximum_results <= HARD_MAXIMUM_RESULTS:
        raise MemoryQueryError(
            "MEMORY_QUERY_LIMIT_EXCEEDED",
            "Requested result limit is outside the deterministic query policy.",
        )
    if not 0 <= maximum_evidence <= HARD_MAXIMUM_EVIDENCE_ITEMS:
        raise MemoryQueryError(
            "MEMORY_QUERY_LIMIT_EXCEEDED",
            "Requested evidence limit is outside the deterministic query policy.",
        )
    if not 0 <= selected.maximum_safe_preview_characters <= HARD_MAXIMUM_PREVIEW_CHARACTERS:
        raise MemoryQueryError(
            "MEMORY_QUERY_POLICY_INVALID", "Evidence preview limit is invalid."
        )
    return replace(
        selected,
        maximum_results=maximum_results,
        maximum_evidence_items=maximum_evidence,
        include_evidence=(
            selected.include_evidence
            if request.include_evidence is None
            else request.include_evidence
        ),
        include_safe_evidence_preview=(
            selected.include_safe_evidence_preview
            if request.include_safe_evidence_preview is None
            else request.include_safe_evidence_preview
        ),
        include_explanation=(
            selected.include_explanation
            if request.include_explanation is None
            else request.include_explanation
        ),
        include_packet=(
            selected.include_packet
            if request.include_packet is None
            else request.include_packet
        ),
        include_conflicted=(
            selected.include_conflicted
            if request.include_conflicted is None
            else request.include_conflicted
        ),
    )


__all__ = [
    "HARD_MAXIMUM_EVIDENCE_ITEMS",
    "HARD_MAXIMUM_PREVIEW_CHARACTERS",
    "HARD_MAXIMUM_RESULTS",
    "strict_query_policy",
]
