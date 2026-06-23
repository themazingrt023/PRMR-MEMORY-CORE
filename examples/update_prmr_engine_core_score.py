import json
from pathlib import Path
from datetime import datetime


PUBLIC_BENCHMARK = Path("reports/v036/public_trust_benchmark_v036.json")
PRIVATE_BENCHMARK = Path("reports/v036/private_internal_trust_benchmark_v036.json")

PROGRESS_DIR = Path("reports/progress")
ENGINE_JSON = PROGRESS_DIR / "prmr_engine_core_score.json"
ENGINE_MD = PROGRESS_DIR / "prmr_engine_core_score.md"


def interpretation(score):
    if score < 50:
        return "engine not trustworthy"
    if score < 70:
        return "prototype engine"
    if score < 80:
        return "promising alpha engine"
    if score < 90:
        return "strong local alpha engine"
    if score < 95:
        return "pilot-grade engine candidate"
    return "serious trusted engine candidate"


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def load_existing():
    if ENGINE_JSON.exists():
        return load_json(ENGINE_JSON)

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "PRMR Engine Core Score",
        "history": []
    }


def clamp(value, maximum):
    return max(0, min(value, maximum))


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    public = load_json(PUBLIC_BENCHMARK)
    private = load_json(PRIVATE_BENCHMARK)
    existing = load_existing()

    trust = public["prmr_continuity_trust_score"]

    # Engine-specific scoring.
    # This strips out product UI/onboarding concerns and focuses on memory-core behavior.

    reconstruction_points = clamp(
        (trust["reconstruction_fidelity"] / 25) * 30,
        30
    )

    compression_points = clamp(
        (trust["compression_efficiency"] / 15) * 25,
        25
    )

    continuity_points = clamp(
        (trust["continuity_preservation"] / 20) * 20,
        20
    )

    noise_points = clamp(
        (trust["noise_resistance"] / 15) * 15,
        15
    )

    latency = public.get("latency_cost_efficiency", {})
    zero_llm = latency.get("llm_calls_used", 0) == 0
    deterministic_points = 10 if zero_llm else 5

    engine_score = round(
        reconstruction_points
        + compression_points
        + continuity_points
        + noise_points
        + deterministic_points,
        2
    )

    previous_score = None
    if existing["history"]:
        previous_score = float(existing["history"][-1]["engine_core_score"])

    if previous_score is None:
        change = 0
        direction = "baseline established"
    else:
        change = round(engine_score - previous_score, 2)
        if change > 0:
            direction = "improved"
        elif change < 0:
            direction = "regressed"
        else:
            direction = "unchanged"

    weak_points = []

    if compression_points < 18:
        weak_points.append("Compression intelligence needs work, especially rule/pattern compression scoring or engine compatibility.")
    if continuity_points < 16:
        weak_points.append("Continuity preservation needs stronger current-state/change-over-time handling.")
    if reconstruction_points < 27:
        weak_points.append("Reconstruction verification needs improvement.")
    if noise_points < 13:
        weak_points.append("Noise/chaos guardrail needs improvement.")
    if deterministic_points < 10:
        weak_points.append("Core benchmark used LLM calls or lost deterministic purity.")

    if not weak_points:
        weak_points.append("No major engine weakness detected in current benchmark.")

    snapshot = private.get("prmr_engine_public_result_snapshot", {})
    engine_version = snapshot.get("version", "unknown") if isinstance(snapshot, dict) else "unknown"
    all_reconstructions_verified = snapshot.get("all_reconstructions_verified") if isinstance(snapshot, dict) else None

    entry = {
        "timestamp": datetime.now().isoformat(),
        "engine_version": engine_version,
        "engine_core_score": engine_score,
        "previous_score": previous_score,
        "change": change,
        "direction": direction,
        "status": interpretation(engine_score),
        "all_reconstructions_verified": all_reconstructions_verified,
        "category_scores": {
            "reconstruction_verification": round(reconstruction_points, 2),
            "compression_intelligence": round(compression_points, 2),
            "continuity_preservation": round(continuity_points, 2),
            "noise_chaos_guardrail": round(noise_points, 2),
            "deterministic_stability_no_llm": deterministic_points
        },
        "source_benchmark": str(PUBLIC_BENCHMARK),
        "weak_points": weak_points,
        "mantra": "Test. Break. Patch. Rerun. Score. Climb."
    }

    existing["current"] = entry
    existing["history"].append(entry)

    ENGINE_JSON.write_text(json.dumps(existing, indent=4), encoding="utf-8")

    md = f"""# PRMR Engine Core Score

Company: Afternum Industries  
Product: PRMR Memory Core  
Tracker: Actual Memory Core Engine Score  

## Current Engine Core Score

**{engine_score}% / 100**

Status: **{interpretation(engine_score)}**  
Direction: **{direction}**  
Change since previous engine score: **{change}**

Engine version detected: **{engine_version}**  
All reconstructions verified: **{all_reconstructions_verified}**

## Engine Category Scores

| Engine Category | Score |
|---|---:|
| Reconstruction Verification | {round(reconstruction_points, 2)}/30 |
| Compression Intelligence | {round(compression_points, 2)}/25 |
| Continuity Preservation | {round(continuity_points, 2)}/20 |
| Noise / Chaos Guardrail | {round(noise_points, 2)}/15 |
| Deterministic Stability / No LLM | {deterministic_points}/10 |

## Current Engine Weak Points

""" + "\n".join(f"- {item}" for item in weak_points) + f"""

## Engine Milestone Ladder

| Range | Meaning |
|---|---|
| 0–49 | Engine not trustworthy |
| 50–69 | Prototype engine |
| 70–79 | Promising alpha engine |
| 80–89 | Strong local alpha engine |
| 90–94 | Pilot-grade engine candidate |
| 95–100 | Serious trusted engine candidate |

## Build Mantra

**Test. Break. Patch. Rerun. Score. Climb.**

The engine score can go up or down depending on real benchmark results.  
100 is not claimed. 100 is earned.
"""

    ENGINE_MD.write_text(md, encoding="utf-8")

    print("PRMR ENGINE CORE SCORE UPDATED")
    print("------------------------------")
    print("Engine Core Score:", f"{engine_score}%")
    print("Status:", interpretation(engine_score))
    print("Direction:", direction)
    print("Change:", change)
    print("All reconstructions verified:", all_reconstructions_verified)
    print()
    print("Weak points:")
    for point in weak_points:
        print("-", point)
    print()
    print("Created/updated:")
    print(ENGINE_JSON)
    print(ENGINE_MD)


if __name__ == "__main__":
    main()