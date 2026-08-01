"""Safe SQLite backup and honest PostgreSQL tooling status."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from prmr.core.continuity_v2_packet import ContinuityPacketV2Service
from prmr.core.source_models import AuthenticatedScope

from .identity import get_release_identity
from .path_safety import atomic_write_bytes, normalise_output_path
from .version import RELEASE_BACKUP_REVISION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_sqlite_backup(
    source_path: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    target = normalise_output_path(destination)
    if not source.is_file():
        raise FileNotFoundError("Configured SQLite database does not exist.")
    if target == source:
        raise ValueError("Backup destination must differ from the active database.")
    if target.exists() and not overwrite:
        raise FileExistsError("Backup destination already exists.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.partial")
    if temporary.exists():
        temporary.unlink()
    try:
        live = sqlite3.connect(source)
        backup = sqlite3.connect(temporary)
        try:
            live.execute("PRAGMA wal_checkpoint(PASSIVE)")
            live.backup(backup)
            backup.commit()
        finally:
            backup.close()
            live.close()
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    verification = verify_sqlite_backup(target)
    manifest = {
        "revision": RELEASE_BACKUP_REVISION,
        "backend": "sqlite",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "backup_file": target.name,
        "sha256": _sha256(target),
        "size_bytes": target.stat().st_size,
        "release_identity": get_release_identity(),
        "verification": verification,
        "source_path_recorded": False,
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    atomic_write_bytes(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        overwrite=overwrite,
    )
    return {**manifest, "manifest_file": manifest_path.name}


def verify_sqlite_backup(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    connection = sqlite3.connect(target)
    try:
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        migration_count = int(connection.execute("SELECT COUNT(*) FROM prmr_runtime_schema_migrations").fetchone()[0])
        packet_row = connection.execute(
            "SELECT packet_id,client_id,vault_id,namespace FROM prmr_continuity_packets_v2 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    v2_replay_verified = None
    if packet_row:
        from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093

        repository = SelfServeRepositoryV093(target)
        scope = AuthenticatedScope(str(packet_row["client_id"]), str(packet_row["vault_id"]), str(packet_row["namespace"]))
        packet = ContinuityPacketV2Service(repository, initialize=False).replay_packet_v2(scope, str(packet_row["packet_id"]))
        v2_replay_verified = bool(ContinuityPacketV2Service(repository, initialize=False).verify_packet_v2_integrity(scope, packet.packet_id).verified)
    return {
        "verified": integrity == "ok" and migration_count > 0 and v2_replay_verified is not False,
        "sqlite_integrity": integrity,
        "migration_count": migration_count,
        "representative_query_passed": migration_count > 0,
        "v2_packet_present": bool(packet_row),
        "v2_packet_replay_verified": v2_replay_verified,
    }


def postgres_backup_tooling_status() -> dict[str, Any]:
    pg_dump = shutil.which("pg_dump")
    restore = shutil.which("pg_restore") or shutil.which("psql")
    if not pg_dump or not restore:
        return {
            "status": "POSTGRES_LOGICAL_BACKUP_NOT_RUN_TOOLING_UNAVAILABLE",
            "pg_dump_available": bool(pg_dump),
            "restore_tool_available": bool(restore),
            "backup_completed": False,
        }
    return {
        "status": "POSTGRES_LOGICAL_BACKUP_TOOLING_AVAILABLE_NOT_EXECUTED",
        "pg_dump_available": True,
        "restore_tool_available": True,
        "backup_completed": False,
    }


__all__ = ["create_sqlite_backup", "postgres_backup_tooling_status", "verify_sqlite_backup"]
