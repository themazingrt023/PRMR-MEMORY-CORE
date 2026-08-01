"""Safe release identity and deterministic Core revision discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

from prmr.core.memory_quality_policy import MEMORY_QUALITY_CORPUS_REVISION
from prmr.core.runtime_migrations import migration_registry

from .version import (
    ENGINE_NAME,
    HUMAN_VERSION,
    RELEASE_CHANNEL,
    RELEASE_SCHEMA_REVISION,
    SUPPORTED_DATABASE_BACKENDS,
    SUPPORTED_PACKET_VERSIONS,
    SUPPORTED_PYTHON,
    __version__,
)


BUILD_TIMESTAMP = "2026-08-01T00:00:00Z"
_REVISION_MODULES = (
    "prmr.core.source_models",
    "prmr.core.candidate_models",
    "prmr.core.admission_models",
    "prmr.core.memory_ledger_models",
    "prmr.core.memory_temporal_models",
    "prmr.core.entity_models",
    "prmr.core.relationship_models",
    "prmr.core.memory_query_models",
    "prmr.core.memory_consolidation_models",
    "prmr.core.interpretation_models",
    "prmr.core.canonical_signal_models",
    "prmr.core.memory_governance_models",
    "prmr.core.runtime_models",
    "prmr.core.memory_quality_models",
    "prmr.core.memory_quality_policy",
    "prmr.core.continuity_v2_models",
    "prmr.core.continuity_v2_policy",
)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def migration_registry_manifest() -> list[dict[str, Any]]:
    return [
        {
            "migration_id": item.migration_id,
            "checksum_sha256": item.checksum_sha256,
            "dependencies": list(item.dependencies),
            "resulting_schema_state": item.resulting_schema_state,
        }
        for item in migration_registry()
    ]


def get_core_revision_manifest() -> dict[str, Any]:
    revisions: dict[str, str] = {}
    duplicates: list[str] = []
    for module_name in _REVISION_MODULES:
        module = importlib.import_module(module_name)
        for name in sorted(dir(module)):
            if "REVISION" not in name or not name.isupper():
                continue
            value = getattr(module, name)
            if not isinstance(value, str):
                continue
            key = f"{module_name.rsplit('.', 1)[-1]}.{name}"
            if key in revisions:
                duplicates.append(key)
            revisions[key] = value
    ordered = dict(sorted(revisions.items()))
    payload = {
        "manifest_revision": "core_revision_manifest_v1",
        "revisions": ordered,
        "duplicate_keys": sorted(duplicates),
        "revision_count": len(ordered),
    }
    payload["core_revision_manifest_hash"] = canonical_hash(payload)
    return payload


def _safe_git_sha() -> str | None:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        return None
    try:
        value = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout.strip()
        return value if len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower()) else None
    except (OSError, subprocess.SubprocessError):
        return None


def get_release_identity() -> dict[str, Any]:
    migrations = migration_registry_manifest()
    core = get_core_revision_manifest()
    return {
        "engine_name": ENGINE_NAME,
        "human_version": HUMAN_VERSION,
        "package_version": __version__,
        "release_channel": RELEASE_CHANNEL,
        "git_commit_sha": _safe_git_sha(),
        "build_timestamp": BUILD_TIMESTAMP,
        "python_version": platform.python_version(),
        "python_executable_kind": "cpython" if sys.implementation.name == "cpython" else sys.implementation.name,
        "schema_revision": RELEASE_SCHEMA_REVISION,
        "migration_registry_hash": canonical_hash(migrations),
        "migration_count": len(migrations),
        "core_revision_manifest_hash": core["core_revision_manifest_hash"],
        "quality_corpus_revision": MEMORY_QUALITY_CORPUS_REVISION,
        "supported_packet_versions": list(SUPPORTED_PACKET_VERSIONS),
        "supported_database_backends": list(SUPPORTED_DATABASE_BACKENDS),
        "supported_python_versions": list(SUPPORTED_PYTHON),
    }


__all__ = [
    "BUILD_TIMESTAMP",
    "canonical_hash",
    "get_core_revision_manifest",
    "get_release_identity",
    "migration_registry_manifest",
]
