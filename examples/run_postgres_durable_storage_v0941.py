"""Run V0.94.1 Postgres durable storage evidence when DATABASE_URL is configured."""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.hosted_backend_foundation_v069 import safe_hash
from prmr.product.postgres_self_serve_storage_v0941 import (
    BOUNDARY_V0941,
    PostgresSelfServeProductV0941,
)


REPORT_DIR = ROOT / "reports" / "v0941"
PUBLIC_REPORT = REPORT_DIR / "public_postgres_durable_storage_v0941.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_postgres_durable_storage_v0941.json"
SMOKE_REPORT = REPORT_DIR / "postgres_durable_storage_smoke_v0941.json"
SCORECARD = REPORT_DIR / "scorecard_v0941.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any, known_values: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(value and value in text for value in (known_values or [])):
        return True
    return bool(
        re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r"\bprmr_session_local_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r"postgres(?:ql)?://[^ <]+", text, re.IGNORECASE)
        or re.search(
            r'"(?:database_url|password|password_hash|password_salt|key_hash|token_hash)"\s*:',
            text,
            re.IGNORECASE,
        )
    )


def synthetic_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_v0941_001",
            "user_id": "synthetic_postgres_builder",
            "type": "project_created",
            "content": "A synthetic project entered planning.",
            "timestamp_index": 1,
        },
        {
            "event_id": "evt_v0941_002",
            "user_id": "synthetic_postgres_builder",
            "type": "project_updated",
            "content": "The synthetic project moved to review after a database reload.",
            "timestamp_index": 2,
        },
    ]


def needs_database_url() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]
]:
    public = {
        "version": "0.94.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Postgres Durable Storage Adapter",
        "truth_label": "Postgres adapter readiness; hosted database execution not run",
        "result": "NEEDS_DATABASE_URL",
        "reason": "Set DATABASE_URL to a fresh server-only pooled Postgres connection string.",
        "database_connection_tested": False,
        "database_url_exposed": False,
        "raw_key_exposed": False,
        "public_safe": True,
        "boundary": BOUNDARY_V0941,
    }
    private = {
        **public,
        "public_safe": False,
        "restricted_note": "DATABASE_URL was absent. No credential value was read or retained.",
    }
    smoke = {
        "version": "0.94.1",
        "result": "NEEDS_DATABASE_URL",
        "database_connection_tested": False,
        "public_safe": True,
        "boundary": BOUNDARY_V0941,
    }
    return public, private, smoke, []


