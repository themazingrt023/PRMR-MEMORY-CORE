"""Audit V0.76 real local HTTP API server."""

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

WRAPPER_MODULE = ROOT / "prmr" / "product" / "hosted_api_wrapper_v075.py"
SERVER_MODULE = ROOT / "prmr" / "product" / "api_server_v076.py"
CONFIG_MODULE = ROOT / "prmr" / "product" / "api_config_v075.py"
STORAGE_MODULE = ROOT / "prmr" / "product" / "persistent_storage_v074.py"
RUNNER = ROOT / "examples" / "run_api_server_v076.py"
ENV_EXAMPLE = ROOT / ".env.example"
REPORT_DIR = ROOT / "reports" / "v076"
PUBLIC_REPORT = REPORT_DIR / "public_api_server_v076.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_server_v076.json"
HTTP_SMOKE_REPORT = REPORT_DIR / "api_server_http_smoke_v076.json"
REQUEST_LOG = REPORT_DIR / "api_server_request_log_v076.json"
STORAGE_STATE = REPORT_DIR / "api_server_storage_state_v076.json"
SCORECARD = REPORT_DIR / "scorecard_v076.md"

REQUIRED_REPORTS = [PUBLIC_REPORT, PRIVATE_REPORT, HTTP_SMOKE_REPORT, REQUEST_LOG, STORAGE_STATE, SCORECARD]
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
REQUIRED_ENV = [
    "PRMR_API_MODE=local_alpha",
    "PRMR_STORAGE_PATH=reports/v076/prmr_api_server_v076.sqlite",
    "PRMR_SYNTHETIC_ONLY=true",
    "PRMR_PUBLIC_REPORTS_DIR=reports/v076",
    "PRMR_PRIVATE_REPORTS_DIR=reports/v076",
    "PRMR_ALLOWED_ORIGINS=http://localhost:3000",
]
PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
    "key_hash",
    "validation_outcomes",
    "private_trace",
]
OVERCLAIM_PATTERNS = [
    "production-ready",
    "production ready",
    "hosted client access is live",
    "live api access granted",
    "billing enabled",
    "stripe",
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], timeout: int = 300) -> dict[str, Any]:
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


