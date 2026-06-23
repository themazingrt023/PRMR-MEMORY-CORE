"""Audit V0.78 live hosted API smoke behavior."""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

SERVER_MODULE = ROOT / "prmr" / "product" / "api_server_v076.py"
V077_RUNNER = ROOT / "examples" / "run_hosted_api_deployment_prep_v077.py"
V077_PUBLIC = ROOT / "reports" / "v077" / "public_hosted_api_deployment_prep_v077.json"
V077_DOCS = [
    ROOT / "backend" / "README.md",
    ROOT / "docs" / "backend_deployment_v077.md",
    ROOT / "docs" / "hosted_api_smoke_test_v077.md",
]
V078_RUNNER = ROOT / "examples" / "run_live_hosted_api_smoke_v078.py"
ENV_EXAMPLE = ROOT / ".env.example"

REPORT_DIR = ROOT / "reports" / "v078"
PUBLIC_REPORT = REPORT_DIR / "public_live_hosted_api_smoke_v078.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_live_hosted_api_smoke_v078.json"
HTTP_RESULTS_REPORT = REPORT_DIR / "live_hosted_api_http_results_v078.json"
ENV_READINESS_REPORT = REPORT_DIR / "hosted_env_readiness_v078.json"
SCORECARD = REPORT_DIR / "scorecard_v078.md"

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
REQUIRED_ENV_TERMS = [
    "PRMR_API_MODE=hosted_alpha",
    "PRMR_STORAGE_PATH",
    "PRMR_SYNTHETIC_ONLY=true",
    "PRMR_PUBLIC_REPORTS_DIR",
    "PRMR_PRIVATE_REPORTS_DIR",
    "PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000",
    "PRMR_DEFAULT_REQUEST_LIMIT=100",
    "PRMR_HOSTED_API_URL=",
    "PRMR_TEST_API_KEY=",
    "PRMR_TEST_CLIENT_ID=",
    "PRMR_TEST_VAULT_ID=",
    "PRMR_TEST_NAMESPACE=",
]
PUBLIC_FRONTEND_ORIGIN = "https://prmr-memory-core.vercel.app"
LOCAL_FRONTEND_ORIGIN = "http://localhost:3000"

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
]
OVERCLAIMS = [
    "production-ready",
    "production ready",
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
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], extra_env: dict[str, str] | None = None, timeout: int = 240) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
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
        env=env,
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


def strip_boundary_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: strip_boundary_fields(value) for key, value in payload.items() if key != "boundary"}
    if isinstance(payload, list):
        return [strip_boundary_fields(item) for item in payload]
    return payload


