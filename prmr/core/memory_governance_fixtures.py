"""Deterministic synthetic fixtures for Core Sprint 10."""

from __future__ import annotations

from .source_models import AuthenticatedScope, SourceInput


def governance_scope(label: str) -> AuthenticatedScope:
    return AuthenticatedScope(
        client_id=f"client_governance_{label}",
        vault_id=f"vault_governance_{label}",
        namespace="memory",
    )


def governed_source(
    label: str,
    *,
    actor: str,
    workspace: str,
    application: str = "app_governance_fixture",
    retention_policy: str = "standard",
    expires_at: str | None = None,
) -> SourceInput:
    return SourceInput(
        "json",
        {
            "event_type": "project.updated",
            "signal": f"Synthetic project {label} changed state.",
            "occurred_at": "2026-07-20T10:00:00Z",
            "previous_state": "queued",
            "current_state": "active",
        },
        occurred_at="2026-07-20T10:00:00Z",
        application_reference=application,
        actor_reference=actor,
        workspace_reference=workspace,
        entity_references=[f"entity_{label}"],
        retention_policy=retention_policy,
        expires_at=expires_at,
        idempotency_key=f"governance-source-{label}-v1",
    )


__all__ = ["governance_scope", "governed_source"]
