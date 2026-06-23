"""Run V0.75 hosted backend API wrapper smoke proof."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.api_config_v075 import load_api_config  # noqa: E402
from prmr.product.hosted_api_wrapper_v075 import (  # noqa: E402
    BOUNDARY_V075,
    OVERCLAIMS,
    PUBLIC_FORBIDDEN_TERMS,
    PRMRHostedAPIWrapper,
    REPORT_DIR,
    ROUTES,
    build_private_report,
    build_public_report,
    build_scorecard,
    contains_full_dev_key,
    sample_event,
    scan_terms,
)
from prmr.product.persistent_storage_v074 import write_json  # noqa: E402


PUBLIC_REPORT = REPORT_DIR / "public_hosted_api_wrapper_v075.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_api_wrapper_v075.json"
REQUEST_LOG = REPORT_DIR / "api_wrapper_request_log_v075.json"
STORAGE_STATE = REPORT_DIR / "api_wrapper_storage_state_v075.json"
SCORECARD = REPORT_DIR / "scorecard_v075.md"


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def run_route_flow() -> tuple[PRMRHostedAPIWrapper, dict[str, Any], list[dict[str, Any]]]:
    config = load_api_config()
    wrapper = PRMRHostedAPIWrapper(config=config, reset_storage=True)
    checks: list[dict[str, Any]] = []
    route_results: dict[str, Any] = {}

    setup = wrapper.setup_synthetic_client()
    raw_key = setup["raw_api_key"]
    client_id = setup["client"].client_id
    vault_id = setup["vault"].vault_id
    namespace = setup["namespace"].namespace
    base = {"client_id": client_id, "vault_id": vault_id, "namespace": namespace, "api_key": raw_key}

    route_results["health"] = wrapper.health()
    add_check(checks, "health_route_works", route_results["health"]["status_code"] == 200, route_results["health"]["body"])

    route_results["ingest"] = wrapper.events_ingest({**base, "events": [sample_event(1), sample_event(2)]})
    add_check(checks, "valid_ingest_works", route_results["ingest"]["status_code"] == 200 and route_results["ingest"]["body"].get("accepted_event_count") == 2, route_results["ingest"]["body"])

    route_results["packet"] = wrapper.continuity_packet(base)
    packet_id = route_results["packet"]["body"].get("packet_id")
    report_id = route_results["packet"]["body"].get("report_id")
    add_check(checks, "valid_continuity_packet_works", route_results["packet"]["status_code"] == 200 and bool(packet_id), route_results["packet"]["body"])

    route_results["reconstruct"] = wrapper.memory_reconstruct({**base, "packet_id": packet_id})
    add_check(checks, "valid_reconstruct_works", route_results["reconstruct"]["status_code"] == 200 and "reconstructable_state" in route_results["reconstruct"]["body"], route_results["reconstruct"]["body"])

    route_results["explain"] = wrapper.explain({**base, "packet_id": packet_id})
    add_check(checks, "valid_explain_works", route_results["explain"]["status_code"] == 200 and route_results["explain"]["body"]["explanation"]["sensitive_details_included"] is False, route_results["explain"]["body"])

    route_results["least_harm_action"] = wrapper.least_harm_action({**base, "packet_id": packet_id})
    add_check(checks, "valid_least_harm_action_works", route_results["least_harm_action"]["status_code"] == 200 and route_results["least_harm_action"]["body"].get("not_final_decision") is True, route_results["least_harm_action"]["body"])

    route_results["report"] = wrapper.get_report(base, str(report_id))
    add_check(checks, "valid_report_read_works", route_results["report"]["status_code"] == 200 and route_results["report"]["body"]["report"]["public_safe"] is True, route_results["report"]["body"])

    route_results["usage"] = wrapper.get_usage(base)
    add_check(checks, "valid_usage_read_works", route_results["usage"]["status_code"] == 200 and "usage" in route_results["usage"]["body"], route_results["usage"]["body"])

    route_results["dashboard_state"] = wrapper.get_dashboard_state(base)
    dashboard_state = route_results["dashboard_state"]["body"].get("dashboard", {})
    add_check(checks, "valid_dashboard_state_read_works", route_results["dashboard_state"]["status_code"] == 200 and dashboard_state.get("memory_health_panel", {}).get("status") == "api_wrapper_connected", dashboard_state)

    route_results["missing_key"] = wrapper.events_ingest({**base, "api_key": None, "events": [sample_event(3)]})
    add_check(checks, "missing_key_blocked", route_results["missing_key"]["status_code"] == 401 and route_results["missing_key"]["body"]["error"]["code"] == "missing_key", route_results["missing_key"]["body"])

    route_results["wrong_key"] = wrapper.events_ingest({**base, "api_key": "prmr_alpha_dev_wrong000000000000000000", "events": [sample_event(4)]})
    add_check(checks, "wrong_key_blocked", route_results["wrong_key"]["status_code"] == 401 and route_results["wrong_key"]["body"]["error"]["code"] == "invalid_key", route_results["wrong_key"]["body"])

    route_results["wrong_client"] = wrapper.events_ingest({**base, "client_id": "client_v075_wrong", "events": [sample_event(5)]})
    add_check(checks, "wrong_client_blocked", route_results["wrong_client"]["status_code"] == 403 and route_results["wrong_client"]["body"]["error"]["code"] == "key_client_mismatch", route_results["wrong_client"]["body"])

    route_results["wrong_vault"] = wrapper.continuity_packet({**base, "vault_id": "vault_v075_wrong"})
    add_check(checks, "wrong_vault_blocked", route_results["wrong_vault"]["status_code"] == 403 and route_results["wrong_vault"]["body"]["error"]["code"] == "vault_denied", route_results["wrong_vault"]["body"])

    route_results["wrong_namespace"] = wrapper.continuity_packet({**base, "namespace": "wrong_namespace"})
    add_check(checks, "wrong_namespace_blocked", route_results["wrong_namespace"]["status_code"] == 403 and route_results["wrong_namespace"]["body"]["error"]["code"] == "namespace_denied", route_results["wrong_namespace"]["body"])

    rotation = wrapper.api.lifecycle.rotate_key(
        client_id=client_id,
        old_raw_api_key=raw_key,
        operator_id="operator_v075_founder",
        approval_reason="V0.75 rotated-key blocked proof",
    )
    wrapper.sync_storage(client_id, vault_id, namespace)
    route_results["rotated_key"] = wrapper.events_ingest({**base, "events": [sample_event(6)]})
    add_check(checks, "rotated_key_blocked", rotation.get("ok") is True and route_results["rotated_key"]["status_code"] == 403 and route_results["rotated_key"]["body"]["error"]["code"] == "rotated_key", route_results["rotated_key"]["body"])

    revoked_issue = wrapper.api.lifecycle.issue_alpha_key(
        client_id=client_id,
        vault_id=vault_id,
        namespace=namespace,
        usage_limit_id="limit_v075_alpha",
        operator_id="operator_v075_founder",
        approval_reason="V0.75 revoked-key blocked proof",
    )
    wrapper.api.lifecycle.revoke_key(
        key_id=revoked_issue["key_id"],
        operator_id="operator_v075_founder",
        revoke_reason="V0.75 revoked-key blocked proof",
    )
    wrapper.sync_storage(client_id, vault_id, namespace)
    route_results["revoked_key"] = wrapper.events_ingest({**base, "api_key": revoked_issue["raw_api_key"], "events": [sample_event(7)]})
    add_check(checks, "revoked_key_blocked", route_results["revoked_key"]["status_code"] == 403 and route_results["revoked_key"]["body"]["error"]["code"] == "revoked_key", route_results["revoked_key"]["body"])

    wrapper.api.lifecycle.create_namespace(client_id, vault_id, namespace="limit_test")
    limit_issue = wrapper.api.lifecycle.issue_alpha_key(
        client_id=client_id,
        vault_id=vault_id,
        namespace="limit_test",
        usage_limit_id="limit_v075_alpha",
        operator_id="operator_v075_founder",
        approval_reason="V0.75 usage-limit blocked proof",
    )
    limit_base = {"client_id": client_id, "vault_id": vault_id, "namespace": "limit_test", "api_key": limit_issue["raw_api_key"]}
    route_results["limit_allowed_1"] = wrapper.events_ingest({**limit_base, "events": [sample_event(8)]})
    route_results["limit_allowed_2"] = wrapper.events_ingest({**limit_base, "events": [sample_event(9)]})
    route_results["limit_allowed_3"] = wrapper.events_ingest({**limit_base, "events": [sample_event(10)]})
    route_results["usage_limit_exceeded"] = wrapper.events_ingest({**limit_base, "events": [sample_event(11)]})
    add_check(checks, "usage_limit_exceeded_blocked", route_results["usage_limit_exceeded"]["status_code"] == 429 and route_results["usage_limit_exceeded"]["body"]["error"]["code"] == "usage_limit_exceeded", route_results["usage_limit_exceeded"]["body"])

    final_dashboard = wrapper.build_dashboard_state(client_id, vault_id, namespace)
    wrapper.persist_dashboard_refresh(client_id, vault_id, namespace)
    route_results["final_dashboard_state"] = {"status_code": 200, "body": {"dashboard": final_dashboard}}

    add_check(checks, "valid_calls_persist_storage_records", len(wrapper.storage.list_memory_events(client_id, vault_id, namespace)) >= 2 and bool(wrapper.storage.get_continuity_packet(client_id, vault_id, namespace, str(packet_id))), None)
    add_check(checks, "request_logs_persist", len(wrapper.storage.list_request_logs(client_id)) >= 15, len(wrapper.storage.list_request_logs(client_id)))
    add_check(checks, "usage_logs_persist", len(wrapper.storage.list_usage_logs(client_id)) >= 15, len(wrapper.storage.list_usage_logs(client_id)))
    add_check(checks, "dashboard_refresh_persists", bool(wrapper.storage.get_latest_dashboard_refresh(client_id, vault_id, namespace)), wrapper.storage.get_latest_dashboard_refresh(client_id, vault_id, namespace))
    key_text = json.dumps(final_dashboard.get("api_key_panel", {}), sort_keys=True)
    add_check(checks, "dashboard_state_uses_safe_key_previews_only", "safe_key_preview" in key_text and "key_hash" not in key_text and not contains_full_dev_key(key_text), None)
    add_check(checks, "raw_api_keys_absent_from_dashboard_state", not contains_full_dev_key(final_dashboard), None)
    add_check(checks, "no_real_client_data_used", final_dashboard.get("client_overview", {}).get("synthetic_only") is True, final_dashboard.get("client_overview"))
    add_check(checks, "no_overclaims_in_dashboard_state", not scan_terms(final_dashboard, OVERCLAIMS), scan_terms(final_dashboard, OVERCLAIMS))

    # Drop runtime-only raw key values before report export.
    safe_route_results = json.loads(json.dumps(route_results))
    return wrapper, safe_route_results, checks


def main() -> int:
    wrapper, route_results, checks = run_route_flow()
    dashboard_state = route_results["final_dashboard_state"]["body"]["dashboard"]
    public_report = build_public_report(checks, dashboard_state, wrapper.config)
    private_report = build_private_report(public_report, checks, wrapper, route_results)
    storage_state = wrapper.storage.export_storage_snapshot(public_safe=True)
    request_log = {
        "version": "0.75",
        "boundary": BOUNDARY_V075,
        "request_logs": wrapper.storage.list_request_logs("client_v075_synthetic_alpha"),
    }

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(REQUEST_LOG, request_log)
    write_json(STORAGE_STATE, storage_state)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.75 Hosted Backend API Wrapper")
    print("Router approach: local server-shaped route handler abstraction")
    print(f"Routes: {len(ROUTES)}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Request log: {REQUEST_LOG.as_posix()}")
    print(f"Storage state: {STORAGE_STATE.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Allowed requests: {dashboard_state['usage_overview']['allowed_request_count']}")
    print(f"Blocked requests: {dashboard_state['usage_overview']['blocked_request_count']}")
    print(f"Events received: {dashboard_state['memory_health_panel']['events_received']}")
    print(f"Packets generated: {dashboard_state['memory_health_panel']['packets_generated']}")
    print(f"Reports visible: {dashboard_state['memory_health_panel']['reports_visible']}")
    print(f"Memory health: {dashboard_state['memory_health_panel']['status']}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")

    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
