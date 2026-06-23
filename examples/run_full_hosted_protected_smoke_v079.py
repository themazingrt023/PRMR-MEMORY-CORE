"""V0.79 full controlled hosted protected-route smoke runner.

This runner exercises the deployed FastAPI backend with synthetic test-scope
credentials supplied through environment variables. It never writes raw keys to
reports. If the hosted URL or controlled test scope is missing, it reports that
honestly instead of forcing a pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v079"
PUBLIC_REPORT = REPORT_DIR / "public_controlled_hosted_test_scope_v079.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_controlled_hosted_test_scope_v079.json"
FULL_SMOKE_REPORT = REPORT_DIR / "full_hosted_protected_smoke_v079.json"
SCORECARD = REPORT_DIR / "scorecard_v079.md"

EXPECTED_RENDER_URL = "https://prmr-memory-core-api.onrender.com"
RESULT_LEVELS = {
    "NEEDS_HOSTED_URL",
    "NEEDS_TEST_SCOPE",
    "NEEDS_TEST_SCOPE_CONFIG",
    "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
    "NEEDS_WORK",
}

BOUNDARY_V079 = (
    "V0.79 is controlled synthetic hosted test-scope smoke evidence only. It "
    "does not prove real client onboarding, production readiness, billing, "
    "external validation, bank approval, compliance approval, legal approval, "
    "external security certification, or real-world validation."
)

TEST_SCOPE_ENV_NAMES = [
    "PRMR_TEST_API_KEY",
    "PRMR_TEST_CLIENT_ID",
    "PRMR_TEST_VAULT_ID",
    "PRMR_TEST_NAMESPACE",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def normalize_url(value: str) -> str:
    return value.strip().rstrip("/")


def safe_key_preview(raw_key: str | None) -> str | None:
    if not raw_key:
        return None
    return f"controlled_test_key_...{raw_key[-4:] if len(raw_key) >= 4 else 'short'}"


def key_hash_prefix(raw_key: str | None) -> str | None:
    if not raw_key:
        return None
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]


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
        "real client onboarding verified",
    ]
    return [phrase for phrase in phrases if phrase in text]


def test_scope_from_env() -> dict[str, Any]:
    values = {name: os.getenv(name, "").strip() for name in TEST_SCOPE_ENV_NAMES}
    missing = [name for name, value in values.items() if not value]
    raw_key = values["PRMR_TEST_API_KEY"]
    return {
        "values": values,
        "missing": missing,
        "present": not missing,
        "safe_key_preview": safe_key_preview(raw_key),
        "key_hash_prefix": key_hash_prefix(raw_key),
        "enable_flag": os.getenv("PRMR_ENABLE_CONTROLLED_TEST_SCOPE", "").strip().lower(),
    }


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            text = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = {"status": "non_json", "body_preview": text[:160]}
            return {"status_code": response.status, "body": body, "ok": 200 <= response.status < 300}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"status": "error", "error": {"code": "non_json_error", "message": text[:160]}, "public_safe": True}
        return {"status_code": exc.code, "body": body, "ok": False}
    except Exception as exc:
        return {
            "status_code": 0,
            "body": {"status": "error", "error": {"code": "request_failed", "message": str(exc)[:180]}, "public_safe": True},
            "ok": False,
        }


def safe_body_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    report = body.get("report") if isinstance(body.get("report"), dict) else {}
    dashboard = body.get("dashboard") if isinstance(body.get("dashboard"), dict) else {}
    return {
        "status": body.get("status"),
        "operation": body.get("operation"),
        "public_safe": body.get("public_safe"),
        "client_id": body.get("client_id"),
        "vault_id": body.get("vault_id"),
        "namespace": body.get("namespace"),
        "error_code": error.get("code"),
        "accepted_event_count": body.get("accepted_event_count"),
        "packet_id_present": bool(body.get("packet_id")),
        "report_id_present": bool(body.get("report_id")),
        "reconstructable_state_present": bool(body.get("reconstructable_state")),
        "explanation_present": bool(body.get("explanation")),
        "recommended_action": body.get("recommended_action"),
        "report_public_safe": report.get("public_safe"),
        "usage_present": bool(body.get("usage")),
        "dashboard_present": bool(dashboard),
    }


def safe_http_result(result: dict[str, Any]) -> dict[str, Any]:
    return {"status_code": result.get("status_code"), "ok": result.get("ok"), "body": safe_body_summary(result.get("body"))}


def auth_headers(scope: dict[str, str], api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Client-ID": scope["PRMR_TEST_CLIENT_ID"],
        "X-Vault-ID": scope["PRMR_TEST_VAULT_ID"],
        "X-Namespace": scope["PRMR_TEST_NAMESPACE"],
    }


def build_public_report(
    *,
    result: str,
    hosted_url: str,
    checks: list[dict[str, Any]],
    safe_results: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "0.79",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Controlled Hosted Test Scope Full Protected Smoke",
        "result": result,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V079,
        "hosted_url_present": bool(hosted_url),
        "hosted_url": hosted_url or None,
        "expected_render_url": EXPECTED_RENDER_URL,
        "test_scope_present": scope.get("present", False),
        "test_scope_missing_env": scope.get("missing", []),
        "safe_key_preview": scope.get("safe_key_preview"),
        "key_hash_prefix_present": bool(scope.get("key_hash_prefix")),
        "raw_key_hardcoded": False,
        "raw_key_reported": False,
        "full_controlled_hosted_smoke_verified": result == "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
        "real_client_onboarding_claimed": False,
        "safe_http_summary": safe_results,
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], safe_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "safe_http_results": safe_results,
        "restricted_note": "No raw API keys are stored here. Only safe response summaries and key preview/hash-prefix status are retained.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.79 Controlled Hosted Test Scope",
        "",
        f"Result: {public_report['result']}",
        f"Hosted URL: {public_report['hosted_url']}",
        f"Test scope present: {public_report['test_scope_present']}",
        f"Full controlled hosted smoke verified: {public_report['full_controlled_hosted_smoke_verified']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V079}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "SKIP" if check["skipped"] else ("PASS" if check["passed"] else "FAIL")
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Command Results",
            "",
            "- RUN: python examples/run_full_hosted_protected_smoke_v079.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    safe_results: dict[str, Any] = {}
    hosted_url = normalize_url(os.getenv("PRMR_HOSTED_API_URL", ""))
    scope = test_scope_from_env()

    if not hosted_url:
        add_check(checks, "hosted_url_present", False, "Set PRMR_HOSTED_API_URL.", skipped=True)
        public_report = build_public_report(result="NEEDS_HOSTED_URL", hosted_url=hosted_url, checks=checks, safe_results=safe_results, scope=scope)
        return public_report, safe_results, checks

    parsed = urllib.parse.urlparse(hosted_url)
    add_check(checks, "hosted_url_present", True, hosted_url)
    add_check(checks, "hosted_url_shape_valid", parsed.scheme in {"http", "https"} and bool(parsed.netloc), hosted_url)
    add_check(checks, "hosted_url_matches_expected_render_url", hosted_url == EXPECTED_RENDER_URL, hosted_url)

    if not scope["present"]:
        result = "NEEDS_TEST_SCOPE_CONFIG" if scope["enable_flag"] == "true" else "NEEDS_TEST_SCOPE"
        add_check(checks, "controlled_test_scope_present", False, {"missing_env": scope["missing"]}, skipped=True)
        public_report = build_public_report(result=result, hosted_url=hosted_url, checks=checks, safe_results=safe_results, scope=scope)
        return public_report, safe_results, checks

    scope_values = scope["values"]
    raw_key = scope_values["PRMR_TEST_API_KEY"]
    headers = auth_headers(scope_values, raw_key)
    run_id = uuid4().hex[:10]

    health = request_json(hosted_url, "GET", "/health")
    safe_results["health"] = safe_http_result(health)
    health_scope = health.get("body", {}).get("controlled_test_scope_v079", {}) if isinstance(health.get("body"), dict) else {}
    add_check(checks, "health_route_success", health["status_code"] == 200 and health.get("body", {}).get("status") == "ok", safe_results["health"])
    add_check(checks, "controlled_test_scope_registered_on_host", health_scope.get("status") == "REGISTERED", health_scope.get("status"))

    events_payload = {
        "events": [
            {
                "event_id": f"evt_v079_{run_id}_001",
                "user_id": "synthetic_hosted_scope_user",
                "type": "hosted_continuity_state",
                "content": "Synthetic hosted test scope event one established an initial continuity state.",
                "timestamp": "2026-06-23T12:01:00Z",
                "timestamp_index": 1,
            },
            {
                "event_id": f"evt_v079_{run_id}_002",
                "user_id": "synthetic_hosted_scope_user",
                "type": "hosted_continuity_update",
                "content": "Synthetic hosted test scope event two updated the current state for reconstruction.",
                "timestamp": "2026-06-23T12:02:00Z",
                "timestamp_index": 2,
            },
        ]
    }
    ingest = request_json(hosted_url, "POST", "/v1/events/ingest", headers=headers, payload=events_payload)
    safe_results["events_ingest"] = safe_http_result(ingest)
    add_check(checks, "events_ingest_valid_key_accepted", ingest["status_code"] == 200 and ingest.get("body", {}).get("accepted_event_count") == 2, safe_results["events_ingest"])

    packet = request_json(hosted_url, "POST", "/v1/continuity/packet", headers=headers, payload={})
    safe_results["continuity_packet"] = safe_http_result(packet)
    packet_id = packet.get("body", {}).get("packet_id")
    report_id = packet.get("body", {}).get("report_id")
    add_check(checks, "continuity_packet_created", packet["status_code"] == 200 and bool(packet_id) and bool(report_id), safe_results["continuity_packet"])

    reconstruct = request_json(hosted_url, "POST", "/v1/memory/reconstruct", headers=headers, payload={"packet_id": packet_id})
    safe_results["memory_reconstruct"] = safe_http_result(reconstruct)
    add_check(checks, "memory_reconstruct_returns_state", reconstruct["status_code"] == 200 and bool(reconstruct.get("body", {}).get("reconstructable_state")), safe_results["memory_reconstruct"])

    explain = request_json(hosted_url, "POST", "/v1/explain", headers=headers, payload={"packet_id": packet_id})
    safe_results["explain"] = safe_http_result(explain)
    add_check(checks, "explain_returns_public_safe_packet", explain["status_code"] == 200 and bool(explain.get("body", {}).get("explanation")), safe_results["explain"])

    action = request_json(hosted_url, "POST", "/v1/actions/least-harm", headers=headers, payload={"packet_id": packet_id})
    safe_results["least_harm_action"] = safe_http_result(action)
    add_check(checks, "least_harm_action_returns_non_final_action", action["status_code"] == 200 and action.get("body", {}).get("not_final_decision") is True, safe_results["least_harm_action"])

    report = request_json(hosted_url, "GET", f"/v1/reports/{report_id}", headers=headers)
    safe_results["get_report"] = safe_http_result(report)
    add_check(checks, "owner_can_fetch_public_report", report["status_code"] == 200 and report.get("body", {}).get("report", {}).get("public_safe") is True, safe_results["get_report"])

    usage = request_json(hosted_url, "GET", "/v1/usage", headers=headers)
    safe_results["get_usage"] = safe_http_result(usage)
    add_check(checks, "usage_route_returns_usage", usage["status_code"] == 200 and bool(usage.get("body", {}).get("usage")), safe_results["get_usage"])

    dashboard = request_json(hosted_url, "GET", "/v1/dashboard/state", headers=headers)
    safe_results["get_dashboard_state"] = safe_http_result(dashboard)
    add_check(checks, "dashboard_state_route_returns_state", dashboard["status_code"] == 200 and bool(dashboard.get("body", {}).get("dashboard")), safe_results["get_dashboard_state"])

    wrong_key_headers = auth_headers(scope_values, f"wrong_v079_{uuid4().hex}")
    wrong_key = request_json(hosted_url, "POST", "/v1/events/ingest", headers=wrong_key_headers, payload=events_payload)
    safe_results["wrong_key_blocked"] = safe_http_result(wrong_key)
    add_check(checks, "wrong_key_blocked", wrong_key["status_code"] in {401, 403}, safe_results["wrong_key_blocked"])

    wrong_vault_headers = {**headers, "X-Vault-ID": f"vault_v079_wrong_{run_id}"}
    wrong_vault = request_json(hosted_url, "POST", "/v1/events/ingest", headers=wrong_vault_headers, payload=events_payload)
    safe_results["wrong_vault_blocked"] = safe_http_result(wrong_vault)
    add_check(checks, "wrong_vault_blocked", wrong_vault["status_code"] in {401, 403, 404}, safe_results["wrong_vault_blocked"])

    wrong_namespace_headers = {**headers, "X-Namespace": f"namespace_v079_wrong_{run_id}"}
    wrong_namespace = request_json(hosted_url, "POST", "/v1/events/ingest", headers=wrong_namespace_headers, payload=events_payload)
    safe_results["wrong_namespace_blocked"] = safe_http_result(wrong_namespace)
    add_check(checks, "wrong_namespace_blocked", wrong_namespace["status_code"] in {401, 403, 404}, safe_results["wrong_namespace_blocked"])

    missing_headers = {
        "X-Client-ID": scope_values["PRMR_TEST_CLIENT_ID"],
        "X-Vault-ID": scope_values["PRMR_TEST_VAULT_ID"],
        "X-Namespace": scope_values["PRMR_TEST_NAMESPACE"],
    }
    missing_auth = request_json(hosted_url, "POST", "/v1/events/ingest", headers=missing_headers, payload=events_payload)
    safe_results["missing_authorization_blocked"] = safe_http_result(missing_auth)
    add_check(checks, "missing_authorization_blocked", missing_auth["status_code"] in {401, 403}, safe_results["missing_authorization_blocked"])

    malformed_auth = request_json(hosted_url, "POST", "/v1/events/ingest", headers={**missing_headers, "Authorization": "Token malformed-v079-smoke"}, payload=events_payload)
    safe_results["malformed_authorization_blocked"] = safe_http_result(malformed_auth)
    add_check(checks, "malformed_authorization_blocked", malformed_auth["status_code"] in {401, 403}, safe_results["malformed_authorization_blocked"])

    public_bundle = {"safe_results": safe_results, "scope": {key: value for key, value in scope.items() if key != "values"}}
    add_check(checks, "public_outputs_contain_no_secrets", not contains_secret_pattern(public_bundle), None)
    add_check(checks, "no_production_billing_certification_claims", not positive_overclaim_hits(public_bundle), positive_overclaim_hits(public_bundle))

    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    result = "PASS_FULL_CONTROLLED_HOSTED_SMOKE" if not blocking_failures else "NEEDS_WORK"
    public_report = build_public_report(result=result, hosted_url=hosted_url, checks=checks, safe_results=safe_results, scope=scope)
    return public_report, safe_results, checks


def write_reports(public_report: dict[str, Any], safe_results: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    private_report = build_private_report(public_report, checks, safe_results)
    smoke_report = {
        "version": "0.79",
        "public_safe": True,
        "boundary": BOUNDARY_V079,
        "result": public_report["result"],
        "hosted_url": public_report.get("hosted_url"),
        "safe_http_results": safe_results,
    }
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(FULL_SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")


def main() -> int:
    public_report, safe_results, checks = run_smoke()
    write_reports(public_report, safe_results, checks)
    print("PRMR Memory Core V0.79 Full Hosted Protected Smoke")
    print(f"Hosted URL: {public_report.get('hosted_url')}")
    print(f"Test scope present: {public_report.get('test_scope_present')}")
    print(f"Safe key preview: {public_report.get('safe_key_preview')}")
    print(f"Full protected smoke verified: {public_report.get('full_controlled_hosted_smoke_verified')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Full smoke report: {FULL_SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") in RESULT_LEVELS and public_report.get("result") != "NEEDS_WORK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
