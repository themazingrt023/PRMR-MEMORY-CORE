"""V0.78.3 hosted basic smoke evidence lock.

This audit locks clean evidence for a deployed backend URL's basic hosted smoke:
health and protected-route auth denial. It does not prove the full protected
hosted API flow unless controlled test credentials are supplied and a separate
full-flow smoke passes.
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
REPORT_DIR = ROOT / "reports" / "v0783"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_basic_smoke_evidence_v0783.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_basic_smoke_evidence_v0783.json"
HTTP_RESULTS_REPORT = REPORT_DIR / "hosted_basic_http_results_v0783.json"
SCORECARD = REPORT_DIR / "scorecard_v0783.md"

EXPECTED_RENDER_URL = "https://prmr-memory-core-api.onrender.com"
PUBLIC_FRONTEND_URL = "https://prmr-memory-core.vercel.app"
RESULT_LEVELS = {
    "NEEDS_HOSTED_URL",
    "PASS_BASIC_HOSTED_SMOKE",
    "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
    "NEEDS_WORK",
}

BOUNDARY_V0783 = (
    "V0.78.3 is hosted basic smoke evidence only. It proves the deployed backend "
    "responds to basic hosted health and auth-denial checks. It does not prove "
    "the full protected hosted API flow because controlled hosted test credentials "
    "are not supplied here. It is not production readiness, billing, external "
    "validation, bank approval, compliance approval, legal approval, external "
    "security certification, or real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def request_json(base_url: str, method: str, path: str, *, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            text = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = {"status": "non_json", "body_preview": text[:120]}
            return {"status_code": response.status, "headers": dict(response.headers.items()), "body": body, "ok": 200 <= response.status < 300}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"status": "error", "error": {"code": "non_json_error", "message": text[:120]}, "public_safe": True}
        return {"status_code": exc.code, "headers": dict(exc.headers.items()), "body": body, "ok": False}
    except Exception as exc:
        return {
            "status_code": 0,
            "headers": {},
            "body": {"status": "error", "error": {"code": "request_failed", "message": str(exc)[:160]}, "public_safe": True},
            "ok": False,
        }


def safe_body_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    cors = body.get("cors") if isinstance(body.get("cors"), dict) else {}
    return {
        "status": body.get("status"),
        "operation": body.get("operation"),
        "api_mode": body.get("api_mode"),
        "synthetic_only": body.get("synthetic_only"),
        "server_framework": body.get("server_framework"),
        "public_safe": body.get("public_safe"),
        "error_code": error.get("code"),
        "error_message_present": bool(error.get("message")),
        "cors_allowed_origins": cors.get("allowed_origins"),
        "wildcard_origin": cors.get("wildcard_origin"),
    }


def safe_http_result(result: dict[str, Any]) -> dict[str, Any]:
    headers = result.get("headers", {})
    return {
        "status_code": result.get("status_code"),
        "ok": result.get("ok"),
        "body": safe_body_summary(result.get("body")),
        "headers": {
            "content_type": headers.get("content-type") or headers.get("Content-Type"),
            "server": headers.get("server") or headers.get("Server"),
        },
    }


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def positive_overclaim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
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
        "full hosted client access verified",
    ]
    return [phrase for phrase in phrases if phrase in text]


def test_scope_status() -> tuple[bool, str]:
    present = all(
        os.getenv(name, "").strip()
        for name in ["PRMR_TEST_API_KEY", "PRMR_TEST_CLIENT_ID", "PRMR_TEST_VAULT_ID", "PRMR_TEST_NAMESPACE"]
    )
    return present, "TEST_SCOPE_PRESENT_NOT_USED_BY_BASIC_LOCK" if present else "SKIPPED_NEEDS_TEST_SCOPE"


def build_public_report(checks: list[dict[str, Any]], result: str, hosted_url: str, safe_results: dict[str, Any], scope_status: str) -> dict[str, Any]:
    return {
        "version": "0.78.3",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Basic Smoke Evidence Lock",
        "result": result,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V0783,
        "hosted_url_present": bool(hosted_url),
        "hosted_url": hosted_url or None,
        "expected_render_url": EXPECTED_RENDER_URL,
        "health_status_code": safe_results.get("health", {}).get("status_code"),
        "root_status_code": safe_results.get("root", {}).get("status_code"),
        "root_404_acceptable": safe_results.get("root", {}).get("status_code") == 404,
        "missing_auth_status_code": safe_results.get("missing_auth", {}).get("status_code"),
        "malformed_auth_status_code": safe_results.get("malformed_auth", {}).get("status_code"),
        "protected_valid_flow_status": scope_status,
        "hosted_basic_smoke_verified": result == "PASS_BASIC_HOSTED_SMOKE",
        "full_controlled_hosted_smoke_verified": result == "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
        "full_hosted_client_access_claimed": False,
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], safe_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "safe_http_results": safe_results,
        "restricted_note": "Only summarized HTTP response metadata is stored. No API keys or secrets are written.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.78.3 Hosted Basic Smoke Evidence",
        "",
        f"Result: {public_report['result']}",
        f"Hosted URL: {public_report['hosted_url']}",
        f"Health status: {public_report['health_status_code']}",
        f"Missing auth status: {public_report['missing_auth_status_code']}",
        f"Malformed auth status: {public_report['malformed_auth_status_code']}",
        f"Protected valid flow: {public_report['protected_valid_flow_status']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V0783}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "SKIP" if check["skipped"] else ("PASS" if check["passed"] else "FAIL")
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/audit_v0783_hosted_basic_smoke_evidence.py", ""])
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    safe_results: dict[str, Any] = {}
    hosted_url = normalize_url(os.getenv("PRMR_HOSTED_API_URL", ""))
    scope_present, scope_status = test_scope_status()

    if not hosted_url:
        add_check(checks, "hosted_url_present", False, "Set PRMR_HOSTED_API_URL.", skipped=True)
        public_report = build_public_report(checks, "NEEDS_HOSTED_URL", hosted_url, safe_results, "NOT_RUN_NEEDS_HOSTED_URL")
        return public_report, safe_results, checks

    parsed = urllib.parse.urlparse(hosted_url)
    add_check(checks, "hosted_url_present", True, hosted_url)
    add_check(checks, "hosted_url_shape_valid", parsed.scheme in {"http", "https"} and bool(parsed.netloc), hosted_url)
    add_check(checks, "hosted_url_matches_expected_render_url", hosted_url == EXPECTED_RENDER_URL, hosted_url)

    root = request_json(hosted_url, "GET", "/")
    safe_results["root"] = safe_http_result(root)
    add_check(checks, "root_404_is_acceptable", root["status_code"] == 404, safe_results["root"])

    health = request_json(hosted_url, "GET", "/health")
    safe_results["health"] = safe_http_result(health)
    health_body = health.get("body", {})
    add_check(checks, "health_route_returns_success", health["status_code"] == 200 and isinstance(health_body, dict) and health_body.get("status") == "ok", safe_results["health"])
    add_check(checks, "health_confirms_public_safe", health_body.get("public_safe") is True, safe_results["health"])
    add_check(checks, "health_lists_frontend_origin", PUBLIC_FRONTEND_URL in json.dumps(health_body), safe_results["health"])
    add_check(checks, "health_has_no_wildcard_cors", health_body.get("cors", {}).get("wildcard_origin") is False, safe_results["health"])

    protected_headers = {
        "X-Client-ID": "client_v0783_basic_smoke",
        "X-Vault-ID": "vault_v0783_basic_smoke",
        "X-Namespace": "default",
    }
    payload = {"events": [{"event_id": "evt_v0783_basic_smoke"}]}

    missing_auth = request_json(hosted_url, "POST", "/v1/events/ingest", headers=protected_headers, payload=payload)
    safe_results["missing_auth"] = safe_http_result(missing_auth)
    add_check(checks, "missing_authorization_blocked", missing_auth["status_code"] in {401, 403}, safe_results["missing_auth"])
    add_check(checks, "missing_authorization_public_safe", missing_auth.get("body", {}).get("public_safe") is True, safe_results["missing_auth"])

    malformed_headers = {**protected_headers, "Authorization": "Token malformed-v0783-smoke"}
    malformed_auth = request_json(hosted_url, "POST", "/v1/events/ingest", headers=malformed_headers, payload=payload)
    safe_results["malformed_auth"] = safe_http_result(malformed_auth)
    add_check(checks, "malformed_authorization_blocked", malformed_auth["status_code"] in {401, 403}, safe_results["malformed_auth"])
    add_check(checks, "malformed_authorization_public_safe", malformed_auth.get("body", {}).get("public_safe") is True, safe_results["malformed_auth"])

    add_check(checks, "protected_valid_flow_skipped_without_test_scope", not scope_present and scope_status == "SKIPPED_NEEDS_TEST_SCOPE", scope_status, skipped=scope_present)
    add_check(checks, "no_full_hosted_client_access_claim", True, "Only hosted basic smoke is claimed.")

    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    result = "PASS_BASIC_HOSTED_SMOKE" if not blocking_failures else "NEEDS_WORK"
    public_report = build_public_report(checks, result, hosted_url, safe_results, scope_status)

    public_bundle = {"public_report": public_report, "safe_results": safe_results}
    add_check(checks, "public_outputs_contain_no_secrets", not contains_secret_pattern(public_bundle), None)
    add_check(checks, "no_production_billing_certification_claims", not positive_overclaim_hits(public_bundle), positive_overclaim_hits(public_bundle))

    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    result = "PASS_BASIC_HOSTED_SMOKE" if not blocking_failures else "NEEDS_WORK"
    public_report = build_public_report(checks, result, hosted_url, safe_results, scope_status)
    return public_report, safe_results, checks


def main() -> int:
    public_report, safe_results, checks = run_audit()
    private_report = build_private_report(public_report, checks, safe_results)
    http_results = {
        "version": "0.78.3",
        "public_safe": True,
        "boundary": BOUNDARY_V0783,
        "hosted_url": public_report.get("hosted_url"),
        "result": public_report.get("result"),
        "safe_http_results": safe_results,
    }

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(HTTP_RESULTS_REPORT, http_results)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.78.3 Hosted Basic Smoke Evidence")
    print(f"Hosted URL: {public_report.get('hosted_url')}")
    print(f"Health status: {public_report.get('health_status_code')}")
    print(f"Root status: {public_report.get('root_status_code')} (404 acceptable: {public_report.get('root_404_acceptable')})")
    print(f"Missing auth status: {public_report.get('missing_auth_status_code')}")
    print(f"Malformed auth status: {public_report.get('malformed_auth_status_code')}")
    print(f"Protected valid-flow status: {public_report.get('protected_valid_flow_status')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"HTTP results: {HTTP_RESULTS_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") in RESULT_LEVELS and public_report.get("result") != "NEEDS_WORK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
