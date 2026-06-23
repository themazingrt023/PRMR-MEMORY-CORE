import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import (
    ALPHA_SANDBOX_KEYS,
    PRMRAlphaAPISandbox,
    contains_raw_sandbox_key,
    scan_public_forbidden_terms,
    scan_unsafe_public_language,
)


VERSION = "0.53.1"
FIXTURE_TIMESTAMP = "2026-06-20T15:00:00Z"

REPORT_DIR = Path("reports/v0531")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_demo_replay_pack_v0531.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_demo_replay_pack_v0531.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v0531.md"
SCRIPT_PATH = Path("docs/demo_script_v0531.md")


CLAIM_TERMS = [
    "hosted api",
    "hosted production api",
    "production ready",
    "production readiness",
    "production certified",
    "bank approved",
    "bank approval",
    "compliance approved",
    "compliance approval",
    "legal approved",
    "legal approval",
    "external security certified",
    "external security certification",
    "real-world validated",
    "real-world validation",
]


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    })


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


def fixture_scenarios():
    return [
        {
            "scenario_id": "scenario_ai_agent_memory",
            "name": "AI agent memory continuity",
            "entity_id": "agent_memory_demo_001",
            "entity_type": "agent_memory",
            "events": [
                event(
                    "ai_001",
                    "agent_memory_demo_001",
                    "agent_memory",
                    1,
                    "origin",
                    "new workspace session",
                    "project preference recorded",
                    "preference_origin",
                    "historical",
                    "Synthetic agent starts with a known project preference.",
                    ["preference_origin"],
                ),
                event(
                    "ai_002",
                    "agent_memory_demo_001",
                    "agent_memory",
                    2,
                    "state_change",
                    "project preference recorded",
                    "preference carried into refreshed context",
                    "preference_recalled",
                    "active",
                    "Synthetic continuity preserves a remembered setup preference.",
                    ["preference_recalled"],
                ),
                event(
                    "ai_003",
                    "agent_memory_demo_001",
                    "agent_memory",
                    3,
                    "current_state",
                    "preference carried into refreshed context",
                    "agent can continue with current project preference",
                    "continuity_ready",
                    "active",
                    "Synthetic current state is available for the next turn.",
                    ["continuity_ready"],
                ),
                stale_event(
                    "ai_004",
                    "agent_memory_demo_001",
                    "agent_memory",
                    4,
                    "old setup note superseded",
                    "outdated setup note archived",
                    "outdated_setup_note",
                    "Synthetic older setup note is no longer current.",
                ),
            ],
        },
        {
            "scenario_id": "scenario_support_history",
            "name": "Customer support/user-history continuity",
            "entity_id": "support_user_demo_001",
            "entity_type": "support_user",
            "events": [
                event(
                    "support_001",
                    "support_user_demo_001",
                    "support_user",
                    1,
                    "origin",
                    "no active support issue",
                    "support history available",
                    "history_origin",
                    "historical",
                    "Synthetic support history begins with prior context available.",
                    ["history_origin"],
                ),
                event(
                    "support_002",
                    "support_user_demo_001",
                    "support_user",
                    2,
                    "state_change",
                    "support history available",
                    "delivery issue repeated after prior contact",
                    "repeat_contact",
                    "active",
                    "Synthetic user returned with a related support issue.",
                    ["repeat_contact"],
                ),
                event(
                    "support_003",
                    "support_user_demo_001",
                    "support_user",
                    3,
                    "current_state",
                    "delivery issue repeated after prior contact",
                    "support follow-up awaiting confirmation",
                    "response_needed",
                    "active",
                    "Synthetic support case needs a confirmation step.",
                    ["response_needed"],
                ),
                stale_event(
                    "support_004",
                    "support_user_demo_001",
                    "support_user",
                    4,
                    "old shipping estimate active",
                    "old shipping estimate superseded",
                    "old_shipping_estimate",
                    "Synthetic older estimate was replaced by later context.",
                ),
            ],
        },
        {
            "scenario_id": "scenario_risk_continuity",
            "name": "Fraud/risk continuity sandbox",
            "entity_id": "risk_demo_account_001",
            "entity_type": "account",
            "events": [
                event(
                    "risk_001",
                    "risk_demo_account_001",
                    "account",
                    1,
                    "origin",
                    "ordinary account activity",
                    "ordinary account activity",
                    "baseline_activity",
                    "historical",
                    "Synthetic baseline activity is available.",
                    ["baseline_activity"],
                ),
                event(
                    "risk_002",
                    "risk_demo_account_001",
                    "account",
                    2,
                    "state_change",
                    "ordinary account activity",
                    "new recipient and invoice note introduced",
                    "recipient_change",
                    "active",
                    "Synthetic recipient and invoice note changed together.",
                    ["recipient_change", "invoice_note_change"],
                ),
                event(
                    "risk_003",
                    "risk_demo_account_001",
                    "account",
                    3,
                    "current_state",
                    "new recipient and invoice note introduced",
                    "recipient change awaiting confirmation",
                    "confirmation_needed",
                    "active",
                    "Synthetic confirmation has not been observed yet.",
                    ["confirmation_needed"],
                ),
                stale_event(
                    "risk_004",
                    "risk_demo_account_001",
                    "account",
                    4,
                    "old device note active",
                    "old device note superseded",
                    "old_device_note",
                    "Synthetic device note is stale.",
                ),
            ],
        },
    ]


