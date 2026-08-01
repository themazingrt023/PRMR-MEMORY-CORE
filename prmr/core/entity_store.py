"""Shared persistence helpers for Core Sprint 6 entity and relationship memory."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from .entity_models import ENTITY_MEMORY_SCHEMA_REVISION
from .relationship_models import RELATIONSHIP_MEMORY_SCHEMA_REVISION
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


POSTGRES_SCHEMA = "prmr_self_serve"
SQLITE_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "core_entity_relationship_memory_v1_sqlite.sql"
)
POSTGRES_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "core_entity_relationship_memory_v1_postgres.sql"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc(value: str | None, *, default: str | None = None) -> str:
    raw = value or default or utc_now()
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def backend_name(repository: Any) -> str:
    name = str(getattr(repository, "backend_name", "sqlite"))
    if name not in {"sqlite", "postgres"}:
        return "sqlite" if hasattr(repository, "storage_path") else "postgres"
    return name


def table(repository: Any, name: str) -> str:
    return f"{POSTGRES_SCHEMA}.{name}" if backend_name(repository) == "postgres" else name


def placeholder(repository: Any) -> str:
    return "%s" if backend_name(repository) == "postgres" else "?"


def initialize_entity_relationship_schema(repository: Any) -> None:
    backend = backend_name(repository)
    with repository.connect() as connection:
        if backend == "sqlite":
            initialize_sqlite_entity_relationship_schema(connection)
            return
        initialize_postgres_entity_relationship_schema(connection)


def initialize_sqlite_entity_relationship_schema(connection: Any) -> None:
    connection.executescript(SQLITE_MIGRATION.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT OR IGNORE INTO prmr_entity_relationship_schema_migrations"
        "(revision,applied_at) VALUES(?,?)",
        (
            f"{ENTITY_MEMORY_SCHEMA_REVISION}+{RELATIONSHIP_MEMORY_SCHEMA_REVISION}",
            utc_now(),
        ),
    )


def initialize_postgres_entity_relationship_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(POSTGRES_MIGRATION.read_text(encoding="utf-8"))
    cursor.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_entity_relationship_schema_migrations"
        "(revision,applied_at) VALUES(%s,%s) ON CONFLICT(revision) DO NOTHING",
        (
            f"{ENTITY_MEMORY_SCHEMA_REVISION}+{RELATIONSHIP_MEMORY_SCHEMA_REVISION}",
            utc_now(),
        ),
    )


def scope_params(scope: AuthenticatedScope) -> tuple[str, str, str]:
    return scope.client_id, scope.vault_id, scope.namespace


def scope_fingerprint(scope: AuthenticatedScope) -> str:
    return sha256_text(canonical_json(scope.memory_boundary()))[:16]


def require_scope(
    scope: AuthenticatedScope, client_id: str, vault_id: str, namespace: str, code: str
) -> None:
    if scope.memory_boundary() != (client_id, vault_id, namespace):
        from .entity_models import EntityMemoryError

        raise EntityMemoryError(code, "Requested record is outside authenticated scope.")


def payload_from_row(row: Any) -> dict[str, Any]:
    raw = row["payload_json"]
    return json.loads(raw) if isinstance(raw, str) else dict(raw or {})


def json_value(repository: Any, value: Any) -> Any:
    return canonical_json(value)


def stable_id(prefix: str, payload: Any, length: int = 24) -> str:
    return f"{prefix}_{sha256_text(canonical_json(payload))[:length]}"


def normalise_label(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def safe_display(value: str | None, maximum: int = 120) -> str:
    clean = " ".join(str(value or "").replace("\x00", "").split())
    return clean[:maximum]


def digest_identifier(namespace: str, value: str) -> str:
    return sha256_text(
        canonical_json(
            {
                "identifier_namespace": normalise_label(namespace),
                "identifier_value": str(value).strip(),
                "revision": "entity_identifier_digest_v1",
            }
        )
    )


def fetch_payloads(
    repository: Any,
    table_name: str,
    scope: AuthenticatedScope,
    *,
    where: str = "",
    params: Iterable[Any] = (),
    order_by: str = "created_at",
) -> list[dict[str, Any]]:
    p = placeholder(repository)
    clause = (
        f"client_id={p} AND vault_id={p} AND namespace={p}"
        + (f" AND {where}" if where else "")
    )
    with repository.connect() as connection:
        rows = connection.execute(
            f"SELECT payload_json FROM {table(repository, table_name)} "
            f"WHERE {clause} ORDER BY {order_by}",
            (*scope_params(scope), *tuple(params)),
        ).fetchall()
    return [payload_from_row(row) for row in rows]


def row_exists(
    repository: Any, table_name: str, column: str, value: str
) -> bool:
    p = placeholder(repository)
    with repository.connect() as connection:
        row = connection.execute(
            f"SELECT 1 AS found FROM {table(repository, table_name)} "
            f"WHERE {column}={p}",
            (value,),
        ).fetchone()
    return bool(row)


__all__ = [
    "POSTGRES_SCHEMA",
    "backend_name",
    "digest_identifier",
    "fetch_payloads",
    "initialize_entity_relationship_schema",
    "initialize_postgres_entity_relationship_schema",
    "initialize_sqlite_entity_relationship_schema",
    "json_value",
    "normalise_label",
    "payload_from_row",
    "placeholder",
    "require_scope",
    "safe_display",
    "scope_fingerprint",
    "scope_params",
    "stable_id",
    "table",
    "utc",
    "utc_now",
]
