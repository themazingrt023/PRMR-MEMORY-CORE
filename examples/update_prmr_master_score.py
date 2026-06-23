import json
from pathlib import Path
from datetime import datetime

PROGRESS_DIR = Path("reports/progress")
MASTER_JSON = PROGRESS_DIR / "prmr_master_score.json"
MASTER_MD = PROGRESS_DIR / "prmr_master_score.md"

V036_PRODUCT = Path("reports/progress/prmr_memory_core_progress.json")
V036_ENGINE = Path("reports/progress/prmr_engine_core_score.json")
V037_REALISTIC = Path("reports/progress/prmr_v037_realistic_memory_progress.json")
V037_ENGINE = Path("reports/progress/prmr_engine_core_score_v037.json")


def load(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_current_block(data):
    if not data:
        return None

    if isinstance(data.get("current"), dict):
        return data["current"]

    history = data.get("history", [])
    if history:
        return history[-1]

    return None


def extract_score(data, possible_keys):
    current = get_current_block(data)

    if not current:
        return None, []

    available_keys = list(current.keys())

    for key in possible_keys:
        if key in current:
            try:
                return float(current[key]), available_keys
            except Exception:
                pass

    # Last-resort scan: find any numeric-looking key with score/readiness in name.
    for key, value in current.items():
        lowered = key.lower()

        if ("score" in lowered or "readiness" in lowered) and isinstance(value, (int, float)):
            return float(value), available_keys

    return None, available_keys


def status(score):
    if score < 50:
        return "not trustworthy"
    if score < 70:
        return "prototype"
    if score < 80:
        return "promising alpha"
    if score < 90:
        return "strong local alpha"
    if score < 95:
        return "pilot candidate"
    return "serious demo candidate"


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    v036_product = load(V036_PRODUCT)
    v036_engine = load(V036_ENGINE)
    v037_realistic = load(V037_REALISTIC)
    v037_engine = load(V037_ENGINE)

    v036_product_score, v036_product_keys = extract_score(
        v036_product,
        ["readiness_score", "readiness", "current_readiness", "score", "current_score"]
    )

    v036_engine_score, v036_engine_keys = extract_score(
        v036_engine,
        ["engine_core_score", "score", "current_score"]
    )

    v037_realistic_score, v037_realistic_keys = extract_score(
        v037_realistic,
        ["score", "realistic_memory_trust_score", "current_score"]
    )

    v037_engine_score, v037_engine_keys = extract_score(
        v037_engine,
        ["engine_core_score", "score", "current_score"]
    )

    scores = {
        "v036_product_readiness": v036_product_score,
        "v036_engine_core": v036_engine_score,
        "v037_realistic_memory": v037_realistic_score,
        "v037_engine_core": v037_engine_score,
    }

    debug_keys = {
        "v036_product_keys": v036_product_keys,
        "v036_engine_keys": v036_engine_keys,
        "v037_realistic_keys": v037_realistic_keys,
        "v037_engine_keys": v037_engine_keys,
    }

    valid_scores = [value for value in scores.values() if value is not None]
    missing = [name for name, value in scores.items() if value is None]

    master_score = round(sum(valid_scores) / max(len(valid_scores), 1), 2)

    weak_points = []

    for name, value in scores.items():
        if value is not None and value < 95:
            weak_points.append(f"{name} is below 95: {value}")

    if missing:
        weak_points.append("Some trackers are missing or unreadable: " + ", ".join(missing))

    if not weak_points:
        weak_points.append("No benchmark tracker below 95. Next work should be adversarial/regression testing, not score-chasing.")

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "Master PRMR Score",
        "timestamp": datetime.now().isoformat(),
        "master_score": master_score,
        "status": status(master_score),
        "component_scores": scores,
        "debug_available_keys": debug_keys,
        "weak_points": weak_points,
        "note": "Master score averages V0.36 trust/product proof and V0.37 realistic memory/engine proof. It is not a production certification.",
        "mantra": "Test. Break. Patch. Rerun. Score. Climb."
    }

    MASTER_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR Memory Core — Master Score

Company: Afternum Industries  
Product: PRMR Memory Core  

## Master Score

**{master_score}/100**

Status: **{status(master_score)}**

## Component Scores

| Component | Score |
|---|---:|
| V0.36 Product Readiness | {scores["v036_product_readiness"]} |
| V0.36 Engine Core | {scores["v036_engine_core"]} |
| V0.37 Realistic Memory | {scores["v037_realistic_memory"]} |
| V0.37 Realistic Engine Core | {scores["v037_engine_core"]} |

## Weak Points / Next Work

""" + "\n".join(f"- {point}" for point in weak_points) + """

## Important Note

100 on one benchmark does not mean the product is finished.  
It means PRMR passed that test. The next step is harder adversarial testing.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    MASTER_MD.write_text(md, encoding="utf-8")

    print("PRMR MASTER SCORE UPDATED")
    print("-------------------------")
    print("Master Score:", f"{master_score}/100")
    print("Status:", status(master_score))
    print()
    print("Component scores:")
    for name, value in scores.items():
        print("-", name + ":", value)
    print()
    print("Weak points / next work:")
    for point in weak_points:
        print("-", point)
    print()
    print("Created/updated:")
    print(MASTER_JSON)
    print(MASTER_MD)


if __name__ == "__main__":
    main()