import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    ALPHA_SANDBOX_KEYS,
    PRMRAlphaAPISandbox,
    contains_raw_sandbox_key,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


REPORT_DIR = Path("reports/v053")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_local_live_demo_v053.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_local_live_demo_v053.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v053.md"


def synthetic_demo_events():
    return [
        {
            "event_id": "evt_demo_001",
            "entity_id": "acct_demo_walkthrough_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T14:00:00Z",
            "timestamp_index": 1,
            "event_type": "origin",
            "state_before": "no active review",
            "state_after": "ordinary account activity",
            "signal_type": "origin",
            "status": "historical",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": "ev_demo_001",
                    "summary": "Synthetic baseline activity for local walkthrough.",
                    "supports": ["ordinary_activity"],
                }
            ],
            "tags": ["synthetic", "local_demo"],
        },
        {
            "event_id": "evt_demo_002",
            "entity_id": "acct_demo_walkthrough_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T14:06:00Z",
            "timestamp_index": 2,
            "event_type": "state_change",
            "state_before": "ordinary account activity",
            "state_after": "new recipient and urgent invoice note introduced",
            "signal_type": "recipient_change",
            "status": "active",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": "ev_demo_002",
                    "summary": "Synthetic new payee and invoice note arrived together.",
                    "supports": ["recipient_change", "invoice_note_change"],
                }
            ],
            "tags": ["synthetic", "messy_input", "local_demo"],
        },
        {
            "event_id": "evt_demo_003",
            "entity_id": "acct_demo_walkthrough_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T14:09:00Z",
            "timestamp_index": 3,
            "event_type": "current_state",
            "state_before": "new recipient and urgent invoice note introduced",
            "state_after": "recipient change awaiting confirmation",
            "signal_type": "confirmation_needed",
            "status": "active",
            "trust_level": "trusted",
            "evidence": [
                {
                    "evidence_id": "ev_demo_003",
                    "summary": "Synthetic customer confirmation is not present yet.",
                    "supports": ["confirmation_needed"],
                }
            ],
            "tags": ["synthetic", "messy_input", "local_demo"],
        },
        {
            "event_id": "evt_demo_004",
            "entity_id": "acct_demo_walkthrough_001",
            "entity_type": "account",
            "timestamp": "2026-06-20T14:12:00Z",
            "timestamp_index": 4,
            "event_type": "stale_signal",
            "state_before": "old device note active",
            "state_after": "old device note superseded",
            "signal_type": "old_device_note",
            "status": "stale",
            "trust_level": "trusted",
            "evidence": [],
            "counter_evidence": [
                {
                    "evidence_id": "ev_demo_004",
                    "summary": "Synthetic device note was superseded by a later trusted event.",
                }
            ],
            "tags": ["synthetic", "messy_input", "local_demo"],
        },
    ]


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


def public_check_list(checks):
    return [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]


def public_boundary():
    return {
        "evidence_scope": "local sandbox evidence",
        "data_scope": "synthetic data only",
        "public_safe_evidence": True,
        "external_validation": "not claimed",
        "production_readiness": "not claimed",
        "hosted_service": "not claimed",
        "banking_approval": "not claimed",
        "compliance_approval": "not claimed",
        "external_security_approval": "not claimed",
        "final_decisions": "not allowed",
    }


def alpha_base_request():
    return {
        "client_id": "client_alpha",
        "api_key": ALPHA_SANDBOX_KEYS["client_alpha"],
        "vault_id": "alpha_vault",
        "namespace": "default",
        "metadata": {"dataset_type": "synthetic"},
    }


def beta_base_request():
    return {
        "client_id": "client_beta",
        "api_key": ALPHA_SANDBOX_KEYS["client_beta"],
        "vault_id": "beta_vault",
        "namespace": "default",
        "metadata": {"dataset_type": "synthetic"},
    }


def print_section(title, lines=None):
    print()
    print(title)
    print("-" * len(title))
    for line in lines or []:
        print(line)


def summarize_events(events):
    return [
        {
            "event_id": event["event_id"],
            "time": event["timestamp"],
            "type": event["event_type"],
            "from": event["state_before"],
            "to": event["state_after"],
            "status": event["status"],
            "signal": event["signal_type"],
        }
        for event in events
    ]


