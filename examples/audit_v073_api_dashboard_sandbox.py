"""Audit V0.73 end-to-end API + dashboard sandbox."""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

API_SURFACE = ROOT / "prmr" / "product" / "controlled_alpha_api_v071.py"
DASHBOARD_AGGREGATOR = ROOT / "prmr" / "product" / "client_dashboard_v072.py"
SANDBOX_MODULE = ROOT / "prmr" / "product" / "api_dashboard_sandbox_v073.py"
RUNNER = ROOT / "examples" / "run_api_dashboard_sandbox_v073.py"
REPORT_DIR = ROOT / "reports" / "v073"
PUBLIC_REPORT = REPORT_DIR / "public_api_dashboard_sandbox_v073.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_dashboard_sandbox_v073.json"
DASHBOARD_REFRESH = REPORT_DIR / "dashboard_refresh_state_v073.json"
REQUEST_LOG = REPORT_DIR / "api_dashboard_request_log_v073.json"
SCORECARD = REPORT_DIR / "scorecard_v073.md"
DEPLOYMENT_MODE = ROOT / "frontend" / "lib" / "deploymentMode.ts"
DEMO_RUN_ROUTE = ROOT / "frontend" / "app" / "api" / "demo" / "run" / "route.ts"

REQUIRED_REPORTS = [PUBLIC_REPORT, PRIVATE_REPORT, DASHBOARD_REFRESH, REQUEST_LOG, SCORECARD]

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "key_hash",
    "validation_outcomes",
    "debug",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client api access is live",
    "live hosted api access",
    "live api access granted",
    "billing enabled",
    "self-serve access enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

