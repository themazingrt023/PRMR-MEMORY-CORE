"""Versioned safe runtime integrity sweep orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .runtime_models import RUNTIME_INTEGRITY_SWEEP_REVISION


@dataclass(frozen=True)
class IntegrityCheckAdapter:
    category: str
    operation: Callable[[], Any]


class RuntimeIntegritySweep:
    CATEGORIES = (
        "source",
        "candidate",
        "admission",
        "ledger",
        "temporal_dynamics",
        "entity",
        "relationship",
        "query",
        "consolidation",
        "interpretation",
        "canonical_signal",
        "governance",
        "job",
    )

    def __init__(self, checks: list[IntegrityCheckAdapter] | None = None) -> None:
        self.checks = {item.category: item.operation for item in checks or []}

    def run(self, *, mode: str = "sampled") -> dict[str, Any]:
        if mode not in {"sampled", "full_scope"}:
            raise ValueError("Integrity sweep mode must be sampled or full_scope.")
        results: list[dict[str, Any]] = []
        for category in self.CATEGORIES:
            operation = self.checks.get(category)
            if operation is None:
                results.append(
                    {
                        "category": category,
                        "status": "not_configured",
                        "checked_count": 0,
                    }
                )
                continue
            try:
                value = operation()
                verified = (
                    bool(value.get("verified"))
                    if isinstance(value, dict) and "verified" in value
                    else bool(value)
                )
                results.append(
                    {
                        "category": category,
                        "status": "verified" if verified else "failed",
                        "checked_count": int(
                            value.get("checked_count", 1)
                            if isinstance(value, dict)
                            else 1
                        ),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "category": category,
                        "status": "failed",
                        "checked_count": 0,
                        "safe_error_code": getattr(
                            exc, "code", type(exc).__name__.upper()
                        ),
                    }
                )
        configured = [item for item in results if item["status"] != "not_configured"]
        return {
            "mode": mode,
            "verified": bool(configured)
            and all(item["status"] == "verified" for item in configured),
            "configured_categories": len(configured),
            "results": results,
            "revision": RUNTIME_INTEGRITY_SWEEP_REVISION,
        }


__all__ = ["IntegrityCheckAdapter", "RuntimeIntegritySweep"]
