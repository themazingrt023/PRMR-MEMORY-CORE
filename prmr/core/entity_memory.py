"""Entity-scoped continuity using linked admitted events and Sprint 5 dynamics."""

from __future__ import annotations

import json
import logging
from typing import Any

from .entity_identity_service import EntityIdentityService
from .entity_models import (
    ENTITY_CONTINUITY_ADAPTER_REVISION,
    ENTITY_IDENTITY_REVISION,
    EVENT_ENTITY_LINK_REVISION,
    EntityMemoryError,
    EntityMemoryView,
)
from .entity_store import (
    initialize_entity_relationship_schema,
    scope_fingerprint,
    utc,
)
from .memory_dynamics_engine import MemoryDynamicsEngine
from .memory_ledger_models import MemoryTemporalBoundary
from .relationship_memory import RelationshipMemoryService
from .relationship_models import RELATIONSHIP_RESOLVER_REVISION
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.entity_memory")


class EntityMemoryService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.identity = EntityIdentityService(repository, initialize=initialize)
        self.relationships = RelationshipMemoryService(
            repository, initialize=initialize
        )
        self.dynamics = MemoryDynamicsEngine(repository, initialize=initialize)

    def generate_entity_continuity(
        self,
        authenticated_scope: AuthenticatedScope,
        entity_id: str,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        dynamics_mode: str = "temporal_memory_v1",
        *,
        persist_dynamics: bool = True,
    ) -> dict[str, Any]:
        boundary = temporal_boundary or MemoryTemporalBoundary()
        canonical = self.identity.resolver.resolve_canonical_entity_id(
            authenticated_scope,
            entity_id,
            known_at=boundary.known_at,
        )
        entity = self.identity.resolver.get_entity(
            authenticated_scope, canonical
        )
        links = self.identity.list_event_links(
            authenticated_scope,
            entity_id=canonical,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
        )
        event_ids = frozenset(link.event_id for link in links)
        packet = self.dynamics.build_continuity_packet(
            authenticated_scope,
            temporal_boundary=boundary,
            dynamics_mode=dynamics_mode,
            event_ids=event_ids,
            persist_dynamics=persist_dynamics,
        )
        relationship_view = self.relationships.resolve_effective_relationships(
            authenticated_scope,
            entity_id=canonical,
            temporal_boundary=boundary,
            include_conflicted=True,
        )
        aliases = self.identity.list_aliases(
            authenticated_scope,
            canonical,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
        )
        context = {
            "entity_id": entity_id,
            "canonical_entity_id": canonical,
            "entity_type": entity.canonical_entity_type,
            "active_alias_count": len(aliases),
            "linked_event_count": len(event_ids),
            "relationship_count": len(
                relationship_view.effective_relationships
            ),
            "open_relationship_conflict_count": len(
                relationship_view.open_conflicts
            ),
            "entity_identity_revision": ENTITY_IDENTITY_REVISION,
            "event_entity_link_revision": EVENT_ENTITY_LINK_REVISION,
            "relationship_resolver_revision": RELATIONSHIP_RESOLVER_REVISION,
            "entity_continuity_adapter_revision": (
                ENTITY_CONTINUITY_ADAPTER_REVISION
            ),
        }
        relationship_context = [
            {
                "relationship_id": item.relationship_id,
                "subject_entity_id": item.subject_entity_id,
                "relationship_type": item.relationship_type,
                "object_entity_id": item.object_entity_id,
                "relationship_status": item.relationship_status,
                "epistemic_status": item.epistemic_status,
                "valid_from": item.valid_from,
            }
            for item in relationship_view.effective_relationships
        ]
        packet["base_continuity_packet_id"] = packet["packet_id"]
        packet["entity_memory_context"] = context
        packet["relationship_context"] = relationship_context
        packet["relationship_context_manifest"] = (
            relationship_view.deterministic_relationship_manifest
        )
        identity = {
            "base_packet_hash": packet["provenance"]["deterministic_packet_hash"],
            "entity_memory_context": context,
            "relationship_context": relationship_context,
            "temporal_boundary": relationship_view.temporal_boundary,
        }
        digest = sha256_text(canonical_json(identity))
        packet["packet_id"] = f"epacket_{digest[:32]}"
        packet["provenance"]["deterministic_packet_hash"] = digest
        packet["provenance"]["entity_scoped"] = True
        packet["provenance"]["linked_event_ids"] = sorted(event_ids)
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "entity_continuity_generated",
                    "entity_id": canonical,
                    "linked_event_count": len(event_ids),
                    "relationship_count": len(relationship_context),
                    "revision": ENTITY_CONTINUITY_ADAPTER_REVISION,
                    "scope_fingerprint": scope_fingerprint(authenticated_scope),
                },
                sort_keys=True,
            ),
        )
        return packet

    def build_entity_memory_view(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        temporal_boundary: MemoryTemporalBoundary | None = None,
        *,
        persist_dynamics: bool = True,
    ) -> EntityMemoryView:
        boundary = temporal_boundary or MemoryTemporalBoundary()
        packet = self.generate_entity_continuity(
            scope,
            entity_id,
            boundary,
            persist_dynamics=persist_dynamics,
        )
        canonical = packet["entity_memory_context"]["canonical_entity_id"]
        entity = self.identity.resolver.get_entity(scope, canonical)
        aliases = self.identity.list_aliases(
            scope,
            canonical,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
        )
        identifiers = self._identifiers(
            scope, canonical, boundary.valid_at, boundary.known_at
        )
        mentions = [
            item
            for item in self.identity.candidates.get_mentions(scope)
            if item.entity_id
            and self.identity.resolver.resolve_canonical_entity_id(
                scope, item.entity_id, known_at=boundary.known_at
            )
            == canonical
        ]
        links = self.identity.list_event_links(
            scope,
            entity_id=canonical,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
        )
        relationships = self.relationships.resolve_effective_relationships(
            scope, entity_id=canonical, temporal_boundary=boundary
        )
        source_ids = sorted(
            {entity.originating_source_id}
            | {item.source_id for item in aliases}
            | {item.source_id for item in links}
        )
        related_ids = sorted(
            {
                endpoint
                for item in relationships.effective_relationships
                for endpoint in (item.subject_entity_id, item.object_entity_id)
                if endpoint != canonical
            }
        )
        last_seen = max(
            [item.occurred_at or item.created_at for item in mentions]
            + [item.valid_from for item in links],
            default=None,
        )
        data = {
            "entity_id": entity_id,
            "canonical_entity_id": canonical,
            "canonical_label": entity.canonical_label,
            "canonical_type": entity.canonical_entity_type,
            "aliases": sorted(item.alias_value for item in aliases),
            "stable_identifiers": identifiers,
            "first_seen": entity.first_valid_at,
            "last_seen": last_seen,
            "source_count": len(source_ids),
            "mention_count": len(mentions),
            "linked_event_count": len(links),
            "active_relationship_count": len(
                relationships.effective_relationships
            ),
            "open_relationship_conflict_count": len(
                relationships.open_conflicts
            ),
            "current_event_state_summary": {
                "current_state_event_id": packet.get("current_state_event_id"),
                "current_state_signal": packet.get("current_state_signal"),
                "source_event_count": packet.get("source_event_count", 0),
            },
            "temporal_memory_summary": {
                "memory_dynamics_mode": packet.get("memory_dynamics_mode"),
                "temporal_horizon_summary": packet.get(
                    "temporal_horizon_summary", {}
                ),
                "temporal_quality": packet.get("temporal_quality", {}),
            },
            "related_entity_ids": related_ids,
            "entity_identity_revisions": [
                entity.entity_identity_revision,
                entity.entity_resolution_revision,
            ],
            "reconstruction_boundary": {
                "valid_at": boundary.valid_at,
                "known_at": boundary.known_at,
            },
            "provenance_references": [
                {"source_id": source_id} for source_id in source_ids
            ],
        }
        digest = sha256_text(canonical_json(data))
        return EntityMemoryView(
            **data, deterministic_view_hash=digest
        )

    def _identifiers(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        valid_at: str | None,
        known_at: str | None,
    ) -> list[dict[str, str | None]]:
        valid, known = utc(valid_at), utc(known_at)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.identity.identifier_table} "
                f"WHERE client_id={self.identity.p} AND vault_id={self.identity.p} "
                f"AND namespace={self.identity.p} AND entity_id={self.identity.p} "
                "ORDER BY created_at,entity_identifier_id",
                (*scope.memory_boundary(), entity_id),
            ).fetchall()
        output = []
        for row in rows:
            raw = row["payload_json"]
            item = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
            if (
                item["identifier_status"] == "active"
                and item["valid_from"] <= valid
                and item["system_known_from"] <= known
                and (not item.get("valid_until") or item["valid_until"] > valid)
                and (
                    not item.get("system_known_until")
                    or item["system_known_until"] > known
                )
            ):
                output.append(
                    {
                        "identifier_namespace": item["identifier_namespace"],
                        "identifier_display_hint": item.get(
                            "identifier_display_hint"
                        ),
                        "identifier_type": item["identifier_type"],
                        "identifier_value_digest": item[
                            "identifier_value_digest"
                        ],
                    }
                )
        return output


__all__ = ["EntityMemoryService"]
