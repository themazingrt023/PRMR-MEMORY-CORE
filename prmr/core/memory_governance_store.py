"""Durable governance storage over the existing repository connection boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .entity_store import json_value, placeholder, table
from .source_integrity import canonical_json


ROOT = Path(__file__).resolve().parents[2]
SQLITE_MIGRATION = ROOT / "migrations" / "core_memory_governance_v1_sqlite.sql"
POSTGRES_MIGRATION = ROOT / "migrations" / "core_memory_governance_v1_postgres.sql"

GOVERNANCE_TABLES = {
    "request": "prmr_memory_governance_requests",
    "graph": "prmr_memory_dependency_graphs",
    "plan": "prmr_memory_governance_plans",
    "plan_item": "prmr_memory_governance_plan_items",
    "execution": "prmr_memory_governance_executions",
    "execution_item": "prmr_memory_governance_execution_items",
    "verification": "prmr_memory_governance_verifications",
    "tombstone": "prmr_memory_erasure_tombstones",
    "hold": "prmr_memory_preservation_holds",
    "retention": "prmr_memory_retention_annotations",
    "export_request": "prmr_memory_export_requests",
    "export_bundle": "prmr_memory_export_bundles",
    "correction": "prmr_memory_correction_requests",
}


def initialize_memory_governance_schema(repository: Any) -> None:
    sql = (
        POSTGRES_MIGRATION.read_text(encoding="utf-8")
        if str(getattr(repository, "backend_name", "sqlite")) == "postgres"
        else SQLITE_MIGRATION.read_text(encoding="utf-8")
    )
    with repository.connect() as connection:
        if hasattr(connection, "executescript"):
            connection.executescript(sql)
        else:
            connection.execute(sql)


class MemoryGovernanceStore:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_memory_governance_schema(repository)
        self.p = placeholder(repository)
        self.tables = {
            key: table(repository, value) for key, value in GOVERNANCE_TABLES.items()
        }

    @staticmethod
    def decode(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else json.loads(value)

    def get(
        self,
        kind: str,
        id_column: str,
        object_id: str,
        scope: tuple[str, str, str] | None = None,
    ) -> dict[str, Any] | None:
        predicates = [f"{id_column}={self.p}"]
        params: list[Any] = [object_id]
        if scope:
            predicates.extend(
                [
                    f"client_id={self.p}",
                    f"vault_id={self.p}",
                    f"namespace={self.p}",
                ]
            )
            params.extend(scope)
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.tables[kind]} WHERE "
                + " AND ".join(predicates),
                tuple(params),
            ).fetchone()
        return self.decode(row["payload_json"]) if row else None

    def insert(
        self,
        kind: str,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
        payload: dict[str, Any],
    ) -> None:
        all_columns = (*columns, "payload_json")
        all_values = (*values, json_value(self.repository, payload))
        with self.repository.connect() as connection:
            connection.execute(
                f"INSERT INTO {self.tables[kind]}({','.join(all_columns)}) "
                f"VALUES({','.join([self.p] * len(all_columns))})",
                all_values,
            )

    def insert_many(
        self,
        kind: str,
        columns: tuple[str, ...],
        rows: list[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        """Persist a deterministic batch in one repository transaction."""

        if not rows:
            return
        all_columns = (*columns, "payload_json")
        values = [
            (*row_values, json_value(self.repository, payload))
            for row_values, payload in rows
        ]
        with self.repository.connect() as connection:
            connection.cursor().executemany(
                f"INSERT INTO {self.tables[kind]}({','.join(all_columns)}) "
                f"VALUES({','.join([self.p] * len(all_columns))})",
                values,
            )

    def update_payload(
        self,
        kind: str,
        id_column: str,
        object_id: str,
        payload: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> None:
        assignments = [f"payload_json={self.p}"]
        params: list[Any] = [json_value(self.repository, payload)]
        for key, value in (extra or {}).items():
            assignments.append(f"{key}={self.p}")
            params.append(value)
        params.append(object_id)
        with self.repository.connect() as connection:
            connection.execute(
                f"UPDATE {self.tables[kind]} SET {','.join(assignments)} "
                f"WHERE {id_column}={self.p}",
                tuple(params),
            )

    def manifest_rows(
        self, kind: str, scope: tuple[str, str, str]
    ) -> list[dict[str, Any]]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.tables[kind]} WHERE "
                f"client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                scope,
            ).fetchall()
        return [self.decode(row["payload_json"]) for row in rows]


__all__ = [
    "GOVERNANCE_TABLES",
    "MemoryGovernanceStore",
    "POSTGRES_MIGRATION",
    "SQLITE_MIGRATION",
    "initialize_memory_governance_schema",
]
