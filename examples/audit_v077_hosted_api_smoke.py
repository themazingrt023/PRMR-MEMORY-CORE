"""Hosted API smoke harness for PRMR Memory Core V0.77.

If PRMR_HOSTED_API_URL is not set, this script reports readiness without
pretending a hosted backend was verified.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v077"
HOSTED_SMOKE_REPORT = REPORT_DIR / "hosted_api_smoke_v077.json"

BOUNDARY_V077 = (
    "V0.77 is hosted API deployment prep plus a hosted smoke harness. Hosted "
    "client access is only claimable after a real deployed backend URL passes "
    "smoke tests. This is not production readiness, billing, external validation, "
    "bank approval, compliance approval, legal approval, external security "
    "certification, or real-world validation."
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def normalize_url(value: str) -> str:
    return value.rstrip("/")


def request_json(base_url: str, method: str, path: str, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
            return {"status_code": response.status, "body": json.loads(text), "ok": 200 <= response.status < 300}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"status": "error", "error": {"code": "non_json_error", "message": text[:200]}, "public_safe": True}
        return {"status_code": exc.code, "body": body, "ok": False}
    except Exception as exc:
        return {"status_code": 0, "body": {"status": "error", "error": {"code": "request_failed", "message": str(exc)[:200]}, "public_safe": True}, "ok": False}


def safe_result(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {})
    error = body.get("error") if isinstance(body, dict) else None
    return {
        "status_code": result.get("status_code"),
        "status": body.get("status") if isinstance(body, dict) else None,
        "operation": body.get("operation") if isinstance(body, dict) else None,
        "error_code": error.get("code") if isinstance(error, dict) else None,
        "public_safe": body.get("public_safe") if isinstance(body, dict) else None,
    }


def hosted_smoke() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hosted_url_raw = os.getenv("PRMR_HOSTED_API_URL", "").strip()
    if not hosted_url_raw:
        add_check(checks, "hosted_url_not_set_readiness_mode", True, "PRMR_HOSTED_API_URL is not set; no live hosted smoke was attempted.")
        payload = {
            "version": "0.77",
            "title": "Hosted API Smoke Harness",
            "result": "PASS_READINESS_NEEDS_HOSTED_URL",
            "public_safe": True,
            "boundary": BOUNDARY_V077,
            "hosted_url_present": False,
            "hosted_client_access_verified": False,
            "required_routes": REQUIRED_ROUTES,
            "checks": checks,
            "next_step": "Set PRMR_HOSTED_API_URL to a deployed backend URL and rerun this smoke harness.",
        }
        write_json(HOSTED_SMOKE_REPORT, payload)
        return payload

    parsed = urllib.parse.urlparse(hosted_url_raw)
    hosted_url_valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    add_check(checks, "hosted_url_shape_valid", hosted_url_valid, hosted_url_raw)
    base_url = normalize_url(hosted_url_raw)
    results: dict[str, Any] = {}

    if hosted_url_valid:
        results["health"] = request_json(base_url, "GET", "/health")
        health_body = results["health"].get("body", {})
        add_check(checks, "public_health_smoke", results["health"]["status_code"] == 200 and health_body.get("status") == "ok", safe_result(results["health"]))

        base_headers = {
            "X-Client-ID": "client_v077_smoke_missing_auth",
            "X-Vault-ID": "vault_v077_smoke",
            "X-Namespace": "default",
        }
        results["missing_auth"] = request_json(base_url, "POST", "/v1/events/ingest", headers=base_headers, payload={"events": [{"event_id": "evt_v077_missing_auth"}]})
        add_check(checks, "blocked_missing_auth_smoke", results["missing_auth"]["status_code"] in {401, 403}, safe_result(results["missing_auth"]))

        malformed_headers = {**base_headers, "Authorization": "Token not-a-bearer-token"}
        results["malformed_auth"] = request_json(base_url, "POST", "/v1/events/ingest", headers=malformed_headers, payload={"events": [{"event_id": "evt_v077_malformed_auth"}]})
        add_check(checks, "blocked_malformed_auth_smoke", results["malformed_auth"]["status_code"] in {401, 403}, safe_result(results["malformed_auth"]))

        api_key = os.getenv("PRMR_HOSTED_API_KEY", "").strip()
        client_id = os.getenv("PRMR_HOSTED_CLIENT_ID", "").strip()
        vault_id = os.getenv("PRMR_HOSTED_VAULT_ID", "").strip()
        namespace = os.getenv("PRMR_HOSTED_NAMESPACE", "").strip()
        protected_creds_present = all([api_key, client_id, vault_id, namespace])
        add_check(checks, "protected_route_credentials_supplied", protected_creds_present, "Optional hosted protected-route variables supplied.", skipped=not protected_creds_present)
        if protected_creds_present:
            protected_headers = {
                "Authorization": f"Bearer {api_key}",
                "X-Client-ID": client_id,
                "X-Vault-ID": vault_id,
                "X-Namespace": namespace,
            }
            results["protected_ingest"] = request_json(
                base_url,
                "POST",
                "/v1/events/ingest",
                headers=protected_headers,
                payload={"events": [{"event_id": "evt_v077_hosted_protected", "content": "Synthetic hosted smoke event.", "timestamp_index": 1}]},
            )
            add_check(checks, "protected_route_valid_ingest_smoke", results["protected_ingest"]["status_code"] == 200, safe_result(results["protected_ingest"]))

    blocking_failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    result = "PASS_HOSTED_HEALTH_AND_AUTH_BOUNDARY" if not blocking_failures else "NEEDS_WORK"
    protected_verified = any(check["name"] == "protected_route_valid_ingest_smoke" and check["passed"] for check in checks)
    payload = {
        "version": "0.77",
        "title": "Hosted API Smoke Harness",
        "result": result,
        "public_safe": True,
        "boundary": BOUNDARY_V077,
        "hosted_url_present": True,
        "hosted_url": base_url,
        "hosted_client_access_verified": protected_verified,
        "public_health_smoke_ran": "health" in results,
        "blocked_auth_smoke_ran": "missing_auth" in results and "malformed_auth" in results,
        "protected_route_smoke_ran": protected_verified,
        "required_routes": REQUIRED_ROUTES,
        "checks": checks,
        "safe_http_results": {name: safe_result(result) for name, result in results.items()},
    }
    write_json(HOSTED_SMOKE_REPORT, payload)
    return payload


def main() -> int:
    payload = hosted_smoke()
    print("PRMR Memory Core V0.77 Hosted API Smoke")
    print(f"Hosted URL present: {payload['hosted_url_present']}")
    print(f"Hosted client access verified: {payload['hosted_client_access_verified']}")
    print(f"Report: {HOSTED_SMOKE_REPORT.as_posix()}")
    print(f"Result: {payload['result']}")
    return 0 if payload["result"] in {"PASS_READINESS_NEEDS_HOSTED_URL", "PASS_HOSTED_HEALTH_AND_AUTH_BOUNDARY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
