"""V0.83 storage mode classification for PRMR Memory Core.

This module classifies the current storage path and API mode without claiming
durability that has not been verified. It is storage-boundary evidence only,
not a database migration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


BOUNDARY_V083 = (
    "V0.83 is storage boundary and durable-hosting readiness evidence only. "
    "It classifies local/hosted storage modes and documents durable storage "
    "requirements. It is not a full production database migration, paid managed "
    "storage, compliance approval, legal approval, external security "
    "certification, or real-world validation."
)

STORAGE_MODES = {
    "local_sqlite",
    "hosted_ephemeral_sqlite",
    "hosted_durable_sqlite",
    "hosted_managed_database_planned",
    "unknown_storage_mode",
}

EPHEMERAL_PREFIXES = ("/tmp", "/var/tmp")
DURABLE_SQLITE_PREFIXES = ("/data", "/var/data", "/mnt/data", "/app/data", "/opt/render/project/src/data")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalized_path_text(storage_path: str | os.PathLike[str] | None) -> str:
    if storage_path is None:
        return ""
    raw = str(storage_path).strip()
    return raw.replace("\\", "/")


def is_sqlite_path(path_text: str) -> bool:
    lowered = path_text.lower()
    return lowered.endswith((".sqlite", ".sqlite3", ".db"))


def is_tmp_path(path_text: str) -> bool:
    lowered = path_text.lower()
    return any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in EPHEMERAL_PREFIXES)


def is_reports_sqlite(path_text: str) -> bool:
    lowered = path_text.lower().lstrip("./")
    return lowered.startswith("reports/") and is_sqlite_path(lowered)


def is_durable_sqlite_candidate(path_text: str) -> bool:
    lowered = path_text.lower()
    return is_sqlite_path(lowered) and any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in DURABLE_SQLITE_PREFIXES)


def classify_storage_mode(
    *,
    storage_path: str | os.PathLike[str] | None,
    api_mode: str | None,
    storage_mode_override: str | None = None,
    durable_storage_verified: bool | None = None,
) -> dict[str, Any]:
    """Classify storage mode and produce public-safe boundary metadata."""

    path_text = normalized_path_text(storage_path)
    mode = str(api_mode or "").strip() or "unknown"
    override = str(storage_mode_override or "").strip()
    verified = bool(durable_storage_verified) if durable_storage_verified is not None else env_bool("PRMR_DURABLE_STORAGE_VERIFIED", False)
    reasons: list[str] = []

    if override in STORAGE_MODES:
        storage_mode = override
        reasons.append(f"PRMR_STORAGE_MODE override set to {override}.")
    elif not path_text:
        storage_mode = "unknown_storage_mode"
        reasons.append("PRMR_STORAGE_PATH is missing or blank.")
    elif is_tmp_path(path_text):
        storage_mode = "hosted_ephemeral_sqlite"
        reasons.append("/tmp or /var/tmp storage is ephemeral and smoke-test only.")
    elif mode.startswith("hosted") and is_durable_sqlite_candidate(path_text):
        storage_mode = "hosted_durable_sqlite"
        reasons.append("Hosted SQLite path is in a durable-path candidate location.")
    elif mode.startswith("hosted") and "postgres" in path_text.lower():
        storage_mode = "hosted_managed_database_planned"
        reasons.append("Managed database storage appears planned/configured by name, not verified here.")
    elif is_reports_sqlite(path_text) or (not mode.startswith("hosted") and is_sqlite_path(path_text)):
        storage_mode = "local_sqlite"
        reasons.append("SQLite path is local workspace/report storage.")
    elif mode.startswith("hosted") and is_sqlite_path(path_text):
        storage_mode = "hosted_managed_database_planned"
        reasons.append("Hosted SQLite path is not /tmp, but durability is not verified by this classifier.")
    else:
        storage_mode = "unknown_storage_mode"
        reasons.append("Storage path did not match known safe classifications.")

    ephemeral = storage_mode == "hosted_ephemeral_sqlite"
    durable_claim_allowed = storage_mode == "hosted_durable_sqlite" and verified
    managed_planned = storage_mode == "hosted_managed_database_planned"

    if ephemeral:
        hosted_boundary = "Hosted storage is ephemeral smoke storage only. Do not use it for real external alpha records."
    elif durable_claim_allowed:
        hosted_boundary = "Durable hosted SQLite storage is explicitly configured and verified by environment evidence."
    elif storage_mode == "hosted_durable_sqlite":
        hosted_boundary = "Hosted SQLite path is a durable candidate, but durability is not verified here."
    elif managed_planned:
        hosted_boundary = "Managed durable database storage is planned or needs configuration before real external alpha records."
    elif storage_mode == "local_sqlite":
        hosted_boundary = "Local SQLite storage is suitable for local synthetic/dev evidence, not hosted durability claims."
    else:
        hosted_boundary = "Storage mode is incomplete or unknown; do not claim durable hosted persistence."

    return {
        "version": "0.83",
        "storage_mode": storage_mode,
        "api_mode": mode,
        "storage_path": path_text or None,
        "sqlite_path": is_sqlite_path(path_text) if path_text else False,
        "ephemeral_storage": ephemeral,
        "durable_storage_verified": durable_claim_allowed,
        "durable_storage_claim_allowed": durable_claim_allowed,
        "managed_database_planned": managed_planned,
        "missing_storage_path": not bool(path_text),
        "classification_reasons": reasons,
        "hosted_storage_boundary": hosted_boundary,
        "public_safe": True,
        "boundary": BOUNDARY_V083,
    }


def classify_from_env() -> dict[str, Any]:
    return classify_storage_mode(
        storage_path=os.getenv("PRMR_STORAGE_PATH", ""),
        api_mode=os.getenv("PRMR_API_MODE", ""),
        storage_mode_override=os.getenv("PRMR_STORAGE_MODE", ""),
        durable_storage_verified=env_bool("PRMR_DURABLE_STORAGE_VERIFIED", False),
    )


def classify_from_config(config: Any) -> dict[str, Any]:
    return classify_storage_mode(
        storage_path=getattr(config, "storage_path", None),
        api_mode=getattr(config, "api_mode", None),
        storage_mode_override=os.getenv("PRMR_STORAGE_MODE", ""),
        durable_storage_verified=env_bool("PRMR_DURABLE_STORAGE_VERIFIED", False),
    )


def public_storage_health_payload(config: Any) -> dict[str, Any]:
    classification = classify_from_config(config)
    return {
        "storage_mode": classification["storage_mode"],
        "storage_path": classification["storage_path"],
        "durable_storage_verified": classification["durable_storage_verified"],
        "durable_storage_claim_allowed": classification["durable_storage_claim_allowed"],
        "ephemeral_storage": classification["ephemeral_storage"],
        "hosted_storage_boundary": classification["hosted_storage_boundary"],
        "storage_boundary_version": "0.83",
    }


def example_classifications() -> dict[str, dict[str, Any]]:
    return {
        "local_sqlite": classify_storage_mode(storage_path="reports/v083/storage_boundary.sqlite", api_mode="local_alpha"),
        "hosted_ephemeral_sqlite": classify_storage_mode(storage_path="/tmp/prmr_api_server.sqlite", api_mode="hosted_alpha"),
        "hosted_durable_sqlite": classify_storage_mode(
            storage_path="/var/data/prmr_api_server.sqlite",
            api_mode="hosted_alpha",
            storage_mode_override="hosted_durable_sqlite",
            durable_storage_verified=False,
        ),
        "hosted_managed_database_planned": classify_storage_mode(
            storage_path="postgres://planned-managed-database-placeholder",
            api_mode="hosted_alpha",
            storage_mode_override="hosted_managed_database_planned",
            durable_storage_verified=False,
        ),
        "unknown_storage_mode": classify_storage_mode(storage_path="", api_mode="hosted_alpha"),
    }
