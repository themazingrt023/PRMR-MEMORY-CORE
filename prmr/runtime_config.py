"""Typed, explicit and secret-safe runtime configuration for RC1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping

from .release.version import RELEASE_CONFIGURATION_REVISION


class ConfigurationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PoolConfiguration:
    minimum: int = 1
    maximum: int = 10
    acquisition_timeout_seconds: float = 10.0
    statement_timeout_ms: int = 30_000
    lock_timeout_ms: int = 5_000


@dataclass(frozen=True)
class WorkerConfiguration:
    enabled: bool = True
    workers: int = 1
    poll_interval_seconds: float = 1.0
    lease_seconds: int = 30
    graceful_timeout_seconds: float = 15.0


@dataclass(frozen=True)
class RuntimeConfiguration:
    mode: str = "sqlite_local"
    database_backend: str = "sqlite"
    sqlite_path: str = "data/prmr-memory-core.sqlite3"
    database_url: str | None = None
    database_url_env: str = "PRMR_DATABASE_URL"
    migration_policy: str = "explicit_or_init"
    log_format: str = "human"
    log_level: str = "INFO"
    export_path: str = "data/exports"
    diagnostics_path: str = "data/diagnostics"
    packet_default: str = "continuity_packet_v1"
    interpretation_provider_policy: str = "recorded_or_disabled"
    test_environment_protection: bool = True
    pool: PoolConfiguration = field(default_factory=PoolConfiguration)
    worker: WorkerConfiguration = field(default_factory=WorkerConfiguration)
    revision: str = RELEASE_CONFIGURATION_REVISION

    def validate(self, *, require_database_url: bool = True) -> "RuntimeConfiguration":
        failures: list[str] = []
        if self.mode not in {"sqlite_local", "postgres_single_node"}:
            failures.append("unsupported runtime mode")
        expected_backend = "sqlite" if self.mode == "sqlite_local" else "postgres"
        if self.database_backend != expected_backend:
            failures.append("runtime mode and database backend disagree")
        if self.database_backend == "sqlite" and not self.sqlite_path.strip():
            failures.append("SQLite path is missing")
        if self.database_backend == "postgres" and require_database_url and not self.database_url:
            failures.append("PostgreSQL database URL is missing")
        if self.pool.minimum < 0 or self.pool.maximum < max(1, self.pool.minimum):
            failures.append("connection pool bounds are invalid")
        if self.worker.workers < 1 or self.worker.workers > 32:
            failures.append("worker count must be between 1 and 32")
        if self.database_backend == "sqlite" and self.worker.workers > 1:
            failures.append("SQLite mode supports one bounded worker only")
        if self.log_format not in {"human", "json"}:
            failures.append("log format must be human or json")
        if self.packet_default not in {"continuity_packet_v1", "epistemic_continuity_v2"}:
            failures.append("packet default is unsupported")
        if failures:
            raise ConfigurationError("CONFIGURATION_INVALID", "; ".join(failures))
        return self


_ENV_MAP = {
    "PRMR_MODE": "mode",
    "PRMR_DATABASE_BACKEND": "database_backend",
    "PRMR_SQLITE_PATH": "sqlite_path",
    "PRMR_DATABASE_URL": "database_url",
    "PRMR_LOG_FORMAT": "log_format",
    "PRMR_LOG_LEVEL": "log_level",
    "PRMR_EXPORT_PATH": "export_path",
    "PRMR_DIAGNOSTICS_PATH": "diagnostics_path",
    "PRMR_PACKET_DEFAULT": "packet_default",
}


def _load_env_file(path: str | Path) -> dict[str, str]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigurationError("CONFIGURATION_FILE_MISSING", "Explicit environment file was not found.")
    values: dict[str, str] = {}
    for number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError("CONFIGURATION_FILE_MALFORMED", f"Malformed environment entry at line {number}.")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _flatten_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime = dict(payload.get("runtime", {}))
    database = dict(payload.get("database", {}))
    logging = dict(payload.get("logging", {}))
    paths = dict(payload.get("paths", {}))
    packet = dict(payload.get("packet", {}))
    interpretation = dict(payload.get("interpretation", {}))
    return {
        "mode": runtime.get("mode"),
        "database_backend": database.get("backend"),
        "sqlite_path": database.get("sqlite_path"),
        "database_url": database.get("database_url"),
        "database_url_env": database.get("database_url_env"),
        "migration_policy": database.get("migration_policy"),
        "log_format": logging.get("format"),
        "log_level": logging.get("level"),
        "export_path": paths.get("export"),
        "diagnostics_path": paths.get("diagnostics"),
        "packet_default": packet.get("default"),
        "interpretation_provider_policy": interpretation.get("provider_policy"),
        "test_environment_protection": runtime.get("test_environment_protection"),
        "pool": payload.get("pool"),
        "worker": payload.get("worker"),
    }


def load_runtime_configuration(
    *,
    config_path: str | Path | None = None,
    env_file: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
    require_database_url: bool = True,
) -> RuntimeConfiguration:
    """Load defaults -> explicit file -> explicit env file/process env -> CLI."""

    values: dict[str, Any] = {}
    if config_path:
        source = Path(config_path).expanduser().resolve()
        if not source.is_file():
            raise ConfigurationError("CONFIGURATION_FILE_MISSING", "Configuration file was not found.")
        try:
            values.update({k: v for k, v in _flatten_config(tomllib.loads(source.read_text(encoding="utf-8"))).items() if v is not None})
        except (tomllib.TOMLDecodeError, OSError) as exc:
            raise ConfigurationError("CONFIGURATION_FILE_MALFORMED", "Configuration file is malformed.") from exc

    merged_env = dict(_load_env_file(env_file)) if env_file else {}
    merged_env.update(dict(os.environ if environ is None else environ))
    for env_name, field_name in _ENV_MAP.items():
        if env_name in merged_env and merged_env[env_name] != "":
            values[field_name] = merged_env[env_name]
    database_url_env = str(values.get("database_url_env", "PRMR_DATABASE_URL"))
    if database_url_env in merged_env and merged_env[database_url_env]:
        values["database_url"] = merged_env[database_url_env]
    if cli_overrides:
        values.update({key: value for key, value in cli_overrides.items() if value is not None})

    defaults = RuntimeConfiguration()
    pool_data = values.pop("pool", None)
    worker_data = values.pop("worker", None)
    pool = replace(defaults.pool, **dict(pool_data or {}))
    worker = replace(defaults.worker, **dict(worker_data or {}))
    config = replace(defaults, pool=pool, worker=worker, **values)
    return config.validate(require_database_url=require_database_url)


def redact_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I):
        return "<redacted-url>"
    return "<redacted>"


def render_redacted_configuration(config: RuntimeConfiguration) -> dict[str, Any]:
    payload = asdict(config)
    payload["database_url"] = redact_secret(config.database_url)
    payload["database_url_configured"] = bool(config.database_url)
    return payload


def configuration_fingerprint(config: RuntimeConfiguration) -> str:
    payload = render_redacted_configuration(config)
    payload.pop("database_url", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def example_configuration(mode: str) -> str:
    if mode not in {"sqlite_local", "postgres_single_node"}:
        raise ConfigurationError("CONFIGURATION_INVALID", "Unsupported example mode.")
    backend = "sqlite" if mode == "sqlite_local" else "postgres"
    sqlite_path = "data/prmr-memory-core.sqlite3" if backend == "sqlite" else ""
    return f'''# PRMR Memory Core v1.0 RC1 - no secrets in this file.\n[runtime]\nmode = "{mode}"\ntest_environment_protection = true\n\n[database]\nbackend = "{backend}"\nsqlite_path = "{sqlite_path}"\ndatabase_url_env = "PRMR_DATABASE_URL"\nmigration_policy = "explicit_or_init"\n\n[pool]\nminimum = 1\nmaximum = 10\nacquisition_timeout_seconds = 10.0\nstatement_timeout_ms = 30000\nlock_timeout_ms = 5000\n\n[worker]\nenabled = true\nworkers = 1\npoll_interval_seconds = 1.0\nlease_seconds = 30\ngraceful_timeout_seconds = 15.0\n\n[logging]\nformat = "human"\nlevel = "INFO"\n\n[paths]\nexport = "data/exports"\ndiagnostics = "data/diagnostics"\n\n[packet]\ndefault = "continuity_packet_v1"\n\n[interpretation]\nprovider_policy = "recorded_or_disabled"\n'''


__all__ = [
    "ConfigurationError",
    "RuntimeConfiguration",
    "configuration_fingerprint",
    "example_configuration",
    "load_runtime_configuration",
    "render_redacted_configuration",
]
