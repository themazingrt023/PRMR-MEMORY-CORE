"""Structured operational logging with bounded redaction."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from .version import __version__


_SECRET_PATTERNS = (
    re.compile(r"postgres(?:ql)?(?:\+[^:]+)?://[^\s]+", re.I),
    re.compile(r"(?:prmr_(?:live|alpha)_|sk-|ghp_|github_pat_)[A-Za-z0-9_.-]{6,}", re.I),
    re.compile(r"Authorization:\s*Bearer\s+[^\s]+", re.I),
    re.compile(r"(?:password|token|api[_-]?key|secret)\s*[=:]\s*[^\s,;]+", re.I),
)


def redact_operational_text(value: Any) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text[:1000]


def operational_log_event(
    event_name: str,
    *,
    level: str = "INFO",
    component: str,
    operation_id: str,
    status: str,
    duration_ms: float | None = None,
    scope_fingerprint: str | None = None,
    safe_error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": level.upper(),
        "event_name": redact_operational_text(event_name),
        "release_version": __version__,
        "component": redact_operational_text(component),
        "safe_operation_id": redact_operational_text(operation_id),
        "scope_fingerprint": scope_fingerprint,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
        "status": redact_operational_text(status),
        "safe_error_code": redact_operational_text(safe_error_code) if safe_error_code else None,
    }


def render_log(event: dict[str, Any], *, format_name: str) -> str:
    if format_name == "json":
        return json.dumps(event, sort_keys=True, separators=(",", ":"))
    return " ".join(
        f"{key}={value}" for key, value in event.items() if value is not None
    )


__all__ = ["operational_log_event", "redact_operational_text", "render_log"]