REQUIRED_BLOCKED_REASONS = {
    "invalid_key",
    "vault_denied",
    "namespace_denied",
    "revoked_key",
    "usage_limit_exceeded",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.73 API + Dashboard Sandbox Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.73 is local/deployable alpha sandbox evidence only. Hosted client access comes later.",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    lines.extend(["", "## Command Results", "", f"- {'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}", ""])
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "v071_api_surface_exists", API_SURFACE.exists(), str(API_SURFACE.relative_to(ROOT)))
    add_check(checks, "v072_dashboard_aggregator_exists", DASHBOARD_AGGREGATOR.exists(), str(DASHBOARD_AGGREGATOR.relative_to(ROOT)))
    add_check(checks, "v073_sandbox_module_exists", SANDBOX_MODULE.exists(), str(SANDBOX_MODULE.relative_to(ROOT)))

    module = importlib.import_module("prmr.product.api_dashboard_sandbox_v073")
    add_check(checks, "PRMRAPIDashboardSandbox_exists", hasattr(module, "PRMRAPIDashboardSandbox"), "PRMRAPIDashboardSandbox")
    add_check(checks, "build_dashboard_refresh_state_exists", hasattr(module, "build_dashboard_refresh_state"), "build_dashboard_refresh_state")
    add_check(checks, "validate_sandbox_result_exists", hasattr(module, "validate_sandbox_result"), "validate_sandbox_result")

    runner = run_command(["python", str(RUNNER)])
    add_check(checks, "runner_passes", runner["passed"], runner["output"][-1200:])

    for path in REQUIRED_REPORTS:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    dashboard = read_json(DASHBOARD_REFRESH) if DASHBOARD_REFRESH.exists() else {}
    request_log = read_json(REQUEST_LOG) if REQUEST_LOG.exists() else {}
    private_checks = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}

    required_private_checks = [
        "valid_ingest_updates_sandbox_state",
        "continuity_packet_generated",
        "reconstruction_generated",
        "explanation_generated",
        "least_harm_action_generated",
        "report_generated",
        "usage_generated",
        "dashboard_refresh_state_generated",
        "dashboard_shows_client_overview",
        "dashboard_shows_safe_key_preview_only",
        "dashboard_shows_vault_namespace_summary",
        "dashboard_shows_allowed_request_count",
        "dashboard_shows_blocked_request_count",
        "dashboard_shows_request_log_entries",
        "dashboard_shows_report_references",
        "dashboard_shows_memory_health",
        "blocked_requests_reflected_safely",
        "wrong_key_blocked",
        "wrong_vault_blocked",
        "wrong_namespace_blocked",
        "revoked_key_blocked",
        "usage_limit_exceeded_blocked",
    ]
    for check_name in required_private_checks:
        add_check(checks, check_name, private_checks.get(check_name) is True, private_checks.get(check_name))

    add_check(checks, "dashboard_has_client_overview", bool(dashboard.get("client_overview", {}).get("client_id")), dashboard.get("client_overview"))
    key_text = json.dumps(dashboard.get("api_key_panel", {}), sort_keys=True)
    add_check(checks, "dashboard_safe_key_preview_only", "safe_key_preview" in key_text and "key_hash" not in key_text and not contains_full_dev_key(key_text), None)
    add_check(checks, "dashboard_has_vault_namespace_summary", bool(dashboard.get("vault_namespace_panel", {}).get("namespaces")), dashboard.get("vault_namespace_panel"))
    add_check(checks, "dashboard_has_allowed_count", dashboard.get("usage_overview", {}).get("allowed_request_count", 0) >= 10, dashboard.get("usage_overview"))
    add_check(checks, "dashboard_has_blocked_count", dashboard.get("usage_overview", {}).get("blocked_request_count", 0) >= 5, dashboard.get("usage_overview"))
    add_check(checks, "dashboard_has_request_log_entries", len(dashboard.get("request_log_summary", {}).get("rows", [])) >= 15, len(dashboard.get("request_log_summary", {}).get("rows", [])))
    add_check(checks, "dashboard_has_report_references", bool(dashboard.get("reports_panel", {}).get("reports")), dashboard.get("reports_panel"))
    add_check(checks, "dashboard_has_memory_health", dashboard.get("memory_health_panel", {}).get("status") == "local_sandbox_connected", dashboard.get("memory_health_panel"))

    blocked_reasons = set(dashboard.get("request_log_summary", {}).get("blocked_reasons", {}).keys())
    add_check(checks, "blocked_reasons_complete", REQUIRED_BLOCKED_REASONS.issubset(blocked_reasons), sorted(blocked_reasons))
    add_check(checks, "request_log_file_has_entries", len(request_log.get("request_log", [])) >= 15, len(request_log.get("request_log", [])))

    add_check(checks, "no_raw_keys_in_public_report", not contains_full_dev_key(public_report) and not scan_terms(public_report, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_report, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "no_raw_keys_in_dashboard_data", not contains_full_dev_key(dashboard) and not scan_terms(dashboard, ["raw_api_key", "full_api_key", "key_hash"]), None)
    add_check(checks, "no_real_client_data_used", dashboard.get("client_overview", {}).get("synthetic_only") is True, dashboard.get("client_overview"))

    deployment_source = DEPLOYMENT_MODE.read_text(encoding="utf-8") if DEPLOYMENT_MODE.exists() else ""
    demo_route_source = DEMO_RUN_ROUTE.read_text(encoding="utf-8") if DEMO_RUN_ROUTE.exists() else ""
    add_check(
        checks,
        "public_demo_bridge_is_not_exposed",
        "isPublicDemoBridgeEnabled" in deployment_source and "demoBridgeDisabledResponse" in demo_route_source,
        {"deployment_mode": DEPLOYMENT_MODE.exists(), "demo_route": DEMO_RUN_ROUTE.exists()},
    )
    add_check(checks, "demo_bridge_note_present", "public frontend demo bridge remains disabled" in json.dumps(public_report).lower(), public_report.get("demo_bridge_note"))

    combined_public = {"public_report": public_report, "dashboard": dashboard, "request_log": request_log}
    add_check(checks, "no_hosted_live_api_claims", not scan_terms(combined_public, ["hosted client api access is live", "live hosted api access", "live api access granted"]), scan_terms(combined_public, ["hosted client api access is live", "live hosted api access", "live api access granted"]))
    add_check(checks, "no_production_readiness_claims", not scan_terms(combined_public, ["production-ready", "production ready"]), scan_terms(combined_public, ["production-ready", "production ready"]))
    add_check(checks, "no_billing_claims", not scan_terms(combined_public, ["billing enabled", "stripe", "payment processed"]), scan_terms(combined_public, ["billing enabled", "stripe", "payment processed"]))
    add_check(checks, "no_certification_or_approval_claims", not scan_terms(combined_public, OVERCLAIMS), scan_terms(combined_public, OVERCLAIMS))
    add_check(checks, "public_wording_non_punitive", not scan_terms(combined_public, PUNITIVE_TERMS), scan_terms(combined_public, PUNITIVE_TERMS))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    print("PRMR Memory Core V0.73 API + Dashboard Sandbox Audit")
    print(f"{'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
