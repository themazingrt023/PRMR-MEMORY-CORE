"""Audit the V0.94.1 Postgres durable storage adapter and claim boundaries."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_postgres_durable_storage_v0941 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret,
    run_smoke,
    write_json,
)
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093
from prmr.product.self_serve_repository_postgres_v0941 import SCHEMA_NAME, TABLES


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def has_unqualified_claim(text: str) -> bool:
    pattern = re.compile(
        r"\b(?:production[- ]ready|production auth(?:entication)? complete|"
        r"compliance approved|legal approved|security certified|externally validated|"
        r"stripe billing connected|real email delivery active)\b",
        re.IGNORECASE,
    )
    for paragraph in re.split(r"\n\s*\n", text):
        if pattern.search(paragraph) and not re.search(
            r"\b(?:not|no|does not|is not|without|unfinished|future|pending)\b",
            paragraph,
            re.IGNORECASE,
        ):
            return True
    return False


def main() -> int:
    checks: list[dict[str, Any]] = []
    v093 = ROOT / "reports" / "v093" / "public_durable_self_serve_storage_v093.json"
    storage_module = ROOT / "prmr" / "product" / "postgres_self_serve_storage_v0941.py"
    repository_module = (
        ROOT / "prmr" / "product" / "self_serve_repository_postgres_v0941.py"
    )
    api_server = ROOT / "prmr" / "product" / "api_server_v094.py"
    hosted_smoke = ROOT / "examples" / "run_hosted_self_serve_key_activation_v094.py"
    docs = ROOT / "docs" / "postgres_durable_storage_v0941.md"
    render = ROOT / "render.yaml"
    env_example = ROOT / ".env.example"
    requirements = ROOT / "requirements-api.txt"

    add(checks, "v093_evidence_exists", v093.exists())
    add(checks, "postgres_storage_module_exists", storage_module.exists())
    add(checks, "postgres_repository_exists", repository_module.exists())
    add(checks, "postgres_docs_exist", docs.exists())

    sources = {
        path: path.read_text(encoding="utf-8")
        for path in [
            storage_module,
            repository_module,
            api_server,
            hosted_smoke,
            docs,
            render,
            env_example,
            requirements,
        ]
        if path.exists()
    }
    combined = "\n".join(sources.values())
    repository_source = sources.get(repository_module, "")
    api_source = sources.get(api_server, "")
    hosted_source = sources.get(hosted_smoke, "")
    docs_source = sources.get(docs, "")

    add(
        checks,
        "required_postgres_entities_declared",
        SCHEMA_NAME == "prmr_self_serve"
        and all(
            table in TABLES
            for table in [
                "users",
                "sessions",
                "plans",
                "clients",
                "vaults",
                "namespaces",
                "api_keys",
                "monthly_usage",
                "request_logs",
                "events",
                "packets",
                "reports",
                "dashboard_snapshots",
                "audit_metadata",
            ]
        ),
    )
    add(
        checks,
        "safe_schema_init_exists",
        "def initialize_postgres_schema" in repository_source
        and "CREATE SCHEMA IF NOT EXISTS" in repository_source
        and "CREATE TABLE IF NOT EXISTS" in repository_source
        and "CREATE INDEX IF NOT EXISTS" in repository_source,
    )
    add(
        checks,
        "schema_init_is_non_destructive",
        not re.search(
            r"\b(?:DROP\s+(?:TABLE|SCHEMA)|TRUNCATE|DELETE\s+FROM)\b",
            repository_source,
            re.IGNORECASE,
        ),
    )
    add(
        checks,
        "repository_uses_upserts_without_table_wipe",
        "ON CONFLICT" in repository_source
        and "_clear_state" not in repository_source
        and "save_strategy" in repository_source,
    )
    add(
        checks,
        "postgres_driver_is_deployable_dependency",
        "psycopg[binary]" in sources.get(requirements, ""),
    )
    add(
        checks,
        "storage_backend_switch_defaults_to_sqlite",
        'os.getenv("PRMR_STORAGE_BACKEND", "sqlite")' in api_source
        and '{"sqlite", "postgres"}' in api_source
        and "configured_storage_path()" in api_source,
    )

    with tempfile.TemporaryDirectory(prefix="prmr-v0941-sqlite-", ignore_cleanup_errors=True) as temp:
        sqlite_product = DurableSelfServeProductV093(Path(temp) / "fallback.sqlite")
        add(
            checks,
            "sqlite_fallback_preserved",
            sqlite_product.storage_status["storage_backend"] == "sqlite"
            and sqlite_product.storage_status["storage_mode"] == "local_sqlite",
        )

    add(
        checks,
        "hosted_smoke_accepts_verified_postgres",
        'storage.get("storage_backend") == "postgres"' in hosted_source
        and 'storage.get("storage_mode") == "hosted_managed_postgres"' in hosted_source
        and "durable_sqlite or durable_postgres" in hosted_source,
    )
    add(
        checks,
        "render_uses_private_database_url_input",
        "PRMR_STORAGE_BACKEND" in sources.get(render, "")
        and "value: postgres" in sources.get(render, "")
        and "DATABASE_URL" in sources.get(render, "")
        and "sync: false" in sources.get(render, "")
        and "postgres://" not in sources.get(render, "")
        and "postgresql://" not in sources.get(render, ""),
    )
    add(
        checks,
        "docs_cover_required_environment_and_start_command",
        all(
            phrase in docs_source
            for phrase in [
                "PRMR_STORAGE_BACKEND=postgres",
                "DATABASE_URL=<POOLED_POSTGRES_CONNECTION_STRING>",
                "PRMR_DURABLE_STORAGE_VERIFIED=true",
                "PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app",
                "uvicorn prmr.product.api_server_v094:app --host 0.0.0.0 --port $PORT",
            ]
        ),
    )
    add(
        checks,
        "database_url_never_publicly_rendered",
        "database_url_exposed" in combined
        and not re.search(r"postgres(?:ql)?://[^<\\s]+:[^<\\s]+@", combined),
    )
    add(
        checks,
        "raw_credentials_are_not_persisted",
        "raw_keys_persisted" in repository_source
        and "raw_passwords_persisted" in repository_source
        and "raw_api_key" not in repository_source,
    )
    add(
        checks,
        "private_schema_guidance_present",
        "private `prmr_self_serve` schema" in docs_source
        and "Do not add `prmr_self_serve` to Supabase Data API exposed schemas"
        in docs_source,
    )

    public, private, smoke, runner_checks = run_smoke()
    configured = bool(os.getenv("DATABASE_URL", "").strip())
    add(
        checks,
        "runner_status_matches_database_availability",
        (
            configured
            and public["result"] in {"PASS", "NEEDS_WORK"}
            and public.get("database_connection_tested") is True
        )
        or (
            not configured
            and public["result"] == "NEEDS_DATABASE_URL"
            and public.get("database_connection_tested") is False
        ),
        public["result"],
    )
    add(
        checks,
        "public_reports_contain_no_secrets",
        not contains_secret(public) and not contains_secret(smoke),
    )
    add(
        checks,
        "truth_boundaries_are_explicit",
        "not real email delivery" in docs_source.lower()
        and "stripe billing" in docs_source.lower()
        and "not production" in docs_source.lower()
        and not has_unqualified_claim(docs_source + "\n" + json.dumps(public)),
    )

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    audit = {
        "version": "0.94.1",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "postgres_runner_result": public["result"],
        "database_connection_tested": public.get("database_connection_tested", False),
        "public_safe": True,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "truth_label": (
            "Postgres adapter static/readiness audit. A PASS does not replace a real "
            "DATABASE_URL persistence run."
        ),
    }
    write_json(PUBLIC_REPORT, {**public, "readiness_audit": audit})
    write_json(
        PRIVATE_REPORT,
        {
            **private,
            "readiness_audit": {**audit, "checks": checks},
            "runner_checks": runner_checks,
        },
    )
    write_json(SMOKE_REPORT, {**smoke, "readiness_audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public, runner_checks)
        + "\n## Readiness audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Postgres execution: {public['result']}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.94.1 Postgres Durable Storage Audit")
    print(f"Postgres runner result: {public['result']}")
    print(f"Database connection tested: {public.get('database_connection_tested', False)}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for item in checks:
            if not item["passed"]:
                print(f"FAIL: {item['name']}")
                if item.get("detail") is not None:
                    print(str(item["detail"])[-600:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
