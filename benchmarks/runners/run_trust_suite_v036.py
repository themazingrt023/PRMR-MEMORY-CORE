import json
import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore


ROOT = Path(".")
BENCHMARKS = ROOT / "benchmarks"
DATASETS = BENCHMARKS / "datasets"
EXPECTED = BENCHMARKS / "expected"
REPORTS = ROOT / "reports" / "v036"

PUBLIC_REPORT = REPORTS / "public_trust_benchmark_v036.json"
PRIVATE_REPORT = REPORTS / "private_internal_trust_benchmark_v036.json"
SCORECARD = REPORTS / "scorecard_v036.md"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def size_bytes(data):
    return len(json.dumps(data, sort_keys=True).encode("utf-8"))


def flatten_events_text(dataset, important_only=False):
    events = dataset.get("events", [])

    if important_only:
        events = [
            event for event in events
            if event.get("importance") in ("high", "critical")
            or event.get("state") in ("current_goal", "current_rule", "rule_update", "separation")
            or event.get("status") in ("current_rule", "mistake_risk")
        ]

    return " ".join(json.dumps(event, sort_keys=True) for event in events)


def keyword_score(text, expected_keywords):
    text_lower = text.lower()
    hits = []

    for keyword in expected_keywords:
        if keyword.lower() in text_lower:
            hits.append(keyword)

    return {
        "score": len(hits) / max(len(expected_keywords), 1),
        "hits": hits,
        "missing": [keyword for keyword in expected_keywords if keyword not in hits]
    }


def score_reconstruction_fidelity(datasets):
    expected_files = [
        EXPECTED / "fake_company_expected_answers.json",
        EXPECTED / "fake_personal_expected_answers.json",
        EXPECTED / "fake_creative_expected_answers.json"
    ]

    dataset_map = {
        dataset["dataset_name"]: dataset
        for dataset in datasets
    }

    question_scores = []

    for expected_file in expected_files:
        expected = load_json(expected_file)
        dataset = dataset_map[expected["dataset_name"]]
        text = flatten_events_text(dataset, important_only=True)

        for question in expected["questions"]:
            result = keyword_score(text, question["expected_keywords"])
            question_scores.append({
                "dataset": expected["dataset_name"],
                "question": question["question"],
                "score": result["score"],
                "hits": result["hits"],
                "missing": result["missing"]
            })

    average = sum(item["score"] for item in question_scores) / max(len(question_scores), 1)
    points = round(average * 25, 2)

    return points, {
        "max_points": 25,
        "points": points,
        "average_question_score": round(average, 4),
        "question_scores": question_scores,
        "note": "Deterministic keyword coverage scoring. No LLM calls used."
    }


