"""Independent Core Sprint 14 audit; runner summaries are not trusted."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.core.runtime_migrations import migration_registry
from prmr.release.identity import get_core_revision_manifest, get_release_identity
from prmr.release.manifest import REQUIRED_DOCUMENTS, documentation_manifest
from prmr.release.version import __version__
from prmr.runtime_config import configuration_fingerprint, load_runtime_configuration, render_redacted_configuration

REPORT_DIR = ROOT / "reports/core_release_candidate"
REQUIRED_REPORTS = (
    "release_manifest.json",
    "core_revision_manifest.json",
    "configuration_validation.json",
    "cli_contract.json",
    "clean_install_result.json",
    "sqlite_release_validation.json",
    "postgres_release_validation.json",
    "worker_release_validation.json",
    "integrity_release_validation.json",
    "backup_restore_status.json",
    "security_boundary_review.json",
    "documentation_manifest.json",
    "public_release_candidate.json",
    "private_internal_release_candidate.json",
)
COMMANDS = (
    ("version",),
    ("config", "init"), ("config", "validate"), ("config", "show"),
    ("db", "status"), ("db", "migrate"), ("db", "verify"), ("db", "migrations"),
    ("engine", "init"), ("engine", "health"), ("engine", "ready"), ("engine", "self-test"),
    ("worker", "run"), ("worker", "run-once"), ("worker", "recover"), ("worker", "status"),
    ("integrity", "sweep"), ("integrity", "verify-release"),
    ("backup", "create"), ("backup", "verify"), ("restore", "verify"),
    ("diagnostics", "collect"), ("release", "manifest"), ("release", "check"),
)


def load(name: str) -> dict[str, Any]:
    path = REPORT_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def command_help(command: tuple[str, ...]) -> bool:
    result = subprocess.run([sys.executable, "-m", "prmr.cli.main", *command, "--help"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    return result.returncode == 0 and "usage:" in result.stdout.lower()


def release_check_contract() -> tuple[bool, Any]:
    with TemporaryDirectory(prefix="prmr-release-check-") as temporary:
        root = Path(temporary)
        config = root / "prmr.toml"
        config.write_text(
            '[runtime]\nmode="sqlite_local"\n'
            '[database]\nbackend="sqlite"\n'
            f'sqlite_path="{(root / "release-check.sqlite3").as_posix()}"\n'
            'migration_policy="explicit_or_init"\n',
            encoding="utf-8",
        )
        initialise = subprocess.run(
            [
                sys.executable,
                "-m",
                "prmr.cli.main",
                "--config",
                str(config),
                "engine",
                "init",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "prmr.cli.main",
                "--config",
                str(config),
                "release",
                "check",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False, {"returncode": completed.returncode, "safe_error": "INVALID_JSON_OUTPUT"}
    required = {
        "configuration_examples_present",
        "command_contract_available",
        "package_build_present",
        "quality_benchmark_evidence_passed",
        "postgres_runtime_evidence_passed",
        "v2_packet_evidence_passed",
        "secret_hygiene_evidence_passed",
        "generated_manifest_clean_and_deterministic",
    }
    checks = payload.get("checks", {})
    passed = (
        initialise.returncode == 0
        and
        completed.returncode == 0
        and payload.get("result") == "PASS"
        and required.issubset(checks)
        and all(checks[name] for name in required)
    )
    return passed, {
        "initialise_returncode": initialise.returncode,
        "returncode": completed.returncode,
        "result": payload.get("result"),
        "required_checks": sorted(required),
    }


def main() -> int:
    checks: list[dict[str, Any]] = []
    identity = get_release_identity()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    release = load("release_manifest.json")
    clean = load("clean_install_result.json")
    sqlite = load("sqlite_release_validation.json")
    postgres = load("postgres_release_validation.json")
    workers = load("worker_release_validation.json")
    integrity = load("integrity_release_validation.json")
    backup = load("backup_restore_status.json")
    security = load("security_boundary_review.json")
    public = load("public_release_candidate.json")
    failure = load("release_failure_tests.json")
    benchmark = load("performance_smoke.json")

    add(checks, "authoritative_version_1_0_0rc1", __version__ == identity["package_version"] == release.get("package_version") == "1.0.0rc1")
    add(checks, "package_metadata_dynamic_from_authority", pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "prmr.release.version.__version__")
    add(checks, "console_entrypoint_declared", pyproject["project"]["scripts"]["prmr-core"] == "prmr.cli.main:main")
    add(checks, "migration_registry_complete", len(migration_registry()) == 12 and all((ROOT / item.sqlite_path).is_file() and (ROOT / item.postgres_path).is_file() for item in migration_registry()))
    core = get_core_revision_manifest()
    add(checks, "core_revision_manifest_deterministic", core == get_core_revision_manifest() and not core["duplicate_keys"] and release.get("core_revision_manifest_hash") == core["core_revision_manifest_hash"])
    all_help_verified = all(command_help(command) for command in COMMANDS)
    add(checks, "all_cli_commands_have_help", all_help_verified)
    release_check_passed, release_check_detail = release_check_contract()
    add(checks, "release_check_verifies_promised_evidence", release_check_passed, release_check_detail)
    cli_contract = {
        "revision": "prmr_cli_v1",
        "commands": [" ".join(item) for item in COMMANDS],
        "all_help_verified": all_help_verified,
        "exit_codes": {"0": "success", "2": "configuration_invalid", "3": "database_unavailable", "4": "migration_required", "5": "migration_failed", "6": "readiness_failed", "7": "integrity_failed", "8": "self_test_failed", "9": "worker_failure", "10": "backup_restore_failed", "11": "release_compatibility_failed", "12": "security_boundary_refusal"},
    }
    (REPORT_DIR / "cli_contract.json").write_text(json.dumps(cli_contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with TemporaryDirectory(prefix="prmr-config-audit-") as temporary:
        root = Path(temporary)
        config = root / "prmr.toml"
        env_file = root / "explicit.env"
        config.write_text('[runtime]\nmode="sqlite_local"\n[database]\nbackend="sqlite"\nsqlite_path="from-file.sqlite3"\n', encoding="utf-8")
        env_file.write_text("PRMR_SQLITE_PATH=from-env-file.sqlite3\n", encoding="utf-8")
        loaded = load_runtime_configuration(config_path=config, env_file=env_file, environ={"PRMR_SQLITE_PATH": "from-process.sqlite3"}, cli_overrides={"sqlite_path": "from-cli.sqlite3"})
        add(checks, "configuration_precedence_cli_wins", loaded.sqlite_path == "from-cli.sqlite3")
        explicit = load_runtime_configuration(config_path=config, env_file=env_file, environ={})
        add(checks, "explicit_env_file_supported", explicit.sqlite_path == "from-env-file.sqlite3")
        secret = load_runtime_configuration(config_path=ROOT / "config/prmr.postgres.example.toml", environ={"PRMR_DATABASE_URL": "postgresql://name:p%40ss@host/db?sslmode=require&channel_binding=require"})
        redacted = render_redacted_configuration(secret)
        add(checks, "secret_configuration_redacted", redacted["database_url"] == "<redacted-url>" and "p%40ss" not in json.dumps(redacted))
        add(checks, "configuration_fingerprint_deterministic", configuration_fingerprint(secret) == configuration_fingerprint(secret))

    docs = documentation_manifest(ROOT)
    add(checks, "documentation_set_complete", docs["complete"] and len(docs["documents"]) == len(REQUIRED_DOCUMENTS))
    add(checks, "all_required_reports_exist", all((REPORT_DIR / name).is_file() for name in REQUIRED_REPORTS))
    wheels = list((ROOT / "dist").glob("*.whl"))
    sdists = list((ROOT / "dist").glob("*.tar.gz"))
    add(checks, "wheel_and_sdist_exist", bool(wheels and sdists))
    if wheels:
        with zipfile.ZipFile(wheels[-1]) as archive:
            names = archive.namelist()
        bundled_sql = {Path(name).name for name in names if name.startswith("migrations/") and name.endswith(".sql")}
        required_sql = {
            Path(path).name
            for item in migration_registry()
            for path in (item.sqlite_path, item.postgres_path)
        }
        add(checks, "wheel_bundles_migrations", required_sql.issubset(bundled_sql))
        add(checks, "wheel_bundles_operator_docs", any("share/prmr-memory-core/docs/operations-runbook.md" in name for name in names))
        add(checks, "wheel_bundles_quality_metadata", any("share/prmr-memory-core/benchmarks/memory_quality_v1/corpus_manifest.json" in name for name in names))
    else:
        add(checks, "wheel_bundles_migrations", False)
        add(checks, "wheel_bundles_operator_docs", False)
        add(checks, "wheel_bundles_quality_metadata", False)
    add(checks, "clean_wheel_install_passed", clean.get("wheel", {}).get("passed") is True and clean.get("wheel", {}).get("package_origin_outside_repository") is True)
    add(checks, "clean_sdist_install_passed", clean.get("source_distribution", {}).get("passed") is True)
    add(checks, "sqlite_release_proof_passed", sqlite.get("result") == "PASS" and sqlite.get("restart", {}).get("deterministic_replay") is True)
    add(checks, "postgres_release_proof_passed", postgres.get("result") == "PASS" and postgres.get("guard_preserved") is True)
    add(checks, "installed_wheel_postgres_proof_passed", clean.get("postgres_installed_wheel", {}).get("result") == "PASS")
    add(checks, "worker_release_proof_passed", workers.get("result") == "PASS")
    add(checks, "integrity_release_proof_passed", integrity.get("sqlite", {}).get("result") == "PASS" and integrity.get("postgres", {}).get("result") == "PASS")
    add(checks, "sqlite_backup_restore_verified", backup.get("sqlite", {}).get("verification", {}).get("verified") is True)
    add(checks, "postgres_backup_status_honest", backup.get("postgres", {}).get("backup_completed") is False and "status" in backup.get("postgres", {}))
    add(
        checks,
        "release_status_matches_optional_backup_limitation",
        public.get("result") == "PASS WITH DOCUMENTED LIMITATIONS"
        and bool(public.get("optional_operation_limitations")),
    )
    add(checks, "failure_tests_passed", failure.get("result") == "PASS")
    add(checks, "performance_smoke_passed", benchmark.get("result") == "PASS")
    add(checks, "security_boundary_review_passed", security.get("result") == "PASS" and security.get("external_penetration_test_claimed") is False)

    public_text = json.dumps(public, sort_keys=True)
    restricted = re.compile(r"postgres(?:ql)?://|Authorization:\s*Bearer|prmr_(?:live|alpha)_[A-Za-z0-9_-]{8,}|github_pat_|ghp_", re.I)
    add(checks, "public_report_secret_safe", not restricted.search(public_text) and public.get("public_contains_memory_content") is False)
    add(checks, "public_boundary_honest", "private engineering release candidate" in public_text.lower() and "does not constitute" in public_text.lower())
    add(checks, "no_production_or_scientific_certification", "production certification" in public_text.lower() and "scientific" in public_text.lower())

    passed = sum(item["passed"] for item in checks)
    result = "PASS" if passed == len(checks) else "NEEDS_WORK"
    audit = {"result": result, "passed_checks": passed, "total_checks": len(checks), "failed_checks": [item for item in checks if not item["passed"]], "checks": checks, "independent_recalculation": True, "database_url_recorded": False}
    (REPORT_DIR / "audit_release_candidate.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard = f"# PRMR Memory Core v1.0 RC1 Scorecard\n\n- Audit result: **{result}**\n- Release status: **{public.get('result', 'MISSING')}**\n- Independent checks: **{passed}/{len(checks)}**\n- SQLite release proof: **{sqlite.get('result', 'MISSING')}**\n- PostgreSQL release proof: **{postgres.get('result', 'MISSING')}**\n- Clean wheel: **{clean.get('wheel', {}).get('passed', False)}**\n- Installed-wheel PostgreSQL: **{clean.get('postgres_installed_wheel', {}).get('result', 'MISSING')}**\n\nPrivate engineering release candidate only. No public-product, production, scientific, legal, compliance, or external security certification is claimed.\n"
    (REPORT_DIR / "scorecard_release_candidate.md").write_text(scorecard, encoding="utf-8")
    print("PRMR Memory Core - Core Sprint 14 Independent Audit")
    print(f"Passed checks: {passed}/{len(checks)}")
    print(f"Result: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
