"""Read-only generation and scoped persistence of Epistemic Continuity Packet V2."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .canonical_signal_registry import CanonicalSignalRegistry
from .continuity_v2_comparison import compare_packet_payloads
from .continuity_v2_entities import build_entity_context
from .continuity_v2_epistemic import (
    event_time,
    project_epistemic_information,
)
from .continuity_v2_integrity import (
    packet_hash_for,
    packet_id_for,
    packet_manifest_hash_for,
    verify_packet_v2_integrity,
)
from .continuity_v2_models import (
    CONTINUITY_V2_ACCELERATION_REVISION,
    CONTINUITY_V2_COMPARISON_REVISION,
    CONTINUITY_V2_ENTITY_REVISION,
    CONTINUITY_V2_EPISTEMIC_REVISION,
    CONTINUITY_V2_GOVERNANCE_REVISION,
    CONTINUITY_V2_INTEGRITY_REVISION,
    CONTINUITY_V2_PROVENANCE_REVISION,
    CONTINUITY_V2_RELATIONSHIP_REVISION,
    CONTINUITY_V2_SCHEMA_REVISION,
    CONTINUITY_V2_STATE_REVISION,
    CONTINUITY_V2_TEMPORAL_REVISION,
    ContinuityConflictContext,
    ContinuityLineageContextV2,
    ContinuityPacketStatus,
    ContinuityPacketV2,
    ContinuityPacketV2Error,
    ContinuityUnknownContext,
)
from .continuity_v2_policy import (
    CONTINUITY_V2_POLICY_ID,
    CONTINUITY_V2_POLICY_REVISION,
    ContinuityPacketV2Policy,
)
from .continuity_v2_provenance import (
    build_governance_context,
    build_provenance_context,
)
from .continuity_v2_relationships import build_relationship_context
from .continuity_v2_state_resolver import (
    resolve_primary_current_state,
    resolve_state_dimensions,
)
from .continuity_v2_temporal import project_temporal_layers
from .entity_store import json_value, placeholder, table
from .memory_consolidation_integrity import MemoryConsolidationIntegrityVerifier
from .memory_consolidation_store import MemoryConsolidationStore
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_ledger_models import MemoryTemporalBoundary
from .memory_recurrence import signal_identity
from .memory_state_resolver import MemoryStateResolver
from .relationship_memory import RelationshipMemoryService
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


ROOT = Path(__file__).resolve().parents[2]
SQLITE_MIGRATION = ROOT / "migrations" / "core_continuity_packet_v2_sqlite.sql"
POSTGRES_MIGRATION = ROOT / "migrations" / "core_continuity_packet_v2_postgres.sql"


def utc(value: str | None = None) -> str:
    raw = value or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def initialize_continuity_v2_schema(repository: Any) -> None:
    path = POSTGRES_MIGRATION if str(getattr(repository, "backend_name", "sqlite")) == "postgres" else SQLITE_MIGRATION
    sql = path.read_text(encoding="utf-8")
    with repository.connect() as connection:
        if hasattr(connection, "executescript"):
            connection.executescript(sql)
        else:
            connection.execute(sql)


class ContinuityPacketV2Service:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_continuity_v2_schema(repository)
        self.state = MemoryStateResolver(repository, initialize=initialize)
        self.dynamics = MemoryDynamicsEngine(repository, initialize=initialize)
        self.canonical = CanonicalSignalRegistry(repository, initialize=initialize)
        self.relationships = RelationshipMemoryService(repository, initialize=initialize)
        self.p = placeholder(repository)
        self.packet_table = table(repository, "prmr_continuity_packets_v2")
        self.dimension_table = table(repository, "prmr_continuity_packet_state_dimensions_v2")
        self.item_table = table(repository, "prmr_continuity_packet_items_v2")
        self.conflict_table = table(repository, "prmr_continuity_packet_conflicts_v2")
        self.entity_table = table(repository, "prmr_continuity_packet_entities_v2")
        self.relationship_table = table(repository, "prmr_continuity_packet_relationships_v2")
        self.comparison_table = table(repository, "prmr_continuity_packet_comparisons_v2")

    def generate_packet_v2(
        self,
        authenticated_scope: AuthenticatedScope,
        subject_scope: dict[str, str | None] | None = None,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        policy_id: str = CONTINUITY_V2_POLICY_ID,
        signal_identity_mode: str = "exact_signal_v1",
        persist: bool = True,
        *,
        event_ids: set[str] | frozenset[str] | None = None,
        policy_override: ContinuityPacketV2Policy | None = None,
        _verify_integrity: bool = True,
    ) -> ContinuityPacketV2:
        policy = policy_override or ContinuityPacketV2Policy(
            policy_id=policy_id, signal_identity_mode=signal_identity_mode
        )
        if policy_override and policy.signal_identity_mode != signal_identity_mode:
            raise ContinuityPacketV2Error(
                "CONTINUITY_V2_POLICY_INVALID",
                "Policy override signal identity mode does not match the requested mode.",
            )
        policy.validate()
        subject = self._subject_scope(authenticated_scope, subject_scope)
        frozen = utc()
        requested = temporal_boundary or MemoryTemporalBoundary()
        boundary = MemoryTemporalBoundary(
            valid_at=utc(requested.valid_at or frozen),
            known_at=utc(requested.known_at or frozen),
        )
        view = self.state.resolve_effective_events(
            authenticated_scope,
            boundary,
            application_reference=subject.get("application_reference"),
            actor_reference=subject.get("actor_reference"),
            workspace_reference=subject.get("workspace_reference"),
            entity_reference=subject.get("entity_reference"),
            session_reference=subject.get("session_reference"),
            include_conflicted=True,
            event_ids=event_ids,
        )
        effective_ids = [str(item["event_id"]) for item in view.effective_events]
        provenance, provenance_by_event = build_provenance_context(
            self.repository, authenticated_scope, effective_ids
        )
        mapping_manifest, signal_projection, resolver = self._signal_projection(
            authenticated_scope,
            view.effective_events,
            boundary,
            signal_identity_mode,
        )
        dynamics = self.dynamics.compute_memory_dynamics(
            authenticated_scope,
            subject,
            boundary,
            persist=False,
            event_ids=frozenset(effective_ids),
            signal_identity_resolver=resolver,
        )
        dynamics_by_signal = {item.signal_key: item for item in dynamics.signals}
        projection_by_event = {item.event_id: item for item in view.projections}
        layers = project_epistemic_information(
            view.effective_events,
            projection_by_event,
            dynamics_by_signal,
            signal_projection,
            provenance_by_event,
            signal_identity_mode=signal_identity_mode,
        )
        if sum(len(value) for key, value in layers.items() if key != "conflicted_information") > policy.maximum_packet_items:
            raise ContinuityPacketV2Error("CONTINUITY_V2_LIMIT_EXCEEDED", "Packet item limit was exceeded.")
        dimensions = resolve_state_dimensions(
            layers, signal_identity_mode=signal_identity_mode
        )
        item_by_event = {
            str(item["event_id"]): item
            for name in (
                "asserted_information",
                "derived_information",
                "tentative_information",
                "unknown_information",
            )
            for item in layers[name]
        }
        current = resolve_primary_current_state(dimensions, item_by_event)
        temporal = project_temporal_layers(layers)
        relationship_context, relationship_manifest, relationships_by_entity, relationship_conflicts = build_relationship_context(
            self.repository,
            authenticated_scope,
            entity_id=subject.get("entity_reference"),
            valid_at=boundary.valid_at or frozen,
            known_at=boundary.known_at or frozen,
            maximum_items=policy.maximum_relationship_items,
        )
        entities = build_entity_context(
            self.repository,
            authenticated_scope,
            set(effective_ids),
            item_by_event,
            relationships_by_entity,
            requested_entity_id=subject.get("entity_reference"),
            valid_at=boundary.valid_at or frozen,
            known_at=boundary.known_at or frozen,
        )[: policy.maximum_entity_items]
        entity_context = [item.to_dict() for item in entities]
        entity_manifest = sha256_text(canonical_json(entity_context))
        conflicts = self._conflict_context(
            view, dimensions, item_by_event, relationship_conflicts
        )[: policy.maximum_conflict_items]
        unknown = self._unknown_context(layers["unknown_information"])
        lineage = self._lineage_context(
            authenticated_scope,
            boundary,
            effective_ids,
            mapping_manifest,
            item_by_event,
        )
        governance = build_governance_context(
            self.repository, authenticated_scope, provenance
        )
        legacy = self.dynamics.build_continuity_packet(
            authenticated_scope,
            subject_scope=subject,
            temporal_boundary=boundary,
            persist_dynamics=False,
            event_ids=frozenset(effective_ids),
        )
        metrics = self._metrics(
            layers,
            temporal,
            provenance.to_dict(),
            governance.to_dict(),
            entity_context,
            relationship_context,
            item_by_event,
            current=current.to_dict(),
            valid_at=boundary.valid_at or frozen,
        )
        eligible_source_ids = sorted(
            item.event_id
            for item in view.projections
            if item.valid_from <= (boundary.valid_at or frozen)
            and item.system_known_from <= (boundary.known_at or frozen)
        )
        effective_manifest = sha256_text(canonical_json(sorted(effective_ids)))
        conflict_manifest = sha256_text(canonical_json([item.to_dict() for item in conflicts]))
        revisions = self._revisions()
        packet_status = current.primary_state_status
        if governance.governance_erasure_present:
            packet_status = ContinuityPacketStatus.GOVERNANCE_ERASURE_LIMITED.value
        elif provenance.partial_event_count or provenance.legacy_event_count:
            packet_status = (
                ContinuityPacketStatus.PARTIALLY_RECOVERABLE.value
                if packet_status != ContinuityPacketStatus.NO_DATA.value
                else packet_status
            )
        payload: dict[str, Any] = {
            "packet_id": "",
            "packet_version": CONTINUITY_V2_SCHEMA_REVISION,
            "packet_mode": policy.packet_mode,
            "packet_status": packet_status,
            "client_id": authenticated_scope.client_id,
            "vault_id": authenticated_scope.vault_id,
            "namespace": authenticated_scope.namespace,
            "application_reference": subject.get("application_reference"),
            "actor_reference": subject.get("actor_reference"),
            "workspace_reference": subject.get("workspace_reference"),
            "entity_id": subject.get("entity_reference"),
            "session_reference": subject.get("session_reference"),
            "valid_at": boundary.valid_at,
            "known_at": boundary.known_at,
            "generated_at": boundary.known_at,
            "current_state": current.to_dict(),
            "state_dimensions": [item.to_dict() for item in dimensions],
            **layers,
            **temporal,
            "conflict_context": [item.to_dict() for item in conflicts],
            "unknown_context": unknown.to_dict(),
            "entity_context": entity_context,
            "relationship_context": relationship_context,
            "lineage_context": lineage.to_dict(),
            "provenance_context": provenance.to_dict(),
            "governance_context": governance.to_dict(),
            "legacy_coherence_score": float(legacy.get("coherence_score", 0.0)),
            "legacy_coherence_breakdown": {
                "score": float(legacy.get("coherence_score", 0.0)),
                "algorithm_revision": legacy.get("algorithm_revision"),
                "formula_unchanged": True,
            },
            "legacy_recoverability_score": float(legacy.get("recoverability_score", 0.0)),
            "legacy_recoverability_breakdown": {
                "score": float(legacy.get("recoverability_score", 0.0)),
                "algorithm_revision": legacy.get("algorithm_revision"),
                "formula_unchanged": True,
            },
            "v2_metrics": metrics,
            "source_event_manifest_hash": sha256_text(canonical_json(eligible_source_ids)),
            "effective_event_manifest_hash": effective_manifest,
            "temporal_dynamics_snapshot_id": dynamics.snapshot.dynamics_snapshot_id,
            "entity_manifest_hash": entity_manifest,
            "relationship_manifest_hash": relationship_manifest,
            "conflict_manifest_hash": conflict_manifest,
            "canonical_signal_manifest_hash": mapping_manifest["manifest_hash_sha256"],
            "governance_manifest_hash": governance.governance_context_hash,
            "packet_policy_configuration": policy.to_dict(),
            "revisions": revisions,
            "packet_manifest_hash": "",
            "packet_hash": "",
            "created_at": boundary.known_at,
        }
        payload["packet_id"] = packet_id_for(payload)
        payload["packet_manifest_hash"] = packet_manifest_hash_for(payload)
        payload["packet_hash"] = packet_hash_for(payload)
        if _verify_integrity:
            integrity = verify_packet_v2_integrity(authenticated_scope, payload)
            if not integrity.verified:
                raise ContinuityPacketV2Error(
                    "CONTINUITY_V2_INTEGRITY_FAILED",
                    "Generated packet failed deterministic integrity verification: "
                    + ",".join(integrity.failures),
                )
        packet = ContinuityPacketV2(**payload)
        if persist:
            self._persist(packet)
        return packet

    def generate_verified_accelerated_packet_v2(
        self,
        authenticated_scope: AuthenticatedScope,
        checkpoint_id: str,
        subject_scope: dict[str, str | None] | None = None,
        *,
        signal_identity_mode: str = "exact_signal_v1",
        persist: bool = True,
        policy_override: ContinuityPacketV2Policy | None = None,
    ) -> dict[str, Any]:
        store = MemoryConsolidationStore(self.repository, initialize=False)
        checkpoint = store.get_checkpoint(authenticated_scope, checkpoint_id)
        if checkpoint is None or checkpoint.checkpoint_status != "current":
            packet = self.generate_packet_v2(
                authenticated_scope,
                subject_scope,
                signal_identity_mode=signal_identity_mode,
                persist=persist,
                policy_override=policy_override,
            )
            return {"packet": packet, "acceleration_used": False, "fallback_reason": "checkpoint_unavailable_or_stale"}
        integrity = MemoryConsolidationIntegrityVerifier(
            self.repository, initialize=False
        ).verify_consolidation_integrity(
            authenticated_scope, checkpoint.consolidation_run_id
        )
        boundary = MemoryTemporalBoundary(
            valid_at=checkpoint.valid_at, known_at=checkpoint.known_at
        )
        canonical_packet = self.generate_packet_v2(
            authenticated_scope,
            subject_scope,
            boundary,
            signal_identity_mode=signal_identity_mode,
            persist=False,
            policy_override=policy_override,
        )
        event_ids = frozenset(
            str(value)
            for value in checkpoint.deterministic_state_payload.get(
                "effective_event_ids", []
            )
        )
        checkpoint_event_id_manifest = sha256_text(
            canonical_json(sorted(event_ids))
        )
        if (
            not integrity.verified
            or checkpoint_event_id_manifest
            != canonical_packet.effective_event_manifest_hash
        ):
            if persist:
                self._persist(canonical_packet)
            return {"packet": canonical_packet, "acceleration_used": False, "fallback_reason": "checkpoint_integrity_or_manifest_mismatch"}
        accelerated = self.generate_packet_v2(
            authenticated_scope,
            subject_scope,
            boundary,
            signal_identity_mode=signal_identity_mode,
            persist=False,
            event_ids=event_ids,
            policy_override=policy_override,
            _verify_integrity=False,
        )
        equivalent = (
            canonical_packet.packet_id == accelerated.packet_id
            and canonical_packet.packet_hash == accelerated.packet_hash
            and canonical_packet.to_dict() == accelerated.to_dict()
        )
        selected = accelerated if equivalent else canonical_packet
        if persist:
            self._persist(selected)
        return {
            "packet": selected,
            "acceleration_used": equivalent,
            "fallback_reason": None if equivalent else "exact_equivalence_failed",
            "equivalence_verified": equivalent,
            "checkpoint_id": checkpoint_id,
            "acceleration_revision": CONTINUITY_V2_ACCELERATION_REVISION,
        }

    def get_packet_v2(
        self, authenticated_scope: AuthenticatedScope, packet_id: str
    ) -> ContinuityPacketV2:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.packet_table} WHERE packet_id={self.p} "
                f"AND client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                "AND artifact_status='current'",
                (packet_id, *authenticated_scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise ContinuityPacketV2Error(
                "CONTINUITY_V2_NOT_FOUND", "Packet was not found in authenticated scope."
            )
        return ContinuityPacketV2(**self._decode(row["payload_json"]))

    def list_packets_v2(
        self, authenticated_scope: AuthenticatedScope, *, limit: int = 100
    ) -> list[ContinuityPacketV2]:
        if not 1 <= limit <= 500:
            raise ContinuityPacketV2Error("CONTINUITY_V2_POLICY_INVALID", "Packet list limit is invalid.")
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.packet_table} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} AND artifact_status='current' "
                f"ORDER BY created_at,packet_id LIMIT {self.p}",
                (*authenticated_scope.memory_boundary(), limit),
            ).fetchall()
        return [ContinuityPacketV2(**self._decode(row["payload_json"])) for row in rows]

    def compare_packets_v2(
        self,
        authenticated_scope: AuthenticatedScope,
        first_packet_id: str,
        second_packet_id: str,
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        first = self.get_packet_v2(authenticated_scope, first_packet_id).to_dict()
        second = self.get_packet_v2(authenticated_scope, second_packet_id).to_dict()
        comparison = compare_packet_payloads(first, second).to_dict()
        if persist:
            with self.repository.connect() as connection:
                connection.execute(
                    f"INSERT INTO {self.comparison_table}(comparison_hash,first_packet_id,second_packet_id,"
                    f"client_id,vault_id,namespace,created_at,payload_json) VALUES({','.join([self.p]*8)}) "
                    "ON CONFLICT(comparison_hash) DO NOTHING",
                    (
                        comparison["comparison_hash"],
                        first_packet_id,
                        second_packet_id,
                        *authenticated_scope.memory_boundary(),
                        second["created_at"],
                        json_value(self.repository, comparison),
                    ),
                )
        return comparison

    def trace_packet_v2_origin(
        self, authenticated_scope: AuthenticatedScope, packet_id: str
    ) -> dict[str, Any]:
        packet = self.get_packet_v2(authenticated_scope, packet_id)
        return {
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "effective_event_ids": sorted(
                {
                    item["event_id"]
                    for name in (
                        "asserted_information",
                        "derived_information",
                        "tentative_information",
                        "unknown_information",
                    )
                    for item in getattr(packet, name)
                }
            ),
            "provenance_manifest_hash": packet.provenance_context["provenance_manifest_hash"],
            "lineage_manifest_hash": packet.lineage_context["lineage_manifest_hash"],
            "source_content_included": False,
        }

    def verify_packet_v2_integrity(
        self, authenticated_scope: AuthenticatedScope, packet_id: str
    ) -> Any:
        return verify_packet_v2_integrity(
            authenticated_scope,
            self.get_packet_v2(authenticated_scope, packet_id).to_dict(),
        )

    def invalidate_packet_v2(
        self, authenticated_scope: AuthenticatedScope, packet_id: str, reason: str
    ) -> bool:
        if not reason or len(reason) > 200:
            raise ContinuityPacketV2Error("CONTINUITY_V2_INVALIDATION_INVALID", "Invalidation reason is invalid.")
        with self.repository.connect() as connection:
            cursor = connection.execute(
                f"UPDATE {self.packet_table} SET artifact_status='invalidated' "
                f"WHERE packet_id={self.p} AND client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND artifact_status='current'",
                (packet_id, *authenticated_scope.memory_boundary()),
            )
        return int(cursor.rowcount) == 1

    def replay_packet_v2(
        self, authenticated_scope: AuthenticatedScope, packet_id: str
    ) -> ContinuityPacketV2:
        stored = self.get_packet_v2(authenticated_scope, packet_id)
        regenerated = self.generate_packet_v2(
            authenticated_scope,
            {
                "application_reference": stored.application_reference,
                "actor_reference": stored.actor_reference,
                "workspace_reference": stored.workspace_reference,
                "entity_reference": stored.entity_id,
                "session_reference": stored.session_reference,
            },
            MemoryTemporalBoundary(stored.valid_at, stored.known_at),
            signal_identity_mode=stored.packet_policy_configuration["signal_identity_mode"],
            persist=False,
        )
        if stored.packet_id != regenerated.packet_id or stored.packet_hash != regenerated.packet_hash:
            raise ContinuityPacketV2Error("CONTINUITY_V2_REPLAY_MISMATCH", "Packet replay did not reproduce stored identity.")
        return regenerated

    def _signal_projection(
        self,
        scope: AuthenticatedScope,
        events: list[dict[str, Any]],
        boundary: MemoryTemporalBoundary,
        mode: str,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], Any]:
        originals = sorted({signal_identity(event)[0] for event in events})
        if mode == "exact_signal_v1":
            items = [
                {
                    "original_signal_key": key,
                    "canonical_signal_key": None,
                    "mapping_applied": False,
                    "alias_assertion_ids": [],
                    "mapping_decision_ids": [],
                }
                for key in originals
            ]
            manifest = {
                "items": items,
                "manifest_hash_sha256": sha256_text(canonical_json({"mode": mode, "items": items})),
                "revision": "canonical_signal_manifest_v1",
            }
            projection = {item["original_signal_key"]: item for item in items}
            return manifest, projection, None
        items = []
        projection = {}
        for key in originals:
            resolution = self.canonical.resolve_canonical_signal(
                scope,
                key,
                valid_at=str(boundary.valid_at),
                known_at=str(boundary.known_at),
            )
            item = {
                "original_signal_key": key,
                "canonical_signal_key": resolution.canonical_signal_key,
                "mapping_applied": resolution.mapping_applied,
                "alias_assertion_ids": list(resolution.alias_assertion_ids),
                "mapping_decision_ids": list(resolution.mapping_decision_ids),
                "mapping_manifest_hash": resolution.manifest_hash_sha256,
            }
            items.append(item)
            projection[key] = item
        manifest = self.canonical.mapping_manifest(
            scope, valid_at=str(boundary.valid_at), known_at=str(boundary.known_at)
        )
        manifest = {**manifest, "event_signal_resolutions": items}
        manifest["manifest_hash_sha256"] = sha256_text(canonical_json(manifest))

        def resolver(event: dict[str, Any]) -> tuple[str, str]:
            original = signal_identity(event)[0]
            return str(projection[original]["canonical_signal_key"]), "approved_canonical_mapping"

        return manifest, projection, resolver

    def _conflict_context(
        self,
        view: Any,
        dimensions: list[Any],
        items: dict[str, dict[str, Any]],
        relationship_conflicts: list[dict[str, Any]],
    ) -> list[ContinuityConflictContext]:
        result: list[ContinuityConflictContext] = []
        for conflict in [*view.open_conflicts, *view.resolved_conflicts]:
            affected = sorted(
                item.state_dimension_key
                for item in dimensions
                if set(item.effective_event_ids) & set(conflict.conflicting_event_ids)
            )
            refs = [
                ref
                for event_id in conflict.conflicting_event_ids
                for ref in items.get(event_id, {}).get("provenance_references", [])
            ]
            material = {
                "id": conflict.conflict_id,
                "status": conflict.conflict_status,
                "events": sorted(conflict.conflicting_event_ids),
                "dimensions": affected,
                "resolution": conflict.resolution_event_id,
                "revision": "continuity_conflict_context_v1",
            }
            result.append(
                ContinuityConflictContext(
                    conflict_id=conflict.conflict_id,
                    conflict_type=conflict.conflict_type,
                    status=conflict.conflict_status,
                    affected_dimension_keys=affected,
                    participating_event_ids=sorted(conflict.conflicting_event_ids),
                    participating_relationship_ids=[],
                    epistemic_statuses=sorted({str(items.get(event_id, {}).get("epistemic_status", "unknown")) for event_id in conflict.conflicting_event_ids}),
                    valid_from=conflict.valid_from,
                    known_from=conflict.system_effective_at,
                    resolution_event_id=conflict.resolution_event_id,
                    resolution_relationship_id=None,
                    evidence_references=refs,
                    conflict_hash=sha256_text(canonical_json(material)),
                )
            )
        for conflict in relationship_conflicts:
            material = {
                "id": conflict["conflict_id"],
                "status": conflict["conflict_status"],
                "relationships": sorted(conflict.get("relationship_ids", [])),
                "revision": "continuity_conflict_context_v1",
            }
            result.append(
                ContinuityConflictContext(
                    conflict_id=str(conflict["conflict_id"]),
                    conflict_type=str(conflict.get("conflict_type", "relationship_conflict")),
                    status=str(conflict["conflict_status"]),
                    affected_dimension_keys=[],
                    participating_event_ids=[],
                    participating_relationship_ids=sorted(conflict.get("relationship_ids", [])),
                    epistemic_statuses=[],
                    valid_from=str(conflict.get("valid_from", "")),
                    known_from=str(conflict.get("system_effective_at", "")),
                    resolution_event_id=None,
                    resolution_relationship_id=conflict.get("resolution_relationship_id"),
                    evidence_references=[],
                    conflict_hash=sha256_text(canonical_json(material)),
                )
            )
        return sorted(result, key=lambda item: item.conflict_id)

    @staticmethod
    def _unknown_context(items: list[dict[str, Any]]) -> ContinuityUnknownContext:
        ordered = sorted(items, key=lambda item: (str(item.get("occurred_at", "")), str(item["event_id"])))
        material = {
            "events": [item["event_id"] for item in ordered],
            "dimensions": sorted({str(item["state_dimension"]) for item in ordered}),
            "statements": [item["signal"] for item in ordered],
            "revision": "continuity_unknown_context_v1",
        }
        return ContinuityUnknownContext(
            unknown_event_ids=material["events"],
            unknown_dimension_keys=material["dimensions"],
            exact_unknown_statements=material["statements"],
            first_unknown_at=ordered[0]["occurred_at"] if ordered else None,
            latest_unknown_at=ordered[-1]["occurred_at"] if ordered else None,
            currently_active_unknown_count=len(ordered),
            historically_resolved_unknown_count=0,
            unresolved_unknown_count=len(ordered),
            resolution_event_ids=[],
            evidence_references=[ref for item in ordered for ref in item.get("provenance_references", [])],
            unknown_context_hash=sha256_text(canonical_json(material)),
        )

    def _lineage_context(
        self,
        scope: AuthenticatedScope,
        boundary: MemoryTemporalBoundary,
        effective_ids: list[str],
        mapping_manifest: dict[str, Any],
        items: dict[str, dict[str, Any]],
    ) -> ContinuityLineageContextV2:
        evolutions = [
            item
            for item in self.state.ledger.list_evolutions(scope)
            if item.system_effective_at <= str(boundary.known_at)
            and item.valid_from <= str(boundary.valid_at)
        ]
        relationships = [
            item
            for item in self.relationships.list_evolutions(scope)
            if item.system_effective_at <= str(boundary.known_at)
            and item.valid_from <= str(boundary.valid_at)
        ]
        merge_table = table(self.repository, "prmr_entity_merges")
        with self.repository.connect() as connection:
            merge_rows = connection.execute(
                f"SELECT entity_merge_id,source_entity_id,target_entity_id,valid_from,"
                f"system_effective_at FROM {merge_table} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND valid_from<={self.p} AND system_effective_at<={self.p} "
                "ORDER BY system_effective_at,entity_merge_id",
                (*scope.memory_boundary(), boundary.valid_at, boundary.known_at),
            ).fetchall()
        payload = {
            "originating_event_ids": sorted(effective_ids),
            "correction_chains": [
                {"evolution_id": item.evolution_id, "source_event_id": item.source_event_id, "replacement_event_id": item.replacement_event_id}
                for item in evolutions if item.evolution_type == "correct"
            ],
            "supersession_chains": [
                {"evolution_id": item.evolution_id, "source_event_id": item.source_event_id, "replacement_event_id": item.replacement_event_id}
                for item in evolutions if item.evolution_type == "supersede"
            ],
            "retraction_records": [
                {"evolution_id": item.evolution_id, "source_event_id": item.source_event_id}
                for item in evolutions if item.evolution_type == "retract"
            ],
            "conflict_declarations": [
                {"evolution_id": item.evolution_id, "conflict_id": item.conflict_id, "source_event_id": item.source_event_id}
                for item in evolutions if item.evolution_type == "declare_contradiction"
            ],
            "conflict_resolutions": [
                {"evolution_id": item.evolution_id, "conflict_id": item.conflict_id, "resolution_event_id": item.resolution_event_id}
                for item in evolutions if item.evolution_type == "resolve_contradiction"
            ],
            "entity_merge_history": [dict(item) for item in merge_rows],
            "relationship_evolution": [
                {
                    "relationship_evolution_id": item.relationship_evolution_id,
                    "evolution_type": item.evolution_type,
                    "source_relationship_id": item.source_relationship_id,
                    "replacement_relationship_id": item.replacement_relationship_id,
                    "conflict_id": item.conflict_id,
                }
                for item in relationships
            ],
            "canonical_signal_mapping_history": list(mapping_manifest.get("items", [])),
            "state_transition_records": [
                {"event_id": event_id, "state_dimension": item["state_dimension"], "valid_from": item["valid_from"]}
                for event_id, item in sorted(items.items())
                if item.get("state_role") == "state_transition"
            ],
        }
        payload["lineage_manifest_hash"] = sha256_text(canonical_json({**payload, "revision": "continuity_lineage_v2"}))
        return ContinuityLineageContextV2(**payload)

    @staticmethod
    def _metrics(
        layers: dict[str, list[dict[str, Any]]],
        temporal: dict[str, Any],
        provenance: dict[str, Any],
        governance: dict[str, Any],
        entities: list[dict[str, Any]],
        relationships: dict[str, list[dict[str, Any]]],
        items: dict[str, dict[str, Any]],
        *,
        current: dict[str, Any],
        valid_at: str,
    ) -> dict[str, Any]:
        total = len(items)
        times = sorted(event_time(item) for item in items.values() if event_time(item))
        def ratio(count: int) -> dict[str, Any]:
            return {"numerator": count, "denominator": total, "decimal": round(count / total, 8) if total else 0.0}
        relationship_ids = {
            item["relationship_id"] for values in relationships.values() for item in values
        }
        current_time = current.get("occurred_at") or current.get("valid_from")
        state_age = 0.0
        if current_time:
            state_age = max(
                0.0,
                (
                    datetime.fromisoformat(valid_at.replace("Z", "+00:00"))
                    - datetime.fromisoformat(str(current_time).replace("Z", "+00:00"))
                ).total_seconds(),
            )
        return {
            "asserted_item_count": len(layers["asserted_information"]),
            "derived_item_count": len(layers["derived_information"]),
            "tentative_item_count": len(layers["tentative_information"]),
            "unknown_item_count": len(layers["unknown_information"]),
            "conflicted_item_count": len(layers["conflicted_information"]),
            "active_item_count": len(temporal["active_information_v2"]),
            "latent_item_count": len(temporal["latent_information_v2"]),
            "dormant_item_count": len(temporal["dormant_information_v2"]),
            "decayed_item_count": len(temporal["decayed_information_v2"]),
            "reinforced_item_count": len(temporal["reinforced_information_v2"]),
            "re_emerging_item_count": len(temporal["re_emergence_information_v2"]),
            "provenance_coverage_rate": provenance["provenance_coverage_rate"],
            "tentative_ratio": ratio(len(layers["tentative_information"])),
            "unknown_ratio": ratio(len(layers["unknown_information"])),
            "conflict_ratio": ratio(len(layers["conflicted_information"])),
            "temporal_coverage_seconds": (
                max(0.0, (datetime.fromisoformat(times[-1].replace("Z", "+00:00")) - datetime.fromisoformat(times[0].replace("Z", "+00:00"))).total_seconds()) if len(times) > 1 else 0.0
            ),
            "current_state_age_seconds": state_age,
            "governance_loss_count": governance["historically_unrecoverable_item_count"],
            "entity_count": len(entities),
            "relationship_count": len(relationship_ids),
            "metrics_revision": "continuity_v2_metrics_v1",
            "aggregate_intelligence_score": None,
        }

    def _persist(self, packet: ContinuityPacketV2) -> None:
        payload = packet.to_dict()
        existing = self._packet_by_id(packet.packet_id)
        if existing:
            if existing.packet_hash != packet.packet_hash:
                raise ContinuityPacketV2Error("CONTINUITY_V2_IDENTITY_COLLISION", "Packet identity already has different content.")
            return
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.packet_table}(packet_id,client_id,vault_id,namespace,packet_status,"
                f"valid_at,known_at,entity_id,signal_identity_mode,packet_hash,effective_event_manifest_hash,"
                f"artifact_status,created_at,payload_json) VALUES({','.join([self.p]*14)})",
                (
                    packet.packet_id,
                    packet.client_id,
                    packet.vault_id,
                    packet.namespace,
                    packet.packet_status,
                    packet.valid_at,
                    packet.known_at,
                    packet.entity_id,
                    packet.packet_policy_configuration["signal_identity_mode"],
                    packet.packet_hash,
                    packet.effective_event_manifest_hash,
                    "current",
                    packet.created_at,
                    json_value(self.repository, payload),
                ),
            )
            dimension_rows = [
                (
                    packet.packet_id,
                    item["state_dimension_key"],
                    *packet_scope(packet),
                    item["resolution_status"],
                    item["state_dimension_hash"],
                    packet.created_at,
                    json_value(self.repository, item),
                )
                for item in packet.state_dimensions
            ]
            if dimension_rows:
                self._executemany(
                    connection,
                    f"INSERT INTO {self.dimension_table}(packet_id,state_dimension_key,client_id,vault_id,namespace,"
                    f"resolution_status,state_dimension_hash,created_at,payload_json) VALUES({','.join([self.p]*9)})",
                    dimension_rows,
                )
            item_rows = []
            for layer in (
                "asserted_information", "derived_information", "tentative_information",
                "unknown_information", "conflicted_information",
            ):
                for item in getattr(packet, layer):
                    item_rows.append(
                        (
                            packet.packet_id,
                            item["event_id"],
                            layer,
                            *packet_scope(packet),
                            item["epistemic_status"],
                            item.get("temporal_phase"),
                            packet.created_at,
                            json_value(self.repository, item),
                        )
                    )
            if item_rows:
                self._executemany(
                    connection,
                    f"INSERT INTO {self.item_table}(packet_id,event_id,layer_name,client_id,vault_id,namespace,"
                    f"epistemic_status,temporal_phase,created_at,payload_json) VALUES({','.join([self.p]*10)})",
                    item_rows,
                )
            conflict_rows = [
                (
                    packet.packet_id,
                    item["conflict_id"],
                    *packet_scope(packet),
                    item["status"],
                    packet.created_at,
                    json_value(self.repository, item),
                )
                for item in packet.conflict_context
            ]
            if conflict_rows:
                self._executemany(
                    connection,
                    f"INSERT INTO {self.conflict_table}(packet_id,conflict_id,client_id,vault_id,namespace,"
                    f"conflict_status,created_at,payload_json) VALUES({','.join([self.p]*8)})",
                    conflict_rows,
                )
            entity_rows = [
                (
                    packet.packet_id,
                    item["canonical_entity_id"],
                    *packet_scope(packet),
                    item["entity_view_hash"],
                    packet.created_at,
                    json_value(self.repository, item),
                )
                for item in packet.entity_context
            ]
            if entity_rows:
                self._executemany(
                    connection,
                    f"INSERT INTO {self.entity_table}(packet_id,entity_id,client_id,vault_id,namespace,"
                    f"entity_view_hash,created_at,payload_json) VALUES({','.join([self.p]*8)})",
                    entity_rows,
                )
            relationship_rows = []
            for layer, values in packet.relationship_context.items():
                for item in values:
                    relationship_rows.append(
                        (
                            packet.packet_id,
                            item["relationship_id"],
                            layer,
                            *packet_scope(packet),
                            item["relationship_hash"],
                            packet.created_at,
                            json_value(self.repository, item),
                        )
                    )
            if relationship_rows:
                self._executemany(
                    connection,
                    f"INSERT INTO {self.relationship_table}(packet_id,relationship_id,layer_name,client_id,vault_id,namespace,"
                    f"relationship_hash,created_at,payload_json) VALUES({','.join([self.p]*9)})",
                    relationship_rows,
                )

    def _packet_by_id(self, packet_id: str) -> ContinuityPacketV2 | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.packet_table} WHERE packet_id={self.p}",
                (packet_id,),
            ).fetchone()
        return ContinuityPacketV2(**self._decode(row["payload_json"])) if row else None

    def _executemany(
        self, connection: Any, statement: str, rows: list[tuple[Any, ...]]
    ) -> None:
        if str(getattr(self.repository, "backend_name", "sqlite")) != "postgres":
            connection.executemany(statement, rows)
            return
        cursor = connection.cursor()
        try:
            cursor.executemany(statement, rows)
        finally:
            cursor.close()

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else json.loads(value)

    @staticmethod
    def _subject_scope(
        scope: AuthenticatedScope, subject: dict[str, str | None] | None
    ) -> dict[str, str | None]:
        requested = dict(subject or {})
        result = {
            "application_reference": requested.get("application_reference"),
            "actor_reference": requested.get("actor_reference"),
            "workspace_reference": requested.get("workspace_reference"),
            "entity_reference": requested.get("entity_reference") or requested.get("entity_id"),
            "session_reference": requested.get("session_reference"),
        }
        assertions = {
            "application_reference": scope.application_reference,
            "actor_reference": scope.actor_reference,
            "workspace_reference": scope.workspace_reference,
            "entity_reference": scope.entity_reference,
            "session_reference": scope.session_reference,
        }
        for key, value in assertions.items():
            if value and result[key] not in (None, value):
                raise ContinuityPacketV2Error("CONTINUITY_V2_SCOPE_DENIED", "Subject scope conflicts with authenticated scope.")
            if value:
                result[key] = value
        return result

    @staticmethod
    def _revisions() -> dict[str, str]:
        return {
            "schema": CONTINUITY_V2_SCHEMA_REVISION,
            "policy": CONTINUITY_V2_POLICY_REVISION,
            "state": CONTINUITY_V2_STATE_REVISION,
            "epistemic": CONTINUITY_V2_EPISTEMIC_REVISION,
            "temporal": CONTINUITY_V2_TEMPORAL_REVISION,
            "entity": CONTINUITY_V2_ENTITY_REVISION,
            "relationship": CONTINUITY_V2_RELATIONSHIP_REVISION,
            "provenance": CONTINUITY_V2_PROVENANCE_REVISION,
            "governance": CONTINUITY_V2_GOVERNANCE_REVISION,
            "comparison": CONTINUITY_V2_COMPARISON_REVISION,
            "integrity": CONTINUITY_V2_INTEGRITY_REVISION,
            "acceleration": CONTINUITY_V2_ACCELERATION_REVISION,
        }


def packet_scope(packet: ContinuityPacketV2) -> tuple[str, str, str]:
    return packet.client_id, packet.vault_id, packet.namespace


__all__ = [
    "ContinuityPacketV2Service",
    "POSTGRES_MIGRATION",
    "SQLITE_MIGRATION",
    "initialize_continuity_v2_schema",
]
