"""Ordered, checksummed Core Sprint migration registry."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from .entity_store import POSTGRES_SCHEMA, placeholder, table
from .runtime_models import (
    MIGRATION_VALIDATION_REVISION,
    MigrationDefinition,
    RuntimeErrorCode,
)


ROOT = Path(__file__).resolve().parents[2]

MIGRATION_SPECS = (
    ("core_01_source_ledger_v1", "Core Sprint 1", "core_source_ledger_v1", ()),
    (
        "core_02_candidate_memory_v1",
        "Core Sprint 2",
        "core_candidate_memory_v1",
        ("core_01_source_ledger_v1",),
    ),
    (
        "core_03_memory_admission_v1",
        "Core Sprint 3",
        "core_memory_admission_v1",
        ("core_02_candidate_memory_v1",),
    ),
    (
        "core_04_memory_ledger_v2",
        "Core Sprint 4",
        "core_memory_ledger_v2",
        ("core_03_memory_admission_v1",),
    ),
    (
        "core_05_temporal_memory_v1",
        "Core Sprint 5",
        "core_temporal_memory_v1",
        ("core_04_memory_ledger_v2",),
    ),
    (
        "core_06_entity_relationship_v1",
        "Core Sprint 6",
        "core_entity_relationship_memory_v1",
        ("core_05_temporal_memory_v1",),
    ),
    (
        "core_07_memory_query_v1",
        "Core Sprint 7",
        "core_memory_query_v1",
        ("core_06_entity_relationship_v1",),
    ),
    (
        "core_08_memory_consolidation_v1",
        "Core Sprint 8",
        "core_memory_consolidation_v1",
        ("core_07_memory_query_v1",),
    ),
    (
        "core_09_semantic_interpretation_v1",
        "Core Sprint 9",
        "core_semantic_interpretation_v1",
        ("core_08_memory_consolidation_v1",),
    ),
    (
        "core_10_memory_governance_v1",
        "Core Sprint 10",
        "core_memory_governance_v1",
        ("core_09_semantic_interpretation_v1",),
    ),
    (
        "core_11_memory_runtime_v1",
        "Core Sprint 11",
        "core_memory_runtime_v1",
        ("core_10_memory_governance_v1",),
    ),
    (
        "core_13_continuity_packet_v2",
        "Core Sprint 13",
        "core_continuity_packet_v2",
        ("core_11_memory_runtime_v1",),
    ),
)


class RuntimeMigrationExecutionError(RuntimeErrorCode):
    """Migration failure retaining only safe phase identity plus the SQL cause."""

    def __init__(self, migration_id: str, phase: str) -> None:
        super().__init__(
            "POSTGRES_MIGRATION_FAILED",
            f"PostgreSQL migration failed during {phase}: {migration_id}.",
        )
        self.migration_id = migration_id
        self.execution_phase = phase


def _checksum(sqlite_path: Path, postgres_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(sqlite_path.read_bytes())
    digest.update(b"\0")
    digest.update(postgres_path.read_bytes())
    return digest.hexdigest()


def migration_registry() -> tuple[MigrationDefinition, ...]:
    definitions: list[MigrationDefinition] = []
    for migration_id, sprint, stem, dependencies in MIGRATION_SPECS:
        sqlite_path = ROOT / "migrations" / f"{stem}_sqlite.sql"
        postgres_path = ROOT / "migrations" / f"{stem}_postgres.sql"
        if not sqlite_path.exists() or not postgres_path.exists():
            raise RuntimeErrorCode(
                "POSTGRES_MIGRATION_FAILED",
                f"Migration pair is missing for {migration_id}.",
            )
        definitions.append(
            MigrationDefinition(
                migration_id=migration_id,
                sprint=sprint,
                sqlite_path=str(sqlite_path.relative_to(ROOT)).replace("\\", "/"),
                postgres_path=str(postgres_path.relative_to(ROOT)).replace("\\", "/"),
                checksum_sha256=_checksum(sqlite_path, postgres_path),
                dependencies=tuple(dependencies),
                transactional=True,
                destructive=False,
                minimum_schema_state=dependencies[-1] if dependencies else "empty_core",
                resulting_schema_state=migration_id,
            )
        )
    return tuple(definitions)


def expected_postgres_relations(
    definitions: Iterable[MigrationDefinition] | None = None,
) -> dict[str, list[str]]:
    """List schema relations declared by each ordered PostgreSQL migration."""

    result: dict[str, list[str]] = {}
    registry = migration_registry() if definitions is None else tuple(definitions)
    for definition in registry:
        sql = (ROOT / definition.postgres_path).read_text(encoding="utf-8")
        result[definition.migration_id] = sorted(
            {
                name.split(".")[-1]
                for name in re.findall(
                    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z0-9_.]+)",
                    sql,
                    flags=re.IGNORECASE,
                )
            }
        )
    return result


def validate_postgres_relation_order(
    definitions: Iterable[MigrationDefinition] | None = None,
) -> dict[str, Any]:
    """Statically verify that foreign-key targets precede dependent tables."""

    known: set[str] = set()
    failures: list[dict[str, Any]] = []
    registry = migration_registry() if definitions is None else tuple(definitions)
    for definition in registry:
        sql = (ROOT / definition.postgres_path).read_text(encoding="utf-8")
        for statement in sql.split(";"):
            created = re.search(
                r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z0-9_.]+)",
                statement,
                flags=re.IGNORECASE,
            )
            if not created:
                continue
            relation = created.group(1).split(".")[-1]
            references = {
                name.split(".")[-1]
                for name in re.findall(
                    r"REFERENCES\s+([A-Za-z0-9_.]+)",
                    statement,
                    flags=re.IGNORECASE,
                )
            }
            missing = sorted(references - known - {relation})
            if missing:
                failures.append(
                    {
                        "migration_id": definition.migration_id,
                        "relation": relation,
                        "missing_references": missing,
                    }
                )
            known.add(relation)
    return {
        "verified": not failures,
        "relation_count": len(known),
        "failures": failures,
    }


def _ensure_registry_table(repository: Any) -> None:
    migration_table = table(repository, "prmr_runtime_schema_migrations")
    if str(getattr(repository, "backend_name", "sqlite")) == "postgres":
        sql = f"""
        CREATE TABLE IF NOT EXISTS {migration_table} (
            migration_id TEXT PRIMARY KEY, sprint TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL, resulting_schema_state TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL
        )
        """
    else:
        sql = f"""
        CREATE TABLE IF NOT EXISTS {migration_table} (
            migration_id TEXT PRIMARY KEY, sprint TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL, resulting_schema_state TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    with repository.connect() as connection:
        if str(getattr(repository, "backend_name", "sqlite")) == "postgres":
            # PostgreSQL's CREATE SCHEMA IF NOT EXISTS can still race in the
            # system catalog when two empty-database bootstraps start at the
            # same instant. Lock before creating either migration relation.
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("prmr_core_migration_registry_bootstrap_v1",),
            )
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
        connection.execute(sql)


