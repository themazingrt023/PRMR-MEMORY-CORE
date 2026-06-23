import json
from pathlib import Path
from datetime import datetime

REPORT = Path("reports/v037/public_realistic_memory_benchmark_v037.json")
PROGRESS_DIR = Path("reports/progress")
PROGRESS_JSON = PROGRESS_DIR / "prmr_v037_realistic_memory_progress.json"
PROGRESS_MD = PROGRESS_DIR / "prmr_v037_realistic_memory_progress.md"


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


def load_existing():
    if PROGRESS_JSON.exists():
        return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "V0.37 Realistic Memory Benchmark Progress",
        "history": []
    }


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    existing = load_existing()

    score = float(data["realistic_memory_trust_score"])

    previous_score = None
    if existing["history"]:
        previous_score = float(existing["history"][-1]["score"])

    if previous_score is None:
        change = 0
        direction = "baseline established"
    else:
        change = round(score - previous_score, 2)
        direction = "improved" if change > 0 else "regressed" if change < 0 else "unchanged"

    scorecard = data["scorecard"]

    weak_points = []
    if scorecard["compression_judgment"] < 15:
        weak_points.append("Compression judgment is the only remaining gap to 100.")
    if scorecard["reconstruction_fidelity"] < 20:
        weak_points.append("Reconstruction fidelity needs work.")
    if scorecard["continuity_preservation"] < 25:
        weak_points.append("Continuity preservation needs work.")
    if scorecard["signal_noise_discrimination"] < 20:
        weak_points.append("Signal/noise discrimination needs work.")
    if scorecard["baseline_comparison"] < 10:
        weak_points.append("Baseline comparison needs work.")
    if scorecard["latency_cost_efficiency"] < 10:
        weak_points.append("Latency/cost efficiency needs work.")

    if not weak_points:
        weak_points.append("No weak points detected. 100% achieved on this benchmark.")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "score": score,
        "previous_score": previous_score,
        "change": change,
        "direction": direction,
        "status": interpretation(score),
        "scorecard": scorecard,
        "weak_points": weak_points,
        "source_report": str(REPORT),
        "mantra": "Test. Break. Patch. Rerun. Score. Climb."
    }

    existing["current"] = entry
    existing["history"].append(entry)

    PROGRESS_JSON.write_text(json.dumps(existing, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.37 Realistic Memory Progress

Company: Afternum Industries  
Product: PRMR Memory Core  

## Current Score

**{score}/100**

Status: **{interpretation(score)}**  
Direction: **{direction}**  
Change: **{change}**

## Scorecard

| Category | Score |
|---|---:|
| Reconstruction Fidelity | {scorecard["reconstruction_fidelity"]}/20 |
| Continuity Preservation | {scorecard["continuity_preservation"]}/25 |
| Signal / Noise Discrimination | {scorecard["signal_noise_discrimination"]}/20 |
| Compression Judgment | {scorecard["compression_judgment"]}/15 |
| Baseline Comparison | {scorecard["baseline_comparison"]}/10 |
| Latency + Cost Efficiency | {scorecard["latency_cost_efficiency"]}/10 |

## Weak Points

""" + "\n".join(f"- {point}" for point in weak_points) + """

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    PROGRESS_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.37 REALISTIC MEMORY PROGRESS UPDATED")
    print("-------------------------------------------")
    print("Current score:", f"{score}/100")
    print("Status:", interpretation(score))
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