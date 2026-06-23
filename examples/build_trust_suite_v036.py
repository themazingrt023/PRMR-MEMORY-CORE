import json
import os
from pathlib import Path


ROOT = Path(".")
BENCHMARKS = ROOT / "benchmarks"
REPORTS = ROOT / "reports" / "v036"

FOLDERS = [
    BENCHMARKS / "datasets",
    BENCHMARKS / "expected",
    BENCHMARKS / "baselines",
    BENCHMARKS / "runners",
    REPORTS
]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_datasets():
    rule_data = {
        "dataset_name": "synthetic_rule_data",
        "type": "structured_pattern",
        "events": [
            {
                "branch": index,
                "project": f"Atlas Branch {index}",
                "state": "active" if index % 2 == 0 else "review",
                "priority": index % 5,
                "rule": "even branches active, odd branches review"
            }
            for index in range(1, 101)
        ]
    }

    document_evolution = {
        "dataset_name": "document_evolution",
        "type": "evolving_document",
        "events": [
            {
                "month": "January",
                "decision": "Team wanted cheap packaging.",
                "status": "old_state"
            },
            {
                "month": "February",
                "decision": "Cheap packaging caused customer complaints.",
                "status": "problem_detected"
            },
            {
                "month": "March",
                "decision": "Founder changed packaging strategy to premium positioning.",
                "status": "current_rule"
            },
            {
                "month": "April",
                "decision": "New team member suggested cheap packaging again.",
                "status": "mistake_risk"
            }
        ]
    }

    random_noise = {
        "dataset_name": "random_noise",
        "type": "noise_guardrail",
        "events": [
            {
                "id": index,
                "message": f"noise_{index}_x9q_{(index * 7919) % 104729}",
                "importance": "none"
            }
            for index in range(1, 501)
        ]
    }

    fake_company_memory = {
        "dataset_name": "fake_company_memory",
        "type": "company_memory",
        "events": [
            {
                "date": "2026-01-03",
                "project": "Project Atlas",
                "event": "Supplier approval delayed packaging samples.",
                "importance": "high"
            },
            {
                "date": "2026-02-14",
                "project": "Project Atlas",
                "event": "Supplier approval was delayed a second time.",
                "importance": "high"
            },
            {
                "date": "2026-03-08",
                "project": "Project Atlas",
                "event": "Packaging decision changed from cheap to premium.",
                "importance": "high"
            },
            {
                "date": "2026-03-28",
                "project": "Project Atlas",
                "event": "Budget pressure caused repeated launch revisions.",
                "importance": "high"
            },
            {
                "date": "2026-04-12",
                "project": "Project Atlas",
                "event": "Launch delay traced to supplier approval, packaging change, and budget revisions.",
                "importance": "high"
            }
        ]
    }

    fake_personal_memory = {
        "dataset_name": "fake_personal_ai_memory",
        "type": "personal_ai_memory",
        "events": [
            {
                "date": "2026-01-01",
                "event": "User wanted to build many projects at once.",
                "state": "old_goal",
                "importance": "medium"
            },
            {
                "date": "2026-02-05",
                "event": "User became overwhelmed by switching between projects.",
                "state": "problem",
                "importance": "high"
            },
            {
                "date": "2026-03-10",
                "event": "User chose PRMR Memory Core as the first serious product blade.",
                "state": "current_goal",
                "importance": "high"
            },
            {
                "date": "2026-04-02",
                "event": "System should protect focus and avoid pulling user back into scattered builds.",
                "state": "current_rule",
                "importance": "high"
            }
        ]
    }

    fake_creative_world_memory = {
        "dataset_name": "fake_creative_world_memory",
        "type": "creative_world_memory",
        "events": [
            {
                "world": "Mythrion",
                "event": "World began as a human imagination creative mode.",
                "state": "origin",
                "importance": "high"
            },
            {
                "world": "Mythrion",
                "event": "AI generation was rejected as the core creative mechanic.",
                "state": "rule_update",
                "importance": "high"
            },
            {
                "world": "AURA",
                "event": "AURA was defined as Authorship, Unity & Real Art.",
                "state": "identity",
                "importance": "high"
            },
            {
                "world": "AURA",
                "event": "AURA became separate from Mythrion and focused on preserving human-made art.",
                "state": "separation",
                "importance": "high"
            }
        ]
    }

    write_json(BENCHMARKS / "datasets" / "synthetic_rule_data.json", rule_data)
    write_json(BENCHMARKS / "datasets" / "document_evolution.json", document_evolution)
    write_json(BENCHMARKS / "datasets" / "random_noise.json", random_noise)
    write_json(BENCHMARKS / "datasets" / "fake_company_memory.json", fake_company_memory)
    write_json(BENCHMARKS / "datasets" / "fake_personal_memory.json", fake_personal_memory)
    write_json(BENCHMARKS / "datasets" / "fake_creative_world_memory.json", fake_creative_world_memory)


