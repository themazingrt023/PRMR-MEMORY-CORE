"""Stable `prmr-core` RC1 command contract."""

from __future__ import annotations

import argparse
from enum import IntEnum
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Sequence

from prmr.core.job_handlers import MemoryJobHandlerRegistry
from prmr.core.job_queue import MemoryJobQueue
from prmr.core.job_recovery import MemoryJobRecovery
from prmr.core.job_worker import MemoryJobWorker
from prmr.core.runtime_migrations import (
    apply_pending_migrations,
    detect_migration_drift,
    get_migration_status,
    migration_registry,
    verify_schema_revision,
)
from prmr.release.backup import create_sqlite_backup, postgres_backup_tooling_status, verify_sqlite_backup
from prmr.release.compatibility import check_runtime_compatibility
from prmr.release.diagnostics import collect_diagnostics
from prmr.release.identity import get_core_revision_manifest, get_release_identity, migration_registry_manifest
from prmr.release.manifest import create_release_manifest, documentation_manifest
from prmr.release.self_test import run_release_integrity, run_release_self_test
from prmr.release.version import HUMAN_VERSION, RELEASE_CLI_REVISION, __version__
from prmr.runtime_bootstrap import bootstrap_runtime
from prmr.runtime_config import (
    ConfigurationError,
    configuration_fingerprint,
    example_configuration,
    load_runtime_configuration,
    render_redacted_configuration,
)
from prmr.runtime_context import RuntimeContext, build_repository
from prmr.runtime_health import collect_runtime_metrics, runtime_health, runtime_readiness
from prmr.runtime_shutdown import ShutdownCoordinator


RELEASE_COMMAND_CONTRACT = (
    ("version",),
    ("config", "init"), ("config", "validate"), ("config", "show"),
    ("db", "status"), ("db", "migrate"), ("db", "verify"), ("db", "migrations"),
    ("engine", "init"), ("engine", "health"), ("engine", "ready"), ("engine", "self-test"),
    ("worker", "run"), ("worker", "run-once"), ("worker", "recover"), ("worker", "status"),
    ("integrity", "sweep"), ("integrity", "verify-release"),
    ("backup", "create"), ("backup", "verify"), ("restore", "verify"),
    ("diagnostics", "collect"), ("release", "manifest"), ("release", "check"),
)


def _json_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _parser_command_paths(parser: argparse.ArgumentParser) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for group, group_parser in action.choices.items():
            nested = [
                candidate
                for candidate in group_parser._actions
                if isinstance(candidate, argparse._SubParsersAction)
            ]
            if not nested:
                paths.add((group,))
                continue
            for nested_action in nested:
                paths.update((group, command) for command in nested_action.choices)
    return paths


def _installed_package_metadata_matches() -> bool:
    try:
        return metadata.version("prmr-memory-core") == __version__
    except metadata.PackageNotFoundError:
        return False


def _release_evidence_checks(root: Path) -> dict[str, bool]:
    report_root = root / "reports"
    quality = _json_report(report_root / "core_memory_quality/public_memory_quality.json")
    postgres = _json_report(report_root / "core_runtime_hardening/postgres_runtime_matrix.json")
    packet_v2 = _json_report(report_root / "core_continuity_packet_v2/public_continuity_packet_v2.json")
    secret = _json_report(report_root / "v0782/public_secret_cleanup_v0782.json")
    config_examples = (
        root / "config/prmr.sqlite.example.toml",
        root / "config/prmr.postgres.example.toml",
        root / "config/prmr.worker.example.toml",
    )
    manifest = create_release_manifest(root)
    artifacts = root / "dist"
    return {
        "configuration_examples_present": all(path.is_file() for path in config_examples),
        "command_contract_available": set(RELEASE_COMMAND_CONTRACT).issubset(_parser_command_paths(_parser())),
        "package_build_present": (
            bool(list(artifacts.glob("*.whl")) and list(artifacts.glob("*.tar.gz")))
            or _installed_package_metadata_matches()
        ),
        "quality_benchmark_evidence_passed": quality.get("result") in {"PASS", "PASS WITH DOCUMENTED LIMITATIONS"},
        "postgres_runtime_evidence_passed": postgres.get("result") == "PASS_FULL_POSTGRES_MATRIX",
        "v2_packet_evidence_passed": packet_v2.get("result") == "PASS",
        "secret_hygiene_evidence_passed": secret.get("result") == "PASS",
        "generated_manifest_clean_and_deterministic": (
            manifest == create_release_manifest(root) and bool(manifest.get("release_manifest_hash"))
        ),
    }


