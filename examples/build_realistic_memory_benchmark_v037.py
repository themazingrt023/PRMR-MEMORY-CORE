import json
import random
from pathlib import Path
from datetime import datetime


random.seed(37)

DATASET_DIR = Path("benchmarks/datasets_v037")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v037")

DATASET_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def build_company_memory(count=300):
    events = []

    phases = [
        ("cheap packaging", "customer complaints", "premium recyclable packaging"),
        ("manual support", "slow response times", "structured support playbook"),
        ("no security review", "client trust risk", "vault isolation checks"),
        ("unclear pricing", "confused buyers", "tiered pilot pricing"),
        ("random roadmap", "team confusion", "evidence-led roadmap"),
    ]

    for i in range(count):
        phase = phases[i % len(phases)]
        old_state, problem, current_state = phase

        event = {
            "event_id": f"company_{i+1}",
            "date": f"2026-07-{(i % 28) + 1:02d}",
            "memory_type": "company",
            "topic": f"company continuity loop {i % 12}",
            "old_state": old_state,
            "problem": problem,
            "active_state": current_state,
            "latent_risk": f"team may accidentally return to {old_state}",
            "lineage_reason": f"{problem} forced the shift from {old_state} to {current_state}",
            "importance": "high" if i % 9 == 0 else "medium",
            "status": "active" if i > count * 0.66 else "historical",
        }

        events.append(event)

    return {
        "dataset_name": "realistic_company_memory_300",
        "description": "Larger fake company memory with repeated strategy changes, old states, active rules, and latent risks.",
        "rows": events,
        "expected": {
            "must_reconstruct_exactly": True,
            "must_preserve_active": ["premium recyclable packaging", "vault isolation checks", "evidence-led roadmap"],
            "must_preserve_latent": ["return to cheap packaging", "return to no security review"],
            "must_preserve_lineage": ["customer complaints", "client trust risk", "team confusion"]
        }
    }


def build_personal_memory(count=300):
    events = []

    loops = [
        ("many scattered projects", "overwhelmed", "PRMR Memory Core first", "avoid scattered builds"),
        ("late nights without structure", "fatigue", "test patch rerun score climb", "burnout risk"),
        ("unclear public identity", "confusion", "Multiverse Architect positioning", "overexplaining risk"),
        ("money pressure", "panic decisions", "protect core build time", "short-term distraction risk"),
        ("creative flood", "too many universes at once", "weekly receipts system", "idea overflow risk"),
    ]

    for i in range(count):
        old_state, problem, active_state, risk = loops[i % len(loops)]

        # Make it messy: typos, repeated thoughts, mixed emotional language.
        noise_note = random.choice([
            "felt messy but still useful",
            "quick note from a tired night",
            "not fully clean but important",
            "maybe repeated before",
            "needs sorting later"
        ])

        events.append({
            "event_id": f"personal_{i+1}",
            "date": f"2026-08-{(i % 28) + 1:02d}",
            "memory_type": "personal",
            "old_state": old_state,
            "problem": problem,
            "active_state": active_state,
            "latent_risk": risk,
            "lineage_reason": f"{problem} made {active_state} necessary",
            "emotion": random.choice(["focused", "stressed", "hopeful", "tired", "locked in"]),
            "messy_note": noise_note,
            "importance": "high" if i % 7 == 0 else random.choice(["medium", "low"]),
            "status": "active" if i > count * 0.55 else "historical",
        })

    return {
        "dataset_name": "messy_personal_memory_300",
        "description": "Messy personal memory with repeated emotional loops, current focus, old states, and latent risks.",
        "rows": events,
        "expected": {
            "must_reconstruct_exactly": True,
            "must_preserve_active": ["PRMR Memory Core first", "test patch rerun score climb", "weekly receipts system"],
            "must_preserve_latent": ["avoid scattered builds", "burnout risk", "idea overflow risk"],
            "must_preserve_lineage": ["overwhelmed", "fatigue", "too many universes at once"]
        }
    }


