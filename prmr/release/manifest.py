"""Deterministic public-safe release and documentation manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .identity import canonical_hash, get_core_revision_manifest, get_release_identity
from .version import (
    RELEASE_CLI_REVISION,
    RELEASE_CONFIGURATION_REVISION,
    RELEASE_MANIFEST_REVISION,
)


REQUIRED_DOCUMENTS = (
    "README.md",
    "docs/architecture.md",
    "docs/configuration.md",
    "docs/installation.md",
    "docs/sqlite-operations.md",
    "docs/postgres-operations.md",
    "docs/migrations.md",
    "docs/workers.md",
    "docs/integrity.md",
    "docs/backup-and-restore.md",
    "docs/governance.md",
    "docs/continuity-packet-v1.md",
    "docs/continuity-packet-v2.md",
    "docs/security-boundaries.md",
    "docs/troubleshooting.md",
    "docs/release-process.md",
    "docs/known-limitations.md",
    "docs/operations-runbook.md",
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def documentation_manifest(root: Path) -> dict[str, Any]:
    documents = []
    for relative in REQUIRED_DOCUMENTS:
        path = root / relative
        documents.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": _hash_file(path) if path.is_file() else None,
            }
        )
    payload = {"documents": documents, "complete": all(item["exists"] for item in documents)}
    payload["documentation_manifest_hash"] = canonical_hash(payload)
    return payload


def dependency_manifest_hash(root: Path) -> str:
    files = [root / name for name in ("pyproject.toml", "requirements-runtime.txt", "requirements-postgres.txt", "requirements-dev.txt")]
    return canonical_hash([{"name": path.name, "sha256": _hash_file(path)} for path in files if path.is_file()])


def build_artifact_hashes(root: Path) -> list[dict[str, str]]:
    dist = root / "dist"
    return [
        {"name": path.name, "sha256": _hash_file(path)}
        for path in sorted(dist.glob("*"))
        if path.is_file()
    ] if dist.is_dir() else []


def create_release_manifest(root: Path | None = None) -> dict[str, Any]:
    base = (root or Path.cwd()).resolve()
    identity = get_release_identity()
    core = get_core_revision_manifest()
    docs = documentation_manifest(base)
    payload = {
        "release_manifest_revision": RELEASE_MANIFEST_REVISION,
        "release_name": identity["human_version"],
        "package_version": identity["package_version"],
        "git_commit_sha": identity["git_commit_sha"],
        "build_timestamp": identity["build_timestamp"],
        "python_support": identity["supported_python_versions"],
        "database_support": identity["supported_database_backends"],
        "migration_registry_hash": identity["migration_registry_hash"],
        "schema_revision": identity["schema_revision"],
        "core_revision_manifest_hash": core["core_revision_manifest_hash"],
        "packet_revisions": identity["supported_packet_versions"],
        "benchmark_revisions": [identity["quality_corpus_revision"]],
        "quality_result_summary": "Core Sprint 12 evidence is referenced, not bundled as runtime state.",
        "postgres_validation_summary": "Guarded PostgreSQL proof is release evidence and contains no connection data.",
        "command_contract_revision": RELEASE_CLI_REVISION,
        "configuration_revision": RELEASE_CONFIGURATION_REVISION,
        "dependency_manifest_hash": dependency_manifest_hash(base),
        "build_artifact_hashes": build_artifact_hashes(base),
        "documentation_manifest_hash": docs["documentation_manifest_hash"],
        "known_limitations": [
            "Private release candidate; no production certification.",
            "SQLite supports bounded single-node operation only.",
            "PostgreSQL logical backup requires external pg_dump tooling.",
            "No automatic failover, multi-region durability or external security validation.",
        ],
    }
    payload["release_manifest_hash"] = canonical_hash(payload)
    return payload


__all__ = ["REQUIRED_DOCUMENTS", "create_release_manifest", "documentation_manifest"]