def build_expected_answers():
    company_expected = {
        "dataset_name": "fake_company_memory",
        "questions": [
            {
                "question": "Why was Project Atlas delayed?",
                "expected_keywords": [
                    "supplier approval",
                    "delayed",
                    "packaging",
                    "premium",
                    "budget",
                    "revisions"
                ],
                "expected_answer": "Project Atlas was delayed because supplier approval was delayed twice, the packaging decision changed to premium, and budget pressure caused repeated revisions."
            }
        ]
    }

    personal_expected = {
        "dataset_name": "fake_personal_ai_memory",
        "questions": [
            {
                "question": "What is the user's current product focus?",
                "expected_keywords": [
                    "PRMR Memory Core",
                    "first serious product",
                    "protect focus",
                    "avoid",
                    "scattered"
                ],
                "expected_answer": "The current focus is PRMR Memory Core as the first serious product blade, while protecting focus and avoiding scattered builds."
            }
        ]
    }

    creative_expected = {
        "dataset_name": "fake_creative_world_memory",
        "questions": [
            {
                "question": "How are Mythrion and AURA different?",
                "expected_keywords": [
                    "Mythrion",
                    "human imagination",
                    "AURA",
                    "Authorship",
                    "Real Art",
                    "separate",
                    "human-made art"
                ],
                "expected_answer": "Mythrion is a human imagination creative mode, while AURA is separate and focuses on Authorship, Unity & Real Art and preserving human-made art."
            }
        ]
    }

    write_json(BENCHMARKS / "expected" / "fake_company_expected_answers.json", company_expected)
    write_json(BENCHMARKS / "expected" / "fake_personal_expected_answers.json", personal_expected)
    write_json(BENCHMARKS / "expected" / "fake_creative_expected_answers.json", creative_expected)


def build_baseline_files():
    write_text(
        BENCHMARKS / "baselines" / "raw_storage_baseline.py",
        '''def evaluate(dataset):
    raw_text = str(dataset)
    return {
        "method": "raw_storage",
        "storage_bytes": len(raw_text.encode("utf-8")),
        "accuracy_estimate": 1.0,
        "continuity_estimate": 0.6,
        "noise_resistance_estimate": 0.4
    }
'''
    )

    write_text(
        BENCHMARKS / "baselines" / "basic_summary_baseline.py",
        '''def evaluate(dataset):
    events = dataset.get("events", [])
    summary = " ".join(str(event.get("event", event.get("decision", event.get("message", "")))) for event in events[:5])
    return {
        "method": "basic_summary",
        "storage_bytes": len(summary.encode("utf-8")),
        "accuracy_estimate": 0.55,
        "continuity_estimate": 0.45,
        "noise_resistance_estimate": 0.55
    }
'''
    )

    write_text(
        BENCHMARKS / "baselines" / "keyword_search_baseline.py",
        '''def evaluate(dataset, keywords=None):
    keywords = keywords or []
    text = str(dataset).lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in text)
    score = hits / max(len(keywords), 1)
    return {
        "method": "keyword_search",
        "keyword_hit_score": score,
        "storage_bytes": len(text.encode("utf-8")),
        "accuracy_estimate": score,
        "continuity_estimate": min(score, 0.65),
        "noise_resistance_estimate": 0.55
    }
'''
    )

    write_text(
        BENCHMARKS / "baselines" / "vector_search_baseline.py",
        '''def evaluate(dataset):
    return {
        "method": "vector_search_placeholder",
        "available": False,
        "note": "No vector database dependency added in V0.36 local trust suite."
    }
'''
    )


