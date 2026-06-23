import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v045/fraud_continuity_simulator_v045.json")

V046_RUNNER = Path("benchmarks/runners/run_fraud_baseline_war_v046.py")
V0461_AUDIT = Path("examples/audit_v0461_pattern_preservation_compression.py")

V046_PUBLIC = Path("reports/v046/public_fraud_baseline_war_v046.json")
V046_INTERNAL = Path("reports/v046/private_internal_fraud_baseline_war_v046.json")

V0461_PUBLIC = Path("reports/v0461/public_pattern_preservation_compression_audit_v0461.json")
V0461_INTERNAL = Path("reports/v0461/private_internal_pattern_preservation_compression_audit_v0461.json")

OUT_DIR = Path("reports/v0462")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "fraud_baseline_pattern_integrity_audit_v0462.json"
OUT_MD = OUT_DIR / "fraud_baseline_pattern_integrity_audit_v0462.md"


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


def estimate_tokens(obj):
    return max(1, len(json.dumps(obj, sort_keys=True)) // 4)


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


def source_hardcode_scan(text):
    suspicious = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped or stripped.startswith("#"):
            continue

        # Conditional result construction is fine:
        # result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
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
                "text": stripped
            })

        # Fixed pass counts are suspicious only if not recomputed.
        if (
            ("passed_count" in lowered or "passed_checks" in lowered)
            and ("= 9" in lowered or "= 7" in lowered or ": 9" in lowered or ": 7" in lowered)
            and "sum(" not in lowered
            and "len(" not in lowered
        ):
            suspicious.append({
                "line": line_number,
                "reason": "possible_fixed_pass_count",
                "text": stripped
            })

    return suspicious