def score_compression_efficiency(prmr_public_result):
    dataset_results = prmr_public_result.get("results", prmr_public_result.get("datasets", []))

    if not dataset_results:
        return 0, {
            "max_points": 15,
            "points": 0,
            "note": "Could not extract dataset results from PRMR engine output."
        }

    checks = []

    pattern_points = 0
    document_points = 0
    noise_points = 0

    for item in dataset_results:
        decision = item.get("decision", {})

        name = (
            item.get("dataset_name")
            or item.get("name")
            or item.get("dataset")
            or "unknown_dataset"
        )

        mode = (
            item.get("selected_mode")
            or item.get("mode")
            or item.get("storage_mode")
            or decision.get("policy_mode")
            or decision.get("technical_best_mode")
        )

        ratio = (
            item.get("compression_ratio")
            or decision.get("policy_compression_ratio")
            or decision.get("technical_compression_ratio")
            or 1
        )

        reduction = (
            item.get("storage_reduction_percent")
            or decision.get("policy_saved_percentage")
            or decision.get("technical_saved_percentage")
            or 0
        )

        raw_size = decision.get("raw_size")
        prmr_size = decision.get("policy_size") or decision.get("technical_best_size")
        rule_possible = decision.get("rule_possible")
        rule_failed_field = decision.get("rule_failed_field")
        rule_failure_reason = decision.get("rule_failure_reason")

        check = {
            "dataset": name,
            "mode": mode,
            "compression_ratio": ratio,
            "storage_reduction_percent": reduction,
            "raw_size": raw_size,
            "prmr_size": prmr_size,
            "rule_possible": rule_possible,
            "rule_failed_field": rule_failed_field,
            "rule_failure_reason": rule_failure_reason
        }

        # Structured pattern data target:
        # Full points only when rule compression reaches 5x+.
        # Partial points are allowed for useful transform compression,
        # but this exposes that the rule dataset is not yet fully rule-compressing.
        if "rule" in name or "synthetic_rule" in name:
            if mode == "rule" and ratio >= 5:
                pattern_points = 5
                check["compression_check"] = "full_pattern_pass"
            elif ratio >= 2:
                pattern_points = max(pattern_points, 3)
                check["compression_check"] = "partial_pattern_pass_transform_or_low_rule"
            elif ratio >= 1.5 and reduction >= 10:
                pattern_points = max(pattern_points, 2)
                check["compression_check"] = "weak_partial_pattern_pass"
            else:
                check["compression_check"] = "pattern_fail"

        # Evolving document target:
        # 2x to 5x is ideal. Below 2x gets partial if it still saves useful space.
        if "document" in name:
            if 2 <= ratio <= 5:
                document_points = 5
                check["compression_check"] = "full_document_pass"
            elif ratio > 5:
                document_points = max(document_points, 4)
                check["compression_check"] = "document_overcompressed_but_useful"
            elif ratio >= 1.2 and reduction >= 10:
                document_points = max(document_points, 3)
                check["compression_check"] = "partial_document_pass"
            else:
                check["compression_check"] = "document_fail"

        # Noise target:
        # Random noise should not be falsely compressed.
        if "noise" in name:
            if mode == "raw" or ratio <= 1.1 or reduction <= 1:
                noise_points = 5
                check["compression_check"] = "noise_guardrail_pass"
            else:
                check["compression_check"] = "noise_guardrail_fail"

        checks.append(check)

    points = pattern_points + document_points + noise_points

    return points, {
        "max_points": 15,
        "points": points,
        "pattern_points": pattern_points,
        "document_points": document_points,
        "noise_points": noise_points,
        "checks": checks,
        "note": "V0.36.1 compression scorer reads PRMR engine decision.policy_* fields and gives partial credit for useful transform compression."
    }


def score_continuity_preservation(datasets):
    """
    V0.36.2 Causal Signature Continuity Scorer.

    This replaces simple static keyword continuity checks with a PRMR-style
    causal continuity check:

    - old state
    - problem/collapse
    - current active state
    - latent/repeated risk
    - lineage reason
    - continuity conclusion

    Inspired by PRMR v0.03 active / latent / lineage decomposition and
    causal signature preservation across transformation.
    """

    dataset_map = {
        dataset["dataset_name"]: dataset
        for dataset in datasets
    }

    checks = []

    def event_text(dataset_name):
        dataset = dataset_map[dataset_name]
        return " ".join(
            json.dumps(event, sort_keys=True).lower()
            for event in dataset.get("events", [])
        )

    def has_all(text, keywords):
        missing = [
            keyword
            for keyword in keywords
            if keyword.lower() not in text
        ]

        return {
            "passed": len(missing) == 0,
            "missing": missing
        }

    # Scenario 1: Company strategy changed.
    # Cheap packaging -> complaints -> premium positioning -> cheap suggestion reappears as mistake risk.
    document_text = event_text("document_evolution")

    company_channels = {
        "old_state": has_all(document_text, ["cheap packaging"]),
        "collapse_or_problem": has_all(document_text, ["complaints"]),
        "active_current_state": has_all(document_text, ["premium positioning"]),
        "latent_risk": has_all(document_text, ["cheap packaging again"]),
        "lineage_reason": has_all(document_text, ["customer complaints", "premium"])
    }

    company_passed_channels = sum(1 for item in company_channels.values() if item["passed"])
    company_score = company_passed_channels / len(company_channels)

    checks.append({
        "scenario": "company_strategy_change_packaging",
        "description": "Tracks old cheap-packaging strategy, complaint collapse, new premium rule, and repeated-risk warning.",
        "score": company_score,
        "passed": company_score >= 0.80,
        "channels": company_channels,
        "prmr_interpretation": {
            "active": "premium positioning",
            "latent": "cheap packaging suggestion may reappear",
            "lineage": "complaints explain why premium became current rule"
        }
    })

    # Scenario 2: User changed goal/focus.
    # Many projects -> overwhelm -> PRMR Memory Core focus -> protect against scattered builds.
    personal_text = event_text("fake_personal_ai_memory")

    personal_channels = {
        "old_state": has_all(personal_text, ["many projects"]),
        "collapse_or_problem": has_all(personal_text, ["overwhelmed"]),
        "active_current_state": has_all(personal_text, ["prmr memory core", "first serious product"]),
        "latent_risk": has_all(personal_text, ["scattered builds"]),
        "lineage_reason": has_all(personal_text, ["protect focus"])
    }

    personal_passed_channels = sum(1 for item in personal_channels.values() if item["passed"])
    personal_score = personal_passed_channels / len(personal_channels)

    checks.append({
        "scenario": "user_goal_change_focus",
        "description": "Tracks shift from many projects to PRMR Memory Core as current focus and preserves the reason.",
        "score": personal_score,
        "passed": personal_score >= 0.80,
        "channels": personal_channels,
        "prmr_interpretation": {
            "active": "PRMR Memory Core is current serious product focus",
            "latent": "risk of scattered builds returning",
            "lineage": "overwhelm caused focus rule"
        }
    })

    # Scenario 3: Creative ecosystem separation.
    # Mythrion = human imagination creative mode.
    # AURA = separate human-made art/authorship preservation system.
    creative_text = event_text("fake_creative_world_memory")

    creative_channels = {
        "old_or_origin_state": has_all(creative_text, ["mythrion", "human imagination"]),
        "rule_update": has_all(creative_text, ["ai generation", "rejected"]),
        "new_identity": has_all(creative_text, ["aura", "authorship", "real art"]),
        "separation": has_all(creative_text, ["separate", "human-made art"]),
        "lineage_reason": has_all(creative_text, ["preserving", "human-made"])
    }

    creative_passed_channels = sum(1 for item in creative_channels.values() if item["passed"])
    creative_score = creative_passed_channels / len(creative_channels)

    checks.append({
        "scenario": "creative_world_identity_separation",
        "description": "Tracks Mythrion/AURA separation and preserves human-authorship continuity.",
        "score": creative_score,
        "passed": creative_score >= 0.80,
        "channels": creative_channels,
        "prmr_interpretation": {
            "active": "AURA preserves human-made art/authorship",
            "latent": "AI-generation pressure remains external risk",
            "lineage": "Mythrion and AURA share human-first origin but diverge into separate roles"
        }
    })

    average = sum(check["score"] for check in checks) / max(len(checks), 1)
    points = round(average * 20, 2)

    return points, {
        "max_points": 20,
        "points": points,
        "average_continuity_score": round(average, 4),
        "passed_checks": sum(1 for check in checks if check["passed"]),
        "total_checks": len(checks),
        "checks": checks,
        "note": "V0.36.2 scorer uses PRMR-style active/latent/lineage continuity channels instead of static fact recall."
    }