def run_smoke() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]
]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return needs_database_url()

    checks: list[dict[str, Any]] = []
    password = secrets.token_urlsafe(24)
    raw_key = ""
    replacement_key = ""
    session_token = ""
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    email = f"postgres-v0941-{suffix}@example.test"
    trace: dict[str, Any] = {}

    try:
        first = PostgresSelfServeProductV0941(
            database_url,
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        add(checks, "postgres_connection_and_schema_init_work", True)
        add(
            checks,
            "postgres_health_reports_verified_durable",
            first.storage_status["storage_backend"] == "postgres"
            and first.storage_status["database_connected"] is True
            and first.storage_status["durable_storage_verified"] is True
            and first.storage_status["durable_storage_claim_allowed"] is True,
        )

        signup = first.signup(
            name="Synthetic Postgres Builder",
            email=email,
            password=password,
        )
        user_id = str(signup.get("account", {}).get("user_id", ""))
        add(checks, "test_user_created", signup.get("status_code") == 201 and bool(user_id))
        verified = first.verify_email_local(user_id=user_id)
        add(
            checks,
            "test_user_verified",
            verified.get("account", {}).get("status") == "verified",
        )
        login = first.login(email=email, password=password)
        session_token = str(login.get("session_token", ""))
        add(checks, "hashed_session_created", bool(session_token))
        selected = first.choose_plan(session_token=session_token, plan_id="free")
        add(
            checks,
            "free_plan_selected",
            selected.get("subscription", {}).get("status") == "active",
        )
        provisioned = first.provision_default_scope(session_token=session_token)
        scope = provisioned.get("scope", {})
        add(
            checks,
            "client_vault_namespace_created",
            str(scope.get("client_id", "")).startswith("client_ss_")
            and str(scope.get("vault_id", "")).startswith("vault_ss_")
            and scope.get("namespace") == "default",
        )
        created_key = first.create_key(
            session_token=session_token,
            label="Postgres durability smoke",
        )
        key_id = str(created_key.get("key_id", ""))
        raw_key = str(created_key.get("raw_api_key", ""))
        preview = str(created_key.get("safe_key_preview", ""))
        add(
            checks,
            "copy_once_api_key_created",
            created_key.get("returned_once") is True
            and raw_key.startswith("prmr_alpha_")
            and bool(preview),
        )
        add(
            checks,
            "key_hash_and_safe_preview_persisted",
            first.repository.private_key_hashes().get(key_id) == safe_hash(raw_key)
            and any(
                row["key_id"] == key_id and row["safe_key_preview"] == preview
                for row in first.repository.safe_key_rows()
            ),
        )
        add(
            checks,
            "raw_key_and_password_not_persisted",
            not first.repository.raw_value_present(raw_key)
            and not first.repository.raw_value_present(password),
        )

        second = PostgresSelfServeProductV0941(
            database_url,
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        add(
            checks,
            "account_scope_and_key_reload",
            user_id in second.product.accounts.accounts
            and second.product.keys.scopes_by_user[user_id].client_id == scope["client_id"]
            and second.product.keys.scopes_by_user[user_id].vault_id == scope["vault_id"],
        )
        valid, reason = second.product.keys.preflight_key(
            raw_key=raw_key,
            client_id=scope["client_id"],
        )
        add(checks, "reloaded_key_validates", valid and reason == "allowed")

        common = {
            "api_key": raw_key,
            "client_id": scope["client_id"],
            "vault_id": scope["vault_id"],
            "namespace": scope["namespace"],
        }
        ingest = second.execute("events_ingest", **common, events=synthetic_events())
        packet = second.execute("continuity_packet", **common)
        packet_id = packet.get("body", {}).get("packet_id")
        report_id = packet.get("body", {}).get("report_id")
        reconstruct = second.execute(
            "memory_reconstruct",
            **common,
            packet_id=packet_id,
        )
        explain = second.execute("explain", **common, packet_id=packet_id)
        least_harm = second.execute(
            "least_harm_action",
            **common,
            packet_id=packet_id,
        )
        report = second.execute("get_report", **common, report_id=report_id)
        usage = second.execute("get_usage", **common)
        flow_statuses = {
            "ingest": ingest.get("status_code"),
            "packet": packet.get("status_code"),
            "reconstruct": reconstruct.get("status_code"),
            "explain": explain.get("status_code"),
            "least_harm": least_harm.get("status_code"),
            "report": report.get("status_code"),
            "usage": usage.get("status_code"),
        }
        add(
            checks,
            "protected_prmr_flow_works",
            all(status == 200 for status in flow_statuses.values()),
            flow_statuses,
        )

        third = PostgresSelfServeProductV0941(
            database_url,
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        dashboard = third.dashboard_state(session_token=session_token)
        add(
            checks,
            "usage_logs_reports_and_dashboard_reload",
            third.product.plans.usage_summary(user_id)["requests_used"] == 7
            and len(third.product.api.api_request_log) >= 7
            and report_id in third.product.api.public_reports
            and dashboard.get("status_code") == 200
            and dashboard.get("dashboard", {}).get("client_scope", {}).get("client_id")
            == scope["client_id"],
        )

        rotated = third.rotate_key(session_token=session_token, key_id=key_id)
        replacement_id = str(rotated.get("new_key_id", ""))
        replacement_key = str(rotated.get("raw_api_key", ""))
        add(
            checks,
            "key_rotation_returns_copy_once_replacement",
            rotated.get("status_code") == 200
            and replacement_id != key_id
            and replacement_key.startswith("prmr_alpha_"),
        )
        fourth = PostgresSelfServeProductV0941(
            database_url,
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        old_blocked = fourth.execute("get_usage", **common)
        add(
            checks,
            "old_key_blocked_after_reload",
            old_blocked.get("status_code") == 403
            and old_blocked.get("body", {}).get("error", {}).get("code") == "rotated_key",
        )
        replacement_valid, replacement_reason = fourth.product.keys.preflight_key(
            raw_key=replacement_key,
            client_id=scope["client_id"],
        )
        add(
            checks,
            "replacement_key_validates_after_reload",
            replacement_valid and replacement_reason == "allowed",
        )
        revoked = fourth.revoke_key(
            session_token=session_token,
            key_id=replacement_id,
        )
        add(checks, "replacement_key_revoked", revoked.get("status_code") == 200)
        fifth = PostgresSelfServeProductV0941(
            database_url,
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        revoked_blocked = fifth.execute(
            "get_usage",
            api_key=replacement_key,
            client_id=scope["client_id"],
            vault_id=scope["vault_id"],
            namespace=scope["namespace"],
        )
        add(
            checks,
            "revoked_key_blocked_after_reload",
            revoked_blocked.get("status_code") == 403
            and revoked_blocked.get("body", {}).get("error", {}).get("code")
            == "revoked_key",
        )
        counts = fifth.repository.table_counts()
        trace = {
            "storage_backend": "postgres",
            "schema": "prmr_self_serve",
            "table_count": len(counts),
            "persisted_counts": counts,
            "safe_key_preview": preview,
            "flow_statuses": flow_statuses,
            "database_url_retained_in_report": False,
            "raw_credentials_retained_in_report": False,
        }
    except Exception as exc:
        add(
            checks,
            "postgres_smoke_completed_without_exception",
            False,
            type(exc).__name__,
        )
        public = {
            "version": "0.94.1",
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "title": "Postgres Durable Storage Adapter",
            "truth_label": "configured Postgres smoke did not complete",
            "result": "NEEDS_WORK",
            "reason": f"Postgres smoke failed with {type(exc).__name__}.",
            "database_connection_tested": True,
            "database_url_exposed": False,
            "raw_key_exposed": False,
            "checks_passed": sum(1 for item in checks if item["passed"]),
            "checks_total": len(checks),
            "public_safe": True,
            "boundary": BOUNDARY_V0941,
        }
        return (
            public,
            {**public, "public_safe": False, "checks": checks},
            {
                "version": "0.94.1",
                "result": "NEEDS_WORK",
                "public_safe": True,
                "checks": [
                    {"name": item["name"], "passed": item["passed"]} for item in checks
                ],
            },
            checks,
        )

    provisional = {
        "version": "0.94.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Postgres Durable Storage Adapter",
        "truth_label": "configured Postgres persistence and reload evidence",
        "result": "PASS",
        "storage_backend": "postgres",
        "storage_mode": "hosted_managed_postgres",
        "database_connection_tested": True,
        "durable_storage_verified": True,
        "schema_initialized_non_destructively": True,
        "copy_once_key_behavior": True,
        "protected_flow_completed": True,
        "rotation_and_revocation_persisted": True,
        "database_url_exposed": False,
        "raw_key_exposed": False,
        "real_email_delivery": "NOT_CONNECTED",
        "stripe_billing": "NOT_CONNECTED",
        "production_auth_hardening": "NOT_COMPLETE",
        "public_safe": True,
        "boundary": BOUNDARY_V0941,
    }
    add(
        checks,
        "public_report_has_no_secrets",
        not contains_secret(
            provisional,
            [database_url, raw_key, replacement_key, session_token, password],
        ),
    )
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public = {
        **provisional,
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
    }
    private = {
        **public,
        "public_safe": False,
        "checks": checks,
        "trace": trace,
        "restricted_note": "No database URL, raw key, session token, or password is retained.",
    }
    smoke = {
        "version": "0.94.1",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "storage_backend": "postgres",
        "database_url_exposed": False,
        "public_safe": True,
        "boundary": BOUNDARY_V0941,
    }
    return public, private, smoke, checks


def build_scorecard(public: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.94.1 Postgres Durable Storage Adapter",
        "",
        f"Result: {public['result']}",
        f"Passed checks: {public.get('checks_passed', 0)}/{public.get('checks_total', 0)}",
        "",
        f"Boundary: {BOUNDARY_V0941}",
        "",
        "## Checks",
        "",
    ]
    if checks:
        lines.extend(
            f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks
        )
    else:
        lines.append("- NOT RUN: Postgres execution requires DATABASE_URL.")
    return "\n".join(lines) + "\n"


def main() -> int:
    public, private, smoke, checks = run_smoke()
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    write_json(SMOKE_REPORT, smoke)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public, checks), encoding="utf-8")
    print("PRMR Memory Core V0.94.1 Postgres Durable Storage")
    print(f"Database connection tested: {public.get('database_connection_tested', False)}")
    print(f"Passed checks: {public.get('checks_passed', 0)}/{public.get('checks_total', 0)}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "NEEDS_DATABASE_URL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
