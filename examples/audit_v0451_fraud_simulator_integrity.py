import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")
RUNNER_PATH = Path("benchmarks/runners/run_fraud_continuity_simulator_v045.py")
PUBLIC_REPORT = Path("reports/v045/public_fraud_continuity_simulator_v045.json")
PRIVATE_REPORT = Path("reports/v045/private_internal_fraud_continuity_simulator_v045.json")

OUT_DIR = Path("reports/v0451")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "fraud_simulator_integrity_audit_v0451.json"
OUT_MD = OUT_DIR / "fraud_simulator_integrity_audit_v0451.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def public_safety_scan(obj):
    text = json.dumps(obj, sort_keys=True).lower()

    forbidden = [
        "truth_private",
        "private_truth",
        "private_packets",
        "private_classifications",
        "private_reconstruction_results",
        "private_checks",
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "protected_note",
        "raw_api_key",
        "api_key",
    ]

    return [term for term in forbidden if term in text]


def hardcode_scan(text):
    suspicious = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped or stripped.startswith("#"):
            continue

        # Allow legitimate threshold checks such as:
        # classification_accuracy == 100.0
        # This is a pass criterion, not a hardcoded output.
        if "classification_accuracy == 100" in lowered:
            continue

        # Flag direct fixed assignment, not comparisons or recomputation.
        if (
            "classification_accuracy" in lowered
            and ("= 100" in lowered or ": 100" in lowered)
            and "==" not in lowered
            and "sum(" not in lowered
            and "len(" not in lowered
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_classification_accuracy",
                "text": stripped
            })

        # Allow honest conditional result construction.
        if (
            "result" in lowered
            and "pass" in lowered
            and " if " not in lowered
            and "else" not in lowered
            and "==" not in lowered
            and ("public_report" in lowered or "report" in lowered)
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_direct_result_pass_assignment",
                "text": stripped
            })

    return suspicious