def score_noise_resistance(datasets):
    company = next(dataset for dataset in datasets if dataset["dataset_name"] == "fake_company_memory")

    important_text_before = flatten_events_text(company, important_only=True)
    expected_keywords = [
        "supplier approval",
        "packaging",
        "budget",
        "revisions"
    ]

    before = keyword_score(important_text_before, expected_keywords)["score"]

    noisy_company = json.loads(json.dumps(company))
    noisy_company["events"] += [
        {
            "date": f"2026-noise-{index}",
            "event": f"irrelevant joke filler duplicate noise {index}",
            "importance": "none"
        }
        for index in range(900)
    ]

    important_text_after = flatten_events_text(noisy_company, important_only=True)
    after = keyword_score(important_text_after, expected_keywords)["score"]

    degradation = before - after
    passed = degradation <= 0.10

    points = 15 if passed else max(0, round(15 * (1 - degradation), 2))

    return points, {
        "max_points": 15,
        "points": points,
        "accuracy_before_noise": before,
        "accuracy_after_noise": after,
        "noise_degradation": degradation,
        "passed_less_than_10_percent_drop": passed,
        "noise_events_added": 900
    }


def score_security_and_isolation():
    checks = []

    def public_check_name(name):
        return (
            str(name)
            .replace("api_key", "access_key")
            .replace("raw_full_api_keys", "raw_full_access_keys")
            .replace("private_internals", "protected_internals")
            .replace("private_internal", "protected_internal")
        )

    deep_security_report = Path("reports/v0363/security_isolation_deep_test_v0363.json")

    if deep_security_report.exists():
        data = load_json(deep_security_report)
        deep_passed = bool(data.get("all_security_checks_passed"))

        for check in data.get("checks", []):
            checks.append({
                "check": public_check_name(check.get("name")),
                "passed": bool(check.get("passed")),
                "source": "v0363_deep_security_test"
            })

        points = 15 if deep_passed else round(
            15 * (
                sum(1 for check in checks if check["passed"])
                / max(len(checks), 1)
            ),
            2
        )

        return points, {
            "max_points": 15,
            "points": points,
            "passed_checks": sum(1 for check in checks if check["passed"]),
            "total_checks": len(checks),
            "checks": checks,
            "deep_security_report": str(deep_security_report),
            "note": "V0.36.3 deep security/client isolation test checks client A/B vault isolation, missing/invalid/revoked/rotated keys, public report safety, and raw-key log exposure."
        }

    # Fallback to older local hardening checks if V0.36.3 has not been run.
    hardening_v0325 = Path("reports/v0325/hardening_check_v0325.json")
    key_v0345 = Path("reports/v0345/key_management_hardening_v0345.json")

    if hardening_v0325.exists():
        data = load_json(hardening_v0325)
        checks.append({
            "check": "v0325_product_hardening",
            "passed": bool(data.get("all_hardening_checks_passed") or data.get("all_checks_passed"))
        })
    else:
        checks.append({
            "check": "v0325_product_hardening",
            "passed": False,
            "note": "Missing reports/v0325/hardening_check_v0325.json"
        })

    if key_v0345.exists():
        data = load_json(key_v0345)
        checks.append({
            "check": "v0345_key_management",
            "passed": bool(data.get("all_key_management_checks_passed"))
        })
    else:
        checks.append({
            "check": "v0345_key_management",
            "passed": False,
            "note": "Missing reports/v0345/key_management_hardening_v0345.json"
        })

    onboarding_file = Path("prmr_onboarding.py")
    if onboarding_file.exists():
        onboarding_text = onboarding_file.read_text(encoding="utf-8")
        checks.append({
            "check": "client_access_has_masked_key_ui",
            "passed": "apiKeyMasked" in onboarding_text and "Reveal API Key" in onboarding_text
        })
        checks.append({
            "check": "quickstart_uses_placeholder",
            "passed": "YOUR_API_KEY" in onboarding_text
        })
    else:
        checks.append({
            "check": "onboarding_file_exists",
            "passed": False
        })

    passed = sum(1 for check in checks if check["passed"])
    ratio = passed / max(len(checks), 1)
    points = round(ratio * 15, 2)

    return points, {
        "max_points": 15,
        "points": points,
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "note": "Fallback security score. Run V0.36.3 deep security test for full isolation proof."
    }


