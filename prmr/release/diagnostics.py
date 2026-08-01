"""Safe diagnostic archive with redacted configuration and content-free status."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import zipfile
from typing import Any

from prmr.core.runtime_migrations import detect_migration_drift, get_migration_status

from .identity import canonical_hash, get_core_revision_manifest, get_release_identity
from .logging import redact_operational_text
from .manifest import create_release_manifest
from .path_safety import normalise_output_path
from .version import RELEASE_DIAGNOSTICS_REVISION
from prmr.runtime_config import configuration_fingerprint, render_redacted_configuration
from prmr.runtime_health import collect_runtime_metrics, runtime_health, runtime_readiness


def collect_diagnostics(context: Any, destination: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    target = normalise_output_path(destination)
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    if target.exists() and not overwrite:
        raise FileExistsError("Diagnostic destination already exists.")
    target.parent.mkdir(parents=True, exist_ok=True)
    readiness = runtime_readiness(context).to_dict()
    payload = {
        "revision": RELEASE_DIAGNOSTICS_REVISION,
        "release_identity": get_release_identity(),
        "redacted_configuration": render_redacted_configuration(context.configuration),
        "configuration_fingerprint": configuration_fingerprint(context.configuration),
        "operating_system": platform.platform(),
        "database_backend": context.configuration.database_backend,
        "migration_status": {
            "applied_count": len(get_migration_status(context.repository)),
            "drift": detect_migration_drift(context.repository),
        },
        "health": runtime_health().to_dict(),
        "readiness": readiness,
        "runtime_metrics": collect_runtime_metrics(context),
        "core_revision_manifest": get_core_revision_manifest(),
        "recent_safe_error_codes": [readiness["safe_error_code"]] if readiness.get("safe_error_code") else [],
        "memory_content_included": False,
        "database_url_included": False,
        "credentials_included": False,
    }
    release = create_release_manifest()
    files = {
        "diagnostics.json": json.dumps(payload, indent=2, sort_keys=True) + "\n",
        "release_manifest.json": json.dumps(release, indent=2, sort_keys=True) + "\n",
    }
    manifest = {
        "files": [
            {"name": name, "sha256": hashlib.sha256(value.encode()).hexdigest()}
            for name, value in sorted(files.items())
        ],
        "memory_content_included": False,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    files["diagnostic_manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    temporary = target.with_name(f".{target.name}.partial")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "created",
        "archive": str(target),
        "manifest_hash": manifest["manifest_hash"],
        "file_count": len(files),
        "memory_content_included": False,
    }


__all__ = ["collect_diagnostics"]
