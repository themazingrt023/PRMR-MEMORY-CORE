import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")
V047_RUNNER = Path("benchmarks/runners/run_fraud_explainability_report_v047.py")
V047_PUBLIC = Path("reports/v047/public_fraud_explainability_report_v047.json")
V047_PRIVATE = Path("reports/v047/private_internal_fraud_explainability_report_v047.json")

OUT_DIR = Path("reports/v0471")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "explainability_integrity_audit_v0471.json"
OUT_MD = OUT_DIR / "explainability_integrity_audit_v0471.md"

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

REQUIRED_SECTIONS = [
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
    return [word for word in UNSAFE_WORDS if word in text]


def hardcode_scan(text):
    suspicious = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped or stripped.startswith("#"):
            continue

        if "result" in lowered and "pass" in lowered:
            if " if " in lowered and "else" in lowered:
                continue
            if "==" in lowered:
                continue
            if "print(" in lowered:
                continue

            suspicious.append({
                "line": line_number,
                "reason": "possible_forced_pass_result",
                "text": stripped,
            })

        if (
            ("passed_count" in lowered or "passed_checks" in lowered)
            and ("= 8" in lowered or ": 8" in lowered)
            and "sum(" not in lowered
            and "len(" not in lowered
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_pass_count",
                "text": stripped,
            })

    return suspicious


