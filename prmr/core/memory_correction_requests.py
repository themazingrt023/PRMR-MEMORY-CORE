"""Correction requests routed through append-oriented authoritative operations."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .canonical_signal_registry import CanonicalSignalRegistry
from .entity_identity_service import EntityIdentityService
from .memory_governance_models import (
    GovernanceActor,
    MEMORY_CORRECTION_REQUEST_REVISION,
    MemoryCorrectionRequest,
    MemoryGovernanceError,
)
from .memory_governance_policy import sanitise_governance_text, validate_actor
from .memory_governance_store import MemoryGovernanceStore
from .memory_ledger_service import MemoryLedgerService
from .relationship_memory import RelationshipMemoryService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


CHANGE_TYPES = {
    "correct_candidate",
    "correct_admitted_memory",
    "supersede_admitted_memory",
    "retract_admitted_memory",
    "entity_alias_correction",
    "relationship_retraction",
    "relationship_supersession",
    "canonical_mapping_retraction",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryCorrectionRequestService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.admission = MemoryAdmissionService(repository, initialize=initialize)
        self.ledger = MemoryLedgerService(repository, initialize=initialize)
        self.relationships = RelationshipMemoryService(
            repository, initialize=initialize
        )
        self.entities = EntityIdentityService(repository, initialize=initialize)
        self.canonical = CanonicalSignalRegistry(repository, initialize=initialize)

    def create_request(
        self,
        scope: AuthenticatedScope,
        *,
        target_type: str,
        target_id: str,
        requested_change_type: str,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        requested_replacement_reference: str | None = None,
        requested_value: str | None = None,
        created_at: str | None = None,
    ) -> MemoryCorrectionRequest:
        actor = validate_actor(actor)
        if requested_change_type not in CHANGE_TYPES:
            raise MemoryGovernanceError(
                "GOVERNANCE_CORRECTION_ROUTE_INVALID",
                "Unsupported correction route.",
            )
        now = created_at or utc_now()
        target_digest = sha256_text(target_id)
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "target_type": target_type,
                    "target_digest": target_digest,
                    "change": requested_change_type,
                    "replacement": requested_replacement_reference,
                    "value_digest": (
                        sha256_text(requested_value) if requested_value else None
                    ),
                    "idempotency_key": idempotency_key,
                    "revision": MEMORY_CORRECTION_REQUEST_REVISION,
                }
            )
        )
        request_id = f"corrreq_{digest[:24]}"
        existing = self.store.get(
            "correction",
            "memory_correction_request_id",
            request_id,
            scope.memory_boundary(),
        )
        if existing:
            existing["scope"] = tuple(existing["scope"])
            return MemoryCorrectionRequest(**existing)
        request = MemoryCorrectionRequest(
            memory_correction_request_id=request_id,
            target_type=target_type,
            target_id=target_id,
            scope=scope.memory_boundary(),
            requested_change_type=requested_change_type,
            requested_replacement_reference=requested_replacement_reference,
            requested_value_digest=(
                sha256_text(requested_value) if requested_value else None
            ),
            correction_reason=sanitise_governance_text(reason),
            requested_by_actor_type=actor.actor_type,
            requested_by_actor_reference=actor.actor_reference,
            request_status="pending",
            routed_operation_type=None,
            routed_operation_id=None,
            memory_correction_request_revision=MEMORY_CORRECTION_REQUEST_REVISION,
            created_at=now,
            resolved_at=None,
        )
        self.store.insert(
            "correction",
            (
                "memory_correction_request_id",
                "client_id",
                "vault_id",
                "namespace",
                "target_type",
                "target_reference_digest",
                "request_status",
                "idempotency_digest",
                "created_at",
                "resolved_at",
            ),
            (
                request_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                target_type,
                target_digest,
                "pending",
                digest,
                now,
                None,
            ),
            request.to_dict(),
        )
        return request

    def route(
        self,
        scope: AuthenticatedScope,
        correction_request_id: str,
        *,
        idempotency_key: str,
        corrected_signal: str | None = None,
        corrected_event_type: str | None = None,
        resolved_at: str | None = None,
    ) -> MemoryCorrectionRequest:
        payload = self.store.get(
            "correction",
            "memory_correction_request_id",
            correction_request_id,
            scope.memory_boundary(),
        )
        if not payload:
            raise MemoryGovernanceError(
                "GOVERNANCE_SCOPE_DENIED",
                "Correction request was not found in scope.",
            )
        payload["scope"] = tuple(payload["scope"])
        request = MemoryCorrectionRequest(**payload)
        if request.request_status == "completed":
            return request
        actor = AdmissionDecisionActor(
            request.requested_by_actor_type,
            request.requested_by_actor_reference,
        )
        operation: Any
        route = request.requested_change_type
        if route == "correct_candidate":
            operation = self.admission.correct_candidate(
                scope,
                request.target_id,
                correction_reason=request.correction_reason,
                decision_actor=actor,
                idempotency_key=idempotency_key,
                corrected_signal=corrected_signal,
                corrected_event_type=corrected_event_type,
            ).admission
        elif route == "correct_admitted_memory":
            self._require_replacement(request)
            operation = self.ledger.correct_admitted_memory(
                scope,
                request.target_id,
                str(request.requested_replacement_reference),
                actor,
                request.correction_reason,
                idempotency_key=idempotency_key,
            )
        elif route == "supersede_admitted_memory":
            self._require_replacement(request)
            operation = self.ledger.supersede_admitted_memory(
                scope,
                request.target_id,
                str(request.requested_replacement_reference),
                actor,
                request.correction_reason,
                idempotency_key=idempotency_key,
            )
        elif route == "retract_admitted_memory":
            operation = self.ledger.retract_admitted_memory(
                scope,
                request.target_id,
                actor,
                request.correction_reason,
                idempotency_key=idempotency_key,
            )
        elif route == "relationship_retraction":
            operation = self.relationships.retract_relationship(
                scope,
                request.target_id,
                actor,
                request.correction_reason,
                idempotency_key=idempotency_key,
            )
        elif route == "relationship_supersession":
            self._require_replacement(request)
            operation = self.relationships.supersede_relationship(
                scope,
                request.target_id,
                str(request.requested_replacement_reference),
                actor,
                request.correction_reason,
                idempotency_key=idempotency_key,
            )
        elif route == "canonical_mapping_retraction":
            operation = self.canonical.retract_signal_mapping(
                scope,
                request.target_id,
                actor_type=request.requested_by_actor_type,
                actor_reference=request.requested_by_actor_reference,
                reason=request.correction_reason,
                idempotency_key=idempotency_key,
                valid_from=resolved_at or utc_now(),
                system_effective_at=resolved_at or utc_now(),
            )
        elif route == "entity_alias_correction":
            if not corrected_signal:
                raise MemoryGovernanceError(
                    "GOVERNANCE_CORRECTION_ROUTE_INVALID",
                    "Entity alias correction requires a replacement alias.",
                )
            prior = self.entities.get_alias(scope, request.target_id)
            self.entities.retract_alias(
                scope,
                request.target_id,
                actor,
                request.correction_reason,
                system_effective_at=resolved_at,
            )
            operation = self.entities.add_alias(
                scope,
                prior.entity_id,
                corrected_signal,
                prior.source_id,
                actor,
                request.correction_reason,
                segment_id=prior.segment_id,
                epistemic_status=prior.epistemic_status,
                valid_from=resolved_at,
                system_effective_at=resolved_at,
                idempotency_key=idempotency_key,
            )
        else:
            updated = replace(request, request_status="deferred")
            self.store.update_payload(
                "correction",
                "memory_correction_request_id",
                request.memory_correction_request_id,
                updated.to_dict(),
                {"request_status": "deferred"},
            )
            return updated
        operation_id = self._operation_id(operation)
        now = resolved_at or utc_now()
        updated = replace(
            request,
            request_status="completed",
            routed_operation_type=route,
            routed_operation_id=operation_id,
            resolved_at=now,
        )
        self.store.update_payload(
            "correction",
            "memory_correction_request_id",
            request.memory_correction_request_id,
            updated.to_dict(),
            {"request_status": "completed", "resolved_at": now},
        )
        return updated

    @staticmethod
    def _operation_id(value: Any) -> str:
        for name in (
            "admission_id",
            "memory_evolution_id",
            "relationship_evolution_id",
            "canonical_signal_decision_id",
            "alias_assertion_id",
        ):
            if hasattr(value, name):
                return str(getattr(value, name))
        return f"operation_{sha256_text(canonical_json(str(value)))[:24]}"

    @staticmethod
    def _require_replacement(request: MemoryCorrectionRequest) -> None:
        if not request.requested_replacement_reference:
            raise MemoryGovernanceError(
                "GOVERNANCE_CORRECTION_ROUTE_INVALID",
                "Correction route requires a replacement reference.",
            )


__all__ = ["MemoryCorrectionRequestService"]
