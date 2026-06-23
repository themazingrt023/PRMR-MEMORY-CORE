"""Audit V0.72 client dashboard MVP."""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

FRONTEND = ROOT / "frontend"
AGGREGATOR = ROOT / "prmr" / "product" / "client_dashboard_v072.py"
RUNNER = ROOT / "examples" / "run_client_dashboard_mvp_v072.py"
REPORT_DIR = ROOT / "reports" / "v072"
PUBLIC_REPORT = REPORT_DIR / "public_client_dashboard_mvp_v072.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_client_dashboard_mvp_v072.json"
DASHBOARD_DATA = REPORT_DIR / "dashboard_data_v072.json"
SCORECARD = REPORT_DIR / "scorecard_v072.md"

SOURCE_INPUTS = [
    ROOT / "reports" / "v069" / "public_hosted_backend_foundation_v069.json",
    ROOT / "reports" / "v069" / "private_internal_hosted_backend_foundation_v069.json",
    ROOT / "reports" / "v070" / "public_api_key_lifecycle_v070.json",
    ROOT / "reports" / "v070" / "private_internal_api_key_lifecycle_v070.json",
    ROOT / "reports" / "v071" / "public_controlled_alpha_api_v071.json",
    ROOT / "reports" / "v071" / "private_internal_controlled_alpha_api_v071.json",
]

FRONTEND_FILES = [
    FRONTEND / "app" / "dashboard" / "page.tsx",
    FRONTEND / "data" / "dashboardMockData.ts",
    FRONTEND / "components" / "dashboard" / "ClientOverview.tsx",
    FRONTEND / "components" / "dashboard" / "ApiKeyPanel.tsx",
    FRONTEND / "components" / "dashboard" / "VaultNamespacePanel.tsx",
    FRONTEND / "components" / "dashboard" / "UsageOverview.tsx",
    FRONTEND / "components" / "dashboard" / "RequestLogTable.tsx",
    FRONTEND / "components" / "dashboard" / "ReportsPanel.tsx",
    FRONTEND / "components" / "dashboard" / "MemoryHealthPanel.tsx",
]

REQUIRED_PANELS = [
    "client_overview",
    "api_key_panel",
    "vault_namespace_panel",
    "usage_overview",
    "request_log_summary",
    "reports_panel",
    "memory_health_panel",
]

REQUIRED_BLOCKED_REASONS = {
    "missing_key",
    "invalid_key",
    "key_client_mismatch",
    "vault_denied",
    "namespace_denied",
    "rotated_key",
    "revoked_key",
    "usage_limit_exceeded",
}

