"""Bitemporal retention annotations and frozen-boundary expiry discovery."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from .entity_store import placeholder, scope_params, table
from .memory_governance_models import (
    GovernanceActor,
    MEMORY_RETENTION_POLICY_REVISION,
    MemoryGovernanceError,
    MemoryRetentionAnnotation,
)
from .memory_governance_planner import MemoryGovernancePlanner
from .memory_governance_policy import (
    RETENTION_MODES,
    sanitise_governance_text,
    validate_actor,
)
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryRetentionService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.p = placeholder(repository)
        self.planner = MemoryGovernancePlanner(repository, initialize=False)

    def annotate(
        self,
        scope: AuthenticatedScope,
        *,
        target_type: str,
        target_reference: str,
        retention_mode: str,
        retain_until: str | None,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        system_effective_at: str | None = None,
    ) -> MemoryRetentionAnnotation:
        actor = validate_actor(actor)
        if retention_mode not in RETENTION_MODES:
            raise MemoryGovernanceError(
                "GOVERNANCE_RETENTION_POLICY_INVALID", "Unsupported retention mode."
            )
        if retention_mode == "retain_until" and not retain_until:
            raise MemoryGovernanceError(
                "GOVERNANCE_RETENTION_POLICY_INVALID",
                "retain_until requires a trusted timestamp.",
            )
        now = system_effective_at or utc_now()
        target_digest = sha256_text(target_reference)
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "target_type": target_type,
                    "target_digest": target_digest,
                    "mode": retention_mode,
                    "retain_until": retain_until,
                    "idempotency_key": idempotency_key,
                    "revision": MEMORY_RETENTION_POLICY_REVISION,
                }
            )
        )
        annotation_id = f"mret_{digest[:24]}"
        existing = self.store.get(
            "retention",
            "retention_annotation_id",
            annotation_id,
            scope.memory_boundary(),
        )
        if existing:
            existing["scope"] = tuple(existing["scope"])
            return MemoryRetentionAnnotation(**existing)
        annotation = MemoryRetentionAnnotation(
            retention_annotation_id=annotation_id,
            target_type=target_type,
            target_reference_digest=target_digest,
            scope=scope.memory_boundary(),
            retention_mode=retention_mode,
            retain_until=retain_until,
            annotation_actor_type=actor.actor_type,
            annotation_actor_reference=actor.actor_reference,
            annotation_reason=sanitise_governance_text(reason),
            system_effective_at=now,
            idempotency_digest=digest,
            memory_retention_policy_revision=MEMORY_RETENTION_POLICY_REVISION,
            created_at=now,
        )
        self.store.insert(
            "retention",
            (
                "retention_annotation_id",
                "client_id",
                "vault_id",
                "namespace",
                "target_type",
                "target_reference_digest",
                "retention_mode",
                "retain_until",
                "system_effective_at",
                "idempotency_digest",
                "created_at",
            ),
            (
                annotation_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                target_type,
                target_digest,
                retention_mode,
                retain_until,
                now,
                digest,
                now,
            ),
            annotation.to_dict(),
        )
        return annotation

    def effective_annotation(
        self,
        scope: AuthenticatedScope,
        target_reference: str,
        *,
        known_at: str,
    ) -> MemoryRetentionAnnotation | None:
        digest = sha256_text(target_reference)
        rows = self.store.manifest_rows("retention", scope.memory_boundary())
        eligible = [
            item
            for item in rows
            if item["target_reference_digest"] == digest
            and item["system_effective_at"] <= known_at
        ]
        if not eligible:
            return None
        payload = sorted(
            eligible,
            key=lambda item: (
                item["system_effective_at"],
                item["retention_annotation_id"],
            ),
        )[-1]
        payload["scope"] = tuple(payload["scope"])
        return MemoryRetentionAnnotation(**payload)

    def expired_sources(
        self, scope: AuthenticatedScope, *, frozen_now: str
    ) -> list[str]:
        source_table = table(self.repository, "prmr_sources")
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT source_id,retention_policy,expires_at FROM {source_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                scope_params(scope),
            ).fetchall()
        expired: list[str] = []
        for row in rows:
            source_id = str(row["source_id"])
            annotation = self.effective_annotation(
                scope, source_id, known_at=frozen_now
            )
            mode = (
                annotation.retention_mode
                if annotation
                else str(row["retention_policy"])
            )
            boundary = (
                annotation.retain_until if annotation else row["expires_at"]
            )
            if mode in {"ephemeral", "retain_until"} and boundary and str(boundary) <= frozen_now:
                expired.append(source_id)
        return sorted(expired)

    def expire_export_artifacts(
        self, scope: AuthenticatedScope, *, frozen_now: str
    ) -> int:
        bundle_table = self.store.tables["export_bundle"]
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT memory_export_bundle_id FROM {bundle_table} WHERE "
                f"client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND expires_at IS NOT NULL AND expires_at<={self.p}",
                (*scope_params(scope), frozen_now),
            ).fetchall()
            for row in rows:
                connection.execute(
                    f"DELETE FROM {bundle_table} WHERE memory_export_bundle_id={self.p}",
                    (row["memory_export_bundle_id"],),
                )
        LOGGER.info(
            "memory_export_expired",
            extra={"object_count": len(rows), "status": "completed"},
        )
        return len(rows)

    def plan_expired_memory_purge(
        self,
        scope: AuthenticatedScope,
        *,
        actor: GovernanceActor,
        frozen_now: str,
        idempotency_key: str,
    ) -> list[Any]:
        plans = []
        for source_id in self.expired_sources(scope, frozen_now=frozen_now):
            request = self.planner.create_request(
                scope,
                action_type="expire",
                target_type="source",
                target_reference=source_id,
                actor=actor,
                reason="Frozen-boundary retention expiry.",
                idempotency_key=f"{idempotency_key}:{source_id}",
                governance_policy_id="retention_expiry_v1",
                requested_at=frozen_now,
            )
            plans.append(
                self.planner.plan(
                    scope,
                    request.governance_request_id,
                    generated_at=frozen_now,
                )
            )
        return plans


__all__ = ["MemoryRetentionService"]