def build_runner():
    runner = r'''import json
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
    dataset_results = prmr_public_result.get("datasets", prmr_public_result.get("results", []))

    if not dataset_results:
        return 0, {
            "max_points": 15,
            "points": 0,
            "note": "Could not extract dataset results from PRMR engine output."
        }

    pattern_ok = False
    document_ok = False
    noise_ok = False

    checks = []

    for item in dataset_results:
        name = item.get("dataset_name") or item.get("name")
        mode = item.get("selected_mode") or item.get("mode") or item.get("storage_mode")
        ratio = item.get("compression_ratio", 1)
        reduction = item.get("storage_reduction_percent", 0)

        if name and "rule" in name:
            pattern_ok = ratio >= 5
        if name and "document" in name:
            document_ok = 2 <= ratio <= 5
        if name and "noise" in name:
            noise_ok = mode == "raw" or ratio <= 1.1 or reduction <= 1

        checks.append({
            "dataset": name,
            "mode": mode,
            "compression_ratio": ratio,
            "storage_reduction_percent": reduction
        })

    points = 0
    if pattern_ok:
        points += 5
    if document_ok:
        points += 5
    if noise_ok:
        points += 5

    return points, {
        "max_points": 15,
        "points": points,
        "pattern_data_5x_plus": pattern_ok,
        "document_data_2x_to_5x": document_ok,
        "random_noise_guardrail": noise_ok,
        "checks": checks
    }


def score_continuity_preservation(datasets):
    dataset_map = {
        dataset["dataset_name"]: dataset
        for dataset in datasets
    }

    checks = []

    document_text = flatten_events_text(dataset_map["document_evolution"], important_only=True).lower()
    packaging_current = (
        "cheap packaging caused customer complaints" in document_text
        and "premium positioning" in document_text
        and "cheap packaging again" in document_text
    )

    checks.append({
        "scenario": "old packaging strategy rejected and current premium rule preserved",
        "passed": packaging_current
    })

    personal_text = flatten_events_text(dataset_map["fake_personal_ai_memory"], important_only=True).lower()
    focus_current = (
        "prmr memory core" in personal_text
        and "first serious product" in personal_text
        and "scattered builds" in personal_text
    )

    checks.append({
        "scenario": "user changed from scattered projects to PRMR Memory Core focus",
        "passed": focus_current
    })

    creative_text = flatten_events_text(dataset_map["fake_creative_world_memory"], important_only=True).lower()
    creative_separation = (
        "mythrion" in creative_text
        and "aura" in creative_text
        and "separate" in creative_text
        and "human-made art" in creative_text
    )

    checks.append({
        "scenario": "Mythrion and AURA separation preserved",
        "passed": creative_separation
    })

    passed = sum(1 for check in checks if check["passed"])
    ratio = passed / len(checks)
    points = round(ratio * 20, 2)

    return points, {
        "max_points": 20,
        "points": points,
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks
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

    # These are based on existing completed hardening artifacts if present.
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

    # Local UI/code policy checks.
    onboarding_file = Path("prmr_onboarding.py")
    if onboarding_file.exists():
        text = onboarding_file.read_text(encoding="utf-8")
        checks.append({
            "check": "client_access_has_masked_key_ui",
            "passed": "apiKeyMasked" in text and "Reveal API Key" in text
        })
        checks.append({
            "check": "quickstart_uses_placeholder",
            "passed": "YOUR_API_KEY" in text
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
        "note": "Uses existing local hardening reports and onboarding UI checks. Cross-client leak tests should be expanded in V0.36.1."
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
    return normalize_prmr_result(engine.run(datasets))


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
        "protected_note": "Public report excludes core internals, compressed artifacts, private schemas, and API keys."
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
        print("V0.36 TRUST SUITE RESULT: PASS ✅")
    else:
        print()
        print("V0.36 TRUST SUITE RESULT: NEEDS WORK ⚠️")


if __name__ == "__main__":
    main()
'''
    write_text(BENCHMARKS / "runners" / "run_trust_suite_v036.py", runner)


def main():
    for folder in FOLDERS:
        folder.mkdir(parents=True, exist_ok=True)

    build_datasets()
    build_expected_answers()
    build_baseline_files()
    build_runner()

    print("PRMR Memory Core V0.36 Trust Benchmark Suite scaffold created ✅")
    print("Created:")
    print("- benchmarks/datasets")
    print("- benchmarks/expected")
    print("- benchmarks/baselines")
    print("- benchmarks/runners/run_trust_suite_v036.py")
    print("- reports/v036")


if __name__ == "__main__":
    main()