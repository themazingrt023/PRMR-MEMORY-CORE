"""Audit V0.75 hosted backend API wrapper."""

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

STORAGE_MODULE = ROOT / "prmr" / "product" / "persistent_storage_v074.py"
CONFIG_MODULE = ROOT / "prmr" / "product" / "api_config_v075.py"
WRAPPER_MODULE = ROOT / "prmr" / "product" / "hosted_api_wrapper_v075.py"
RUNNER = ROOT / "examples" / "run_hosted_api_wrapper_v075.py"
REPORT_DIR = ROOT / "reports" / "v075"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_api_wrapper_v075.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_api_wrapper_v075.json"
REQUEST_LOG = REPORT_DIR / "api_wrapper_request_log_v075.json"
STORAGE_STATE = REPORT_DIR / "api_wrapper_storage_state_v075.json"
SCORECARD = REPORT_DIR / "scorecard_v075.md"

REQUIRED_REPORTS = [PUBLIC_REPORT, PRIVATE_REPORT, REQUEST_LOG, STORAGE_STATE, SCORECARD]
REQUIRED_ROUTES = {
    "GET /health",
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "GET /v1/dashboard/state",
}
REQUIRED_HANDLERS = [
    "health",
    "events_ingest",
    "continuity_packet",
    "memory_reconstruct",
    "explain",
    "least_harm_action",
    "get_report",
    "get_usage",
    "get_dashboard_state",
]
PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
]
OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client access is live",
    "live api access granted",
    "billing enabled",
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], timeout: int = 240) -> dict[str, Any]:
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


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.75 Hosted API Wrapper Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.75 is a local/deployable backend API wrapper only. Live hosted client access comes after deployment and smoke testing.",
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

    add_check(checks, "v074_storage_module_exists", STORAGE_MODULE.exists(), str(STORAGE_MODULE.relative_to(ROOT)))
    add_check(checks, "v075_api_wrapper_exists", WRAPPER_MODULE.exists(), str(WRAPPER_MODULE.relative_to(ROOT)))
    add_check(checks, "config_module_exists", CONFIG_MODULE.exists(), str(CONFIG_MODULE.relative_to(ROOT)))

    wrapper_module = importlib.import_module("prmr.product.hosted_api_wrapper_v075")
    config_module = importlib.import_module("prmr.product.api_config_v075")
    wrapper_class = getattr(wrapper_module, "PRMRHostedAPIWrapper", None)
    routes = getattr(wrapper_module, "ROUTES", {})
    add_check(checks, "PRMRHostedAPIWrapper_exists", wrapper_class is not None, "PRMRHostedAPIWrapper")
    add_check(checks, "load_api_config_exists", hasattr(config_module, "load_api_config"), "load_api_config")
    add_check(checks, "all_required_routes_exist", REQUIRED_ROUTES.issubset(set(routes.keys())), sorted(routes.keys()))
    for handler in REQUIRED_HANDLERS:
        add_check(checks, f"{handler}_handler_exists", hasattr(wrapper_class, handler), handler)

    runner = run_command(["python", str(RUNNER)])
    add_check(checks, "runner_passes", runner["passed"], runner["output"][-1500:])

    for path in REQUIRED_REPORTS:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    request_log = read_json(REQUEST_LOG) if REQUEST_LOG.exists() else {}
    storage_state = read_json(STORAGE_STATE) if STORAGE_STATE.exists() else {}
    private_checks = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}
    route_results = private_report.get("route_results", {})
    dashboard_state = route_results.get("final_dashboard_state", {}).get("body", {}).get("dashboard", {})

    for check_name in [
        "health_route_works",
        "valid_ingest_works",
        "valid_continuity_packet_works",
        "valid_reconstruct_works",
        "valid_explain_works",
        "valid_least_harm_action_works",
        "valid_report_read_works",
        "valid_usage_read_works",
        "valid_dashboard_state_read_works",
        "valid_calls_persist_storage_records",
        "request_logs_persist",
        "usage_logs_persist",
        "dashboard_refresh_persists",
        "missing_key_blocked",
        "wrong_key_blocked",
        "revoked_key_blocked",
        "rotated_key_blocked",
        "wrong_client_blocked",
        "wrong_vault_blocked",
        "wrong_namespace_blocked",
        "usage_limit_exceeded_blocked",
        "dashboard_state_uses_safe_key_previews_only",
        "raw_api_keys_absent_from_dashboard_state",
        "no_real_client_data_used",
    ]:
        add_check(checks, check_name, private_checks.get(check_name) is True, private_checks.get(check_name))

    add_check(checks, "dashboard_state_has_client_overview", bool(dashboard_state.get("client_overview", {}).get("client_id")), dashboard_state.get("client_overview"))
    add_check(checks, "dashboard_state_has_safe_key_previews_only", not contains_full_dev_key(dashboard_state) and not scan_terms(dashboard_state.get("api_key_panel", {}), ["key_hash", "raw_api_key"]), None)
    add_check(checks, "dashboard_state_has_vault_namespace_summary", bool(dashboard_state.get("vault_namespace_panel", {}).get("namespaces")), dashboard_state.get("vault_namespace_panel"))
    add_check(checks, "dashboard_state_has_usage_counts", dashboard_state.get("usage_overview", {}).get("allowed_request_count", 0) >= 11 and dashboard_state.get("usage_overview", {}).get("blocked_request_count", 0) >= 7, dashboard_state.get("usage_overview"))
    add_check(checks, "dashboard_state_has_request_logs", len(dashboard_state.get("request_log_summary", {}).get("rows", [])) >= 18, len(dashboard_state.get("request_log_summary", {}).get("rows", [])))
    add_check(checks, "dashboard_state_has_report_refs", bool(dashboard_state.get("reports_panel", {}).get("reports")), dashboard_state.get("reports_panel"))
    add_check(checks, "dashboard_state_has_memory_health", dashboard_state.get("memory_health_panel", {}).get("status") == "api_wrapper_connected", dashboard_state.get("memory_health_panel"))
    add_check(checks, "request_log_export_persisted", len(request_log.get("request_logs", [])) >= 18, len(request_log.get("request_logs", [])))
    add_check(checks, "storage_state_persisted_records", len(storage_state.get("clients", [])) >= 1 and len(storage_state.get("memory_events", [])) >= 5 and len(storage_state.get("request_logs", [])) >= 18, None)

    public_bundle = {"public_report": public_report, "request_log": request_log, "storage_state": storage_state}
    add_check(checks, "raw_api_keys_absent_from_public_reports", not contains_full_dev_key(public_bundle) and not scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "raw_api_keys_absent_from_dashboard_state", not contains_full_dev_key(dashboard_state), None)
    add_check(checks, "no_real_client_data_used_public", all(str(client.get("client_id", "")).startswith("client_v075_synthetic") for client in storage_state.get("clients", [])), storage_state.get("clients", []))
    add_check(checks, "no_production_readiness_claims", not scan_terms(public_bundle, ["production-ready", "production ready"]), scan_terms(public_bundle, ["production-ready", "production ready"]))
    add_check(checks, "no_billing_claims", not scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]), scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]))
    add_check(checks, "no_certification_or_approval_claims", not scan_terms(public_bundle, OVERCLAIMS), scan_terms(public_bundle, OVERCLAIMS))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    print("PRMR Memory Core V0.75 Hosted API Wrapper Audit")
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
