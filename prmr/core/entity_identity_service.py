"""Canonical entity identity, aliases, merges, distinctness and event links."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .entity_candidates import EntityCandidateEngine
from .entity_models import (
    ENTITY_ALIAS_REVISION,
    ENTITY_IDENTITY_REVISION,
    ENTITY_MENTION_REVISION,
    ENTITY_RESOLUTION_REVISION,
    EVENT_ENTITY_LINK_REVISION,
    EntityAliasAssertion,
    EntityMemoryError,
    EntityRecord,
    EventEntityLink,
)
from .entity_resolution import EntityResolver
from .entity_store import (
    initialize_entity_relationship_schema,
    json_value,
    normalise_label,
    payload_from_row,
    placeholder,
    scope_fingerprint,
    scope_params,
    stable_id,
    table,
    utc,
    utc_now,
)
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.entity_identity")


class EntityIdentityService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.candidates = EntityCandidateEngine(repository, initialize=initialize)
        self.resolver = EntityResolver(repository, initialize=False)
        self.admission = MemoryAdmissionService(repository, initialize=initialize)
        self.entity_table = table(repository, "prmr_entities")
        self.identifier_table = table(repository, "prmr_entity_identifiers")
        self.alias_table = table(repository, "prmr_entity_alias_assertions")
        self.merge_table = table(repository, "prmr_entity_merges")
        self.distinct_table = table(repository, "prmr_entity_distinctness_assertions")
        self.link_table = table(repository, "prmr_event_entity_links")
        self.mention_table = table(repository, "prmr_entity_mentions")
        self.p = placeholder(repository)

    def add_alias(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        alias_value: str,
        source_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        segment_id: str | None = None,
        evidence_manifest_hash_sha256: str | None = None,
        epistemic_status: str = "explicit",
        valid_from: str | None = None,
        valid_until: str | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> EntityAliasAssertion:
        entity = self.resolver.get_entity(scope, entity_id, resolve_current=True)
        actor.validate()
        normalised = normalise_label(alias_value)
        if not normalised or len(normalised) > 240:
            raise EntityMemoryError("ENTITY_ALIAS_INVALID", "Entity alias is invalid.")
        if normalised == normalise_label(entity.canonical_label):
            raise EntityMemoryError(
                "ENTITY_ALIAS_INVALID", "Alias duplicates the canonical label."
            )
        possible = self.resolver.resolve_alias_or_label(scope, alias_value)
        for other_id in possible.get("candidate_entity_ids", []):
            if other_id == entity.entity_id:
                continue
            other = self.resolver.get_entity(scope, other_id)
            reverse_aliases = self.list_aliases(
                scope, other.entity_id, include_inactive=False
            )
            if any(
                item.alias_normalised == normalise_label(entity.canonical_label)
                for item in reverse_aliases
            ):
                raise EntityMemoryError(
                    "ENTITY_ALIAS_CONFLICT",
                    "Alias assertion would create a reciprocal identity cycle.",
                )
        manifest = evidence_manifest_hash_sha256 or sha256_text(
            canonical_json(
                {
                    "source_id": source_id,
                    "segment_id": segment_id,
                    "alias_hash": sha256_text(normalised),
                    "reason": reason,
                }
            )
        )
        effective = utc(system_effective_at)
        valid = utc(valid_from, default=effective)
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "entity_id": entity.entity_id,
                    "alias": normalised,
                    "source_id": source_id,
                    "key": idempotency_key or "",
                    "revision": ENTITY_ALIAS_REVISION,
                }
            )
        )
        existing = self._alias_by_idempotency(scope, idem)
        if existing:
            return existing
        alias = EntityAliasAssertion(
            alias_assertion_id=f"alias_{idem[:24]}",
            entity_id=entity.entity_id,
            alias_value=str(alias_value).strip(),
            alias_normalised=normalised,
            alias_hash_sha256=sha256_text(normalised),
            source_id=source_id,
            segment_id=segment_id,
            evidence_manifest_hash_sha256=manifest,
            epistemic_status=epistemic_status,
            assertion_actor_type=actor.actor_type,
            assertion_actor_reference=actor.actor_reference,
            assertion_reason=reason,
            valid_from=valid,
            valid_until=utc(valid_until) if valid_until else None,
            system_effective_at=effective,
            alias_status="active",
            entity_alias_revision=ENTITY_ALIAS_REVISION,
            idempotency_digest=idem,
            created_at=utc_now(),
        )
        with self.repository.connect() as connection:
            conflict_rows = connection.execute(
                f"SELECT payload_json FROM {self.alias_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND alias_normalised={self.p} AND alias_status={self.p}",
                (*scope_params(scope), normalised, "active"),
            ).fetchall()
            distinct_entities = {
                payload_from_row(row)["entity_id"] for row in conflict_rows
            } - {entity.entity_id}
            status = "conflicted" if distinct_entities else "active"
            if status != alias.alias_status:
                alias = replace(alias, alias_status=status)
            connection.execute(
                f"INSERT INTO {self.alias_table}("
                "alias_assertion_id,entity_id,client_id,vault_id,namespace,"
                "alias_normalised,alias_hash_sha256,source_id,valid_from,valid_until,"
                "system_effective_at,alias_status,idempotency_digest,created_at,payload_json"
                ") VALUES(" + ",".join([self.p] * 15) + ")",
                (
                    alias.alias_assertion_id,
                    alias.entity_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    alias.alias_normalised,
                    alias.alias_hash_sha256,
                    alias.source_id,
                    alias.valid_from,
                    alias.valid_until,
                    alias.system_effective_at,
                    alias.alias_status,
                    alias.idempotency_digest,
                    alias.created_at,
                    json_value(self.repository, alias.to_dict()),
                ),
            )
        self._log("entity_alias_added", scope, entity_id=entity.entity_id, status=alias.alias_status)
        return alias

    def retract_alias(
        self,
        scope: AuthenticatedScope,
        alias_assertion_id: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        system_effective_at: str | None = None,
    ) -> EntityAliasAssertion:
        actor.validate()
        alias = self.get_alias(scope, alias_assertion_id)
        updated = replace(
            alias,
            alias_status="retracted",
            valid_until=utc(system_effective_at),
        )
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.alias_table} SET alias_status={self.p},"
                f"valid_until={self.p},payload_json={self.p} "
                f"WHERE alias_assertion_id={self.p}",
                (
                    updated.alias_status,
                    updated.valid_until,
                    json_value(self.repository, updated.to_dict()),
                    alias_assertion_id,
                ),
            )
        return updated

    def get_alias(
        self, scope: AuthenticatedScope, alias_assertion_id: str
    ) -> EntityAliasAssertion:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.alias_table} "
                f"WHERE alias_assertion_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (alias_assertion_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise EntityMemoryError(
                "ENTITY_ALIAS_INVALID", "Alias assertion was not found in scope."
            )
        return EntityAliasAssertion(**payload_from_row(row))

    def list_aliases(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        *,
        valid_at: str | None = None,
        known_at: str | None = None,
        include_inactive: bool = False,
    ) -> list[EntityAliasAssertion]:
        canonical = self.resolver.resolve_canonical_entity_id(
            scope, entity_id, known_at=known_at
        )
        valid, known = utc(valid_at), utc(known_at)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.alias_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND entity_id={self.p} ORDER BY system_effective_at,alias_assertion_id",
                (*scope_params(scope), canonical),
            ).fetchall()
        aliases = [EntityAliasAssertion(**payload_from_row(row)) for row in rows]
        if include_inactive:
            return aliases
        return [
            item
            for item in aliases
            if item.alias_status == "active"
            and item.valid_from <= valid
            and item.system_effective_at <= known
            and (not item.valid_until or item.valid_until > valid)
        ]

    def merge_entities(
        self,
        scope: AuthenticatedScope,
        source_entity_id: str,
        target_entity_id: str,
        decision_actor: AdmissionDecisionActor,
        reason: str,
        *,
        evidence: list[dict[str, Any]] | None = None,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        decision_actor.validate()
        if source_entity_id == target_entity_id:
            raise EntityMemoryError("ENTITY_MERGE_INVALID", "Entity cannot merge into itself.")
        source = self.resolver.get_entity(scope, source_entity_id)
        target = self.resolver.get_entity(scope, target_entity_id, resolve_current=True)
        if self.resolver.resolve_canonical_entity_id(scope, target.entity_id) == source.entity_id:
            self._log(
                "entity_merge_cycle_rejected",
                scope,
                entity_id=source.entity_id,
                status="rejected",
            )
            raise EntityMemoryError(
                "ENTITY_MERGE_CYCLE_DETECTED", "Entity merge would create a cycle."
            )
        if not reason.strip() or (not evidence and decision_actor.actor_type == "engine_policy"):
            raise EntityMemoryError(
                "ENTITY_MERGE_INVALID", "Explicit merge reason or evidence is required."
            )
        effective = utc(system_effective_at)
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "source": source.entity_id,
                    "target": target.entity_id,
                    "key": idempotency_key or "",
                    "revision": ENTITY_RESOLUTION_REVISION,
                }
            )
        )
        with self.repository.connect() as connection:
            existing = connection.execute(
                f"SELECT * FROM {self.merge_table} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                f"AND idempotency_digest={self.p}",
                (*scope_params(scope), idem),
            ).fetchone()
            if existing:
                return dict(existing)
            merge_id = f"emerge_{idem[:24]}"
            connection.execute(
                f"INSERT INTO {self.merge_table}("
                "entity_merge_id,client_id,vault_id,namespace,source_entity_id,"
                "target_entity_id,actor_type,actor_reference,reason,evidence_json,"
                "valid_from,system_effective_at,idempotency_digest,created_at) VALUES("
                + ",".join([self.p] * 14)
                + ")",
                (
                    merge_id,
                    *scope_params(scope),
                    source.entity_id,
                    target.entity_id,
                    decision_actor.actor_type,
                    decision_actor.actor_reference,
                    reason,
                    json_value(self.repository, evidence or []),
                    effective,
                    effective,
                    idem,
                    utc_now(),
                ),
            )
            updated = replace(
                source,
                entity_status="merged",
                retired_at=effective,
                merged_into_entity_id=target.entity_id,
                updated_at=utc_now(),
            )
            connection.execute(
                f"UPDATE {self.entity_table} SET entity_status={self.p},"
                f"retired_at={self.p},merged_into_entity_id={self.p},updated_at={self.p},"
                f"payload_json={self.p} WHERE entity_id={self.p}",
                (
                    updated.entity_status,
                    updated.retired_at,
                    updated.merged_into_entity_id,
                    updated.updated_at,
                    json_value(self.repository, updated.to_dict()),
                    source.entity_id,
                ),
            )
        self._log("entity_merge_completed", scope, entity_id=source.entity_id, status="merged")
        return {
            "entity_merge_id": merge_id,
            "source_entity_id": source.entity_id,
            "target_entity_id": target.entity_id,
            "system_effective_at": effective,
            "history_deleted": False,
        }

    def declare_entities_distinct(
        self,
        scope: AuthenticatedScope,
        entity_ids: list[str],
        decision_actor: AdmissionDecisionActor,
        reason: str,
        *,
        evidence: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        decision_actor.validate()
        unique = sorted(set(entity_ids))
        if len(unique) < 2:
            raise EntityMemoryError(
                "ENTITY_DISTINCTNESS_CONFLICT", "At least two entities are required."
            )
        for entity_id in unique:
            self.resolver.get_entity(scope, entity_id)
        idem = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "entities": unique,
                    "key": idempotency_key or "",
                    "revision": ENTITY_RESOLUTION_REVISION,
                }
            )
        )
        record = {
            "distinctness_assertion_id": f"edist_{idem[:24]}",
            "entity_ids": unique,
            "actor_type": decision_actor.actor_type,
            "actor_reference": decision_actor.actor_reference,
            "reason": reason,
            "evidence": evidence or [],
            "status": "active",
            "system_effective_at": utc_now(),
            "idempotency_digest": idem,
            "created_at": utc_now(),
        }
        with self.repository.connect() as connection:
            existing = connection.execute(
                f"SELECT distinctness_assertion_id FROM {self.distinct_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} AND idempotency_digest={self.p}",
                (*scope_params(scope), idem),
            ).fetchone()
            if not existing:
                connection.execute(
                    f"INSERT INTO {self.distinct_table}("
                    "distinctness_assertion_id,client_id,vault_id,namespace,"
                    "entity_ids_json,actor_type,actor_reference,reason,evidence_json,"
                    "status,system_effective_at,idempotency_digest,created_at) VALUES("
                    + ",".join([self.p] * 13)
                    + ")",
                    (
                        record["distinctness_assertion_id"],
                        *scope_params(scope),
                        json_value(self.repository, unique),
                        decision_actor.actor_type,
                        decision_actor.actor_reference,
                        reason,
                        json_value(self.repository, evidence or []),
                        "active",
                        record["system_effective_at"],
                        idem,
                        record["created_at"],
                    ),
                )
        self._log("entities_declared_distinct", scope, count=len(unique), status="active")
        return record

    def link_event_to_entity(
        self,
        scope: AuthenticatedScope,
        event_id: str,
        entity_id: str,
        role: str,
        epistemic_status: str,
        actor: AdmissionDecisionActor,
        reason: str,
        *,
        evidence: dict[str, Any] | None = None,
        source_id: str | None = None,
        segment_id: str | None = None,
        candidate_id: str | None = None,
        admission_id: str | None = None,
        entity_candidate_id: str | None = None,
        entity_resolution_decision_id: str | None = None,
        link_method: str = "manual_internal_link",
        valid_from: str | None = None,
        system_known_from: str | None = None,
        idempotency_key: str | None = None,
    ) -> EventEntityLink:
        actor.validate()
        entity = self.resolver.get_entity(scope, entity_id, resolve_current=True)
        event = self.admission.get_admitted_event(scope, event_id)
        if not event:
            raise EntityMemoryError(
                "ENTITY_EVENT_LINK_INVALID", "Admitted event was not found."
            )
        if role not in {
            "primary_subject",
            "actor",
            "object",
            "participant",
            "owner",
            "related",
            "speaker",
            "target",
            "unknown",
        }:
            raise EntityMemoryError("ENTITY_EVENT_LINK_INVALID", "Event role is invalid.")
        if link_method not in {"explicit_event_reference", "structured_source_reference"} and not (
            evidence or reason.strip()
        ):
            raise EntityMemoryError(
                "ENTITY_EVENT_LINK_INVALID", "Non-explicit event link requires evidence."
            )
        event_source = source_id or self._source_for_event(scope, event_id)
        occurred = utc(
            valid_from
            or str(event.get("timestamp") or event.get("occurred_at") or utc_now())
        )
        known = utc(system_known_from)
        identity = {
            "scope": scope.memory_boundary(),
            "event_id": event_id,
            "entity_id": entity.entity_id,
            "role": role,
            "key": idempotency_key or "",
            "revision": EVENT_ENTITY_LINK_REVISION,
        }
        link_id = stable_id("eel", identity)
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.link_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND event_id={self.p} AND entity_id={self.p} AND entity_role={self.p} "
                "AND valid_until IS NULL AND system_known_until IS NULL",
                (*scope_params(scope), event_id, entity.entity_id, role),
            ).fetchone()
            if row:
                return EventEntityLink(**payload_from_row(row))
            link = EventEntityLink(
                event_entity_link_id=link_id,
                event_id=event_id,
                entity_id=entity.entity_id,
                entity_role=role,
                link_epistemic_status=epistemic_status,
                link_method=link_method,
                source_id=event_source,
                segment_id=segment_id,
                candidate_id=candidate_id,
                admission_id=admission_id,
                entity_candidate_id=entity_candidate_id,
                entity_resolution_decision_id=entity_resolution_decision_id,
                valid_from=occurred,
                valid_until=None,
                system_known_from=known,
                system_known_until=None,
                event_entity_link_revision=EVENT_ENTITY_LINK_REVISION,
                created_at=utc_now(),
            )
            connection.execute(
                f"INSERT INTO {self.link_table}("
                "event_entity_link_id,event_id,entity_id,client_id,vault_id,namespace,"
                "entity_role,source_id,valid_from,valid_until,system_known_from,"
                "system_known_until,created_at,payload_json) VALUES("
                + ",".join([self.p] * 14)
                + ")",
                (
                    link.event_entity_link_id,
                    link.event_id,
                    link.entity_id,
                    *scope_params(scope),
                    link.entity_role,
                    link.source_id,
                    link.valid_from,
                    link.valid_until,
                    link.system_known_from,
                    link.system_known_until,
                    link.created_at,
                    json_value(self.repository, link.to_dict()),
                ),
            )
        self._log("event_entity_link_created", scope, entity_id=entity.entity_id, status="active")
        return link

    def list_event_links(
        self,
        scope: AuthenticatedScope,
        *,
        entity_id: str | None = None,
        event_id: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
        current_only: bool = True,
    ) -> list[EventEntityLink]:
        conditions: list[str] = []
        params: list[Any] = []
        if entity_id:
            canonical = self.resolver.resolve_canonical_entity_id(
                scope, entity_id, known_at=known_at
            )
            source_ids = [
                item.entity_id
                for item in self.resolver.list_entities(scope, include_inactive=True)
                if self.resolver.resolve_canonical_entity_id(
                    scope, item.entity_id, known_at=known_at
                )
                == canonical
            ]
            conditions.append(
                "entity_id IN (" + ",".join([self.p] * len(source_ids)) + ")"
            )
            params.extend(source_ids)
        if event_id:
            conditions.append(f"event_id={self.p}")
            params.append(event_id)
        extra = " AND " + " AND ".join(conditions) if conditions else ""
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.link_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
                f"{extra} ORDER BY created_at,event_entity_link_id",
                (*scope_params(scope), *params),
            ).fetchall()
        links = [EventEntityLink(**payload_from_row(row)) for row in rows]
        if not current_only:
            return links
        valid, known = utc(valid_at), utc(known_at)
        return [
            link
            for link in links
            if link.valid_from <= valid
            and link.system_known_from <= known
            and (not link.valid_until or link.valid_until > valid)
            and (not link.system_known_until or link.system_known_until > known)
        ]

    def _source_for_event(self, scope: AuthenticatedScope, event_id: str) -> str:
        prefix = table(self.repository, "prmr_admitted_memory_links")
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT source_id FROM {prefix} WHERE admitted_event_id={self.p} "
                f"AND client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                (event_id, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise EntityMemoryError(
                "ENTITY_EVENT_LINK_INVALID", "Event provenance link was not found."
            )
        return str(row["source_id"])

    def _alias_by_idempotency(
        self, scope: AuthenticatedScope, digest: str
    ) -> EntityAliasAssertion | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.alias_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND idempotency_digest={self.p}",
                (*scope_params(scope), digest),
            ).fetchone()
        return EntityAliasAssertion(**payload_from_row(row)) if row else None

    @staticmethod
    def _log(event: str, scope: AuthenticatedScope, **fields: Any) -> None:
        allowed = {"entity_id", "status", "count"}
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


__all__ = ["EntityIdentityService"]
