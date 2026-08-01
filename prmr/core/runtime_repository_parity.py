"""Logical SQLite/PostgreSQL runtime schema and repository parity helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from .runtime_models import REPOSITORY_PARITY_REVISION
from .source_integrity import canonical_json, sha256_text


@dataclass(frozen=True)
class RepositoryParityCase:
    name: str
    sqlite_operation: Callable[[], Any]
    postgres_operation: Callable[[], Any]
    normalise: Callable[[Any], Any] = lambda value: value


class RuntimeRepositoryParity:
    """Compare deterministic repository effects, not database-specific metadata."""

    def run(self, cases: list[RepositoryParityCase]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for case in cases:
            sqlite_value = case.normalise(case.sqlite_operation())
            postgres_value = case.normalise(case.postgres_operation())
            sqlite_hash = sha256_text(canonical_json(sqlite_value))
            postgres_hash = sha256_text(canonical_json(postgres_value))
            results.append(
                {
                    "name": case.name,
                    "equivalent": sqlite_hash == postgres_hash,
                    "sqlite_hash": sqlite_hash,
                    "postgres_hash": postgres_hash,
                }
            )
        return {
            "verified": all(item["equivalent"] for item in results),
            "cases": results,
            "revision": REPOSITORY_PARITY_REVISION,
        }


def logical_runtime_migration_contract(sql: str) -> dict[str, Any]:
    """Extract a bounded logical contract from runtime DDL for static comparison."""

    lowered = re.sub(r"\s+", " ", sql.lower())
    tables = sorted(
        {
            name.split(".")[-1]
            for name in re.findall(
                r"create table if not exists ([a-z0-9_.]+)", lowered
            )
        }
    )
    indexes = sorted(
        set(re.findall(r"create index if not exists ([a-z0-9_]+)", lowered))
    )
    required_columns = {
        column: column in lowered
        for column in (
            "job_id",
            "job_type",
            "client_id",
            "vault_id",
            "namespace",
            "payload_hash_sha256",
            "idempotency_key_digest",
            "job_status",
            "lease_token_digest",
            "lease_expires_at",
            "heartbeat_at",
            "result_reference_id",
            "sequence_number",
        )
    }
    return {
        "tables": tables,
        "indexes": indexes,
        "required_columns": required_columns,
        "foreign_keys_present": "references" in lowered,
        "unique_constraints_present": "unique" in lowered,
    }


def compare_runtime_migration_contracts(
    sqlite_sql: str, postgres_sql: str
) -> dict[str, Any]:
    sqlite = logical_runtime_migration_contract(sqlite_sql)
    postgres = logical_runtime_migration_contract(postgres_sql)
    checks = {
        "tables": sqlite["tables"] == postgres["tables"],
        "indexes": sqlite["indexes"] == postgres["indexes"],
        "required_columns": sqlite["required_columns"]
        == postgres["required_columns"],
        "foreign_keys": sqlite["foreign_keys_present"]
        == postgres["foreign_keys_present"],
        "unique_constraints": sqlite["unique_constraints_present"]
        == postgres["unique_constraints_present"],
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "intentional_differences": [
            "SQLite stores canonical JSON as TEXT; PostgreSQL uses JSONB.",
            "SQLite stores UTC timestamps as ISO text; PostgreSQL uses TIMESTAMPTZ.",
            "PostgreSQL leasing uses row locks and SKIP LOCKED; SQLite is single-writer.",
            "PostgreSQL adds check constraints that SQLite runners enforce in code.",
        ],
        "revision": REPOSITORY_PARITY_REVISION,
    }


__all__ = [
    "RepositoryParityCase",
    "RuntimeRepositoryParity",
    "compare_runtime_migration_contracts",
    "logical_runtime_migration_contract",
]