class ExitCode(IntEnum):
    SUCCESS = 0
    CONFIGURATION_INVALID = 2
    DATABASE_UNAVAILABLE = 3
    MIGRATION_REQUIRED = 4
    MIGRATION_FAILED = 5
    READINESS_FAILED = 6
    INTEGRITY_FAILED = 7
    SELF_TEST_FAILED = 8
    WORKER_FAILURE = 9
    BACKUP_RESTORE_FAILED = 10
    RELEASE_COMPATIBILITY_FAILED = 11
    SECURITY_BOUNDARY_REFUSAL = 12


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prmr-core", description=HUMAN_VERSION)
    parser.add_argument("--config", help="Explicit prmr.toml path")
    parser.add_argument("--env-file", help="Explicit environment file; never loaded implicitly")
    parser.add_argument("--json", action="store_true", dest="json_output")
    groups = parser.add_subparsers(dest="group", required=True)

    groups.add_parser("version")

    config = groups.add_parser("config")
    config_sub = config.add_subparsers(dest="command", required=True)
    init = config_sub.add_parser("init")
    init.add_argument("--mode", choices=("sqlite_local", "postgres_single_node"), default="sqlite_local")
    init.add_argument("--output", default="prmr.toml")
    init.add_argument("--force", action="store_true")
    config_sub.add_parser("validate")
    show = config_sub.add_parser("show")
    show.add_argument("--redacted", action="store_true", required=True)

    database = groups.add_parser("db")
    database_sub = database.add_subparsers(dest="command", required=True)
    database_sub.add_parser("status")
    migrate = database_sub.add_parser("migrate")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--verify-only", action="store_true")
    migrate.add_argument("--json", action="store_true", dest="local_json")
    database_sub.add_parser("verify")
    database_sub.add_parser("migrations")

    engine = groups.add_parser("engine")
    engine_sub = engine.add_subparsers(dest="command", required=True)
    engine_sub.add_parser("init")
    engine_sub.add_parser("health")
    engine_sub.add_parser("ready")
    engine_sub.add_parser("self-test")

    worker = groups.add_parser("worker")
    worker_sub = worker.add_subparsers(dest="command", required=True)
    run = worker_sub.add_parser("run")
    run.add_argument("--workers", type=int, default=None)
    run.add_argument("--once", action="store_true")
    run.add_argument("--until-idle", action="store_true")
    run.add_argument("--job-type")
    run.add_argument("--poll-interval", type=float)
    run.add_argument("--graceful-timeout", type=float)
    worker_sub.add_parser("run-once")
    worker_sub.add_parser("recover")
    worker_sub.add_parser("status")

    integrity = groups.add_parser("integrity")
    integrity_sub = integrity.add_subparsers(dest="command", required=True)
    sweep = integrity_sub.add_parser("sweep")
    sweep.add_argument("--mode", choices=("sampled", "full-scope", "release-smoke"), default="release-smoke")
    sweep.add_argument("--scope")
    sweep.add_argument("--fail-fast", action="store_true")
    sweep.add_argument("--report")
    integrity_sub.add_parser("verify-release")

    backup = groups.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="command", required=True)
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("--backend", choices=("sqlite", "postgres"), required=True)
    backup_create.add_argument("--destination")
    backup_create.add_argument("--force", action="store_true")
    backup_verify = backup_sub.add_parser("verify")
    backup_verify.add_argument("--path", required=True)

    restore = groups.add_parser("restore")
    restore_sub = restore.add_subparsers(dest="command", required=True)
    restore_verify = restore_sub.add_parser("verify")
    restore_verify.add_argument("--destination", required=True)
    restore_verify.add_argument("--verification-mode", choices=("sqlite", "postgres"), required=True)
    restore_verify.add_argument("--allow-destructive-test", action="store_true")

    diagnostics = groups.add_parser("diagnostics")
    diagnostics_sub = diagnostics.add_subparsers(dest="command", required=True)
    collect = diagnostics_sub.add_parser("collect")
    collect.add_argument("--output", required=True)
    collect.add_argument("--force", action="store_true")

    release = groups.add_parser("release")
    release_sub = release.add_subparsers(dest="command", required=True)
    release_sub.add_parser("manifest")
    release_sub.add_parser("check")
    return parser


