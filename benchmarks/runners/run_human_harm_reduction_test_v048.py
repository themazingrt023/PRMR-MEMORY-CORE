import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")
V046_RUNNER = Path("benchmarks/runners/run_fraud_baseline_war_v046.py")
V047_RUNNER = Path("benchmarks/runners/run_fraud_explainability_report_v047.py")

REPORT_DIR = Path("reports/v048")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_human_harm_reduction_test_v048.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_human_harm_reduction_test_v048.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v048.md"


HARM_SAFE_EXPECTED_ACTIONS = {
    "acct_normal_001": "no_escalation",
    "acct_scam_victim_001": "protect_and_support",
    "acct_pressured_mule_001": "safeguarding_review",
    "acct_ato_001": "protect_account_access",
    "acct_malicious_001": "investigation_review",
    "acct_false_positive_001": "avoid_punitive_label",
}

HARM_SENSITIVE_ACCOUNTS = [
    "acct_normal_001",
    "acct_scam_victim_001",
    "acct_pressured_mule_001",
    "acct_ato_001",
    "acct_false_positive_001",
]

UNSAFE_DECISION_WORDS = [
    "criminal",
    "fraudster",
    "guilty",
    "blacklist",
    "ban user",
    "close account immediately",
    "definitely fraud",
]


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def safe_lower(value):
    return str(value or "").lower()


def public_safety_scan(obj):
    text = json.dumps(obj, sort_keys=True).lower()

    forbidden = [
        "truth_private",
        "private_truth",
        "private_packets",
        "private_classifications",
        "private_explanations",
        "private_checks",
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "protected_note",
        "raw_api_key",
        "api_key",
    ]

    return [term for term in forbidden if term in text]


def unsafe_language_scan(obj):
    text = json.dumps(obj, sort_keys=True).lower()
    return [word for word in UNSAFE_DECISION_WORDS if word in text]


def map_prmr_label_to_harm_action(label):
    if label == "normal_user":
        return "no_escalation"

    if label == "possible_scam_victim":
        return "protect_and_support"

    if label == "possible_coercion_or_pressured_mule":
        return "safeguarding_review"

    if label == "possible_account_takeover_victim":
        return "protect_account_access"

    if label == "likely_false_positive":
        return "avoid_punitive_label"

    if label == "fraud_investigation_needed":
        return "investigation_review"

    return "human_review_required"


def map_rule_label_to_harm_action(label):
    """
    This simulates what a simple punitive baseline tends to do:
    if it sees a fraud-like label, it escalates as investigation/punitive risk
    without differentiating victim/support/safeguarding pathways.
    """
    if label == "normal_user":
        return "no_escalation"

    if label == "fraud_investigation_needed":
        return "investigation_review"

    return "human_review_required"


def action_is_harm_safe(account_id, action):
    expected = HARM_SAFE_EXPECTED_ACTIONS[account_id]
    return action == expected


def action_is_not_punitive_for_harm_sensitive(account_id, action):
    if account_id not in HARM_SENSITIVE_ACCOUNTS:
        return True

    punitive_actions = {
        "investigation_review",
        "punitive_escalation",
        "close_or_restrict_without_review",
    }

    return action not in punitive_actions


def build_harm_packet(account_id, label, action, explanation):
    return {
        "account_id": account_id,
        "safe_label": explanation.get("safe_label"),
        "harm_safe_action": action,
        "why_not_flattened": explanation.get("harm_reduction_warning"),
        "human_review_boundary": explanation.get("final_decision_boundary"),
        "recommended_action": explanation.get("recommended_action"),
        "confidence": explanation.get("confidence"),
    }