def event(prefix, entity_id, entity_type, index, event_type, state_before, state_after, signal_type, status, summary, supports):
    return {
        "event_id": f"evt_v0531_{prefix}",
        "entity_id": entity_id,
        "entity_type": entity_type,
        "timestamp": f"2026-06-20T15:{index:02d}:00Z",
        "timestamp_index": index,
        "event_type": event_type,
        "state_before": state_before,
        "state_after": state_after,
        "signal_type": signal_type,
        "status": status,
        "trust_level": "trusted",
        "evidence": [
            {
                "evidence_id": f"ev_v0531_{prefix}",
                "summary": summary,
                "supports": supports,
            }
        ],
        "tags": ["synthetic", "replay_fixture"],
    }


def stale_event(prefix, entity_id, entity_type, index, state_before, state_after, signal_type, summary):
    return {
        "event_id": f"evt_v0531_{prefix}",
        "entity_id": entity_id,
        "entity_type": entity_type,
        "timestamp": f"2026-06-20T15:{index:02d}:00Z",
        "timestamp_index": index,
        "event_type": "stale_signal",
        "state_before": state_before,
        "state_after": state_after,
        "signal_type": signal_type,
        "status": "stale",
        "trust_level": "trusted",
        "evidence": [],
        "counter_evidence": [
            {
                "evidence_id": f"ev_v0531_{prefix}",
                "summary": summary,
            }
        ],
        "tags": ["synthetic", "replay_fixture"],
    }


def print_title():
    print("PRMR Memory Core V0.53.1 Demo Replay Pack")
    print("==========================================")
    print("Deterministic local sandbox replay using synthetic fixtures only.")


def print_scenario_walkthrough(result):
    print()
    print(result["scenario_name"])
    print("-" * len(result["scenario_name"]))
    print("Raw events summary:")
    for row in result["raw_events_summary"]:
        print(f"  - {row['event_id']}: {row['from']} -> {row['to']} [{row['status']}]")
    print("Continuity packet summary:")
    print(f"  Current state: {result['packet_summary']['current_state']}")
    print(f"  Active signals: {', '.join(result['packet_summary']['active_signals'])}")
    print(f"  Stale signals: {', '.join(result['packet_summary']['stale_signals'])}")
    print("Reconstructed state:")
    print(f"  {result['reconstructed_state'].get('current_state')}")
    print("Explanation:")
    print(f"  {result['public_explanation'].get('summary')}")
    print(f"  {result['public_explanation'].get('customer_next_step')}")
    print("Least-harm action:")
    print(f"  {result['action_label']}")
    print("Report access result:")
    print(f"  owner -> {result['owner_report_ok']}")
    print("Denial/tamper result:")
    print(f"  {result['denial_outcome']}")
    print("Alpha boundary:")
    print("  local controlled-alpha sandbox, synthetic data only, no external validation claimed")


def summarize_events(events):
    return [
        {
            "event_id": event["event_id"],
            "from": event["state_before"],
            "to": event["state_after"],
            "status": event["status"],
            "signal": event["signal_type"],
        }
        for event in events
    ]


