import json
from pathlib import Path
from datetime import datetime


PUBLIC_BENCHMARK = Path("reports/v036/public_trust_benchmark_v036.json")
PROGRESS_DIR = Path("reports/progress")
PROGRESS_JSON = PROGRESS_DIR / "prmr_memory_core_progress.json"
PROGRESS_MD = PROGRESS_DIR / "prmr_memory_core_progress.md"


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


def load_latest_benchmark():
    if not PUBLIC_BENCHMARK.exists():
        raise FileNotFoundError(
            "Missing reports/v036/public_trust_benchmark_v036.json. Run the V0.36 benchmark first."
        )

    return json.loads(PUBLIC_BENCHMARK.read_text(encoding="utf-8"))


def load_existing_progress():
    if PROGRESS_JSON.exists():
        return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "PRMR Memory Core Readiness",
        "history": []
    }


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    benchmark = load_latest_benchmark()
    progress = load_existing_progress()

    score_data = benchmark["prmr_continuity_trust_score"]
    current_score = float(score_data["total"])

    previous_score = None
    if progress["history"]:
        previous_score = float(progress["history"][-1]["readiness_percent"])

    if previous_score is None:
        change = 0
        direction = "baseline established"
    else:
        change = round(current_score - previous_score, 2)

        if change > 0:
            direction = "improved"
        elif change < 0:
            direction = "regressed"
        else:
            direction = "unchanged"

    category_scores = {
        "reconstruction_fidelity": score_data["reconstruction_fidelity"],
        "compression_efficiency": score_data["compression_efficiency"],
        "continuity_preservation": score_data["continuity_preservation"],
        "noise_resistance": score_data["noise_resistance"],
        "security_client_isolation": score_data["security_client_isolation"],
        "latency_cost_efficiency": score_data["latency_cost_efficiency"]
    }

    weak_points = []

    if category_scores["compression_efficiency"] < 10:
        weak_points.append("Compression efficiency needs work.")
    if category_scores["continuity_preservation"] < 16:
        weak_points.append("Continuity preservation needs stronger change-over-time handling.")
    if category_scores["security_client_isolation"] < 13:
        weak_points.append("Security/client isolation needs deeper proof.")
    if category_scores["reconstruction_fidelity"] < 22:
        weak_points.append("Reconstruction fidelity needs improvement.")
    if category_scores["noise_resistance"] < 12:
        weak_points.append("Noise resistance needs improvement.")
    if category_scores["latency_cost_efficiency"] < 8:
        weak_points.append("Latency/cost efficiency needs improvement.")

    if not weak_points:
        weak_points.append("No major weak category detected in current scorecard.")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "version": benchmark.get("version", "unknown"),
        "readiness_percent": current_score,
        "previous_percent": previous_score,
        "change": change,
        "direction": direction,
        "status": interpretation(current_score),
        "category_scores": category_scores,
        "weak_points": weak_points,
        "public_report": str(PUBLIC_BENCHMARK)
    }

    progress["current"] = entry
    progress["history"].append(entry)

    PROGRESS_JSON.write_text(json.dumps(progress, indent=4), encoding="utf-8")

    md = f"""# PRMR Memory Core Progress Tracker

Company: Afternum Industries  
Product: PRMR Memory Core  
Tracker: PRMR Memory Core Readiness %

## Current Readiness

**{current_score}% / 100**

Status: **{interpretation(current_score)}**  
Direction: **{direction}**  
Change since previous run: **{change}**

## Category Scores

| Category | Score |
|---|---:|
| Reconstruction Fidelity | {category_scores["reconstruction_fidelity"]}/25 |
| Compression Efficiency | {category_scores["compression_efficiency"]}/15 |
| Continuity Preservation | {category_scores["continuity_preservation"]}/20 |
| Noise Resistance | {category_scores["noise_resistance"]}/15 |
| Security + Client Isolation | {category_scores["security_client_isolation"]}/15 |
| Latency + Cost Efficiency | {category_scores["latency_cost_efficiency"]}/10 |

## Current Weak Points

""" + "\n".join(f"- {item}" for item in weak_points) + f"""

## Milestone Ladder

| Range | Meaning |
|---|---|
| 0–49 | Not trustworthy |
| 50–69 | Prototype only |
| 70–79 | Promising alpha |
| 80–89 | Strong local alpha |
| 90–94 | Pilot candidate |
| 95–100 | Serious investor/demo candidate |

## Next Target

**80%+** — Strong Local Alpha

This tracker should be updated after every serious benchmark, patch, regression test, or hardening run.
"""

    PROGRESS_MD.write_text(md, encoding="utf-8")

    print("PRMR MEMORY CORE READINESS TRACKER UPDATED")
    print("------------------------------------------")
    print("Current readiness:", f"{current_score}%")
    print("Status:", interpretation(current_score))
    print("Direction:", direction)
    print("Change:", change)
    print()
    print("Weak points:")
    for point in weak_points:
        print("-", point)
    print()
    print("Created/updated:")
    print(PROGRESS_JSON)
    print(PROGRESS_MD)


if __name__ == "__main__":
    main()