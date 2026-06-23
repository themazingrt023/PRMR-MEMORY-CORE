import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("reports/v049")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "fraud_track_master_gauntlet_v049.json"
OUT_MD = OUT_DIR / "fraud_track_master_gauntlet_v049.md"

COMMANDS = [
    {
        "name": "v045_fraud_continuity_simulator",
        "command": ["python", "benchmarks/runners/run_fraud_continuity_simulator_v045.py"],
        "expected_phrases": ["Passed checks: 8/8", "Result: PASS"],
    },
    {
        "name": "v0451_fraud_simulator_integrity_audit",
        "command": ["python", "examples/audit_v0451_fraud_simulator_integrity.py"],
        "expected_phrases": ["Passed checks: 11/11", "All integrity checks passed: True"],
    },
    {
        "name": "v0452_fraud_report_leak_scan",
        "command": ["python", "examples/audit_v0452_fraud_report_leak_scan.py"],
        "expected_phrases": ["Passed checks: 3/3", "Result: PASS"],
    },
    {
        "name": "v046_fraud_baseline_war",
        "command": ["python", "benchmarks/runners/run_fraud_baseline_war_v046.py"],
        "expected_phrases": ["Passed checks: 9/9", "Result: PASS"],
    },
    {
        "name": "v0461_pattern_preservation_compression_audit",
        "command": ["python", "examples/audit_v0461_pattern_preservation_compression.py"],
        "expected_phrases": ["Passed checks: 7/7", "Result: PASS"],
    },
    {
        "name": "v0462_fraud_baseline_pattern_integrity_audit",
        "command": ["python", "examples/audit_v0462_fraud_baseline_pattern_integrity.py"],
        "expected_phrases": ["Result: PASS"],
    },
    {
        "name": "v047_fraud_explainability_report",
        "command": ["python", "benchmarks/runners/run_fraud_explainability_report_v047.py"],
        "expected_phrases": ["Passed checks: 8/8", "Result: PASS"],
    },
    {
        "name": "v0471_explainability_integrity_audit",
        "command": ["python", "examples/audit_v0471_explainability_integrity.py"],
        "expected_phrases": ["Passed checks: 11/11", "All integrity checks passed: True"],
    },
    {
        "name": "v0472_explainability_report_leak_scan",
        "command": ["python", "examples/audit_v0472_explainability_report_leak_scan.py"],
        "expected_phrases": ["Passed checks: 4/4", "Result: PASS"],
    },
    {
        "name": "v048_human_harm_reduction_test",
        "command": ["python", "benchmarks/runners/run_human_harm_reduction_test_v048.py"],
        "expected_phrases": ["Passed checks: 11/11", "Result: PASS"],
    },
    {
        "name": "v0481_human_harm_integrity_audit",
        "command": ["python", "examples/audit_v0481_human_harm_integrity.py"],
        "expected_phrases": ["Passed checks: 13/13", "All integrity checks passed: True"],
    },
    {
        "name": "v0482_human_harm_report_leak_scan",
        "command": ["python", "examples/audit_v0482_human_harm_report_leak_scan.py"],
        "expected_phrases": ["Passed checks: 4/4", "Result: PASS"],
    },
]


def run_command(entry):
    completed = subprocess.run(
        entry["command"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")

    expected_results = {
        phrase: phrase in output
        for phrase in entry["expected_phrases"]
    }

    passed = completed.returncode == 0 and all(expected_results.values())

    return {
        "name": entry["name"],
        "command": " ".join(entry["command"]),
        "returncode": completed.returncode,
        "passed": passed,
        "expected_phrase_results": expected_results,
        "output_preview": output[-2000:],
    }


def main():
    print("PRMR V0.49 FRAUD TRACK MASTER GAUNTLET")
    print("--------------------------------------")

    results = []

    for entry in COMMANDS:
        print()
        print("Running:", entry["name"])
        result = run_command(entry)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print("-", status)

        if not result["passed"]:
            print("Failed command:", result["command"])
            print("Output preview:")
            print(result["output_preview"])
            break

    passed_count = sum(1 for result in results if result["passed"])
    total_checks = len(COMMANDS)
    all_passed = passed_count == total_checks
    final_result = "PASS" if all_passed else "NEEDS_WORK"

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.49",
        "report_type": "fraud_track_master_gauntlet",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
        "commands_expected": total_checks,
        "commands_completed": len(results),
        "passed_commands": passed_count,
        "all_commands_passed": all_passed,
        "result": final_result,
        "results": results,
        "safe_claim": (
            "V0.49 reruns the synthetic fraud-continuity track from V0.45 through V0.48.2. "
            "It verifies fraud continuity simulation, integrity audits, report leak scans, baseline comparison, pattern preservation, explainability, and human-harm reduction as a single regression gauntlet."
        ),
        "honest_boundary": (
            "Synthetic internal regression evidence only. Not bank certification, not legal advice, not compliance approval, and not production fraud deployment proof."
        ),
        "next_phase": "V0.50 Pilot Sandbox / Multi-Client Simulation",
    }

    OUT_JSON.write_text(json.dumps(report, indent=4), encoding="utf-8")

    md = [
        "# PRMR V0.49 Fraud Track Master Gauntlet",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.49  ",
        "",
        "## Result",
        "",
        f"**{final_result}**",
        "",
        f"Passed commands: **{passed_count}/{total_checks}**",
        "",
        "## Safe Claim",
        "",
        report["safe_claim"],
        "",
        "## Honest Boundary",
        "",
        report["honest_boundary"],
        "",
        "## Command Results",
        "",
    ]

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        md.append(f"- **{status}** — {result['name']}")

    md.extend([
        "",
        "## Meaning",
        "",
        "This gauntlet checks the full fraud-continuity proof arc in one run.",
        "",
        "It confirms the track still works together after patches, audits, and report hygiene fixes.",
        "",
        "## Build Mantra",
        "",
        "Test. Break. Patch. Rerun. Score. Climb.",
        "",
    ])

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print()
    print("Passed commands:", f"{passed_count}/{total_checks}")
    print("Result:", final_result)
    print()
    print("Created:")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()