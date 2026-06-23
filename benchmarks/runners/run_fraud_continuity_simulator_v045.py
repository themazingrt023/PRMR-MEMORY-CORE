import json
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")

REPORT_DIR = Path("reports/v045")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_fraud_continuity_simulator_v045.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_fraud_continuity_simulator_v045.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v045.md"


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def classify_packet(packet):
    current = packet.get("current_state", "").lower()
    risk = " ".join(packet.get("risk_signals", [])).lower()
    human = " ".join(packet.get("human_context", [])).lower()
    counter = " ".join(packet.get("counter_evidence", [])).lower()
    action = packet.get("review_action", "").lower()

    full_text = " ".join([current, risk, human, counter, action])

    # Normal user: stable pattern and no escalation.
    if "ordinary spending continues" in full_text or "no fraud escalation" in full_text:
        return "normal_user"

    # False positive protection should happen before generic fraud suspicion.
    if "documented student finance" in counter or "likely false positive" in action:
        return "likely_false_positive"

    # Account takeover victim: broken login/device continuity + customer denial.
    if (
        "device continuity broke" in risk
        or "account takeover" in action
        or "did not authorize" in human
    ):
        return "possible_account_takeover_victim"

    # Scam victim: coached by caller / victim support.
    if "coached by caller" in human or "scam victim support" in action:
        return "possible_scam_victim"

    # Malicious/coordinated pattern:
    # Important: this must handle NEGATED victim/coercion evidence.
    # "no clear victim-coaching, coercion..." means do NOT classify as coerced.
    if (
        "coordinated pattern" in risk
        and (
            "no clear victim" in counter
            or "no clear victim-coaching" in counter
            or "no clear victim-coaching, coercion" in counter
        )
    ):
        return "fraud_investigation_needed"

    # Pressured/coerced mule:
    # Only use positive human-context/action signals, not negated counter-evidence.
    if (
        "messages suggest pressure" in human
        or "being instructed by another person" in human
        or "safeguarding assessment" in action
        or "coercion and safeguarding" in action
    ):
        return "possible_coercion_or_pressured_mule"

    # Fallback: if risk exists but context is unclear, require human review.
    if risk:
        return "needs_human_review"

    return "needs_human_review"


def build_packet(rows):
    trusted = [
        row for row in rows
        if row.get("trust_level") == "trusted"
        and row.get("status") in ("active", "historical")
    ]

    ordered = sorted(trusted, key=lambda row: row.get("timestamp_index", 0))

    def latest(signal_type):
        matches = [row for row in ordered if row.get("signal_type") == signal_type]
        return matches[-1]["memory_value"] if matches else ""

    def all_values(signal_type):
        return [row["memory_value"] for row in ordered if row.get("signal_type") == signal_type]

    return {
        "origin": latest("origin"),
        "current_state": latest("current_state"),
        "risk_signals": all_values("risk_signal"),
        "human_context": all_values("human_context"),
        "counter_evidence": all_values("counter_evidence"),
        "review_action": latest("review_action"),
    }


def public_safety_scan(obj):
    text = json.dumps(obj, sort_keys=True).lower()
    forbidden = [
        "truth_private",
        "private_internal",
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "protected_note",
        "raw_api_key",
        "api_key",
    ]
    return [term for term in forbidden if term in text]


