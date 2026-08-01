"""Append-oriented preservation holds that block destructive governance."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import logging
from typing import Any

from .memory_governance_models import (
    GovernanceActor,
    MEMORY_PRESERVATION_HOLD_REVISION,
    MemoryGovernanceError,
    MemoryPreservationHold,
)
from .memory_governance_policy import sanitise_governance_text, validate_actor
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryPreservationHoldService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.store = MemoryGovernanceStore(repository, initialize=initialize)

    def apply_hold(
        self,
        scope: AuthenticatedScope,
        *,
        target_type: str,
        target_reference: str,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        applied_at: str | None = None,
    ) -> MemoryPreservationHold:
        actor = validate_actor(actor)
        now = applied_at or utc_now()
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "target_type": target_type,
                    "target_digest": sha256_text(target_reference),
                    "idempotency_key": idempotency_key,
                    "revision": MEMORY_PRESERVATION_HOLD_REVISION,
                }
            )
        )
        hold_id = f"mhold_{digest[:24]}"
        existing = self.store.get(
            "hold", "preservation_hold_id", hold_id, scope.memory_boundary()
        )
        if existing:
            return MemoryPreservationHold(**existing)
        hold = MemoryPreservationHold(
            preservation_hold_id=hold_id,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            target_type=target_type,
            target_reference_digest=sha256_text(target_reference),
            application_reference=scope.application_reference,
            actor_reference=scope.actor_reference,
            workspace_reference=scope.workspace_reference,
            entity_id=scope.entity_reference,
            session_reference=scope.session_reference,
            hold_status="active",
            hold_reason=sanitise_governance_text(reason),
            applied_by_actor_type=actor.actor_type,
            applied_by_actor_reference=actor.actor_reference,
            applied_at=now,
            release_at=None,
            released_by_actor_reference=None,
            released_reason=None,
            hold_idempotency_digest=digest,
            memory_preservation_hold_revision=MEMORY_PRESERVATION_HOLD_REVISION,
            created_at=now,
            updated_at=now,
        )
        self.store.insert(
            "hold",
            (
                "preservation_hold_id",
                "client_id",
                "vault_id",
                "namespace",
                "target_type",
                "target_reference_digest",
                "hold_status",
                "hold_idempotency_digest",
                "applied_at",
                "updated_at",
            ),
            (
                hold_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                target_type,
                hold.target_reference_digest,
                "active",
                digest,
                now,
                now,
            ),
            hold.to_dict(),
        )
        LOGGER.info(
            "memory_preservation_hold_applied",
            extra={"preservation_hold_id": hold_id, "target_type": target_type},
        )
        return hold

    def release_hold(
        self,
        scope: AuthenticatedScope,
        preservation_hold_id: str,
        *,
        actor: GovernanceActor,
        reason: str,
        released_at: str | None = None,
    ) -> MemoryPreservationHold:
        actor = validate_actor(actor)
        payload = self.store.get(
            "hold",
            "preservation_hold_id",
            preservation_hold_id,
            scope.memory_boundary(),
        )
        if not payload:
            raise MemoryGovernanceError(
                "GOVERNANCE_SCOPE_DENIED", "Preservation hold was not found in scope."
            )
        hold = MemoryPreservationHold(**payload)
        if hold.hold_status == "released":
            return hold
        now = released_at or utc_now()
        updated = replace(
            hold,
            hold_status="released",
            release_at=now,
            released_by_actor_reference=actor.actor_reference,
            released_reason=sanitise_governance_text(reason),
            updated_at=now,
        )
        self.store.update_payload(
            "hold",
            "preservation_hold_id",
            preservation_hold_id,
            updated.to_dict(),
            {"hold_status": "released", "updated_at": now},
        )
        LOGGER.info(
            "memory_preservation_hold_released",
            extra={"preservation_hold_id": preservation_hold_id},
        )
        return updated


__all__ = ["MemoryPreservationHoldService"]
