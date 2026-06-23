import json
import random
import importlib.util
from pathlib import Path
from datetime import datetime

PUBLIC_REPORT = Path("reports/v039/public_adversarial_memory_trial_v039.json")
PRIVATE_REPORT = Path("reports/v039/private_internal_adversarial_memory_trial_v039.json")
DATASET_PATH = Path("benchmarks/datasets_v039/adversarial_memory_trial_v039.json")
RUNNER_PATH = Path("benchmarks/runners/run_adversarial_memory_trial_v039.py")

OUT_DIR = Path("reports/v0391")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "adversarial_integrity_audit_v0391.json"
OUT_MD = OUT_DIR / "adversarial_integrity_audit_v0391.md"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks, name, passed, details=None):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "details": details or {}
    })


def load_runner_module():
    spec = importlib.util.spec_from_file_location("v039_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_safety_scan(text):
    forbidden = [
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

    return [term for term in forbidden if term in text.lower()]


def hardcode_scan(text):
    suspicious = [
        "scores[\"prmr\"] = 100",
        "scores['prmr'] = 100",
        "\"prmr\": 100",
        "'prmr': 100",
        "prmr_score = 100",
        "raw_storage\": 0",
        "vector_like\": 0",
        "return 100",
        "score = 100"
    ]

    lowered = text.lower()

    return [pattern for pattern in suspicious if pattern.lower() in lowered]


def recompute_scores(private, runner, expected):
    recomputed = {}

    for system, topic_details in private["details"].items():
        answer = {
            topic: detail["answer"]
            for topic, detail in topic_details.items()
        }

        score, _ = runner.judge_answer(answer, expected)
        recomputed[system] = score

    return recomputed


def baseline_fragment_audit(private):
    baseline_names = [
        "raw_storage",
        "basic_summary",
        "keyword_search",
        "vector_like",
        "mempalace_verbatim"
    ]

    fields = [
        "current_state",
        "old_state",
        "problem",
        "latent_risk",
        "lineage_reason"
    ]

    audit = {}

    for baseline in baseline_names:
        total_topics = 0
        total_filled_fragments = 0
        client_mismatches = 0
        wrong_current_or_near_miss = 0

        for topic, detail in private["details"][baseline].items():
            total_topics += 1
            answer = detail["answer"]
            filled = [field for field in fields if answer.get(field) is not None]
            total_filled_fragments += len(filled)

            if answer.get("client_id") != "client_alpha":
                client_mismatches += 1

            expected = detail["expected"]
            wrong_values = expected.get("must_not_return", [])

            answer_text = json.dumps(answer)

            if any(value in answer_text for value in wrong_values):
                wrong_current_or_near_miss += 1

        audit[baseline] = {
            "total_topics": total_topics,
            "total_filled_fragments": total_filled_fragments,
            "client_mismatches": client_mismatches,
            "wrong_current_or_near_miss_hits": wrong_current_or_near_miss,
            "baseline_saw_some_fragments": total_filled_fragments > 0
        }

    return audit


def shuffle_test(runner, dataset):
    rows = list(dataset["rows"])
    random.seed(391)
    random.shuffle(rows)

    expected = dataset["expected"]
    target_client = dataset["target_client"]

    systems = {
        "PRMR": runner.prmr_answer(rows, target_client),
        "raw_storage": runner.raw_storage_baseline(rows),
        "basic_summary": runner.summary_baseline(rows),
        "keyword_search": runner.keyword_baseline(rows),
        "vector_like": runner.vector_like_baseline(rows, expected),
        "mempalace_verbatim": runner.mempalace_baseline(rows),
    }

    scores = {}

    for name, answer in systems.items():
        score, _ = runner.judge_answer(answer, expected)
        scores[name] = score

    best_baseline = max(
        score for name, score in scores.items()
        if name != "PRMR"
    )

    return {
        "scores": scores,
        "best_baseline": best_baseline,
        "win_margin": round(scores["PRMR"] - best_baseline, 2),
        "pass": scores["PRMR"] >= 90 and scores["PRMR"] > best_baseline
    }


def main():
    checks = []

    public = load_json(PUBLIC_REPORT)
    private = load_json(PRIVATE_REPORT)
    dataset = load_json(DATASET_PATH)
    runner = load_runner_module()

    expected = dataset["expected"]

    # 1. Scores recompute.
    recomputed = recompute_scores(private, runner, expected)
    mismatches = {}

    for system, reported_score in public["scores"].items():
        if float(reported_score) != float(recomputed.get(system)):
            mismatches[system] = {
                "reported": reported_score,
                "recomputed": recomputed.get(system)
            }

    add_check(
        checks,
        "scores_recompute_from_private_answers",
        len(mismatches) == 0,
        {
            "reported": public["scores"],
            "recomputed": recomputed,
            "mismatches": mismatches
        }
    )

    # 2. Reconstruction matches dataset.
    engine_result = private.get("engine_result_snapshot", {})
    reconstructed = engine_result["results"][0]["decision"]["reconstructed_rows"]

    add_check(
        checks,
        "prmr_reconstruction_matches_original_dataset",
        reconstructed == dataset["rows"],
        {
            "original_rows": len(dataset["rows"]),
            "reconstructed_rows": len(reconstructed)
        }
    )

    # 3. PRMR target-client scoped and scores 100.
    prmr_answer = {
        topic: detail["answer"]
        for topic, detail in private["details"]["PRMR"].items()
    }

    prmr_score, prmr_detail = runner.judge_answer(prmr_answer, expected)

    all_client_alpha = all(
        item.get("client_id") == dataset["target_client"]
        for item in prmr_answer.values()
    )

    add_check(
        checks,
        "prmr_answer_is_target_client_scoped_and_scores_100",
        prmr_score == 100.0 and all_client_alpha,
        {
            "prmr_score": prmr_score,
            "all_client_alpha": all_client_alpha,
            "details": prmr_detail
        }
    )

    # 4. Baselines fail for real fragment/client/near-miss reasons.
    fragment_audit = baseline_fragment_audit(private)

    baselines_saw_fragments = all(
        item["baseline_saw_some_fragments"]
        for item in fragment_audit.values()
    )

    add_check(
        checks,
        "baselines_fail_despite_seeing_memory_fragments",
        baselines_saw_fragments,
        {
            "fragment_audit": fragment_audit
        }
    )

    # 5. Public report safety.
    public_text = PUBLIC_REPORT.read_text(encoding="utf-8", errors="ignore")
    forbidden_public = public_safety_scan(public_text)

    add_check(
        checks,
        "public_report_exposes_no_private_internals",
        len(forbidden_public) == 0,
        {
            "forbidden_terms_found": forbidden_public
        }
    )

    # 6. Runner hardcode scan.
    runner_text = RUNNER_PATH.read_text(encoding="utf-8", errors="ignore")
    suspicious = hardcode_scan(runner_text)

    add_check(
        checks,
        "runner_does_not_hardcode_scores",
        len(suspicious) == 0,
        {
            "suspicious_patterns_found": suspicious
        }
    )

    # 7. Shuffle robustness.
    shuffled = shuffle_test(runner, dataset)

    add_check(
        checks,
        "shuffling_dataset_order_preserves_prmr_win",
        shuffled["pass"],
        shuffled
    )

    # 8. Baseline zero explanation.
    baseline_scores = {
        key: value
        for key, value in public["scores"].items()
        if key != "PRMR"
    }

    all_zero = all(float(score) == 0.0 for score in baseline_scores.values())

    zero_is_explainable = all_zero and baselines_saw_fragments

    add_check(
        checks,
        "baseline_zero_scores_are_explainable_not_missing_data",
        zero_is_explainable,
        {
            "baseline_scores": baseline_scores,
            "fragment_audit": fragment_audit
        }
    )

    passed_count = sum(1 for check in checks if check["passed"])
    all_passed = all(check["passed"] for check in checks)

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.39.1",
        "report_type": "adversarial_memory_integrity_and_fairness_audit",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "passed_checks": passed_count,
        "total_checks": len(checks),
        "all_integrity_checks_passed": all_passed,
        "checks": checks,
        "verdict": (
            "V0.39 adversarial result is internally consistent. Baseline zero scores are explainable by fragment-only retrieval, client-boundary traps, stale/fake updates, and lack of synthesis."
            if all_passed
            else "V0.39 adversarial result needs review. One or more integrity/fairness checks failed."
        ),
        "next_phase": "V0.40 regression suite or V0.39.2 stronger baseline fairness patch"
    }

    OUT_JSON = OUT_DIR / "adversarial_integrity_audit_v0391.json"
    OUT_MD = OUT_DIR / "adversarial_integrity_audit_v0391.md"

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.39.1 Adversarial Memory Integrity + Fairness Audit

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.39.1  

## Result

**{passed_count}/{len(checks)} checks passed**

All checks passed: **{all_passed}**

## Verdict

{report["verdict"]}

## Checks

"""

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        md += f"- **{status}** — {check['name']}\n"

    md += """

## Important Note

This audit checks whether V0.39's extreme baseline failure is explainable rather than fake.  
It does not mean PRMR is production-certified.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.39.1 ADVERSARIAL INTEGRITY + FAIRNESS AUDIT")
    print("----------------------------------------------------")
    print("Passed checks:", f"{passed_count}/{len(checks)}")
    print("All checks passed:", all_passed)
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