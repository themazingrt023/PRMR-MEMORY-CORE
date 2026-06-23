import json
from pathlib import Path
from datetime import datetime

REPORT = Path("reports/v037/public_realistic_memory_benchmark_v037.json")
PROGRESS_DIR = Path("reports/progress")
ENGINE_JSON = PROGRESS_DIR / "prmr_engine_core_score_v037.json"
ENGINE_MD = PROGRESS_DIR / "prmr_engine_core_score_v037.md"


def interpretation(score):
    if score < 50:
        return "engine not trustworthy under realistic memory load"
    if score < 70:
        return "prototype engine under realistic memory load"
    if score < 80:
        return "promising alpha engine under realistic memory load"
    if score < 90:
        return "strong local alpha engine under realistic memory load"
    if score < 95:
        return "pilot-grade engine under realistic memory load"
    return "serious realistic engine candidate"


def load_existing():
    if ENGINE_JSON.exists():
        return json.loads(ENGINE_JSON.read_text(encoding="utf-8"))

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "V0.37 Realistic Engine Core Score",
        "history": []
    }


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    existing = load_existing()

    scorecard = data["scorecard"]

    # Engine-focused score from V0.37. Excludes product onboarding/admin UI.
    # Includes realistic reconstruction, continuity, signal/noise, compression judgment, and deterministic latency.
    engine_score = round(
        scorecard["reconstruction_fidelity"]
        + scorecard["continuity_preservation"]
        + scorecard["signal_noise_discrimination"]
        + scorecard["compression_judgment"]
        + scorecard["latency_cost_efficiency"],
        2
    )

    # V0.37 engine score max = 90 from the above categories.
    # Convert to /100 so it compares to the old engine score.
    engine_score_100 = round((engine_score / 90) * 100, 2)

    previous_score = None
    if existing["history"]:
        previous_score = float(existing["history"][-1]["engine_core_score"])

    if previous_score is None:
        change = 0
        direction = "baseline established"
    else:
        change = round(engine_score_100 - previous_score, 2)
        direction = "improved" if change > 0 else "regressed" if change < 0 else "unchanged"

    weak_points = []
    if scorecard["compression_judgment"] < 15:
        weak_points.append("Compression judgment is the only remaining engine gap under V0.37 realistic load.")
    if scorecard["reconstruction_fidelity"] < 20:
        weak_points.append("Reconstruction fidelity needs work.")
    if scorecard["continuity_preservation"] < 25:
        weak_points.append("Continuity preservation needs work.")
    if scorecard["signal_noise_discrimination"] < 20:
        weak_points.append("Signal/noise discrimination needs work.")
    if scorecard["latency_cost_efficiency"] < 10:
        weak_points.append("Latency/cost efficiency needs work.")

    if not weak_points:
        weak_points.append("No engine weak points detected under V0.37 realistic benchmark.")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "engine_core_score": engine_score_100,
        "raw_engine_points": engine_score,
        "raw_engine_max": 90,
        "previous_score": previous_score,
        "change": change,
        "direction": direction,
        "status": interpretation(engine_score_100),
        "source_report": str(REPORT),
        "scorecard_used": {
            "reconstruction_fidelity": scorecard["reconstruction_fidelity"],
            "continuity_preservation": scorecard["continuity_preservation"],
            "signal_noise_discrimination": scorecard["signal_noise_discrimination"],
            "compression_judgment": scorecard["compression_judgment"],
            "latency_cost_efficiency": scorecard["latency_cost_efficiency"]
        },
        "weak_points": weak_points,
        "mantra": "Test. Break. Patch. Rerun. Score. Climb."
    }

    existing["current"] = entry
    existing["history"].append(entry)

    ENGINE_JSON.write_text(json.dumps(existing, indent=4), encoding="utf-8")

    md = f"""# PRMR Engine Core Score — V0.37 Realistic Load

Company: Afternum Industries  
Product: PRMR Memory Core  

## Current Engine Score

**{engine_score_100}/100**

Raw engine points: **{engine_score}/90**  
Status: **{interpretation(engine_score_100)}**  
Direction: **{direction}**  
Change: **{change}**

## Engine Categories Used

| Category | Score |
|---|---:|
| Reconstruction Fidelity | {scorecard["reconstruction_fidelity"]}/20 |
| Continuity Preservation | {scorecard["continuity_preservation"]}/25 |
| Signal / Noise Discrimination | {scorecard["signal_noise_discrimination"]}/20 |
| Compression Judgment | {scorecard["compression_judgment"]}/15 |
| Latency + Cost Efficiency | {scorecard["latency_cost_efficiency"]}/10 |

## Weak Points

""" + "\n".join(f"- {point}" for point in weak_points) + """

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    ENGINE_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.37 ENGINE CORE SCORE UPDATED")
    print("-----------------------------------")
    print("Engine Core Score:", f"{engine_score_100}/100")
    print("Raw engine points:", f"{engine_score}/90")
    print("Status:", interpretation(engine_score_100))
    print("Direction:", direction)
    print("Change:", change)
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