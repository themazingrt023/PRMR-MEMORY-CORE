"""Runtime repository context shared by CLI and stable facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prmr.core.runtime_database import PostgresRuntimeRepository, RuntimeDatabaseConfig
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093

from .runtime_config import RuntimeConfiguration


@dataclass
class RuntimeContext:
    configuration: RuntimeConfiguration
    repository: Any
    ready: bool = False
    shutting_down: bool = False

    def close(self) -> None:
        close = getattr(self.repository, "close", None)
        if callable(close):
            close()
        self.ready = False


def build_repository(configuration: RuntimeConfiguration) -> Any:
    if configuration.database_backend == "sqlite":
        return SelfServeRepositoryV093(configuration.sqlite_path)
    assert configuration.database_url is not None
    return PostgresRuntimeRepository(
        configuration.database_url,
        config=RuntimeDatabaseConfig(
            pool_minimum=configuration.pool.minimum,
            pool_maximum=configuration.pool.maximum,
            acquisition_timeout_seconds=configuration.pool.acquisition_timeout_seconds,
            statement_timeout_ms=configuration.pool.statement_timeout_ms,
            lock_timeout_ms=configuration.pool.lock_timeout_ms,
        ),
    )


__all__ = ["RuntimeContext", "build_repository"]
