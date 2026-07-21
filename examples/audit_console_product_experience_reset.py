"""Audit the PRMR Console Product Experience Reset."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "console_product_experience_reset"
PUBLIC_REPORT = REPORT_DIR / "public_console_product_experience_reset_audit.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_console_product_experience_reset_audit.json"
SCORECARD = REPORT_DIR / "scorecard_console_product_experience_reset_audit.md"
BOUNDARY = (
    "Console Product Experience Reset audit. PASS means local synthetic UX, "
    "backend endpoint, test/live isolation, and regression checks passed. It "
    "does not claim production auth hardening, live billing, compliance "
    "approval, legal approval, external security certification, or external "
    "real-world validation."
)


REQUIRED_FILES = [
    ROOT / "frontend" / "components" / "dashboard" / "HostedSelfServeDashboard.tsx",
    ROOT / "frontend" / "components" / "console" / "ConsoleShell.tsx",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "events" / "route.ts",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "packets" / "route.ts",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "packets" / "[packetId]" / "route.ts",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "actors" / "route.ts",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "usage" / "live" / "route.ts",
    ROOT / "examples" / "run_console_product_experience_reset.py",
]


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def command(args: list[str], cwd: Path = ROOT, timeout: int = 240) -> tuple[bool, str]:
    completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-3000:]


def has_secret(payload: str) -> bool:
    return bool(re.search(r"prmr_(?:alpha|live)_[A-Za-z0-9_\-]{24,}", payload))


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "required_files_exist", all(path.exists() for path in REQUIRED_FILES), [str(path) for path in REQUIRED_FILES if not path.exists()])
    console_text = text(ROOT / "frontend" / "components" / "dashboard" / "HostedSelfServeDashboard.tsx") + text(ROOT / "frontend" / "components" / "console" / "ConsoleShell.tsx")
    add(checks, "console_primary_nav_is_product_focused", all(term in console_text for term in ["Home", "Playground", "Events", "Packets", "Actors", "API Keys", "Usage", "Logs", "How to Use", "Settings"]), None)
    add(checks, "console_does_not_lead_with_infrastructure", not any(term in console_text for term in ["Vault ID", "Namespace", "Storage backend", "Scope Resolution", "Internal Reports"]), None)
    add(checks, "playground_test_mode_copy_present", "TEST MODE" in console_text and "isolated and will not affect live continuity" in console_text, None)
    add(checks, "billing_hidden", "Upgrade plan" not in console_text and "Billing" not in text(ROOT / "frontend" / "components" / "console" / "ConsoleShell.tsx"), None)
    add(checks, "public_nav_has_no_docs", "Docs" not in text(ROOT / "frontend" / "components" / "landing" / "Navigation.tsx"), None)
    add(checks, "no_raw_secret_literals", not has_secret(console_text), None)

    reset_ok, reset_output = command(["python", "examples/run_console_product_experience_reset.py"], ROOT, timeout=180)
    add(checks, "console_product_reset_runner_passes", reset_ok, reset_output)

    ref_ok, ref_output = command(["python", "examples/run_real_client_reference_contract_sprint.py"], ROOT, timeout=180)
    add(checks, "external_reference_client_regression_passes", ref_ok, ref_output)

    npm = "npm.cmd" if os.name == "nt" else "npm"
    type_ok, type_output = command([npm, "run", "typecheck"], ROOT / "frontend", timeout=180)
    add(checks, "frontend_typecheck_passes", type_ok, type_output)
    build_ok, build_output = command([npm, "run", "build"], ROOT / "frontend", timeout=240)
    add(checks, "frontend_build_passes", build_ok, build_output)

    public_reset = text(ROOT / "reports" / "console_product_experience_reset" / "public_console_product_experience_reset.json")
    add(checks, "public_report_secret_safe", public_reset != "" and not has_secret(public_reset), None)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "console_product_experience_reset",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Console Product Experience Reset Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "truth_label": "local synthetic console product experience evidence",
        "public_safe": True,
        "raw_keys_exposed": False,
        "billing_exposed": False,
        "boundary": BOUNDARY,
        "remaining_blockers": [
            "Render backend redeploy required for new hosted dashboard endpoints",
            "hosted console smoke after backend redeploy",
            "real customer UX observation",
            "delete actor data backend enforcement before enabling destructive UI",
        ],
    }
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, {**public, "checks": checks, "public_safe": False})
    SCORECARD.write_text(
        f"# Console Product Experience Reset Audit\n\nResult: {result}\nChecks: {public['checks_passed']}/{public['checks_total']}\n\nBoundary: {BOUNDARY}\n",
        encoding="utf-8",
    )
    print("PRMR Console Product Experience Reset Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    for failure in failures:
        print(f"FAIL: {failure['name']}")
        print(str(failure.get("detail"))[-1000:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