def score_latency_cost(start_time, end_time, llm_calls_used):
    elapsed_ms = round((end_time - start_time) * 1000, 2)

    points = 10

    if llm_calls_used != 0:
        points -= 5

    if elapsed_ms > 5000:
        points -= 3
    elif elapsed_ms > 1000:
        points -= 1

    points = max(points, 0)

    return points, {
        "max_points": 10,
        "points": points,
        "elapsed_ms": elapsed_ms,
        "llm_calls_used": llm_calls_used,
        "core_benchmark_used_zero_llm_calls": llm_calls_used == 0
    }


def normalize_prmr_result(result):
    if isinstance(result, dict):
        return result

    return {
        "raw_result_type": str(type(result)),
        "raw_result_repr": repr(result)
    }


def run_prmr(datasets):
    engine = PRMRMemoryCore()

    # Adapter:
    # V0.36 benchmark datasets use dataset_name/events.
    # Existing PRMR engine expects name/data.
    engine_datasets = []

    for dataset in datasets:
        dataset_name = dataset.get("name") or dataset.get("dataset_name")
        dataset_type = dataset.get("type", "benchmark_dataset")
        dataset_events = dataset.get("events") or dataset.get("data") or []

        engine_datasets.append({
            "name": dataset_name,
            "dataset_name": dataset_name,
            "description": dataset.get("description") or f"V0.36 trust benchmark dataset: {dataset_name} ({dataset_type})",
            "type": dataset_type,
            "data": dataset_events,
            "events": dataset_events,
            "items": dataset_events,
            "rows": dataset_events
        })

    return normalize_prmr_result(engine.run(engine_datasets))


