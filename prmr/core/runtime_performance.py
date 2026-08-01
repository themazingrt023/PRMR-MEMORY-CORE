"""Local runtime performance measurement helpers without production claims."""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
import time
from typing import Any, Callable

from .runtime_models import RUNTIME_PERFORMANCE_REVISION


@dataclass(frozen=True)
class TimingSeries:
    samples_ms: tuple[float, ...]

    @property
    def median_ms(self) -> float:
        return round(statistics.median(self.samples_ms), 2)

    @property
    def p95_ms(self) -> float:
        ordered = sorted(self.samples_ms)
        index = max(0, math.ceil(len(ordered) * 0.95) - 1)
        return round(ordered[index], 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples_ms": [round(item, 2) for item in self.samples_ms],
            "median_ms": self.median_ms,
            "p95_ms": self.p95_ms,
        }


def measure(operation: Callable[[], Any], *, runs: int = 5) -> TimingSeries:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return TimingSeries(tuple(samples))


def throughput(count: int, duration_seconds: float) -> float:
    return round(count / duration_seconds, 2) if duration_seconds > 0 else 0.0


def runtime_performance_report(**measurements: Any) -> dict[str, Any]:
    return {
        "measurements": measurements,
        "revision": RUNTIME_PERFORMANCE_REVISION,
        "boundary": (
            "Local synthetic runtime observations only; not a production "
            "throughput, latency, availability or scale claim."
        ),
    }


__all__ = [
    "TimingSeries",
    "measure",
    "runtime_performance_report",
    "throughput",
]