def build_public_report(checks, demo_summary, public_explanation, action_label, denial_outcome):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.53",
        "report_type": "local_live_demo",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "demo_steps_completed": demo_summary,
        "synthetic_only_boundary": True,
        "public_safe_explanation": public_explanation,
        "least_harm_action_label": action_label,
        "denial_path_outcome": denial_outcome,
        "checks": public_check_list(checks),
        "boundary": public_boundary(),
        "honest_boundary_statement": (
            "V0.53 is a local controlled-alpha demo harness using synthetic data only. "
            "It does not provide hosted infrastructure, production readiness, banking approval, "
            "compliance approval, legal approval, external security approval, or real-world validation."
        ),
        "remaining_gaps": [
            "Add a lightweight visual walkthrough wrapper for screen recordings.",
            "Add more synthetic scenarios for multiple namespaces and event rhythms.",
            "Add a resettable fixture mode for repeated live presentations.",
            "Keep hosted API, billing, and external validation work out of this local demo milestone.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.53 Local Live Demo Harness",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.53  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Demo Flow",
        "",
    ]

    for step in public_report["demo_steps_completed"]:
        lines.append(f"- {step}")

    lines.extend([
        "",
        "## Public Output",
        "",
        f"- Least-harm action: {public_report['least_harm_action_label']}",
        f"- Denial path: {public_report['denial_path_outcome']}",
        "",
        "## Checks",
        "",
    ])

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {check['name']}: {status}")

    lines.extend([
        "",
        "## Boundary",
        "",
        public_report["honest_boundary_statement"],
        "",
        "## Remaining Gaps",
        "",
    ])

    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")

    return "\n".join(lines)


def public_artifacts_are_clean(public_report, scorecard_text):
    scan_target = {
        "public_report": public_report,
        "scorecard": scorecard_text,
    }
    return {
        "restricted_terms": scan_public_forbidden_terms(scan_target),
        "unsafe_terms": scan_unsafe_public_language(scan_target),
        "contains_raw_keys": contains_raw_sandbox_key(scan_target),
    }


