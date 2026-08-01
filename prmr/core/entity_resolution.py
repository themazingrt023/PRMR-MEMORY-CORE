"""Deterministic scoped entity resolution without fuzzy automatic matching."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .entity_models import EntityMemoryError, EntityRecord
from .entity_store import (
    digest_identifier,
    initialize_entity_relationship_schema,
    normalise_label,
    payload_from_row,
    placeholder,
    scope_params,
    table,
    utc,
)
from .source_models import AuthenticatedScope


class EntityResolver:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_entity_relationship_schema(repository)
        self.entity_table = table(repository, "prmr_entities")
        self.identifier_table = table(repository, "prmr_entity_identifiers")
        self.alias_table = table(repository, "prmr_entity_alias_assertions")
        self.merge_table = table(repository, "prmr_entity_merges")
        self.distinct_table = table(repository, "prmr_entity_distinctness_assertions")
        self.p = placeholder(repository)

    def get_entity(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        *,
        resolve_current: bool = False,
        known_at: str | None = None,
    ) -> EntityRecord:
        requested = (
            self.resolve_canonical_entity_id(scope, entity_id, known_at=known_at)
            if resolve_current
            else entity_id
        )
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.entity_table} "
                f"WHERE entity_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p}",
                (requested, *scope_params(scope)),
            ).fetchone()
        if not row:
            raise EntityMemoryError(
                "ENTITY_NOT_FOUND", "Entity was not found in authenticated scope."
            )
        return EntityRecord(**payload_from_row(row))

    def list_entities(
        self, scope: AuthenticatedScope, *, include_inactive: bool = False
    ) -> list[EntityRecord]:
        status = "" if include_inactive else f" AND entity_status={self.p}"
        params: tuple[Any, ...] = () if include_inactive else ("active",)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.entity_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p}"
                f"{status} ORDER BY created_at,entity_id",
                (*scope_params(scope), *params),
            ).fetchall()
        return [EntityRecord(**payload_from_row(row)) for row in rows]

    def resolve_identifier(
        self,
        scope: AuthenticatedScope,
        identifier_namespace: str,
        identifier_value: str,
        *,
        entity_type: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
    ) -> dict[str, Any]:
        digest = digest_identifier(identifier_namespace, identifier_value)
        valid = utc(valid_at)
        known = utc(known_at)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.identifier_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND identifier_namespace={self.p} AND identifier_value_digest={self.p} "
                f"AND identifier_status={self.p}",
                (*scope_params(scope), identifier_namespace, digest, "active"),
            ).fetchall()
        matches = []
        for row in rows:
            item = payload_from_row(row)
            if item["valid_from"] > valid:
                continue
            if item.get("valid_until") and item["valid_until"] <= valid:
                continue
            if item["system_known_from"] > known:
                continue
            if item.get("system_known_until") and item["system_known_until"] <= known:
                continue
            entity = self.get_entity(scope, item["entity_id"])
            if entity_type and not self.types_compatible(
                entity.canonical_entity_type, entity_type
            ):
                return {
                    "resolution_status": "conflict",
                    "resolution_level": 5,
                    "entity_id": None,
                    "candidate_entity_ids": [entity.entity_id],
                    "basis": "type_conflict",
                }
            matches.append(
                self.resolve_canonical_entity_id(
                    scope, entity.entity_id, known_at=known_at
                )
            )
        matches = sorted(set(matches))
        if len(matches) == 1:
            return {
                "resolution_status": "resolved",
                "resolution_level": 1,
                "entity_id": matches[0],
                "candidate_entity_ids": matches,
                "basis": "exact_stable_identifier",
            }
        if len(matches) > 1:
            return {
                "resolution_status": "ambiguous",
                "resolution_level": 1,
                "entity_id": None,
                "candidate_entity_ids": matches,
                "basis": "identifier_conflict",
            }
        return {
            "resolution_status": "unresolved",
            "resolution_level": 1,
            "entity_id": None,
            "candidate_entity_ids": [],
            "basis": "identifier_not_found",
        }

    def resolve_alias_or_label(
        self,
        scope: AuthenticatedScope,
        value: str,
        *,
        entity_type: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
    ) -> dict[str, Any]:
        normalised = normalise_label(value)
        valid = utc(valid_at)
        known = utc(known_at)
        alias_ids: list[str] = []
        with self.repository.connect() as connection:
            alias_rows = connection.execute(
                f"SELECT payload_json FROM {self.alias_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} AND namespace={self.p} "
                f"AND alias_normalised={self.p} AND alias_status={self.p}",
                (*scope_params(scope), normalised, "active"),
            ).fetchall()
        for row in alias_rows:
            alias = payload_from_row(row)
            if alias["valid_from"] > valid or alias["system_effective_at"] > known:
                continue
            if alias.get("valid_until") and alias["valid_until"] <= valid:
                continue
            entity = self.get_entity(scope, alias["entity_id"])
            if entity_type and not self.types_compatible(
                entity.canonical_entity_type, entity_type
            ):
                continue
            alias_ids.append(
                self.resolve_canonical_entity_id(
                    scope, entity.entity_id, known_at=known_at
                )
            )
        alias_ids = sorted(set(alias_ids))
        if len(alias_ids) == 1:
            return {
                "resolution_status": "resolved",
                "resolution_level": 2,
                "entity_id": alias_ids[0],
                "candidate_entity_ids": alias_ids,
                "basis": "explicit_alias",
            }
        if len(alias_ids) > 1:
            return {
                "resolution_status": "ambiguous",
                "resolution_level": 2,
                "entity_id": None,
                "candidate_entity_ids": alias_ids,
                "basis": "alias_conflict",
            }

        possible = [
            entity.entity_id
            for entity in self.list_entities(scope)
            if normalise_label(entity.canonical_label) == normalised
            and (
                entity_type is None
                or self.types_compatible(entity.canonical_entity_type, entity_type)
            )
        ]
        possible = sorted(
            {
                self.resolve_canonical_entity_id(
                    scope, entity_id, known_at=known_at
                )
                for entity_id in possible
            }
        )
        possible = self._exclude_explicitly_distinct_pairs(scope, possible, known)
        if possible:
            return {
                "resolution_status": (
                    "possible_match" if len(possible) == 1 else "ambiguous"
                ),
                "resolution_level": 3,
                "entity_id": None,
                "candidate_entity_ids": possible,
                "basis": "label_only",
            }
        return {
            "resolution_status": "unresolved",
            "resolution_level": 3,
            "entity_id": None,
            "candidate_entity_ids": [],
            "basis": "label_not_found",
        }

    def resolve_canonical_entity_id(
        self,
        scope: AuthenticatedScope,
        entity_id: str,
        *,
        known_at: str | None = None,
    ) -> str:
        boundary = utc(known_at)
        current = entity_id
        visited: set[str] = set()
        while True:
            if current in visited:
                raise EntityMemoryError(
                    "ENTITY_MERGE_CYCLE_DETECTED", "Entity merge cycle was detected."
                )
            visited.add(current)
            self.get_entity(scope, current)
            with self.repository.connect() as connection:
                row = connection.execute(
                    f"SELECT target_entity_id FROM {self.merge_table} "
                    f"WHERE client_id={self.p} AND vault_id={self.p} "
                    f"AND namespace={self.p} AND source_entity_id={self.p} "
                    f"AND system_effective_at<={self.p} "
                    f"ORDER BY system_effective_at DESC,entity_merge_id DESC LIMIT 1",
                    (*scope_params(scope), current, boundary),
                ).fetchone()
            if not row:
                return current
            current = str(row["target_entity_id"])

    @staticmethod
    def types_compatible(first: str, second: str) -> bool:
        return first == second or "unknown" in {first, second}

    def _exclude_explicitly_distinct_pairs(
        self, scope: AuthenticatedScope, entity_ids: list[str], known_at: str
    ) -> list[str]:
        if len(entity_ids) < 2:
            return entity_ids
        # Distinctness does not remove candidates; it prevents an automatic
        # confirmed merge. Label resolution therefore stays ambiguous.
        return entity_ids


__all__ = ["EntityResolver"]
