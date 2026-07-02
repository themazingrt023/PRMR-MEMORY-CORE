"""Run V0.82 hosted dashboard connection smoke."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.hosted_dashboard_connection_v082 import (
    BOUNDARY_V082,
    HostedDashboardConnectionV082,
    contains_secret_pattern,
    public_dashboard_summary,
)


REPORT_DIR = ROOT / "reports" / "v082"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_dashboard_connection_v082.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_dashboard_connection_v082.json"
SMOKE_REPORT = REPORT_DIR / "hosted_dashboard_connection_smoke_v082.json"
SCORECARD = REPORT_DIR / "scorecard_v082.md"
FRONTEND_PROXY = ROOT / "frontend" / "app" / "api" / "dashboard" / "state" / "route.ts"
FRONTEND_DASHBOARD = ROOT / "frontend" / "app" / "dashboard" / "page.tsx"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def forbidden_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "production login enabled",
        "self-serve dashboard access enabled",
        "billing enabled",
        "bank-approved",
        "compliance-certified",
        "legal-approved",
        "security-certified",
        "external certification complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def build_public_report(checks: list[dict[str, Any]], smoke_summary: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.82",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Dashboard Connection",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V082,
        "truth_label": "hosted dashboard connection evidence only",
        "backend_dashboard_connection_design": {
            "dashboard_token_header": "X-Dashboard-Token",
            "client_id_header": "X-Client-ID",
            "raw_dashboard_token_returned": False,
            "raw_api_keys_returned": False,
            "client_scoped": True,
        },
        "frontend_proxy_behavior": {
            "route": "/api/dashboard/state",
            "locked_by_default": True,
            "server_side_token_only": True,
            "direct_browser_backend_secret_exposure": False,
        },
        "smoke_summary": smoke_summary,
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke_summary": smoke_summary,
        "restricted_note": "Raw dashboard tokens and raw API keys are intentionally excluded from reports.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.82 Hosted Dashboard Connection",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V082}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command", "", "- RUN: python examples/run_hosted_dashboard_connection_v082.py", ""])
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    connection = HostedDashboardConnectionV082()
    setup = connection.provision_synthetic_demo_scope()
    token = setup["session_a"]["dashboard_token"]
    session_id = setup["session_a"]["session_id"]
    client_a_id = setup["client_a"]["client"]["client_id"]
    client_b_id = setup["client_b"]["client"]["client_id"]
    raw_key_a = setup["client_a"]["raw_api_key"]
    raw_key_b = setup["client_b"]["raw_api_key"]

    valid = connection.get_dashboard_state({"X-Dashboard-Token": token, "X-Client-ID": client_a_id})
    missing = connection.get_dashboard_state({"X-Client-ID": client_a_id})
    invalid = connection.get_dashboard_state({"X-Dashboard-Token": "dash_v082_invalid_local_token", "X-Client-ID": client_a_id})
    wrong_client = connection.get_dashboard_state({"X-Dashboard-Token": token, "X-Client-ID": client_b_id})
    revoked = connection.revoke_session(session_id)
    revoked_result = connection.get_dashboard_state({"X-Dashboard-Token": token, "X-Client-ID": client_a_id})

    valid_summary = public_dashboard_summary(valid)
    missing_summary = public_dashboard_summary(missing)
    invalid_summary = public_dashboard_summary(invalid)
    wrong_summary = public_dashboard_summary(wrong_client)
    revoked_summary = public_dashboard_summary(revoked_result)

    add_check(checks, "backend_dashboard_state_fetch_valid_token", valid.get("status_code") == 200 and valid_summary["status"] == "ok", valid_summary)
    add_check(checks, "missing_dashboard_token_blocked", missing_summary["error_code"] == "missing_dashboard_token" and missing.get("status_code") == 401, missing_summary)
    add_check(checks, "invalid_dashboard_token_blocked", invalid_summary["error_code"] == "invalid_dashboard_token" and invalid.get("status_code") == 401, invalid_summary)
    add_check(checks, "wrong_client_blocked", wrong_summary["error_code"] == "client_scope_denied" and wrong_client.get("status_code") == 403, wrong_summary)
    add_check(checks, "revoked_token_blocked", revoked.get("status") == "revoked" and revoked_summary["error_code"] == "revoked_dashboard_token", revoked_summary)

    dashboard_text = json.dumps(valid.get("body", {}).get("dashboard", {}), sort_keys=True)
    add_check(checks, "dashboard_state_contains_expected_safe_fields", all(valid_summary["panels_present"].values()), valid_summary["panels_present"])
    add_check(checks, "dashboard_state_scoped_to_client_a_only", client_b_id not in dashboard_text, None)
    add_check(checks, "raw_api_keys_absent_from_dashboard_state", raw_key_a not in dashboard_text and raw_key_b not in dashboard_text, None)
    add_check(checks, "raw_dashboard_token_absent_from_dashboard_state", token not in dashboard_text, None)

    proxy_source = read_text(FRONTEND_PROXY)
    page_source = read_text(FRONTEND_DASHBOARD)
    add_check(checks, "frontend_proxy_route_exists", FRONTEND_PROXY.exists(), FRONTEND_PROXY.as_posix())
    add_check(checks, "frontend_proxy_locked_by_default", "CONTROLLED_DASHBOARD_ACCESS_ENABLED" in proxy_source and "lockedResponse()" in proxy_source, None)
    add_check(checks, "frontend_proxy_keeps_token_server_side", "PRMR_DASHBOARD_TOKEN" in proxy_source and "NEXT_PUBLIC_PRMR_DASHBOARD_TOKEN" not in proxy_source, None)
    add_check(checks, "frontend_proxy_removes_raw_credential_fields", all(term in proxy_source for term in ["delete payload.raw_api_key", "delete payload.raw_dashboard_token", "delete payload.dashboard_token", "delete payload.api_key"]), None)
    add_check(checks, "dashboard_page_uses_proxy_not_direct_backend", "/api/dashboard/state" in page_source and "PRMR_DASHBOARD_TOKEN" not in page_source, None)

    smoke_summary = {
        "valid": valid_summary,
        "missing_token": missing_summary,
        "invalid_token": invalid_summary,
        "wrong_client": wrong_summary,
        "revoked_token": revoked_summary,
        "frontend_proxy_locked_by_default": True,
        "raw_token_in_summary": False,
        "raw_api_key_in_summary": False,
        "synthetic_clients": [client_a_id, client_b_id],
    }
    public_report = build_public_report(checks, smoke_summary)
    add_check(checks, "public_frontend_does_not_expose_raw_key_or_token", token not in json.dumps(public_report, sort_keys=True) and raw_key_a not in json.dumps(public_report, sort_keys=True), None)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_claims", not forbidden_claim_hits(public_report), forbidden_claim_hits(public_report))

    public_report = build_public_report(checks, smoke_summary)
    private_report = build_private_report(public_report, checks, smoke_summary)
    smoke_report = {
        "version": "0.82",
        "public_safe": True,
        "boundary": BOUNDARY_V082,
        "result": public_report["result"],
        "smoke_summary": smoke_summary,
    }
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.82 Hosted Dashboard Connection")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Valid dashboard state: {public_report['smoke_summary']['valid']['status']}")
    print(f"Wrong client: {public_report['smoke_summary']['wrong_client']['error_code']}")
    print(f"Missing token: {public_report['smoke_summary']['missing_token']['error_code']}")
    print(f"Invalid token: {public_report['smoke_summary']['invalid_token']['error_code']}")
    print(f"Revoked token: {public_report['smoke_summary']['revoked_token']['error_code']}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