def build_creative_memory(count=300):
    events = []

    worlds = [
        ("MYTHRION", "creative operating system", "human imagination", "AI generation rejected"),
        ("AURA", "authorship and real art", "human-made art protection", "AI slop pressure"),
        ("Cyber Vania", "manga saga", "arc continuity", "ending fatigue risk"),
        ("Psycha", "underground streetwear myth", "brand mystery", "overexposure risk"),
        ("PRNM", "narrative theory", "recursive storytelling", "too broad risk"),
    ]

    for i in range(count):
        world, role, active_state, risk = worlds[i % len(worlds)]

        events.append({
            "event_id": f"creative_{i+1}",
            "date": f"2026-09-{(i % 28) + 1:02d}",
            "memory_type": "creative_canon",
            "world": world,
            "role": role,
            "active_canon": active_state,
            "latent_risk": risk,
            "lineage_reason": f"{world} exists to preserve {active_state} through creative transformation",
            "canon_status": "canon" if i % 5 != 0 else "sandbox",
            "importance": "high" if i % 8 == 0 else "medium",
        })

    return {
        "dataset_name": "creative_world_canon_memory_300",
        "description": "Creative world/canon memory with separate universes, canon/sandbox states, lineage, and risks.",
        "rows": events,
        "expected": {
            "must_reconstruct_exactly": True,
            "must_preserve_active": ["human imagination", "human-made art protection", "arc continuity"],
            "must_preserve_latent": ["AI generation rejected", "overexposure risk", "ending fatigue risk"],
            "must_preserve_lineage": ["preserve human imagination", "preserve human-made art protection"]
        }
    }


def build_mixed_noise_signal(count=500, signal_ratio=0.20):
    events = []
    signal_count = int(count * signal_ratio)

    for i in range(count):
        is_signal = i < signal_count

        if is_signal:
            events.append({
                "event_id": f"mixed_signal_{i+1}",
                "memory_type": "signal",
                "importance": "high",
                "topic": random.choice(["security", "continuity", "focus", "canon", "compression"]),
                "active_state": random.choice([
                    "PRMR Memory Core first",
                    "vault isolation must hold",
                    "noise should not fake compression",
                    "AURA and MYTHRION stay separate",
                    "symbolic templates should become rules"
                ]),
                "latent_risk": random.choice([
                    "noise flood hides signal",
                    "old revoked key returns",
                    "scattered projects dilute focus",
                    "AI-generation pressure returns",
                    "template rule misses human pattern"
                ]),
                "lineage_reason": "signal survived inside a noisy memory flood",
                "status": "active"
            })
        else:
            events.append({
                "event_id": f"mixed_noise_{i+1}",
                "memory_type": "noise",
                "importance": "none",
                "message": f"noise filler random irrelevant duplicate {random.randint(100000, 999999)}",
                "status": "noise",
                "junk": random.choice(["abc", "random", "ignore", "temp", "loose"])
            })

    random.shuffle(events)

    return {
        "dataset_name": "mixed_noise_80_signal_20_500",
        "description": "Mixed memory flood with 80% noise and 20% meaningful signal.",
        "rows": events,
        "expected": {
            "must_reconstruct_exactly": True,
            "signal_ratio": signal_ratio,
            "must_preserve_active": [
                "PRMR Memory Core first",
                "vault isolation must hold",
                "noise should not fake compression",
                "symbolic templates should become rules"
            ],
            "must_not_treat_noise_as_meaning": True
        }
    }


datasets = [
    build_company_memory(),
    build_personal_memory(),
    build_creative_memory(),
    build_mixed_noise_signal()
]

for dataset in datasets:
    write_json(DATASET_DIR / f"{dataset['dataset_name']}.json", dataset)


