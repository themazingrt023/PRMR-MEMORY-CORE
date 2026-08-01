"""Bounded PostgreSQL runtime connections and transaction retry policy."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import time
from typing import Any, Callable, Iterator, TypeVar

from .runtime_models import RuntimeErrorCode, RuntimeTransactionPolicy


LOGGER = logging.getLogger("prmr.core.runtime")
T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeDatabaseConfig:
    pool_minimum: int = 1
    pool_maximum: int = 10
    acquisition_timeout_seconds: float = 10.0
    statement_timeout_ms: int = 30_000
    lock_timeout_ms: int = 5_000
    idle_transaction_timeout_ms: int = 30_000
    serialization_maximum_attempts: int = 3

    def __post_init__(self) -> None:
        if self.pool_minimum < 0 or self.pool_maximum < max(1, self.pool_minimum):
            raise ValueError("Invalid PostgreSQL pool bounds.")
        if min(
            self.acquisition_timeout_seconds,
            self.statement_timeout_ms,
            self.lock_timeout_ms,
            self.idle_transaction_timeout_ms,
        ) <= 0:
            raise ValueError("Database timeouts must be positive.")


def _pool_driver() -> tuple[Any, Any]:
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeErrorCode(
            "POSTGRES_CONNECTION_FAILED",
            'PostgreSQL pooling requires the "psycopg[pool,binary]" package.',
        ) from exc
    return ConnectionPool, dict_row


class PostgresRuntimeRepository:
    """Repository-compatible pooled PostgreSQL connection boundary."""

    backend_name = "postgres"

    def __init__(
        self,
        database_url: str,
        *,
        config: RuntimeDatabaseConfig | None = None,
        open_pool: bool = True,
    ) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise RuntimeErrorCode(
                "POSTGRES_TEST_DATABASE_URL_MISSING",
                "Dedicated PostgreSQL test database URL is required.",
            )
        self._database_url = database_url.strip()
        self.config = config or RuntimeDatabaseConfig()
        ConnectionPool, dict_row = _pool_driver()
        self._pool = ConnectionPool(
            conninfo=self._database_url,
            min_size=self.config.pool_minimum,
            max_size=self.config.pool_maximum,
            timeout=self.config.acquisition_timeout_seconds,
            kwargs={
                "row_factory": dict_row,
                "prepare_threshold": None,
                "autocommit": False,
            },
            configure=self._configure_connection,
            open=open_pool,
        )
        if open_pool:
            self._pool.wait(timeout=self.config.acquisition_timeout_seconds)

    def _configure_connection(self, connection: Any) -> None:
        connection.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(self.config.statement_timeout_ms),),
        )
        connection.execute(
            "SELECT set_config('lock_timeout', %s, false)",
            (str(self.config.lock_timeout_ms),),
        )
        connection.execute(
            "SELECT set_config('idle_in_transaction_session_timeout', %s, false)",
            (str(self.config.idle_transaction_timeout_ms),),
        )
        connection.commit()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        acquired = False
        try:
            with self._pool.connection(
                timeout=self.config.acquisition_timeout_seconds
            ) as connection:
                acquired = True
                try:
                    yield connection
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except RuntimeErrorCode:
            raise
        except Exception as exc:
            if acquired:
                raise
            LOGGER.error(
                "database_pool_exhausted",
                extra={"safe_error_code": "POSTGRES_POOL_EXHAUSTED"},
            )
            raise RuntimeErrorCode(
                "POSTGRES_POOL_EXHAUSTED",
                "PostgreSQL connection could not be acquired.",
            ) from exc

    def close(self) -> None:
        self._pool.close()

    def health_check(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT 1 AS healthy").fetchone()
        return bool(row and int(row["healthy"]) == 1)

    def pool_stats(self) -> dict[str, int]:
        stats = self._pool.get_stats()
        allowed = (
            "pool_min",
            "pool_max",
            "pool_size",
            "pool_available",
            "requests_waiting",
            "requests_errors",
        )
        return {key: int(stats.get(key, 0)) for key in allowed}

    def run_transaction(
        self,
        operation: Callable[[Any], T],
        *,
        policy: RuntimeTransactionPolicy = RuntimeTransactionPolicy.READ_COMMITTED_V1,
    ) -> tuple[T, int]:
        attempts = (
            self.config.serialization_maximum_attempts
            if policy == RuntimeTransactionPolicy.SERIALIZABLE_RETRY_V1
            else 1
        )
        for attempt in range(1, attempts + 1):
            try:
                with self.connect() as connection:
                    if policy == RuntimeTransactionPolicy.SERIALIZABLE_RETRY_V1:
                        connection.execute(
                            "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
                        )
                    return operation(connection), attempt - 1
            except Exception as exc:
                if not _serialization_failure(exc) or attempt >= attempts:
                    if _serialization_failure(exc):
                        raise RuntimeErrorCode(
                            "POSTGRES_SERIALIZATION_RETRY_EXHAUSTED",
                            "Serializable transaction retry limit was reached.",
                        ) from exc
                    raise
                LOGGER.warning(
                    "database_serialization_retry",
                    extra={"retry_count": attempt},
                )
                time.sleep(0.01 * attempt)
        raise AssertionError("unreachable")


def _serialization_failure(error: BaseException) -> bool:
    sqlstate = getattr(error, "sqlstate", None)
    if sqlstate in {"40001", "40P01"}:
        return True
    text = f"{type(error).__name__} {error}".lower()
    return "serialization" in text or "deadlock" in text


__all__ = [
    "PostgresRuntimeRepository",
    "RuntimeDatabaseConfig",
]