def build_engine_input(accounts):
    return [
        {
            "name": account["account_id"],
            "description": "Synthetic fraud explainability integrity timeline",
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


def recompute_explanations(dataset, runner):
    engine = PRMRMemoryCore()
    accounts = dataset["accounts"]

    engine_result = engine.run(build_engine_input(accounts))

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

        packet = runner.runner.build_prmr_packet(reconstructed) if hasattr(runner, "runner") else None

        # Fallback: V0.47 imports V0.46 runner as local variable in main,
        # so we load it directly here for clean recomputation.
        if packet is None:
            v046_runner = load_module(Path("benchmarks/runners/run_fraud_baseline_war_v046.py"), "run_fraud_baseline_war_v046_for_v0471")
            packet = v046_runner.build_prmr_packet(reconstructed)
            label = v046_runner.classify_prmr(packet)
        else:
            label = runner.runner.classify_prmr(packet)

        packets[account_id] = packet
        classifications[account_id] = label
        explanations[account_id] = runner.explain_case(account_id, label, packet)

    return {
        "reconstruction_results": reconstruction_results,
        "all_reconstruct_exactly": all(reconstruction_results.values()),
        "packets": packets,
        "classifications": classifications,
        "explanations": explanations,
    }


def main():
    print("PRMR V0.47.1 EXPLAINABILITY INTEGRITY AUDIT")
    print("-------------------------------------------")

    checks = []

    dataset = load_json(DATASET_PATH)
    runner = load_module(V047_RUNNER, "run_fraud_explainability_report_v047")
    public = load_json(V047_PUBLIC)
    private = load_json(V047_PRIVATE)

    recomputed = recompute_explanations(dataset, runner)
    explanations = recomputed["explanations"]

    add_check(
        checks,
        "all_timelines_reconstruct_exactly",
        recomputed["all_reconstruct_exactly"],
        recomputed["reconstruction_results"]
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

    public_status = {check["name"]: check["passed"] for check in public["checks"]}
    private_status = {check["name"]: check["passed"] for check in private["checks"]}

    add_check(
        checks,
        "public_and_private_reports_agree_on_check_statuses",
        public_status == private_status,
        {
            "public_only": sorted(set(public_status) - set(private_status)),
            "private_only": sorted(set(private_status) - set(public_status)),
        }
    )

    required_section_coverage = {
        account_id: all(section in explanation for section in REQUIRED_SECTIONS)
        for account_id, explanation in explanations.items()
    }

    add_check(
        checks,
        "recomputed_explanations_have_required_sections",
        all(required_section_coverage.values()),
        required_section_coverage
    )

    evidence_coverage = {
        account_id: (
            len(explanation["supporting_evidence"]) > 0
            and len(explanation["human_review_evidence"]) > 0
        )
        for account_id, explanation in explanations.items()
    }

    add_check(
        checks,
        "recomputed_explanations_include_evidence",
        all(evidence_coverage.values()),
        evidence_coverage
    )

    human_review_boundary = {
        account_id: "does not make a final punitive decision" in explanation["final_decision_boundary"].lower()
        for account_id, explanation in explanations.items()
    }

    add_check(
        checks,
        "recomputed_explanations_preserve_human_review_boundary",
        all(human_review_boundary.values()),
        human_review_boundary
    )

    unsafe_public = unsafe_language_scan(public)
    unsafe_private_explanations = unsafe_language_scan(explanations)

    add_check(
        checks,
        "explanations_avoid_punitive_or_certain_guilt_language",
        len(unsafe_public) == 0 and len(unsafe_private_explanations) == 0,
        {
            "unsafe_public_terms": unsafe_public,
            "unsafe_private_explanation_terms": unsafe_private_explanations,
        }
    )

    expected_safe_labels = {
        "acct_normal_001": "No fraud escalation indicated",
        "acct_scam_victim_001": "Possible scam victim support needed",
        "acct_pressured_mule_001": "Possible coercion or pressured mule risk",
        "acct_ato_001": "Possible account takeover victim",
        "acct_malicious_001": "Investigation-worthy risk pattern",
        "acct_false_positive_001": "Likely false positive",
    }

    recomputed_safe_labels = {
        account_id: explanation["safe_label"]
        for account_id, explanation in explanations.items()
    }

    add_check(
        checks,
        "safe_labels_recompute_to_expected_bank_safe_wording",
        recomputed_safe_labels == expected_safe_labels,
        {
            "expected": expected_safe_labels,
            "recomputed": recomputed_safe_labels,
        }
    )

    public_forbidden = public_safety_scan(public)

    add_check(
        checks,
        "public_report_exposes_no_private_labels_or_engine_internals",
        len(public_forbidden) == 0,
        {"forbidden_terms_found": public_forbidden}
    )

    private_has_debug = all(
        key in private
        for key in [
            "private_packets",
            "private_classifications",
            "private_explanations",
            "private_reconstruction_results",
            "private_checks",
        ]
    )

    add_check(
        checks,
        "private_report_contains_debug_packets_and_explanations",
        private_has_debug,
        {}
    )

    source_text = V047_RUNNER.read_text(encoding="utf-8", errors="ignore")
    suspicious = hardcode_scan(source_text)

    add_check(
        checks,
        "runner_does_not_force_final_pass_or_fixed_counts",
        len(suspicious) == 0,
        {"suspicious_patterns_found": suspicious}
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks
    result = "PASS" if all_passed else "NEEDS_WORK"

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.47.1",
        "report_type": "explainability_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "result": result,
        "checks": checks,
        "verdict": (
            "V0.47 explainability report is internally consistent. Explanations recompute, required sections exist, evidence is present, unsafe punitive language is avoided, human-review boundaries hold, and public report hygiene passes."
            if all_passed
            else "V0.47 explainability report needs review. One or more integrity checks failed."
        ),
        "honest_claim": (
            "V0.47 is synthetic internal explainability evidence only. It is not bank certification, legal advice, compliance approval, or production fraud deployment proof."
        ),
        "next_phase": "V0.47.2 Explainability Report Leak Scan or V0.48 Human Harm Reduction Test",
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.47.1 Explainability Integrity Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.47.1  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
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
        "This audit checks that the explainability layer is not decorative.",
        "",
        "It verifies that explanations recompute from PRMR packets, contain evidence, avoid punitive certainty, and preserve human review.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("All integrity checks passed:", all_passed)
    print("Result:", result)
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