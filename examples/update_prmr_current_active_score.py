import json
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("reports/progress")
OUT_DIR.mkdir(parents=True, exist_ok=True)

V037_PROGRESS = Path("reports/progress/prmr_v037_realistic_memory_progress.json")
V037_ENGINE = Path("reports/progress/prmr_engine_core_score_v037.json")

OUT_JSON = OUT_DIR / "prmr_current_active_score.json"
OUT_MD = OUT_DIR / "prmr_current_active_score.md"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    realistic = load(V037_PROGRESS)
    engine = load(V037_ENGINE)

    realistic_score = float(realistic["current"]["score"])
    engine_score = float(engine["current"]["engine_core_score"])

    active_score = round((realistic_score + engine_score) / 2, 2)

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "tracker": "Current Active PRMR Score",
        "active_version_line": "V0.37 / V0.37.1",
        "timestamp": datetime.now().isoformat(),
        "active_score": active_score,
        "realistic_memory_score": realistic_score,
        "engine_core_score": engine_score,
        "status": "active engine benchmark complete" if active_score == 100 else "active benchmark needs work",
        "note": "V0.36 is historical trust/security proof. V0.37/V0.37.1 is the active realistic engine benchmark line.",
        "next_phase": "V0.38 Baseline War Test"
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR Memory Core — Current Active Score

Company: Afternum Industries  
Product: PRMR Memory Core  

## Active Version Line

**V0.37 / V0.37.1**

## Current Active Score

**{active_score}/100**

| Component | Score |
|---|---:|
| V0.37 Realistic Memory Benchmark | {realistic_score}/100 |
| V0.37 Realistic Engine Core | {engine_score}/100 |

## Important Note

V0.36 is now historical trust/security/skeleton proof.  
The current active engine line is V0.37/V0.37.1.

## Next Phase

**V0.38 — Baseline War Test**

Goal: prove PRMR does not merely score high, but beats weaker memory methods under realistic and adversarial continuity pressure.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR CURRENT ACTIVE SCORE UPDATED ✅")
    print("-----------------------------------")
    print("Active Score:", f"{active_score}/100")
    print("Realistic Memory:", realistic_score)
    print("Engine Core:", engine_score)
    print("Next:", "V0.38 Baseline War Test")
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()