def source_contains(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8")


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.76 API Server Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.76 is a real local HTTP API server and local smoke-test layer only. Hosted live client access comes after deployment and live smoke verification.",
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

    add_check(checks, "v075_wrapper_exists", WRAPPER_MODULE.exists(), str(WRAPPER_MODULE.relative_to(ROOT)))
    add_check(checks, "v076_server_exists", SERVER_MODULE.exists(), str(SERVER_MODULE.relative_to(ROOT)))
    add_check(checks, "v075_config_exists", CONFIG_MODULE.exists(), str(CONFIG_MODULE.relative_to(ROOT)))
    add_check(checks, "v074_storage_exists", STORAGE_MODULE.exists(), str(STORAGE_MODULE.relative_to(ROOT)))

    server_module = importlib.import_module("prmr.product.api_server_v076")
    routes = getattr(server_module, "ROUTES", {})
    create_app = getattr(server_module, "create_app", None)
    add_check(checks, "create_app_exists", callable(create_app), "create_app")
    add_check(checks, "fastapi_framework_used", getattr(server_module, "SERVER_FRAMEWORK", "") == "FastAPI", getattr(server_module, "SERVER_FRAMEWORK", ""))
    add_check(checks, "all_required_http_routes_declared", REQUIRED_ROUTES.issubset(set(routes.keys())), sorted(routes.keys()))

    if callable(create_app):
        app = create_app()
        app_paths = {f"{method} {route.path}" for route in app.routes for method in getattr(route, "methods", set())}
        expected_paths = {
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
        add_check(checks, "all_required_fastapi_routes_exist", expected_paths.issubset(app_paths), sorted(app_paths))
    else:
        add_check(checks, "all_required_fastapi_routes_exist", False, "create_app missing")

    server_source = SERVER_MODULE.read_text(encoding="utf-8") if SERVER_MODULE.exists() else ""
    add_check(checks, "required_header_shape_documented", all(header in server_source for header in ["Authorization: Bearer <api_key>", "X-Client-ID", "X-Vault-ID", "X-Namespace"]), None)
    add_check(checks, "cors_security_prep_in_server", "CORSMiddleware" in server_source and "allow_origins=active_config.allowed_origins" in server_source and "allow_headers" in server_source, None)
    add_check(checks, "wrapper_storage_imports_present", all(term in server_source for term in ["hosted_api_wrapper_v075", "api_config_v075", "PRMRHostedAPIWrapper"]), None)

    runner = run_command(["python", str(RUNNER)])
    add_check(checks, "runner_passes", runner["passed"], runner["output"][-1500:])

    for path in REQUIRED_REPORTS:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    smoke_report = read_json(HTTP_SMOKE_REPORT) if HTTP_SMOKE_REPORT.exists() else {}
    request_log = read_json(REQUEST_LOG) if REQUEST_LOG.exists() else {}
    storage_state = read_json(STORAGE_STATE) if STORAGE_STATE.exists() else {}
    private_checks = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}
    http_results = private_report.get("http_results", {})
    smoke_summary = public_report.get("smoke_summary", {})

    for check_name in [
        "health_route_works",
        "valid_http_ingest_works",
        "valid_http_packet_works",
        "valid_http_reconstruct_works",
        "valid_http_explain_works",
        "valid_http_least_harm_action_works",
        "valid_http_report_read_works",
        "valid_http_usage_read_works",
        "valid_http_dashboard_state_read_works",
        "missing_authorization_blocked",
        "malformed_authorization_blocked",
        "wrong_key_blocked",
        "revoked_key_blocked",
        "rotated_old_key_blocked",
        "wrong_client_blocked",
        "wrong_vault_blocked",
        "wrong_namespace_blocked",
        "usage_limit_exceeded_blocked",
        "request_logs_persisted",
        "usage_logs_persisted",
        "dashboard_state_persisted",
        "storage_state_updated",
        "safe_key_previews_only",
        "raw_api_keys_absent_from_public_outputs",
        "no_real_client_data_used",
        "local_cors_security_prep_exists",
    ]:
        add_check(checks, check_name, private_checks.get(check_name) is True, private_checks.get(check_name))

    add_check(checks, "response_shape_valid_success", all(http_results.get(name, {}).get("body", {}).get("status") == "ok" and http_results.get(name, {}).get("body", {}).get("public_safe") is True and http_results.get(name, {}).get("body", {}).get("request_id") for name in ["ingest", "packet", "reconstruct", "explain", "least_harm_action", "report", "usage", "dashboard_state"]), None)
    add_check(checks, "response_shape_valid_blocked", all(http_results.get(name, {}).get("body", {}).get("status") == "error" and http_results.get(name, {}).get("body", {}).get("public_safe") is True and isinstance(http_results.get(name, {}).get("body", {}).get("error"), dict) for name in ["missing_authorization", "malformed_authorization", "wrong_key", "revoked_key", "rotated_old_key", "wrong_client", "wrong_vault", "wrong_namespace", "usage_limit_exceeded"]), None)
    add_check(checks, "dashboard_state_http_memory_health", http_results.get("dashboard_state", {}).get("body", {}).get("dashboard", {}).get("memory_health_panel", {}).get("status") == "http_api_server_connected", http_results.get("dashboard_state", {}).get("body", {}).get("dashboard", {}).get("memory_health_panel"))
    add_check(checks, "storage_has_request_logs", len(storage_state.get("request_logs", [])) >= 18 and len(request_log.get("request_logs", [])) >= 18, {"storage": len(storage_state.get("request_logs", [])), "export": len(request_log.get("request_logs", []))})
    add_check(checks, "storage_has_usage_logs", len(storage_state.get("usage_logs", [])) >= 18, len(storage_state.get("usage_logs", [])))
    add_check(checks, "storage_has_dashboard_refresh", bool(storage_state.get("dashboard_refresh_records")), storage_state.get("dashboard_refresh_records", [])[-1:] if storage_state.get("dashboard_refresh_records") else [])
    add_check(checks, "storage_has_events_packets_reports", len(storage_state.get("memory_events", [])) >= 5 and len(storage_state.get("continuity_packets", [])) >= 1 and len(storage_state.get("reports", [])) >= 1, {key: len(storage_state.get(key, [])) for key in ["memory_events", "continuity_packets", "reports"]})
    add_check(checks, "safe_key_previews_only_in_public_storage", not scan_terms(storage_state.get("api_key_records", []), ["key_hash"]) and not contains_full_dev_key(storage_state.get("api_key_records", [])), storage_state.get("api_key_records", []))
    add_check(checks, "smoke_summary_matches_expected_counts", smoke_summary.get("allowed_request_count", 0) >= 11 and smoke_summary.get("blocked_request_count", 0) >= 9 and smoke_summary.get("memory_health") == "http_api_server_connected", smoke_summary)

    env_text = ENV_EXAMPLE.read_text(encoding="utf-8") if ENV_EXAMPLE.exists() else ""
    add_check(checks, "env_example_exists", ENV_EXAMPLE.exists(), str(ENV_EXAMPLE.relative_to(ROOT)))
    for env_line in REQUIRED_ENV:
        add_check(checks, f"env_{env_line.split('=')[0].lower()}_present", env_line in env_text, env_line)

    public_bundle = {"public_report": public_report, "smoke_report": smoke_report, "request_log": request_log, "storage_state": storage_state}
    add_check(checks, "public_reports_have_no_raw_keys", not contains_full_dev_key(public_bundle), None)
    add_check(checks, "public_reports_have_no_private_terms", not scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "public_reports_have_no_punitive_terms", not scan_terms(public_bundle, PUNITIVE_TERMS), scan_terms(public_bundle, PUNITIVE_TERMS))
    add_check(checks, "no_hosted_live_api_claim", "hosted_live_client_access" in public_report and public_report.get("hosted_live_client_access") is False and not scan_terms(public_bundle, ["hosted client access is live", "live api access granted"]), public_report.get("hosted_live_client_access"))
    add_check(checks, "no_production_readiness_claim", not scan_terms(public_bundle, ["production-ready", "production ready"]), scan_terms(public_bundle, ["production-ready", "production ready"]))
    add_check(checks, "no_billing_claim", not scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]), scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]))
    add_check(checks, "no_certification_or_approval_claims", not scan_terms(public_bundle, OVERCLAIM_PATTERNS), scan_terms(public_bundle, OVERCLAIM_PATTERNS))
    add_check(checks, "no_real_client_data_used_public", all(str(client.get("client_id", "")).startswith("client_v075_synthetic") for client in storage_state.get("clients", [])), storage_state.get("clients", []))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    print("PRMR Memory Core V0.76 API Server Audit")
    print(f"{'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
