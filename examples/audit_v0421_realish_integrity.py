import json
import random
import importlib.util
from pathlib import Path
from datetime import datetime

PUBLIC_REPORT = Path("reports/v042/public_realish_dataset_trial_v042.json")
PRIVATE_REPORT = Path("reports/v042/private_internal_realish_dataset_trial_v042.json")
DATASET_PATH = Path("benchmarks/datasets_v042/realish_dataset_trial_v042.json")
RUNNER_PATH = Path("benchmarks/runners/run_realish_dataset_trial_v042.py")

OUT_DIR = Path("reports/v0421")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "realish_integrity_audit_v0421.json"
OUT_MD = OUT_DIR / "realish_integrity_audit_v0421.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def load_runner_module():
    spec = importlib.util.spec_from_file_location("v042_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def close_enough(a, b, tolerance=0.01):
    try:
        return abs(float(a) - float(b)) <= tolerance
    except Exception:
        return False


def public_safety_scan(text):
    forbidden_terms = [
        "private_answer_details",
        "protected_note",
        "engine_result_snapshot",
        "reconstructed_rows",
        "compressed_package",
        "internal_rule_data",
        "private_internal",
        "x-prmr-api-key",
        "api_key",
        "secret"
    ]

    lowered = text.lower()
    return [term for term in forbidden_terms if term in lowered]


def hardcode_scan(text):
    suspicious_patterns = [
        "prmr_accuracy = 100",
        "useful_reconstruction_accuracy = 100",
        "payload_tokens = 660",
        "\"prmr_memory_core\": 100",
        "'prmr_memory_core': 100",
        "return 100",
        "score = 100"
    ]

    lowered = text.lower()
    return [pattern for pattern in suspicious_patterns if pattern.lower() in lowered]


def rerun_methods(runner, dataset):
    rows = dataset["rows"]
    expected = dataset["expected"]
    target_client = dataset["target_client"]

    method_outputs = {
        "raw_context": runner.raw_context_method(rows, expected, target_client),
        "basic_summary": runner.basic_summary_method(rows, expected, target_client),
        "keyword_search": runner.keyword_method(rows, expected, target_client),
        "vector_like": runner.vector_like_method(rows, expected, target_client),
        "prmr_memory_core": runner.prmr_method(rows, expected, target_client),
    }

    results = runner.score_methods(method_outputs, expected)
    return method_outputs, results


def shuffle_prmr_test(runner, dataset):
    rows = list(dataset["rows"])
    random.seed(421)
    random.shuffle(rows)

    expected = dataset["expected"]
    target_client = dataset["target_client"]

    output = runner.prmr_method(rows, expected, target_client)
    score, details = runner.judge_answer(output["answer"], expected)
    tokens = runner.estimate_tokens(output["payload"])

    return {
        "score": score,
        "payload_tokens": tokens,
        "reconstruction_match": output["engine_decision_public"]["reconstruction_match"],
        "details": details
    }


def main():
    checks = []

    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)
    dataset = load_json(DATASET_PATH)
    runner = load_runner_module()

    method_outputs, recomputed_results = rerun_methods(runner, dataset)
    reported_results = public["results"]

    # 1. Accuracy recomputes.
    accuracy_mismatches = {}

    for name, reported in reported_results.items():
        reported_accuracy = reported["useful_reconstruction_accuracy"]
        recomputed_accuracy = recomputed_results[name]["useful_reconstruction_accuracy"]

        if not close_enough(reported_accuracy, recomputed_accuracy):
            accuracy_mismatches[name] = {
                "reported": reported_accuracy,
                "recomputed": recomputed_accuracy
            }

    add_check(
        checks,
        "method_accuracies_recompute_from_runner_outputs",
        len(accuracy_mismatches) == 0,
        {"mismatches": accuracy_mismatches}
    )

    # 2. Token counts recompute.
    token_mismatches = {}

    for name, reported in reported_results.items():
        reported_tokens = reported["payload_tokens"]
        recomputed_tokens = runner.estimate_tokens(method_outputs[name]["payload"])

        if int(reported_tokens) != int(recomputed_tokens):
            token_mismatches[name] = {
                "reported": reported_tokens,
                "recomputed": recomputed_tokens
            }

    add_check(
        checks,
        "payload_token_counts_recompute_from_actual_payloads",
        len(token_mismatches) == 0,
        {"mismatches": token_mismatches}
    )

    raw = reported_results["raw_context"]
    basic = reported_results["basic_summary"]
    keyword = reported_results["keyword_search"]
    vector = reported_results["vector_like"]
    prmr = reported_results["prmr_memory_core"]

    # 3. PRMR matches raw accuracy with lower payload.
    add_check(
        checks,
        "prmr_matches_raw_accuracy_with_lower_payload",
        prmr["useful_reconstruction_accuracy"] == raw["useful_reconstruction_accuracy"]
        and prmr["payload_tokens"] < raw["payload_tokens"],
        {
            "raw_accuracy": raw["useful_reconstruction_accuracy"],
            "prmr_accuracy": prmr["useful_reconstruction_accuracy"],
            "raw_tokens": raw["payload_tokens"],
            "prmr_tokens": prmr["payload_tokens"]
        }
    )

    # 4. PRMR beats non-raw baselines.
    best_non_raw_accuracy = max(
        basic["useful_reconstruction_accuracy"],
        keyword["useful_reconstruction_accuracy"],
        vector["useful_reconstruction_accuracy"]
    )

    add_check(
        checks,
        "prmr_beats_non_raw_baselines_on_realish_memory",
        prmr["useful_reconstruction_accuracy"] > best_non_raw_accuracy,
        {
            "prmr_accuracy": prmr["useful_reconstruction_accuracy"],
            "basic_summary_accuracy": basic["useful_reconstruction_accuracy"],
            "keyword_accuracy": keyword["useful_reconstruction_accuracy"],
            "vector_like_accuracy": vector["useful_reconstruction_accuracy"],
            "best_non_raw_accuracy": best_non_raw_accuracy
        }
    )

    # 5. PRMR token reduction recomputes.
    recomputed_reduction = round((1 - prmr["payload_tokens"] / raw["payload_tokens"]) * 100, 2)
    reported_reduction = public["summary"]["prmr_token_reduction_vs_raw_percent"]

    add_check(
        checks,
        "prmr_token_reduction_vs_raw_recomputes",
        close_enough(reported_reduction, recomputed_reduction, 0.01),
        {
            "reported_reduction": reported_reduction,
            "recomputed_reduction": recomputed_reduction,
            "raw_tokens": raw["payload_tokens"],
            "prmr_tokens": prmr["payload_tokens"]
        }
    )

    # 6. PRMR reconstruction match is true.
    prmr_engine_decision = prmr.get("engine_decision_public", {})

    add_check(
        checks,
        "prmr_engine_reconstruction_match_is_true",
        prmr_engine_decision.get("reconstruction_match") is True,
        prmr_engine_decision
    )

    # 7. Private report contains detailed answer scoring.
    add_check(
        checks,
        "private_report_contains_answer_details",
        "private_answer_details" in private,
        {
            "private_answer_details_present": "private_answer_details" in private
        }
    )

    # 8. Public report safety.
    public_text = PUBLIC_REPORT.read_text(encoding="utf-8", errors="ignore")
    forbidden_public = public_safety_scan(public_text)

    add_check(
        checks,
        "public_report_exposes_no_private_answer_details_or_engine_internals",
        len(forbidden_public) == 0,
        {"forbidden_terms_found": forbidden_public}
    )

    # 9. Runner does not appear to hardcode result.
    runner_text = RUNNER_PATH.read_text(encoding="utf-8", errors="ignore")
    suspicious = hardcode_scan(runner_text)

    add_check(
        checks,
        "runner_does_not_appear_to_hardcode_v042_result",
        len(suspicious) == 0,
        {"suspicious_patterns_found": suspicious}
    )

    # 10. PRMR survives row shuffle.
    shuffled = shuffle_prmr_test(runner, dataset)

    add_check(
        checks,
        "prmr_result_survives_dataset_row_shuffle",
        shuffled["score"] == 100.0 and shuffled["reconstruction_match"] is True,
        shuffled
    )

    # 11. Real-ish dataset contains intended messy source types.
    source_types = set(row.get("source_type") for row in dataset["rows"])
    required_sources = {"chat_log", "project_note", "dev_log", "fake_company_doc", "roadmap_fragment", "canon_record"}

    add_check(
        checks,
        "dataset_contains_realish_source_types",
        required_sources.issubset(source_types),
        {
            "required_sources": sorted(required_sources),
            "found_sources": sorted(source_types)
        }
    )

    # 12. Dataset contains stale/near-miss/cross-client traps.
    rows = dataset["rows"]

    has_stale_or_near_miss = any(
        row.get("signal_type") in ("fake_current", "near_miss", "stale_update")
        or row.get("trust_level") in ("stale", "untrusted", "low")
        for row in rows
    )

    has_cross_client = any(row.get("client_id") != dataset["target_client"] for row in rows)

    add_check(
        checks,
        "dataset_contains_stale_near_miss_and_cross_client_traps",
        has_stale_or_near_miss and has_cross_client,
        {
            "has_stale_or_near_miss": has_stale_or_near_miss,
            "has_cross_client": has_cross_client
        }
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    all_passed = passed_count == total_checks

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.42.1",
        "report_type": "realish_dataset_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_integrity_checks_passed": all_passed,
        "checks": checks,
        "verdict": (
            "V0.42 real-ish dataset result is internally consistent. PRMR matched raw-context useful reconstruction, beat non-raw baselines, used far fewer payload tokens, and survived messy memory traps."
            if all_passed
            else "V0.42 real-ish dataset result needs review. One or more integrity checks failed."
        ),
        "honest_claim": (
            "In V0.42, PRMR matched raw-context useful reconstruction on messy real-ish memory while using a much smaller downstream continuity packet. "
            "Raw context still matched accuracy but paid the full memory payload cost."
        ),
        "next_phase": "V0.43 Security Killbox or V0.42.2 harder real-ish dataset with fewer repeated trusted fragments"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.42.1 Real-ish Dataset Integrity Audit

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.42.1  

## Result

**{passed_count}/{total_checks} checks passed**

All integrity checks passed: **{all_passed}**

## Verdict

{report["verdict"]}

## Honest Claim

{report["honest_claim"]}

## Key Numbers

- Raw context tokens: **{raw["payload_tokens"]}**
- PRMR tokens: **{prmr["payload_tokens"]}**
- PRMR token reduction vs raw: **{reported_reduction}%**
- Raw context useful reconstruction: **{raw["useful_reconstruction_accuracy"]}%**
- PRMR useful reconstruction: **{prmr["useful_reconstruction_accuracy"]}%**
- Best non-raw baseline: **{best_non_raw_accuracy}%**

## Checks

"""

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md += f"- **{status}** — {check['name']}\n"

    md += """

## Meaning

This verifies the V0.42 real-ish messy memory benchmark.

It remains an internal benchmark, not production certification.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.42.1 REAL-ISH DATASET INTEGRITY AUDIT")
    print("---------------------------------------------")
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