PUBLIC_RESTRICTED_TERMS = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "private packet",
    "internal packet",
    "key_hash",
    "validation_outcomes",
    "debug_trace",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted dashboard is live",
    "hosted api is live",
    "live api access granted",
    "billing enabled",
    "self-serve access enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], cwd: Path, timeout: int = 240) -> dict[str, Any]:
    resolved_command = command[:]
    if resolved_command and resolved_command[0] == "npm":
        resolved_command[0] = shutil.which("npm") or shutil.which("npm.cmd") or "npm.cmd"
    completed = subprocess.run(
        resolved_command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = json.dumps(payload, sort_keys=True).lower() if not isinstance(payload, str) else payload.lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def build_scorecard(checks: list[dict[str, Any]], command_results: list[dict[str, Any]]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.72 Client Dashboard MVP Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.72 is a local/deployable client dashboard MVP only. It is not hosted customer authentication, not a production portal, not billing, not self-serve access, not live API access, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    lines.extend(["", "## Command Results", ""])
    for result_item in command_results:
        status = "PASS" if result_item["passed"] else "FAIL"
        lines.append(f"- {status}: {result_item['command']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    for path in SOURCE_INPUTS:
        add_check(checks, f"{path.parent.name}_{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    add_check(checks, "aggregator_exists", AGGREGATOR.exists(), str(AGGREGATOR.relative_to(ROOT)))
    module = importlib.import_module("prmr.product.client_dashboard_v072")
    add_check(checks, "build_dashboard_data_exists", hasattr(module, "build_dashboard_data"), "build_dashboard_data")
    add_check(checks, "generate_dashboard_reports_exists", hasattr(module, "generate_dashboard_reports"), "generate_dashboard_reports")

    command_results: list[dict[str, Any]] = []
    runner_result = run_command(["python", str(RUNNER)], ROOT)
    command_results.append(runner_result)
    add_check(checks, "runner_passes", runner_result["passed"], runner_result["output"][-1000:])

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, DASHBOARD_DATA, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    dashboard_data = read_json(DASHBOARD_DATA) if DASHBOARD_DATA.exists() else {}
    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}

    for panel in REQUIRED_PANELS:
        add_check(checks, f"{panel}_in_dashboard_data", panel in dashboard_data, panel)

    safe_key_text = json.dumps(dashboard_data.get("api_key_panel", {}), sort_keys=True)
    add_check(checks, "api_key_panel_safe_preview_only", "safe_key_preview" in safe_key_text and "key_hash" not in safe_key_text, None)
    add_check(checks, "dashboard_data_no_full_raw_keys", not contains_full_dev_key(dashboard_data), None)

    blocked_reasons = set(dashboard_data.get("request_log_summary", {}).get("blocked_reasons", {}).keys())
    add_check(checks, "blocked_reasons_complete", REQUIRED_BLOCKED_REASONS.issubset(blocked_reasons), sorted(blocked_reasons))
    add_check(checks, "boundary_notice_present", "local controlled-alpha dashboard MVP" in dashboard_data.get("dashboard_notice", ""), dashboard_data.get("dashboard_notice"))
    add_check(checks, "memory_health_panel_has_state", dashboard_data.get("memory_health_panel", {}).get("packets_generated", 0) >= 1, dashboard_data.get("memory_health_panel"))

    public_terms = scan_terms(public_report, PUBLIC_RESTRICTED_TERMS)
    add_check(checks, "public_report_no_restricted_terms", not public_terms, public_terms)
    add_check(checks, "public_report_no_full_raw_keys", not contains_full_dev_key(public_report), None)
    add_check(checks, "public_report_no_overclaims", not scan_terms(public_report, OVERCLAIMS), scan_terms(public_report, OVERCLAIMS))
    add_check(checks, "public_report_non_punitive", not scan_terms(public_report, PUNITIVE_TERMS), scan_terms(public_report, PUNITIVE_TERMS))
    add_check(checks, "private_report_contains_detailed_checks", bool(private_report.get("checks")), len(private_report.get("checks", [])))

    for path in FRONTEND_FILES:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    dashboard_route_source = (FRONTEND / "app" / "dashboard" / "page.tsx").read_text(encoding="utf-8") if (FRONTEND / "app" / "dashboard" / "page.tsx").exists() else ""
    add_check(checks, "dashboard_route_public_mode_gated", "isPublicFrontendMode()" in dashboard_route_source and "DashboardDisabled" in dashboard_route_source, None)
    add_check(checks, "dashboard_route_shows_public_disabled_boundary", "not enabled on the public frontend" in dashboard_route_source, None)
    for component_name in ["ClientOverview", "ApiKeyPanel", "VaultNamespacePanel", "UsageOverview", "RequestLogTable", "ReportsPanel", "MemoryHealthPanel"]:
        add_check(checks, f"{component_name}_rendered_by_route", f"<{component_name}" in dashboard_route_source, component_name)

    frontend_text = "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND_FILES if path.exists())
    add_check(checks, "frontend_no_full_raw_keys", not contains_full_dev_key(frontend_text), None)
    add_check(checks, "frontend_no_overclaims", not scan_terms(frontend_text, OVERCLAIMS), scan_terms(frontend_text, OVERCLAIMS))
    add_check(checks, "frontend_non_punitive", not scan_terms(frontend_text, PUNITIVE_TERMS), scan_terms(frontend_text, PUNITIVE_TERMS))
    add_check(checks, "frontend_synthetic_data_label_present", "synthetic/dev-only" in frontend_text, None)

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND, timeout=240)
    command_results.append(typecheck)
    add_check(checks, "npm_run_typecheck_passes", typecheck["passed"], typecheck["output"][-1000:])

    build = run_command(["npm", "run", "build"], FRONTEND, timeout=300)
    command_results.append(build)
    add_check(checks, "npm_run_build_passes", build["passed"], build["output"][-1200:])

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, command_results), encoding="utf-8")

    print("PRMR Memory Core V0.72 Client Dashboard MVP Audit")
    for item in command_results:
        print(f"{'PASS' if item['passed'] else 'FAIL'}: {item['command']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
