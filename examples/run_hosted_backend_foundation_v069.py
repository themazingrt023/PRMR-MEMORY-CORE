"""Run V0.69 local hosted-backend foundation simulation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.hosted_backend_foundation_v069 import (
    BOUNDARY_V069,
    PRMRHostedBackendFoundation,
    dataclass_list,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


REPORT_DIR = Path("reports/v069")
PUBLIC_REPORT = REPORT_DIR / "public_hosted_backend_foundation_v069.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_backend_foundation_v069.json"
USAGE_LEDGER = REPORT_DIR / "usage_ledger_v069.json"
REQUEST_LOG = REPORT_DIR / "request_log_v069.json"
SCORECARD = REPORT_DIR / "scorecard_v069.md"

RAW_TEST_KEY = "prmr_v069_local_alpha_test_key_not_real"
WRONG_TEST_KEY = "prmr_v069_wrong_local_test_key_not_real"


def add_check(checks: list[dict], name: str, passed: bool, details: dict | None = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_scorecard(public_report: dict, checks: list[dict]) -> str:
    lines = [
        "# V0.69 Hosted Backend Foundation / Product Platform Base",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V069}",
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
            "## Product Objects",
            "",
            *[f"- {name}" for name in public_report["foundation_objects"]],
            "",
            "## Command Results",
            "",
            "- RUN: python examples/run_hosted_backend_foundation_v069.py",
            "",
            BOUNDARY_V069,
            "",
        ]
    )
    return "\n".join(lines)


def simulate_foundation() -> tuple[PRMRHostedBackendFoundation, list[dict]]:
    foundation = PRMRHostedBackendFoundation()
    checks: list[dict] = []

    client = foundation.create_client(
        organisation="Synthetic Alpha Client",
        contact_email="synthetic-alpha@example.test",
        client_id="client_v069_synthetic_alpha",
    )
    other_client = foundation.create_client(
        organisation="Synthetic Other Client",
        contact_email="synthetic-other@example.test",
        client_id="client_v069_other",
    )
    limit = foundation.create_usage_limit(
        max_events_per_day=2,
        max_packets_per_day=1,
        max_reports_per_day=1,
        alpha_limit_reason="V0.69 local alpha usage ceiling for safe simulation.",
        usage_limit_id="limit_v069_alpha",
    )
    vault = foundation.create_vault(client.client_id, vault_id="vault_v069_alpha")
    other_vault = foundation.create_vault(other_client.client_id, vault_id="vault_v069_other")
    namespace = foundation.create_namespace(client.client_id, vault.vault_id, namespace="default")
    foundation.create_namespace(other_client.client_id, other_vault.vault_id, namespace="default")
    key_record = foundation.create_test_key_record(
        client_id=client.client_id,
        raw_key=RAW_TEST_KEY,
        usage_limit_id=limit.usage_limit_id,
        key_id="key_v069_alpha",
    )

    report_ref = foundation.register_report(client.client_id, vault.vault_id, namespace.namespace)

    valid = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=RAW_TEST_KEY,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "valid_key_allowed", valid.allowed and valid.status_code == 200, {"decision": valid.reason})

    missing = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=None,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "missing_key_blocked", not missing.allowed and missing.reason == "missing_key", {"decision": missing.reason})

    wrong_key = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=WRONG_TEST_KEY,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "wrong_key_blocked", not wrong_key.allowed and wrong_key.reason == "invalid_key", {"decision": wrong_key.reason})

    foundation.revoke_key(key_record.key_id)
    revoked = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=RAW_TEST_KEY,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="events_ingest",
    )
    add_check(checks, "revoked_key_blocked", not revoked.allowed and revoked.reason == "revoked_key", {"decision": revoked.reason})

    replacement_key = "prmr_v069_local_alpha_replacement_key_not_real"
    replacement = foundation.create_test_key_record(
        client_id=client.client_id,
        raw_key=replacement_key,
        usage_limit_id=limit.usage_limit_id,
        key_id="key_v069_alpha_replacement",
    )

    wrong_vault = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=replacement_key,
        vault_id=other_vault.vault_id,
        namespace="default",
        operation="continuity_packet",
    )
    add_check(checks, "wrong_vault_blocked", not wrong_vault.allowed and wrong_vault.reason == "vault_denied", {"decision": wrong_vault.reason})

    wrong_namespace = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=replacement_key,
        vault_id=vault.vault_id,
        namespace="other_namespace",
        operation="continuity_packet",
    )
    add_check(
        checks,
        "wrong_namespace_blocked",
        not wrong_namespace.allowed and wrong_namespace.reason == "namespace_denied",
        {"decision": wrong_namespace.reason},
    )

    packet_allowed = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=replacement_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="continuity_packet",
    )
    add_check(checks, "continuity_packet_allowed_before_limit", packet_allowed.allowed, {"decision": packet_allowed.reason})

    packet_limit = foundation.validate_access(
        client_id=client.client_id,
        raw_api_key=replacement_key,
        vault_id=vault.vault_id,
        namespace=namespace.namespace,
        operation="continuity_packet",
    )
    add_check(
        checks,
        "usage_limit_enforced",
        not packet_limit.allowed and packet_limit.reason == "usage_limit_exceeded",
        {"decision": packet_limit.reason},
    )

    add_check(checks, "usage_logged", len(foundation.usage_ledger) >= 8, {"usage_events": len(foundation.usage_ledger)})
    add_check(checks, "request_log_written", len(foundation.request_log) >= 8, {"request_logs": len(foundation.request_log)})
    add_check(checks, "report_ref_registered", report_ref.report_id in foundation.report_registry, {"report_id": report_ref.report_id})
    add_check(checks, "key_last_used_updated", replacement.last_used_at is not None, {"last_used_at": replacement.last_used_at})

    return foundation, checks


def main() -> None:
    print("PRMR V0.69 HOSTED BACKEND FOUNDATION")
    print("------------------------------------")

    foundation, checks = simulate_foundation()

    public_report = foundation.public_status_report(checks)
    public_forbidden = scan_public_forbidden_terms(public_report)
    public_unsafe = scan_unsafe_public_language(public_report)
    public_text = json.dumps(public_report)
    add_check(
        checks,
        "public_report_contains_no_raw_keys",
        RAW_TEST_KEY not in public_text and WRONG_TEST_KEY not in public_text and "replacement_key" not in public_text,
        {},
    )
    add_check(checks, "public_report_contains_no_private_internals", not public_forbidden, {"terms": public_forbidden})
    add_check(checks, "public_report_uses_non_punitive_wording", not public_unsafe, {"terms": public_unsafe})

    public_report = foundation.public_status_report(checks)
    private_report = foundation.private_status_report(checks)

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(
        USAGE_LEDGER,
        {
            "version": "0.69",
            "boundary": BOUNDARY_V069,
            "usage_summary": foundation.usage_summary(),
            "usage_events": dataclass_list(foundation.usage_ledger),
        },
    )
    write_json(
        REQUEST_LOG,
        {
            "version": "0.69",
            "boundary": BOUNDARY_V069,
            "request_logs": dataclass_list(foundation.request_log),
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
    print(USAGE_LEDGER)
    print(REQUEST_LOG)
    print(SCORECARD)


if __name__ == "__main__":
    main()
