import json
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    ALPHA_SANDBOX_KEYS,
    PRMRAlphaAPISandbox,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
    contains_raw_sandbox_key,
)


REPORT_DIR = Path("reports/v0521")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_alpha_api_sandbox_v0521.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_alpha_api_sandbox_v0521.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0521.md"


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


def sample_events():
    return [
        {
            "event_id": "evt_alpha_001",
            "entity_id": "acct_alpha_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T12:00:00Z",
            "timestamp_index": 1,
            "event_type": "origin",
            "state_before": "no active review",
            "state_after": "ordinary account activity",
            "signal_type": "origin",
            "status": "historical",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": "ev_alpha_001",
                    "summary": "Synthetic baseline account activity.",
                    "supports": ["ordinary_activity"],
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
        {
            "event_id": "evt_alpha_002",
            "entity_id": "acct_alpha_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T12:05:00Z",
            "timestamp_index": 2,
            "event_type": "current_state",
            "state_before": "ordinary account activity",
            "state_after": "unusual recipient introduced",
            "signal_type": "unusual_recipient",
            "status": "active",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": "ev_alpha_002",
                    "summary": "Synthetic recipient change requires review.",
                    "supports": ["unusual_recipient"],
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
        {
            "event_id": "evt_alpha_003",
            "entity_id": "acct_alpha_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T12:10:00Z",
            "timestamp_index": 3,
            "event_type": "stale_signal",
            "state_before": "old device note active",
            "state_after": "old device note superseded",
            "signal_type": "old_device_note",
            "status": "stale",
            "trust_level": "trusted",
            "evidence": [],
            "counter_evidence": [
                {
                    "evidence_id": "ev_alpha_003",
                    "summary": "Synthetic device note is stale.",
                }
            ],
            "tags": ["synthetic", "controlled_alpha"],
        },
    ]


def public_tests(checks):
    return [
        {
            "name": check["name"].replace("api_key", "access_key"),
            "passed": check["passed"],
        }
        for check in checks
    ]


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.52.1 Alpha API Sandbox",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.52.1  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Functions",
        "",
    ]

    for name in public_report["function_list"]:
        lines.append(f"- {name}")

    lines.extend([
        "",
        "## Boundary",
        "",
        public_report["honest_boundary"],
        "",
        "This remains a local controlled-alpha sandbox, not hosted production infrastructure.",
        "",
    ])

    return "\n".join(lines)


def main():
    print("PRMR V0.52.1 ALPHA API SANDBOX TEST")
    print("-----------------------------------")

    api = PRMRAlphaAPISandbox()
    checks = []

    alpha_key = ALPHA_SANDBOX_KEYS["client_alpha"]
    beta_key = ALPHA_SANDBOX_KEYS["client_beta"]

    base = {
        "client_id": "client_alpha",
        "api_key": alpha_key,
        "vault_id": "alpha_vault",
        "namespace": "default",
        "metadata": {"dataset_type": "synthetic"},
    }
    beta_base = {
        "client_id": "client_beta",
        "api_key": beta_key,
        "vault_id": "beta_vault",
        "namespace": "default",
        "metadata": {"dataset_type": "synthetic"},
    }

    ingest = api.events_ingest({**base, "events": sample_events()})
    add_check(
        checks,
        "valid_api_key_can_ingest_events_into_own_vault_namespace",
        ingest["ok"] is True,
        ingest,
    )

    invalid = api.events_ingest({**base, "api_key": "wrong_key", "events": sample_events()})
    add_check(
        checks,
        "invalid_api_key_is_rejected",
        invalid["ok"] is False and invalid["error"]["code"] == "invalid_key",
        invalid,
    )

    missing = api.events_ingest({**base, "api_key": None, "events": sample_events()})
    add_check(
        checks,
        "missing_api_key_is_rejected",
        missing["ok"] is False and missing["error"]["code"] == "missing_auth",
        missing,
    )

    revoke_api = PRMRAlphaAPISandbox()
    revoke_base = dict(base)
    revoke_result = revoke_api.revoke_key(revoke_base)
    revoked_call = revoke_api.events_ingest({**revoke_base, "events": sample_events()})
    add_check(
        checks,
        "revoked_api_key_is_rejected",
        revoke_result["ok"] is True
        and revoked_call["ok"] is False
        and revoked_call["error"]["code"] == "revoked_key",
        {"revoke_result": revoke_result, "revoked_call": revoked_call},
    )

    rotation = api.rotate_key(base)
    rotated_key = rotation["data"].get("new_api_key") if rotation["ok"] else None
    rotated_base = {**base, "api_key": rotated_key}
    rotated_works = api.events_ingest({**rotated_base, "events": [sample_events()[1]]})
    old_after_rotation = api.events_ingest({**base, "events": [sample_events()[1]]})
    add_check(
        checks,
        "rotated_new_key_works",
        rotation["ok"] is True and rotated_works["ok"] is True,
        {"rotation": rotation, "rotated_works": rotated_works},
    )
    add_check(
        checks,
        "old_rotated_key_no_longer_works",
        old_after_rotation["ok"] is False and old_after_rotation["error"]["code"] == "revoked_key",
        old_after_rotation,
    )

    cross_vault = api.events_ingest({**rotated_base, "vault_id": "beta_vault", "events": sample_events()})
    add_check(
        checks,
        "client_a_cannot_access_client_b_vault",
        cross_vault["ok"] is False and cross_vault["error"]["code"] == "vault_denied",
        cross_vault,
    )

    add_check(
        checks,
        "events_ingest_returns_accepted_event_count",
        ingest["ok"] is True and ingest["data"]["accepted_event_count"] == len(sample_events()),
        ingest,
    )

    packet_result = api.continuity_packet({**rotated_base, "entity_id": "acct_alpha_001"})
    packet = packet_result["data"]["packet"] if packet_result["ok"] else {}
    report_id = packet_result["data"].get("public_report_id") if packet_result["ok"] else None
    add_check(
        checks,
        "continuity_packet_returns_expected_fields",
        packet_result["ok"] is True
        and packet.get("current_state") == "unusual recipient introduced"
        and "unusual_recipient" in packet.get("active_signals", [])
        and "old_device_note" in packet.get("stale_signals", [])
        and len(packet.get("evidence_summary", [])) >= 1
        and bool(packet.get("continuity_summary")),
        packet_result,
    )

    reconstruct = api.memory_reconstruct({**rotated_base, "packet_id": packet.get("packet_id")})
    add_check(
        checks,
        "memory_reconstruct_returns_reconstructable_state",
        reconstruct["ok"] is True
        and reconstruct["data"]["reconstruction_match"] is True
        and reconstruct["data"]["reconstructable_state"]["current_state"] == "unusual recipient introduced",
        reconstruct,
    )

    explanation = api.explain({**rotated_base, "packet_id": packet.get("packet_id"), "audience": "customer_safe"})
    explanation_payload = explanation["data"]["explanation"] if explanation["ok"] else {}
    add_check(
        checks,
        "explain_returns_public_safe_explanation_packet",
        explanation["ok"] is True
        and explanation_payload.get("sensitive_details_allowed") is False
        and "final conclusion" in explanation_payload.get("review_boundary", ""),
        explanation,
    )

    action = api.least_harm_action({**rotated_base, "packet_id": packet.get("packet_id")})
    add_check(
        checks,
        "least_harm_action_returns_non_punitive_action_boundary",
        action["ok"] is True
        and action["data"]["recommended_action"] in action["data"]["allowed_actions"]
        and action["data"]["not_final_decision"] is True
        and action["data"]["recommended_action"] != "automatic_account_closure",
        action,
    )

    report = api.get_report({**rotated_base, "report_id": report_id})
    beta_report_attempt = api.get_report({**beta_base, "report_id": report_id})
    add_check(
        checks,
        "get_report_returns_public_report_only_for_owner",
        report["ok"] is True
        and report["data"]["report"]["public_safe"] is True
        and "packet_debug" not in report["data"]["report"]
        and beta_report_attempt["ok"] is False
        and beta_report_attempt["error"]["code"] == "vault_denied",
        {"owner_report": report, "beta_report_attempt": beta_report_attempt},
    )

    usage = api.get_usage(rotated_base)
    add_check(
        checks,
        "get_usage_returns_per_client_usage_count",
        usage["ok"] is True
        and usage["data"]["usage"]["client_id"] == "client_alpha"
        and usage["data"]["usage"]["events_ingested"] >= len(sample_events()),
        usage,
    )

    public_objects = {
        "report": report["data"]["report"] if report["ok"] else {},
        "explanation": explanation_payload,
        "action": action["data"] if action["ok"] else {},
    }
    public_forbidden = scan_public_forbidden_terms(public_objects)
    public_unsafe = scan_unsafe_public_language(public_objects)
    public_raw_keys = contains_raw_sandbox_key(public_objects)

    add_check(
        checks,
        "public_report_contains_no_restricted_packet_terms",
        len(public_forbidden) == 0 and public_raw_keys is False,
        {"forbidden_terms_found": public_forbidden, "raw_key_found": public_raw_keys},
    )
    add_check(
        checks,
        "public_report_avoids_punitive_or_certain_guilt_wording",
        len(public_unsafe) == 0,
        {"unsafe_language_found": public_unsafe},
    )

    restricted_report = api.restricted_debug_reports.get(report_id, {})
    add_check(
        checks,
        "restricted_report_contains_debug_details",
        restricted_report.get("public_safe") is False
        and "packet_debug" in restricted_report
        and "event_debug" in restricted_report,
        restricted_report,
    )

    boundary = ingest["data"].get("alpha_boundary", {}) if ingest["ok"] else {}
    add_check(
        checks,
        "alpha_boundary_is_present",
        boundary.get("controlled_alpha_only") is True
        and boundary.get("hosted_production_api") is False
        and boundary.get("no_bank_certification") is True
        and boundary.get("no_real_sensitive_data_unless_approved") is True,
        boundary,
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    function_list = [
        "events_ingest",
        "continuity_packet",
        "memory_reconstruct",
        "explain",
        "least_harm_action",
        "get_report",
        "get_usage",
        "rotate_key",
        "revoke_key",
    ]

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.52.1",
        "report_type": "alpha_api_sandbox",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "function_list": function_list,
        "checks": public_tests(checks),
        "honest_boundary": (
            "V0.52.1 is a local controlled-alpha API sandbox. It is not hosted production infrastructure, "
            "does not include billing, does not certify bank or compliance use, and accepts synthetic or approved data only."
        ),
        "v0522_integrity_audit_gaps": [
            "Recompute sandbox outputs from raw events in a separate audit.",
            "Probe public outputs for raw rotated-key leakage.",
            "Verify usage counters across failed and successful calls.",
            "Add tamper checks for report ownership and packet ownership.",
        ],
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "debug": {
            "ingest": ingest,
            "packet_result": packet_result,
            "reconstruct": reconstruct,
            "explanation": explanation,
            "action": action,
            "usage": usage,
            "restricted_report": restricted_report,
        },
        "restricted_note": "Restricted report includes full sandbox call details for internal validation.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(build_scorecard(public_report), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)


if __name__ == "__main__":
    main()
