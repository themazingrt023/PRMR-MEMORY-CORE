import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path("reports/v0415")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    {
        "name": "V0.36 Trust Suite",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_trust_suite_v036.py"],
        "required_output": "V0.36 TRUST SUITE RESULT: PASS"
    },
    {
        "name": "V0.37 Realistic Memory Benchmark",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_realistic_memory_benchmark_v037.py"],
        "required_output": "V0.37 REALISTIC MEMORY BENCHMARK: PASS"
    },
    {
        "name": "V0.37.1 Result Integrity Audit",
        "command": [sys.executable, "-X", "utf8", "examples/audit_v0371_result_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.38.1 Baseline War Anti-Leak",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_baseline_war_antileak_v0381.py"],
        "required_output": "Result: PASS"
    },
    {
        "name": "V0.38.2 Baseline War Integrity Audit",
        "command": [sys.executable, "-X", "utf8", "examples/audit_v0382_baseline_war_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.39 Adversarial Memory Trial",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_adversarial_memory_trial_v039.py"],
        "required_output": "Result: PASS"
    },
    {
        "name": "V0.39.1 Adversarial Integrity + Fairness Audit",
        "command": [sys.executable, "-X", "utf8", "examples/audit_v0391_adversarial_integrity.py"],
        "required_output": "All checks passed: True"
    },
    {
        "name": "V0.40 Master Regression Gauntlet",
        "command": [sys.executable, "-X", "utf8", "examples/run_master_regression_gauntlet_v040.py"],
        "required_output": "Result: PASS"
    },
    {
        "name": "V0.41 Token Tax / Cost War",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_token_tax_cost_war_v041.py"],
        "required_output": "result: PASS"
    },
    {
        "name": "V0.41.1 Token Tax Integrity Audit",
        "command": [sys.executable, "-X", "utf8", "examples/audit_v0411_token_tax_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.41.2 Hard Token Tax / Cost War",
        "command": [sys.executable, "-X", "utf8", "benchmarks/runners/run_hard_token_tax_cost_war_v0412.py"],
        "required_output": "result: PASS"
    },
    {
        "name": "V0.41.3 Hard Token Tax Integrity Audit",
        "command": [sys.executable, "-X", "utf8", "examples/audit_v0413_hard_token_tax_integrity.py"],
        "required_output": "All integrity checks passed: True"
    },
    {
        "name": "V0.41.4 Claim Hardening",
        "command": [sys.executable, "-X", "utf8", "examples/patch_v0414_claim_hardening.py"],
        "required_output": "PRMR V0.41.4 CLAIM HARDENING COMPLETE"
    },
]


def run_command(item):
    print()
    print("=" * 76)
    print(item["name"])
    print("=" * 76)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        item["command"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        env=env
    )

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")

    passed = completed.returncode == 0 and item["required_output"] in output

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
    print("PRMR V0.41.5 EXPANDED MASTER REGRESSION GAUNTLET")
    print("------------------------------------------------")

    results = [run_command(item) for item in COMMANDS]

    passed_count = sum(1 for item in results if item["passed"])
    total_count = len(results)
    all_passed = passed_count == total_count

    report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.41.5",
        "report_type": "expanded_master_regression_gauntlet",
        "timestamp": datetime.now().isoformat(),
        "public_safe": True,
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
        "safe_claim": (
            "PRMR Memory Core has a repeatable internal proof chain covering reconstruction, realistic memory, "
            "anti-leak baseline comparison, adversarial continuity, token/cost efficiency, claim hardening, "
            "and regression stability. This is internal regression evidence, not production certification."
        )
    }

    private_report = {
        **report,
        "public_safe": False,
        "full_outputs": results
    }

    public_path = REPORT_DIR / "public_expanded_master_gauntlet_v0415.json"
    private_path = REPORT_DIR / "private_internal_expanded_master_gauntlet_v0415.json"
    scorecard_path = REPORT_DIR / "scorecard_v0415.md"

    public_path.write_text(json.dumps(report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.41.5 Expanded Master Regression Gauntlet

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.41.5  

## Result

**{report["result"]}**

Passed: **{passed_count}/{total_count}**

## Safe Claim

{report["safe_claim"]}

## Checks

"""

    for item in report["checks"]:
        status = "PASS" if item["passed"] else "FAIL"
        md += f"- **{status}** — {item['name']}\n"

    md += """

## Meaning

This expanded gauntlet reruns the major benchmark, audit, token/cost, claim-hardening, and regression chain.

It proves the current local proof chain survives reruns.  
It does not mean production certification.

## Build Mantra

Test. Break. Patch. Rerun. Score. Climb.
"""

    scorecard_path.write_text(md, encoding="utf-8")

    print()
    print("PRMR V0.41.5 EXPANDED MASTER GAUNTLET RESULT")
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