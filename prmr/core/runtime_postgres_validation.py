"""Strict isolated-PostgreSQL environment guard for destructive core tests."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse
from typing import Any

from .runtime_models import (
    POSTGRES_VALIDATION_REVISION,
    PostgresEnvironmentEvidence,
    RuntimeErrorCode,
)


TEST_DATABASE_ENV = "PRMR_POSTGRES_TEST_DATABASE_URL"
DESTRUCTIVE_PERMISSION_ENV = "PRMR_ALLOW_DESTRUCTIVE_POSTGRES_TESTS"
APPLICATION_SCHEMA = "prmr_self_serve"


def _direct_driver() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeErrorCode(
            "POSTGRES_CONNECTION_FAILED",
            "PostgreSQL driver is unavailable.",
        ) from exc
    return psycopg, dict_row


def verify_postgres_test_environment(
    database_url: str | None = None,
    *,
    destructive_permission: str | bool | None = None,
) -> PostgresEnvironmentEvidence:
    """Verify the guard row before any destructive PostgreSQL test operation."""

    configured_url = (database_url or os.getenv(TEST_DATABASE_ENV, "")).strip()
    if not configured_url:
        raise RuntimeErrorCode(
            "POSTGRES_TEST_DATABASE_URL_MISSING",
            f"Set {TEST_DATABASE_ENV} to an isolated test database.",
        )
    permission = (
        destructive_permission
        if destructive_permission is not None
        else os.getenv(DESTRUCTIVE_PERMISSION_ENV, "")
    )
    allowed = permission is True or str(permission).strip().lower() == "true"
    if not allowed:
        raise RuntimeErrorCode(
            "POSTGRES_DESTRUCTIVE_TEST_PERMISSION_MISSING",
            f"Set {DESTRUCTIVE_PERMISSION_ENV}=true after confirming isolation.",
        )
    psycopg, dict_row = _direct_driver()
    try:
        with psycopg.connect(
            configured_url,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=10,
        ) as connection:
            identity = connection.execute(
                """
                SELECT current_database() AS database_name,
                       current_schema() AS schema_name,
                       current_setting('server_version') AS server_version,
                       current_setting('statement_timeout') AS statement_timeout,
                       current_setting('lock_timeout') AS lock_timeout
                """
            ).fetchone()
            verify_test_guard_connection(connection)
    except RuntimeErrorCode:
        raise
    except Exception as exc:
        raise RuntimeErrorCode(
            "POSTGRES_CONNECTION_FAILED",
            "Could not verify the isolated PostgreSQL test environment.",
        ) from exc
    parsed = urlparse(configured_url)
    host_hint = parsed.hostname or "configured-host"
    database_name = str(identity["database_name"])
    return PostgresEnvironmentEvidence(
        status="VERIFIED_ISOLATED_TEST_DATABASE",
        database_hint=f"{host_hint[:32]}/{database_name[:48]}",
        schema=str(identity["schema_name"]),
        server_version=str(identity["server_version"]),
        transaction_support=True,
        destructive_tests_allowed=True,
        guard_verified=True,
        production_guard_absent=True,
        statement_timeout=str(identity["statement_timeout"]),
        lock_timeout=str(identity["lock_timeout"]),
        revision=POSTGRES_VALIDATION_REVISION,
    )


def verify_test_guard_connection(connection: Any) -> bool:
    """Verify the public guard using an existing PostgreSQL connection."""

    guard_exists = connection.execute(
        "SELECT to_regclass('public.prmr_test_environment_guard') AS relation"
    ).fetchone()
    if not guard_exists or not guard_exists["relation"]:
        raise RuntimeErrorCode(
            "POSTGRES_TEST_ENVIRONMENT_NOT_CONFIRMED",
            "Isolated test environment guard table is missing.",
        )
    guard = connection.execute(
        """
        SELECT environment_kind, destructive_tests_allowed
        FROM public.prmr_test_environment_guard
        WHERE environment_kind = 'isolated_test'
          AND destructive_tests_allowed IS TRUE
        LIMIT 1
        """
    ).fetchone()
    production_marker = connection.execute(
        """
        SELECT EXISTS(
            SELECT 1
            FROM public.prmr_test_environment_guard
            WHERE environment_kind IN ('production', 'live')
        ) AS present
        """
    ).fetchone()
    if not guard or bool(production_marker["present"]):
        raise RuntimeErrorCode(
            "POSTGRES_TEST_ENVIRONMENT_NOT_CONFIRMED",
            "Database marker does not authorise destructive test execution.",
        )
    return True


def reset_postgres_test_application_schema(connection: Any) -> dict[str, Any]:
    """Reset only PRMR test application objects while preserving the guard."""

    verify_test_guard_connection(connection)
    connection.execute(f"DROP SCHEMA IF EXISTS {APPLICATION_SCHEMA} CASCADE")
    guard_preserved = verify_test_guard_connection(connection)
    return {
        "application_schema_removed": APPLICATION_SCHEMA,
        "guard_schema": "public",
        "guard_preserved": guard_preserved,
    }


def safe_postgres_exception_diagnostics(
    error: BaseException,
    *,
    execution_phase: str,
    migration_id: str | None = None,
) -> dict[str, Any]:
    """Return bounded PostgreSQL diagnostics without connection or content data."""

    current: BaseException | None = error
    sqlstate: str | None = None
    relation: str | None = None
    discovered_migration = migration_id or getattr(error, "migration_id", None)
    discovered_phase = getattr(error, "execution_phase", None) or execution_phase
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        sqlstate = sqlstate or getattr(current, "sqlstate", None)
        diagnostic = getattr(current, "diag", None)
        if diagnostic is not None:
            relation = relation or getattr(diagnostic, "table_name", None)
            primary = str(getattr(diagnostic, "message_primary", "") or "")
        else:
            primary = ""
        if not relation and primary:
            match = re.search(r'relation "([A-Za-z0-9_.]+)" does not exist', primary)
            if match:
                relation = match.group(1)
        current = current.__cause__ or current.__context__
    safe_code = getattr(error, "code", None)
    if sqlstate == "42P01":
        safe_code = "POSTGRES_UNDEFINED_TABLE"
    return {
        "safe_error_code": safe_code or type(error).__name__.upper(),
        "sqlstate": sqlstate,
        "missing_relation": relation,
        "migration_id": discovered_migration,
        "execution_phase": discovered_phase,
        "database_url_recorded": False,
    }


def create_test_guard_sql() -> str:
    """Return explicit operator-run SQL; never creates the guard automatically."""

    return (
        "CREATE TABLE IF NOT EXISTS public.prmr_test_environment_guard ("
        "environment_kind TEXT PRIMARY KEY, destructive_tests_allowed BOOLEAN NOT NULL);"
        " INSERT INTO public.prmr_test_environment_guard"
        "(environment_kind, destructive_tests_allowed)"
        " VALUES ('isolated_test', TRUE)"
        " ON CONFLICT (environment_kind) DO UPDATE"
        " SET destructive_tests_allowed=EXCLUDED.destructive_tests_allowed;"
    )


__all__ = [
    "APPLICATION_SCHEMA",
    "DESTRUCTIVE_PERMISSION_ENV",
    "TEST_DATABASE_ENV",
    "create_test_guard_sql",
    "reset_postgres_test_application_schema",
    "safe_postgres_exception_diagnostics",
    "verify_test_guard_connection",
    "verify_postgres_test_environment",
]
