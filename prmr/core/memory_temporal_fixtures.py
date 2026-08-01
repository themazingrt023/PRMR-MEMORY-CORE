"""Deterministic synthetic fixtures for Temporal Memory Dynamics V1."""

from __future__ import annotations

from dataclasses import dataclass

from .source_models import SourceInput


@dataclass(frozen=True)
class TemporalMemoryFixture:
    name: str
    event_type: str
    occurred_at: str
    signal: str

    def source(self, *, idempotency_suffix: str = "") -> SourceInput:
        suffix = f":{idempotency_suffix}" if idempotency_suffix else ""
        return SourceInput(
            "json",
            {
                "event_type": self.event_type,
                "signal": self.signal,
                "occurred_at": self.occurred_at,
                "metadata": {"fixture": self.name, "synthetic": True},
            },
            occurred_at=self.occurred_at,
            metadata={
                "fixture": self.name,
                "synthetic": True,
                "canonical_signal": self.event_type,
            },
            idempotency_key=f"temporal-memory-v1:{self.name}{suffix}",
        )


def temporal_memory_fixtures() -> dict[str, TemporalMemoryFixture]:
    values = {
        "natural_decay": (
            "goal.created",
            "2026-01-01T00:00:00Z",
            "A synthetic goal was created.",
        ),
        "project_1": (
            "status.updated",
            "2026-01-01T00:00:00Z",
            "Synthetic project update one.",
        ),
        "project_2": (
            "status.updated",
            "2026-05-01T00:00:00Z",
            "Synthetic project update two.",
        ),
        "project_3": (
            "status.updated",
            "2026-06-24T00:00:00Z",
            "Synthetic project update three.",
        ),
        "project_4": (
            "status.updated",
            "2026-07-01T00:00:00Z",
            "Synthetic project update four.",
        ),
        "blocker_old": (
            "blocker.detected",
            "2026-01-01T00:00:00Z",
            "A synthetic blocker was recorded.",
        ),
        "blocker_returned": (
            "blocker.detected",
            "2026-07-01T00:00:00Z",
            "The synthetic blocker returned after absence.",
        ),
        "importance_normal": (
            "observation.recorded",
            "2026-05-01T00:00:00Z",
            "A neutral-importance synthetic event.",
        ),
        "importance_critical": (
            "observation.recorded",
            "2026-05-01T00:00:00Z",
            "A critical-importance synthetic event.",
        ),
        "late_arrival": (
            "observation.recorded",
            "2026-01-01T00:00:00Z",
            "A synthetic late-arriving checkpoint.",
        ),
        "supersession_old": (
            "status.updated",
            "2026-04-01T00:00:00Z",
            "Synthetic status before supersession.",
        ),
        "supersession_new": (
            "status.updated",
            "2026-07-01T00:00:00Z",
            "Synthetic successor status.",
        ),
        "retraction": (
            "observation.recorded",
            "2026-06-01T00:00:00Z",
            "Synthetic claim later retracted.",
        ),
        "conflict_a": (
            "status.updated",
            "2026-07-01T00:00:00Z",
            "Synthetic service state A.",
        ),
        "conflict_b": (
            "status.updated",
            "2026-07-01T00:05:00Z",
            "Synthetic incompatible service state B.",
        ),
        "conflict_resolution": (
            "observation.recorded",
            "2026-07-01T00:10:00Z",
            "Synthetic explicit conflict resolution.",
        ),
    }
    return {
        name: TemporalMemoryFixture(name, event_type, occurred_at, signal)
        for name, (event_type, occurred_at, signal) in values.items()
    }


__all__ = ["TemporalMemoryFixture", "temporal_memory_fixtures"]
