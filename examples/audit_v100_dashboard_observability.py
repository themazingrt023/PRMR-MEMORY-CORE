"""Audit V1.0 Afternum API dashboard observability and plan shell."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.product.api_server_v094 import create_app_v094
from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093
from prmr.product.supabase_auth_bridge_v095 import (
    FixtureSupabaseIdentityVerifier,
    SupabaseAuthBridgeV095,
    SupabaseIdentity,
)


REPORT_DIR = ROOT / "reports" / "v100"
PUBLIC_REPORT = REPORT_DIR / "public_dashboard_observability_v100.json"
PRIVATE_REPORT = REPORT_DIR / "private_dashboard_observability_v100.json"
SCORECARD = REPORT_DIR / "scorecard_v100.md"
DOC_PATH = ROOT / "docs" / "dashboard_observability_v100.md"
BOUNDARY_V100 = (
    "V1.0 improves real Afternum/PRMR API dashboard observability and a "
    "manual plan-upgrade shell. It does not implement Stripe billing, "
    "enterprise certification, compliance approval, legal approval, or "
    "external security certification."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def command(command_args: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    completed = subprocess.run(
        command_args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-1600:]


def contains_secret(payload: Any, known: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(value and value in text for value in (known or [])):
        return True
    patterns = [
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_\-]{24,}\b",
        r"Authorization:\s*Bearer\s+(?!<PRMR_API_KEY>)[A-Za-z0-9_\-\.]{20,}",
        r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}",
        r"postgres(?:ql)?://[^\\s]+",
        r"service_role",
        r"database_url",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def fixture_app() -> tuple[TestClient, DurableSelfServeProductV093, list[str]]:
    product = DurableSelfServeProductV093(Path(tempfile.mkdtemp(prefix="prmr-v100-")) / "dashboard.sqlite")
    tokens = ["fixture_v100_alpha", "fixture_v100_beta"]
    verifier = FixtureSupabaseIdentityVerifier(
        {
            tokens[0]: SupabaseIdentity(
                subject="fixture-v100-alpha",
                email="alpha-v100@example.test",
                email_confirmed_at="2026-07-05T12:00:00+00:00",
                role="authenticated",
                display_name="Alpha Dashboard",
            ),
            tokens[1]: SupabaseIdentity(
                subject="fixture-v100-beta",
                email="beta-v100@example.test",
                email_confirmed_at="2026-07-05T12:00:00+00:00",
                role="authenticated",
                display_name="Beta Dashboard",
            ),
        }
    )
    bridge = SupabaseAuthBridgeV095(product, verifier)
    client = TestClient(create_app_v094(product, bridge))
    return client, product, tokens


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run_fixture_checks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    client, product, tokens = fixture_app()
    known_secrets = list(tokens)
    try:
        client.post("/v1/auth/supabase/activate", headers=auth(tokens[0]), json={"plan_id": "free"})
        key = client.post("/v1/auth/supabase/keys", headers=auth(tokens[0]), json={"label": "Dashboard v100"}).json()
        raw_key = key["raw_api_key"]
        known_secrets.append(raw_key)
        protected_headers = {"Authorization": f"Bearer {raw_key}"}
        for index in range(31):
            client.post(
                "/v1/events/ingest",
                headers=protected_headers,
                json={
                    "event_type": "dashboard.test" if index % 2 else "dashboard.repeat",
                    "signal": f"Synthetic dashboard event {index}",
                    "occurred_at": f"2026-07-05T12:{index:02d}:00Z",
                    "idempotency_key": f"evt-v100-{index}",
                    "timestamp_index": index + 1,
                },
            )
            if index % 3 == 0:
                client.post("/v1/continuity/packet", headers=protected_headers, json={})
        client.get("/v1/usage", headers=protected_headers)
        logs_page = client.get("/v1/auth/supabase/dashboard/logs?limit=5&offset=0", headers=auth(tokens[0]))
        logs_next = client.get("/v1/auth/supabase/dashboard/logs?limit=5&offset=5", headers=auth(tokens[0]))
        reports_page = client.get("/v1/auth/supabase/dashboard/reports?limit=5&offset=0", headers=auth(tokens[0]))
        first_report = reports_page.json()["reports"][0]["report_id"]
        report_detail = client.get(f"/v1/auth/supabase/dashboard/reports/{first_report}", headers=auth(tokens[0]))
        packet_test = client.post("/v1/auth/supabase/dashboard/packet", headers=auth(tokens[0]))
        plan = client.get("/v1/auth/supabase/dashboard/plan", headers=auth(tokens[0]))
        storage = client.get("/v1/auth/supabase/dashboard/storage", headers=auth(tokens[0]))

        client.post("/v1/auth/supabase/activate", headers=auth(tokens[1]), json={"plan_id": "free"})
        cross_report = client.get(f"/v1/auth/supabase/dashboard/reports/{first_report}", headers=auth(tokens[1]))

        logs_body = logs_page.json()
        reports_body = reports_page.json()
        detail_body = report_detail.json()
        packet_body = packet_test.json()
        storage_body = storage.json()
        plan_text = json.dumps(plan.json(), sort_keys=True)
        logs_text = json.dumps(logs_body, sort_keys=True)
        reports_text = json.dumps(reports_body, sort_keys=True)
        storage_text = json.dumps(storage_body, sort_keys=True)

        add(checks, "dashboard_can_request_paginated_logs", logs_page.status_code == 200 and len(logs_body.get("logs", [])) == 5 and logs_body.get("total_count", 0) > 5 and logs_body.get("has_more") is True, logs_body)
        add(checks, "dashboard_logs_latest_first_and_pageable", logs_next.status_code == 200 and logs_body.get("logs", [])[0].get("timestamp") >= logs_next.json().get("logs", [])[0].get("timestamp"), logs_next.json())
        add(checks, "dashboard_can_request_paginated_reports", reports_page.status_code == 200 and len(reports_body.get("reports", [])) == 5 and reports_body.get("total_count", 0) >= 5, reports_body)
        add(checks, "report_detail_is_scoped_to_current_client", report_detail.status_code == 200 and detail_body.get("report", {}).get("packet", {}).get("current_state") is not None, detail_body)
        add(checks, "cross_client_report_access_denied", cross_report.status_code == 404, cross_report.json())
        add(checks, "request_logs_do_not_expose_authorization_or_keys", not contains_secret(logs_text, known_secrets), logs_body)
        add(checks, "reports_do_not_expose_secrets", not contains_secret(reports_text, known_secrets), reports_body)
        add(checks, "packet_tester_returns_v099_fields", packet_test.status_code == 200 and all(field in packet_body.get("packet", {}) for field in ["current_state", "active_information", "causal_signature", "coherence_score", "recoverability_score"]), packet_body)
        add(checks, "upgrade_shell_does_not_claim_live_payment", "Billing is not connected yet" in plan_text and "payment_checkout_live\": false" in plan_text, plan.json())
        add(
            checks,
            "storage_boundary_hides_database_secrets",
            storage.status_code == 200
            and "postgres://" not in storage_text.lower()
            and storage_body.get("database_url_exposed") is False
            and storage_body.get("service_role_key_exposed") is False,
            storage_body,
        )
        add(checks, "existing_self_serve_key_creation_still_works", key.get("returned_once") is True and raw_key.startswith("prmr_alpha_"), {"safe_key_preview": key.get("safe_key_preview")})

        return checks, {
            "log_total": logs_body.get("total_count"),
            "report_total": reports_body.get("total_count"),
            "packet_tester_status": packet_test.status_code,
            "storage_mode": storage_body.get("storage", {}).get("storage_mode"),
            "raw_key_reported": False,
            "secret_safe": True,
            "repository_raw_key_present": product.repository.raw_value_present(raw_key),
        }
    finally:
        client.close()


def main() -> int:
    checks, fixture_summary = run_fixture_checks()
    docs_text = DOC_PATH.read_text(encoding="utf-8", errors="replace") if DOC_PATH.exists() else ""
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "frontend").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.suffix in {".ts", ".tsx"}
    )
    add(checks, "docs_exist", DOC_PATH.exists() and "dashboard observability" in docs_text.lower())
    add(checks, "frontend_contains_observability_shell", all(term in frontend_text for term in ["Generate Continuity Packet", "Upgrade plan", "Request logs", "Continuity reports", "Storage boundary"]))

    regression_commands = [
        ("existing_supabase_auth_audit_still_passes", ["python", "examples/audit_v095_supabase_auth_real_email.py"], ROOT),
        ("existing_external_api_key_usability_audit_still_passes", ["python", "examples/audit_external_api_key_usability.py"], ROOT),
        ("existing_v098_audit_still_passes", ["python", "examples/audit_v098_external_event_contract.py"], ROOT),
        ("existing_v099_packet_audit_still_passes", ["python", "examples/audit_v099_theory_to_product_packet.py"], ROOT),
        ("secret_audit_still_passes", ["python", "examples/audit_v0782_secret_cleanup.py"], ROOT),
    ]
    for name, args, cwd in regression_commands:
        ok, output = command(args, cwd)
        add(checks, name, ok, output)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    type_ok, type_output = command([npm, "run", "typecheck"], ROOT / "frontend")
    add(checks, "typescript_passes", type_ok, type_output)
    build_ok, build_output = command([npm, "run", "build"], ROOT / "frontend")
    add(checks, "production_build_passes", build_ok, build_output)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "1.0",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Afternum API Dashboard Observability + Plan Upgrade Shell",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "public_safe": True,
        "truth_label": "dashboard observability and manual plan-upgrade shell evidence only",
        "features": [
            "paginated request logs",
            "paginated continuity reports",
            "scoped report detail",
            "dashboard packet tester",
            "manual plan upgrade shell",
            "storage boundary panel",
        ],
        "fixture_summary": fixture_summary,
        "stripe_billing_connected": False,
        "raw_keys_exposed": False,
        "database_url_exposed": False,
        "boundary": BOUNDARY_V100,
        "remaining_gaps": [
            "Stripe billing integration",
            "deployed backend/frontend rollout",
            "advanced log filtering UI",
            "enterprise security/compliance review",
        ],
    }
    private = {**public, "public_safe": False, "checks": checks}
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(
        "\n".join(
            [
                "# V1.0 Dashboard Observability",
                "",
                f"Result: {result}",
                f"Checks: {public['checks_passed']}/{public['checks_total']}",
                "",
                "Boundary: manual beta upgrade shell only; no Stripe billing claim.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("PRMR V1.0 Dashboard Observability Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    if failures:
        for item in failures:
            print(f"FAIL: {item['name']}")
            print(str(item.get("detail"))[-600:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
