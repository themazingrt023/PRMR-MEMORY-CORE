"""Independent integrity verification for entity identity memory."""

from __future__ import annotations

import json
from typing import Any

from .entity_admission import EntityAdmissionService
from .entity_identity_service import EntityIdentityService
from .entity_memory import EntityMemoryService
from .entity_models import ENTITY_IDENTITY_REVISION
from .entity_store import payload_from_row, scope_params
from .entity_store import utc_now
from .memory_ledger_models import MemoryTemporalBoundary
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


ENTITY_INTEGRITY_REVISION = "entity_integrity_v1"


class EntityIntegrityVerifier:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.admission = EntityAdmissionService(
            repository, initialize=initialize
        )
        self.identity = EntityIdentityService(
            repository, initialize=initialize
        )
        self.memory = EntityMemoryService(repository, initialize=initialize)

    def verify_entity_integrity(
        self, scope: AuthenticatedScope, entity_id: str
    ) -> dict[str, Any]:
        failures: list[str] = []
        checks: dict[str, bool] = {}
        entity = self.identity.resolver.get_entity(scope, entity_id)
        candidate = self.admission.candidates.get_candidate(
            scope, entity.originating_entity_candidate_id
        )
        evidence = self.admission.candidates.get_evidence(
            scope, candidate.entity_candidate_id
        )
        checks["candidate_has_primary_evidence"] = bool(evidence) and any(
            item.evidence_role == "primary" for item in evidence
        )
        source_integrity = self.admission.candidates.ledger.verify_source_integrity(
            scope, candidate.source_id
        )
        checks["source_integrity"] = source_integrity.verified
        candidate_identity = {
            "scope": scope.memory_boundary(),
            "source_id": candidate.source_id,
            "entity_type": candidate.proposed_entity_type,
            "label": candidate.normalisation_details.get("normalised_label", ""),
            "identifiers": candidate.proposed_external_identifiers,
            "aliases": sorted(
                " ".join(alias.strip().lower().split())
                for alias in candidate.proposed_aliases
            ),
            "rule": candidate.primary_rule_id,
            "json_pointer": evidence[0].json_pointer if evidence else None,
            "revision": candidate.entity_candidate_revision,
        }
        checks["candidate_fingerprint_reproduces"] = (
            sha256_text(canonical_json(candidate_identity))
            == candidate.entity_candidate_fingerprint_sha256
        )
        identifiers = self._identifier_payloads(scope, entity.entity_id)
        if identifiers:
            primary = sorted(
                identifiers,
                key=lambda item: (
                    item["identifier_namespace"],
                    item["identifier_value_digest"],
                ),
            )[0]
            entity_identity = {
                "scope": scope.memory_boundary(),
                "entity_type": entity.canonical_entity_type,
                "identifier_namespace": primary["identifier_namespace"],
                "identifier_digest": primary["identifier_value_digest"],
                "revision": ENTITY_IDENTITY_REVISION,
            }
        else:
            entity_identity = {
                "scope": scope.memory_boundary(),
                "source_id": candidate.source_id,
                "evidence_ids": sorted(
                    item.entity_evidence_id for item in evidence
                ),
                "entity_type": candidate.proposed_entity_type,
                "decision_id": entity.originating_admission_id,
                "revision": ENTITY_IDENTITY_REVISION,
            }
        checks["identity_fingerprint_reproduces"] = (
            sha256_text(canonical_json(entity_identity))
            == entity.identity_fingerprint_sha256
        )
        checks["identifiers_scope_match"] = all(
            (
                item["client_id"],
                item["vault_id"],
                item["namespace"],
            )
            == scope.memory_boundary()
            for item in identifiers
        )
        aliases = self.identity.list_aliases(
            scope, entity.entity_id, include_inactive=True
        )
        checks["aliases_have_provenance"] = all(
            item.source_id
            and item.evidence_manifest_hash_sha256
            and item.alias_hash_sha256 == sha256_text(item.alias_normalised)
            for item in aliases
        )
        mentions = [
            item
            for item in self.admission.candidates.get_mentions(scope)
            if item.entity_candidate_id == candidate.entity_candidate_id
        ]
        checks["mentions_valid"] = all(
            item.entity_id is None
            or self.identity.resolver.get_entity(scope, item.entity_id)
            for item in mentions
        )
        links = self.identity.list_event_links(
            scope, entity_id=entity.entity_id, current_only=False
        )
        checks["event_links_scoped"] = all(
            self.identity.admission.get_admitted_event(scope, item.event_id)
            and self.identity.resolver.get_entity(scope, item.entity_id)
            for item in links
        )
        try:
            self.identity.resolver.resolve_canonical_entity_id(
                scope, entity.entity_id
            )
            checks["merge_graph_acyclic"] = True
        except Exception:
            checks["merge_graph_acyclic"] = False
        failures.extend(name for name, passed in checks.items() if not passed)
        return {
            "entity_id": entity.entity_id,
            "verified": not failures,
            "checks": checks,
            "failures": failures,
            "entity_integrity_revision": ENTITY_INTEGRITY_REVISION,
        }

    def verify_entity_packet(
        self, scope: AuthenticatedScope, entity_id: str
    ) -> dict[str, Any]:
        captured = utc_now()
        boundary = MemoryTemporalBoundary(valid_at=captured, known_at=captured)
        first = self.memory.generate_entity_continuity(
            scope, entity_id, boundary
        )
        second = self.memory.generate_entity_continuity(
            scope, entity_id, boundary
        )
        checks = {
            "packet_id_reproduces": first["packet_id"] == second["packet_id"],
            "packet_hash_reproduces": (
                first["provenance"]["deterministic_packet_hash"]
                == second["provenance"]["deterministic_packet_hash"]
            ),
            "entity_context_scoped": (
                first["entity_memory_context"]["canonical_entity_id"]
                == self.identity.resolver.resolve_canonical_entity_id(
                    scope, entity_id
                )
            ),
            "raw_credentials_absent": not any(
                token in canonical_json(first).lower()
                for token in ("authorization", "api_key", "bearer ")
            ),
        }
        return {
            "verified": all(checks.values()),
            "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
            "packet_id": first["packet_id"],
            "packet_hash": first["provenance"]["deterministic_packet_hash"],
            "entity_integrity_revision": ENTITY_INTEGRITY_REVISION,
        }

    def verify_entity_relationship_graph_integrity(
        self, scope: AuthenticatedScope
    ) -> dict[str, Any]:
        entity_results = [
            self.verify_entity_integrity(scope, entity.entity_id)
            for entity in self.identity.resolver.list_entities(
                scope, include_inactive=True
            )
        ]
        cross_scope_count = self._cross_scope_reference_count()
        checks = {
            "entities_verify": all(item["verified"] for item in entity_results),
            "no_cross_scope_references": cross_scope_count == 0,
        }
        return {
            "verified": all(checks.values()),
            "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
            "entity_count": len(entity_results),
            "cross_scope_reference_count": cross_scope_count,
            "entity_integrity_revision": ENTITY_INTEGRITY_REVISION,
        }

    def _identifier_payloads(
        self, scope: AuthenticatedScope, entity_id: str
    ) -> list[dict[str, Any]]:
        p = self.identity.p
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT client_id,vault_id,namespace,payload_json "
                f"FROM {self.identity.identifier_table} "
                f"WHERE client_id={p} AND vault_id={p} AND namespace={p} "
                f"AND entity_id={p}",
                (*scope_params(scope), entity_id),
            ).fetchall()
        output = []
        for row in rows:
            payload = payload_from_row(row)
            payload.update(
                {
                    "client_id": row["client_id"],
                    "vault_id": row["vault_id"],
                    "namespace": row["namespace"],
                }
            )
            output.append(payload)
        return output

    def _cross_scope_reference_count(self) -> int:
        p = self.identity.p
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT l.client_id AS lc,l.vault_id AS lv,l.namespace AS ln,"
                f"e.client_id AS ec,e.vault_id AS ev,e.namespace AS en "
                f"FROM {self.identity.link_table} l "
                f"JOIN {self.identity.entity_table} e ON e.entity_id=l.entity_id"
            ).fetchall()
        return sum(
            (row["lc"], row["lv"], row["ln"])
            != (row["ec"], row["ev"], row["en"])
            for row in rows
        )


__all__ = ["ENTITY_INTEGRITY_REVISION", "EntityIntegrityVerifier"]