def get_migration_status(repository: Any) -> list[dict[str, Any]]:
    _ensure_registry_table(repository)
    migration_table = table(repository, "prmr_runtime_schema_migrations")
    with repository.connect() as connection:
        rows = connection.execute(
            f"SELECT migration_id,sprint,checksum_sha256,resulting_schema_state,"
            f"applied_at FROM {migration_table} ORDER BY applied_at,migration_id"
        ).fetchall()
    return [dict(row) for row in rows]


def apply_pending_migrations(
    repository: Any,
    *,
    definitions: Iterable[MigrationDefinition] | None = None,
) -> list[str]:
    """Apply known non-destructive migrations under a database migration lock."""

    registry = (
        migration_registry() if definitions is None else tuple(definitions)
    )
    _ensure_registry_table(repository)
    existing = {row["migration_id"]: row for row in get_migration_status(repository)}
    applied: list[str] = []
    postgres = str(getattr(repository, "backend_name", "sqlite")) == "postgres"
    for definition in registry:
        prior = existing.get(definition.migration_id)
        if prior:
            if prior["checksum_sha256"] != definition.checksum_sha256:
                raise RuntimeErrorCode(
                    "POSTGRES_MIGRATION_CHECKSUM_MISMATCH",
                    f"Migration checksum drift: {definition.migration_id}.",
                )
            continue
        missing = [item for item in definition.dependencies if item not in existing]
        if missing:
            raise RuntimeErrorCode(
                "POSTGRES_MIGRATION_FAILED",
                f"Migration dependency is missing for {definition.migration_id}.",
            )
        path = ROOT / (
            definition.postgres_path if postgres else definition.sqlite_path
        )
        sql = path.read_text(encoding="utf-8")
        migration_table = table(repository, "prmr_runtime_schema_migrations")
        p = placeholder(repository)
        with repository.connect() as connection:
            if postgres:
                try:
                    connection.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        ("prmr_core_migration_registry_v1",),
                    )
                    current = connection.execute(
                        f"SELECT checksum_sha256 FROM {migration_table} "
                        f"WHERE migration_id={p}",
                        (definition.migration_id,),
                    ).fetchone()
                    if current:
                        if current["checksum_sha256"] != definition.checksum_sha256:
                            raise RuntimeErrorCode(
                                "POSTGRES_MIGRATION_CHECKSUM_MISMATCH",
                                f"Migration checksum drift: {definition.migration_id}.",
                            )
                        existing[definition.migration_id] = {
                            "checksum_sha256": definition.checksum_sha256
                        }
                        continue
                    connection.execute(sql)
                except RuntimeErrorCode:
                    raise
                except Exception as exc:
                    raise RuntimeMigrationExecutionError(
                        definition.migration_id, "migration_apply"
                    ) from exc
            else:
                connection.executescript(sql)
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            try:
                connection.execute(
                    f"INSERT INTO {migration_table}(migration_id,sprint,checksum_sha256,"
                    f"resulting_schema_state,applied_at) VALUES({','.join([p]*5)})",
                    (
                        definition.migration_id,
                        definition.sprint,
                        definition.checksum_sha256,
                        definition.resulting_schema_state,
                        now,
                    ),
                )
            except RuntimeErrorCode:
                raise
            except Exception as exc:
                if postgres:
                    raise RuntimeMigrationExecutionError(
                        definition.migration_id, "migration_record"
                    ) from exc
                raise
        existing[definition.migration_id] = {
            "checksum_sha256": definition.checksum_sha256
        }
        applied.append(definition.migration_id)
    return applied


