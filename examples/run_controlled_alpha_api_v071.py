"""Run V0.71 controlled-alpha API surface simulation."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.controlled_alpha_api_v071 import (  # noqa: E402
    BOUNDARY_V071,
    ENDPOINTS,
    PRMRControlledAlphaAPI,
    scan_forbidden_public_terms,
    scan_unsafe_public_language,
)


REPORT_DIR = Path("reports/v071")
PUBLIC_REPORT = REPORT_DIR / "public_controlled_alpha_api_v071.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_controlled_alpha_api_v071.json"
REQUEST_LOG = REPORT_DIR / "api_request_log_v071.json"
USAGE_SUMMARY = REPORT_DIR / "api_usage_summary_v071.json"
SCORECARD = REPORT_DIR / "scorecard_v071.md"


def add_check(checks: list[dict], name: str, passed: bool, details: dict | None = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def full_dev_key_present(obj: object) -> bool:
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", json.dumps(obj, sort_keys=True)))


def sample_event() -> dict:
    return {
        "event_id": "evt_v071_001",
        "user_id": "synthetic_user_071",
        "type": "project_memory",
        "content": "Synthetic user is building a persistent AI companion and needs continuity across sessions.",
        "timestamp": "2026-06-22T00:00:00Z",
    }


def build_scorecard(public_report: dict, checks: list[dict]) -> str:
    lines = [
        "# V0.71 Hosted Controlled-Alpha API Surface",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V071}",
        "",
        "## Endpoints",
        "",
        *[f"- {endpoint}" for endpoint in ENDPOINTS],
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Command Results",
            "",
            "- RUN: python examples/run_controlled_alpha_api_v071.py",
            "",
            BOUNDARY_V071,
            "",
        ]
    )
    return "\n".join(lines)


def simulate_api() -> tuple[PRMRControlledAlphaAPI, list[dict], dict]:
    api = PRMRControlledAlphaAPI()
    checks: list[dict] = []
    setup = api.setup_synthetic_client()
    raw_key = setup["raw_api_key"]
    client_id = setup["client"].client_id
    vault_id = setup["vault"].vault_id
    namespace = setup["namespace"].namespace

    base = {
        "client_id": client_id,
        "vault_id": vault_id,
        "namespace": namespace,
        "api_key": raw_key,
    }

    ingest = api.events_ingest({**base, "events": [sample_event()]})
    add_check(checks, "valid_ingest_works", ingest["status_code"] == 200 and ingest["body"].get("accepted_event_count") == 1, ingest["body"])

    packet = api.continuity_packet(base)
    packet_id = packet["body"].get("packet_id")
    report_id = packet["body"].get("report_id")
    add_check(checks, "continuity_packet_works", packet["status_code"] == 200 and bool(packet_id), packet["body"])

    reconstruct = api.memory_reconstruct({**base, "packet_id": packet_id})
    add_check(
        checks,
        "memory_reconstruct_works",
        reconstruct["status_code"] == 200 and "reconstructable_state" in reconstruct["body"],
        reconstruct["body"],
    )

    explanation = api.explain({**base, "packet_id": packet_id})
    add_check(
        checks,
        "explain_works",
        explanation["status_code"] == 200 and explanation["body"]["explanation"]["sensitive_details_included"] is False,
        explanation["body"],
    )

    action = api.least_harm_action({**base, "packet_id": packet_id})
    add_check(
        checks,
        "least_harm_action_works",
        action["status_code"] == 200 and action["body"]["not_final_decision"] is True,
        action["body"],
    )

    report = api.get_report(base, report_id)
    add_check(
        checks,
        "report_read_works",
        report["status_code"] == 200 and report["body"]["report"]["public_safe"] is True,
        report["body"],
    )

    usage = api.get_usage(base)
    add_check(checks, "usage_read_works", usage["status_code"] == 200 and "usage" in usage["body"], usage["body"])

    missing = api.events_ingest({**base, "api_key": None, "events": [sample_event()]})
    add_check(checks, "missing_key_blocked", missing["status_code"] == 401 and missing["body"]["error"]["code"] == "missing_key", missing["body"])

    wrong = api.events_ingest({**base, "api_key": "prmr_alpha_dev_wrong000000000000000000", "events": [sample_event()]})
    add_check(checks, "wrong_key_blocked", wrong["status_code"] == 401 and wrong["body"]["error"]["code"] == "invalid_key", wrong["body"])

    other = PRMRControlledAlphaAPI()
    other_setup = other.setup_synthetic_client(client_id="client_v071_other", vault_id="vault_v071_other")
    wrong_client = api.events_ingest(
        {
            "client_id": "client_v071_other",
            "vault_id": vault_id,
            "namespace": namespace,
            "api_key": raw_key,
            "events": [sample_event()],
        }
    )
    add_check(
        checks,
        "wrong_client_blocked",
        wrong_client["status_code"] == 403 and wrong_client["body"]["error"]["code"] == "key_client_mismatch",
        wrong_client["body"],
    )

    wrong_vault = api.continuity_packet({**base, "vault_id": other_setup["vault"].vault_id})
    add_check(
        checks,
        "wrong_vault_blocked",
        wrong_vault["status_code"] == 403 and wrong_vault["body"]["error"]["code"] == "vault_denied",
        wrong_vault["body"],
    )

    wrong_namespace = api.continuity_packet({**base, "namespace": "wrong_namespace"})
    add_check(
        checks,
        "wrong_namespace_blocked",
        wrong_namespace["status_code"] == 403 and wrong_namespace["body"]["error"]["code"] == "namespace_denied",
        wrong_namespace["body"],
    )

    rotation = api.lifecycle.rotate_key(
        client_id=client_id,
        old_raw_api_key=raw_key,
        operator_id="operator_v071_founder",
        approval_reason="rotation test for controlled-alpha API",
    )
    rotated_key = rotation["raw_api_key"]
    old_rotated = api.events_ingest({**base, "events": [sample_event()]})
    add_check(
        checks,
        "rotated_old_key_blocked",
        old_rotated["status_code"] == 403 and old_rotated["body"]["error"]["code"] == "rotated_key",
        old_rotated["body"],
    )

    rotated_base = {**base, "api_key": rotated_key}
    rotated_valid = api.events_ingest({**rotated_base, "events": [sample_event()]})
    add_check(checks, "rotated_new_key_validates", rotated_valid["status_code"] == 200, rotated_valid["body"])

    revoke = api.lifecycle.revoke_key(
        key_id=rotation["new_key_id"],
        operator_id="operator_v071_founder",
        revoke_reason="revoked after rotation validation",
    )
    revoked = api.events_ingest({**rotated_base, "events": [sample_event()]})
    add_check(
        checks,
        "revoked_key_blocked",
        revoke["ok"] is True and revoked["status_code"] == 403 and revoked["body"]["error"]["code"] == "revoked_key",
        revoked["body"],
    )

    api.lifecycle.create_namespace(client_id, vault_id, namespace="limit_test")
    second_issue = api.lifecycle.issue_alpha_key(
        client_id=client_id,
        vault_id=vault_id,
        namespace="limit_test",
        usage_limit_id="limit_v071_alpha",
        operator_id="operator_v071_founder",
        approval_reason="issue key for limit test",
    )
    limit_key = second_issue["raw_api_key"]
    limit_base = {**base, "api_key": limit_key, "namespace": "limit_test"}
    # max_events_per_day is 3; this key has already logged no events, so three pass and the fourth blocks.
    api.events_ingest({**limit_base, "events": [sample_event()]})
    api.events_ingest({**limit_base, "events": [sample_event()]})
    api.events_ingest({**limit_base, "events": [sample_event()]})
    limit_exceeded = api.events_ingest({**limit_base, "events": [sample_event()]})
    add_check(
        checks,
        "usage_limit_enforced",
        limit_exceeded["status_code"] == 429 and limit_exceeded["body"]["error"]["code"] == "usage_limit_exceeded",
        limit_exceeded["body"],
    )

    add_check(checks, "usage_logged", api.lifecycle.foundation.usage_summary()["allowed_request_count"] >= 7, api.lifecycle.foundation.usage_summary())
    add_check(checks, "request_log_created", len(api.api_request_log) >= 15, {"api_request_log_count": len(api.api_request_log)})

    runtime = {
        "initial_raw_key": raw_key,
        "rotated_raw_key": rotated_key,
        "limit_raw_key": limit_key,
    }
    return api, checks, runtime


def main() -> None:
    print("PRMR V0.71 CONTROLLED-ALPHA API SURFACE")
    print("---------------------------------------")
    api, checks, runtime = simulate_api()

    public_report = api.public_status_report(checks)
    private_report = api.private_status_report(checks)
    public_forbidden = scan_forbidden_public_terms(public_report)
    public_unsafe = scan_unsafe_public_language(public_report)
    add_check(checks, "public_report_contains_no_raw_keys", not full_dev_key_present(public_report), {})
    add_check(checks, "private_report_contains_no_raw_keys_persisted", not full_dev_key_present(private_report), {})
    add_check(checks, "runtime_raw_keys_returned_but_not_persisted", all(value.startswith("prmr_alpha_dev_") for value in runtime.values()), {"runtime_values": len(runtime)})
    add_check(checks, "public_report_contains_no_private_internals", not public_forbidden, {"terms": public_forbidden})
    add_check(checks, "public_report_uses_non_punitive_wording", not public_unsafe, {"terms": public_unsafe})

    public_report = api.public_status_report(checks)
    private_report = api.private_status_report(checks)
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(REQUEST_LOG, api.request_log_report())
    write_json(USAGE_SUMMARY, api.usage_summary_report())
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Created:")
    print(PUBLIC_REPORT)
    print(PRIVATE_REPORT)
    print(REQUEST_LOG)
    print(USAGE_SUMMARY)
    print(SCORECARD)


if __name__ == "__main__":
    main()
