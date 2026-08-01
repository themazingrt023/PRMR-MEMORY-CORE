"""Post-erasure verification that refuses completion on residual governed data."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from .memory_dependency_graph import (
    MemoryDependencyGraph,
    SUBJECT_FIELDS,
    _reference_strings,
    _strings,
)
from .memory_governance_models import (
    MEMORY_GOVERNANCE_VERIFICATION_REVISION,
    MemoryGovernanceExecution,
    MemoryGovernanceRequest,
    MemoryGovernanceVerification,
)
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryGovernanceVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.graphs = MemoryDependencyGraph(repository, initialize=False)

    def verify_erasure(
        self,
        scope: AuthenticatedScope,
        request: MemoryGovernanceRequest,
        execution: MemoryGovernanceExecution,
        *,
        erased_storage_keys: tuple[str, ...],
        shared_recomputed: bool,
        verified_at: str | None = None,
    ) -> MemoryGovernanceVerification:
        now = verified_at or utc_now()
        records = self.graphs._scope_records(scope)
        residual_by_type: dict[str, int] = {}
        for node, payload, _ in records:
            residual = False
            if request.target_type == "tenant_memory_boundary":
                residual = True
            elif request.target_type in SUBJECT_FIELDS:
                residual = request.opaque_target_reference in _strings(payload)
            else:
                residual = (
                    node.storage_key == request.opaque_target_reference
                    or request.opaque_target_reference
                    in _reference_strings(payload)
                    or node.storage_key in erased_storage_keys
                )
            if residual:
                residual_by_type[node.node_type] = (
                    residual_by_type.get(node.node_type, 0) + 1
                )
        target_absent = not residual_by_type
        cache_types = {
            "query_run",
            "query_result",
            "evidence_bundle",
            "evidence_item",
            "explanation",
            "checkpoint",
            "checkpoint_delta",
            "consolidated_memory",
            "consolidation_member",
            "interpretation_request",
            "interpretation_attempt",
            "interpretation_response",
            "event_signal_projection",
            "canonical_signal_artifact",
            "packet",
            "report",
        }
        cache_residual = {
            key: count for key, count in residual_by_type.items() if key in cache_types
        }
        checks = {
            "target_absent": target_absent,
            "governed_dependencies_absent_or_valid": not residual_by_type,
            "indexes_cleared": not cache_residual,
            "scope_parameterised": True,
            "tombstone_content_not_used_for_verification": True,
        }
        status = "verified" if all(checks.values()) else "failed"
        material = {
            "execution": execution.governance_execution_id,
            "status": status,
            "checks": checks,
            "remaining": residual_by_type,
            "revision": MEMORY_GOVERNANCE_VERIFICATION_REVISION,
        }
        manifest = sha256_text(canonical_json(material))
        verification = MemoryGovernanceVerification(
            governance_verification_id=f"govver_{manifest[:24]}",
            governance_execution_id=execution.governance_execution_id,
            verification_status=status,
            target_absent=target_absent,
            governed_dependencies_absent_or_valid=not residual_by_type,
            shared_dependencies_recomputed=shared_recomputed,
            indexes_cleared=not cache_residual,
            checkpoints_invalidated=not any(
                key in residual_by_type for key in ("checkpoint", "checkpoint_delta")
            ),
            queries_invalidated=not any(
                key in residual_by_type
                for key in ("query_run", "query_result", "evidence_bundle", "explanation")
            ),
            exports_invalidated=not any(
                key in residual_by_type for key in ("export_bundle", "export_request")
            ),
            no_cross_scope_change=True,
            integrity_checks=checks,
            remaining_reference_counts=dict(sorted(residual_by_type.items())),
            verification_manifest_hash=manifest,
            memory_governance_verification_revision=MEMORY_GOVERNANCE_VERIFICATION_REVISION,
            verified_at=now,
            created_at=now,
        )
        existing = self.store.get(
            "verification",
            "governance_verification_id",
            verification.governance_verification_id,
            scope.memory_boundary(),
        )
        if not existing:
            self.store.insert(
                "verification",
                (
                    "governance_verification_id",
                    "governance_execution_id",
                    "client_id",
                    "vault_id",
                    "namespace",
                    "verification_status",
                    "verification_manifest_hash",
                    "created_at",
                ),
                (
                    verification.governance_verification_id,
                    execution.governance_execution_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    status,
                    manifest,
                    now,
                ),
                verification.to_dict(),
            )
        LOGGER.info(
            "memory_erasure_verified"
            if status == "verified"
            else "memory_erasure_verification_failed",
            extra={
                "governance_execution_id": execution.governance_execution_id,
                "status": status,
                "object_count": sum(residual_by_type.values()),
            },
        )
        return verification

    def erased_evidence_status(
        self,
        scope: AuthenticatedScope,
        target_reference: str,
    ) -> dict[str, Any]:
        digest = sha256_text(target_reference)
        tombstones = self.store.manifest_rows(
            "tombstone", scope.memory_boundary()
        )
        match = next(
            (
                item
                for item in tombstones
                if item["target_reference_digest"] == digest
                and item["tombstone_status"] == "verified"
            ),
            None,
        )
        return {
            "status": (
                "evidence_unavailable_due_to_governance_erasure"
                if match
                else "no_data"
            ),
            "erasure_tombstone_id": (
                match["erasure_tombstone_id"] if match else None
            ),
            "content_recoverable": False,
        }


__all__ = ["MemoryGovernanceVerifier"]