runner = r'''import json
import os
import sys
import time
import math
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore


DATASET_DIR = Path("benchmarks/datasets_v037")
REPORT_DIR = Path("reports/v037")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_size(data):
    return len(json.dumps(data, sort_keys=True).encode("utf-8"))


def tokenize(text):
    return [
        token.strip(".,!?;:()[]{}'\"").lower()
        for token in str(text).split()
        if token.strip(".,!?;:()[]{}'\"")
    ]


def row_text(row):
    return json.dumps(row, sort_keys=True).lower()


def dataset_text(rows):
    return " ".join(row_text(row) for row in rows)


def keyword_baseline_score(rows, expected_terms):
    text = dataset_text(rows)
    hits = sum(1 for term in expected_terms if term.lower() in text)
    return hits / max(len(expected_terms), 1)


def summary_baseline_score(rows, expected_terms):
    # crude baseline: keeps only first 20 and last 20 rows, like a lossy summary window
    summary_rows = rows[:20] + rows[-20:]
    text = dataset_text(summary_rows)
    hits = sum(1 for term in expected_terms if term.lower() in text)
    return hits / max(len(expected_terms), 1)


def vector_like_baseline_score(rows, expected_terms):
    # dependency-free vector-ish baseline using token overlap.
    corpus = [row_text(row) for row in rows]
    corpus_tokens = [set(tokenize(text)) for text in corpus]

    hit_count = 0

    for term in expected_terms:
        query_tokens = set(tokenize(term))
        best_score = 0

        for tokens in corpus_tokens:
            if not query_tokens:
                continue

            overlap = len(query_tokens & tokens) / max(len(query_tokens), 1)
            best_score = max(best_score, overlap)

        if best_score >= 0.5:
            hit_count += 1

    return hit_count / max(len(expected_terms), 1)


def score_reconstruction(results):
    passed = 0
    details = []

    for result in results:
        decision = result["decision"]
        ok = decision.get("reconstruction_match") is True
        passed += 1 if ok else 0
        details.append({
            "dataset": result["dataset"],
            "reconstruction_match": ok
        })

    points = round((passed / max(len(results), 1)) * 20, 2)

    return points, {
        "points": points,
        "max_points": 20,
        "passed": passed,
        "total": len(results),
        "details": details
    }


def score_continuity(results, dataset_specs):
    total_score = 0
    details = []

    for result in results:
        name = result["dataset"]
        rows = result["decision"]["reconstructed_rows"]
        text = dataset_text(rows)
        expected = dataset_specs[name]["expected"]

        active_terms = expected.get("must_preserve_active", [])
        latent_terms = expected.get("must_preserve_latent", [])
        lineage_terms = expected.get("must_preserve_lineage", [])

        all_terms = active_terms + latent_terms + lineage_terms

        hits = [term for term in all_terms if term.lower() in text]
        missing = [term for term in all_terms if term.lower() not in text]

        score = len(hits) / max(len(all_terms), 1)
        total_score += score

        details.append({
            "dataset": name,
            "score": round(score, 4),
            "hits": hits,
            "missing": missing
        })

    average = total_score / max(len(results), 1)
    points = round(average * 25, 2)

    return points, {
        "points": points,
        "max_points": 25,
        "average": round(average, 4),
        "details": details
    }


def score_signal_noise(results):
    details = []
    total = 0

    for result in results:
        name = result["dataset"]
        rows = result["decision"]["reconstructed_rows"]
        decision = result["decision"]

        noise_rows = [
            row for row in rows
            if str(row.get("memory_type", "")).lower() == "noise"
            or str(row.get("importance", "")).lower() in ("none", "noise")
        ]

        signal_rows = [
            row for row in rows
            if str(row.get("memory_type", "")).lower() == "signal"
            or str(row.get("importance", "")).lower() in ("high",)
        ]

        noise_ratio = len(noise_rows) / max(len(rows), 1)

        if "mixed_noise" in name:
            # Mixed flood should preserve signal while refusing to over-trust noise compression.
            raw_or_guarded = (
                decision.get("policy_mode") == "raw"
                or decision.get("noise_guardrail_triggered") is True
            )
            signal_present = len(signal_rows) >= 50
            dataset_score = 1.0 if raw_or_guarded and signal_present else 0.5 if signal_present else 0.0
        else:
            # Normal datasets should not be mistaken as noise.
            dataset_score = 1.0 if noise_ratio < 0.5 else 0.5

        total += dataset_score

        details.append({
            "dataset": name,
            "score": dataset_score,
            "policy_mode": decision.get("policy_mode"),
            "noise_guardrail_triggered": decision.get("noise_guardrail_triggered"),
            "noise_ratio": round(noise_ratio, 4),
            "signal_rows": len(signal_rows),
            "noise_rows": len(noise_rows)
        })

    average = total / max(len(results), 1)
    points = round(average * 20, 2)

    return points, {
        "points": points,
        "max_points": 20,
        "average": round(average, 4),
        "details": details
    }


def score_compression_judgment(results):
    details = []
    total = 0

    for result in results:
        name = result["dataset"]
        d = result["decision"]

        mode = d.get("policy_mode")
        ratio = float(d.get("policy_compression_ratio", 1.0) or 1.0)
        saved = float(d.get("policy_saved_percentage", 0.0) or 0.0)

        if "mixed_noise" in name:
            # On noise-heavy data, honesty matters more than compression.
            score = 1.0 if mode == "raw" else 0.5 if saved < 15 else 0.0
        elif "company" in name or "personal" in name or "creative" in name:
            # Messy human data may compress modestly or remain raw. Reward useful compression but don't punish safe raw too hard.
            if saved >= 20 and ratio >= 1.2:
                score = 1.0
            elif mode == "raw":
                score = 0.7
            elif saved >= 10:
                score = 0.8
            else:
                score = 0.5
        else:
            score = 0.5

        total += score

        details.append({
            "dataset": name,
            "score": score,
            "policy_mode": mode,
            "compression_ratio": ratio,
            "saved_percentage": saved
        })

    average = total / max(len(results), 1)
    points = round(average * 15, 2)

    return points, {
        "points": points,
        "max_points": 15,
        "average": round(average, 4),
        "details": details
    }


def score_baselines(results, dataset_specs):
    details = []
    prmr_total = 0
    best_baseline_total = 0

    for result in results:
        name = result["dataset"]
        rows = result["decision"]["reconstructed_rows"]
        expected = dataset_specs[name]["expected"]

        terms = (
            expected.get("must_preserve_active", [])
            + expected.get("must_preserve_latent", [])
            + expected.get("must_preserve_lineage", [])
        )

        prmr_score = keyword_baseline_score(rows, terms)
        summary_score = summary_baseline_score(rows, terms)
        keyword_score = keyword_baseline_score(rows, terms)
        vector_score = vector_like_baseline_score(rows, terms)

        best_baseline = max(summary_score, keyword_score, vector_score)

        prmr_total += prmr_score
        best_baseline_total += best_baseline

        details.append({
            "dataset": name,
            "prmr_reconstructed_score": round(prmr_score, 4),
            "summary_baseline": round(summary_score, 4),
            "keyword_baseline": round(keyword_score, 4),
            "vector_like_baseline": round(vector_score, 4),
            "best_baseline": round(best_baseline, 4)
        })

    prmr_avg = prmr_total / max(len(results), 1)
    baseline_avg = best_baseline_total / max(len(results), 1)

    # PRMR should at least match baselines while preserving reconstruction and policy evidence.
    if prmr_avg >= baseline_avg:
        points = 10
    else:
        points = round((prmr_avg / max(baseline_avg, 0.001)) * 10, 2)

    return points, {
        "points": points,
        "max_points": 10,
        "prmr_average": round(prmr_avg, 4),
        "best_baseline_average": round(baseline_avg, 4),
        "details": details
    }


def score_latency(start, end):
    duration = end - start

    if duration <= 2:
        points = 10
    elif duration <= 5:
        points = 8
    elif duration <= 10:
        points = 6
    else:
        points = 4

    return points, {
        "points": points,
        "max_points": 10,
        "duration_seconds": round(duration, 4),
        "llm_calls_used": 0
    }


def interpretation(score):
    if score < 50:
        return "not trustworthy under realistic memory load"
    if score < 70:
        return "prototype under realistic memory load"
    if score < 80:
        return "promising but unstable under realistic memory load"
    if score < 90:
        return "strong local alpha under realistic memory load"
    if score < 95:
        return "pilot candidate under realistic memory load"
    return "serious realistic demo candidate"


def main():
    print("PRMR MEMORY CORE V0.37 REALISTIC MEMORY BENCHMARK")
    print("--------------------------------------------------")

    dataset_paths = sorted(DATASET_DIR.glob("*.json"))
    specs = [load_json(path) for path in dataset_paths]

    dataset_specs = {
        spec["dataset_name"]: spec
        for spec in specs
    }

    engine_inputs = [
        {
            "name": spec["dataset_name"],
            "description": spec["description"],
            "rows": spec["rows"]
        }
        for spec in specs
    ]

    engine = PRMRMemoryCore()

    start = time.time()
    engine_result = engine.run(engine_inputs)
    end = time.time()

    results = engine_result["results"]

    reconstruction_points, reconstruction_report = score_reconstruction(results)
    continuity_points, continuity_report = score_continuity(results, dataset_specs)
    signal_noise_points, signal_noise_report = score_signal_noise(results)
    compression_points, compression_report = score_compression_judgment(results)
    baseline_points, baseline_report = score_baselines(results, dataset_specs)
    latency_points, latency_report = score_latency(start, end)

    total = round(
        reconstruction_points
        + continuity_points
        + signal_noise_points
        + compression_points
        + baseline_points
        + latency_points,
        2
    )

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.37",
        "report_type": "realistic_memory_benchmark_pack",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "realistic_memory_trust_score": total,
        "interpretation": interpretation(total),
        "scorecard": {
            "reconstruction_fidelity": reconstruction_points,
            "continuity_preservation": continuity_points,
            "signal_noise_discrimination": signal_noise_points,
            "compression_judgment": compression_points,
            "baseline_comparison": baseline_points,
            "latency_cost_efficiency": latency_points
        },
        "details": {
            "reconstruction": reconstruction_report,
            "continuity": continuity_report,
            "signal_noise": signal_noise_report,
            "compression_judgment": compression_report,
            "baseline_comparison": baseline_report,
            "latency": latency_report
        },
        "note": "V0.37 tests larger, messier, more human-like memory datasets. This score may be lower than V0.36 by design."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "engine_result_snapshot": engine_result,
        "protected_note": "Private benchmark report includes full engine decision objects and reconstructed rows. Do not publish raw."
    }

    public_path = REPORT_DIR / "public_realistic_memory_benchmark_v037.json"
    private_path = REPORT_DIR / "private_internal_realistic_memory_benchmark_v037.json"
    scorecard_path = REPORT_DIR / "scorecard_v037.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    scorecard = f"""# PRMR Memory Core V0.37 Realistic Memory Benchmark

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: 0.37  

## Score

**{total}/100**

Interpretation: **{interpretation(total)}**

## Categories

| Category | Score |
|---|---:|
| Reconstruction Fidelity | {reconstruction_points}/20 |
| Continuity Preservation | {continuity_points}/25 |
| Signal / Noise Discrimination | {signal_noise_points}/20 |
| Compression Judgment | {compression_points}/15 |
| Baseline Comparison | {baseline_points}/10 |
| Latency + Cost Efficiency | {latency_points}/10 |

## Note

V0.37 is intentionally harder than V0.36.4.  
It tests larger fake company memory, messy personal memory, creative world/canon memory, and mixed noise flood.

Test. Break. Patch. Rerun. Score. Climb.
"""

    scorecard_path.write_text(scorecard, encoding="utf-8")

    print("Reconstruction Fidelity:", f"{reconstruction_points}/20")
    print("Continuity Preservation:", f"{continuity_points}/25")
    print("Signal / Noise Discrimination:", f"{signal_noise_points}/20")
    print("Compression Judgment:", f"{compression_points}/15")
    print("Baseline Comparison:", f"{baseline_points}/10")
    print("Latency + Cost Efficiency:", f"{latency_points}/10")
    print("--------------------------------------------------")
    print("PRMR V0.37 Realistic Memory Trust Score:", f"{total}/100")
    print("Interpretation:", interpretation(total))
    print()
    print("Reports created:")
    print(public_path)
    print(private_path)
    print(scorecard_path)

    if total >= 90:
        print()
        print("V0.37 REALISTIC MEMORY BENCHMARK: PASS ✅")
    else:
        print()
        print("V0.37 REALISTIC MEMORY BENCHMARK: NEEDS WORK ⚠️")


if __name__ == "__main__":
    main()
'''

runner_path = RUNNER_DIR / "run_realistic_memory_benchmark_v037.py"
runner_path.write_text(runner, encoding="utf-8")

print("PRMR V0.37 realistic memory benchmark pack created ✅")
print("Datasets:")
for dataset in datasets:
    print("-", DATASET_DIR / f"{dataset['dataset_name']}.json")
print("Runner:")
print("-", runner_path)