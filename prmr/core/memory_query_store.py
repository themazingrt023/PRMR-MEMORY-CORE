"""Schema and JSON storage helpers for durable deterministic query artifacts."""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
from typing import Any, TypeVar

from .memory_query_models import (
    MEMORY_QUERY_SCHEMA_REVISION,
    MemoryEvidenceBundle,
    MemoryEvidenceItem,
    MemoryExplanation,
    MemoryQueryResult,
    MemoryQueryRun,
)
from .source_integrity import canonical_json


ROOT = Path(__file__).resolve().parents[2]
SQLITE_MIGRATION = ROOT / "migrations" / "core_memory_query_v1_sqlite.sql"
POSTGRES_MIGRATION = ROOT / "migrations" / "core_memory_query_v1_postgres.sql"
POSTGRES_SCHEMA = "prmr_self_serve"
T = TypeVar("T")


def backend_name(repository: Any) -> str:
    return str(getattr(repository, "backend_name", "sqlite"))


def placeholder(repository: Any) -> str:
    return "%s" if backend_name(repository) == "postgres" else "?"


def table(repository: Any, name: str) -> str:
    return f"{POSTGRES_SCHEMA}.{name}" if backend_name(repository) == "postgres" else name


def json_value(repository: Any, payload: Any) -> Any:
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    if backend_name(repository) == "postgres":
        from psycopg.types.json import Jsonb

        return Jsonb(payload)
    return canonical_json(payload)


def payload_from_row(row: Any) -> dict[str, Any]:
    payload = row["payload_json"]
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)


def dataclass_from_payload(cls: type[T], payload: dict[str, Any]) -> T:
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in payload.items() if key in allowed})


def initialize_memory_query_schema(repository: Any) -> None:
    with repository.connect() as connection:
        if backend_name(repository) == "postgres":
            initialize_postgres_memory_query_schema(connection)
        else:
            initialize_sqlite_memory_query_schema(connection)


def initialize_sqlite_memory_query_schema(connection: Any) -> None:
    connection.executescript(SQLITE_MIGRATION.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT OR IGNORE INTO prmr_memory_query_schema_migrations(revision,applied_at) "
        "VALUES(?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
        (MEMORY_QUERY_SCHEMA_REVISION,),
    )


def initialize_postgres_memory_query_schema(connection: Any) -> None:
    connection.execute(POSTGRES_MIGRATION.read_text(encoding="utf-8"))
    connection.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_memory_query_schema_migrations"
        "(revision,applied_at) VALUES(%s,TO_CHAR(NOW() AT TIME ZONE 'UTC',"
        "'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')) ON CONFLICT(revision) DO NOTHING",
        (MEMORY_QUERY_SCHEMA_REVISION,),
    )


def run_from_row(row: Any) -> MemoryQueryRun:
    return dataclass_from_payload(MemoryQueryRun, payload_from_row(row))


def result_from_row(row: Any) -> MemoryQueryResult:
    return dataclass_from_payload(MemoryQueryResult, payload_from_row(row))


def evidence_bundle_from_row(row: Any) -> MemoryEvidenceBundle:
    payload = payload_from_row(row)
    payload["evidence_items"] = [
        dataclass_from_payload(MemoryEvidenceItem, item)
        for item in payload.get("evidence_items", [])
    ]
    return dataclass_from_payload(MemoryEvidenceBundle, payload)


def explanation_from_row(row: Any) -> MemoryExplanation:
    return dataclass_from_payload(MemoryExplanation, payload_from_row(row))


__all__ = [
    "POSTGRES_MIGRATION",
    "POSTGRES_SCHEMA",
    "SQLITE_MIGRATION",
    "backend_name",
    "dataclass_from_payload",
    "evidence_bundle_from_row",
    "explanation_from_row",
    "initialize_memory_query_schema",
    "initialize_postgres_memory_query_schema",
    "initialize_sqlite_memory_query_schema",
    "json_value",
    "payload_from_row",
    "placeholder",
    "result_from_row",
    "run_from_row",
    "table",
]
