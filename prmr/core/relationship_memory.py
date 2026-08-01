"""Append-oriented relationship evolution, projection and reconstruction."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
from typing import Any

from .admission_models import AdmissionDecisionActor
from .entity_resolution import EntityResolver
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    payload_from_row,
    placeholder,
    scope_fingerprint,
    scope_params,
    table,
    utc,
    utc_now,
)
from .relationship_admission import RelationshipAdmissionService
from .relationship_models import (
    RELATIONSHIP_EVOLUTION_REVISION,
    RELATIONSHIP_RESOLVER_REVISION,
    RelationshipEvolutionRecord,
    RelationshipMemoryError,
    RelationshipRecord,
    ResolvedRelationshipView,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.relationship_memory")


class RelationshipMemoryService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.admission = RelationshipAdmissionService(
            repository, initialize=initialize
        )
        self.entities = EntityResolver(repository, initialize=False)
        self.relationship_table = table(repository, "prmr_relationships")
        self.evolution_table = table(
            repository, "prmr_relationship_evolution_records"
        )
        self.conflict_table = table(repository, "prmr_relationship_conflicts")
        self.p = placeholder(repository)

    def supersede_relationship(
        self,
        scope: AuthenticatedScope,
        source_relationship_id: str,
        replacement_relationship_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> RelationshipEvolutionRecord:
        if source_relationship_id == replacement_relationship_id:
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVOLUTION_INVALID",
                "Relationship cannot supersede itself.",
            )
        source = self.admission.get_relationship(scope, source_relationship_id)
        replacement = self.admission.get_relationship(
            scope, replacement_relationship_id
        )
        self._reject_supersession_cycle(
            scope, source.relationship_id, replacement.relationship_id
        )
        return self._evolve(
            scope,
            "supersede",
            source,
            actor,
            reason,
            replacement_relationship_id=replacement.relationship_id,
            valid_from=valid_from or replacement.valid_from,
            system_effective_at=system_effective_at,
            idempotency_key=idempotency_key,
        )

    def retract_relationship(
        self,
        scope: AuthenticatedScope,
        relationship_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> RelationshipEvolutionRecord:
        source = self.admission.get_relationship(scope, relationship_id)
        return self._evolve(
            scope,
            "retract",
            source,
            actor,
            reason,
            valid_from=valid_from,
            system_effective_at=system_effective_at,
            idempotency_key=idempotency_key,
        )

    def invalidate_relationship(
        self,
        scope: AuthenticatedScope,
        relationship_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> RelationshipEvolutionRecord:
        source = self.admission.get_relationship(scope, relationship_id)
        return self._evolve(
            scope,
            "invalidate",
            source,
            actor,
            reason,
            valid_from=valid_from,
            system_effective_at=system_effective_at,
            idempotency_key=idempotency_key,
        )

    def declare_contradiction(
        self,
        scope: AuthenticatedScope,
        relationship_ids: list[str],
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        conflict_type: str = "exclusive_relationship_claim",
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        actor.validate()
        unique = sorted(set(relationship_ids))
        if len(unique) < 2:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CONFLICT_INVALID",
                "At least two relationships are required for contradiction.",
            )
        relationships = [
            self.admission.get_relationship(scope, relationship_id)
            for relationship_id in unique
        ]
        effective = utc(system_effective_at)
        valid = utc(
            valid_from,
            default=max(item.valid_from for item in relationships),
        )
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "relationships": unique,
                    "conflict_type": conflict_type,
                    "key": idempotency_key or "",
                    "revision": RELATIONSHIP_EVOLUTION_REVISION,
                }
            )
        )
        conflict_id = f"rconf_{idem[:24]}"
        with self.repository.connect() as connection:
            existing = connection.execute(
                f"SELECT * FROM {self.conflict_table} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND conflict_id={self.p}",
                (*scope_params(scope), conflict_id),
            ).fetchone()
            if existing:
                return self._conflict_from_row(existing)
            connection.execute(
                f"INSERT INTO {self.conflict_table}("
                "conflict_id,client_id,vault_id,namespace,relationship_ids_json,"
                "conflict_type,conflict_status,valid_from,system_effective_at,"
                "resolution_relationship_id,resolved_at,reason,created_at) VALUES("
                + ",".join([self.p] * 13)
                + ")",
                (
                    conflict_id,
                    *scope_params(scope),
                    json_value(self.repository, unique),
                    conflict_type,
                    "open",
                    valid,
                    effective,
                    None,
                    None,
                    reason,
                    utc_now(),
                ),
            )
        evolutions = [
            self._evolve(
                scope,
                "declare_contradiction",
                relationship,
                actor,
                reason,
                conflict_id=conflict_id,
                valid_from=valid,
                system_effective_at=effective,
                idempotency_key=f"{idem}:{relationship.relationship_id}",
            )
            for relationship in relationships
        ]
        self._log(
            "relationship_conflict_declared",
            scope,
            conflict_id=conflict_id,
            count=len(unique),
            status="open",
        )
        return {
            "conflict_id": conflict_id,
            "relationship_ids": unique,
            "conflict_type": conflict_type,
            "conflict_status": "open",
            "valid_from": valid,
            "system_effective_at": effective,
            "resolution_relationship_id": None,
            "resolved_at": None,
            "reason": reason,
            "evolution_ids": [
                item.relationship_evolution_id for item in evolutions
            ],
            "winner_selected_automatically": False,
        }

    def resolve_contradiction(
        self,
        scope: AuthenticatedScope,
        conflict_id: str,
        resolution_relationship_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        actor.validate()
        conflict = self.get_conflict(scope, conflict_id)
        if conflict["conflict_status"] == "resolved":
            return conflict
        if resolution_relationship_id not in conflict["relationship_ids"]:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CONFLICT_INVALID",
                "Resolution relationship is not part of the conflict.",
            )
        relationship = self.admission.get_relationship(
            scope, resolution_relationship_id
        )
        effective = utc(system_effective_at)
        valid = utc(valid_from, default=effective)
        evolution = self._evolve(
            scope,
            "resolve_contradiction",
            relationship,
            actor,
            reason,
            conflict_id=conflict_id,
            resolution_relationship_id=resolution_relationship_id,
            valid_from=valid,
            system_effective_at=effective,
            idempotency_key=idempotency_key,
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.conflict_table} SET conflict_status={self.p},"
                f"resolution_relationship_id={self.p},resolved_at={self.p},reason={self.p} "
                f"WHERE conflict_id={self.p}",
                (
                    "resolved",
                    resolution_relationship_id,
                    effective,
                    reason,
                    conflict_id,
                ),
            )
        self._log(
            "relationship_conflict_resolved",
            scope,
            conflict_id=conflict_id,
            status="resolved",
        )
        return {
            **conflict,
            "conflict_status": "resolved",
            "resolution_relationship_id": resolution_relationship_id,
            "resolved_at": effective,
            "reason": reason,
            "relationship_evolution_id": evolution.relationship_evolution_id,
        }

    def get_conflict(
        self, scope: AuthenticatedScope, conflict_id: str
    ) -> dict[str, Any]:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.conflict_table} WHERE conflict_id={self.p} "
                f"AND client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                (conflict_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise RelationshipMemoryError(
                "RELATIONSHIP_CONFLICT_INVALID",
                "Relationship conflict was not found in scope.",
            )
        return self._conflict_from_row(row)

    def list_evolutions(
        self, scope: AuthenticatedScope
    ) -> list[RelationshipEvolutionRecord]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.evolution_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                "ORDER BY system_effective_at,relationship_evolution_id",
                scope_params(scope),
            ).fetchall()
        return [RelationshipEvolutionRecord(**payload_from_row(row)) for row in rows]

    def resolve_effective_relationships(
        self,
        scope: AuthenticatedScope,
        subject_scope: dict[str, Any] | None = None,
        entity_id: str | None = None,
        temporal_boundary: Any | None = None,
        relationship_type: str | None = None,
        include_conflicted: bool = True,
    ) -> ResolvedRelationshipView:
        valid_at = utc(
            getattr(temporal_boundary, "valid_at", None)
            if temporal_boundary is not None
            else None
        )
        known_at = utc(
            getattr(temporal_boundary, "known_at", None)
            if temporal_boundary is not None
            else None
        )
        if isinstance(temporal_boundary, dict):
            valid_at = utc(temporal_boundary.get("valid_at"))
            known_at = utc(temporal_boundary.get("known_at"))
        relationships = self.admission.list_relationships(scope)
        evolutions = [
            item
            for item in self.list_evolutions(scope)
            if item.system_effective_at <= known_at and item.valid_from <= valid_at
        ]
        conflicts = self._conflicts_as_known(scope, valid_at, known_at)
        by_source: dict[str, list[RelationshipEvolutionRecord]] = {}
        for evolution in evolutions:
            by_source.setdefault(evolution.source_relationship_id, []).append(evolution)
        excluded = {
            "outside_valid_time": 0,
            "not_yet_known": 0,
            "superseded": 0,
            "retracted": 0,
            "invalidated": 0,
            "conflicted": 0,
            "resolved_conflict": 0,
            "outside_entity_scope": 0,
            "relationship_type": 0,
        }
        canonical_filter = (
            self.entities.resolve_canonical_entity_id(
                scope, entity_id, known_at=known_at
            )
            if entity_id
            else None
        )
        effective: list[RelationshipRecord] = []
        open_conflict_ids = {
            item["conflict_id"]
            for item in conflicts
            if item["conflict_status"] == "open"
        }
        resolved_conflict_winners = {
            relationship_id: item["resolution_relationship_id"]
            for item in conflicts
            if item["conflict_status"] == "resolved"
            and item.get("resolution_relationship_id")
            for relationship_id in item["relationship_ids"]
        }
        for relationship in relationships:
            reason = None
            if relationship.system_known_from > known_at:
                reason = "not_yet_known"
            elif relationship.valid_from > valid_at or (
                relationship.valid_until and relationship.valid_until <= valid_at
            ):
                reason = "outside_valid_time"
            current_status = "active"
            for evolution in by_source.get(relationship.relationship_id, []):
                if evolution.evolution_type == "supersede":
                    current_status, reason = "superseded", "superseded"
                elif evolution.evolution_type == "retract":
                    current_status, reason = "retracted", "retracted"
                elif evolution.evolution_type == "invalidate":
                    current_status, reason = "invalidated", "invalidated"
                elif (
                    evolution.evolution_type == "declare_contradiction"
                    and evolution.conflict_id in open_conflict_ids
                ):
                    current_status = "conflicted"
                    if not include_conflicted:
                        reason = "conflicted"
                elif evolution.evolution_type == "resolve_contradiction":
                    current_status = (
                        "resolved"
                        if evolution.resolution_relationship_id
                        == relationship.relationship_id
                        else current_status
                    )
            winner = resolved_conflict_winners.get(relationship.relationship_id)
            if winner and winner != relationship.relationship_id:
                current_status, reason = "resolved", "resolved_conflict"
            subject = self.entities.resolve_canonical_entity_id(
                scope, relationship.subject_entity_id, known_at=known_at
            )
            object_ = self.entities.resolve_canonical_entity_id(
                scope, relationship.object_entity_id, known_at=known_at
            )
            if canonical_filter and canonical_filter not in {subject, object_}:
                reason = "outside_entity_scope"
            if relationship_type and relationship.relationship_type != relationship_type:
                reason = "relationship_type"
            if reason:
                excluded[reason] += 1
                continue
            effective.append(
                replace(
                    relationship,
                    subject_entity_id=subject,
                    object_entity_id=object_,
                    relationship_status=current_status,
                )
            )
        effective.sort(
            key=lambda item: (
                item.valid_from,
                item.subject_entity_id,
                item.relationship_type,
                item.object_entity_id,
                item.relationship_id,
            )
        )
        manifest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "valid_at": valid_at,
                    "known_at": known_at,
                    "relationships": [
                        {
                            "relationship_id": item.relationship_id,
                            "fingerprint": item.relationship_fingerprint_sha256,
                            "status": item.relationship_status,
                            "subject": item.subject_entity_id,
                            "object": item.object_entity_id,
                        }
                        for item in effective
                    ],
                    "conflicts": [
                        {
                            "conflict_id": item["conflict_id"],
                            "status": item["conflict_status"],
                        }
                        for item in conflicts
                    ],
                    "revision": RELATIONSHIP_RESOLVER_REVISION,
                }
            )
        )
        return ResolvedRelationshipView(
            effective_relationships=effective,
            excluded_counts=excluded,
            open_conflicts=[
                item for item in conflicts if item["conflict_status"] == "open"
            ],
            temporal_boundary={"valid_at": valid_at, "known_at": known_at},
            deterministic_relationship_manifest=manifest,
        )

    def compare_relationship_views(
        self,
        scope: AuthenticatedScope,
        first_boundary: Any,
        second_boundary: Any,
        *,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        first = self.resolve_effective_relationships(
            scope, entity_id=entity_id, temporal_boundary=first_boundary
        )
        second = self.resolve_effective_relationships(
            scope, entity_id=entity_id, temporal_boundary=second_boundary
        )
        first_ids = {item.relationship_id for item in first.effective_relationships}
        second_ids = {item.relationship_id for item in second.effective_relationships}
        return {
            "added_relationship_ids": sorted(second_ids - first_ids),
            "removed_relationship_ids": sorted(first_ids - second_ids),
            "unchanged_relationship_ids": sorted(first_ids & second_ids),
            "changed": (
                first.deterministic_relationship_manifest
                != second.deterministic_relationship_manifest
            ),
            "resolver_revision": RELATIONSHIP_RESOLVER_REVISION,
        }

    def _evolve(
        self,
        scope: AuthenticatedScope,
        evolution_type: str,
        source: RelationshipRecord,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        replacement_relationship_id: str | None = None,
        conflict_id: str | None = None,
        resolution_relationship_id: str | None = None,
        valid_from: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> RelationshipEvolutionRecord:
        actor.validate()
        if not reason.strip():
            raise RelationshipMemoryError(
                "RELATIONSHIP_EVOLUTION_INVALID",
                "Relationship evolution reason is required.",
            )
        effective = utc(system_effective_at)
        valid = utc(valid_from, default=effective)
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "type": evolution_type,
                    "source": source.relationship_id,
                    "replacement": replacement_relationship_id,
                    "conflict": conflict_id,
                    "resolution": resolution_relationship_id,
                    "key": idempotency_key or "",
                    "revision": RELATIONSHIP_EVOLUTION_REVISION,
                }
            )
        )
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.evolution_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND idempotency_digest={self.p}",
                (*scope_params(scope), idem),
            ).fetchone()
            if row:
                return RelationshipEvolutionRecord(**payload_from_row(row))
            record = RelationshipEvolutionRecord(
                relationship_evolution_id=f"revo_{idem[:24]}",
                evolution_type=evolution_type,
                source_relationship_id=source.relationship_id,
                replacement_relationship_id=replacement_relationship_id,
                conflict_id=conflict_id,
                resolution_relationship_id=resolution_relationship_id,
                client_id=scope.client_id,
                vault_id=scope.vault_id,
                namespace=scope.namespace,
                valid_from=valid,
                system_effective_at=effective,
                actor_type=actor.actor_type,
                actor_reference=actor.actor_reference,
                reason=reason,
                idempotency_digest=idem,
                relationship_evolution_revision=RELATIONSHIP_EVOLUTION_REVISION,
                created_at=utc_now(),
            )
            connection.execute(
                f"INSERT INTO {self.evolution_table}("
                "relationship_evolution_id,evolution_type,source_relationship_id,"
                "replacement_relationship_id,conflict_id,resolution_relationship_id,"
                "client_id,vault_id,namespace,valid_from,system_effective_at,"
                "idempotency_digest,created_at,payload_json) VALUES("
                + ",".join([self.p] * 14)
                + ")",
                (
                    record.relationship_evolution_id,
                    record.evolution_type,
                    record.source_relationship_id,
                    record.replacement_relationship_id,
                    record.conflict_id,
                    record.resolution_relationship_id,
                    *scope_params(scope),
                    record.valid_from,
                    record.system_effective_at,
                    record.idempotency_digest,
                    record.created_at,
                    json_value(self.repository, record.to_dict()),
                ),
            )
        event = {
            "supersede": "relationship_superseded",
            "retract": "relationship_retracted",
        }.get(evolution_type)
        if event:
            self._log(
                event,
                scope,
                relationship_id=source.relationship_id,
                status=evolution_type,
            )
        return record

    def _reject_supersession_cycle(
        self, scope: AuthenticatedScope, source_id: str, target_id: str
    ) -> None:
        graph: dict[str, str] = {}
        for item in self.list_evolutions(scope):
            if item.evolution_type == "supersede" and item.replacement_relationship_id:
                graph[item.source_relationship_id] = item.replacement_relationship_id
        graph[source_id] = target_id
        for start in graph:
            current, visited = start, set()
            while current in graph:
                if current in visited:
                    raise RelationshipMemoryError(
                        "RELATIONSHIP_EVOLUTION_CYCLE_DETECTED",
                        "Relationship evolution cycle was detected.",
                    )
                visited.add(current)
                current = graph[current]

    def _conflicts_as_known(
        self, scope: AuthenticatedScope, valid_at: str, known_at: str
    ) -> list[dict[str, Any]]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.conflict_table} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND valid_from<={self.p} AND system_effective_at<={self.p} "
                "ORDER BY system_effective_at,conflict_id",
                (*scope_params(scope), valid_at, known_at),
            ).fetchall()
        output = []
        for row in rows:
            item = self._conflict_from_row(row)
            if item.get("resolved_at") and item["resolved_at"] > known_at:
                item = {
                    **item,
                    "conflict_status": "open",
                    "resolution_relationship_id": None,
                    "resolved_at": None,
                }
            output.append(item)
        return output

    def _conflict_from_row(self, row: Any) -> dict[str, Any]:
        raw = row["relationship_ids_json"]
        ids = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        return {
            "conflict_id": str(row["conflict_id"]),
            "relationship_ids": ids,
            "conflict_type": str(row["conflict_type"]),
            "conflict_status": str(row["conflict_status"]),
            "valid_from": str(row["valid_from"]),
            "system_effective_at": str(row["system_effective_at"]),
            "resolution_relationship_id": row["resolution_relationship_id"],
            "resolved_at": row["resolved_at"],
            "reason": str(row["reason"]),
        }

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        allowed = {"relationship_id", "conflict_id", "count", "status"}
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": event,
                    "scope_fingerprint": scope_fingerprint(scope),
                    **{key: value for key, value in fields.items() if key in allowed},
                },
                sort_keys=True,
            ),
        )


RelationshipStateResolver = RelationshipMemoryService


__all__ = ["RelationshipMemoryService", "RelationshipStateResolver"]
