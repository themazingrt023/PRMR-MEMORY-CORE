"""Run V0.76 real local HTTP API server smoke proof."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

os.environ["PRMR_API_MODE"] = "local_alpha"
os.environ["PRMR_STORAGE_PATH"] = str(ROOT / "reports" / "v076" / "prmr_api_server_v076.sqlite")
os.environ["PRMR_SYNTHETIC_ONLY"] = "true"
os.environ["PRMR_PUBLIC_REPORTS_DIR"] = str(ROOT / "reports" / "v076")
os.environ["PRMR_PRIVATE_REPORTS_DIR"] = str(ROOT / "reports" / "v076")
os.environ["PRMR_ALLOWED_ORIGINS"] = "http://localhost:3000"

from prmr.product.api_config_v075 import load_api_config  # noqa: E402
from prmr.product.api_server_v076 import (  # noqa: E402
    BOUNDARY_V076,
    OVERCLAIMS_V076,
    PUBLIC_FORBIDDEN_TERMS_V076,
    REPORT_DIR,
    ROUTES,
    SERVER_FRAMEWORK,
    add_check,
    build_private_report,
    build_public_report,
    build_scorecard,
    create_app,
    public_hygiene_failures,
    safe_route_results_for_public,
)
from prmr.product.hosted_api_wrapper_v075 import PRMRHostedAPIWrapper, contains_full_dev_key, sample_event, scan_terms  # noqa: E402
from prmr.product.persistent_storage_v074 import write_json  # noqa: E402
from prmr.product.hosted_backend_foundation_v069 import utc_now  # noqa: E402


PUBLIC_REPORT = REPORT_DIR / "public_api_server_v076.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_server_v076.json"
HTTP_SMOKE_REPORT = REPORT_DIR / "api_server_http_smoke_v076.json"
REQUEST_LOG = REPORT_DIR / "api_server_request_log_v076.json"
STORAGE_STATE = REPORT_DIR / "api_server_storage_state_v076.json"
SCORECARD = REPORT_DIR / "scorecard_v076.md"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8")
            return {"status_code": response.status, "body": json.loads(text)}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"status": "error", "error": {"code": "non_json_error", "message": text[:200]}, "public_safe": True}
        return {"status_code": exc.code, "body": body}


def wait_for_health(base_url: str) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(60):
        try:
            last = request_json(base_url, "GET", "/health")
            if last["status_code"] == 200:
                return last
        except Exception:
            pass
        time.sleep(0.1)
    return last or {"status_code": 0, "body": {"status": "error", "error": {"code": "health_timeout"}}}


def start_server(app: Any, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def stop_server(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=10)


def base_headers(raw_key: str, client_id: str, vault_id: str, namespace: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {raw_key}",
        "X-Client-ID": client_id,
        "X-Vault-ID": vault_id,
        "X-Namespace": namespace,
    }


def strip_boundary_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: strip_boundary_fields(value) for key, value in payload.items() if key != "boundary"}
    if isinstance(payload, list):
        return [strip_boundary_fields(item) for item in payload]
    return payload


def run_http_smoke() -> tuple[PRMRHostedAPIWrapper, dict[str, Any], list[dict[str, Any]]]:
    config = load_api_config()
    wrapper = PRMRHostedAPIWrapper(config=config, reset_storage=True)
    setup = wrapper.setup_synthetic_client()
    raw_key = setup["raw_api_key"]
    client_id = setup["client"].client_id
    vault_id = setup["vault"].vault_id
    namespace = setup["namespace"].namespace
    headers = base_headers(raw_key, client_id, vault_id, namespace)

    app = create_app(wrapper=wrapper, config=config)
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server, thread = start_server(app, port)
    checks: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    try:
        results["health"] = wait_for_health(base_url)
        add_check(checks, "health_route_works", results["health"]["status_code"] == 200 and results["health"]["body"].get("server_framework") == SERVER_FRAMEWORK, results["health"]["body"])

        results["ingest"] = request_json(base_url, "POST", "/v1/events/ingest", headers=headers, payload={"events": [sample_event(1), sample_event(2)]})
        add_check(checks, "valid_http_ingest_works", results["ingest"]["status_code"] == 200 and results["ingest"]["body"].get("accepted_event_count") == 2 and results["ingest"]["body"].get("operation") == "events_ingest", results["ingest"]["body"])

        results["packet"] = request_json(base_url, "POST", "/v1/continuity/packet", headers=headers, payload={})
        packet_id = results["packet"]["body"].get("packet_id")
        report_id = results["packet"]["body"].get("report_id")
        add_check(checks, "valid_http_packet_works", results["packet"]["status_code"] == 200 and bool(packet_id) and results["packet"]["body"].get("operation") == "continuity_packet", results["packet"]["body"])

        results["reconstruct"] = request_json(base_url, "POST", "/v1/memory/reconstruct", headers=headers, payload={"packet_id": packet_id})
        add_check(checks, "valid_http_reconstruct_works", results["reconstruct"]["status_code"] == 200 and "reconstructable_state" in results["reconstruct"]["body"], results["reconstruct"]["body"])

        results["explain"] = request_json(base_url, "POST", "/v1/explain", headers=headers, payload={"packet_id": packet_id})
        add_check(checks, "valid_http_explain_works", results["explain"]["status_code"] == 200 and results["explain"]["body"]["explanation"]["sensitive_details_included"] is False, results["explain"]["body"])

        results["least_harm_action"] = request_json(base_url, "POST", "/v1/actions/least-harm", headers=headers, payload={"packet_id": packet_id})
        add_check(checks, "valid_http_least_harm_action_works", results["least_harm_action"]["status_code"] == 200 and results["least_harm_action"]["body"].get("not_final_decision") is True, results["least_harm_action"]["body"])

        results["report"] = request_json(base_url, "GET", f"/v1/reports/{report_id}", headers=headers)
        add_check(checks, "valid_http_report_read_works", results["report"]["status_code"] == 200 and results["report"]["body"]["report"].get("public_safe") is True, results["report"]["body"])

        results["usage"] = request_json(base_url, "GET", "/v1/usage", headers=headers)
        add_check(checks, "valid_http_usage_read_works", results["usage"]["status_code"] == 200 and "usage" in results["usage"]["body"], results["usage"]["body"])

        results["dashboard_state"] = request_json(base_url, "GET", "/v1/dashboard/state", headers=headers)
        dashboard = results["dashboard_state"]["body"].get("dashboard", {})
        add_check(checks, "valid_http_dashboard_state_read_works", results["dashboard_state"]["status_code"] == 200 and dashboard.get("memory_health_panel", {}).get("status") == "http_api_server_connected", dashboard.get("memory_health_panel"))

        results["missing_authorization"] = request_json(base_url, "POST", "/v1/events/ingest", headers={k: v for k, v in headers.items() if k != "Authorization"}, payload={"events": [sample_event(3)]})
        add_check(checks, "missing_authorization_blocked", results["missing_authorization"]["status_code"] == 401 and results["missing_authorization"]["body"]["error"]["code"] == "missing_key", results["missing_authorization"]["body"])

        malformed_headers = {**headers, "Authorization": f"Token {raw_key}"}
        results["malformed_authorization"] = request_json(base_url, "POST", "/v1/events/ingest", headers=malformed_headers, payload={"events": [sample_event(4)]})
        add_check(checks, "malformed_authorization_blocked", results["malformed_authorization"]["status_code"] == 401 and results["malformed_authorization"]["body"]["error"]["code"] == "malformed_authorization", results["malformed_authorization"]["body"])

        wrong_key_headers = {**headers, "Authorization": "Bearer prmr_alpha_dev_wrong000000000000000000"}
        results["wrong_key"] = request_json(base_url, "POST", "/v1/events/ingest", headers=wrong_key_headers, payload={"events": [sample_event(5)]})
        add_check(checks, "wrong_key_blocked", results["wrong_key"]["status_code"] == 401 and results["wrong_key"]["body"]["error"]["code"] == "invalid_key", results["wrong_key"]["body"])

        wrong_client_headers = {**headers, "X-Client-ID": "client_v076_wrong"}
        results["wrong_client"] = request_json(base_url, "POST", "/v1/events/ingest", headers=wrong_client_headers, payload={"events": [sample_event(6)]})
        add_check(checks, "wrong_client_blocked", results["wrong_client"]["status_code"] == 403 and results["wrong_client"]["body"]["error"]["code"] == "key_client_mismatch", results["wrong_client"]["body"])

        wrong_vault_headers = {**headers, "X-Vault-ID": "vault_v076_wrong"}
        results["wrong_vault"] = request_json(base_url, "POST", "/v1/continuity/packet", headers=wrong_vault_headers, payload={})
        add_check(checks, "wrong_vault_blocked", results["wrong_vault"]["status_code"] == 403 and results["wrong_vault"]["body"]["error"]["code"] == "vault_denied", results["wrong_vault"]["body"])

        wrong_namespace_headers = {**headers, "X-Namespace": "wrong_namespace"}
        results["wrong_namespace"] = request_json(base_url, "POST", "/v1/continuity/packet", headers=wrong_namespace_headers, payload={})
        add_check(checks, "wrong_namespace_blocked", results["wrong_namespace"]["status_code"] == 403 and results["wrong_namespace"]["body"]["error"]["code"] == "namespace_denied", results["wrong_namespace"]["body"])

        rotation = wrapper.api.lifecycle.rotate_key(
            client_id=client_id,
            old_raw_api_key=raw_key,
            operator_id="operator_v076_founder",
            approval_reason="V0.76 rotated-key local HTTP blocked proof",
        )
        wrapper.sync_storage(client_id, vault_id, namespace)
        results["rotated_old_key"] = request_json(base_url, "POST", "/v1/events/ingest", headers=headers, payload={"events": [sample_event(7)]})
        add_check(checks, "rotated_old_key_blocked", rotation.get("ok") is True and results["rotated_old_key"]["status_code"] == 403 and results["rotated_old_key"]["body"]["error"]["code"] == "rotated_key", results["rotated_old_key"]["body"])

        revoked_issue = wrapper.api.lifecycle.issue_alpha_key(
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            usage_limit_id="limit_v075_alpha",
            operator_id="operator_v076_founder",
            approval_reason="V0.76 revoked-key local HTTP blocked proof",
        )
        wrapper.api.lifecycle.revoke_key(
            key_id=revoked_issue["key_id"],
            operator_id="operator_v076_founder",
            revoke_reason="V0.76 revoked-key local HTTP blocked proof",
        )
        wrapper.sync_storage(client_id, vault_id, namespace)
        revoked_headers = base_headers(revoked_issue["raw_api_key"], client_id, vault_id, namespace)
        results["revoked_key"] = request_json(base_url, "POST", "/v1/events/ingest", headers=revoked_headers, payload={"events": [sample_event(8)]})
        add_check(checks, "revoked_key_blocked", results["revoked_key"]["status_code"] == 403 and results["revoked_key"]["body"]["error"]["code"] == "revoked_key", results["revoked_key"]["body"])

        wrapper.api.lifecycle.create_namespace(client_id, vault_id, namespace="limit_test")
        limit_issue = wrapper.api.lifecycle.issue_alpha_key(
            client_id=client_id,
            vault_id=vault_id,
            namespace="limit_test",
            usage_limit_id="limit_v075_alpha",
            operator_id="operator_v076_founder",
            approval_reason="V0.76 usage-limit local HTTP blocked proof",
        )
        wrapper.sync_storage(client_id, vault_id, "limit_test")
        limit_headers = base_headers(limit_issue["raw_api_key"], client_id, vault_id, "limit_test")
        results["limit_allowed_1"] = request_json(base_url, "POST", "/v1/events/ingest", headers=limit_headers, payload={"events": [sample_event(9)]})
        results["limit_allowed_2"] = request_json(base_url, "POST", "/v1/events/ingest", headers=limit_headers, payload={"events": [sample_event(10)]})
        results["limit_allowed_3"] = request_json(base_url, "POST", "/v1/events/ingest", headers=limit_headers, payload={"events": [sample_event(11)]})
        results["usage_limit_exceeded"] = request_json(base_url, "POST", "/v1/events/ingest", headers=limit_headers, payload={"events": [sample_event(12)]})
        add_check(checks, "usage_limit_exceeded_blocked", results["usage_limit_exceeded"]["status_code"] == 429 and results["usage_limit_exceeded"]["body"]["error"]["code"] == "usage_limit_exceeded", results["usage_limit_exceeded"]["body"])

        final_dashboard = wrapper.build_dashboard_state(client_id, vault_id, namespace)
        wrapper.storage.store_dashboard_refresh(
            {
                "refresh_id": "refresh_v076_final",
                "client_id": client_id,
                "vault_id": vault_id,
                "namespace": namespace,
                "allowed_request_count": final_dashboard["usage_overview"]["allowed_request_count"],
                "blocked_request_count": final_dashboard["usage_overview"]["blocked_request_count"],
                "events_received": final_dashboard["memory_health_panel"]["events_received"],
                "packets_generated": final_dashboard["memory_health_panel"]["packets_generated"],
                "reports_visible": final_dashboard["memory_health_panel"]["reports_visible"],
                "memory_health": "http_api_server_connected",
                "created_at": utc_now(),
            }
        )
        snapshot = wrapper.storage.export_storage_snapshot(public_safe=True)
        request_logs = wrapper.storage.list_request_logs(client_id)
        usage_logs = wrapper.storage.list_usage_logs(client_id)
        dashboard_refresh = wrapper.storage.get_latest_dashboard_refresh(client_id, vault_id, namespace)

        add_check(checks, "request_logs_persisted", len(request_logs) >= 18, len(request_logs))
        add_check(checks, "usage_logs_persisted", len(usage_logs) >= 18, len(usage_logs))
        add_check(checks, "dashboard_state_persisted", bool(dashboard_refresh), dashboard_refresh)
        add_check(checks, "storage_state_updated", len(snapshot.get("memory_events", [])) >= 5 and len(snapshot.get("continuity_packets", [])) >= 1, {key: len(value) for key, value in snapshot.items() if isinstance(value, list)})
        add_check(checks, "safe_key_previews_only", "safe_key_preview" in json.dumps(snapshot.get("api_key_records", []), sort_keys=True) and "key_hash" not in json.dumps(snapshot.get("api_key_records", []), sort_keys=True), snapshot.get("api_key_records", []))
        add_check(checks, "raw_api_keys_absent_from_public_outputs", not contains_full_dev_key({"results": results, "snapshot": snapshot}), None)
        add_check(checks, "no_real_client_data_used", all(str(client.get("client_id", "")).startswith("client_v075_synthetic") for client in snapshot.get("clients", [])), snapshot.get("clients", []))
        add_check(checks, "local_cors_security_prep_exists", results["health"]["body"].get("cors", {}).get("allowed_origins") == ["http://localhost:3000"] and results["health"]["body"].get("cors", {}).get("wildcard_origin") is False, results["health"]["body"].get("cors"))
        non_boundary_outputs = strip_boundary_fields({"results": results, "snapshot": snapshot})
        add_check(checks, "no_overclaims_in_http_outputs", not scan_terms(non_boundary_outputs, OVERCLAIMS_V076), scan_terms(non_boundary_outputs, OVERCLAIMS_V076))

        smoke_summary = {
            "base_url": base_url,
            "server_framework": SERVER_FRAMEWORK,
            "valid_routes_called": [
                "health",
                "ingest",
                "packet",
                "reconstruct",
                "explain",
                "least_harm_action",
                "report",
                "usage",
                "dashboard_state",
            ],
            "blocked_cases_called": [
                "missing_authorization",
                "malformed_authorization",
                "wrong_key",
                "revoked_key",
                "rotated_old_key",
                "wrong_client",
                "wrong_vault",
                "wrong_namespace",
                "usage_limit_exceeded",
            ],
            "allowed_request_count": len([row for row in snapshot.get("request_logs", []) if row["status"] == "allowed"]),
            "blocked_request_count": len([row for row in snapshot.get("request_logs", []) if row["status"] == "blocked"]),
            "events_received": len(snapshot.get("memory_events", [])),
            "packets_generated": len(snapshot.get("continuity_packets", [])),
            "reports_visible": len(snapshot.get("reports", [])),
            "memory_health": dashboard_refresh.get("memory_health") if dashboard_refresh else None,
        }
        results["smoke_summary"] = smoke_summary
    finally:
        stop_server(server, thread)

    return wrapper, results, checks


def main() -> int:
    wrapper, http_results, checks = run_http_smoke()
    config = wrapper.config
    smoke_summary = http_results["smoke_summary"]
    public_report = build_public_report(checks, smoke_summary, config)
    private_report = build_private_report(public_report, checks, wrapper, http_results)
    request_log = {
        "version": "0.76",
        "boundary": BOUNDARY_V076,
        "public_safe": True,
        "request_logs": wrapper.storage.export_storage_snapshot(public_safe=True).get("request_logs", []),
    }
    storage_state = wrapper.storage.export_storage_snapshot(public_safe=True)
    http_smoke_report = {
        "version": "0.76",
        "boundary": BOUNDARY_V076,
        "public_safe": True,
        "server_framework": SERVER_FRAMEWORK,
        "routes": sorted(ROUTES.keys()),
        "http_results": safe_route_results_for_public(http_results),
        "smoke_summary": smoke_summary,
    }

    add_check(checks, "public_report_has_no_restricted_material", not public_hygiene_failures(public_report)["full_dev_key_present"] and not public_hygiene_failures(public_report)["restricted_terms"], public_hygiene_failures(public_report))
    add_check(checks, "public_smoke_report_has_no_restricted_material", not public_hygiene_failures(http_smoke_report)["full_dev_key_present"] and not public_hygiene_failures(http_smoke_report)["restricted_terms"], public_hygiene_failures(http_smoke_report))

    public_report = build_public_report(checks, smoke_summary, config)
    private_report = build_private_report(public_report, checks, wrapper, http_results)
    http_smoke_report["result"] = public_report["result"]
    http_smoke_report["checks_passed"] = public_report["checks_passed"]
    http_smoke_report["checks_total"] = public_report["checks_total"]

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(HTTP_SMOKE_REPORT, http_smoke_report)
    write_json(REQUEST_LOG, request_log)
    write_json(STORAGE_STATE, storage_state)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.76 Real Local HTTP API Server")
    print(f"Server framework: {SERVER_FRAMEWORK}")
    print("Truth label: real local HTTP API server + local HTTP smoke tests")
    print(f"Routes: {len(ROUTES)}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"HTTP smoke report: {HTTP_SMOKE_REPORT.as_posix()}")
    print(f"Request log: {REQUEST_LOG.as_posix()}")
    print(f"Storage state: {STORAGE_STATE.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Allowed requests: {smoke_summary['allowed_request_count']}")
    print(f"Blocked requests: {smoke_summary['blocked_request_count']}")
    print(f"Events received: {smoke_summary['events_received']}")
    print(f"Packets generated: {smoke_summary['packets_generated']}")
    print(f"Reports visible: {smoke_summary['reports_visible']}")
    print(f"Memory health: {smoke_summary['memory_health']}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")

    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
