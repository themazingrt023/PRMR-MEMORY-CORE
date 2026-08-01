"""Deterministic bridge from admitted candidates to the existing event shape."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from prmr.product.controlled_alpha_api_v071 import (
    ALGORITHM_REVISION,
    PACKET_VERSION,
    PRMRControlledAlphaAPI,
)

from .admission_models import (
    ADMISSION_BRIDGE_REVISION,
    ADMISSION_POLICY_REVISION,
    ADMITTED_EVENT_METADATA_REVISION,
    MemoryAdmissionError,
)
from .candidate_models import CandidateEvidence, CandidateMemory, EVENT_TYPE_PATTERN
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope, SourceRecord, SourceSegment


class CandidateToEventBridge:
    """Build canonical events without making an HTTP/API-key request."""

    def __init__(self) -> None:
        self.normalizer = PRMRControlledAlphaAPI()

    @staticmethod
    def scope_key(scope: AuthenticatedScope) -> str:
        return f"{scope.client_id}::{scope.vault_id}::{scope.namespace}"

    @staticmethod
    def deterministic_event_id(scope: AuthenticatedScope, candidate: CandidateMemory) -> str:
        material = {
            "client_id": scope.client_id,
            "vault_id": scope.vault_id,
            "namespace": scope.namespace,
            "candidate_id": candidate.candidate_id,
            "candidate_fingerprint_sha256": candidate.candidate_fingerprint_sha256,
            "admission_bridge_revision": ADMISSION_BRIDGE_REVISION,
        }
        return f"evt_mem_{sha256_text(canonical_json(material))[:24]}"

    @staticmethod
    def deterministic_link_id(candidate_id: str, event_id: str) -> str:
        return f"amem_{sha256_text(canonical_json({'candidate_id': candidate_id, 'event_id': event_id}))[:24]}"

    @staticmethod
    def occurred_at(
        candidate: CandidateMemory,
        source: SourceRecord,
        evidence: list[CandidateEvidence],
        segments: dict[str, SourceSegment],
    ) -> str:
        if candidate.proposed_occurred_at:
            return candidate.proposed_occurred_at
        primary = next((item for item in evidence if item.evidence_role == "primary"), None)
        if primary and segments.get(primary.segment_id) and segments[primary.segment_id].occurred_at:
            return str(segments[primary.segment_id].occurred_at)
        return str(source.occurred_at or source.ingested_at)

    @staticmethod
    def timestamp_index(
        occurred_at: str,
        *,
        segment_sequence: int,
        candidate_order: int,
    ) -> int:
        try:
            normalized = occurred_at.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            epoch_ms = int(parsed.timestamp() * 1000)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MemoryAdmissionError(
                "ADMISSION_EVENT_CREATE_FAILED",
                "Candidate source chronology could not be normalized.",
            ) from exc
        return epoch_ms * 1_000_000 + max(0, segment_sequence) * 1_000 + max(0, candidate_order)

    def build_event(
        self,
        *,
        scope: AuthenticatedScope,
        candidate: CandidateMemory,
        source: SourceRecord,
        evidence: list[CandidateEvidence],
        segments: dict[str, SourceSegment],
        admission_id: str,
        admitted_memory_link_id: str,
        candidate_order: int,
    ) -> dict[str, Any]:
        if not candidate.proposed_event_type or not EVENT_TYPE_PATTERN.fullmatch(candidate.proposed_event_type):
            raise MemoryAdmissionError("ADMISSION_EVENT_TYPE_INVALID", "Candidate event type is invalid.")
        if not candidate.proposed_signal.strip() or len(candidate.proposed_signal) > 1_200:
            raise MemoryAdmissionError(
                "ADMISSION_SIGNAL_INVALID",
                "Candidate signal is empty or exceeds the existing event contract.",
            )
        primary = next((item for item in evidence if item.evidence_role == "primary"), None)
        if primary is None or primary.segment_id not in segments:
            raise MemoryAdmissionError("ADMISSION_EVIDENCE_INVALID", "Primary candidate evidence is unavailable.")
        occurred_at = self.occurred_at(candidate, source, evidence, segments)
        event_id = self.deterministic_event_id(scope, candidate)
        metadata = {
            "memory_origin": "candidate_admission",
            "source_id": source.source_id,
            "candidate_id": candidate.candidate_id,
            "extraction_run_id": candidate.extraction_run_id,
            "admission_id": admission_id,
            "admitted_memory_link_id": admitted_memory_link_id,
            "epistemic_status": candidate.epistemic_status,
            "extraction_method": candidate.extraction_method,
            "candidate_fingerprint_sha256": candidate.candidate_fingerprint_sha256,
            "evidence_manifest_hash_sha256": candidate.evidence_manifest_hash_sha256,
            "source_content_hash_sha256": source.content_hash_sha256,
            "admission_policy_revision": ADMISSION_POLICY_REVISION,
            "admission_bridge_revision": ADMISSION_BRIDGE_REVISION,
            "admitted_event_metadata_revision": ADMITTED_EVENT_METADATA_REVISION,
        }
        canonical_signal = source.metadata.get("canonical_signal")
        if (
            isinstance(canonical_signal, str)
            and EVENT_TYPE_PATTERN.fullmatch(canonical_signal)
        ):
            metadata["canonical_signal"] = canonical_signal
        importance_level = source.metadata.get("importance_level")
        if importance_level in {"low", "normal", "high", "critical"}:
            metadata["importance_level"] = importance_level
        importance_weight = source.metadata.get("importance_weight")
        if (
            isinstance(importance_weight, (int, float))
            and not isinstance(importance_weight, bool)
            and 0.50 <= float(importance_weight) <= 2.00
        ):
            metadata["importance_weight"] = float(importance_weight)
        # State metadata is trusted adapter metadata carried by SourceInput,
        # never a directive parsed from source content. V2 uses only this
        # narrow allowlist when selecting state dimensions and roles.
        state_key = source.metadata.get("state_key")
        if (
            isinstance(state_key, str)
            and EVENT_TYPE_PATTERN.fullmatch(state_key)
        ):
            metadata["state_key"] = state_key
        state_role = source.metadata.get("state_role")
        if state_role in {
            "state_assertion",
            "state_transition",
            "milestone",
            "decision",
            "goal",
            "blocker",
            "observation",
            "statement",
            "unknown",
            "non_state",
        }:
            metadata["state_role"] = state_role
        state_value = source.metadata.get("state_value")
        if isinstance(state_value, (str, int, float, bool)):
            metadata["state_value"] = str(state_value)[:500]
        payload = {
            "event_id": event_id,
            "event_type": candidate.proposed_event_type,
            "signal": candidate.proposed_signal,
            "occurred_at": occurred_at,
            "timestamp_index": self.timestamp_index(
                occurred_at,
                segment_sequence=segments[primary.segment_id].sequence_index,
                candidate_order=candidate_order,
            ),
            "application_reference": candidate.application_reference,
            "actor_reference": candidate.actor_reference,
            "workspace_reference": candidate.workspace_reference,
            "entity_reference": candidate.entity_references[0] if candidate.entity_references else None,
            "session_reference": candidate.session_reference,
            "metadata": metadata,
        }
        normalized, error = self.normalizer.normalize_event(payload, candidate_order)
        if error:
            raise MemoryAdmissionError("ADMISSION_EVENT_CREATE_FAILED", error)
        normalized["event_id"] = event_id
        return normalized

    def build_packet(
        self,
        scope: AuthenticatedScope,
        events: list[dict[str, Any]],
        *,
        previous_packet: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ordered = sorted(
            events,
            key=lambda item: (
                int(item.get("timestamp_index", 0)),
                str(item.get("timestamp", "")),
                str(item.get("event_id", "")),
            ),
        )
        entity_scope = {
            "application_reference": scope.application_reference or "",
            "actor_reference": scope.actor_reference or "",
            "workspace_reference": scope.workspace_reference or "",
            "entity_reference": scope.entity_reference or "",
            "session_reference": scope.session_reference or "",
        }
        context = {
            "client_id": scope.client_id,
            "vault_id": scope.vault_id,
            "namespace": scope.namespace,
        }
        packet_id = self.normalizer.deterministic_packet_id(context, entity_scope, ordered)
        packet = {
            **self.normalizer.build_theory_packet(ordered),
            "packet_id": packet_id,
            "report_id": f"report_{packet_id.removeprefix('packet_')}",
            **context,
            **entity_scope,
            "scope_mode": "entity_scoped" if any(entity_scope.values()) else "legacy_namespace_scope",
            "source_event_count": len(ordered),
            "first_event_at": str(ordered[0].get("timestamp", "")) if ordered else None,
            "packet_version": PACKET_VERSION,
            "algorithm_revision": ALGORITHM_REVISION,
            "provenance": self.normalizer.packet_provenance(
                ordered,
                [],
                entity_scope,
                previous_packet,
            ),
            "public_safe": True,
        }
        packet["provenance"]["packet_reproducible"] = True
        packet["provenance"]["deterministic_packet_hash"] = packet_id.removeprefix("packet_")
        return packet

    @staticmethod
    def event_list_from_storage(value: Any) -> list[dict[str, Any]]:
        parsed = json.loads(value) if isinstance(value, str) else value
        return list(parsed or [])


__all__ = ["CandidateToEventBridge"]