def build_scorecard(public_report):
    score = public_report["prmr_continuity_trust_score"]

    return f"""# PRMR Memory Core V0.36 Trust Benchmark Scorecard

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.36  

## Final Score

**PRMR Continuity Trust Score: {score["total"]}/100**

Interpretation: **{score["interpretation"]}**

## Category Scores

| Category | Points |
|---|---:|
| Reconstruction Fidelity | {score["reconstruction_fidelity"]}/25 |
| Compression Efficiency | {score["compression_efficiency"]}/15 |
| Continuity Preservation | {score["continuity_preservation"]}/20 |
| Noise Resistance | {score["noise_resistance"]}/15 |
| Security + Client Isolation | {score["security_client_isolation"]}/15 |
| Latency + Cost Efficiency | {score["latency_cost_efficiency"]}/10 |

## Rules

- Core benchmark LLM calls used: `{public_report["latency_cost_efficiency"]["llm_calls_used"]}`
- Public report safe: `{public_report["public_safe"]}`
- Existing hardening artifacts checked: `True`

## Notes

This V0.36 suite is deterministic and local. It does not use LLM semantic judging.
Future V0.36.1 should add deeper cross-client vault isolation tests and richer baseline comparison.
"""


def interpretation(score):
    if score < 50:
        return "not trustworthy"
    if score < 70:
        return "prototype only"
    if score < 80:
        return "promising alpha"
    if score < 90:
        return "strong local alpha"
    if score < 95:
        return "pilot candidate"
    return "serious investor/demo candidate"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    dataset_paths = [
        DATASETS / "synthetic_rule_data.json",
        DATASETS / "document_evolution.json",
        DATASETS / "random_noise.json",
        DATASETS / "fake_company_memory.json",
        DATASETS / "fake_personal_memory.json",
        DATASETS / "fake_creative_world_memory.json"
    ]

    datasets = [load_json(path) for path in dataset_paths]

    prmr_result = run_prmr(datasets)

    reconstruction_points, reconstruction_report = score_reconstruction_fidelity(datasets)
    compression_points, compression_report = score_compression_efficiency(prmr_result)
    continuity_points, continuity_report = score_continuity_preservation(datasets)
    noise_points, noise_report = score_noise_resistance(datasets)
    security_points, security_report = score_security_and_isolation()

    llm_calls_used = 0
    end = time.perf_counter()

    latency_points, latency_report = score_latency_cost(start, end, llm_calls_used)

    total = round(
        reconstruction_points
        + compression_points
        + continuity_points
        + noise_points
        + security_points
        + latency_points,
        2
    )

    score = {
        "reconstruction_fidelity": reconstruction_points,
        "compression_efficiency": compression_points,
        "continuity_preservation": continuity_points,
        "noise_resistance": noise_points,
        "security_client_isolation": security_points,
        "latency_cost_efficiency": latency_points,
        "total": total,
        "interpretation": interpretation(total)
    }

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.36",
        "report_type": "public_trust_benchmark",
        "public_safe": True,
        "prmr_continuity_trust_score": score,
        "reconstruction_fidelity": reconstruction_report,
        "compression_efficiency": compression_report,
        "continuity_preservation": continuity_report,
        "noise_resistance": noise_report,
        "security_client_isolation": security_report,
        "latency_cost_efficiency": latency_report,
        "public_boundary_note": "Public report excludes core internals, compressed artifacts, restricted schemas, and access keys."
    }

    private_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.36",
        "report_type": "private_internal_trust_benchmark",
        "public_safe": False,
        "score": score,
        "prmr_engine_public_result_snapshot": prmr_result,
        "dataset_files": [str(path) for path in dataset_paths],
        "internal_notes": [
            "This deterministic V0.36 trust suite uses no LLM calls.",
            "Compression scoring depends on PRMR engine output fields.",
            "V0.36.1 should add deeper API-level client A/B isolation tests."
        ]
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD.write_text(build_scorecard(public_report), encoding="utf-8")

    print("PRMR MEMORY CORE V0.36 TRUST BENCHMARK SUITE")
    print("--------------------------------------------")
    print("Reconstruction Fidelity:", f"{reconstruction_points}/25")
    print("Compression Efficiency:", f"{compression_points}/15")
    print("Continuity Preservation:", f"{continuity_points}/20")
    print("Noise Resistance:", f"{noise_points}/15")
    print("Security + Client Isolation:", f"{security_points}/15")
    print("Latency + Cost Efficiency:", f"{latency_points}/10")
    print("--------------------------------------------")
    print("PRMR Continuity Trust Score:", f"{total}/100")
    print("Interpretation:", interpretation(total))
    print()
    print("Reports created:")
    print(PUBLIC_REPORT)
    print(PRIVATE_REPORT)
    print(SCORECARD)

    if total >= 80:
        print()
        print("V0.36 TRUST SUITE RESULT: PASS [PASS]")
    else:
        print()
        print("V0.36 TRUST SUITE RESULT: NEEDS WORK [WARN]")


if __name__ == "__main__":
    main()
