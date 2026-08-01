"""Run the mandatory Core Sprint 1-12 and secret-hygiene regressions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/core_continuity_packet_v2/regression_results_continuity_packet_v2.json"

COMMANDS = (
    ("core_sprint_01_runner", "examples/run_core_source_ledger_provenance.py"),
    ("core_sprint_01_audit", "examples/audit_core_source_ledger_provenance.py"),
    ("core_sprint_02_runner", "examples/run_core_candidate_memory_engine.py"),
    ("core_sprint_02_audit", "examples/audit_core_candidate_memory_engine.py"),
    ("core_sprint_03_runner", "examples/run_core_memory_admission.py"),
    ("core_sprint_03_audit", "examples/audit_core_memory_admission.py"),
    ("core_sprint_04_runner", "examples/run_core_memory_ledger_evolution.py"),
    ("core_sprint_04_audit", "examples/audit_core_memory_ledger_evolution.py"),
    ("core_sprint_05_runner", "examples/run_core_temporal_memory_dynamics.py"),
    ("core_sprint_05_audit", "examples/audit_core_temporal_memory_dynamics.py"),
    ("core_sprint_06_runner", "examples/run_core_entity_relationship_memory.py"),
    ("core_sprint_06_audit", "examples/audit_core_entity_relationship_memory.py"),
    ("core_sprint_07_runner", "examples/run_core_memory_query.py"),
    ("core_sprint_07_audit", "examples/audit_core_memory_query.py"),
    ("core_sprint_08_runner", "examples/run_core_memory_consolidation.py"),
    ("core_sprint_08_audit", "examples/audit_core_memory_consolidation.py"),
    ("core_sprint_09_runner", "examples/run_core_semantic_interpretation.py"),
    ("core_sprint_09_audit", "examples/audit_core_semantic_interpretation.py"),
    ("core_sprint_10_runner", "examples/run_core_memory_governance.py"),
    ("core_sprint_10_audit", "examples/audit_core_memory_governance.py"),
    ("core_sprint_11_runner", "examples/run_core_postgres_runtime_validation.py"),
    ("core_sprint_11_audit", "examples/audit_core_postgres_runtime_validation.py"),
    ("core_sprint_12_runner", "examples/run_core_memory_quality_benchmark.py"),
    ("core_sprint_12_audit", "examples/audit_core_memory_quality_benchmark.py"),
    ("secret_hygiene", "examples/audit_v0782_secret_cleanup.py"),
)


def _safe_tail(value: str, maximum_lines: int = 8) -> list[str]:
    forbidden = ("postgresql://", "postgres://", "authorization: bearer")
    lines = []
    for line in value.splitlines()[-maximum_lines:]:
        lowered = line.lower()
        if any(pattern in lowered for pattern in forbidden):
            lines.append("[redacted connection or credential output]")
        else:
            lines.append(line[:500])
    return lines


def main() -> int:
    failed_only = "--failed-only" in sys.argv[1:]
    previous_by_name: dict[str, dict[str, Any]] = {}
    if failed_only and REPORT.exists():
        previous = json.loads(REPORT.read_text(encoding="utf-8"))
        previous_by_name = {
            str(item["name"]): item for item in previous.get("commands", [])
        }
    results: list[dict[str, Any]] = []
    for name, script in COMMANDS:
        previous_result = previous_by_name.get(name)
        if previous_result and previous_result.get("passed") is True:
            results.append(previous_result)
            print(f"Reusing current-turn PASS for {name}.", flush=True)
            continue
        started = time.perf_counter()
        print(f"Running {name}...", flush=True)
        try:
            completed = subprocess.run(
                [sys.executable, script],
                cwd=ROOT,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2_400,
                check=False,
            )
            result = {
                "name": name,
                "script": script,
                "return_code": completed.returncode,
                "passed": completed.returncode == 0,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "stdout_tail": _safe_tail(completed.stdout),
                "stderr_tail": _safe_tail(completed.stderr),
            }
        except subprocess.TimeoutExpired as exc:
            result = {
                "name": name,
                "script": script,
                "return_code": None,
                "passed": False,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "safe_error": "REGRESSION_TIMEOUT",
                "stdout_tail": _safe_tail(str(exc.stdout or "")),
                "stderr_tail": _safe_tail(str(exc.stderr or "")),
            }
        results.append(result)
        print(f"{name}: {'PASS' if result['passed'] else 'NEEDS_WORK'}", flush=True)
    passed = sum(item["passed"] for item in results)
    payload = {
        "sprint": "Core Sprint 13",
        "suite": "Core Sprint 1-12 and secret-hygiene regressions",
        "postgres_guard_required": True,
        "database_url_recorded": False,
        "passed_commands": passed,
        "total_commands": len(results),
        "commands": results,
        "result": "PASS" if passed == len(results) else "NEEDS_WORK",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Passed regression commands: {passed}/{len(results)}")
    print(f"Result: {payload['result']}")
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