def run_scenario(api, scenario):
    alpha_base = alpha_base_request()
    beta_base = beta_base_request()

    ingest = api.events_ingest({**alpha_base, "events": scenario["events"]})
    packet_result = api.continuity_packet({**alpha_base, "entity_id": scenario["entity_id"]})
    packet = packet_result.get("data", {}).get("packet", {}) if packet_result.get("ok") else {}
    reconstruct = api.memory_reconstruct({**alpha_base, "packet_id": packet.get("packet_id")})
    explanation = api.explain({
        **alpha_base,
        "packet_id": packet.get("packet_id"),
        "audience": "customer_safe",
    })
    action = api.least_harm_action({**alpha_base, "packet_id": packet.get("packet_id")})
    report_id = packet_result.get("data", {}).get("public_report_id")
    owner_report = api.get_report({**alpha_base, "report_id": report_id})
    wrong_key = api.get_report({
        **alpha_base,
        "api_key": "wrong_replay_demo_key",
        "report_id": report_id,
    })
    cross_client = api.get_report({**beta_base, "report_id": report_id})

    public_explanation = explanation.get("data", {}).get("explanation", {})
    action_data = action.get("data", {})
    reconstructed_state = reconstruct.get("data", {}).get("reconstructable_state", {})
    denial_outcome = (
        f"wrong key -> {wrong_key.get('error', {}).get('code')}; "
        f"cross-client -> {cross_client.get('error', {}).get('code')}"
    )

    return {
        "scenario_id": scenario["scenario_id"],
        "scenario_name": scenario["name"],
        "raw_events_summary": summarize_events(scenario["events"]),
        "packet_summary": {
            "current_state": packet.get("current_state"),
            "active_signals": packet.get("active_signals", []),
            "stale_signals": packet.get("stale_signals", []),
            "human_review_required": packet.get("human_review_required"),
        },
        "reconstructed_state": reconstructed_state,
        "public_explanation": {
            "summary": public_explanation.get("summary"),
            "customer_next_step": public_explanation.get("customer_next_step"),
            "review_boundary": public_explanation.get("review_boundary"),
            "sensitive_details_allowed": public_explanation.get("sensitive_details_allowed"),
        },
        "action_label": action_data.get("recommended_action"),
        "owner_report_ok": owner_report.get("ok") is True,
        "denial_outcome": denial_outcome,
        "checks": {
            "ingest_ok": ingest.get("ok") is True,
            "packet_ok": packet_result.get("ok") is True and bool(packet.get("packet_id")),
            "reconstruct_ok": reconstruct.get("ok") is True and bool(reconstructed_state),
            "explanation_ok": explanation.get("ok") is True and bool(public_explanation),
            "action_ok": action.get("ok") is True and bool(action_data.get("recommended_action")),
            "owner_report_ok": owner_report.get("ok") is True,
            "denial_ok": (
                wrong_key.get("ok") is False
                and wrong_key.get("error", {}).get("code") == "invalid_key"
                and cross_client.get("ok") is False
                and cross_client.get("error", {}).get("code") == "vault_denied"
            ),
        },
        "debug_trace": {
            "ingest": ingest,
            "packet_result": packet_result,
            "reconstruct": reconstruct,
            "explanation": explanation,
            "action": action,
            "owner_report": owner_report,
            "wrong_key": wrong_key,
            "cross_client": cross_client,
        },
    }


def public_boundary():
    return {
        "evidence_scope": "local sandbox evidence",
        "data_scope": "synthetic fixture data only",
        "resettable_fixture_mode": True,
        "external_validation": "not claimed",
        "production_readiness": "not claimed",
        "hosted_service": "not claimed",
        "banking_approval": "not claimed",
        "compliance_approval": "not claimed",
        "legal_approval": "not claimed",
        "external_security_approval": "not claimed",
        "final_decisions": "not allowed",
    }


def public_checks(checks):
    return [
        {
            "name": check["name"],
            "passed": check["passed"],
        }
        for check in checks
    ]


