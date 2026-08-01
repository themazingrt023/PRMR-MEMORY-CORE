"""Bitemporal entity and relationship reconstruction with provenance."""

from __future__ import annotations

import json
from typing import Any

from .entity_memory import EntityMemoryService
from .entity_models import ENTITY_RESOLUTION_REVISION, EntityMemoryError
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    placeholder,
    scope_params,
    stable_id,
    table,
    utc,
    utc_now,
)
from .memory_ledger_models import MemoryTemporalBoundary
from .relationship_models import RELATIONSHIP_RESOLVER_REVISION
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


ENTITY_RELATIONSHIP_RECONSTRUCTION_REVISION = "entity_relationship_reconstruction_v1"


class EntityRelationshipReconstructionService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.memory = EntityMemoryService(repository, initialize=initialize)
        self.identity = self.memory.identity
        self.relationships = self.memory.relationships
        self.table = table(
            repository, "prmr_entity_relationship_reconstructions"
        )
        self.p = placeholder(repository)

    def reconstruct_entity_at_time(
        self, scope: AuthenticatedScope, entity_id: str, valid_at: str
    ) -> dict[str, Any]:
        return self.reconstruct_entity_bitemporal(
            scope, entity_id, valid_at=valid_at, known_at=None
        )

    def reconstruct_entity_as_known_at(
        self, scope: AuthenticatedScope, entity_id: str, known_at: str
    ) -> dict[str, Any]:
        return self.reconstruct_entity_bitemporal(
            scope, entity_id, valid_at=None, known_at=known_at
        )

    def reconstruct_entity_bitemporal(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        *,
        valid_at: str | None,
        known_at: str | None,
        persist: bool = True,
    ) -> dict[str, Any]:
        boundary = MemoryTemporalBoundary(
            valid_at=utc(valid_at), known_at=utc(known_at)
        )
        original = self.identity.resolver.get_entity(scope, entity_id)
        if original.first_valid_at > str(boundary.valid_at) or original.first_known_at > str(
            boundary.known_at
        ):
            raise EntityMemoryError(
                "ENTITY_NOT_FOUND", "Entity did not exist at the requested boundary."
            )
        canonical = self.identity.resolver.resolve_canonical_entity_id(
            scope, entity_id, known_at=boundary.known_at
        )
        entity = self.identity.resolver.get_entity(scope, canonical)
        aliases = self.identity.list_aliases(
            scope,
            canonical,
            valid_at=boundary.valid_at,
            known_at=boundary.known_at,
        )
        identifiers = self.memory._identifiers(
            scope, canonical, boundary.valid_at, boundary.known_at
        )
        mentions = [
            item.to_dict()
            for item in self.identity.candidates.get_mentions(scope)
            if item.entity_id
            and item.created_at <= str(boundary.known_at)
            and (
                item.occurred_at is None
                or item.occurred_at <= str(boundary.valid_at)
            )
            and self.identity.resolver.resolve_canonical_entity_id(
                scope, item.entity_id, known_at=boundary.known_at
            )
            == canonical
        ]
        links = [
            item.to_dict()
            for item in self.identity.list_event_links(
                scope,
                entity_id=canonical,
                valid_at=boundary.valid_at,
                known_at=boundary.known_at,
            )
        ]
        relationship_view = self.relationships.resolve_effective_relationships(
            scope, entity_id=canonical, temporal_boundary=boundary
        )
        source_ids = sorted(
            {entity.originating_source_id}
            | {item.source_id for item in aliases}
            | {item["source_id"] for item in links}
            | {
                item.originating_source_id
                for item in relationship_view.effective_relationships
            }
        )
        payload = {
            "requested_entity_id": entity_id,
            "canonical_entity_id": canonical,
            "entity": entity.to_dict(),
            "temporal_boundary": {
                "valid_at": boundary.valid_at,
                "known_at": boundary.known_at,
            },
            "effective_aliases": [item.to_dict() for item in aliases],
            "effective_identifiers": identifiers,
            "entity_mentions": mentions,
            "linked_events": links,
            "effective_relationships": [
                item.to_dict()
                for item in relationship_view.effective_relationships
            ],
            "open_conflicts": relationship_view.open_conflicts,
            "excluded_counts": relationship_view.excluded_counts,
            "provenance_references": [
                {"source_id": source_id} for source_id in source_ids
            ],
            "revision_identifiers": {
                "entity_resolution_revision": ENTITY_RESOLUTION_REVISION,
                "relationship_resolver_revision": RELATIONSHIP_RESOLVER_REVISION,
                "reconstruction_revision": (
                    ENTITY_RELATIONSHIP_RECONSTRUCTION_REVISION
                ),
            },
        }
        digest = sha256_text(canonical_json(payload))
        reconstruction_id = f"ercon_{digest[:24]}"
        result = {
            "reconstruction_id": reconstruction_id,
            "reconstruction_hash_sha256": digest,
            **payload,
        }
        if persist:
            self._persist(scope, result, source_ids)
        return result

    def reconstruct_relationships_at_time(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        *,
        valid_at: str | None = None,
        known_at: str | None = None,
    ) -> dict[str, Any]:
        reconstruction = self.reconstruct_entity_bitemporal(
            scope,
            entity_id,
            valid_at=valid_at,
            known_at=known_at,
        )
        return {
            "reconstruction_id": reconstruction["reconstruction_id"],
            "reconstruction_hash_sha256": reconstruction[
                "reconstruction_hash_sha256"
            ],
            "canonical_entity_id": reconstruction["canonical_entity_id"],
            "temporal_boundary": reconstruction["temporal_boundary"],
            "effective_relationships": reconstruction[
                "effective_relationships"
            ],
            "open_conflicts": reconstruction["open_conflicts"],
            "excluded_counts": reconstruction["excluded_counts"],
            "provenance_references": reconstruction[
                "provenance_references"
            ],
            "revision_identifiers": reconstruction["revision_identifiers"],
        }

    def compare_entity_views(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        first_boundary: MemoryTemporalBoundary,
        second_boundary: MemoryTemporalBoundary,
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        first = self.reconstruct_entity_bitemporal(
            scope,
            entity_id,
            valid_at=first_boundary.valid_at,
            known_at=first_boundary.known_at,
            persist=persist,
        )
        second = self.reconstruct_entity_bitemporal(
            scope,
            entity_id,
            valid_at=second_boundary.valid_at,
            known_at=second_boundary.known_at,
            persist=persist,
        )
        first_aliases = {
            item["alias_assertion_id"] for item in first["effective_aliases"]
        }
        second_aliases = {
            item["alias_assertion_id"] for item in second["effective_aliases"]
        }
        return {
            "first_reconstruction_id": first["reconstruction_id"],
            "second_reconstruction_id": second["reconstruction_id"],
            "canonical_identity_changed": (
                first["canonical_entity_id"] != second["canonical_entity_id"]
            ),
            "aliases_added": sorted(second_aliases - first_aliases),
            "aliases_removed": sorted(first_aliases - second_aliases),
            "changed": (
                first["reconstruction_hash_sha256"]
                != second["reconstruction_hash_sha256"]
            ),
            "reconstruction_revision": (
                ENTITY_RELATIONSHIP_RECONSTRUCTION_REVISION
            ),
        }

    def compare_relationship_views(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        first_boundary: MemoryTemporalBoundary,
        second_boundary: MemoryTemporalBoundary,
    ) -> dict[str, Any]:
        return self.relationships.compare_relationship_views(
            scope,
            first_boundary,
            second_boundary,
            entity_id=entity_id,
        )

    def trace_entity_origin(
        self, scope: AuthenticatedScope, entity_id: str
    ) -> dict[str, Any]:
        entity = self.identity.resolver.get_entity(scope, entity_id)
        candidate = self.identity.candidates.get_candidate(
            scope, entity.originating_entity_candidate_id
        )
        evidence = self.identity.candidates.get_evidence(
            scope, candidate.entity_candidate_id
        )
        source = self.identity.candidates.ledger.get_source(
            scope, candidate.source_id
        )
        return {
            "entity_id": entity.entity_id,
            "entity_admission_id": entity.originating_admission_id,
            "entity_candidate_id": candidate.entity_candidate_id,
            "entity_evidence": [
                {
                    "entity_evidence_id": item.entity_evidence_id,
                    "source_id": item.source_id,
                    "segment_id": item.segment_id,
                    "evidence_role": item.evidence_role,
                }
                for item in evidence
            ],
            "source": {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "content_hash_sha256": source.content_hash_sha256,
                "segment_manifest_hash_sha256": (
                    source.segment_manifest_hash_sha256
                ),
            },
            "source_content_exposed": False,
        }

    def trace_relationship_origin(
        self, scope: AuthenticatedScope, relationship_id: str
    ) -> dict[str, Any]:
        relationship = self.relationships.admission.get_relationship(
            scope, relationship_id
        )
        candidate = self.relationships.admission.candidates.get_candidate(
            scope, relationship.originating_relationship_candidate_id
        )
        evidence = self.relationships.admission.candidates.get_evidence(
            scope, candidate.relationship_candidate_id
        )
        return {
            "relationship_id": relationship.relationship_id,
            "relationship_admission_id": (
                relationship.originating_admission_id
            ),
            "relationship_candidate_id": candidate.relationship_candidate_id,
            "relationship_evidence": [
                {
                    "relationship_evidence_id": item.relationship_evidence_id,
                    "source_id": item.source_id,
                    "segment_id": item.segment_id,
                    "evidence_role": item.evidence_role,
                }
                for item in evidence
            ],
            "subject_entity_origin": self.trace_entity_origin(
                scope, relationship.subject_entity_id
            ),
            "object_entity_origin": self.trace_entity_origin(
                scope, relationship.object_entity_id
            ),
            "source_content_exposed": False,
        }

    def _persist(
        self,
        scope: AuthenticatedScope,
        reconstruction: dict[str, Any],
        source_ids: list[str],
    ) -> None:
        with self.repository.connect() as connection:
            existing = connection.execute(
                f"SELECT reconstruction_id FROM {self.table} "
                f"WHERE reconstruction_id={self.p}",
                (reconstruction["reconstruction_id"],),
            ).fetchone()
            if existing:
                return
            connection.execute(
                f"INSERT INTO {self.table}("
                "reconstruction_id,entity_id,client_id,vault_id,namespace,valid_at,"
                "known_at,reconstruction_hash_sha256,source_ids_json,created_at,"
                "payload_json) VALUES(" + ",".join([self.p] * 11) + ")",
                (
                    reconstruction["reconstruction_id"],
                    reconstruction["canonical_entity_id"],
                    *scope_params(scope),
                    reconstruction["temporal_boundary"]["valid_at"],
                    reconstruction["temporal_boundary"]["known_at"],
                    reconstruction["reconstruction_hash_sha256"],
                    json_value(self.repository, source_ids),
                    utc_now(),
                    json_value(self.repository, reconstruction),
                ),
            )


__all__ = [
    "ENTITY_RELATIONSHIP_RECONSTRUCTION_REVISION",
    "EntityRelationshipReconstructionService",
]
