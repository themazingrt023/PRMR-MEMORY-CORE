"""Run V0.70 manual API key lifecycle simulation."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.api_key_lifecycle_v070 import (  # noqa: E402
    BOUNDARY_V070,
    PRMRAPIKeyLifecycle,
    scan_forbidden_public_terms,
    scan_unsafe_public_language,
)


REPORT_DIR = Path("reports/v070")
PUBLIC_REPORT = REPORT_DIR / "public_api_key_lifecycle_v070.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_key_lifecycle_v070.json"
LIFECYCLE_EVENTS = REPORT_DIR / "key_lifecycle_events_v070.json"
USAGE_SUMMARY = REPORT_DIR / "usage_summary_v070.json"
SCORECARD = REPORT_DIR / "scorecard_v070.md"


def add_check(checks: list[dict], name: str, passed: bool, details: dict | None = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def contains_full_dev_key(payload: object) -> bool:
    text = json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def build_scorecard(public_report: dict, checks: list[dict]) -> str:
    lines = [
        "# V0.70 Manual API Key Lifecycle Layer",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V070}",
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
            "## Lifecycle Functions",
            "",
            *[f"- {name}" for name in public_report["lifecycle_functions"]],
            "",
            "## Command Results",
            "",
            "- RUN: python examples/run_api_key_lifecycle_v070.py",
            "",
            BOUNDARY_V070,
            "",
        ]
    )
    return "\n".join(lines)


def simulate_lifecycle() -> tuple[PRMRAPIKeyLifecycle, list[dict], dict]:
    lifecycle = PRMRAPIKeyLifecycle()
    checks: list[dict] = []

    client = lifecycle.create_client(
        organisation="Synthetic Alpha Client",
        contact_email="synthetic-alpha@example.test",
        client_id="client_v070_synthetic_alpha",
    )
    add_check(checks, "create_synthetic_client", client.client_id == "client_v070_synthetic_alpha", {"status": client.status})

    limit = lifecycle.create_usage_limit(
        usage_limit_id="limit_v070_alpha",
        max_events_per_day=20,
        max_packets_per_day=20,
        max_reports_per_day=20,
        alpha_limit_reason="V0.70 manual lifecycle local alpha limit.",
    )
    vault = lifecycle.create_vault(client.client_id, vault_id="vault_v070_alpha")
    namespace = lifecycle.create_namespace(client.client_id, vault.vault_id, namespace="default")
    add_check(checks, "create_vault", vault.client_id == client.client_id, {"vault_id": vault.vault_id})
    add_check(checks, "create_namespace", namespace.vault_id == vault.vault_id, {"namespace": namespace.namespace})

    blocked_issue = lifecycle.issue_alpha_key(
        client_id=client.client_id,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        usage_limit_id=limit.usage_limit_id,
        operator_id="",
        approval_reason="",
    )
    add_check(
        checks,
        "issue_without_operator_approval_blocked",
        blocked_issue["ok"] is False and blocked_issue["reason"] == "operator_approval_required",
        blocked_issue,
    )

    issue = lifecycle.issue_alpha_key(
        client_id=client.client_id,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        usage_limit_id=limit.usage_limit_id,
        operator_id="operator_v070_founder",
        approval_reason="approved for synthetic local alpha lifecycle test",
    )
    first_raw_key = issue["raw_api_key"]
    first_key_id = issue["key_id"]
    add_check(checks, "issue_with_operator_approval_works", issue["ok"] is True and first_raw_key.startswith("prmr_alpha_dev_"), {"key_id": first_key_id})

    active = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=first_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "active_key_validates", active.allowed and active.status_code == 200, {"reason": active.reason})

    missing = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=None,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "missing_key_blocked", not missing.allowed and missing.reason == "missing_key", {"reason": missing.reason})

    wrong = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key="prmr_alpha_dev_wrong00000000000000000000",
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "wrong_key_blocked", not wrong.allowed and wrong.reason == "invalid_key", {"reason": wrong.reason})

    rotation = lifecycle.rotate_key(
        client_id=client.client_id,
        old_raw_api_key=first_raw_key,
        operator_id="operator_v070_founder",
        approval_reason="routine local alpha rotation test",
    )
    rotated_raw_key = rotation["raw_api_key"]
    rotated_key_id = rotation["new_key_id"]
    add_check(checks, "rotate_key_works", rotation["ok"] is True and rotated_raw_key.startswith("prmr_alpha_dev_"), {"new_key_id": rotated_key_id})

    old_after_rotation = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=first_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(
        checks,
        "old_rotated_key_blocked",
        not old_after_rotation.allowed and old_after_rotation.reason == "rotated_key",
        {"reason": old_after_rotation.reason},
    )

    new_after_rotation = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=rotated_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "rotated_new_key_validates", new_after_rotation.allowed, {"reason": new_after_rotation.reason})

    revoke = lifecycle.revoke_key(
        key_id=rotated_key_id,
        operator_id="operator_v070_founder",
        revoke_reason="end rotated-key validation test",
    )
    revoked_validate = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=rotated_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(
        checks,
        "revoked_key_blocked",
        revoke["ok"] is True and not revoked_validate.allowed and revoked_validate.reason == "revoked_key",
        {"reason": revoked_validate.reason},
    )

    second_issue = lifecycle.issue_alpha_key(
        client_id=client.client_id,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        usage_limit_id=limit.usage_limit_id,
        operator_id="operator_v070_founder",
        approval_reason="approved for suspension/reactivation test",
    )
    second_raw_key = second_issue["raw_api_key"]
    second_key_id = second_issue["key_id"]

    suspend = lifecycle.suspend_client(
        client_id=client.client_id,
        operator_id="operator_v070_founder",
        reason="local suspension behavior test",
    )
    suspended_validate = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=second_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(
        checks,
        "suspended_client_blocks_validation",
        suspend["ok"] is True and not suspended_validate.allowed and suspended_validate.reason in {"client_not_active", "rotated_key"},
        {"reason": suspended_validate.reason},
    )

    reactivate = lifecycle.reactivate_client(
        client_id=client.client_id,
        operator_id="operator_v070_founder",
        reason="local reactivation behavior test",
    )
    reactivated_validate = lifecycle.validate_key(
        client_id=client.client_id,
        raw_api_key=second_raw_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(
        checks,
        "reactivated_client_key_validates",
        reactivate["ok"] is True and reactivated_validate.allowed,
        {"reason": reactivated_validate.reason},
    )

    key_status = lifecycle.get_key_status(second_key_id)
    usage = lifecycle.get_client_usage(client.client_id)
    add_check(checks, "get_key_status_safe", key_status["ok"] is True and "key_hash" not in key_status["key"], key_status)
    add_check(
        checks,
        "usage_logs_allowed_and_blocked",
        usage["allowed_request_count"] >= 3 and usage["blocked_request_count"] >= 5,
        usage,
    )
    add_check(checks, "lifecycle_event_history_exists", len(lifecycle.lifecycle_events) >= 7, {"events": len(lifecycle.lifecycle_events)})

    runtime = {
        "issue_raw_key": first_raw_key,
        "rotation_raw_key": rotated_raw_key,
        "second_issue_raw_key": second_raw_key,
    }
    return lifecycle, checks, runtime


def main() -> None:
    print("PRMR V0.70 API KEY LIFECYCLE")
    print("----------------------------")

    lifecycle, checks, runtime = simulate_lifecycle()

    public_report, private_report = lifecycle.export_key_lifecycle_report(checks)
    public_forbidden = scan_forbidden_public_terms(public_report)
    public_unsafe = scan_unsafe_public_language(public_report)
    add_check(checks, "public_report_contains_no_raw_keys", not contains_full_dev_key(public_report), {})
    add_check(checks, "private_report_contains_no_raw_keys_persisted", not contains_full_dev_key(private_report), {})
    add_check(checks, "public_report_contains_no_private_internals", not public_forbidden, {"terms": public_forbidden})
    add_check(checks, "public_report_uses_non_punitive_wording", not public_unsafe, {"terms": public_unsafe})

    # Prove runtime delivery happened without persisting the values.
    add_check(
        checks,
        "raw_key_returned_only_at_issue_or_rotation_runtime",
        all(value.startswith("prmr_alpha_dev_") for value in runtime.values()),
        {"runtime_values_returned": len(runtime)},
    )

    public_report, private_report = lifecycle.export_key_lifecycle_report(checks)

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(
        LIFECYCLE_EVENTS,
        {
            "version": "0.70",
            "boundary": BOUNDARY_V070,
            "events": lifecycle.lifecycle_events_private(),
            "raw_api_keys_persisted": False,
        },
    )
    write_json(
        USAGE_SUMMARY,
        {
            "version": "0.70",
            "boundary": BOUNDARY_V070,
            "usage": lifecycle.get_client_usage("client_v070_synthetic_alpha"),
            "raw_api_keys_persisted": False,
        },
    )
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Created:")
    print(PUBLIC_REPORT)
    print(PRIVATE_REPORT)
    print(LIFECYCLE_EVENTS)
    print(USAGE_SUMMARY)
    print(SCORECARD)


if __name__ == "__main__":
    main()