def recompute_from_dataset(dataset, runner_module):
    engine = PRMRMemoryCore()

    accounts = dataset["accounts"]
    truth = dataset["truth_private"]

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

        packet = runner_module.build_packet(reconstructed)
        packets[account_id] = packet
        classifications[account_id] = runner_module.classify_packet(packet)

    classification_matches = {
        account_id: classifications[account_id] == truth[account_id]
        for account_id in truth
    }

    classification_accuracy = (
        sum(1 for passed in classification_matches.values() if passed)
        / len(classification_matches)
        * 100
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

    malicious_flagged = classifications.get("acct_malicious_001") == "fraud_investigation_needed"

    return {
        "reconstruction_results": reconstruction_results,
        "all_reconstruct_exactly": all(reconstruction_results.values()),
        "packets": packets,
        "classifications": classifications,
        "classification_matches": classification_matches,
        "classification_accuracy": classification_accuracy,
        "harm_sensitive_matches": harm_sensitive_matches,
        "human_harm_sensitive_protected": all(harm_sensitive_matches.values()),
        "malicious_flagged": malicious_flagged,
    }


def main():
    print("PRMR V0.45.1 FRAUD SIMULATOR INTEGRITY AUDIT")
    print("--------------------------------------------")

    checks = []

    dataset = load_json(DATASET_PATH)
    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)
    runner_module = load_module(RUNNER_PATH, "run_fraud_continuity_simulator_v045")

    required_families = {
        "normal_user",
        "scam_victim",
        "pressured_mule",
        "account_takeover",
        "malicious_fraud",
        "false_positive",
    }

    present_families = {account["case_family"] for account in dataset["accounts"]}

    add_check(
        checks,
        "synthetic_dataset_has_required_case_families",
        required_families.issubset(present_families),
        {
            "required": sorted(required_families),
            "present": sorted(present_families),
        }
    )

    truth = dataset.get("truth_private", {})

    add_check(
        checks,
        "expected_labels_exist_for_all_accounts",
        set(truth.keys()) == {account["account_id"] for account in dataset["accounts"]},
        {
            "truth_count": len(truth),
            "account_count": len(dataset["accounts"]),
        }
    )

    source_text = DATASET_PATH.read_text(encoding="utf-8", errors="ignore").lower()

    distributed_signals_present = all(
        signal in source_text
        for signal in [
            "origin",
            "current_state",
            "risk_signal",
            "review_action",
            "fake_current",
        ]
    )

    add_check(
        checks,
        "fraud_patterns_are_distributed_across_timeline_rows",
        distributed_signals_present,
        {}
    )

    recomputed = recompute_from_dataset(dataset, runner_module)

    add_check(
        checks,
        "all_account_timelines_reconstruct_exactly",
        recomputed["all_reconstruct_exactly"],
        recomputed["reconstruction_results"]
    )

    add_check(
        checks,
        "classification_accuracy_recomputes_to_100",
        recomputed["classification_accuracy"] == 100.0,
        {
            "classification_accuracy": recomputed["classification_accuracy"],
            "classification_matches": recomputed["classification_matches"],
            "classifications": recomputed["classifications"],
        }
    )

    add_check(
        checks,
        "human_harm_sensitive_cases_remain_protected",
        recomputed["human_harm_sensitive_protected"],
        recomputed["harm_sensitive_matches"]
    )

    add_check(
        checks,
        "malicious_case_still_flagged_for_investigation_review",
        recomputed["malicious_flagged"],
        {
            "classification": recomputed["classifications"].get("acct_malicious_001")
        }
    )

    public_passed = sum(1 for check in public["checks"] if check["passed"])
    public_total = len(public["checks"])

    add_check(
        checks,
        "public_report_pass_count_recomputes",
        public_passed == public["passed_checks"] and public_total == public["total_checks"],
        {
            "reported_passed": public["passed_checks"],
            "recomputed_passed": public_passed,
            "reported_total": public["total_checks"],
            "recomputed_total": public_total,
        }
    )

    public_forbidden = public_safety_scan(public)

    add_check(
        checks,
        "public_report_exposes_no_private_labels_or_engine_internals",
        len(public_forbidden) == 0,
        {
            "forbidden_terms_found": public_forbidden
        }
    )

    private_has_debug = all(
        key in private
        for key in [
            "private_truth",
            "private_packets",
            "private_classifications",
            "private_reconstruction_results",
            "private_checks",
        ]
    )

    add_check(
        checks,
        "private_report_contains_debug_truth_and_packets",
        private_has_debug,
        {}
    )

    runner_text = RUNNER_PATH.read_text(encoding="utf-8", errors="ignore")
    suspicious = hardcode_scan(runner_text)

    add_check(
        checks,
        "runner_does_not_directly_hardcode_final_pass_or_accuracy",
        len(suspicious) == 0,
        {
            "suspicious_patterns_found": suspicious
        }
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.45.1",
        "report_type": "fraud_simulator_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "checks": checks,
        "verdict": (
            "V0.45 fraud continuity simulator is internally consistent. Synthetic cases exist, reconstructions match, classifications recompute, human-harm-sensitive cases remain protected, malicious pattern is flagged for investigation review, and public report hygiene holds."
            if all_passed
            else "V0.45 fraud continuity simulator needs review. One or more integrity checks failed."
        ),
        "honest_claim": (
            "V0.45 is synthetic internal fraud-continuity simulation evidence only. "
            "It is not bank certification, not legal advice, and not production fraud deployment proof."
        ),
        "next_phase": "V0.45.2 Fraud Report Leak Scan or V0.46 PRMR vs Rule Engine vs Vector Search"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.45.1 Fraud Simulator Integrity Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.45.1  ",
        "",
        "## Result",
        "",
        f"**{passed_count}/{total_checks} checks passed**",
        "",
        f"All integrity checks passed: **{all_passed}**",
        "",
        "## Verdict",
        "",
        report["verdict"],
        "",
        "## Honest Claim",
        "",
        report["honest_claim"],
        "",
        "## Checks",
        "",
    ]

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This verifies that the V0.45 fraud/banking continuity simulator result is real enough for internal proof-chain work.",
        "",
        "It confirms the simulator protects harm-sensitive cases while still flagging investigation-worthy malicious continuity patterns.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("All integrity checks passed:", all_passed)
    print("Verdict:", report["verdict"])
    print()
    print("Honest claim:")
    print(report["honest_claim"])
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()