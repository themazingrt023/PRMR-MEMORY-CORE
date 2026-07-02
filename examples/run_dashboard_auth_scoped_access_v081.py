"""Run V0.81 dashboard auth scoped access smoke."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.dashboard_auth_v081 import BOUNDARY_V081, DashboardAuthV081


REPORT_DIR = ROOT / "reports" / "v081"
PUBLIC_REPORT = REPORT_DIR / "public_dashboard_auth_scoped_access_v081.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_dashboard_auth_scoped_access_v081.json"
SMOKE_REPORT = REPORT_DIR / "dashboard_auth_smoke_v081.json"
SCORECARD = REPORT_DIR / "scorecard_v081.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v081_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def forbidden_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "self-serve login enabled",
        "production auth enabled",
        "production authentication enabled",
        "production authentication certified",
        "production-ready",
        "production ready",
        "billing enabled",
        "bank-approved",
        "compliance-certified",
        "legal-approved",
        "security-certified",
        "external certification",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def safe_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    dashboard = state.get("dashboard", {}) if isinstance(state, dict) else {}
    return {
        "status": state.get("status"),
        "status_code": state.get("status_code"),
        "client_id": dashboard.get("client_overview", {}).get("client_id"),
        "panels_present": {
            "client_overview": bool(dashboard.get("client_overview")),
            "api_key_panel": bool(dashboard.get("api_key_panel")),
            "vault_namespace_panel": bool(dashboard.get("vault_namespace_panel")),
            "usage_overview": bool(dashboard.get("usage_overview")),
            "request_log_summary": bool(dashboard.get("request_log_summary")),
            "reports_panel": bool(dashboard.get("reports_panel")),
            "memory_health_panel": bool(dashboard.get("memory_health_panel")),
        },
        "error_code": state.get("error", {}).get("code") if isinstance(state.get("error"), dict) else None,
        "raw_api_keys_exposed": dashboard.get("api_key_panel", {}).get("raw_api_keys_exposed"),
        "raw_token_exposed": dashboard.get("dashboard_session", {}).get("raw_token_exposed"),
    }


def build_public_report(checks: list[dict[str, Any]], smoke_summary: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.81",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Dashboard Auth And Scoped Client Access",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V081,
        "truth_label": "dashboard scoped access evidence only",
        "dashboard_auth_design": {
            "synthetic_session_tokens": True,
            "session_tokens_hashed_internally": True,
            "raw_dashboard_token_in_public_report": False,
            "raw_api_keys_in_dashboard_state": False,
            "client_scoped_dashboard_state": True,
            "self_serve_login": False,
            "billing": False,
            "production_auth_claimed": False,
        },
        "smoke_summary": smoke_summary,
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke_summary": smoke_summary,
        "restricted_note": "Raw dashboard tokens and raw API keys are intentionally excluded from this private report.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.81 Dashboard Auth Scoped Access",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V081}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command", "", "- RUN: python examples/run_dashboard_auth_scoped_access_v081.py", ""])
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    auth = DashboardAuthV081()

    client_a = auth.create_client_scope(
        client_id="client_v081_alpha_a",
        organisation="Synthetic V0.81 Alpha Client A",
        contact_email="synthetic-a-v081@example.test",
        vault_id="vault_v081_alpha_a",
    )
    client_b = auth.create_client_scope(
        client_id="client_v081_alpha_b",
        organisation="Synthetic V0.81 Alpha Client B",
        contact_email="synthetic-b-v081@example.test",
        vault_id="vault_v081_alpha_b",
    )
    auth.record_synthetic_activity(
        client_id=client_a["client"]["client_id"],
        vault_id=client_a["vault"]["vault_id"],
        namespace=client_a["namespace"]["namespace"],
        raw_api_key=client_a["raw_api_key"],
    )
    auth.record_synthetic_activity(
        client_id=client_b["client"]["client_id"],
        vault_id=client_b["vault"]["vault_id"],
        namespace=client_b["namespace"]["namespace"],
        raw_api_key=client_b["raw_api_key"],
    )
    session_a = auth.create_dashboard_session(client_id=client_a["client"]["client_id"])
    token_a = session_a["dashboard_token"]

    state_a = auth.dashboard_state(raw_token=token_a, requested_client_id=client_a["client"]["client_id"])
    state_b_with_a = auth.dashboard_state(raw_token=token_a, requested_client_id=client_b["client"]["client_id"])
    missing_token = auth.dashboard_state(raw_token=None, requested_client_id=client_a["client"]["client_id"])
    invalid_token = auth.dashboard_state(raw_token="dash_v081_invalid_local_token", requested_client_id=client_a["client"]["client_id"])

    dashboard = state_a.get("dashboard", {})
    add_check(checks, "client_a_dashboard_access_works", state_a.get("status") == "ok" and dashboard.get("client_overview", {}).get("client_id") == client_a["client"]["client_id"], safe_state_summary(state_a))
    add_check(checks, "client_b_isolation_works", state_b_with_a.get("status") == "error" and state_b_with_a.get("error", {}).get("code") == "client_scope_denied", safe_state_summary(state_b_with_a))
    add_check(checks, "missing_token_blocked", missing_token.get("status") == "error" and missing_token.get("error", {}).get("code") == "missing_dashboard_token", safe_state_summary(missing_token))
    add_check(checks, "invalid_token_blocked", invalid_token.get("status") == "error" and invalid_token.get("error", {}).get("code") == "invalid_dashboard_token", safe_state_summary(invalid_token))

    required_panels = [
        "client_overview",
        "api_key_panel",
        "vault_namespace_panel",
        "usage_overview",
        "request_log_summary",
        "reports_panel",
        "memory_health_panel",
    ]
    add_check(checks, "dashboard_state_includes_required_panels", all(bool(dashboard.get(panel)) for panel in required_panels), safe_state_summary(state_a))
    add_check(checks, "dashboard_state_scoped_to_client_a_only", client_b["client"]["client_id"] not in json.dumps(dashboard, sort_keys=True), None)
    add_check(checks, "dashboard_state_has_safe_key_preview_hash_only", all("safe_key_preview" in record and "key_hash_prefix" in record and "key_hash" not in record for record in dashboard.get("api_key_panel", {}).get("records", [])), dashboard.get("api_key_panel"))
    add_check(checks, "raw_api_key_absent_from_dashboard_state", client_a["raw_api_key"] not in json.dumps(state_a, sort_keys=True) and client_b["raw_api_key"] not in json.dumps(state_a, sort_keys=True), None)
    add_check(checks, "raw_dashboard_token_absent_from_dashboard_state", token_a not in json.dumps(state_a, sort_keys=True), None)

    revoked = auth.revoke_session(session_id=session_a["session_id"])
    revoked_state = auth.dashboard_state(raw_token=token_a, requested_client_id=client_a["client"]["client_id"])
    add_check(checks, "revoked_token_blocked", revoked.get("status") == "revoked" and revoked_state.get("error", {}).get("code") == "revoked_dashboard_token", safe_state_summary(revoked_state))

    smoke_summary = {
        "client_a_state": safe_state_summary(state_a),
        "client_b_with_a_token": safe_state_summary(state_b_with_a),
        "missing_token": safe_state_summary(missing_token),
        "invalid_token": safe_state_summary(invalid_token),
        "revoked_token": safe_state_summary(revoked_state),
        "safe_session_preview": session_a["safe_token_preview"],
        "raw_token_in_summary": False,
        "raw_api_key_in_summary": False,
        "synthetic_clients": [client_a["client"]["client_id"], client_b["client"]["client_id"]],
    }
    public_report = build_public_report(checks, smoke_summary)
    add_check(checks, "raw_dashboard_token_absent_from_public_report", token_a not in json.dumps(public_report, sort_keys=True), None)
    add_check(checks, "raw_api_key_absent_from_public_report", client_a["raw_api_key"] not in json.dumps(public_report, sort_keys=True) and client_b["raw_api_key"] not in json.dumps(public_report, sort_keys=True), None)
    add_check(checks, "public_report_contains_no_secret_patterns", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_claims", not forbidden_claim_hits(public_report), forbidden_claim_hits(public_report))
    add_check(checks, "no_real_client_data_used", all("Synthetic V0.81" in item["organisation"] and item["contact_email"].endswith(".test") for item in [client_a["client"], client_b["client"]]), None)

    public_report = build_public_report(checks, smoke_summary)
    private_report = build_private_report(public_report, checks, smoke_summary)
    smoke_report = {
        "version": "0.81",
        "public_safe": True,
        "boundary": BOUNDARY_V081,
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

    print("PRMR Memory Core V0.81 Dashboard Auth Scoped Access")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Client A access: {public_report['smoke_summary']['client_a_state']['status']}")
    print(f"Client B with A token: {public_report['smoke_summary']['client_b_with_a_token']['error_code']}")
    print(f"Missing token: {public_report['smoke_summary']['missing_token']['error_code']}")
    print(f"Invalid token: {public_report['smoke_summary']['invalid_token']['error_code']}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