def build_public_report(checks, scenario_results, v053_status):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "demo_replay_pack",
        "public_safe": True,
        "timestamp": FIXTURE_TIMESTAMP,
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "resettable_fixture_mode": True,
        "scenarios_completed": [item["scenario_name"] for item in scenario_results],
        "demo_outputs_summary": [
            {
                "scenario": item["scenario_name"],
                "current_state": item["packet_summary"]["current_state"],
                "active_signals": item["packet_summary"]["active_signals"],
                "stale_signals": item["packet_summary"]["stale_signals"],
                "public_explanation": item["public_explanation"],
                "least_harm_action": item["action_label"],
                "report_access": "owner access allowed" if item["owner_report_ok"] else "owner access failed",
                "denial_path": item["denial_outcome"],
            }
            for item in scenario_results
        ],
        "checks": public_checks(checks),
        "v053_original_demo_status": v053_status,
        "alpha_boundary": public_boundary(),
        "honest_boundary_statement": (
            "V0.53.1 is a repeatable local demo replay pack using deterministic synthetic fixtures. "
            "It stays local and synthetic, with no deployment readiness, banking sign-off, "
            "regulatory sign-off, legal sign-off, third-party security sign-off, or field validation asserted."
        ),
        "remaining_v054_landing_page_gaps": [
            "Create a public-facing landing page that stays aligned with internal evidence boundaries.",
            "Add screenshots or short clips from the local replay without exposing restricted traces.",
            "Keep network deployment, billing, and external validation claims out unless separately proven.",
            "Add a visual scenario selector if the landing page includes a live local demo mode.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.53.1 Demo Replay Pack",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.53.1  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Scenarios",
        "",
    ]

    for scenario in public_report["demo_outputs_summary"]:
        lines.append(f"- {scenario['scenario']}: {scenario['current_state']}")

    lines.extend([
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
        "## V0.54 Landing Page Gaps",
        "",
    ])

    for gap in public_report["remaining_v054_landing_page_gaps"]:
        lines.append(f"- {gap}")

    return "\n".join(lines)


def build_demo_script_doc():
    return "\n".join([
        "# PRMR V0.53.1 Demo Replay Script",
        "",
        "Use this talk track for founder walkthroughs, pitch recordings, and early buyer conversations.",
        "",
        "## Before Running",
        "",
        "Say: This is a local controlled-alpha replay using deterministic synthetic fixtures. The goal is to show how PRMR preserves continuity across events and produces review-safe outputs.",
        "",
        "Say: The replay stays local and synthetic. It does not assert deployment readiness, banking sign-off, regulatory sign-off, legal sign-off, third-party security sign-off, or field validation.",
        "",
        "## Step Meanings",
        "",
        "1. Scenario name: tells the viewer which continuity problem is being shown.",
        "2. Raw events summary: shows messy changes over time before PRMR organizes them.",
        "3. Continuity packet summary: shows the current state, active signals, and stale signals.",
        "4. Reconstructed state: shows that the sandbox can rebuild the current memory state from stored events.",
        "5. Explanation: shows public-safe wording that avoids sensitive internals and final conclusions.",
        "6. Least-harm action: shows a proportionate next step for review support.",
        "7. Report access result: shows that the owner can fetch the public report.",
        "8. Denial/tamper result: shows that wrong-key and cross-client access attempts are rejected.",
        "9. Alpha boundary: reminds the viewer this is synthetic local evidence only.",
        "",
        "## Scenario Notes",
        "",
        "- AI agent memory continuity: useful for explaining persistent project context without overclaiming general AI reliability.",
        "- Customer support/user-history continuity: useful for explaining user-history continuity and safer follow-up.",
        "- Fraud/risk continuity sandbox: useful for explaining review support without accusation or final decisions.",
        "",
        "## What Not To Claim",
        "",
        "- Do not claim an online service.",
        "- Do not claim deployment readiness.",
        "- Do not claim banking, regulatory, legal, third-party security, or field validation.",
        "- Do not claim the system makes final punitive decisions.",
        "- Do not use real sensitive data in this replay.",
        "",
        "## Closing Line",
        "",
        "Say: This replay is intentionally narrow: synthetic local evidence, public-safe outputs, and clear security boundaries. The next step is choosing which scenario deserves a richer visual walkthrough.",
        "",
    ])


def text_contains_unqualified_claim(text, claim):
    lower = text.lower()
    start = 0
    while True:
        index = lower.find(claim, start)
        if index == -1:
            return False
        window_before = lower[max(0, index - 28):index]
        window_after = lower[index:index + len(claim) + 24]
        if not any(marker in window_before for marker in ["not ", "no ", "without ", "does not ", "do not "]):
            if "not claimed" not in window_after and "claim" not in window_after:
                return True
        start = index + len(claim)


def public_artifacts_are_clean(public_report, scorecard_text, demo_script_text):
    scan_target = {
        "public_report": public_report,
        "scorecard": scorecard_text,
        "demo_script": demo_script_text,
    }
    text = json.dumps(scan_target, sort_keys=True)
    return {
        "restricted_terms": scan_public_forbidden_terms(scan_target),
        "unsafe_terms": scan_unsafe_public_language(scan_target),
        "contains_raw_keys": contains_raw_sandbox_key(scan_target),
        "unqualified_claims": [
            claim
            for claim in CLAIM_TERMS
            if text_contains_unqualified_claim(text, claim)
        ],
    }