def _configuration(args: argparse.Namespace, *, allow_missing_database_url: bool = False):
    return load_runtime_configuration(
        config_path=args.config,
        env_file=args.env_file,
        require_database_url=not allow_missing_database_url,
    )


def _emit(payload: Any, args: argparse.Namespace) -> None:
    if args.json_output or getattr(args, "local_json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list, tuple)):
                print(f"{key}: {json.dumps(value, sort_keys=True, default=str)}")
            else:
                print(f"{key}: {value}")
    else:
        print(payload)


def _repository(args: argparse.Namespace):
    config = _configuration(args)
    return config, build_repository(config)


def _db_status(config: Any, repository: Any) -> dict[str, Any]:
    status = get_migration_status(repository)
    registry = migration_registry()
    applied = {row["migration_id"] for row in status}
    drift = detect_migration_drift(repository)
    pool = getattr(repository, "pool_stats", lambda: {})()
    return {
        "configured_backend": config.database_backend,
        "connection_available": True,
        "schema_revision": status[-1]["resulting_schema_state"] if status else None,
        "migration_registry_hash": get_release_identity()["migration_registry_hash"],
        "applied_migration_count": len(status),
        "pending_migration_count": sum(item.migration_id not in applied for item in registry),
        "drift_status": "drift_detected" if drift["drift_detected"] else "clean",
        "pool_status": pool,
        "database_metadata": {"backend": config.database_backend},
        "release_compatibility": check_runtime_compatibility(repository),
        "database_url_recorded": False,
    }


def _handle(args: argparse.Namespace) -> int:
    if args.group == "version":
        _emit({**get_release_identity(), "cli_revision": RELEASE_CLI_REVISION}, args)
        return ExitCode.SUCCESS

    if args.group == "config":
        if args.command == "init":
            target = Path(args.output).expanduser().resolve()
            if target.exists() and not args.force:
                raise FileExistsError("Configuration already exists; use --force to replace it.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(example_configuration(args.mode), encoding="utf-8")
            _emit({"status": "created", "path": str(target), "contains_secrets": False}, args)
            return ExitCode.SUCCESS
        config = _configuration(args)
        if args.command == "validate":
            _emit({"status": "valid", "fingerprint": configuration_fingerprint(config)}, args)
        else:
            _emit(render_redacted_configuration(config), args)
        return ExitCode.SUCCESS

    if args.group == "db":
        config, repository = _repository(args)
        try:
            if args.command == "migrations":
                _emit({"migrations": migration_registry_manifest()}, args)
            elif args.command == "status":
                _emit(_db_status(config, repository), args)
            elif args.command == "verify":
                drift = detect_migration_drift(repository)
                _emit({"verified": not drift["drift_detected"], "drift": drift}, args)
                return ExitCode.SUCCESS if not drift["drift_detected"] else ExitCode.MIGRATION_REQUIRED
            else:
                status = get_migration_status(repository)
                applied_ids = {row["migration_id"] for row in status}
                pending = [item.migration_id for item in migration_registry() if item.migration_id not in applied_ids]
                if args.dry_run:
                    _emit({"dry_run": True, "pending": pending, "database_modified": False}, args)
                elif args.verify_only:
                    drift = detect_migration_drift(repository)
                    _emit({"verify_only": True, "drift": drift}, args)
                    return ExitCode.SUCCESS if not drift["drift_detected"] else ExitCode.MIGRATION_REQUIRED
                else:
                    applied = apply_pending_migrations(repository)
                    _emit({"applied": applied, "applied_count": len(applied), "destructive": False}, args)
            return ExitCode.SUCCESS
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()

    if args.group == "engine":
        if args.command == "health":
            _emit(runtime_health().to_dict(), args)
            return ExitCode.SUCCESS
        config = _configuration(args)
        if args.command == "init":
            started = time.perf_counter()
            result = bootstrap_runtime(config, migrate=True)
            try:
                _emit({"status": "initialised", "phases": result.phases, "migrations_applied": result.migrations_applied, "duration_ms": round((time.perf_counter()-started)*1000, 3)}, args)
            finally:
                result.context.close()
            return ExitCode.SUCCESS
        context = RuntimeContext(config, build_repository(config))
        try:
            if args.command == "ready":
                result = runtime_readiness(context).to_dict()
                _emit(result, args)
                return ExitCode.SUCCESS if result["ready"] else ExitCode.READINESS_FAILED
            result = run_release_self_test(context.repository)
            _emit(result, args)
            return ExitCode.SUCCESS if result["result"] == "PASS" else ExitCode.SELF_TEST_FAILED
        finally:
            context.close()

    if args.group == "worker":
        config, repository = _repository(args)
        context = RuntimeContext(config, repository, ready=True)
        try:
            workers = getattr(args, "workers", None) or config.worker.workers
            if config.database_backend == "sqlite" and workers > 1:
                _emit({"status": "refused", "safe_error_code": "SQLITE_MULTI_WORKER_UNSUPPORTED"}, args)
                return ExitCode.SECURITY_BOUNDARY_REFUSAL
            queue = MemoryJobQueue(repository, initialize=False)
            registry = MemoryJobHandlerRegistry()
            if args.command == "status":
                _emit(collect_runtime_metrics(context), args)
                return ExitCode.SUCCESS
            if args.command == "recover":
                result = MemoryJobRecovery(queue, registry).recover_until_idle()
                _emit(result, args)
                return ExitCode.SUCCESS
            worker = MemoryJobWorker(queue, registry, worker_id="worker_release_cli_1")
            if args.command == "run-once" or getattr(args, "once", False):
                result = worker.run_once()
            elif getattr(args, "until_idle", False):
                result = worker.run_until_idle()
            else:
                coordinator = ShutdownCoordinator(context, getattr(args, "graceful_timeout", None) or config.worker.graceful_timeout_seconds)
                coordinator.register_stopper(worker.stop_gracefully)
                coordinator.install_signal_handlers()
                try:
                    worker.start_polling()
                    result = {"status": "stopped"}
                finally:
                    coordinator.shutdown()
            _emit(result, args)
            terminal_status = str(result.get("status", "")) if isinstance(result, dict) else ""
            return ExitCode.WORKER_FAILURE if terminal_status in {"dead_letter", "failed", "worker_crashed"} else ExitCode.SUCCESS
        finally:
            context.close()

    if args.group == "integrity":
        config, repository = _repository(args)
        try:
            mode = getattr(args, "mode", "release-smoke")
            result = run_release_integrity(repository, mode=mode)
            report = getattr(args, "report", None)
            if report:
                target = Path(report).expanduser().resolve()
                if target.exists():
                    raise FileExistsError("Integrity report already exists.")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _emit(result, args)
            return ExitCode.SUCCESS if result["result"] == "PASS" else ExitCode.INTEGRITY_FAILED
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()

    if args.group == "backup":
        config = _configuration(args)
        if args.command == "verify":
            result = verify_sqlite_backup(args.path)
        elif args.backend == "postgres":
            result = postgres_backup_tooling_status()
        else:
            destination = args.destination or str(Path(config.sqlite_path).with_suffix(".backup.sqlite3"))
            result = create_sqlite_backup(config.sqlite_path, destination, overwrite=args.force)
        _emit(result, args)
        verified = result.get("verified")
        if verified is None and isinstance(result.get("verification"), dict):
            verified = result["verification"].get("verified")
        if verified is None:
            verified = result.get("status") is not None
        return ExitCode.SUCCESS if verified else ExitCode.BACKUP_RESTORE_FAILED

    if args.group == "restore":
        if not args.allow_destructive_test:
            _emit({"status": "refused", "safe_error_code": "RESTORE_VERIFICATION_GUARD_REQUIRED"}, args)
            return ExitCode.SECURITY_BOUNDARY_REFUSAL
        if args.verification_mode == "sqlite":
            result = verify_sqlite_backup(args.destination)
        else:
            result = {"verified": False, "status": "POSTGRES_RESTORE_VERIFICATION_REQUIRES_ISOLATED_OPERATOR_DESTINATION"}
        _emit(result, args)
        return ExitCode.SUCCESS if result.get("verified") else ExitCode.BACKUP_RESTORE_FAILED

    if args.group == "diagnostics":
        config = _configuration(args)
        context = RuntimeContext(config, build_repository(config))
        try:
            result = collect_diagnostics(context, args.output, overwrite=args.force)
            _emit(result, args)
            return ExitCode.SUCCESS
        finally:
            context.close()

    if args.group == "release":
        root = Path.cwd()
        if args.command == "manifest":
            _emit(create_release_manifest(root), args)
            return ExitCode.SUCCESS
        config, repository = _repository(args)
        try:
            docs = documentation_manifest(root)
            self_test = run_release_self_test(repository)
            integrity = run_release_integrity(repository)
            checks = {
                "version_consistent": get_release_identity()["package_version"] == __version__,
                "package_metadata_present": (root / "pyproject.toml").is_file() or _installed_package_metadata_matches(),
                "migration_registry_valid": len(migration_registry()) == 12,
                "core_revision_manifest_valid": not get_core_revision_manifest()["duplicate_keys"],
                "documentation_complete": docs["complete"] if (root / "docs").is_dir() else True,
                "self_test_passed": self_test["result"] == "PASS",
                "integrity_passed": integrity["result"] == "PASS",
                **_release_evidence_checks(root),
            }
            result = {"result": "PASS" if all(checks.values()) else "NEEDS_WORK", "checks": checks}
            _emit(result, args)
            return ExitCode.SUCCESS if result["result"] == "PASS" else ExitCode.RELEASE_COMPATIBILITY_FAILED
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()
    raise AssertionError("unreachable")


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--json" in raw and raw[:1] != ["--json"]:
        raw.remove("--json")
        raw.insert(0, "--json")
    parser = _parser()
    args = parser.parse_args(raw)
    try:
        return int(_handle(args))
    except ConfigurationError as exc:
        _emit({"status": "failed", "safe_error_code": exc.code, "message": str(exc)}, args)
        return int(ExitCode.CONFIGURATION_INVALID)
    except FileExistsError as exc:
        _emit({"status": "refused", "safe_error_code": "UNSAFE_OVERWRITE_REFUSED", "message": str(exc)}, args)
        return int(ExitCode.SECURITY_BOUNDARY_REFUSAL)
    except Exception as exc:
        code = str(getattr(exc, "code", type(exc).__name__.upper()))
        safe = {
            "status": "failed",
            "safe_error_code": code,
            "message": "Command failed safely; use diagnostics for bounded operational evidence.",
        }
        _emit(safe, args)
        if "MIGRATION" in code:
            return int(ExitCode.MIGRATION_FAILED)
        if "POSTGRES" in code or "DATABASE" in code:
            return int(ExitCode.DATABASE_UNAVAILABLE)
        return int(ExitCode.RELEASE_COMPATIBILITY_FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
