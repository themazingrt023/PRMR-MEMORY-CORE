import json
import random
import importlib.util
from pathlib import Path
from datetime import datetime

PUBLIC_REPORT = Path("reports/v0381/public_baseline_war_antileak_v0381.json")
PRIVATE_REPORT = Path("reports/v0381/private_internal_baseline_war_antileak_v0381.json")
DATASET_PATH = Path("benchmarks/datasets_v0381/baseline_war_antileak_v0381.json")
RUNNER_PATH = Path("benchmarks/runners/run_baseline_war_antileak_v0381.py")

OUT_DIR = Path("reports/v0382")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "result_integrity_audit_v0382.json"
OUT_MD = OUT_DIR / "result_integrity_audit_v0382.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def load_runner_module():
    spec = importlib.util.spec_from_file_location("v0381_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recompute_scores_from_private_details(private, runner):
    expected = load_json(DATASET_PATH)["expected"]
    recomputed = {}

    for system_name, topic_details in private["details"].items():
        answer = {}

        for topic, detail in topic_details.items():
            answer[topic] = detail["answer"]

        score, _ = runner.judge_answer(answer, expected)
        recomputed[system_name] = score

    return recomputed


def no_complete_answer_leakage(dataset):
    rows = dataset["rows"]
    expected = dataset["expected"]

    leaks = []

    forbidden_complete_keys = [
        "current_state",
        "old_state",
        "problem",
        "latent_risk",
        "lineage_reason"
    ]

    for topic, truth in expected.items():
        truth_values = [
            truth["current_state"],
            truth["old_state"],
            truth["problem"],
            truth["latent_risk"],
            truth["lineage_reason"]
        ]

        for row in rows:
            if row.get("topic") != topic:
                continue

            row_text = json.dumps(row, sort_keys=True)

            contains_all_truth_values = all(value in row_text for value in truth_values)
            contains_forbidden_complete_keys = any(key in row for key in forbidden_complete_keys)

            if contains_all_truth_values or contains_forbidden_complete_keys:
                leaks.append({
                    "topic": topic,
                    "event_id": row.get("event_id"),
                    "contains_all_truth_values": contains_all_truth_values,
                    "contains_forbidden_complete_keys": contains_forbidden_complete_keys,
                    "row": row
                })

    return leaks


def baseline_field_access_is_limited(private):
    baseline_names = [
        "raw_storage",
        "basic_summary",
        "keyword_search",
        "vector_like",
        "mempalace_verbatim"
    ]

    violations = []

    answer_fields = [
        "current_state",
        "old_state",
        "problem",
        "latent_risk",
        "lineage_reason"
    ]

    for baseline in baseline_names:
        topic_details = private["details"].get(baseline, {})

        for topic, detail in topic_details.items():
            answer = detail["answer"]

            filled_fields = [
                field for field in answer_fields
                if answer.get(field) is not None
            ]

            # In V0.38.1, baselines are one-row retrieval simulations.
            # They should not synthesize complete active/latent/lineage packets.
            if len(filled_fields) > 1:
                violations.append({
                    "baseline": baseline,
                    "topic": topic,
                    "filled_fields": filled_fields,
                    "answer": answer
                })

    return violations


def public_report_safety(public_text):
    forbidden_terms = [
        "engine_result_snapshot",
        "reconstructed_rows",
        "compressed_package",
        "internal_rule_data",
        "private_internal",
        "x-prmr-api-key",
        "api_key",
        "secret",
        "protected_note"
    ]

    return [
        term for term in forbidden_terms
        if term in public_text
    ]


def runner_hardcode_scan(runner_text):
    suspicious = [
        "scores[\"prmr\"] = 100",
        "scores['prmr'] = 100",
        "\"prmr\": 100",
        "'prmr': 100",
        "prmr_score = 100",
        "return 100",
        "score = 100"
    ]

    return [
        pattern for pattern in suspicious
        if pattern.lower() in runner_text.lower()
    ]


def shuffle_order_test(runner, dataset):
    rows = list(dataset["rows"])
    expected = dataset["expected"]

    random.seed(382)
    random.shuffle(rows)

    systems = {
        "PRMR": runner.prmr_answer(rows),
        "raw_storage": runner.raw_storage_baseline(rows),
        "basic_summary": runner.summary_baseline(rows),
        "keyword_search": runner.keyword_baseline(rows),
        "vector_like": runner.vector_like_baseline(rows, expected),
        "mempalace_verbatim": runner.mempalace_baseline(rows),
    }

    shuffled_scores = {}

    for name, answer in systems.items():
        score, _ = runner.judge_answer(answer, expected)
        shuffled_scores[name] = score

    best_baseline = max(
        score for name, score in shuffled_scores.items()
        if name != "PRMR"
    )

    return {
        "scores": shuffled_scores,
        "best_baseline": best_baseline,
        "prmr_win_margin": round(shuffled_scores["PRMR"] - best_baseline, 2),
        "pass": shuffled_scores["PRMR"] > best_baseline
    }


def main():
    checks = []

    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)
    dataset = load_json(DATASET_PATH)
    runner = load_runner_module()

    public_text = PUBLIC_REPORT.read_text(encoding="utf-8", errors="ignore")
    runner_text = RUNNER_PATH.read_text(encoding="utf-8", errors="ignore")

    # 1. Recompute scores from private raw answer details.
    recomputed_scores = recompute_scores_from_private_details(private, runner)
    reported_scores = public["scores"]

    score_mismatches = {}

    for system, reported in reported_scores.items():
        recomputed = recomputed_scores.get(system)

        if float(reported) != float(recomputed):
            score_mismatches[system] = {
                "reported": reported,
                "recomputed": recomputed
            }

    add_check(
        checks,
        "scores_recompute_from_raw_private_answer_details",
        len(score_mismatches) == 0,
        {
            "reported_scores": reported_scores,
            "recomputed_scores": recomputed_scores,
            "mismatches": score_mismatches
        }
    )

    # 2. Verify expected answers are not present in one baseline-readable row.
    leaks = no_complete_answer_leakage(dataset)

    add_check(
        checks,
        "expected_answers_not_leaked_into_single_baseline_readable_rows",
        len(leaks) == 0,
        {
            "leak_count": len(leaks),
            "leaks": leaks[:5]
        }
    )

    # 3. Verify baselines only see allowed one-row fragment outputs.
    baseline_violations = baseline_field_access_is_limited(private)

    add_check(
        checks,
        "baselines_only_return_one_row_fragment_fields",
        len(baseline_violations) == 0,
        {
            "violation_count": len(baseline_violations),
            "violations": baseline_violations[:5]
        }
    )

    # 4. Verify PRMR reconstruction and answer output.
    engine_result = private.get("engine_result_snapshot", {})
    results = engine_result.get("results", [])
    reconstructed_rows = results[0]["decision"]["reconstructed_rows"] if results else None

    reconstruction_match = reconstructed_rows == dataset["rows"]

    prmr_answer = {
        topic: detail["answer"]
        for topic, detail in private["details"]["PRMR"].items()
    }

    prmr_recomputed_score, prmr_detail = runner.judge_answer(prmr_answer, dataset["expected"])

    add_check(
        checks,
        "prmr_reconstruction_matches_dataset_and_scores_100",
        reconstruction_match and prmr_recomputed_score == 100.0,
        {
            "reconstruction_match": reconstruction_match,
            "prmr_recomputed_score": prmr_recomputed_score,
            "prmr_detail": prmr_detail
        }
    )

    # 5. Verify public report exposes no private internals.
    forbidden_public = public_report_safety(public_text)

    add_check(
        checks,
        "public_report_exposes_no_private_internals",
        len(forbidden_public) == 0,
        {
            "forbidden_terms_found": forbidden_public
        }
    )

    # 6. Verify no runner hardcodes PRMR = 100.
    hardcoded_patterns = runner_hardcode_scan(runner_text)

    add_check(
        checks,
        "runner_does_not_hardcode_prmr_100",
        len(hardcoded_patterns) == 0,
        {
            "suspicious_patterns_found": hardcoded_patterns
        }
    )

    # 7. Verify changing dataset row order does not break result.
    shuffled = shuffle_order_test(runner, dataset)

    add_check(
        checks,
        "shuffling_dataset_order_does_not_break_baseline_war_result",
        shuffled["pass"] and shuffled["scores"]["PRMR"] == 100.0,
        shuffled
    )

    all_passed = all(check["passed"] for check in checks)
    passed_count = sum(1 for check in checks if check["passed"])

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.38.2",
        "report_type": "baseline_war_result_integrity_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": len(checks),
        "all_integrity_checks_passed": all_passed,
        "checks": checks,
        "verdict": (
            "V0.38.1 Baseline War result is internally consistent, anti-leak validated, not hardcoded, and robust to dataset row ordering."
            if all_passed
            else "V0.38.1 Baseline War result needs review. One or more integrity checks failed."
        ),
        "next_phase": "V0.39 Adversarial Memory Trial"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.38.2 Baseline War Result Integrity Audit

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.38.2  

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

## Meaning

This audit verifies that the V0.38.1 Baseline War result was not simply a fake 100, a hardcoded score, or a leaked-answer benchmark.

It does not mean PRMR is production-certified.

## Next Phase

V0.39 — Adversarial Memory Trial:
contradictions, stale facts, fake updates, duplicated noise, near-miss similar memories, cross-client boundary traps, temporal reversals, and old-state/new-state conflicts.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.38.2 BASELINE WAR RESULT INTEGRITY AUDIT")
    print("------------------------------------------------")
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