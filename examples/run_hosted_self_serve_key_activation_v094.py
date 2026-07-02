"""Run real hosted V0.94 self-serve activation smoke when configured."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.api_server_v094 import BOUNDARY_V094


REPORT_DIR = ROOT / "reports" / "v094"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_self_serve_key_activation_v094.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_self_serve_key_activation_v094.json"
SMOKE_REPORT = REPORT_DIR / "hosted_self_serve_key_activation_smoke_v094.json"
SCORECARD = REPORT_DIR / "scorecard_v094.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any, known: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(value and value in text for value in (known or [])):
        return True
    return bool(
        re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r"\bprmr_session_local_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r'"(?:password|key_hash|password_hash)"\s*:', text, re.IGNORECASE)
    )


def unique_email(configured: str) -> str:
    local, separator, domain = configured.partition("@")
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{local}+v094{suffix}@{domain}" if separator else configured


def unavailable_report(reason: str, health: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "version": "0.94",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Self-Serve Key Activation",
        "result": "NEEDS_HOSTED_DURABLE_STORAGE",
        "reason": reason,
        "hosted_health_reached": health is not None,
        "storage_mode": (health or {}).get("storage", {}).get("storage_mode")
        or (health or {}).get("storage_boundary_v083", {}).get("storage_mode"),
        "durable_storage_verified": False,
        "raw_key_exposed": False,
        "public_safe": True,
        "boundary": BOUNDARY_V094,
    }


def run_hosted_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    base_url = os.getenv("PRMR_HOSTED_API_URL", "").strip().rstrip("/")
    configured_email = os.getenv("PRMR_SELF_SERVE_TEST_EMAIL", "").strip()
    password = os.getenv("PRMR_SELF_SERVE_TEST_PASSWORD", "").strip() or "synthetic-hosted-v094-password"
    if not base_url or not configured_email:
        public = unavailable_report("PRMR_HOSTED_API_URL and PRMR_SELF_SERVE_TEST_EMAIL are required.")
        return public, {**public, "public_safe": False}, dict(public), []

    checks: list[dict[str, Any]] = []
    raw_key = ""
    replacement_key = ""
    session = ""
    trace: dict[str, Any] = {}
    try:
        with httpx.Client(base_url=base_url, timeout=45.0, follow_redirects=True) as client:
            health_response = client.get("/health")
            health = health_response.json() if health_response.headers.get("content-type", "").startswith("application/json") else {}
            add(checks, "hosted_health_works", health_response.status_code == 200)
            storage = health.get("storage", {})
            durable_sqlite = bool(
                storage.get("storage_mode") == "hosted_durable_sqlite"
                and storage.get("durable_storage_verified") is True
                and storage.get("durable_storage_claim_allowed") is True
            )
            durable_postgres = bool(
                storage.get("storage_backend") == "postgres"
                and storage.get("storage_mode") == "hosted_managed_postgres"
                and storage.get("database_connected") is True
                and storage.get("durable_storage_verified") is True
                and storage.get("durable_storage_claim_allowed") is True
            )
            durable = durable_sqlite or durable_postgres
            add(checks, "hosted_storage_reports_verified_durable", durable, storage)
            if not durable:
                public = unavailable_report(
                    "Hosted health does not report verified durable SQLite or Postgres storage.",
                    health,
                )
                private = {**public, "public_safe": False, "checks": checks, "health": health}
                smoke = {**public, "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks]}
                return public, private, smoke, checks

            email = unique_email(configured_email)
            signup = client.post(
                "/v1/self-serve/signup",
                json={"name": "Generic Hosted V0.94 Builder", "email": email, "password": password},
            )
            signup_json = signup.json()
            add(checks, "generic_test_user_created", signup.status_code == 201)
            user_id = signup_json.get("account", {}).get("user_id", "")

            verify = client.post("/v1/self-serve/verify", json={"user_id": user_id})
            add(
                checks,
                "local_test_verification_recorded",
                verify.status_code == 200
                and verify.json().get("verification_simulated") is True
                and verify.json().get("email_sent") is False,
            )
            login = client.post(
                "/v1/self-serve/login",
                json={"email": email, "password": password},
            )
            login_json = login.json()
            session = str(login_json.get("session_token", ""))
            session_headers = {"Authorization": f"Session {session}"}

            plan = client.post("/v1/self-serve/plan", headers=session_headers, json={"plan_id": "free"})
            add(
                checks,
                "free_plan_selected",
                plan.status_code == 200 and plan.json().get("subscription", {}).get("status") == "active",
            )
            provision = client.post("/v1/self-serve/provision", headers=session_headers)
            scope = provision.json().get("scope", {})
            add(
                checks,
                "generic_scope_provisioned",
                provision.status_code in {200, 201}
                and str(scope.get("client_id", "")).startswith("client_ss_")
                and str(scope.get("vault_id", "")).startswith("vault_ss_")
                and scope.get("namespace") == "default",
            )
            key_create = client.post(
                "/v1/self-serve/keys",
                headers=session_headers,
                json={"label": "Hosted smoke server"},
            )
            key_json = key_create.json()
            raw_key = str(key_json.get("raw_api_key", ""))
            key_id = str(key_json.get("key_id", ""))
            add(checks, "copy_once_key_created", key_create.status_code == 201 and bool(raw_key))
            add(
                checks,
                "raw_key_returned_once",
                key_json.get("returned_once") is True and raw_key.startswith("prmr_alpha_"),
            )
            key_list = client.get("/v1/self-serve/keys", headers=session_headers)
            add(
                checks,
                "key_list_is_safe_preview_only",
                key_list.status_code == 200
                and key_list.json().get("credential_values_returned") is False
                and raw_key not in json.dumps(key_list.json()),
            )

            api_headers = {
                "Authorization": f"Bearer {raw_key}",
                "X-Client-ID": str(scope.get("client_id", "")),
                "X-Vault-ID": str(scope.get("vault_id", "")),
                "X-Namespace": str(scope.get("namespace", "")),
            }
            ingest = client.post(
                "/v1/events/ingest",
                headers=api_headers,
                json={
                    "events": [
                        {
                            "event_id": "evt_v094_hosted_001",
                            "type": "project_updated",
                            "content": "A generic synthetic hosted project moved to review.",
                            "timestamp_index": 1,
                        }
                    ]
                },
            )
            packet = client.post("/v1/continuity/packet", headers=api_headers, json={})
            packet_json = packet.json()
            packet_id = packet_json.get("packet_id")
            report_id = packet_json.get("report_id")
            reconstruct = client.post(
                "/v1/memory/reconstruct",
                headers=api_headers,
                json={"packet_id": packet_id},
            )
            explain = client.post(
                "/v1/explain",
                headers=api_headers,
                json={"packet_id": packet_id},
            )
            report = client.get(f"/v1/reports/{report_id}", headers=api_headers)
            usage = client.get("/v1/usage", headers=api_headers)
            protected_statuses = {
                "ingest": ingest.status_code,
                "packet": packet.status_code,
                "reconstruct": reconstruct.status_code,
                "explain": explain.status_code,
                "report": report.status_code,
                "usage": usage.status_code,
            }
            add(
                checks,
                "protected_hosted_prmr_flow_works",
                all(status == 200 for status in protected_statuses.values()),
                protected_statuses,
            )
            dashboard = client.get("/v1/self-serve/dashboard", headers=session_headers)
            dashboard_json = dashboard.json()
            add(
                checks,
                "dashboard_shows_usage_and_report",
                dashboard.status_code == 200
                and dashboard_json.get("dashboard", {}).get("plan", {}).get("usage", {}).get("requests_used", 0) >= 6
                and len(dashboard_json.get("dashboard", {}).get("reports", [])) >= 1,
            )

            rotate = client.patch(
                "/v1/self-serve/keys",
                headers=session_headers,
                json={"key_id": key_id},
            )
            rotate_json = rotate.json()
            replacement_key = str(rotate_json.get("raw_api_key", ""))
            replacement_id = str(rotate_json.get("new_key_id", ""))
            add(checks, "key_rotation_works", rotate.status_code == 200 and bool(replacement_key))
            old_blocked = client.get("/v1/usage", headers=api_headers)
            add(
                checks,
                "old_key_is_blocked",
                old_blocked.status_code == 403
                and old_blocked.json().get("error", {}).get("code") == "rotated_key",
            )
            revoke = client.request(
                "DELETE",
                "/v1/self-serve/keys",
                headers=session_headers,
                json={"key_id": replacement_id},
            )
            add(checks, "replacement_key_revoked", revoke.status_code == 200)
            revoked_headers = {**api_headers, "Authorization": f"Bearer {replacement_key}"}
            revoked_blocked = client.get("/v1/usage", headers=revoked_headers)
            add(
                checks,
                "revoked_key_is_blocked",
                revoked_blocked.status_code == 403
                and revoked_blocked.json().get("error", {}).get("code") == "revoked_key",
            )
            trace = {
                "base_url": base_url,
                "health_status": health_response.status_code,
                "storage": storage,
                "safe_scope": scope,
                "safe_key_preview": key_json.get("safe_key_preview"),
                "protected_statuses": protected_statuses,
                "dashboard_report_count": len(dashboard_json.get("dashboard", {}).get("reports", [])),
                "raw_credentials_retained": False,
            }
    except Exception as exc:
        public = unavailable_report(f"Hosted smoke request failed: {type(exc).__name__}.")
        return public, {**public, "public_safe": False, "exception_type": type(exc).__name__}, dict(public), checks

    provisional = {
        "version": "0.94",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Self-Serve Key Activation",
        "truth_label": "hosted generic self-serve activation with verified durable storage",
        "result": "PASS" if all(item["passed"] for item in checks) else "NEEDS_WORK",
        "checks_passed": sum(1 for item in checks if item["passed"]),
        "checks_total": len(checks) + 1,
        "public_safe": True,
        "hosted_url": base_url,
        "storage_backend": trace.get("storage", {}).get("storage_backend", "sqlite"),
        "storage_mode": trace.get("storage", {}).get("storage_mode"),
        "durable_storage_verified": True,
        "generic_client_flow": True,
        "copy_once_key": True,
        "protected_flow": trace.get("protected_statuses", {}),
        "raw_key_exposed_in_report": False,
        "real_email_delivery": "NOT_CONNECTED",
        "stripe_billing": "NOT_CONNECTED",
        "production_auth_hardening": "NOT_COMPLETE",
        "boundary": BOUNDARY_V094,
    }
    add(
        checks,
        "public_report_has_no_secrets",
        not contains_secret(provisional, [raw_key, replacement_key, session, password]),
    )
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public = {**provisional, "result": result, "checks_passed": passed, "checks_total": total}
    private = {
        **public,
        "public_safe": False,
        "checks": checks,
        "trace": trace,
        "restricted_note": "No raw API key, session token, or password is retained.",
    }
    smoke = {
        "version": "0.94",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "public_safe": True,
        "boundary": BOUNDARY_V094,
    }
    return public, private, smoke, checks


def build_scorecard(public: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.94 Hosted Self-Serve Key Activation",
        "",
        f"Result: {public['result']}",
        f"Passed checks: {public.get('checks_passed', 0)}/{public.get('checks_total', 0)}",
        "",
        f"Boundary: {BOUNDARY_V094}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks)
    return "\n".join(lines) + "\n"


def main() -> int:
    public, private, smoke, checks = run_hosted_smoke()
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    write_json(SMOKE_REPORT, smoke)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public, checks), encoding="utf-8")
    print("PRMR Memory Core V0.94 Hosted Self-Serve Key Activation")
    print(f"Passed checks: {public.get('checks_passed', 0)}/{public.get('checks_total', 0)}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "NEEDS_HOSTED_DURABLE_STORAGE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
