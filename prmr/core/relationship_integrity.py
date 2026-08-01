"""Independent integrity verification for relationship memory."""

from __future__ import annotations

from typing import Any

from .entity_integrity import EntityIntegrityVerifier
from .entity_store import payload_from_row, utc_now
from .memory_ledger_models import MemoryTemporalBoundary
from .relationship_memory import RelationshipMemoryService
from .relationship_models import (
    RELATIONSHIP_MEMORY_SCHEMA_REVISION,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


RELATIONSHIP_INTEGRITY_REVISION = "relationship_integrity_v1"


class RelationshipIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.memory = RelationshipMemoryService(
            repository, initialize=initialize
        )
        self.entities = EntityIntegrityVerifier(
            repository, initialize=initialize
        )

    def verify_relationship_integrity(
        self, scope: AuthenticatedScope, relationship_id: str
    ) -> dict[str, Any]:
        relationship = self.memory.admission.get_relationship(
            scope, relationship_id
        )
        candidate = self.memory.admission.candidates.get_candidate(
            scope, relationship.originating_relationship_candidate_id
        )
        evidence = self.memory.admission.candidates.get_evidence(
            scope, candidate.relationship_candidate_id
        )
        checks: dict[str, bool] = {
            "candidate_has_primary_evidence": bool(evidence)
            and any(item.evidence_role == "primary" for item in evidence),
            "source_integrity": (
                self.memory.admission.candidates.ledger.verify_source_integrity(
                    scope, candidate.source_id
                ).verified
            ),
        }
        subject = self.memory.entities.get_entity(
            scope, relationship.subject_entity_id
        )
        object_ = self.memory.entities.get_entity(
            scope, relationship.object_entity_id
        )
        checks["endpoint_scope_matches"] = (
            (
                subject.client_id,
                subject.vault_id,
                subject.namespace,
            )
            == scope.memory_boundary()
            and (
                object_.client_id,
                object_.vault_id,
                object_.namespace,
            )
            == scope.memory_boundary()
        )
        expected = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "subject": relationship.subject_entity_id,
                    "relationship_type": relationship.relationship_type,
                    "object": relationship.object_entity_id,
                    "valid_from": relationship.valid_from,
                    "candidate_fingerprint": (
                        candidate.relationship_candidate_fingerprint_sha256
                    ),
                    "revision": RELATIONSHIP_MEMORY_SCHEMA_REVISION,
                }
            )
        )
        checks["relationship_fingerprint_reproduces"] = (
            expected == relationship.relationship_fingerprint_sha256
        )
        try:
            self.memory._reject_supersession_cycle(
                scope, relationship.relationship_id, "__terminal__"
            )
            checks["evolution_graph_acyclic"] = True
        except Exception:
            checks["evolution_graph_acyclic"] = False
        captured = utc_now()
        boundary = MemoryTemporalBoundary(valid_at=captured, known_at=captured)
        view_a = self.memory.resolve_effective_relationships(
            scope, temporal_boundary=boundary
        )
        view_b = self.memory.resolve_effective_relationships(
            scope, temporal_boundary=boundary
        )
        checks["relationship_resolution_reproduces"] = (
            view_a.deterministic_relationship_manifest
            == view_b.deterministic_relationship_manifest
        )
        failures = [name for name, passed in checks.items() if not passed]
        return {
            "relationship_id": relationship.relationship_id,
            "verified": not failures,
            "checks": checks,
            "failures": failures,
            "relationship_integrity_revision": RELATIONSHIP_INTEGRITY_REVISION,
        }

    def verify_entity_relationship_graph_integrity(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        entity = self.entities.verify_entity_relationship_graph_integrity(scope)
        relationship_results = [
            self.verify_relationship_integrity(scope, item.relationship_id)
            for item in self.memory.admission.list_relationships(scope)
        ]
        cross_scope = self._cross_scope_relationship_count()
        checks = {
            "entity_graph_integrity": entity["verified"],
            "relationships_verify": all(
                item["verified"] for item in relationship_results
            ),
            "no_cross_scope_relationships": cross_scope == 0,
        }
        return {
            "verified": all(checks.values()),
            "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
            "relationship_count": len(relationship_results),
            "relationship_results": relationship_results,
            "cross_scope_relationship_count": cross_scope,
            "relationship_integrity_revision": RELATIONSHIP_INTEGRITY_REVISION,
        }

    def _cross_scope_relationship_count(self) -> int:
        table = self.memory.relationship_table
        entity_table = self.memory.entities.entity_table
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT r.client_id AS rc,r.vault_id AS rv,r.namespace AS rn,"
                f"s.client_id AS sc,s.vault_id AS sv,s.namespace AS sn,"
                f"o.client_id AS oc,o.vault_id AS ov,o.namespace AS onn "
                f"FROM {table} r "
                f"JOIN {entity_table} s ON s.entity_id=r.subject_entity_id "
                f"JOIN {entity_table} o ON o.entity_id=r.object_entity_id"
            ).fetchall()
        return sum(
            (row["rc"], row["rv"], row["rn"])
            != (row["sc"], row["sv"], row["sn"])
            or (row["rc"], row["rv"], row["rn"])
            != (row["oc"], row["ov"], row["onn"])
            for row in rows
        )


__all__ = [
    "RELATIONSHIP_INTEGRITY_REVISION",
    "RelationshipIntegrityVerifier",
]
