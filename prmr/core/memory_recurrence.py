"""Deterministic structural signal identity and recurrence calculations."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .memory_temporal_models import SIGNAL_IDENTITY_REVISION, MemoryDynamicsError


SIGNAL_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


def event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    direct = event.get("metadata")
    external = event.get("external_metadata")
    nested = external.get("metadata") if isinstance(external, dict) else None
    merged: dict[str, Any] = {}
    if isinstance(direct, dict):
        merged.update(direct)
    if isinstance(nested, dict):
        merged.update(nested)
    return merged


def signal_identity(event: dict[str, Any]) -> tuple[str, str]:
    metadata = event_metadata(event)
    candidate = metadata.get("canonical_signal") or event.get("canonical_signal")
    if isinstance(candidate, str) and SIGNAL_PATTERN.fullmatch(candidate):
        return candidate, "canonical_signal"
    event_type = str(event.get("type") or event.get("event_type") or "").lower()
    if not SIGNAL_PATTERN.fullmatch(event_type):
        raise MemoryDynamicsError(
            "MEMORY_RECURRENCE_CALCULATION_FAILED",
            "Event does not contain a valid structural signal identity.",
        )
    return event_type, "event_type"


def group_occurrences(
    occurrences: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for occurrence in sorted(
        occurrences,
        key=lambda item: (
            item["occurred_at"],
            item["global_index"],
            item["event_id"],
        ),
    ):
        grouped.setdefault(occurrence["signal_key"], []).append(occurrence)
    return dict(sorted(grouped.items()))


def recurrence_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    horizon_counts = Counter(item["horizon"] for item in items)
    gaps_seconds = [
        max(0.0, right["occurred_epoch"] - left["occurred_epoch"])
        for left, right in zip(items, items[1:])
    ]
    gaps_events = [
        max(0, right["global_index"] - left["global_index"] - 1)
        for left, right in zip(items, items[1:])
    ]
    return {
        "occurrence_count": len(items),
        "first_occurrence_at": items[0]["occurred_at"],
        "latest_occurrence_at": items[-1]["occurred_at"],
        "occurrence_event_ids": [item["event_id"] for item in items],
        "occurrences_by_horizon": dict(sorted(horizon_counts.items())),
        "distinct_horizon_count": len(horizon_counts),
        "maximum_gap_seconds": max(gaps_seconds, default=0.0),
        "maximum_gap_event_count": max(gaps_events, default=0),
        "recurrence_span_seconds": max(
            0.0, items[-1]["occurred_epoch"] - items[0]["occurred_epoch"]
        ),
        "signal_identity_revision": SIGNAL_IDENTITY_REVISION,
    }


__all__ = [
    "SIGNAL_PATTERN",
    "event_metadata",
    "group_occurrences",
    "recurrence_summary",
    "signal_identity",
]
