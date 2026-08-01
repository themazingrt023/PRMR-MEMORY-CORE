"""Explicit graceful shutdown coordination."""

from __future__ import annotations

from dataclasses import dataclass
import signal
import threading
import time
from typing import Any, Callable

from .runtime_context import RuntimeContext


@dataclass
class ShutdownCoordinator:
    context: RuntimeContext
    graceful_timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        self._stop = threading.Event()
        self._stoppers: list[Callable[[], Any]] = []

    def register_stopper(self, operation: Callable[[], Any]) -> None:
        self._stoppers.append(operation)

    def request_shutdown(self) -> None:
        self.context.shutting_down = True
        self.context.ready = False
        self._stop.set()

    def install_signal_handlers(self) -> None:
        def handler(_signum: int, _frame: Any) -> None:
            self.request_shutdown()

        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)

    def shutdown(self) -> dict[str, Any]:
        started = time.perf_counter()
        self.request_shutdown()
        failures: list[str] = []
        for stopper in reversed(self._stoppers):
            if time.perf_counter() - started >= self.graceful_timeout_seconds:
                failures.append("SHUTDOWN_TIMEOUT")
                break
            try:
                stopper()
            except Exception as exc:
                failures.append(str(getattr(exc, "code", type(exc).__name__.upper())))
            if time.perf_counter() - started >= self.graceful_timeout_seconds:
                failures.append("SHUTDOWN_TIMEOUT")
                break
        self.context.close()
        return {
            "status": "stopped" if not failures else "stopped_with_failures",
            "safe_failure_codes": failures,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "pool_closed": True,
            "timeout_reached": "SHUTDOWN_TIMEOUT" in failures,
        }


__all__ = ["ShutdownCoordinator"]
