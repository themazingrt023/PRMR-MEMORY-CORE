"""Opt-in canonical signal adapters for temporal, query, packet, and checkpoint use."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from typing import Any

from .canonical_signal_models import SignalIdentityMode
from .canonical_signal_projection import CanonicalSignalProjector
from .canonical_signal_registry import CanonicalSignalRegistry
from .entity_store import json_value, placeholder, scope_params, table
from .memory_consolidation_engine import MemoryConsolidationEngine
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_query_engine import MemoryQueryEngine
from .memory_query_models import MemoryQueryRequest
from .memory_query_results import signal_key_for_event
from .memory_reconstruction import MemoryReconstructionService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


class CanonicalSignalIntegration:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.projector = CanonicalSignalProjector(repository, initialize=initialize)
        self.registry = self.projector.registry
        self.dynamics = MemoryDynamicsEngine(repository, initialize=initialize)
        self.queries = MemoryQueryEngine(repository, initialize=initialize)
        self.consolidation = MemoryConsolidationEngine(repository, initialize=initialize)
        self.reconstruction = MemoryReconstructionService(repository, initialize=initialize)
        self.p = placeholder(repository)
        self.artifacts = table(repository, "prmr_canonical_signal_artifacts")

    def compute_temporal(
        self,
        scope: AuthenticatedScope,
        *,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | None = None,
    ) -> Any:
        resolver = self._resolver(scope, boundary)
        return self.dynamics.compute_memory_dynamics(
            scope,
            subject_scope,
            boundary,
            persist=False,
            signal_identity_resolver=resolver,
        )

    def build_continuity_packet(
        self,
        scope: AuthenticatedScope,
        *,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        packet = self.dynamics.build_continuity_packet(
            scope,
            subject_scope,
            boundary,
            persist_dynamics=False,
            signal_identity_resolver=self._resolver(scope, boundary),
        )
        events = self._events(scope, boundary, subject_scope)
        projections = self.projector.project_events(
            scope,
            events,
            valid_at=boundary.valid_at or "",
            known_at=boundary.known_at or "",
        )
        distribution: dict[str, Counter[str]] = defaultdict(Counter)
        for item in projections:
            distribution[item.canonical_signal_key][item.original_signal_key] += 1
        manifest = self.registry.mapping_manifest(
            scope,
            valid_at=boundary.valid_at or "",
            known_at=boundary.known_at or "",
        )
        projection_hash = sha256_text(
            canonical_json([item.to_dict() for item in projections])
        )
        context = {
            "signal_identity_mode": SignalIdentityMode.CANONICAL_SIGNAL_V1.value,
            "canonical_signal_registry_revision": manifest["revision"],
            "canonical_mapping_manifest_hash": manifest["manifest_hash_sha256"],
            "mapping_decision_manifest": manifest["items"],
            "original_to_canonical_signal_distribution": {
                key: dict(sorted(value.items()))
                for key, value in sorted(distribution.items())
            },
            "projection_hash": projection_hash,
            "projection_revision": "canonical_signal_projection_v1",
        }
        packet["canonical_signal_context"] = context
        material = {
            "base_packet_hash": packet["provenance"]["deterministic_packet_hash"],
            **context,
        }
        digest = sha256_text(canonical_json(material))
        packet["base_exact_packet_id"] = packet["packet_id"]
        packet["packet_id"] = f"packet_canonical_{digest[:24]}"
        packet["report_id"] = f"report_canonical_{digest[:24]}"
        packet["provenance"]["deterministic_packet_hash"] = digest
        packet["provenance"]["signal_identity_mode"] = (
            SignalIdentityMode.CANONICAL_SIGNAL_V1.value
        )
        self._persist_artifact(
            scope,
            "continuity_packet",
            boundary,
            manifest["manifest_hash_sha256"],
            digest,
            {
                "packet_id": packet["packet_id"],
                "context": context,
                "event_ids": [item.event_id for item in projections],
            },
        )
        return packet

    def query_memory(
        self,
        scope: AuthenticatedScope,
        request: MemoryQueryRequest,
        *,
        signal_identity_mode: str = SignalIdentityMode.EXACT_SIGNAL_V1.value,
    ) -> Any:
        if signal_identity_mode == SignalIdentityMode.EXACT_SIGNAL_V1.value:
            return self.queries.query_memory(scope, request)
        if signal_identity_mode != SignalIdentityMode.CANONICAL_SIGNAL_V1.value:
            raise ValueError("CANONICAL_SIGNAL_INVALID")
        captured = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        boundary = MemoryTemporalBoundary(
            valid_at=request.valid_at or captured,
            known_at=request.known_at or captured,
        )
        dynamics = self.compute_temporal(scope, boundary=boundary, subject_scope={
            "application_reference": request.application_reference,
            "actor_reference": request.actor_reference,
            "workspace_reference": request.workspace_reference,
            "entity_reference": request.entity_id,
            "session_reference": request.session_reference,
        })
        signals = dynamics.signals
        if request.signal_key:
            signals = [item for item in signals if item.signal_key == request.signal_key]
        stable_signals = []
        for item in signals:
            payload = item.to_dict()
            payload.pop("created_at", None)
            stable_signals.append(payload)
        answer = {
            "signal_identity_mode": signal_identity_mode,
            "canonical_signal_key": request.signal_key,
            "signals": stable_signals,
            "original_signal_distribution": self._distribution(scope, boundary),
            "mapping_manifest": self.registry.mapping_manifest(
                scope,
                valid_at=boundary.valid_at or "",
                known_at=boundary.known_at or "",
            ),
            "evidence_availability": "event_references_preserved",
        }
        digest = sha256_text(
            canonical_json(
                {
                    "request": request.to_dict(),
                    "answer": answer,
                    "signal_identity_mode": signal_identity_mode,
                }
            )
        )
        return {
            "query_result_id": f"qres_canonical_{digest[:24]}",
            "query_type": request.query_type,
            "status": "answered" if signals else "no_data",
            "answer": answer,
            "result_hash_sha256": digest,
        }

    def consolidate_memory(
        self,
        scope: AuthenticatedScope,
        *,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | None = None,
        signal_identity_mode: str = SignalIdentityMode.EXACT_SIGNAL_V1.value,
    ) -> Any:
        if signal_identity_mode == SignalIdentityMode.EXACT_SIGNAL_V1.value:
            return self.consolidation.consolidate_memory(
                scope, subject_scope, boundary
            )
        packet = self.build_continuity_packet(
            scope, boundary=boundary, subject_scope=subject_scope
        )
        events = self._events(scope, boundary, subject_scope)
        manifest = packet["canonical_signal_context"][
            "canonical_mapping_manifest_hash"
        ]
        payload = {
            "signal_identity_mode": signal_identity_mode,
            "event_ids": sorted(str(item.get("event_id")) for item in events),
            "packet_id": packet["packet_id"],
            "packet_hash": packet["provenance"]["deterministic_packet_hash"],
            "mapping_manifest_hash": manifest,
            "raw_events_preserved": True,
            "membership_preserves_original_signals": True,
        }
        digest = sha256_text(canonical_json(payload))
        artifact_id = self._persist_artifact(
            scope,
            "canonical_checkpoint",
            boundary,
            manifest,
            digest,
            payload,
        )
        return {
            "canonical_checkpoint_id": artifact_id,
            "status": "completed",
            "checkpoint_hash_sha256": digest,
            **payload,
        }

    def _resolver(self, scope: AuthenticatedScope, boundary: MemoryTemporalBoundary):
        cache: dict[str, tuple[str, str]] = {}

        def resolve(event: dict[str, Any]) -> tuple[str, str]:
            original = signal_key_for_event(event)
            if original in cache:
                return cache[original]
            result = self.registry.resolve_canonical_signal(
                scope,
                original,
                valid_at=boundary.valid_at or "",
                known_at=boundary.known_at or "",
            )
            resolved = result.canonical_signal_key, (
                "approved_canonical_signal"
                if result.mapping_applied
                else "original_event_signal"
            )
            cache[original] = resolved
            return resolved

        return resolve

    def _events(
        self,
        scope: AuthenticatedScope,
        boundary: MemoryTemporalBoundary,
        subject_scope: dict[str, str | None] | None,
    ) -> list[dict[str, Any]]:
        kwargs = self.reconstruction._subject_kwargs(subject_scope)
        view = self.reconstruction.resolver.resolve_effective_events(
            scope, boundary, **kwargs, include_conflicted=True
        )
        return list(view.effective_events)

    def _distribution(
        self, scope: AuthenticatedScope, boundary: MemoryTemporalBoundary
    ) -> dict[str, dict[str, int]]:
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        for event in self._events(scope, boundary, None):
            projection = self.projector.project_event(
                scope,
                event,
                valid_at=boundary.valid_at or "",
                known_at=boundary.known_at or "",
            )
            counts[projection.canonical_signal_key][projection.original_signal_key] += 1
        return {
            key: dict(sorted(value.items())) for key, value in sorted(counts.items())
        }

    def _persist_artifact(
        self,
        scope: AuthenticatedScope,
        artifact_type: str,
        boundary: MemoryTemporalBoundary,
        mapping_manifest_hash: str,
        artifact_hash: str,
        payload: dict[str, Any],
    ) -> str:
        artifact_id = f"csart_{artifact_hash[:24]}"
        values = (
            artifact_id,
            scope.client_id,
            scope.vault_id,
            scope.namespace,
            artifact_type,
            boundary.valid_at,
            boundary.known_at,
            mapping_manifest_hash,
            artifact_hash,
            "current",
            boundary.known_at,
            json_value(self.repository, payload),
        )
        with self.repository.connect() as connection:
            if str(getattr(self.repository, "backend_name", "sqlite")) == "postgres":
                connection.execute(
                    f"INSERT INTO {self.artifacts}(canonical_artifact_id,client_id,"
                    f"vault_id,namespace,artifact_type,valid_at,known_at,"
                    f"mapping_manifest_hash,artifact_hash,artifact_status,created_at,"
                    f"payload_json) VALUES({','.join([self.p]*12)}) ON CONFLICT "
                    "(canonical_artifact_id) DO NOTHING",
                    values,
                )
            else:
                connection.execute(
                    f"INSERT OR IGNORE INTO {self.artifacts}(canonical_artifact_id,"
                    f"client_id,vault_id,namespace,artifact_type,valid_at,known_at,"
                    f"mapping_manifest_hash,artifact_hash,artifact_status,created_at,"
                    f"payload_json) VALUES({','.join([self.p]*12)})",
                    values,
                )
        return artifact_id


__all__ = ["CanonicalSignalIntegration"]
