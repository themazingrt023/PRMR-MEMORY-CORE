"""Deterministic synthetic fixtures for Core Sprint 8 consolidation proofs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from .source_models import AuthenticatedScope


def consolidation_fixture_scope(name: str) -> AuthenticatedScope:
    return AuthenticatedScope(
        f"client_consolidation_{name}",
        f"vault_consolidation_{name}",
        "default",
        application_reference=f"app_consolidation_{name}",
        actor_reference=f"actor_consolidation_{name}",
        workspace_reference=f"workspace_consolidation_{name}",
        session_reference=f"session_consolidation_{name}",
    )


def synthetic_consolidation_events(
    count: int,
    *,
    prefix: str,
    start_index: int = 0,
    start_at: str = "2025-01-01T00:00:00Z",
    signal_count: int = 17,
) -> list[dict[str, Any]]:
    base = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return [
        {
            "event_id": f"evt_{prefix}_{index:05d}",
            "user_id": "synthetic_memory_subject",
            "type": f"memory.signal_{index % signal_count}",
            "content": f"Synthetic consolidation event {index}.",
            "timestamp": (
                base + timedelta(minutes=index)
            ).isoformat().replace("+00:00", "Z"),
            "timestamp_index": index,
            "synthetic": True,
            "application_reference": "",
            "actor_reference": "",
            "workspace_reference": "",
            "entity_reference": "",
            "session_reference": "",
            "external_metadata": {
                "metadata": {
                    "synthetic": True,
                    "epistemic_status": (
                        "explicit"
                        if index % 7
                        else "inferred"
                        if index % 11
                        else "unknown"
                    ),
                }
            },
        }
        for index in range(start_index, start_index + count)
    ]


def write_fixture_events(
    repository: Any,
    scope: AuthenticatedScope,
    events: list[dict[str, Any]],
    *,
    append: bool = False,
) -> None:
    scope_key = "::".join(scope.memory_boundary())
    scoped_events = [
        {
            **event,
            "application_reference": scope.application_reference or "",
            "actor_reference": scope.actor_reference or "",
            "workspace_reference": scope.workspace_reference or "",
            "entity_reference": scope.entity_reference or "",
            "session_reference": scope.session_reference or "",
        }
        for event in events
    ]
    with repository.connect() as connection:
        existing: list[dict[str, Any]] = []
        if append:
            row = connection.execute(
                "SELECT payload_json FROM events WHERE scope_key=?",
                (scope_key,),
            ).fetchone()
            if row:
                existing = json.loads(row["payload_json"])
        payload = existing + scoped_events
        connection.execute(
            "INSERT INTO events(scope_key,payload_json) VALUES(?,?) "
            "ON CONFLICT(scope_key) DO UPDATE SET payload_json=excluded.payload_json",
            (scope_key, json.dumps(payload, sort_keys=True)),
        )


def exact_signal_fixture() -> list[dict[str, Any]]:
    events = synthetic_consolidation_events(
        12, prefix="exact_signal", signal_count=3
    )
    # Re-emergence-friendly gap while preserving deterministic event order.
    events[-1]["timestamp"] = "2025-12-01T00:00:00Z"
    return events


__all__ = [
    "consolidation_fixture_scope",
    "exact_signal_fixture",
    "synthetic_consolidation_events",
    "write_fixture_events",
]
