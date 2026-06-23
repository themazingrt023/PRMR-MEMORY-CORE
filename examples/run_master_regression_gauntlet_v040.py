import subprocess
import json
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path("reports/v040")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    {
        "name": "V0.36 Trust Suite",
        "command": ["python", "benchmarks/runners/run_trust_suite_v036.py"],
        "required_output": "V0.36 TRUST SUITE RESULT: PASS"
    },
    {
        "name": "V0.37 Realistic Memory Benchmark",
        "command": ["python", "benchmarks/runners/run_realistic_memory_benchmark_v037.py"],
        "required_output": "V0.37 REALISTIC MEMORY BENCHMARK: PASS"
    },
    {
        "name": "V0.37.1 Result Integrity Audit",
        "command": ["python", "examples/audit_v0371_result_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.38.1 Baseline War Anti-Leak",
        "command": ["python", "benchmarks/runners/run_baseline_war_antileak_v0381.py"],
        "required_output": "Result: PASS"
    },
    {
        "name": "V0.38.2 Baseline War Integrity Audit",
        "command": ["python", "examples/audit_v0382_baseline_war_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.39 Adversarial Memory Trial",
        "command": ["python", "benchmarks/runners/run_adversarial_memory_trial_v039.py"],
        "required_output": "Result: PASS"
    },
    {
        "name": "V0.39.1 Adversarial Integrity + Fairness Audit",
        "command": ["python", "examples/audit_v0391_adversarial_integrity.py"],
        "required_output": "All checks passed: True"
    },
]


def run_command(item):
    print()
    print("=" * 70)
    print(item["name"])
    print("=" * 70)

    completed = subprocess.run(
        item["command"],
        capture_output=True,
        text=True,
        shell=False
    )

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")

    passed = (
        completed.returncode == 0
        and item["required_output"] in output
    )

    print(output)

    return {
        "name": item["name"],
        "command": " ".join(item["command"]),
        "returncode": completed.returncode,
        "required_output": item["required_output"],
        "passed": passed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main():
    print("PRMR V0.40 MASTER REGRESSION GAUNTLET")
    print("-------------------------------------")

    results = [run_command(item) for item in COMMANDS]

    passed_count = sum(1 for item in results if item["passed"])
    total_count = len(results)
    all_passed = passed_count == total_count

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.40",
        "report_type": "master_regression_gauntlet",
        "timestamp": datetime.now().isoformat(),
        "passed_count": passed_count,
        "total_count": total_count,
        "all_passed": all_passed,
        "result": "PASS" if all_passed else "NEEDS_WORK",
        "checks": [
            {
                "name": item["name"],
                "command": item["command"],
                "returncode": item["returncode"],
                "required_output": item["required_output"],
                "passed": item["passed"],
            }
            for item in results
        ],
        "note": "Full stdout/stderr is stored in private report only."
    }

    private_report = {
        **report,
        "public_safe": False,
        "full_outputs": results
    }

    public_report = {
        **report,
        "public_safe": True
    }

    public_path = REPORT_DIR / "public_master_regression_gauntlet_v040.json"
    private_path = REPORT_DIR / "private_internal_master_regression_gauntlet_v040.json"
    scorecard_path = REPORT_DIR / "scorecard_v040.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.40 Master Regression Gauntlet

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.40  

## Result

**{report["result"]}**

Passed: **{passed_count}/{total_count}**

## Checks

"""

    for item in report["checks"]:
        status = "PASS" if item["passed"] else "FAIL"
        md += f"- **{status}** — {item['name']}\n"

    md += """

## Meaning

This gauntlet reruns the major benchmark and audit chain to make sure new engine changes do not break earlier proof layers.

It is internal regression evidence, not production certification.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    scorecard_path.write_text(md, encoding="utf-8")

    print()
    print("PRMR V0.40 MASTER REGRESSION GAUNTLET RESULT")
    print("--------------------------------------------")
    print("Passed:", f"{passed_count}/{total_count}")
    print("Result:", report["result"])
    print()
    print("Created:")
    print(public_path)
    print(private_path)
    print(scorecard_path)


if __name__ == "__main__":
    main()