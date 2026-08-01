"""Exact query acceleration over integrity-bound immutable checkpoints."""

from __future__ import annotations

from dataclasses import replace
import logging
import time
from typing import Any

from .memory_consolidation_engine import (
    SUPPORTED_ACCELERATED_QUERY_TYPES,
    consolidation_query_key,
)
from .memory_consolidation_membership import fast_authoritative_manifest
from .memory_consolidation_models import (
    MEMORY_CONSOLIDATION_COMPARISON_REVISION,
    MemoryAcceleratedQueryResult,
    MemoryAccelerationMetadata,
    MemoryCheckpointStatus,
    MemoryConsolidationEquivalenceProof,
    MemoryConsolidationStatus,
)
from .memory_consolidation_planner import utc
from .memory_consolidation_store import MemoryConsolidationStore
from .memory_query_engine import MemoryQueryEngine
from .memory_query_models import MemoryQueryRequest
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_consolidation.query_adapter")


class MemoryConsolidationQueryAdapter:
    """Return the exact canonical result artifact only when its checkpoint is valid."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryConsolidationStore(repository, initialize=initialize)
        self.canonical = MemoryQueryEngine(repository, initialize=initialize)

    def query_memory(
        self,
        scope: AuthenticatedScope,
        request: MemoryQueryRequest,
    ) -> MemoryAcceleratedQueryResult:
        started = time.perf_counter()
        if request.query_type not in SUPPORTED_ACCELERATED_QUERY_TYPES:
            return self._fallback(
                scope, request, started, "unsupported_query_type"
            )
        checkpoint, normalised, snapshot = self._select_checkpoint(scope, request)
        if checkpoint is None or snapshot is None or normalised is None:
            return self._fallback(
                scope, request, started, "compatible_checkpoint_not_found"
            )
        manifest = fast_authoritative_manifest(
            self.repository, scope
        )["authoritative_manifest_hash"]
        if manifest != checkpoint.authoritative_event_manifest_hash:
            self._mark_stale(scope, checkpoint)
            return self._fallback(
                scope, request, started, "authoritative_manifest_changed"
            )
        try:
            result = self.canonical.get_query_result(
                scope, snapshot["query_result_id"]
            )
        except Exception:
            return self._fallback(
                scope, request, started, "canonical_result_artifact_missing"
            )
        accelerated_hash = result.result_hash_sha256
        equivalent = (
            accelerated_hash == snapshot["result_hash_sha256"]
            and result.result_manifest_hash_sha256
            == snapshot["result_manifest_hash_sha256"]
            and result.evidence_bundle_id == snapshot["evidence_bundle_id"]
            and result.explanation_id == snapshot["explanation_id"]
        )
        if not equivalent:
            self._record_proof(
                scope,
                checkpoint,
                snapshot,
                accelerated_hash,
                False,
                ["canonical_artifact_binding"],
                round((time.perf_counter() - started) * 1000, 3),
            )
            return self._fallback(
                scope, request, started, "equivalence_verification_failed"
            )
        duration = round((time.perf_counter() - started) * 1000, 3)
        self._record_proof(
            scope, checkpoint, snapshot, accelerated_hash, True, [], duration
        )
        LOGGER.info(
            "memory_query_accelerated checkpoint_id=%s query_type=%s duration_ms=%s",
            checkpoint.memory_checkpoint_id,
            request.query_type,
            duration,
        )
        return MemoryAcceleratedQueryResult(
            result=replace(result, replayed=True),
            metadata=MemoryAccelerationMetadata(
                execution_path="consolidated_checkpoint",
                checkpoint_id=checkpoint.memory_checkpoint_id,
                consolidation_run_id=checkpoint.consolidation_run_id,
                acceleration_supported=True,
                acceleration_used=True,
                fallback_used=False,
                fallback_reason=None,
                canonical_verification_performed=True,
                canonical_result_hash=snapshot["result_hash_sha256"],
                accelerated_result_hash=accelerated_hash,
                equivalence_verified=True,
                checkpoint_age=0,
                delta_event_count=0,
                acceleration_duration_ms=duration,
                canonical_comparison_duration_ms=None,
            ),
        )

    def _select_checkpoint(
        self, scope: AuthenticatedScope, request: MemoryQueryRequest
    ) -> tuple[Any, MemoryQueryRequest | None, dict[str, Any] | None]:
        for checkpoint in self.store.list_checkpoints(
            scope, statuses=(MemoryCheckpointStatus.CURRENT.value,)
        ):
            if (
                request.valid_at
                and request.valid_at != checkpoint.valid_at
                or request.known_at
                and request.known_at != checkpoint.known_at
            ):
                continue
            if not self._subject_compatible(checkpoint, request):
                continue
            normalised = replace(
                request,
                client_id=None,
                vault_id=None,
                namespace=None,
                application_reference=(
                    request.application_reference
                    or checkpoint.application_reference
                ),
                actor_reference=request.actor_reference or checkpoint.actor_reference,
                workspace_reference=(
                    request.workspace_reference or checkpoint.workspace_reference
                ),
                entity_id=request.entity_id or checkpoint.entity_id,
                relationship_id=(
                    request.relationship_id or checkpoint.relationship_id
                ),
                session_reference=(
                    request.session_reference or checkpoint.session_reference
                ),
                valid_at=checkpoint.valid_at,
                known_at=checkpoint.known_at,
            )
            snapshot = checkpoint.deterministic_state_payload.get(
                "query_snapshots", {}
            ).get(consolidation_query_key(normalised))
            if snapshot:
                return checkpoint, normalised, snapshot
        return None, None, None

    def _fallback(
        self,
        scope: AuthenticatedScope,
        request: MemoryQueryRequest,
        started: float,
        reason: str,
    ) -> MemoryAcceleratedQueryResult:
        canonical_started = time.perf_counter()
        result = self.canonical.query_memory(scope, request)
        canonical_duration = round(
            (time.perf_counter() - canonical_started) * 1000, 3
        )
        total = round((time.perf_counter() - started) * 1000, 3)
        LOGGER.info(
            "memory_query_acceleration_fallback query_type=%s reason=%s duration_ms=%s",
            request.query_type,
            reason,
            total,
        )
        return MemoryAcceleratedQueryResult(
            result=result,
            metadata=MemoryAccelerationMetadata(
                execution_path="consolidated_fallback_to_authoritative",
                checkpoint_id=None,
                consolidation_run_id=None,
                acceleration_supported=(
                    request.query_type in SUPPORTED_ACCELERATED_QUERY_TYPES
                ),
                acceleration_used=False,
                fallback_used=True,
                fallback_reason=reason,
                canonical_verification_performed=False,
                canonical_result_hash=result.result_hash_sha256,
                accelerated_result_hash=None,
                equivalence_verified=False,
                checkpoint_age=None,
                delta_event_count=0,
                acceleration_duration_ms=total,
                canonical_comparison_duration_ms=canonical_duration,
            ),
        )

    def _record_proof(
        self,
        scope: AuthenticatedScope,
        checkpoint: Any,
        snapshot: dict[str, Any],
        accelerated_hash: str,
        equivalent: bool,
        mismatches: list[str],
        accelerated_duration: float,
    ) -> None:
        material = {
            "run_id": checkpoint.consolidation_run_id,
            "checkpoint_id": checkpoint.memory_checkpoint_id,
            "query_type": snapshot["query_type"],
            "canonical_result_id": snapshot["query_result_id"],
            "canonical_hash": snapshot["result_hash_sha256"],
            "accelerated_hash": accelerated_hash,
            "equivalent": equivalent,
            "mismatches": mismatches,
            "proof_revision": MEMORY_CONSOLIDATION_COMPARISON_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        canonical_duration = snapshot.get("canonical_duration_ms")
        speedup = (
            round(float(canonical_duration) / accelerated_duration, 3)
            if canonical_duration and accelerated_duration > 0
            else None
        )
        proof = MemoryConsolidationEquivalenceProof(
            equivalence_proof_id=f"meq_{digest[:24]}",
            consolidation_run_id=checkpoint.consolidation_run_id,
            checkpoint_id=checkpoint.memory_checkpoint_id,
            proof_type="query_result",
            query_type=snapshot["query_type"],
            canonical_result_id=snapshot["query_result_id"],
            accelerated_result_id=snapshot["query_result_id"],
            canonical_result_hash=snapshot["result_hash_sha256"],
            accelerated_result_hash=accelerated_hash,
            canonical_packet_id=None,
            accelerated_packet_id=None,
            canonical_packet_hash=None,
            accelerated_packet_hash=None,
            equivalent=equivalent,
            mismatch_fields=mismatches,
            canonical_duration_ms=canonical_duration,
            accelerated_duration_ms=accelerated_duration,
            speedup_ratio=speedup,
            proof_revision=MEMORY_CONSOLIDATION_COMPARISON_REVISION,
            created_at=utc(None),
        )
        self.store.put_proof(scope, proof)

    def _mark_stale(self, scope: AuthenticatedScope, checkpoint: Any) -> None:
        self.store.put_checkpoint(
            replace(
                checkpoint,
                checkpoint_status=MemoryCheckpointStatus.STALE.value,
            )
        )
        run = self.store.get_run(scope, checkpoint.consolidation_run_id)
        if run:
            self.store.put_run(
                replace(
                    run,
                    status=MemoryConsolidationStatus.STALE.value,
                    updated_at=utc(None),
                )
            )
        LOGGER.info(
            "memory_consolidation_marked_stale checkpoint_id=%s",
            checkpoint.memory_checkpoint_id,
        )

    @staticmethod
    def _subject_compatible(checkpoint: Any, request: MemoryQueryRequest) -> bool:
        return all(
            requested in (None, stored)
            for requested, stored in (
                (request.application_reference, checkpoint.application_reference),
                (request.actor_reference, checkpoint.actor_reference),
                (request.workspace_reference, checkpoint.workspace_reference),
                (request.entity_id, checkpoint.entity_id),
                (request.relationship_id, checkpoint.relationship_id),
                (request.session_reference, checkpoint.session_reference),
            )
        )


__all__ = ["MemoryConsolidationQueryAdapter"]
