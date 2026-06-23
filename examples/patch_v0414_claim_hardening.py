import json
from pathlib import Path
from datetime import datetime

PUBLIC_0412 = Path("reports/v0412/public_hard_token_tax_cost_war_v0412.json")
PRIVATE_0412 = Path("reports/v0412/private_internal_hard_token_tax_cost_war_v0412.json")
SCORECARD_0412 = Path("reports/v0412/scorecard_v0412.md")

AUDIT_0413 = Path("reports/v0413/hard_token_tax_integrity_audit_v0413.json")
AUDIT_MD_0413 = Path("reports/v0413/hard_token_tax_integrity_audit_v0413.md")

OUT_DIR = Path("reports/v0414")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "claim_hardening_v0414.json"
OUT_MD = OUT_DIR / "claim_hardening_v0414.md"


SAFE_CLAIM = (
    "In the V0.41.2 hard token-cost benchmark, PRMR matched raw-context continuity accuracy "
    "while reducing the benchmark-estimated downstream memory payload from 479,064 tokens to 453 tokens. "
    "Under retrieval traps, keyword and vector-like baselines lost continuity accuracy, while PRMR preserved "
    "the target-client state with a much smaller public-safe continuity packet. These figures are internal "
    "benchmark estimates, not live provider billing guarantees."
)

TOKEN_DEFINITION = (
    "Payload tokens are benchmark-estimated from serialized JSON payload size using the runner's approximate "
    "token estimator. They are used for relative comparison between memory strategies, not as guaranteed live "
    "provider token counts."
)

RAW_CONTEXT_NOTE = (
    "The raw-context baseline intentionally sends the full memory history. Its large token count is not a bug; "
    "it represents the context tax paid by systems that repeatedly send full history downstream."
)

