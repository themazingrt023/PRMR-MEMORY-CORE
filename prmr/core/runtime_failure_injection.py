"""Explicitly test-only deterministic runtime failure injection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


class InjectedRuntimeFailure(RuntimeError):
    def __init__(self, injection_point: str, *, crash: bool = True) -> None:
        super().__init__(f"Injected failure at {injection_point}.")
        self.injection_point = injection_point
        self.crash = crash
        self.code = "RUNTIME_FAILURE_INJECTED"
        self.safe_detail = f"Test-only failure injected at {injection_point}."


INJECTION_POINTS = {
    "before_transaction",
    "after_first_write",
    "before_event_insert",
    "after_event_insert",
    "before_admitted_link",
    "after_checkpoint_creation",
    "before_governance_deletion_batch",
    "after_governance_deletion_batch",
    "before_tombstone",
    "after_tombstone",
    "before_job_completion",
    "after_effect_commit_before_job_completion",
    "during_heartbeat",
    "during_connection_acquisition",
    "during_serialization_conflict",
}


@dataclass
class RuntimeFailureInjector:
    enabled_for_tests: bool = False
    fail_counts: dict[str, int] = field(default_factory=dict)
    crash_points: set[str] = field(default_factory=set)
    observed: Counter[str] = field(default_factory=Counter)

    def inject(self, point: str) -> None:
        if point not in INJECTION_POINTS:
            raise ValueError(f"Unknown runtime failure injection point: {point}")
        if not self.enabled_for_tests:
            return
        self.observed[point] += 1
        remaining = int(self.fail_counts.get(point, 0))
        if remaining <= 0:
            return
        self.fail_counts[point] = remaining - 1
        raise InjectedRuntimeFailure(point, crash=point in self.crash_points)


__all__ = [
    "INJECTION_POINTS",
    "InjectedRuntimeFailure",
    "RuntimeFailureInjector",
]