def verify_migration_checksums(repository: Any) -> dict[str, Any]:
    expected = {item.migration_id: item for item in migration_registry()}
    status = get_migration_status(repository)
    mismatches = [
        row["migration_id"]
        for row in status
        if row["migration_id"] in expected
        and row["checksum_sha256"] != expected[row["migration_id"]].checksum_sha256
    ]
    return {
        "verified": not mismatches,
        "mismatches": mismatches,
        "revision": MIGRATION_VALIDATION_REVISION,
    }


def verify_schema_revision(repository: Any) -> dict[str, Any]:
    status = get_migration_status(repository)
    expected = [item.migration_id for item in migration_registry()]
    applied = [row["migration_id"] for row in status]
    missing = [item for item in expected if item not in applied]
    return {
        "verified": not missing,
        "current": applied[-1] if applied else None,
        "expected": expected[-1],
        "missing": missing,
    }


def detect_migration_drift(repository: Any) -> dict[str, Any]:
    checksums = verify_migration_checksums(repository)
    revision = verify_schema_revision(repository)
    return {
        "drift_detected": not checksums["verified"] or not revision["verified"],
        "checksum": checksums,
        "schema": revision,
    }


__all__ = [
    "apply_pending_migrations",
    "detect_migration_drift",
    "expected_postgres_relations",
    "get_migration_status",
    "migration_registry",
    "RuntimeMigrationExecutionError",
    "validate_postgres_relation_order",
    "verify_migration_checksums",
    "verify_schema_revision",
]