def run_v053_original_demo():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "examples/demo_v053_local_live_demo.py"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def main():
    print_title()

    api = PRMRAlphaAPISandbox()
    checks = []
    scenarios = fixture_scenarios()
    scenario_results = []

    for scenario in scenarios:
        result = run_scenario(api, scenario)
        scenario_results.append(result)
        print_scenario_walkthrough(result)

    v053_run = run_v053_original_demo()
    v053_stdout = v053_run.stdout
    v053_still_passes = (
        v053_run.returncode == 0
        and "Passed checks: 10/10" in v053_stdout
        and "Result: PASS" in v053_stdout
    )

    add_check(
        checks,
        "all_three_scenarios_completed",
        len(scenario_results) == 3
        and all(item["checks"]["ingest_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "each_scenario_has_continuity_packet",
        all(item["checks"]["packet_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "each_scenario_has_reconstruct_output",
        all(item["checks"]["reconstruct_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "each_scenario_has_explanation_output",
        all(item["checks"]["explanation_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "each_scenario_has_least_harm_action_output",
        all(item["checks"]["action_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "owner_report_access_works_for_each_scenario",
        all(item["checks"]["owner_report_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "denial_tamper_path_works",
        all(item["checks"]["denial_ok"] for item in scenario_results),
    )
    add_check(
        checks,
        "alpha_boundary_present",
        public_boundary()["resettable_fixture_mode"] is True
        and public_boundary()["data_scope"] == "synthetic fixture data only"
        and public_boundary()["production_readiness"] == "not claimed",
    )
    add_check(
        checks,
        "v053_original_demo_still_passes",
        v053_still_passes,
        {
            "returncode": v053_run.returncode,
            "stdout_tail": v053_stdout.splitlines()[-8:],
            "stderr_tail": v053_run.stderr.splitlines()[-8:],
        },
    )

    demo_script_text = build_demo_script_doc()
    public_report = build_public_report(
        checks,
        scenario_results,
        "PASS" if v053_still_passes else "NEEDS_WORK",
    )
    scorecard_text = build_scorecard(public_report)
    clean_scan = public_artifacts_are_clean(public_report, scorecard_text, demo_script_text)
    add_check(
        checks,
        "public_report_is_clean",
        not clean_scan["restricted_terms"]
        and not clean_scan["contains_raw_keys"]
        and not clean_scan["unqualified_claims"],
        clean_scan,
    )
    add_check(
        checks,
        "public_wording_hygiene_holds",
        not clean_scan["unsafe_terms"],
        clean_scan,
    )

    public_report = build_public_report(
        checks,
        scenario_results,
        "PASS" if v053_still_passes else "NEEDS_WORK",
    )
    scorecard_text = build_scorecard(public_report)
    final_clean_scan = public_artifacts_are_clean(public_report, scorecard_text, demo_script_text)
    if (
        final_clean_scan["restricted_terms"]
        or final_clean_scan["unsafe_terms"]
        or final_clean_scan["contains_raw_keys"]
        or final_clean_scan["unqualified_claims"]
    ):
        add_check(
            checks,
            "final_public_artifact_hygiene_holds",
            False,
            final_clean_scan,
        )
        public_report = build_public_report(
            checks,
            scenario_results,
            "PASS" if v053_still_passes else "NEEDS_WORK",
        )
        scorecard_text = build_scorecard(public_report)

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
        "fixture_ids": [scenario["scenario_id"] for scenario in scenarios],
        "detailed_scenario_traces": [
            {
                "scenario_id": item["scenario_id"],
                "scenario_name": item["scenario_name"],
                "debug_trace": deepcopy(item["debug_trace"]),
            }
            for item in scenario_results
        ],
        "v053_original_demo": {
            "returncode": v053_run.returncode,
            "stdout": v053_run.stdout,
            "stderr": v053_run.stderr,
        },
        "restricted_note": "Restricted replay report includes fixture IDs and detailed call outcomes for internal validation.",
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")
    SCRIPT_PATH.write_text(demo_script_text, encoding="utf-8")

    print()
    print("Alpha boundary")
    print("--------------")
    print("Local controlled-alpha replay only; synthetic fixtures only; no hosted, production, approval, certification, or real-world validation claim.")

    print()
    print("Self-check")
    print("----------")
    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print("V0.53 original demo:", "PASS" if v053_still_passes else "NEEDS_WORK")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)
    print(SCRIPT_PATH)

    if result != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