def main():
    print("PRMR Memory Core V0.53 Local Demo")
    print("=================================")

    api = PRMRAlphaAPISandbox()
    checks = []
    trace = {}
    events = synthetic_demo_events()
    alpha_base = alpha_base_request()
    beta_base = beta_base_request()
    entity_id = events[0]["entity_id"]

    print_section(
        "Step 1: Synthetic events",
        [
            "Client initialized: client_alpha / alpha_vault / default namespace.",
            f"Synthetic event count: {len(events)}",
            "Messy inputs include a recipient change, an invoice note change, missing confirmation, and one stale device note.",
        ],
    )

    ingest = api.events_ingest({**alpha_base, "events": events})
    print_section(
        "Step 2: Ingest events",
        [
            f"Accepted event count: {ingest.get('data', {}).get('accepted_event_count')}",
            "Access key accepted for the owner's vault and namespace.",
        ],
    )

    packet_result = api.continuity_packet({**alpha_base, "entity_id": entity_id})
    packet = packet_result.get("data", {}).get("packet", {}) if packet_result.get("ok") else {}
    print_section(
        "Step 3: Generate continuity packet",
        [
            f"Packet created: {bool(packet)}",
            f"Current state: {packet.get('current_state')}",
            f"Active signals: {', '.join(packet.get('active_signals', []))}",
            f"Stale signals: {', '.join(packet.get('stale_signals', []))}",
        ],
    )

    reconstruct = api.memory_reconstruct({**alpha_base, "packet_id": packet.get("packet_id")})
    reconstructed_state = reconstruct.get("data", {}).get("reconstructable_state", {})
    print_section(
        "Step 4: Reconstruct current state",
        [
            f"Reconstruction exists: {bool(reconstructed_state)}",
            f"Reconstructed current state: {reconstructed_state.get('current_state')}",
        ],
    )

    explanation = api.explain({
        **alpha_base,
        "packet_id": packet.get("packet_id"),
        "audience": "customer_safe",
    })
    public_explanation = explanation.get("data", {}).get("explanation", {})
    print_section(
        "Step 5: Public-safe explanation",
        [
            public_explanation.get("summary", "No explanation generated."),
            public_explanation.get("customer_next_step", "No next step generated."),
            public_explanation.get("review_boundary", "No review boundary generated."),
        ],
    )

    action = api.least_harm_action({**alpha_base, "packet_id": packet.get("packet_id")})
    action_data = action.get("data", {})
    action_label = action_data.get("recommended_action")
    print_section(
        "Step 6: Least-harm action",
        [
            f"Recommended action: {action_label}",
            f"Human review required: {action_data.get('human_review_required')}",
            action_data.get("safety_boundary", "No safety boundary generated."),
        ],
    )

    report_id = packet_result.get("data", {}).get("public_report_id")
    owner_report = api.get_report({**alpha_base, "report_id": report_id})
    print_section(
        "Step 7: Owner report access",
        [
            f"Owner report fetch ok: {owner_report.get('ok')}",
            f"Report id present: {bool(report_id)}",
        ],
    )

    wrong_key = api.get_report({
        **alpha_base,
        "api_key": "wrong_local_demo_key",
        "report_id": report_id,
    })
    cross_client = api.get_report({
        **beta_base,
        "report_id": report_id,
    })
    denial_outcome = (
        f"wrong key -> {wrong_key.get('error', {}).get('code')}; "
        f"cross-client -> {cross_client.get('error', {}).get('code')}"
    )
    print_section(
        "Step 8: Tamper/cross-client denial",
        [
            denial_outcome,
            "Unauthorized access did not return the owner report.",
        ],
    )

    print_section(
        "Step 9: Boundary",
        [
            "Local controlled-alpha sandbox only.",
            "Synthetic data only.",
            "No hosted infrastructure, production readiness, approval, certification, or real-world validation is claimed.",
        ],
    )

    demo_steps = [
        "client initialized for local sandbox walkthrough",
        "synthetic messy events prepared",
        "events ingested into owner vault and namespace",
        "continuity packet generated",
        "memory state reconstructed",
        "public-safe explanation generated",
        "least-harm action returned",
        "owner public report fetched",
        "wrong-key and cross-client denial demonstrated",
        "alpha boundary printed and reported",
    ]

    add_check(
        checks,
        "demo_completed_all_required_steps",
        len(demo_steps) == 10
        and ingest.get("ok") is True
        and packet_result.get("ok") is True
        and reconstruct.get("ok") is True
        and explanation.get("ok") is True
        and action.get("ok") is True
        and owner_report.get("ok") is True,
    )
    add_check(checks, "continuity_packet_exists", bool(packet.get("packet_id")))
    add_check(checks, "reconstruct_output_exists", bool(reconstructed_state))
    add_check(checks, "explanation_output_exists", bool(public_explanation))
    add_check(checks, "least_harm_action_output_exists", bool(action_label))
    add_check(checks, "owner_report_access_works", owner_report.get("ok") is True)
    add_check(
        checks,
        "wrong_key_and_cross_client_denial_work",
        wrong_key.get("ok") is False
        and wrong_key.get("error", {}).get("code") == "invalid_key"
        and cross_client.get("ok") is False
        and cross_client.get("error", {}).get("code") == "vault_denied",
        {
            "wrong_key_error": wrong_key.get("error"),
            "cross_client_error": cross_client.get("error"),
        },
    )
    add_check(
        checks,
        "alpha_boundary_is_present",
        ingest.get("data", {}).get("alpha_boundary", {}).get("controlled_alpha_only") is True
        and ingest.get("data", {}).get("alpha_boundary", {}).get("hosted_production_api") is False
        and ingest.get("data", {}).get("alpha_boundary", {}).get("no_final_punitive_decisions") is True
        and public_boundary()["production_readiness"] == "not claimed",
    )

    public_report = build_public_report(
        checks,
        demo_steps,
        {
            "summary": public_explanation.get("summary"),
            "customer_next_step": public_explanation.get("customer_next_step"),
            "review_boundary": public_explanation.get("review_boundary"),
            "sensitive_details_allowed": public_explanation.get("sensitive_details_allowed"),
        },
        action_label,
        denial_outcome,
    )
    scorecard_text = build_scorecard(public_report)
    clean_scan = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "restricted_terms_absent_from_public_output",
        not clean_scan["restricted_terms"] and not clean_scan["contains_raw_keys"],
        clean_scan,
    )
    add_check(
        checks,
        "punitive_wording_absent_from_public_output",
        not clean_scan["unsafe_terms"],
        clean_scan,
    )

    public_report = build_public_report(
        checks,
        demo_steps,
        {
            "summary": public_explanation.get("summary"),
            "customer_next_step": public_explanation.get("customer_next_step"),
            "review_boundary": public_explanation.get("review_boundary"),
            "sensitive_details_allowed": public_explanation.get("sensitive_details_allowed"),
        },
        action_label,
        denial_outcome,
    )
    scorecard_text = build_scorecard(public_report)
    final_clean_scan = public_artifacts_are_clean(public_report, scorecard_text)
    if (
        final_clean_scan["restricted_terms"]
        or final_clean_scan["unsafe_terms"]
        or final_clean_scan["contains_raw_keys"]
    ):
        add_check(
            checks,
            "final_public_artifact_hygiene_holds",
            False,
            final_clean_scan,
        )
        public_report = build_public_report(
            checks,
            demo_steps,
            {
                "summary": public_explanation.get("summary"),
                "customer_next_step": public_explanation.get("customer_next_step"),
                "review_boundary": public_explanation.get("review_boundary"),
                "sensitive_details_allowed": public_explanation.get("sensitive_details_allowed"),
            },
            action_label,
            denial_outcome,
        )
        scorecard_text = build_scorecard(public_report)

    trace.update({
        "synthetic_events": summarize_events(events),
        "ingest": ingest,
        "packet_result": packet_result,
        "reconstruct": reconstruct,
        "explanation": explanation,
        "least_harm_action": action,
        "owner_report": owner_report,
        "wrong_key_denial": wrong_key,
        "cross_client_denial": cross_client,
        "public_hygiene_scan": final_clean_scan,
        "sandbox_state_counts": {
            "events_scopes": len(api.events),
            "packet_count": len(api.packets),
            "public_report_count": len(api.public_reports),
            "usage_scope_count": len(api.usage),
        },
    })

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    public_report["result"] = result
    public_report["passed_checks"] = passed_count
    public_report["total_checks"] = total_checks
    public_report["all_checks_passed"] = passed_count == total_checks
    scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "debug_trace": deepcopy(trace),
        "restricted_note": "Restricted demo report includes call outcomes and sandbox trace details for internal validation.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print()
    print("Self-check")
    print("----------")
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if result != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