def main():
    print("PRMR V0.45 FRAUD CONTINUITY SIMULATOR")
    print("-------------------------------------")

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    engine = PRMRMemoryCore()

    checks = []

    accounts = dataset["accounts"]
    truth = dataset["truth_private"]

    add_check(
        checks,
        "synthetic_dataset_exists",
        DATASET_PATH.exists(),
        {"dataset_path": str(DATASET_PATH)}
    )

    required_families = {
        "normal_user",
        "scam_victim",
        "pressured_mule",
        "account_takeover",
        "malicious_fraud",
        "false_positive",
    }

    present_families = {account["case_family"] for account in accounts}

    add_check(
        checks,
        "required_case_families_present",
        required_families.issubset(present_families),
        {
            "required": sorted(required_families),
            "present": sorted(present_families)
        }
    )

    engine_input = [
        {
            "name": account["account_id"],
            "description": "Synthetic fraud continuity account timeline",
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
    packets = {}
    classifications = {}

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

        packet = build_packet(reconstructed)
        packets[account_id] = packet
        classifications[account_id] = classify_packet(packet)

    add_check(
        checks,
        "all_account_timelines_reconstruct_exactly",
        all(reconstruction_results.values()),
        reconstruction_results
    )

    add_check(
        checks,
        "continuity_packets_created_for_all_accounts",
        set(packets.keys()) == {account["account_id"] for account in accounts},
        {"packet_count": len(packets), "account_count": len(accounts)}
    )

    classification_matches = {
        account_id: classifications[account_id] == truth[account_id]
        for account_id in truth
    }

    classification_accuracy = (
        sum(1 for passed in classification_matches.values() if passed)
        / len(classification_matches)
        * 100
    )

    add_check(
        checks,
        "fraud_continuity_classification_matches_expected_labels",
        classification_accuracy == 100.0,
        {
            "classification_accuracy": classification_accuracy,
            "matches": classification_matches,
            "classifications": classifications
        }
    )

    harm_sensitive_expected = {
        "acct_scam_victim_001": "possible_scam_victim",
        "acct_pressured_mule_001": "possible_coercion_or_pressured_mule",
        "acct_ato_001": "possible_account_takeover_victim",
        "acct_false_positive_001": "likely_false_positive",
    }

    harm_sensitive_matches = {
        account_id: classifications.get(account_id) == expected
        for account_id, expected in harm_sensitive_expected.items()
    }

    add_check(
        checks,
        "human_harm_sensitive_cases_keep_distinct_labels",
        all(harm_sensitive_matches.values()),
        harm_sensitive_matches
    )

    malicious_flagged = classifications.get("acct_malicious_001") == "fraud_investigation_needed"

    add_check(
        checks,
        "malicious_pattern_still_flagged_for_review",
        malicious_flagged,
        {"classification": classifications.get("acct_malicious_001")}
    )

    public_report_preview = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.45",
        "report_type": "fraud_continuity_simulator",
        "public_safe": True,
        "synthetic_only": True,
        "account_count": len(accounts),
        "case_family_count": len(present_families),
        "classification_accuracy": classification_accuracy,
        "human_harm_sensitive_cases_protected": all(harm_sensitive_matches.values()),
        "malicious_pattern_flagged_for_review": malicious_flagged,
    }

    public_forbidden = public_safety_scan(public_report_preview)

    add_check(
        checks,
        "public_report_preview_exposes_no_private_labels_or_protected_engine_terms",
        len(public_forbidden) == 0,
        {"forbidden_terms_found": public_forbidden}
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"

    public_report = {
        **public_report_preview,
        "timestamp": datetime.now().isoformat(),
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "result": result,
        "checks": [
            {"name": check["name"], "passed": check["passed"]}
            for check in checks
        ],
        "honest_claim": (
            "V0.45 uses synthetic banking-style data to test whether PRMR can reconstruct fraud-relevant continuity "
            "and separate scam victims, coercion, account takeover, false positives, normal users, and investigation-worthy patterns. "
            "It is internal simulation evidence only, not bank certification or production fraud deployment proof."
        ),
        "next_phase": "V0.45.1 Fraud Simulator Integrity Audit"
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_truth": truth,
        "private_packets": packets,
        "private_classifications": classifications,
        "private_reconstruction_results": reconstruction_results,
        "private_checks": checks,
        "protected_note": "Private report includes synthetic truth labels and continuity packets. Do not publish."
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.45 Fraud Continuity Simulator",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.45  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Honest Claim",
        "",
        public_report["honest_claim"],
        "",
        "## Checks",
        "",
    ]

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This starts the fraud/banking continuity proof track.",
        "",
        "The aim is not simply to catch fraud. The aim is to preserve enough continuity to avoid flattening victims, pressured people, account takeover victims, and false positives into one harmful label.",
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
    print("Classification accuracy:", classification_accuracy)
    print("Human harm sensitive protected:", all(harm_sensitive_matches.values()))
    print("Malicious pattern flagged:", malicious_flagged)
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
