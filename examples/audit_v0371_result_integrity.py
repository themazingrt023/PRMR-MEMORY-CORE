import json
import math
from pathlib import Path
from datetime import datetime


PUBLIC_REPORT = Path("reports/v037/public_realistic_memory_benchmark_v037.json")
PRIVATE_REPORT = Path("reports/v037/private_internal_realistic_memory_benchmark_v037.json")
DATASET_DIR = Path("benchmarks/datasets_v037")
RUNNER = Path("benchmarks/runners/run_realistic_memory_benchmark_v037.py")

OUT_DIR = Path("reports/v0371")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "result_integrity_audit_v0371.json"
OUT_MD = OUT_DIR / "result_integrity_audit_v0371.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_size(data):
    return len(json.dumps(data, sort_keys=True).encode("utf-8"))


def close_enough(a, b, tolerance=0.05):
    try:
        return abs(float(a) - float(b)) <= tolerance
    except Exception:
        return False


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def main():
    checks = []

    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)

    scorecard = public.get("scorecard", {})
    reported_total = float(public.get("realistic_memory_trust_score"))

    recomputed_total = round(
        float(scorecard.get("reconstruction_fidelity", 0))
        + float(scorecard.get("continuity_preservation", 0))
        + float(scorecard.get("signal_noise_discrimination", 0))
        + float(scorecard.get("compression_judgment", 0))
        + float(scorecard.get("baseline_comparison", 0))
        + float(scorecard.get("latency_cost_efficiency", 0)),
        2
    )

    add_check(
        checks,
        "score_recomputes_from_category_points",
        close_enough(reported_total, recomputed_total),
        {
            "reported_total": reported_total,
            "recomputed_total": recomputed_total,
            "scorecard": scorecard
        }
    )

    engine_result = private.get("engine_result_snapshot", {})
    results = engine_result.get("results", [])

    add_check(
        checks,
        "restricted_report_contains_expected_engine_snapshot",
        isinstance(results, list) and len(results) > 0,
        {
            "result_count": len(results)
        }
    )

    reconstruction_details = []

    for result in results:
        dataset_name = result.get("dataset")
        dataset_path = DATASET_DIR / f"{dataset_name}.json"

        if not dataset_path.exists():
            reconstruction_details.append({
                "dataset": dataset_name,
                "passed": False,
                "reason": "Original dataset file missing."
            })
            continue

        original = load_json(dataset_path)["rows"]
        reconstructed = result.get("decision", {}).get("reconstructed_rows")

        passed = original == reconstructed

        reconstruction_details.append({
            "dataset": dataset_name,
            "passed": passed,
            "original_rows": len(original),
            "reconstructed_rows": len(reconstructed) if isinstance(reconstructed, list) else None
        })

    add_check(
        checks,
        "all_restored_rows_match_original_dataset_files",
        all(item["passed"] for item in reconstruction_details),
        {
            "details": reconstruction_details
        }
    )

    compression_details = []

    for result in results:
        dataset = result.get("dataset")
        decision = result.get("decision", {})

        raw_size = decision.get("raw_size")
        policy_size = decision.get("policy_size")
        reported_ratio = decision.get("policy_compression_ratio")
        reported_saved = decision.get("policy_saved_percentage")
        mode = decision.get("policy_mode")

        if not raw_size or not policy_size:
            compression_details.append({
                "dataset": dataset,
                "passed": False,
                "reason": "Missing raw_size or policy_size."
            })
            continue

        recomputed_ratio = raw_size / policy_size if policy_size else None
        recomputed_saved = ((raw_size - policy_size) / raw_size) * 100 if raw_size else None

        compression_details.append({
            "dataset": dataset,
            "passed": close_enough(reported_ratio, recomputed_ratio, 0.01)
                      and close_enough(reported_saved, recomputed_saved, 0.01),
            "policy_mode": mode,
            "raw_size": raw_size,
            "policy_size": policy_size,
            "reported_ratio": reported_ratio,
            "recomputed_ratio": recomputed_ratio,
            "reported_saved": reported_saved,
            "recomputed_saved": recomputed_saved
        })

    add_check(
        checks,
        "compression_ratios_recompute_from_raw_and_policy_sizes",
        all(item["passed"] for item in compression_details),
        {
            "details": compression_details
        }
    )

    policy_details = []

    for result in results:
        dataset = result.get("dataset")
        decision = result.get("decision", {})
        mode = decision.get("policy_mode")
        saved = float(decision.get("policy_saved_percentage", 0) or 0)

        if "mixed_noise" in dataset:
            expected = mode == "raw" and saved == 0
            reason = "mixed noise flood should stay raw"
        else:
            expected = mode in ("dictionary", "rule", "transform") and saved > 0
            reason = "structured realistic memory should compress usefully"

        policy_details.append({
            "dataset": dataset,
            "passed": expected,
            "policy_mode": mode,
            "saved_percentage": saved,
            "expected_reason": reason
        })

    add_check(
        checks,
        "policy_choices_match_v0371_expected_behavior",
        all(item["passed"] for item in policy_details),
        {
            "details": policy_details
        }
    )

    public_text = PUBLIC_REPORT.read_text(encoding="utf-8", errors="ignore").lower()

    forbidden_public_terms = [
        "compressed_package",
        "reconstructed_rows",
        "engine_result_snapshot",
        "internal_rule_data",
        "private_internal",
        "x-prmr-api-key",
        "api_key",
        "secret"
    ]

    found_forbidden = [
        term for term in forbidden_public_terms
        if term in public_text
    ]

    add_check(
        checks,
        "public_report_exposes_no_private_engine_internals",
        len(found_forbidden) == 0,
        {
            "forbidden_terms_found": found_forbidden
        }
    )

    runner_text = RUNNER.read_text(encoding="utf-8", errors="ignore").lower()

    suspicious_patterns = [
        "realistic_memory_trust_score = 100",
        "total = 100",
        "return 100",
        "score = 100"
    ]

    suspicious_found = [
        pattern for pattern in suspicious_patterns
        if pattern in runner_text
    ]

    add_check(
        checks,
        "runner_does_not_appear_to_hardcode_100_score",
        len(suspicious_found) == 0,
        {
            "suspicious_patterns_found": suspicious_found
        }
    )

    all_passed = all(check["passed"] for check in checks)
    passed_count = sum(1 for check in checks if check["passed"])

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.37.1",
        "report_type": "result_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "all_integrity_checks_passed": all_passed,
        "passed_checks": passed_count,
        "total_checks": len(checks),
        "checks": checks,
        "verdict": (
            "V0.37.1 score is internally consistent and supported by reconstruction, compression, policy, and report-safety checks."
            if all_passed
            else "V0.37.1 needs review. One or more integrity checks failed."
        ),
        "note": "This audit verifies benchmark integrity. It does not certify production readiness."
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.37.1 Result Integrity Audit

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.37.1  

## Result

**{passed_count}/{len(checks)} checks passed**

All integrity checks passed: **{all_passed}**

## Verdict

{report["verdict"]}

## Checks

"""

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md += f"- **{status}** — {check['name']}\n"

    md += """

## Important Note

This audit does not mean the product is finished.  
It means the V0.37.1 benchmark result is internally consistent and not obviously fake/hardcoded.

Next phase: V0.38 Baseline War Test.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.37.1 RESULT INTEGRITY AUDIT")
    print("-----------------------------------")
    print("Passed checks:", f"{passed_count}/{len(checks)}")
    print("All integrity checks passed:", all_passed)
    print("Verdict:", report["verdict"])
    print()
    print("Check list:")
    for check in checks:
        status = "PASS [PASS]" if check["passed"] else "FAIL [FAIL]"
        print("-", check["name"] + ":", status)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()
