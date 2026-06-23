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

REPORT_DIR = Path("reports/v047")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_fraud_explainability_report_v047.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_fraud_explainability_report_v047.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v047.md"


SAFE_LABELS = {
    "normal_user": "No fraud escalation indicated",
    "possible_scam_victim": "Possible scam victim support needed",
    "possible_coercion_or_pressured_mule": "Possible coercion or pressured mule risk",
    "possible_account_takeover_victim": "Possible account takeover victim",
    "fraud_investigation_needed": "Investigation-worthy risk pattern",
    "likely_false_positive": "Likely false positive",
    "needs_human_review": "Needs human review",
}

UNSAFE_WORDS = [
    "criminal",
    "fraudster",
    "ban user",
    "punish",
    "guilty",
    "definitely fraud",
    "close account immediately",
    "blacklist",
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
    return [word for word in UNSAFE_WORDS if word in text]


def evidence_from_packet(packet):
    supporting = []
    weakening = []
    human_review = []

    current = packet.get("current_state", "")
    risk_signals = packet.get("risk_signals", [])
    human_context = packet.get("human_context", [])
    counter_evidence = packet.get("counter_evidence", [])
    review_action = packet.get("review_action", "")

    if current:
        supporting.append(f"Current state: {current}")

    for risk in risk_signals:
        supporting.append(f"Risk signal: {risk}")

    for context in human_context:
        human_review.append(f"Human context: {context}")

    for counter in counter_evidence:
        weakening.append(f"Counter-evidence: {counter}")

    if review_action:
        human_review.append(f"Recommended review action: {review_action}")

    return supporting, weakening, human_review


def explain_case(account_id, label, packet):
    safe_label = SAFE_LABELS.get(label, "Needs human review")
    supporting, weakening, human_review = evidence_from_packet(packet)

    continuity_change = packet.get("current_state") or "No clear current-state change captured."

    if label == "normal_user":
        reviewer_action = "No fraud escalation indicated. Continue ordinary monitoring."
        harm_warning = "Avoid unnecessary intervention where continuity remains stable."
        confidence = "medium"
    elif label == "possible_scam_victim":
        reviewer_action = "Route to scam-victim support review before any punitive action."
        harm_warning = "Customer may be a victim being coached or pressured. Protect before blaming."
        confidence = "high"
    elif label == "possible_coercion_or_pressured_mule":
        reviewer_action = "Escalate to human safeguarding review for coercion or pressure indicators."
        harm_warning = "Do not flatten the person into a malicious label without checking pressure and exploitation."
        confidence = "high"
    elif label == "possible_account_takeover_victim":
        reviewer_action = "Protect account access and verify with customer before attributing intent."
        harm_warning = "The account holder may be a victim of credential or device compromise."
        confidence = "high"
    elif label == "likely_false_positive":
        reviewer_action = "Avoid punitive label. Verify benign explanation and supporting documentation."
        harm_warning = "Large or unusual transactions can be legitimate life events."
        confidence = "high"
    elif label == "fraud_investigation_needed":
        reviewer_action = "Flag for investigation review. Require human decision before punitive action."
        harm_warning = "Investigation-worthy pattern detected, but final judgment requires human review."
        confidence = "medium"
    else:
        reviewer_action = "Send to human review due to insufficient certainty."
        harm_warning = "Do not punish where evidence is incomplete."
        confidence = "low"

    return {
        "account_id": account_id,
        "safe_label": safe_label,
        "continuity_change": continuity_change,
        "supporting_evidence": supporting,
        "weakening_or_contextual_evidence": weakening,
        "human_review_evidence": human_review,
        "recommended_action": reviewer_action,
        "harm_reduction_warning": harm_warning,
        "confidence": confidence,
        "final_decision_boundary": "This packet supports human review. It does not make a final punitive decision.",
    }


def main():
    print("PRMR V0.47 FRAUD EXPLAINABILITY REPORT")
    print("--------------------------------------")

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    runner = load_module(V046_RUNNER, "run_fraud_baseline_war_v046")
    engine = PRMRMemoryCore()

    checks = []
    accounts = dataset["accounts"]

    engine_input = [
        {
            "name": account["account_id"],
            "description": "Synthetic fraud explainability timeline",
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

    explanations = {}
    classifications = {}
    packets = {}
    reconstruction_results = {}

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

        packet = runner.build_prmr_packet(reconstructed)
        label = runner.classify_prmr(packet)

        packets[account_id] = packet
        classifications[account_id] = label
        explanations[account_id] = explain_case(account_id, label, packet)

    required_sections = [
        "safe_label",
        "continuity_change",
        "supporting_evidence",
        "weakening_or_contextual_evidence",
        "human_review_evidence",
        "recommended_action",
        "harm_reduction_warning",
        "confidence",
        "final_decision_boundary",
    ]

    section_coverage = {
        account_id: all(section in explanation for section in required_sections)
        for account_id, explanation in explanations.items()
    }

    evidence_coverage = {
        account_id: (
            len(explanation["supporting_evidence"]) > 0
            and len(explanation["human_review_evidence"]) > 0
        )
        for account_id, explanation in explanations.items()
    }

    weakening_context_cases = [
        "acct_malicious_001",
        "acct_false_positive_001",
        "acct_normal_001",
    ]

    weakening_coverage = {
        account_id: len(explanations[account_id]["weakening_or_contextual_evidence"]) > 0
        for account_id in weakening_context_cases
    }

    human_review_boundary = {
        account_id: "does not make a final punitive decision" in explanations[account_id]["final_decision_boundary"].lower()
        for account_id in explanations
    }

    unsafe_language = unsafe_language_scan(explanations)

    add_check(
        checks,
        "all_timelines_reconstruct_exactly",
        all(reconstruction_results.values()),
        reconstruction_results
    )

    add_check(
        checks,
        "explanations_created_for_all_accounts",
        set(explanations.keys()) == {account["account_id"] for account in accounts},
        {"explanation_count": len(explanations), "account_count": len(accounts)}
    )

    add_check(
        checks,
        "all_explanations_have_required_sections",
        all(section_coverage.values()),
        section_coverage
    )

    add_check(
        checks,
        "explanations_include_supporting_and_review_evidence",
        all(evidence_coverage.values()),
        evidence_coverage
    )

    add_check(
        checks,
        "explanations_include_context_or_counter_evidence_where_needed",
        all(weakening_coverage.values()),
        weakening_coverage
    )

    add_check(
        checks,
        "explanations_avoid_punitive_or_certain_guilt_language",
        len(unsafe_language) == 0,
        {"unsafe_language_found": unsafe_language}
    )

    add_check(
        checks,
        "all_explanations_preserve_human_review_boundary",
        all(human_review_boundary.values()),
        human_review_boundary
    )

    public_preview = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.47",
        "report_type": "fraud_explainability_report",
        "public_safe": True,
        "synthetic_only": True,
        "explanation_count": len(explanations),
        "safe_labels": {
            account_id: explanation["safe_label"]
            for account_id, explanation in explanations.items()
        },
        "confidence_summary": {
            account_id: explanation["confidence"]
            for account_id, explanation in explanations.items()
        },
        "human_review_boundary_preserved": all(human_review_boundary.values()),
        "unsafe_language_found": unsafe_language,
    }

    public_forbidden = public_safety_scan(public_preview)

    add_check(
        checks,
        "public_report_preview_exposes_no_private_labels_or_engine_internals",
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
            "V0.47 generates synthetic bank-safe explainability packets that summarize continuity changes, supporting evidence, contextual evidence, recommended human-review action, and harm-reduction warnings without making final punitive decisions."
        ),
        "honest_boundary": (
            "Synthetic internal explainability evidence only. Not bank certification, not legal advice, not compliance approval, and not production fraud deployment proof."
        ),
        "next_phase": "V0.47.1 Explainability Integrity Audit",
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_packets": packets,
        "private_classifications": classifications,
        "private_explanations": explanations,
        "private_reconstruction_results": reconstruction_results,
        "private_checks": checks,
        "protected_note": "Private report includes full synthetic explanations and packets. Do not publish."
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.47 Fraud Explainability Report",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.47  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Safe Claim",
        "",
        public_report["safe_claim"],
        "",
        "## Honest Boundary",
        "",
        public_report["honest_boundary"],
        "",
        "## Safe Labels",
        "",
    ]

    for account_id, label in public_preview["safe_labels"].items():
        md.append(f"- **{account_id}**: {label}")

    md.extend([
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
        "This test moves from detection to explanation.",
        "",
        "The point is not only to flag risk, but to explain risk safely enough for human review.",
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
    print("Safe labels:")
    for account_id, label in public_preview["safe_labels"].items():
        print("-", account_id + ":", label)
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