def main():
    print("PRMR V0.48 HUMAN HARM REDUCTION TEST")
    print("------------------------------------")

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    fraud_runner = load_module(V046_RUNNER, "run_fraud_baseline_war_v046")
    explain_runner = load_module(V047_RUNNER, "run_fraud_explainability_report_v047")

    engine = PRMRMemoryCore()
    checks = []
    accounts = dataset["accounts"]

    engine_input = [
        {
            "name": account["account_id"],
            "description": "Synthetic human harm reduction timeline",
            "rows": [
                {
                    **row,
                    "account_id": account["account_id"],
                    "case_family": account["case_family"],
                }
                for row in account["rows"]
            ],
        }
        for account in accounts
    ]

    engine_result = engine.run(engine_input)

    reconstruction_results = {}
    prmr_labels = {}
    prmr_actions = {}
    rule_labels = {}
    rule_actions = {}
    harm_packets = {}
    explanations = {}

    for account, result in zip(accounts, engine_result["results"]):
        account_id = account["account_id"]

        original_rows = [
            {
                **row,
                "account_id": account["account_id"],
                "case_family": account["case_family"],
            }
            for row in account["rows"]
        ]

        reconstructed = result["decision"]["reconstructed_rows"]
        reconstruction_results[account_id] = reconstructed == original_rows

        prmr_packet = fraud_runner.build_prmr_packet(reconstructed)
        prmr_label = fraud_runner.classify_prmr(prmr_packet)
        prmr_action = map_prmr_label_to_harm_action(prmr_label)

        rule_label = fraud_runner.classify_rule_engine(original_rows)
        rule_action = map_rule_label_to_harm_action(rule_label)

        explanation = explain_runner.explain_case(account_id, prmr_label, prmr_packet)

        prmr_labels[account_id] = prmr_label
        prmr_actions[account_id] = prmr_action
        rule_labels[account_id] = rule_label
        rule_actions[account_id] = rule_action
        explanations[account_id] = explanation
        harm_packets[account_id] = build_harm_packet(account_id, prmr_label, prmr_action, explanation)

    prmr_harm_safe_matches = {
        account_id: action_is_harm_safe(account_id, action)
        for account_id, action in prmr_actions.items()
    }

    prmr_non_punitive_harm_sensitive = {
        account_id: action_is_not_punitive_for_harm_sensitive(account_id, action)
        for account_id, action in prmr_actions.items()
    }

    rule_non_punitive_harm_sensitive = {
        account_id: action_is_not_punitive_for_harm_sensitive(account_id, action)
        for account_id, action in rule_actions.items()
    }

    rule_flattens_count = sum(
        1 for account_id, safe in rule_non_punitive_harm_sensitive.items()
        if account_id in HARM_SENSITIVE_ACCOUNTS and safe is False
    )

    explanation_boundary = {
        account_id: "does not make a final punitive decision" in safe_lower(packet.get("human_review_boundary"))
        for account_id, packet in harm_packets.items()
    }

    harm_warning_present = {
        account_id: bool(packet.get("why_not_flattened"))
        for account_id, packet in harm_packets.items()
    }

    unsafe_language = unsafe_language_scan(harm_packets)

    add_check(
        checks,
        "all_timelines_reconstruct_exactly",
        all(reconstruction_results.values()),
        reconstruction_results
    )

    add_check(
        checks,
        "prmr_assigns_expected_harm_safe_actions",
        all(prmr_harm_safe_matches.values()),
        {
            "expected_actions": HARM_SAFE_EXPECTED_ACTIONS,
            "prmr_actions": prmr_actions,
            "matches": prmr_harm_safe_matches,
        }
    )

    add_check(
        checks,
        "prmr_does_not_punitively_flatten_harm_sensitive_cases",
        all(prmr_non_punitive_harm_sensitive.values()),
        {
            "prmr_actions": prmr_actions,
            "non_punitive_matches": prmr_non_punitive_harm_sensitive,
        }
    )

    add_check(
        checks,
        "rule_engine_flattens_at_least_one_harm_sensitive_case",
        rule_flattens_count >= 1,
        {
            "rule_labels": rule_labels,
            "rule_actions": rule_actions,
            "flattened_harm_sensitive_count": rule_flattens_count,
        }
    )

    add_check(
        checks,
        "malicious_case_still_gets_investigation_review",
        prmr_actions.get("acct_malicious_001") == "investigation_review",
        {
            "label": prmr_labels.get("acct_malicious_001"),
            "action": prmr_actions.get("acct_malicious_001"),
        }
    )

    add_check(
        checks,
        "false_positive_gets_avoid_punitive_label_action",
        prmr_actions.get("acct_false_positive_001") == "avoid_punitive_label",
        {
            "label": prmr_labels.get("acct_false_positive_001"),
            "action": prmr_actions.get("acct_false_positive_001"),
        }
    )

    add_check(
        checks,
        "victim_and_coercion_cases_get_support_or_safeguarding_actions",
        prmr_actions.get("acct_scam_victim_001") == "protect_and_support"
        and prmr_actions.get("acct_pressured_mule_001") == "safeguarding_review"
        and prmr_actions.get("acct_ato_001") == "protect_account_access",
        {
            "scam_victim_action": prmr_actions.get("acct_scam_victim_001"),
            "pressured_mule_action": prmr_actions.get("acct_pressured_mule_001"),
            "account_takeover_action": prmr_actions.get("acct_ato_001"),
        }
    )

    add_check(
        checks,
        "harm_packets_preserve_human_review_boundary",
        all(explanation_boundary.values()),
        explanation_boundary
    )

    add_check(
        checks,
        "harm_packets_include_harm_reduction_warning",
        all(harm_warning_present.values()),
        harm_warning_present
    )

    add_check(
        checks,
        "harm_packets_avoid_punitive_or_certain_guilt_language",
        len(unsafe_language) == 0,
        {"unsafe_language_found": unsafe_language}
    )

    public_preview = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.48",
        "report_type": "human_harm_reduction_test",
        "public_safe": True,
        "synthetic_only": True,
        "account_count": len(accounts),
        "prmr_harm_safe_action_rate": round(
            sum(1 for ok in prmr_harm_safe_matches.values() if ok) / len(prmr_harm_safe_matches) * 100,
            2
        ),
        "prmr_non_punitive_harm_sensitive_rate": round(
            sum(1 for ok in prmr_non_punitive_harm_sensitive.values() if ok) / len(prmr_non_punitive_harm_sensitive) * 100,
            2
        ),
        "rule_engine_flattened_harm_sensitive_count": rule_flattens_count,
        "safe_action_summary": prmr_actions,
        "human_review_boundary_preserved": all(explanation_boundary.values()),
    }

    public_forbidden = public_safety_scan(public_preview)

    add_check(
        checks,
        "public_report_preview_exposes_no_hidden_labels_or_engine_terms",
        len(public_forbidden) == 0,
        {"forbidden_terms_found": public_forbidden}
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    public_report = {
        **public_preview,
        "timestamp": datetime.now().isoformat(),
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "result": result,
        "checks": [
            {"name": check["name"], "passed": check["passed"]}
            for check in checks
        ],
        "safe_claim": (
            "V0.48 tests whether PRMR can convert synthetic fraud-continuity classifications into harm-aware actions: support victims, safeguard pressured people, protect account-takeover victims, avoid punitive false-positive handling, and still route investigation-worthy patterns to human review."
        ),
        "honest_boundary": (
            "Synthetic internal harm-reduction evidence only. Not bank certification, not legal advice, not compliance approval, and not production fraud deployment proof."
        ),
        "next_phase": "V0.48.1 Human Harm Integrity Audit",
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_prmr_labels": prmr_labels,
        "private_rule_labels": rule_labels,
        "private_rule_actions": rule_actions,
        "private_harm_packets": harm_packets,
        "private_explanations": explanations,
        "private_reconstruction_results": reconstruction_results,
        "private_checks": checks,
        "protected_note": "Private report includes labels, actions, explanations, and harm packets. Do not publish."
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.48 Human Harm Reduction Test",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.48  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Harm Reduction Metrics",
        "",
        f"- PRMR harm-safe action rate: **{public_preview['prmr_harm_safe_action_rate']}%**",
        f"- PRMR non-punitive harm-sensitive rate: **{public_preview['prmr_non_punitive_harm_sensitive_rate']}%**",
        f"- Rule engine flattened harm-sensitive count: **{rule_flattens_count}**",
        "",
        "## Safe Action Summary",
        "",
    ]

    for account_id, action in prmr_actions.items():
        md.append(f"- **{account_id}**: {action}")

    md.extend([
        "",
        "## Safe Claim",
        "",
        public_report["safe_claim"],
        "",
        "## Honest Boundary",
        "",
        public_report["honest_boundary"],
        "",
        "## Checks",
        "",
    ])

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This test checks whether PRMR can reduce human harm, not merely detect suspicious patterns.",
        "",
        "The aim is to preserve enough continuity to avoid treating victims, pressured people, account-takeover victims, and false positives as one flat category.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    SCORECARD_PATH.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("Result:", result)
    print()
    print("Harm metrics:")
    print("- prmr_harm_safe_action_rate:", str(public_preview["prmr_harm_safe_action_rate"]) + "%")
    print("- prmr_non_punitive_harm_sensitive_rate:", str(public_preview["prmr_non_punitive_harm_sensitive_rate"]) + "%")
    print("- rule_engine_flattened_harm_sensitive_count:", rule_flattens_count)
    print()
    print("Safe actions:")
    for account_id, action in prmr_actions.items():
        print("-", account_id + ":", action)
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
