"""Run V0.78 live hosted API smoke checks.

This runner does not claim live hosted API evidence unless a real hosted URL is
provided and the HTTP checks pass.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

REPORT_DIR = ROOT / "reports" / "v078"
PUBLIC_REPORT = REPORT_DIR / "public_live_hosted_api_smoke_v078.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_live_hosted_api_smoke_v078.json"
HTTP_RESULTS_REPORT = REPORT_DIR / "live_hosted_api_http_results_v078.json"
ENV_READINESS_REPORT = REPORT_DIR / "hosted_env_readiness_v078.json"
SCORECARD = REPORT_DIR / "scorecard_v078.md"

BOUNDARY_V078 = (
    "V0.78 is live hosted API smoke testing only. Hosted API smoke evidence exists "
    "only when a real public or staging backend URL is supplied and passes checks. "
    "This is not production readiness, billing, external validation, bank approval, "
    "compliance approval, legal approval, external security certification, real "
    "client data use, or real-world validation."
)

REQUIRED_ROUTES = [
    "GET /health",
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "GET /v1/dashboard/state",
]

PUBLIC_FRONTEND_ORIGIN = "https://prmr-memory-core.vercel.app"
LOCAL_FRONTEND_ORIGIN = "http://localhost:3000"
RESULT_LEVELS = {
    "NEEDS_HOSTED_URL",
    "PASS_BASIC_HOSTED_SMOKE",
    "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
    "NEEDS_WORK",
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def normalize_url(value: str) -> str:
    return value.rstrip("/")


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 25,
) -> dict[str, Any]:
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = {"status": "non_json", "body_preview": text[:200]}
            return {
                "status_code": response.status,
                "headers": dict(response.headers.items()),
                "body": body,
                "ok": 200 <= response.status < 300,
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"status": "error", "error": {"code": "non_json_error", "message": text[:200]}, "public_safe": True}
        return {"status_code": exc.code, "headers": dict(exc.headers.items()), "body": body, "ok": False}
    except Exception as exc:
        return {
            "status_code": 0,
            "headers": {},
            "body": {"status": "error", "error": {"code": "request_failed", "message": str(exc)[:240]}, "public_safe": True},
            "ok": False,
        }


def request_options(base_url: str, path: str, origin: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url}{path}",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,x-client-id,x-vault-id,x-namespace,content-type",
        },
        method="OPTIONS",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return {"status_code": response.status, "headers": dict(response.headers.items()), "ok": 200 <= response.status < 300}
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code, "headers": dict(exc.headers.items()), "ok": False}
    except Exception as exc:
        return {"status_code": 0, "headers": {}, "error": str(exc)[:240], "ok": False}


def safe_body_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    return {
        "status": body.get("status"),
        "operation": body.get("operation"),
        "client_id": body.get("client_id"),
        "vault_id": body.get("vault_id"),
        "namespace": body.get("namespace"),
        "public_safe": body.get("public_safe"),
        "error_code": error.get("code"),
        "has_packet_id": bool(body.get("packet_id")),
        "has_report_id": bool(body.get("report_id")),
        "has_report": "report" in body,
        "has_usage": "usage" in body,
        "has_dashboard": "dashboard" in body,
    }


def safe_http_result(result: dict[str, Any]) -> dict[str, Any]:
    headers = result.get("headers", {})
    return {
        "status_code": result.get("status_code"),
        "ok": result.get("ok"),
        "body": safe_body_summary(result.get("body")),
        "cors": {
            "access_control_allow_origin": headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin"),
            "access_control_allow_methods": headers.get("access-control-allow-methods") or headers.get("Access-Control-Allow-Methods"),
        },
    }


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def env_readiness(hosted_url: str, test_scope_present: bool) -> dict[str, Any]:
    return {
        "version": "0.78",
        "public_safe": True,
        "boundary": BOUNDARY_V078,
        "hosted_url_present": bool(hosted_url),
        "test_scope_present": test_scope_present,
        "required_hosted_env": {
            "PRMR_API_MODE": "hosted_alpha",
            "PRMR_STORAGE_PATH": "<host-safe-path>",
            "PRMR_SYNTHETIC_ONLY": "true",
            "PRMR_PUBLIC_REPORTS_DIR": "<host-safe-public-report-dir>",
            "PRMR_PRIVATE_REPORTS_DIR": "<host-safe-private-report-dir>",
            "PRMR_ALLOWED_ORIGINS": f"{PUBLIC_FRONTEND_ORIGIN},{LOCAL_FRONTEND_ORIGIN}",
            "PRMR_DEFAULT_REQUEST_LIMIT": "100",
        },
        "live_smoke_env": [
            "PRMR_HOSTED_API_URL",
            "PRMR_TEST_API_KEY",
            "PRMR_TEST_CLIENT_ID",
            "PRMR_TEST_VAULT_ID",
            "PRMR_TEST_NAMESPACE",
        ],
        "cors": {
            "frontend_origin_required": PUBLIC_FRONTEND_ORIGIN,
            "localhost_origin_allowed_for_dev": LOCAL_FRONTEND_ORIGIN,
            "wildcard_cors_allowed": False,
        },
        "storage_note": "If the chosen host has an ephemeral filesystem, V0.78 uses ephemeral smoke storage only. Persistent hosted storage is V0.79/V0.80 work.",
    }


def build_public_report(checks: list[dict[str, Any]], result_level: str, hosted_url_present: bool, test_scope_present: bool) -> dict[str, Any]:
    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    return {
        "version": "0.78",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Live Hosted API Smoke",
        "result": result_level,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "blocking_failures": len(blocking_failures),
        "public_safe": True,
        "boundary": BOUNDARY_V078,
        "hosted_url_present": hosted_url_present,
        "test_scope_present": test_scope_present,
        "hosted_client_access_verified": result_level in {"PASS_BASIC_HOSTED_SMOKE", "PASS_FULL_CONTROLLED_HOSTED_SMOKE"},
        "full_controlled_hosted_smoke_verified": result_level == "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
        "protected_flow_status": "SKIPPED_NEEDS_TEST_SCOPE" if hosted_url_present and not test_scope_present else ("RUN" if test_scope_present else "NOT_RUN_NEEDS_HOSTED_URL"),
        "routes": REQUIRED_ROUTES,
        "cors": {
            "frontend_origin": PUBLIC_FRONTEND_ORIGIN,
            "localhost_origin": LOCAL_FRONTEND_ORIGIN,
            "wildcard_cors_enabled": False,
        },
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], safe_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Live Hosted API Smoke Restricted Evidence",
        "checks": checks,
        "safe_http_results": safe_results,
        "restricted_note": "HTTP result bodies are summarized. Raw API keys and secrets are not written.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.78 Live Hosted API Smoke",
        "",
        f"Result: {public_report['result']}",
        f"Hosted URL present: {public_report['hosted_url_present']}",
        f"Test scope present: {public_report['test_scope_present']}",
        f"Hosted client access verified: {public_report['hosted_client_access_verified']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V078}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        if check["skipped"]:
            status = "SKIP"
        else:
            status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_live_hosted_api_smoke_v078.py", "- RUN: python examples/audit_v078_live_hosted_api_smoke.py", ""])
    return "\n".join(lines)


def run_live_smoke() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    raw_url = os.getenv("PRMR_HOSTED_API_URL", "").strip()
    test_api_key = os.getenv("PRMR_TEST_API_KEY", "").strip()
    test_client_id = os.getenv("PRMR_TEST_CLIENT_ID", "").strip()
    test_vault_id = os.getenv("PRMR_TEST_VAULT_ID", "").strip()
    test_namespace = os.getenv("PRMR_TEST_NAMESPACE", "").strip()
    test_scope_present = all([test_api_key, test_client_id, test_vault_id, test_namespace])
    safe_results: dict[str, Any] = {}

    if not raw_url:
        add_check(checks, "hosted_url_required", False, "PRMR_HOSTED_API_URL is not set.", skipped=True)
        result_level = "NEEDS_HOSTED_URL"
        public_report = build_public_report(checks, result_level, False, test_scope_present)
        return public_report, safe_results, checks

    parsed = urllib.parse.urlparse(raw_url)
    hosted_url_valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    add_check(checks, "hosted_url_shape_valid", hosted_url_valid, raw_url)
    base_url = normalize_url(raw_url)
    if not hosted_url_valid:
        public_report = build_public_report(checks, "NEEDS_WORK", True, test_scope_present)
        return public_report, safe_results, checks

    health = request_json(base_url, "GET", "/health")
    safe_results["health"] = safe_http_result(health)
    health_body = health.get("body", {})
    add_check(checks, "health_route_passes", health["status_code"] == 200 and isinstance(health_body, dict) and health_body.get("status") == "ok", safe_results["health"])

    cors = request_options(base_url, "/v1/events/ingest", PUBLIC_FRONTEND_ORIGIN)
    safe_results["cors_preflight_frontend"] = safe_http_result({"status_code": cors.get("status_code"), "headers": cors.get("headers", {}), "body": {}, "ok": cors.get("ok")})
    allow_origin = safe_results["cors_preflight_frontend"]["cors"]["access_control_allow_origin"]
    add_check(checks, "frontend_origin_cors_allowed_or_health_documents_it", allow_origin in {PUBLIC_FRONTEND_ORIGIN, None} and (allow_origin == PUBLIC_FRONTEND_ORIGIN or PUBLIC_FRONTEND_ORIGIN in json.dumps(health_body)), safe_results["cors_preflight_frontend"])

    local_cors = request_options(base_url, "/v1/events/ingest", LOCAL_FRONTEND_ORIGIN)
    safe_results["cors_preflight_localhost"] = safe_http_result({"status_code": local_cors.get("status_code"), "headers": local_cors.get("headers", {}), "body": {}, "ok": local_cors.get("ok")})
    local_allow_origin = safe_results["cors_preflight_localhost"]["cors"]["access_control_allow_origin"]
    add_check(checks, "localhost_cors_allowed_or_documented", local_allow_origin in {LOCAL_FRONTEND_ORIGIN, None} and (local_allow_origin == LOCAL_FRONTEND_ORIGIN or LOCAL_FRONTEND_ORIGIN in json.dumps(health_body)), safe_results["cors_preflight_localhost"])
    add_check(checks, "wildcard_cors_not_enabled", "*" not in {allow_origin, local_allow_origin}, {"frontend": allow_origin, "localhost": local_allow_origin})

    missing_headers = {
        "X-Client-ID": "client_v078_missing_auth",
        "X-Vault-ID": "vault_v078_missing_auth",
        "X-Namespace": "default",
    }
    missing_auth = request_json(base_url, "POST", "/v1/events/ingest", headers=missing_headers, payload={"events": [{"event_id": "evt_v078_missing_auth"}]})
    safe_results["missing_auth"] = safe_http_result(missing_auth)
    add_check(checks, "missing_authorization_blocked", missing_auth["status_code"] in {401, 403}, safe_results["missing_auth"])

    malformed_headers = {**missing_headers, "Authorization": "Token malformed-test-token"}
    malformed_auth = request_json(base_url, "POST", "/v1/events/ingest", headers=malformed_headers, payload={"events": [{"event_id": "evt_v078_malformed_auth"}]})
    safe_results["malformed_auth"] = safe_http_result(malformed_auth)
    add_check(checks, "malformed_authorization_blocked", malformed_auth["status_code"] in {401, 403}, safe_results["malformed_auth"])

    add_check(checks, "controlled_test_scope_present", test_scope_present, "Protected valid-flow smoke needs PRMR_TEST_* vars.", skipped=not test_scope_present)
    if not test_scope_present:
        blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
        result_level = "PASS_BASIC_HOSTED_SMOKE" if not blocking_failures else "NEEDS_WORK"
        public_report = build_public_report(checks, result_level, True, False)
        return public_report, safe_results, checks

    test_headers = {
        "Authorization": f"Bearer {test_api_key}",
        "X-Client-ID": test_client_id,
        "X-Vault-ID": test_vault_id,
        "X-Namespace": test_namespace,
    }
    ingest = request_json(
        base_url,
        "POST",
        "/v1/events/ingest",
        headers=test_headers,
        payload={
            "events": [
                {
                    "event_id": "evt_v078_controlled_001",
                    "user_id": "synthetic_v078_user",
                    "type": "hosted_smoke_memory",
                    "content": "Synthetic V0.78 controlled hosted smoke event.",
                    "timestamp_index": 1,
                }
            ]
        },
    )
    safe_results["valid_ingest"] = safe_http_result(ingest)
    add_check(checks, "valid_ingest_passes", ingest["status_code"] == 200 and ingest.get("body", {}).get("status") == "ok", safe_results["valid_ingest"])

    packet = request_json(base_url, "POST", "/v1/continuity/packet", headers=test_headers, payload={})
    safe_results["valid_packet"] = safe_http_result(packet)
    packet_id = packet.get("body", {}).get("packet_id")
    report_id = packet.get("body", {}).get("report_id")
    add_check(checks, "valid_continuity_packet_passes", packet["status_code"] == 200 and bool(packet_id) and bool(report_id), safe_results["valid_packet"])

    reconstruct = request_json(base_url, "POST", "/v1/memory/reconstruct", headers=test_headers, payload={"packet_id": packet_id})
    safe_results["valid_reconstruct"] = safe_http_result(reconstruct)
    add_check(checks, "valid_reconstruct_passes", reconstruct["status_code"] == 200 and "reconstructable_state" in reconstruct.get("body", {}), safe_results["valid_reconstruct"])

    explain = request_json(base_url, "POST", "/v1/explain", headers=test_headers, payload={"packet_id": packet_id})
    safe_results["valid_explain"] = safe_http_result(explain)
    add_check(checks, "valid_explain_passes", explain["status_code"] == 200 and "explanation" in explain.get("body", {}), safe_results["valid_explain"])

    action = request_json(base_url, "POST", "/v1/actions/least-harm", headers=test_headers, payload={"packet_id": packet_id})
    safe_results["valid_least_harm"] = safe_http_result(action)
    add_check(checks, "valid_least_harm_passes", action["status_code"] == 200 and action.get("body", {}).get("not_final_decision") is True, safe_results["valid_least_harm"])

    report = request_json(base_url, "GET", f"/v1/reports/{report_id}", headers=test_headers)
    safe_results["valid_report"] = safe_http_result(report)
    add_check(checks, "valid_report_read_passes", report["status_code"] == 200 and "report" in report.get("body", {}), safe_results["valid_report"])

    usage = request_json(base_url, "GET", "/v1/usage", headers=test_headers)
    safe_results["valid_usage"] = safe_http_result(usage)
    add_check(checks, "valid_usage_read_passes", usage["status_code"] == 200 and "usage" in usage.get("body", {}), safe_results["valid_usage"])

    dashboard = request_json(base_url, "GET", "/v1/dashboard/state", headers=test_headers)
    safe_results["valid_dashboard"] = safe_http_result(dashboard)
    add_check(checks, "valid_dashboard_state_passes", dashboard["status_code"] == 200 and "dashboard" in dashboard.get("body", {}), safe_results["valid_dashboard"])

    wrong_key_headers = {**test_headers, "Authorization": "Bearer prmr_alpha_dev_wrong000000000000000000"}
    wrong_key = request_json(base_url, "POST", "/v1/events/ingest", headers=wrong_key_headers, payload={"events": [{"event_id": "evt_v078_wrong_key"}]})
    safe_results["wrong_key"] = safe_http_result(wrong_key)
    add_check(checks, "wrong_key_blocked", wrong_key["status_code"] in {401, 403}, safe_results["wrong_key"])

    wrong_vault_headers = {**test_headers, "X-Vault-ID": "vault_v078_wrong"}
    wrong_vault = request_json(base_url, "POST", "/v1/continuity/packet", headers=wrong_vault_headers, payload={})
    safe_results["wrong_vault"] = safe_http_result(wrong_vault)
    add_check(checks, "wrong_vault_blocked", wrong_vault["status_code"] in {401, 403, 404}, safe_results["wrong_vault"])

    wrong_namespace_headers = {**test_headers, "X-Namespace": "wrong_namespace"}
    wrong_namespace = request_json(base_url, "POST", "/v1/continuity/packet", headers=wrong_namespace_headers, payload={})
    safe_results["wrong_namespace"] = safe_http_result(wrong_namespace)
    add_check(checks, "wrong_namespace_blocked", wrong_namespace["status_code"] in {401, 403, 404}, safe_results["wrong_namespace"])

    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    result_level = "PASS_FULL_CONTROLLED_HOSTED_SMOKE" if not blocking_failures else "NEEDS_WORK"
    public_report = build_public_report(checks, result_level, True, True)
    return public_report, safe_results, checks


def write_reports(public_report: dict[str, Any], safe_results: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    hosted_url_present = bool(public_report.get("hosted_url_present"))
    test_scope_present = bool(public_report.get("test_scope_present"))
    env_report = env_readiness(os.getenv("PRMR_HOSTED_API_URL", "").strip(), test_scope_present)
    private_report = build_private_report(public_report, checks, safe_results)
    http_results_report = {
        "version": "0.78",
        "public_safe": True,
        "boundary": BOUNDARY_V078,
        "hosted_url_present": hosted_url_present,
        "test_scope_present": test_scope_present,
        "safe_http_results": safe_results,
    }

    public_bundle = {"public_report": public_report, "http_results": http_results_report, "env": env_report}
    if contains_full_dev_key(public_bundle) or scan_terms(public_bundle, ["raw_api_key", "full_api_key", "api_secret", "private_key", "secret"]):
        public_report["result"] = "NEEDS_WORK"
        public_report["public_hygiene_failure"] = True

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(HTTP_RESULTS_REPORT, http_results_report)
    write_json(ENV_READINESS_REPORT, env_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")


def main() -> int:
    public_report, safe_results, checks = run_live_smoke()
    write_reports(public_report, safe_results, checks)
    print("PRMR Memory Core V0.78 Live Hosted API Smoke")
    print(f"Hosted URL present: {public_report['hosted_url_present']}")
    print(f"Test scope present: {public_report['test_scope_present']}")
    print(f"Smoke result level: {public_report['result']}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"HTTP results: {HTTP_RESULTS_REPORT.as_posix()}")
    print(f"Env readiness: {ENV_READINESS_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] in RESULT_LEVELS else 1


if __name__ == "__main__":
    raise SystemExit(main())
