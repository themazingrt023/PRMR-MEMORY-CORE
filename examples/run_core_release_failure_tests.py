"""RC1 safe failure and exit-code regression suite."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.runtime_config import load_runtime_configuration
from prmr.runtime_context import RuntimeContext, build_repository
from prmr.runtime_shutdown import ShutdownCoordinator

REPORT = ROOT / "reports/core_release_candidate/release_failure_tests.json"


def command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PRMR_DATABASE_URL", None)
    return subprocess.run([sys.executable, "-m", "prmr.cli.main", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)


def add(rows: list[dict[str, Any]], name: str, observed: bool, completed: subprocess.CompletedProcess[str] | None = None, expected_exit: int | None = None) -> None:
    rows.append(
        {
            "name": name,
            "passed": bool(observed),
            "expected_exit": expected_exit,
            "actual_exit": completed.returncode if completed else None,
            "output_secret_safe": not any(token in ((completed.stdout + completed.stderr) if completed else "").lower() for token in ("postgresql://", "prmr_live_", "authorization: bearer")),
        }
    )


def main() -> int:
    rows: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="prmr-rc1-failure-") as temporary:
        root = Path(temporary)
        missing = command(["--config", str(root / "missing.toml"), "config", "validate"], root)
        add(rows, "configuration_missing", missing.returncode == 2, missing, 2)

        malformed_path = root / "malformed.toml"
        malformed_path.write_text("[runtime\nmode = nope", encoding="utf-8")
        malformed = command(["--config", str(malformed_path), "config", "validate"], root)
        add(rows, "configuration_malformed", malformed.returncode == 2, malformed, 2)

        postgres_path = root / "postgres.toml"
        postgres_path.write_text('[runtime]\nmode="postgres_single_node"\n[database]\nbackend="postgres"\ndatabase_url_env="PRMR_DATABASE_URL"\n', encoding="utf-8")
        credentials = command(["--config", str(postgres_path), "config", "validate"], root)
        add(rows, "database_credentials_missing", credentials.returncode == 2, credentials, 2)

        sqlite_path = root / "sqlite.toml"
        database_path = root / "core.sqlite3"
        sqlite_path.write_text(f'[runtime]\nmode="sqlite_local"\n[database]\nbackend="sqlite"\nsqlite_path="{database_path.as_posix()}"\n', encoding="utf-8")
        behind = command(["--config", str(sqlite_path), "engine", "ready"], root)
        add(rows, "schema_behind_not_ready", behind.returncode == 6, behind, 6)

        init = command(["--config", str(sqlite_path), "engine", "init"], root)
        add(rows, "valid_initialisation_control", init.returncode == 0, init, 0)
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("UPDATE prmr_runtime_schema_migrations SET checksum_sha256='broken' WHERE migration_id='core_01_source_ledger_v1'")
            connection.commit()
        finally:
            connection.close()
        drift = command(["--config", str(sqlite_path), "db", "verify"], root)
        add(rows, "migration_checksum_mismatch", drift.returncode == 4, drift, 4)
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("DELETE FROM prmr_runtime_schema_migrations")
            connection.commit()
        finally:
            connection.close()
        command(["--config", str(sqlite_path), "db", "migrate"], root)

        multi = command(["--config", str(sqlite_path), "worker", "run", "--workers", "2", "--once"], root)
        add(rows, "sqlite_multi_worker_refused", multi.returncode == 12, multi, 12)

        existing_config = command(["config", "init", "--output", str(sqlite_path)], root)
        add(rows, "configuration_overwrite_refused", existing_config.returncode == 12, existing_config, 12)

        backup = root / "backup.sqlite3"
        first_backup = command(["--config", str(sqlite_path), "backup", "create", "--backend", "sqlite", "--destination", str(backup)], root)
        second_backup = command(["--config", str(sqlite_path), "backup", "create", "--backend", "sqlite", "--destination", str(backup)], root)
        add(rows, "backup_overwrite_refused", first_backup.returncode == 0 and second_backup.returncode == 12, second_backup, 12)

        diagnostic = root / "diagnostics.zip"
        diagnostic.write_bytes(b"existing")
        diagnostics = command(["--config", str(sqlite_path), "diagnostics", "collect", "--output", str(diagnostic)], root)
        add(rows, "diagnostics_overwrite_refused", diagnostics.returncode == 12, diagnostics, 12)

        restore = command(["restore", "verify", "--destination", str(backup), "--verification-mode", "sqlite"], root)
        add(rows, "restore_without_guard_refused", restore.returncode == 12, restore, 12)

        config = load_runtime_configuration(config_path=sqlite_path)
        context = RuntimeContext(config, build_repository(config), ready=True)
        coordinator = ShutdownCoordinator(context, graceful_timeout_seconds=0.001)
        coordinator.register_stopper(lambda: time.sleep(0.01))
        shutdown = coordinator.shutdown()
        add(rows, "shutdown_timeout_structured", shutdown["timeout_reached"] and "SHUTDOWN_TIMEOUT" in shutdown["safe_failure_codes"])

    passed = sum(row["passed"] and row["output_secret_safe"] for row in rows)
    result = "PASS" if passed == len(rows) else "NEEDS_WORK"
    payload = {"result": result, "passed_checks": passed, "total_checks": len(rows), "checks": rows, "raw_credentials_recorded": False}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PRMR Memory Core - RC1 Failure Tests")
    print(f"Passed checks: {passed}/{len(rows)}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