def build_audit_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.78 Live Hosted API Smoke Audit",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.78 does not prove live hosted API access unless a real hosted URL is supplied and smoke checks pass.",
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

    add_check(checks, "v076_server_exists", SERVER_MODULE.exists(), str(SERVER_MODULE.relative_to(ROOT)))
    server_module = importlib.import_module("prmr.product.api_server_v076")
    add_check(checks, "fastapi_app_imports", hasattr(server_module, "app") and callable(getattr(server_module, "create_app", None)), "app/create_app")
    routes = set(getattr(server_module, "ROUTES", {}).keys())
    add_check(checks, "required_routes_exist", REQUIRED_ROUTES.issubset(routes), sorted(routes))

    add_check(checks, "v077_deployment_prep_exists", V077_RUNNER.exists() and all(path.exists() for path in V077_DOCS), None)
    v077_public = read_json(V077_PUBLIC) if V077_PUBLIC.exists() else {}
    add_check(checks, "v077_deployment_prep_report_exists", V077_PUBLIC.exists() and v077_public.get("result") == "PASS", v077_public.get("result"))
    add_check(checks, "v078_runner_exists", V078_RUNNER.exists(), str(V078_RUNNER.relative_to(ROOT)))

    runner_source = read(V078_RUNNER)
    add_check(checks, "runner_supports_missing_url_honestly", "NEEDS_HOSTED_URL" in runner_source and "PRMR_HOSTED_API_URL" in runner_source, None)
    add_check(checks, "runner_supports_basic_health_auth_smoke", all(term in runner_source for term in ["health_route_passes", "missing_authorization_blocked", "malformed_authorization_blocked"]), None)
    add_check(checks, "runner_supports_protected_flow", all(term in runner_source for term in ["valid_ingest_passes", "valid_continuity_packet_passes", "valid_reconstruct_passes", "valid_explain_passes", "valid_least_harm_passes", "valid_report_read_passes", "valid_usage_read_passes", "valid_dashboard_state_passes"]), None)
    add_check(checks, "runner_supports_protected_blocked_flow", all(term in runner_source for term in ["wrong_key_blocked", "wrong_vault_blocked", "wrong_namespace_blocked"]), None)
    add_check(checks, "runner_uses_prmr_test_scope_vars", all(term in runner_source for term in ["PRMR_TEST_API_KEY", "PRMR_TEST_CLIENT_ID", "PRMR_TEST_VAULT_ID", "PRMR_TEST_NAMESPACE"]), None)
    add_check(checks, "runner_marks_missing_test_scope_skipped", "SKIPPED_NEEDS_TEST_SCOPE" in runner_source and "controlled_test_scope_present" in runner_source, None)

    env_text = read(ENV_EXAMPLE)
    for term in REQUIRED_ENV_TERMS:
        add_check(checks, f"env_{term.split('=')[0].lower()}_documented", term in env_text, term)
    docs_bundle = "\n".join(read(path) for path in V077_DOCS)
    add_check(checks, "cors_docs_include_frontend_url", PUBLIC_FRONTEND_ORIGIN in docs_bundle and PUBLIC_FRONTEND_ORIGIN in env_text, None)
    add_check(checks, "cors_docs_include_localhost", LOCAL_FRONTEND_ORIGIN in docs_bundle and LOCAL_FRONTEND_ORIGIN in env_text, None)
    add_check(checks, "no_wildcard_cors_claim", "PRMR_ALLOWED_ORIGINS=*" not in env_text and "wildcard CORS should remain false" not in docs_bundle, None)
    add_check(checks, "ephemeral_storage_limit_documented", "ephemeral" in docs_bundle.lower() and "Persistent hosted storage" in docs_bundle, None)

    blank_env = {
        "PRMR_HOSTED_API_URL": "",
        "PRMR_TEST_API_KEY": "",
        "PRMR_TEST_CLIENT_ID": "",
        "PRMR_TEST_VAULT_ID": "",
        "PRMR_TEST_NAMESPACE": "",
    }
    runner = run_command(["python", str(V078_RUNNER)], extra_env=blank_env)
    add_check(checks, "runner_executes_without_url", runner["passed"], runner["output"][-1500:])

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    http_results = read_json(HTTP_RESULTS_REPORT) if HTTP_RESULTS_REPORT.exists() else {}
    env_readiness = read_json(ENV_READINESS_REPORT) if ENV_READINESS_REPORT.exists() else {}

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, HTTP_RESULTS_REPORT, ENV_READINESS_REPORT, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    add_check(checks, "no_url_result_is_needs_hosted_url", public_report.get("result") == "NEEDS_HOSTED_URL" and public_report.get("hosted_url_present") is False, public_report)
    add_check(checks, "no_live_client_access_claim_without_url", public_report.get("hosted_client_access_verified") is False and public_report.get("full_controlled_hosted_smoke_verified") is False, public_report)
    add_check(checks, "public_report_status_level_valid", public_report.get("result") in {"NEEDS_HOSTED_URL", "PASS_BASIC_HOSTED_SMOKE", "PASS_FULL_CONTROLLED_HOSTED_SMOKE", "NEEDS_WORK"}, public_report.get("result"))
    add_check(checks, "http_results_are_public_safe_summaries", http_results.get("public_safe") is True and "safe_http_results" in http_results, http_results)
    add_check(checks, "env_readiness_has_hosted_vars", env_readiness.get("required_hosted_env", {}).get("PRMR_ALLOWED_ORIGINS") == f"{PUBLIC_FRONTEND_ORIGIN},{LOCAL_FRONTEND_ORIGIN}", env_readiness)
    add_check(checks, "env_readiness_documents_no_wildcard_cors", env_readiness.get("cors", {}).get("wildcard_cors_allowed") is False, env_readiness.get("cors"))

    public_bundle = strip_boundary_fields({"public_report": public_report, "http_results": http_results, "env_readiness": env_readiness})
    add_check(checks, "public_reports_have_no_raw_keys", not contains_full_dev_key(public_bundle), None)
    add_check(checks, "public_reports_have_no_secret_terms", not scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "no_production_billing_certification_claims", not scan_terms(public_bundle, OVERCLAIMS), scan_terms(public_bundle, OVERCLAIMS))
    add_check(checks, "private_report_avoids_raw_keys", not contains_full_dev_key(private_report), None)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_audit_scorecard(checks, runner), encoding="utf-8")

    print("PRMR Memory Core V0.78 Live Hosted API Smoke Audit")
    print(f"{'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}")
    print(f"Smoke result level: {public_report.get('result')}")
    print(f"Hosted URL present: {public_report.get('hosted_url_present')}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