PRMR_PACKET_NOTE = (
    "The PRMR payload is the downstream public-safe continuity packet, not the restricted compressed package or full "
    "engine internals."
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def patch_report(path):
    data = load_json(path)

    data["claim"] = SAFE_CLAIM
    data["claim_safety_notes"] = {
        "token_definition": TOKEN_DEFINITION,
        "raw_context_note": RAW_CONTEXT_NOTE,
        "prmr_packet_note": PRMR_PACKET_NOTE,
        "billing_warning": "Cost numbers use the benchmark's stated assumed input price and are not live provider billing guarantees.",
        "accuracy_warning": "Raw context still matched PRMR accuracy; PRMR's advantage in this test is accuracy-per-token under retrieval trap pressure."
    }

    return data


def main():
    public = patch_report(PUBLIC_0412)
    private = patch_report(PRIVATE_0412)

    save_json(PUBLIC_0412, public)
    save_json(PRIVATE_0412, private)

    summary = public["summary"]
    results = public["results"]

    raw = results["raw_context"]
    keyword = results["keyword_search"]
    vector = results["vector_like"]
    prmr = results["prmr_memory_core"]

    # Rewrite V0.41.2 scorecard with safer language.
    scorecard = f"""# PRMR V0.41.2 Hard Token Tax / Cost War Benchmark

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.41.2  

## Result

**{summary["result"]}**

## Investor-Safe Claim

{SAFE_CLAIM}

## Token Definition

{TOKEN_DEFINITION}

## Important Notes

- {RAW_CONTEXT_NOTE}
- {PRMR_PACKET_NOTE}
- Cost numbers use the benchmark's stated assumed input price and are not live provider billing guarantees.
- Raw context still matched PRMR accuracy; PRMR's advantage here is accuracy-per-token under retrieval trap pressure.

## Core Result

- Raw context accuracy: **{raw["continuity_accuracy"]}%**
- Raw context estimated payload: **{raw["payload_tokens"]} tokens**
- Raw context estimated cost / 1,000 sessions: **${raw["estimated_cost_per_1000_sessions_usd"]}**
- PRMR accuracy: **{prmr["continuity_accuracy"]}%**
- PRMR estimated downstream payload: **{prmr["payload_tokens"]} tokens**
- PRMR estimated cost / 1,000 sessions: **${prmr["estimated_cost_per_1000_sessions_usd"]}**
- PRMR reduction vs raw context: **{summary["prmr_token_reduction_vs_raw_percent"]}%**
- Keyword accuracy under retrieval traps: **{keyword["continuity_accuracy"]}%**
- Vector-like accuracy under retrieval traps: **{vector["continuity_accuracy"]}%**

## Method Table

| Method | Accuracy | Estimated Payload Tokens | Reduction vs Raw | Estimated Cost / 1,000 Sessions |
|---|---:|---:|---:|---:|
"""

    for name, result in results.items():
        scorecard += (
            f"| {name} | {result['continuity_accuracy']}% | "
            f"{result['payload_tokens']} | "
            f"{result['token_reduction_vs_raw_percent']}% | "
            f"${result['estimated_cost_per_1000_sessions_usd']} |\n"
        )

    scorecard += """

## Meaning

V0.41.2 is a hard internal benchmark for memory-token tax under retrieval traps.

It does not claim live billing certainty.  
It does not claim raw context is inaccurate.  
It claims PRMR preserved continuity with a much smaller benchmark-estimated downstream memory payload.

Test. Break. Patch. Rerun. Score. Climb.
"""

    SCORECARD_0412.write_text(scorecard, encoding="utf-8")

    # Patch audit JSON if it exists.
    audit_summary = None

    if AUDIT_0413.exists():
        audit = load_json(AUDIT_0413)
        audit["honest_claim"] = SAFE_CLAIM
        audit["claim_safety_notes"] = {
            "token_definition": TOKEN_DEFINITION,
            "raw_context_note": RAW_CONTEXT_NOTE,
            "prmr_packet_note": PRMR_PACKET_NOTE,
        }
        save_json(AUDIT_0413, audit)
        audit_summary = audit.get("verdict")

    # Patch audit markdown if it exists.
    if AUDIT_MD_0413.exists():
        old_md = AUDIT_MD_0413.read_text(encoding="utf-8")
        hardened_md = old_md + f"""

---

## V0.41.4 Claim Hardening Addendum

{SAFE_CLAIM}

### Token Definition

{TOKEN_DEFINITION}

### Raw Context Note

{RAW_CONTEXT_NOTE}

### PRMR Packet Note

{PRMR_PACKET_NOTE}
"""
        AUDIT_MD_0413.write_text(hardened_md, encoding="utf-8")

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.41.4",
        "report_type": "claim_hardening_and_token_definition_patch",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "safe_claim": SAFE_CLAIM,
        "token_definition": TOKEN_DEFINITION,
        "raw_context_note": RAW_CONTEXT_NOTE,
        "prmr_packet_note": PRMR_PACKET_NOTE,
        "patched_public_files": [
            str(PUBLIC_0412),
            str(SCORECARD_0412),
        ],
        "restricted_artifacts_updated": bool(PRIVATE_0412.exists()),
        "audit_artifacts_updated": bool(AUDIT_0413.exists() or AUDIT_MD_0413.exists()),
        "audit_summary": audit_summary,
        "verdict": "V0.41.2 token/cost claim hardened for honest public/investor-safe language."
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.41.4 Claim Hardening + Token Definition Patch

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.41.4  

## Verdict

V0.41.2 token/cost claim hardened for honest public/investor-safe language.

## Safe Claim

{SAFE_CLAIM}

## Token Definition

{TOKEN_DEFINITION}

## Raw Context Note

{RAW_CONTEXT_NOTE}

## PRMR Packet Note

{PRMR_PACKET_NOTE}

## Patched Files

- {PUBLIC_0412}
- {SCORECARD_0412}

Restricted and audit artifacts were updated when present; public output does not list restricted file paths.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("PRMR V0.41.4 CLAIM HARDENING COMPLETE")
    print("-------------------------------------")
    print("Safe claim:")
    print(SAFE_CLAIM)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()
