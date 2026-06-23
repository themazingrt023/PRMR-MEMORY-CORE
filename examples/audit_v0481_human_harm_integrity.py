import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")
V048_RUNNER = Path("benchmarks/runners/run_human_harm_reduction_test_v048.py")
V048_PUBLIC = Path("reports/v048/public_human_harm_reduction_test_v048.json")
V048_PRIVATE = Path("reports/v048/private_internal_human_harm_reduction_test_v048.json")

OUT_DIR = Path("reports/v0481")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "human_harm_integrity_audit_v0481.json"
OUT_MD = OUT_DIR / "human_harm_integrity_audit_v0481.md"


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
        "private_harm_packets",
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
    unsafe = [
        "criminal",
        "fraudster",
        "guilty",
        "blacklist",
        "ban user",
        "close account immediately",
        "definitely fraud",
    ]
    return [term for term in unsafe if term in text]


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
            and ("= 11" in lowered or ": 11" in lowered)
            and "sum(" not in lowered
            and "len(" not in lowered
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_pass_count",
                "text": stripped,
            })

    return suspicious


def recompute_harm_test(dataset, runner):
    fraud_runner = load_module(Path("benchmarks/runners/run_fraud_baseline_war_v046.py"), "run_fraud_baseline_war_v046_for_v0481")
    explain_runner = load_module(Path("benchmarks/runners/run_fraud_explainability_report_v047.py"), "run_fraud_explainability_report_v047_for_v0481")

    engine = PRMRMemoryCore()
    accounts = dataset["accounts"]

    engine_input = [
        {
            "name": account["account_id"],
            "description": "Synthetic human harm integrity timeline",
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
        prmr_action = runner.map_prmr_label_to_harm_action(prmr_label)

        rule_label = fraud_runner.classify_rule_engine(original_rows)
        rule_action = runner.map_rule_label_to_harm_action(rule_label)

        explanation = explain_runner.explain_case(account_id, prmr_label, prmr_packet)

        prmr_labels[account_id] = prmr_label
        prmr_actions[account_id] = prmr_action
        rule_labels[account_id] = rule_label
        rule_actions[account_id] = rule_action
        explanations[account_id] = explanation
        harm_packets[account_id] = runner.build_harm_packet(account_id, prmr_label, prmr_action, explanation)

    prmr_harm_safe_matches = {
        account_id: runner.action_is_harm_safe(account_id, action)
        for account_id, action in prmr_actions.items()
    }

    prmr_non_punitive_harm_sensitive = {
        account_id: runner.action_is_not_punitive_for_harm_sensitive(account_id, action)
        for account_id, action in prmr_actions.items()
    }

    rule_non_punitive_harm_sensitive = {
        account_id: runner.action_is_not_punitive_for_harm_sensitive(account_id, action)
        for account_id, action in rule_actions.items()
    }

    rule_flattens_count = sum(
        1 for account_id, safe in rule_non_punitive_harm_sensitive.items()
        if account_id in runner.HARM_SENSITIVE_ACCOUNTS and safe is False
    )

    explanation_boundary = {
        account_id: "does not make a final punitive decision" in str(packet.get("human_review_boundary", "")).lower()
        for account_id, packet in harm_packets.items()
    }

    harm_warning_present = {
        account_id: bool(packet.get("why_not_flattened"))
        for account_id, packet in harm_packets.items()
    }

    return {
        "reconstruction_results": reconstruction_results,
        "all_reconstruct_exactly": all(reconstruction_results.values()),
        "prmr_labels": prmr_labels,
        "prmr_actions": prmr_actions,
        "rule_labels": rule_labels,
        "rule_actions": rule_actions,
        "harm_packets": harm_packets,
        "explanations": explanations,
        "prmr_harm_safe_matches": prmr_harm_safe_matches,
        "prmr_harm_safe_action_rate": round(sum(1 for ok in prmr_harm_safe_matches.values() if ok) / len(prmr_harm_safe_matches) * 100, 2),
        "prmr_non_punitive_harm_sensitive": prmr_non_punitive_harm_sensitive,
        "prmr_non_punitive_harm_sensitive_rate": round(sum(1 for ok in prmr_non_punitive_harm_sensitive.values() if ok) / len(prmr_non_punitive_harm_sensitive) * 100, 2),
        "rule_non_punitive_harm_sensitive": rule_non_punitive_harm_sensitive,
        "rule_flattens_count": rule_flattens_count,
        "explanation_boundary": explanation_boundary,
        "harm_warning_present": harm_warning_present,
    }


def main():
    print("PRMR V0.48.1 HUMAN HARM INTEGRITY AUDIT")
    print("---------------------------------------")

    checks = []

    dataset = load_json(DATASET_PATH)
    public = load_json(V048_PUBLIC)
    private = load_json(V048_PRIVATE)
    runner = load_module(V048_RUNNER, "run_human_harm_reduction_test_v048")

    recomputed = recompute_harm_test(dataset, runner)

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
        {}
    )

    add_check(
        checks,
        "prmr_harm_safe_action_rate_recomputes_to_100",
        recomputed["prmr_harm_safe_action_rate"] == public["prmr_harm_safe_action_rate"] == 100.0,
        {
            "reported": public["prmr_harm_safe_action_rate"],
            "recomputed": recomputed["prmr_harm_safe_action_rate"],
            "matches": recomputed["prmr_harm_safe_matches"],
        }
    )

    add_check(
        checks,
        "prmr_non_punitive_harm_sensitive_rate_recomputes_to_100",
        recomputed["prmr_non_punitive_harm_sensitive_rate"] == public["prmr_non_punitive_harm_sensitive_rate"] == 100.0,
        {
            "reported": public["prmr_non_punitive_harm_sensitive_rate"],
            "recomputed": recomputed["prmr_non_punitive_harm_sensitive_rate"],
            "matches": recomputed["prmr_non_punitive_harm_sensitive"],
        }
    )

    add_check(
        checks,
        "rule_engine_flattened_count_recomputes",
        recomputed["rule_flattens_count"] == public["rule_engine_flattened_harm_sensitive_count"],
        {
            "reported": public["rule_engine_flattened_harm_sensitive_count"],
            "recomputed": recomputed["rule_flattens_count"],
            "rule_actions": recomputed["rule_actions"],
        }
    )

    expected_actions = runner.HARM_SAFE_EXPECTED_ACTIONS

    add_check(
        checks,
        "safe_action_summary_recomputes_to_expected_actions",
        recomputed["prmr_actions"] == expected_actions and public["safe_action_summary"] == expected_actions,
        {
            "expected": expected_actions,
            "recomputed_actions": recomputed["prmr_actions"],
            "reported_actions": public["safe_action_summary"],
        }
    )

    add_check(
        checks,
        "human_review_boundary_recomputes",
        all(recomputed["explanation_boundary"].values()) and public["human_review_boundary_preserved"] is True,
        recomputed["explanation_boundary"]
    )

    add_check(
        checks,
        "harm_packets_include_harm_reduction_warning",
        all(recomputed["harm_warning_present"].values()),
        recomputed["harm_warning_present"]
    )

    public_forbidden = public_safety_scan(public)

    add_check(
        checks,
        "public_report_exposes_no_hidden_harm_packets_or_engine_terms",
        len(public_forbidden) == 0,
        {"forbidden_terms_found": public_forbidden}
    )

    unsafe_public = unsafe_language_scan(public)
    unsafe_private_packets = unsafe_language_scan(recomputed["harm_packets"])

    add_check(
        checks,
        "harm_reports_avoid_punitive_or_certain_guilt_language",
        len(unsafe_public) == 0 and len(unsafe_private_packets) == 0,
        {
            "unsafe_public_terms": unsafe_public,
            "unsafe_private_packet_terms": unsafe_private_packets,
        }
    )

    private_has_debug = all(
        key in private
        for key in [
            "private_prmr_labels",
            "private_rule_labels",
            "private_rule_actions",
            "private_harm_packets",
            "private_explanations",
            "private_reconstruction_results",
            "private_checks",
        ]
    )

    add_check(
        checks,
        "private_report_contains_debug_harm_packets_and_actions",
        private_has_debug,
        {}
    )

    source_text = V048_RUNNER.read_text(encoding="utf-8", errors="ignore")
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
        "version": "0.48.1",
        "report_type": "human_harm_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "result": result,
        "checks": checks,
        "summary": {
            "prmr_harm_safe_action_rate": recomputed["prmr_harm_safe_action_rate"],
            "prmr_non_punitive_harm_sensitive_rate": recomputed["prmr_non_punitive_harm_sensitive_rate"],
            "rule_engine_flattened_harm_sensitive_count": recomputed["rule_flattens_count"],
        },
        "verdict": (
            "V0.48 human harm reduction result is internally consistent. Harm-safe actions recompute, harm-sensitive cases remain non-punitive, rule-engine flattening recomputes, human-review boundaries hold, and public report hygiene passes."
            if all_passed
            else "V0.48 human harm reduction result needs review. One or more integrity checks failed."
        ),
        "honest_claim": (
            "V0.48 is synthetic internal human-harm reduction evidence only. It is not bank certification, legal advice, compliance approval, or production fraud deployment proof."
        ),
        "next_phase": "V0.48.2 Human Harm Report Leak Scan or V0.49 Fraud Track Master Gauntlet",
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.48.1 Human Harm Integrity Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.48.1  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        f"All integrity checks passed: **{all_passed}**",
        "",
        "## Summary",
        "",
        f"- PRMR harm-safe action rate: **{report['summary']['prmr_harm_safe_action_rate']}%**",
        f"- PRMR non-punitive harm-sensitive rate: **{report['summary']['prmr_non_punitive_harm_sensitive_rate']}%**",
        f"- Rule engine flattened harm-sensitive count: **{report['summary']['rule_engine_flattened_harm_sensitive_count']}**",
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
        "This audit verifies the human-harm reduction layer is not just a story.",
        "",
        "It recomputes harm-safe actions, non-punitive handling, rule-engine flattening, and human-review boundaries.",
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
    print("Summary:")
    for key, value in report["summary"].items():
        print("-", key + ":", value)
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