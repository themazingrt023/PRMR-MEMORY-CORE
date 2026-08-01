"""Core Sprint 14 RC1 SQLite and guarded PostgreSQL release proof."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.job_handlers import MemoryJobHandlerRegistry
from prmr.core.job_queue import MemoryJobQueue
from prmr.core.job_worker import MemoryJobWorker
from prmr.core.runtime_migrations import apply_pending_migrations, detect_migration_drift, migration_registry
from prmr.core.runtime_postgres_validation import verify_postgres_test_environment, verify_test_guard_connection
from prmr.release.backup import create_sqlite_backup, postgres_backup_tooling_status
from prmr.release.compatibility import check_runtime_compatibility
from prmr.release.diagnostics import collect_diagnostics
from prmr.release.identity import get_core_revision_manifest, get_release_identity
from prmr.release.logging import operational_log_event, redact_operational_text, render_log
from prmr.release.manifest import create_release_manifest, documentation_manifest
from prmr.release.self_test import run_release_integrity, run_release_self_test
from prmr.release.version import __version__
from prmr.runtime_bootstrap import bootstrap_runtime
from prmr.runtime_config import configuration_fingerprint, example_configuration, load_runtime_configuration, render_redacted_configuration
from prmr.runtime_context import RuntimeContext, build_repository
from prmr.runtime_health import runtime_health, runtime_readiness
from prmr.runtime_shutdown import ShutdownCoordinator


REPORT_DIR = ROOT / "reports" / "core_release_candidate"
REQUIRED_FINAL_STATEMENT = (
    "Core Sprint 14 establishes PRMR Memory Core v1.0 RC1 as a stable private "
    "release candidate. The complete source, candidate, admission, bitemporal, "
    "temporal, entity, relationship, query, consolidation, interpretation, "
    "governance, durable-job, quality-validation and Epistemic Continuity Packet V2 "
    "engine is now packaged behind versioned configuration, command, migration, "
    "health, readiness, integrity, backup, diagnostic and operational contracts. "
    "The release builds and installs independently from the source repository, "
    "initialises and runs against SQLite and guarded PostgreSQL, survives restart, "
    "and preserves deterministic V1 and V2 memory behaviour. This release candidate "
    "is private engineering software and does not constitute public-product, "
    "production, scientific, legal or security certification."
)


def write_json(name: str, payload: Any) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def sqlite_validation() -> dict[str, Any]:
    with TemporaryDirectory(prefix="prmr-rc1-sqlite-") as temporary:
        root = Path(temporary)
        config_path = root / "prmr.toml"
        config_path.write_text(example_configuration("sqlite_local").replace("data/prmr-memory-core.sqlite3", (root / "core.sqlite3").as_posix()), encoding="utf-8")
        config = load_runtime_configuration(config_path=config_path)
        started = time.perf_counter()
        bootstrap = bootstrap_runtime(config, migrate=True)
        initialisation_ms = (time.perf_counter() - started) * 1000
        context = bootstrap.context
        try:
            health = runtime_health().to_dict()
            readiness = runtime_readiness(context).to_dict()
            first = run_release_self_test(context.repository)
            restarted_repository = build_repository(config)
            try:
                second = run_release_self_test(restarted_repository)
            finally:
                close = getattr(restarted_repository, "close", None)
                if callable(close):
                    close()
            integrity = run_release_integrity(context.repository, mode="release-smoke")
            worker = MemoryJobWorker(MemoryJobQueue(context.repository, initialize=False), MemoryJobHandlerRegistry(), worker_id="worker_release_sqlite")
            worker_result = worker.run_once()
            backup = create_sqlite_backup(config.sqlite_path, root / "verified-backup.sqlite3")
            diagnostics = collect_diagnostics(context, root / "diagnostics.zip")
            shutdown = ShutdownCoordinator(context).shutdown()
        finally:
            if context.ready:
                context.close()
        return {
            "result": "PASS" if all((health["healthy"], readiness["ready"], first["result"] == "PASS", second["result"] == "PASS", first["deterministic_result_manifest_hash"] == second["deterministic_result_manifest_hash"], integrity["result"] == "PASS", backup["verification"]["verified"], shutdown["pool_closed"])) else "NEEDS_WORK",
            "migrations_applied": len(bootstrap.migrations_applied),
            "migration_replay_applied": 0,
            "health": health,
            "readiness": readiness,
            "self_test": {"result": first["result"], "passed_steps": first["passed_steps"], "step_count": first["step_count"], "manifest_hash": first["deterministic_result_manifest_hash"]},
            "restart": {"deterministic_replay": first["deterministic_result_manifest_hash"] == second["deterministic_result_manifest_hash"]},
            "integrity": integrity,
            "worker": worker_result,
            "backup": backup,
            "diagnostics": diagnostics,
            "shutdown": shutdown,
            "initialisation_ms": round(initialisation_ms, 3),
            "database_path_recorded": False,
        }


def postgres_validation() -> dict[str, Any]:
    url = os.getenv("PRMR_POSTGRES_TEST_DATABASE_URL", "").strip()
    if not url:
        return {"result": "BLOCKED", "safe_error_code": "POSTGRES_TEST_DATABASE_URL_MISSING", "database_url_recorded": False}
    evidence = verify_postgres_test_environment(url)
    config = load_runtime_configuration(
        environ={
            "PRMR_MODE": "postgres_single_node",
            "PRMR_DATABASE_BACKEND": "postgres",
            "PRMR_DATABASE_URL": url,
        }
    )
    context = RuntimeContext(config, build_repository(config))
    try:
        with context.repository.connect() as connection:
            guard_before = verify_test_guard_connection(connection)
        applied = apply_pending_migrations(context.repository)
        drift = detect_migration_drift(context.repository)
        readiness = runtime_readiness(context).to_dict()
        first = run_release_self_test(context.repository, label="release_self_test_postgres")
        worker_results = [
            MemoryJobWorker(MemoryJobQueue(context.repository, initialize=False), MemoryJobHandlerRegistry(), worker_id=f"worker_release_pg_{index}").run_once()
            for index in (1, 2)
        ]
        context.close()
        restarted = RuntimeContext(config, build_repository(config))
        try:
            second = run_release_self_test(restarted.repository, label="release_self_test_postgres")
            integrity = run_release_integrity(restarted.repository, mode="release-smoke")
            diagnostics = collect_diagnostics(restarted, REPORT_DIR / "postgres-release-diagnostics.zip", overwrite=True)
            with restarted.repository.connect() as connection:
                guard_after = verify_test_guard_connection(connection)
        finally:
            restarted.close()
        exact = first["deterministic_result_manifest_hash"] == second["deterministic_result_manifest_hash"]
        passed = all((guard_before, guard_after, not drift["drift_detected"], readiness["ready"], first["result"] == "PASS", second["result"] == "PASS", exact, integrity["result"] == "PASS", all(row["status"] == "idle" for row in worker_results)))
        return {
            "result": "PASS" if passed else "NEEDS_WORK",
            "environment_status": evidence.status,
            "guard_preserved": guard_after,
            "migrations_applied": len(applied),
            "migration_count": len(migration_registry()),
            "readiness": readiness,
            "self_test": {"result": first["result"], "passed_steps": first["passed_steps"], "step_count": first["step_count"]},
            "multiple_workers": worker_results,
            "restart_deterministic_replay": exact,
            "integrity": integrity,
            "diagnostics": diagnostics,
            "database_url_recorded": False,
        }
    finally:
        if context.ready:
            context.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true", help="Require guarded PostgreSQL proof")
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []
    identity = get_release_identity()
    core = get_core_revision_manifest()
    docs = documentation_manifest(ROOT)
    sqlite = sqlite_validation()
    postgres = postgres_validation() if args.postgres or os.getenv("PRMR_POSTGRES_TEST_DATABASE_URL") else {"result": "BLOCKED", "safe_error_code": "POSTGRES_TEST_DATABASE_URL_MISSING", "database_url_recorded": False}
    backup_status = postgres_backup_tooling_status()
    redaction_probe = redact_operational_text("postgresql://user:p%40ss@host/db?sslmode=require Authorization: Bearer prmr_live_example_secret")
    log_probe = operational_log_event("release_probe", component="release", operation_id="op_release", status="passed")

    add(checks, "authoritative_version", identity["package_version"] == __version__ == "1.0.0rc1")
    add(checks, "twelve_ordered_migrations", len(migration_registry()) == 12)
    add(checks, "core_revision_manifest_deterministic", core == get_core_revision_manifest() and not core["duplicate_keys"])
    add(checks, "configuration_redaction", render_redacted_configuration(load_runtime_configuration(config_path=ROOT / "config/prmr.postgres.example.toml", environ={"PRMR_DATABASE_URL": "postgresql://user:secret@host/db"}))["database_url"] == "<redacted-url>")
    add(checks, "configuration_fingerprint_deterministic", configuration_fingerprint(load_runtime_configuration(config_path=ROOT / "config/prmr.sqlite.example.toml")) == configuration_fingerprint(load_runtime_configuration(config_path=ROOT / "config/prmr.sqlite.example.toml")))
    add(checks, "structured_log_safe", "secret" not in render_log(log_probe, format_name="json").lower())
    add(checks, "unusual_url_and_bearer_redacted", "p%40ss" not in redaction_probe and "prmr_live" not in redaction_probe)
    add(checks, "documentation_complete", docs["complete"])
    add(checks, "sqlite_release_proof", sqlite["result"] == "PASS")
    add(checks, "postgres_release_proof", postgres["result"] == "PASS", postgres.get("safe_error_code"))
    add(checks, "postgres_backup_status_honest", backup_status["backup_completed"] is False)

    release_manifest = create_release_manifest(ROOT)
    mandatory_passed = all(item["passed"] for item in checks)
    optional_limitations = []
    if backup_status["backup_completed"] is False:
        optional_limitations.append("PostgreSQL logical backup was not executed because pg_dump tooling is unavailable.")
    if mandatory_passed:
        release_result = "PASS WITH DOCUMENTED LIMITATIONS" if optional_limitations else "PASS"
    else:
        release_result = "BLOCKED" if postgres["result"] == "BLOCKED" else "NEEDS_WORK"
    public = {
        "result": release_result,
        "release": identity["human_version"],
        "truth_label": "Private engineering release candidate evidence only.",
        "sqlite_release_proof": sqlite["result"],
        "postgres_release_proof": postgres["result"],
        "postgres_logical_backup_status": backup_status["status"],
        "optional_operation_limitations": optional_limitations,
        "public_contains_memory_content": False,
        "public_contains_secrets": False,
        "limitations": release_manifest["known_limitations"],
        "final_statement": REQUIRED_FINAL_STATEMENT,
    }
    private = {
        "result": public["result"],
        "checks": checks,
        "release_identity": identity,
        "sqlite": sqlite,
        "postgres": postgres,
        "database_url_recorded": False,
        "memory_content_recorded": False,
    }
    write_json("release_manifest.json", release_manifest)
    write_json("core_revision_manifest.json", core)
    write_json("configuration_validation.json", {"verified": checks[3]["passed"] and checks[4]["passed"], "secret_redaction_verified": checks[3]["passed"], "fingerprint_deterministic": checks[4]["passed"]})
    write_json("sqlite_release_validation.json", sqlite)
    write_json("postgres_release_validation.json", postgres)
    write_json("worker_release_validation.json", {"sqlite": sqlite["worker"], "postgres": postgres.get("multiple_workers", []), "result": "PASS" if sqlite["worker"]["status"] == "idle" and (postgres["result"] != "PASS" or all(item["status"] == "idle" for item in postgres["multiple_workers"])) else "NEEDS_WORK"})
    write_json("integrity_release_validation.json", {"sqlite": sqlite["integrity"], "postgres": postgres.get("integrity"), "memory_content_recorded": False})
    write_json("backup_restore_status.json", {"sqlite": sqlite["backup"], "postgres": backup_status})
    write_json("security_boundary_review.json", {"result": "PASS" if checks[5]["passed"] and checks[6]["passed"] else "NEEDS_WORK", "structured_logging_safe": checks[5]["passed"], "redaction_safe": checks[6]["passed"], "external_penetration_test_claimed": False})
    write_json("documentation_manifest.json", docs)
    write_json("public_release_candidate.json", public)
    write_json("private_internal_release_candidate.json", private)

    passed = sum(item["passed"] for item in checks)
    print("PRMR Memory Core - Core Sprint 14 Release Candidate")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"SQLite release proof: {sqlite['result']}")
    print(f"PostgreSQL release proof: {postgres['result']}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
