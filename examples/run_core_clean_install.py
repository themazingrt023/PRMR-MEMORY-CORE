"""Build-artifact clean-install proof outside the source repository."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/core_release_candidate/clean_install_result.json"


def write(payload: Any) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=420)
    return {
        "command": [Path(command[0]).name, *command[1:]],
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "safe_output_tail": [line[:240] for line in completed.stdout.splitlines()[-4:]],
        "safe_error_code": None if completed.returncode == 0 else "CLEAN_INSTALL_COMMAND_FAILED",
    }


def artifact_proof(artifact: Path, *, label: str) -> dict[str, Any]:
    with TemporaryDirectory(prefix=f"prmr-clean-{label}-") as temporary:
        base = Path(temporary)
        venv = base / "venv"
        work = base / "outside-repository"
        work.mkdir()
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, timeout=120)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        console = venv / ("Scripts/prmr-core.exe" if os.name == "nt" else "bin/prmr-core")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        install = run([str(python), "-m", "pip", "install", "--no-deps", str(artifact)], cwd=work, env=env)
        commands = [install]
        if not install["passed"]:
            return {"label": label, "artifact": artifact.name, "commands": commands, "passed": False}
        commands.append(run([str(console), "version", "--json"], cwd=work, env=env))
        commands.append(run([str(console), "config", "init", "--mode", "sqlite_local", "--output", str(work / "prmr.toml")], cwd=work, env=env))
        config_text = (work / "prmr.toml").read_text(encoding="utf-8").replace("data/prmr-memory-core.sqlite3", (work / "core.sqlite3").as_posix())
        (work / "prmr.toml").write_text(config_text, encoding="utf-8")
        prefix = [str(console), "--config", str(work / "prmr.toml")]
        commands.extend(
            [
                run([*prefix, "engine", "init"], cwd=work, env=env),
                run([*prefix, "engine", "self-test"], cwd=work, env=env),
                run([*prefix, "integrity", "sweep", "--mode", "release-smoke"], cwd=work, env=env),
                run([*prefix, "release", "manifest", "--json"], cwd=work, env=env),
            ]
        )
        package_origin = subprocess.run(
            [str(python), "-c", "import pathlib,prmr; print(pathlib.Path(prmr.__file__).resolve())"],
            cwd=work, env=env, capture_output=True, text=True, timeout=30, check=True
        ).stdout.strip()
        outside_source = str(ROOT).lower() not in package_origin.lower()
        return {
            "label": label,
            "artifact": artifact.name,
            "commands": commands,
            "console_script_installed": console.is_file(),
            "package_origin_outside_repository": outside_source,
            "migrations_bundled": subprocess.run([str(python), "-c", "from prmr.core.runtime_migrations import migration_registry; assert len(migration_registry()) == 12"], cwd=work, env=env).returncode == 0,
            "passed": all(item["passed"] for item in commands) and console.is_file() and outside_source,
        }


def postgres_wheel_proof(wheel: Path) -> dict[str, Any]:
    url = os.getenv("PRMR_POSTGRES_TEST_DATABASE_URL", "").strip()
    if not url:
        return {"result": "BLOCKED", "safe_error_code": "POSTGRES_TEST_DATABASE_URL_MISSING", "database_url_recorded": False}
    with TemporaryDirectory(prefix="prmr-clean-postgres-") as temporary:
        base = Path(temporary)
        venv = base / "venv"
        work = base / "outside-repository"
        work.mkdir()
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, timeout=120)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        console = venv / ("Scripts/prmr-core.exe" if os.name == "nt" else "bin/prmr-core")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PRMR_DATABASE_URL"] = url
        install = run([str(python), "-m", "pip", "install", str(wheel), "psycopg[binary]>=3.1,<4", "psycopg-pool>=3.2,<4"], cwd=work, env=env)
        config = work / "postgres.toml"
        config.write_text(
            '[runtime]\nmode="postgres_single_node"\ntest_environment_protection=true\n[database]\nbackend="postgres"\ndatabase_url_env="PRMR_DATABASE_URL"\nsqlite_path=""\nmigration_policy="explicit_or_init"\n[worker]\nworkers=2\n',
            encoding="utf-8",
        )
        prefix = [str(console), "--config", str(config)]
        commands = [install]
        if install["passed"]:
            commands.extend(
                [
                    run([*prefix, "db", "status"], cwd=work, env=env),
                    run([*prefix, "db", "migrate"], cwd=work, env=env),
                    run([*prefix, "engine", "init"], cwd=work, env=env),
                    run([*prefix, "engine", "self-test"], cwd=work, env=env),
                    run([*prefix, "worker", "run", "--workers", "2", "--until-idle"], cwd=work, env=env),
                    run([*prefix, "integrity", "sweep", "--mode", "release-smoke"], cwd=work, env=env),
                    run([*prefix, "diagnostics", "collect", "--output", str(work / "diagnostics.zip")], cwd=work, env=env),
                ]
            )
        return {
            "result": "PASS" if all(item["passed"] for item in commands) else "NEEDS_WORK",
            "commands": commands,
            "database_url_recorded": False,
            "installed_wheel": wheel.name,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true")
    args = parser.parse_args()
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    sdists = sorted((ROOT / "dist").glob("*.tar.gz"))
    if not wheels or not sdists:
        payload = {"result": "BLOCKED", "safe_error_code": "BUILD_ARTIFACTS_MISSING"}
        write(payload)
        print("Result: BLOCKED")
        return 1
    wheel = artifact_proof(wheels[-1], label="wheel")
    sdist = artifact_proof(sdists[-1], label="sdist")
    postgres = postgres_wheel_proof(wheels[-1]) if args.postgres else {"result": "NOT_REQUESTED", "database_url_recorded": False}
    passed = wheel["passed"] and sdist["passed"] and (not args.postgres or postgres["result"] == "PASS")
    payload = {
        "result": "PASS" if passed else "NEEDS_WORK",
        "wheel": wheel,
        "source_distribution": sdist,
        "postgres_installed_wheel": postgres,
        "repository_relative_import_used": False,
        "database_url_recorded": False,
    }
    write(payload)
    print("PRMR Memory Core - RC1 Clean Install")
    print(f"Wheel: {'PASS' if wheel['passed'] else 'NEEDS_WORK'}")
    print(f"Source distribution: {'PASS' if sdist['passed'] else 'NEEDS_WORK'}")
    if args.postgres:
        print(f"Installed-wheel PostgreSQL: {postgres['result']}")
    print(f"Result: {payload['result']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
