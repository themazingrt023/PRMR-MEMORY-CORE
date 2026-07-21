"""Audit PRMR real-client proof and console separation sprint."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "real_client_console_sprint"
PUBLIC_REPORT = REPORT_DIR / "public_real_client_console_audit.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_real_client_console_audit.json"
SCORECARD = REPORT_DIR / "scorecard_real_client_console_audit.md"
BOUNDARY = (
    "Real client and console separation sprint audit. PASS WITH DOCUMENTED "
    "LIMITATIONS means local HTTP public-contract proof and separation prep "
    "passed, while hosted external-client deployment and DNS migration remain "
    "manual. This is not production authentication hardening, live billing, "
    "compliance approval, legal approval, external security certification, or "
    "external real-world validation."
)


REQUIRED = [
    ROOT / "reference-client" / "app" / "page.tsx",
    ROOT / "reference-client" / "app" / "api" / "project" / "action" / "route.ts",
    ROOT / "reference-client" / "app" / "api" / "project" / "packet" / "route.ts",
    ROOT / "reference-client" / "tools" / "hosted-smoke.mjs",
    ROOT / "console" / "app" / "page.tsx",
    ROOT / "console" / "README.md",
    ROOT / "frontend" / "components" / "console" / "ConsoleShell.tsx",
    ROOT / "docs" / "real_client_reference_client_sprint.md",
    ROOT / "docs" / "console_separation_sprint.md",
    ROOT / "docs" / "real_client_console_deployment_runbook.md",
    ROOT / "examples" / "run_real_client_reference_contract_sprint.py",
]


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def command(args: list[str], cwd: Path = ROOT, timeout: int = 180) -> tuple[bool, str, int]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-3000:], completed.returncode


def has_secret(payload: str) -> bool:
    return bool(
        re.search(r"prmr_(?:alpha|live)_[A-Za-z0-9_\-]{24,}", payload)
        or re.search(r"sk-[A-Za-z0-9_\-]{16,}", payload)
        or re.search(r"github_pat_[A-Za-z0-9_]+", payload)
        or re.search(r"ghp_[A-Za-z0-9_]+", payload)
    )


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "required_files_exist", all(path.exists() for path in REQUIRED), [str(path) for path in REQUIRED if not path.exists()])

    reference_text = "\n".join(
        text(path)
        for path in (ROOT / "reference-client").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.name != "package-lock.json"
        and path.suffix in {".ts", ".tsx", ".mjs", ".json", ".css"}
    )
    add(checks, "reference_client_uses_public_endpoints", "/v1/events/ingest" in reference_text and "/v1/continuity/packet" in reference_text, None)
    add(checks, "reference_client_keeps_key_server_side", "process.env.PRMR_API_KEY" in reference_text and "NEXT_PUBLIC_PRMR_API_KEY" not in reference_text, None)
    forbidden_reference_terms = ["prmr.product", "TestClient", "DATABASE_URL", "/api/dashboard", "X-Dashboard-Token", "client_id", "vault_id", "namespace"]
    add(checks, "reference_client_has_no_internal_shortcuts_or_scope_values", not any(term in reference_text for term in forbidden_reference_terms), [term for term in forbidden_reference_terms if term in reference_text])
    add(checks, "reference_client_event_mapping_complete", all(term in reference_text for term in [
        "reference.project.created",
        "reference.project.goal_updated",
        "reference.project.deadline_changed",
        "reference.project.blocker_recorded",
        "reference.project.decision_recorded",
        "reference.project.milestone_completed",
        "prmr_reference_client",
    ]), None)

    console_text = text(ROOT / "frontend" / "components" / "console" / "ConsoleShell.tsx") + "\n" + text(ROOT / "console" / "app" / "page.tsx")
    add(checks, "console_has_operational_nav", all(term in console_text for term in [
        "Overview", "Playground", "API Keys", "Applications", "Events", "Continuity Packets",
        "Request Logs", "Usage", "Billing", "Team", "Settings", "Documentation"
    ]), None)
    add(checks, "console_excludes_marketing_nav", not any(term in console_text for term in ["Problem", "Solution", "Market", "Pilot", "Demo", "Start Building"]), None)

    docs_text = "\n".join(text(path) for path in REQUIRED if path.suffix == ".md")
    add(checks, "deployment_architecture_documented", all(term in docs_text for term in [
        "prmr.afternumindustries.co.uk",
        "app.prmr.afternumindustries.co.uk",
        "api.afternumindustries.co.uk",
        "Supabase redirect",
    ]), None)
    add(checks, "no_unsafe_claims", not any(term in docs_text.lower() for term in [
        "production ready", "compliance approved", "security certified", "guaranteed results", "bank approved"
    ]), None)
    add(checks, "no_secret_patterns", not has_secret(reference_text + docs_text + console_text), None)

    runner_ok, runner_output, _ = command(["python", "examples/run_real_client_reference_contract_sprint.py"], ROOT, timeout=180)
    add(checks, "real_client_local_http_runner_passes", runner_ok, runner_output)

    npm = "npm.cmd" if os.name == "nt" else "npm"
    frontend_type_ok, frontend_type_output, _ = command([npm, "run", "typecheck"], ROOT / "frontend", timeout=180)
    add(checks, "frontend_typecheck_passes", frontend_type_ok, frontend_type_output)
    frontend_build_ok, frontend_build_output, _ = command([npm, "run", "build"], ROOT / "frontend", timeout=240)
    add(checks, "frontend_build_passes", frontend_build_ok, frontend_build_output)

    # The reference client and console roots are prepared for separate deployment.
    # If dependencies are not installed there yet, npm install remains a deployment step.
    hosted_ok, hosted_output, hosted_code = command([npm, "run", "hosted:smoke"], ROOT / "reference-client", timeout=60)
    add(checks, "hosted_reference_smoke_is_honest_without_credentials", hosted_code == 2 and "NEEDS_CREDENTIALS" in hosted_output, hosted_output)

    public_smoke_text = text(REPORT_DIR / "public_real_client_console_sprint.json")
    add(checks, "public_sprint_report_secret_safe", public_smoke_text != "" and not has_secret(public_smoke_text), None)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS WITH DOCUMENTED LIMITATIONS" if not failures else "NEEDS_WORK"
    public = {
        "version": "real_client_console_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Real Client Proof and Console Separation Sprint Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "reference_client_deployment": "prepared_not_deployed",
        "marketing_deployment_url": "https://afternumindustries.co.uk",
        "console_deployment_url": "prepared_for_app.prmr.afternumindustries.co.uk",
        "api_domain": "https://prmr-memory-core-api.onrender.com",
        "dns_status": "planned_not_verified",
        "supabase_redirect_status": "planned_not_verified",
        "legacy_route_redirect_status": "current_dashboard_shell_separated; cross-domain redirect deferred until console DNS verified",
        "public_safe": True,
        "raw_keys_exposed": False,
        "boundary": BOUNDARY,
        "remaining_blockers": [
            "deploy reference-client as its own Vercel app",
            "create server-side PRMR reference-client API key",
            "run hosted reference-client smoke",
            "deploy console as its own Vercel app",
            "configure DNS and Supabase redirects",
            "verify legacy dashboard redirect after console domain is live",
        ],
    }
    private = {**public, "checks": checks, "public_safe": False}
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(
        "\n".join(
            [
                "# Real Client Proof and Console Separation Sprint Audit",
                "",
                f"Result: {result}",
                f"Checks: {public['checks_passed']}/{public['checks_total']}",
                "",
                f"Boundary: {BOUNDARY}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("PRMR Real Client + Console Separation Sprint Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    for failure in failures:
        print(f"FAIL: {failure['name']}")
        print(str(failure.get("detail"))[-1000:])
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