def build_engine_input(accounts):
    return [
        {
            "name": account["account_id"],
            "description": "Synthetic fraud integrity recomputation timeline",
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


def recompute_v046(dataset, runner):
    engine = PRMRMemoryCore()
    accounts = dataset["accounts"]

    engine_result = engine.run(build_engine_input(accounts))

    prmr_predictions = {}
    raw_predictions = {}
    rule_predictions = {}
    keyword_predictions = {}
    vector_predictions = {}
    summary_predictions = {}

    reconstruction_results = {}
    prmr_payload_packets = {}

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
        prmr_payload_packets[account_id] = packet

        prmr_predictions[account_id] = runner.classify_prmr(packet)
        raw_predictions[account_id] = runner.classify_raw_context(original_rows)
        rule_predictions[account_id] = runner.classify_rule_engine(original_rows)
        keyword_predictions[account_id] = runner.classify_keyword_search(original_rows)
        vector_predictions[account_id] = runner.classify_vector_like(original_rows)
        summary_predictions[account_id] = runner.classify_basic_summary(original_rows)

    method_predictions = {
        "prmr_memory_core": prmr_predictions,
        "raw_context": raw_predictions,
        "rule_engine": rule_predictions,
        "keyword_search": keyword_predictions,
        "vector_like": vector_predictions,
        "basic_summary": summary_predictions,
    }

    method_scores = {
        method: runner.score_predictions(predictions)
        for method, predictions in method_predictions.items()
    }

    raw_payload_tokens = runner.estimate_payload_tokens(accounts)
    prmr_payload_tokens = runner.estimate_payload_tokens(prmr_payload_packets)

    return {
        "reconstruction_results": reconstruction_results,
        "all_reconstruct_exactly": all(reconstruction_results.values()),
        "method_predictions": method_predictions,
        "method_scores": method_scores,
        "raw_payload_tokens": raw_payload_tokens,
        "prmr_payload_tokens": prmr_payload_tokens,
        "token_reduction_percentage": round((1 - prmr_payload_tokens / raw_payload_tokens) * 100, 2),
        "prmr_payload_packets": prmr_payload_packets,
    }


def recompute_v0461(dataset, runner, pattern_module):
    engine = PRMRMemoryCore()
    accounts = dataset["accounts"]

    engine_result = engine.run(build_engine_input(accounts))

    reconstruction_results = {}
    packets = {}
    predictions = {}
    missing_facts = {}
    stale_trap_leaks = {}
    raw_payload = {}
    packet_payload = {}

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

        decision = result["decision"]
        reconstructed = decision["reconstructed_rows"]

        reconstruction_results[account_id] = reconstructed == original_rows

        packet = runner.build_prmr_packet(reconstructed)
        packets[account_id] = packet
        predictions[account_id] = runner.classify_prmr(packet)

        raw_payload[account_id] = estimate_tokens(original_rows)
        packet_payload[account_id] = estimate_tokens(packet)

        packet_text = json.dumps(packet, sort_keys=True).lower()

        missing_facts[account_id] = [
            fact for fact in pattern_module.EXPECTED_PATTERN_FACTS[account_id]
            if fact.lower() not in packet_text
        ]

        stale_trap_leaks[account_id] = [
            phrase for phrase in [
                "fake_current",
                "stale duplicate",
                "close account immediately without review",
                "customer is malicious fraud actor",
                "money mule pattern confirmed",
                "skip api and launch public beta immediately",
                "normal ordinary household spending only",
            ]
            if phrase in packet_text
        ]

    total_raw_tokens = sum(raw_payload.values())
    total_packet_tokens = sum(packet_payload.values())
    token_reduction_percentage = round((1 - total_packet_tokens / total_raw_tokens) * 100, 2)

    prediction_matches = {
        account_id: predictions[account_id] == pattern_module.EXPECTED_LABELS[account_id]
        for account_id in pattern_module.EXPECTED_LABELS
    }

    fact_preservation_matches = {
        account_id: len(missing) == 0
        for account_id, missing in missing_facts.items()
    }

    stale_trap_clean = {
        account_id: len(leaks) == 0
        for account_id, leaks in stale_trap_leaks.items()
    }

    prediction_accuracy = round(
        sum(1 for ok in prediction_matches.values() if ok) / len(prediction_matches) * 100,
        2
    )

    pattern_fact_preservation_rate = round(
        sum(1 for ok in fact_preservation_matches.values() if ok) / len(fact_preservation_matches) * 100,
        2
    )

    stale_trap_exclusion_rate = round(
        sum(1 for ok in stale_trap_clean.values() if ok) / len(stale_trap_clean) * 100,
        2
    )

    return {
        "reconstruction_results": reconstruction_results,
        "all_reconstruct_exactly": all(reconstruction_results.values()),
        "packets": packets,
        "predictions": predictions,
        "missing_facts": missing_facts,
        "stale_trap_leaks": stale_trap_leaks,
        "total_raw_tokens": total_raw_tokens,
        "total_packet_tokens": total_packet_tokens,
        "token_reduction_percentage": token_reduction_percentage,
        "prediction_accuracy": prediction_accuracy,
        "pattern_fact_preservation_rate": pattern_fact_preservation_rate,
        "stale_trap_exclusion_rate": stale_trap_exclusion_rate,
        "prediction_matches": prediction_matches,
        "fact_preservation_matches": fact_preservation_matches,
        "stale_trap_clean": stale_trap_clean,
    }


def main():
    print("PRMR V0.46.2 FRAUD BASELINE + PATTERN INTEGRITY AUDIT")
    print("------------------------------------------------------")

    checks = []

    dataset = load_json(DATASET_PATH)

    runner = load_module(V046_RUNNER, "run_fraud_baseline_war_v046")
    pattern_module = load_module(V0461_AUDIT, "audit_v0461_pattern_preservation_compression")

    v046_public = load_json(V046_PUBLIC)
    v046_internal = load_json(V046_INTERNAL)

    v0461_public = load_json(V0461_PUBLIC)
    v0461_internal = load_json(V0461_INTERNAL)

    v046_recomputed = recompute_v046(dataset, runner)
    v0461_recomputed = recompute_v0461(dataset, runner, pattern_module)

    # V0.46 report consistency.
    v046_public_passed = sum(1 for check in v046_public["checks"] if check["passed"])
    v046_public_total = len(v046_public["checks"])

    add_check(
        checks,
        "v046_public_report_pass_count_recomputes",
        v046_public_passed == v046_public["passed_checks"]
        and v046_public_total == v046_public["total_checks"],
        {
            "reported_passed": v046_public["passed_checks"],
            "recomputed_passed": v046_public_passed,
            "reported_total": v046_public["total_checks"],
            "recomputed_total": v046_public_total,
        }
    )

    v046_public_status = {check["name"]: check["passed"] for check in v046_public["checks"]}
    v046_internal_status = {check["name"]: check["passed"] for check in v046_internal["checks"]}

    add_check(
        checks,
        "v046_public_and_internal_report_statuses_agree",
        v046_public_status == v046_internal_status,
        {}
    )

    # V0.46 method accuracy recomputes.
    recomputed_method_accuracy = {
        method: v046_recomputed["method_scores"][method]["accuracy"]
        for method in v046_recomputed["method_scores"]
    }

    add_check(
        checks,
        "v046_method_accuracies_recompute",
        recomputed_method_accuracy == v046_public["method_accuracy"],
        {
            "reported": v046_public["method_accuracy"],
            "recomputed": recomputed_method_accuracy,
        }
    )

    add_check(
        checks,
        "v046_payload_numbers_recompute",
        v046_recomputed["raw_payload_tokens"] == v046_public["raw_payload_tokens"]
        and v046_recomputed["prmr_payload_tokens"] == v046_public["prmr_payload_tokens"]
        and v046_recomputed["token_reduction_percentage"] == v046_public["prmr_token_reduction_percentage"],
        {
            "reported_raw_tokens": v046_public["raw_payload_tokens"],
            "recomputed_raw_tokens": v046_recomputed["raw_payload_tokens"],
            "reported_prmr_tokens": v046_public["prmr_payload_tokens"],
            "recomputed_prmr_tokens": v046_recomputed["prmr_payload_tokens"],
            "reported_reduction": v046_public["prmr_token_reduction_percentage"],
            "recomputed_reduction": v046_recomputed["token_reduction_percentage"],
        }
    )

    add_check(
        checks,
        "v046_prmr_beats_non_raw_baselines_and_matches_raw",
        v046_recomputed["method_scores"]["prmr_memory_core"]["accuracy"] == v046_recomputed["method_scores"]["raw_context"]["accuracy"]
        and v046_recomputed["method_scores"]["prmr_memory_core"]["accuracy"] > max(
            v046_recomputed["method_scores"]["rule_engine"]["accuracy"],
            v046_recomputed["method_scores"]["keyword_search"]["accuracy"],
            v046_recomputed["method_scores"]["vector_like"]["accuracy"],
            v046_recomputed["method_scores"]["basic_summary"]["accuracy"],
        ),
        recomputed_method_accuracy
    )

    # V0.46.1 report consistency.
    v0461_public_passed = sum(1 for check in v0461_public["checks"] if check["passed"])
    v0461_public_total = len(v0461_public["checks"])

    add_check(
        checks,
        "v0461_public_report_pass_count_recomputes",
        v0461_public_passed == v0461_public["passed_checks"]
        and v0461_public_total == v0461_public["total_checks"],
        {
            "reported_passed": v0461_public["passed_checks"],
            "recomputed_passed": v0461_public_passed,
            "reported_total": v0461_public["total_checks"],
            "recomputed_total": v0461_public_total,
        }
    )

    add_check(
        checks,
        "v0461_pattern_preservation_metrics_recompute",
        v0461_recomputed["prediction_accuracy"] == v0461_public["prediction_accuracy"]
        and v0461_recomputed["pattern_fact_preservation_rate"] == v0461_public["pattern_fact_preservation_rate"]
        and v0461_recomputed["stale_trap_exclusion_rate"] == v0461_public["stale_trap_exclusion_rate"],
        {
            "reported_prediction_accuracy": v0461_public["prediction_accuracy"],
            "recomputed_prediction_accuracy": v0461_recomputed["prediction_accuracy"],
            "reported_pattern_fact_preservation_rate": v0461_public["pattern_fact_preservation_rate"],
            "recomputed_pattern_fact_preservation_rate": v0461_recomputed["pattern_fact_preservation_rate"],
            "reported_stale_trap_exclusion_rate": v0461_public["stale_trap_exclusion_rate"],
            "recomputed_stale_trap_exclusion_rate": v0461_recomputed["stale_trap_exclusion_rate"],
        }
    )

    add_check(
        checks,
        "v0461_compression_numbers_recompute",
        v0461_recomputed["total_raw_tokens"] == v0461_public["total_raw_tokens"]
        and v0461_recomputed["total_packet_tokens"] == v0461_public["total_packet_tokens"]
        and v0461_recomputed["token_reduction_percentage"] == v0461_public["token_reduction_percentage"],
        {
            "reported_raw_tokens": v0461_public["total_raw_tokens"],
            "recomputed_raw_tokens": v0461_recomputed["total_raw_tokens"],
            "reported_packet_tokens": v0461_public["total_packet_tokens"],
            "recomputed_packet_tokens": v0461_recomputed["total_packet_tokens"],
            "reported_reduction": v0461_public["token_reduction_percentage"],
            "recomputed_reduction": v0461_recomputed["token_reduction_percentage"],
        }
    )

    add_check(
        checks,
        "v0461_packets_preserve_patterns_and_exclude_stale_traps",
        all(v0461_recomputed["fact_preservation_matches"].values())
        and all(v0461_recomputed["stale_trap_clean"].values())
        and all(v0461_recomputed["prediction_matches"].values()),
        {
            "fact_preservation_matches": v0461_recomputed["fact_preservation_matches"],
            "stale_trap_clean": v0461_recomputed["stale_trap_clean"],
            "prediction_matches": v0461_recomputed["prediction_matches"],
        }
    )

    # Public safety.
    v046_public_forbidden = public_safety_scan(v046_public)
    v0461_public_forbidden = public_safety_scan(v0461_public)

    add_check(
        checks,
        "public_reports_expose_no_label_internals_or_engine_diagnostics",
        len(v046_public_forbidden) == 0 and len(v0461_public_forbidden) == 0,
        {
            "v046_forbidden_terms": v046_public_forbidden,
            "v0461_forbidden_terms": v0461_public_forbidden,
        }
    )

    # Source hardcode scan.
    source_text = (
        V046_RUNNER.read_text(encoding="utf-8", errors="ignore")
        + "\n"
        + V0461_AUDIT.read_text(encoding="utf-8", errors="ignore")
    )

    suspicious = source_hardcode_scan(source_text)

    add_check(
        checks,
        "source_files_do_not_force_final_pass_or_fixed_counts",
        len(suspicious) == 0,
        {"suspicious_patterns_found": suspicious}
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks
    result = "PASS" if all_passed else "NEEDS_WORK"

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.46.2",
        "report_type": "fraud_baseline_pattern_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "result": result,
        "checks": [
            {"name": check["name"], "passed": check["passed"]}
            for check in checks
        ],
        "summary": {
            "v046_prmr_accuracy": recomputed_method_accuracy["prmr_memory_core"],
            "v046_best_non_raw_baseline_accuracy": max(
                recomputed_method_accuracy["rule_engine"],
                recomputed_method_accuracy["keyword_search"],
                recomputed_method_accuracy["vector_like"],
                recomputed_method_accuracy["basic_summary"],
            ),
            "v0461_pattern_fact_preservation_rate": v0461_recomputed["pattern_fact_preservation_rate"],
            "v0461_stale_trap_exclusion_rate": v0461_recomputed["stale_trap_exclusion_rate"],
            "v0461_packet_token_reduction": v0461_recomputed["token_reduction_percentage"],
        },
        "safe_claim": (
            "V0.46.2 verifies that the V0.46 fraud baseline comparison and V0.46.1 pattern-preservation audit recompute from source data. "
            "In this synthetic simulator, PRMR matched raw-context accuracy, beat non-raw baselines, and preserved required pattern facts in smaller continuity packets."
        ),
        "honest_boundary": (
            "Synthetic internal evidence only. This is not banking certification, not compliance approval, and not production fraud deployment proof."
        ),
        "next_phase": "V0.47 Explainability Report",
    }

    internal_report = {
        **public_report,
        "public_safe": False,
        "internal_v046_recomputed": v046_recomputed,
        "internal_v0461_recomputed": v0461_recomputed,
        "internal_checks": checks,
        "internal_note": "Internal report includes recomputed predictions, packets, and audit diagnostics. Do not publish."
    }

    public_path = OUT_DIR / "public_fraud_baseline_pattern_integrity_audit_v0462.json"
    internal_path = OUT_DIR / "private_internal_fraud_baseline_pattern_integrity_audit_v0462.json"
    scorecard_path = OUT_DIR / "scorecard_v0462.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    internal_path.write_text(json.dumps(internal_report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.46.2 Fraud Baseline + Pattern Integrity Audit",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.46.2  ",
        "",
        "## Result",
        "",
        f"**{result}**",
        "",
        f"Passed: **{passed_count}/{total_checks}**",
        "",
        "## Summary",
        "",
        f"- V0.46 PRMR accuracy: **{public_report['summary']['v046_prmr_accuracy']}%**",
        f"- V0.46 best non-raw baseline accuracy: **{public_report['summary']['v046_best_non_raw_baseline_accuracy']}%**",
        f"- V0.46.1 pattern fact preservation: **{public_report['summary']['v0461_pattern_fact_preservation_rate']}%**",
        f"- V0.46.1 stale trap exclusion: **{public_report['summary']['v0461_stale_trap_exclusion_rate']}%**",
        f"- V0.46.1 packet token reduction: **{public_report['summary']['v0461_packet_token_reduction']}%**",
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
    ]

    for check in public_report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        md.append(f"- **{status}** — {check['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This audit locks the fraud baseline comparison and pattern-preservation proof together.",
        "",
        "It checks that PRMR is not just winning a benchmark, but preserving useful continuity information inside a smaller packet.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    scorecard_path.write_text("\n".join(md), encoding="utf-8")

    print("Passed checks:", f"{passed_count}/{total_checks}")
    print("All integrity checks passed:", all_passed)
    print("Result:", result)
    print()
    print("Summary:")
    for key, value in public_report["summary"].items():
        print("-", key + ":", value)
    print()
    print("Check list:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(public_path)
    print(internal_path)
    print(scorecard_path)


if __name__ == "__main__":
    main()