"""Canonical query-result projections over existing core-engine outputs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from .memory_query_models import EpistemicSummary, MemoryQueryResultStatus


def event_signal(event: dict[str, Any]) -> str:
    return str(
        event.get("content")
        or event.get("signal")
        or event.get("summary")
        or event.get("type")
        or event.get("event_type")
        or ""
    )


def event_type(event: dict[str, Any]) -> str:
    return str(event.get("type") or event.get("event_type") or "event.recorded")


def event_time(event: dict[str, Any]) -> str:
    return str(event.get("timestamp") or event.get("occurred_at") or "")


def signal_key_for_event(event: dict[str, Any]) -> str:
    metadata = event.get("external_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    nested = metadata.get("metadata", {})
    if not isinstance(nested, dict):
        nested = {}
    return str(
        nested.get("signal_key")
        or metadata.get("signal_key")
        or event.get("signal_key")
        or event_type(event)
    )


def epistemic_status_for_event(event: dict[str, Any]) -> str:
    metadata = event.get("external_metadata", {})
    nested = metadata.get("metadata", {}) if isinstance(metadata, dict) else {}
    if not isinstance(nested, dict):
        nested = {}
    return str(
        nested.get("epistemic_status")
        or event.get("epistemic_status")
        or "legacy_unclassified"
    )


def ordered_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda item: (
            event_time(item),
            int(item.get("timestamp_index", 0)),
            str(item.get("event_id", "")),
        ),
    )


def current_event(events: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    values = ordered_events(events)
    return values[-1] if values else None


def safe_event_projection(
    event: dict[str, Any],
    projection: Any | None = None,
    signal: Any | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(event.get("event_id", "")),
        "event_type": event_type(event),
        "exact_signal": event_signal(event),
        "signal_key": signal_key_for_event(event),
        "occurred_at": event_time(event),
        "valid_at": getattr(projection, "valid_from", event_time(event)),
        "known_at": getattr(projection, "system_known_from", event_time(event)),
        "event_time_basis": getattr(signal, "event_time_basis", None),
        "effective_state": getattr(projection, "effective_state", "active"),
        "epistemic_status": getattr(
            projection, "epistemic_status", epistemic_status_for_event(event)
        ),
        "memory_phase": getattr(signal, "memory_phase", None),
        "temporal_horizon": getattr(signal, "latest_horizon", None),
        "final_influence": getattr(signal, "final_influence", None),
        "conflicted": bool(getattr(projection, "open_conflict_ids", [])),
        "open_conflict_ids": list(getattr(projection, "open_conflict_ids", [])),
        "resolved_conflict_ids": list(
            getattr(projection, "resolved_conflict_ids", [])
        ),
        "source_id": getattr(projection, "source_id", None),
        "admission_id": getattr(projection, "admission_id", None),
        "evolution_ids": [],
    }


def phase_record(signal: Any) -> dict[str, Any]:
    return {
        "signal_key": signal.signal_key,
        "signal_identity_source": signal.signal_identity_source,
        "memory_phase": signal.memory_phase,
        "final_influence": signal.final_influence,
        "occurrence_count": signal.occurrence_count,
        "reinforced": signal.reinforced,
        "re_emerging": signal.re_emerging,
        "first_occurrence_at": signal.first_occurrence_at,
        "latest_occurrence_at": signal.latest_occurrence_at,
        "epistemic_status_counts": dict(signal.epistemic_status_counts),
        "open_conflict_ids": list(signal.open_conflict_ids),
        "event_references": list(signal.occurrence_event_ids),
        "source_count": signal.source_count,
        "evidence_available": signal.source_count > 0,
    }


def recurrence_record(signal: Any) -> dict[str, Any]:
    return {
        **phase_record(signal),
        "distinct_horizon_count": signal.distinct_horizon_count,
        "occurrences_by_horizon": dict(signal.occurrences_by_horizon),
        "recurrence_boost": signal.recurrence_boost,
        "cross_horizon_boost": signal.cross_horizon_boost,
        "maximum_gap_seconds": signal.maximum_gap_seconds,
        "maximum_gap_event_count": signal.maximum_gap_event_count,
        "recurrence_span_seconds": signal.recurrence_span_seconds,
    }


def reemergence_record(signal: Any) -> dict[str, Any]:
    return {
        "signal_key": signal.signal_key,
        "prior_occurrence_event_id": signal.prior_occurrence_event_id,
        "latest_occurrence_event_id": signal.latest_occurrence_event_id,
        "gap_duration_seconds": signal.reemergence_gap_seconds,
        "intervening_event_count": signal.reemergence_gap_event_count,
        "prior_phase": signal.prior_memory_phase,
        "current_phase": signal.memory_phase,
        "re_emergence_count": signal.re_emergence_count,
        "evidence_references": list(signal.source_ids),
        "epistemic_distribution": dict(signal.epistemic_status_counts),
        "conflict_state": {
            "conflicted": signal.conflicted,
            "open_conflict_ids": list(signal.open_conflict_ids),
        },
    }


def build_epistemic_summary(payload: Any) -> EpistemicSummary:
    counts = {
        "explicit": 0,
        "derived": 0,
        "inferred": 0,
        "unknown": 0,
        "conflicted": 0,
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            status = value.get("epistemic_status")
            if status in counts:
                counts[status] += 1
            status_counts = value.get("epistemic_status_counts")
            if isinstance(status_counts, dict):
                for key in ("explicit", "derived", "inferred", "unknown"):
                    counts[key] += int(status_counts.get(key, 0))
            if value.get("conflicted") is True:
                counts["conflicted"] += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(payload)
    epistemic = {key: counts[key] for key in ("explicit", "derived", "inferred", "unknown")}
    dominant = max(epistemic, key=lambda key: (epistemic[key], key))
    if epistemic[dominant] == 0:
        dominant = None
    return EpistemicSummary(
        explicit_item_count=counts["explicit"],
        derived_item_count=counts["derived"],
        inferred_item_count=counts["inferred"],
        unknown_item_count=counts["unknown"],
        conflicted_item_count=counts["conflicted"],
        dominant_epistemic_status=dominant,
        contains_unconfirmed_information=bool(
            counts["derived"] or counts["inferred"] or counts["unknown"]
        ),
        contains_unknown_information=counts["unknown"] > 0,
        contains_conflict=counts["conflicted"] > 0,
    )


def result_status_for(
    payload: dict[str, Any],
    *,
    no_data: bool = False,
    partial: bool = False,
    truncated: bool = False,
) -> str:
    if truncated:
        return MemoryQueryResultStatus.TRUNCATED.value
    if no_data:
        return MemoryQueryResultStatus.NO_DATA.value
    summary = build_epistemic_summary(payload)
    if summary.contains_conflict:
        return MemoryQueryResultStatus.CONFLICTED.value
    if summary.contains_unknown_information:
        return MemoryQueryResultStatus.UNKNOWN.value
    if partial:
        return MemoryQueryResultStatus.PARTIAL.value
    return MemoryQueryResultStatus.ANSWERED.value


def canonical_items(payload: dict[str, Any]) -> list[Any]:
    for key in (
        "items",
        "events",
        "signals",
        "conflicts",
        "relationships",
        "history",
        "unknown_items",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return [payload] if payload else []


__all__ = [
    "build_epistemic_summary",
    "canonical_items",
    "current_event",
    "epistemic_status_for_event",
    "event_signal",
    "event_time",
    "event_type",
    "ordered_events",
    "phase_record",
    "recurrence_record",
    "reemergence_record",
    "result_status_for",
    "safe_event_projection",
    "signal_key_for_event",
]
