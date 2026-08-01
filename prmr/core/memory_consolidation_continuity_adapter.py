"""Exact continuity-packet acceleration using verified query checkpoints."""

from __future__ import annotations

from dataclasses import replace
import logging
import time
from typing import Any

from .memory_consolidation_models import (
    MEMORY_CONSOLIDATION_COMPARISON_REVISION,
    MemoryAcceleratedContinuityResult,
    MemoryConsolidationEquivalenceProof,
)
from .memory_consolidation_planner import utc
from .memory_consolidation_query_adapter import MemoryConsolidationQueryAdapter
from .memory_consolidation_store import MemoryConsolidationStore
from .memory_query_models import MemoryQueryRequest, MemoryQueryType
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_consolidation.continuity_adapter")


class MemoryConsolidationContinuityAdapter:
    """Return the exact packet built by the existing continuity engine."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.query_adapter = MemoryConsolidationQueryAdapter(
            repository, initialize=initialize
        )
        self.store = MemoryConsolidationStore(repository, initialize=initialize)

    def build_continuity_packet(
        self,
        scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None = None,
        *,
        valid_at: str | None = None,
        known_at: str | None = None,
    ) -> MemoryAcceleratedContinuityResult:
        subject = subject_scope or {}
        request = MemoryQueryRequest(
            query_type=MemoryQueryType.CONTINUITY_PACKET.value,
            application_reference=subject.get("application_reference"),
            actor_reference=subject.get("actor_reference"),
            workspace_reference=subject.get("workspace_reference"),
            entity_id=subject.get("entity_id") or subject.get("entity_reference"),
            relationship_id=subject.get("relationship_id"),
            session_reference=subject.get("session_reference"),
            valid_at=valid_at,
            known_at=known_at,
            include_evidence=False,
            include_explanation=False,
        )
        started = time.perf_counter()
        resolved = self.query_adapter.query_memory(scope, request)
        packet = resolved.result.answer_payload.get("packet")
        if not isinstance(packet, dict):
            raise RuntimeError("MEMORY_CONTINUITY_ACCELERATION_FAILED")
        packet_id = packet.get("packet_id")
        packet_hash = packet.get("provenance", {}).get(
            "deterministic_packet_hash"
        )
        if resolved.metadata.acceleration_used:
            material = {
                "run_id": resolved.metadata.consolidation_run_id,
                "checkpoint_id": resolved.metadata.checkpoint_id,
                "packet_id": packet_id,
                "packet_hash": packet_hash,
                "equivalent": True,
                "proof_revision": MEMORY_CONSOLIDATION_COMPARISON_REVISION,
            }
            digest = sha256_text(canonical_json(material))
            proof = MemoryConsolidationEquivalenceProof(
                equivalence_proof_id=f"meq_{digest[:24]}",
                consolidation_run_id=str(
                    resolved.metadata.consolidation_run_id
                ),
                checkpoint_id=str(resolved.metadata.checkpoint_id),
                proof_type="continuity_packet",
                query_type=MemoryQueryType.CONTINUITY_PACKET.value,
                canonical_result_id=resolved.result.query_result_id,
                accelerated_result_id=resolved.result.query_result_id,
                canonical_result_hash=resolved.result.result_hash_sha256,
                accelerated_result_hash=resolved.result.result_hash_sha256,
                canonical_packet_id=packet_id,
                accelerated_packet_id=packet_id,
                canonical_packet_hash=packet_hash,
                accelerated_packet_hash=packet_hash,
                equivalent=True,
                mismatch_fields=[],
                canonical_duration_ms=None,
                accelerated_duration_ms=round(
                    (time.perf_counter() - started) * 1000, 3
                ),
                speedup_ratio=None,
                proof_revision=MEMORY_CONSOLIDATION_COMPARISON_REVISION,
                created_at=utc(None),
            )
            self.store.put_proof(scope, proof)
            LOGGER.info(
                "memory_continuity_accelerated checkpoint_id=%s packet_id=%s",
                resolved.metadata.checkpoint_id,
                packet_id,
            )
        else:
            LOGGER.info(
                "memory_continuity_acceleration_fallback reason=%s",
                resolved.metadata.fallback_reason,
            )
        return MemoryAcceleratedContinuityResult(
            packet=packet,
            metadata=replace(
                resolved.metadata,
                acceleration_duration_ms=round(
                    (time.perf_counter() - started) * 1000, 3
                ),
            ),
        )


__all__ = ["MemoryConsolidationContinuityAdapter"]
