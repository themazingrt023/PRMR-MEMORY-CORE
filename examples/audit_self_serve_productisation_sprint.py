"""Audit the PRMR self-serve productisation sprint deliverables."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT_DIR = ROOT / "reports" / "self_serve_productisation_sprint"
PUBLIC_REPORT = REPORT_DIR / "public_self_serve_productisation_audit.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_self_serve_productisation_audit.json"
SCORECARD = REPORT_DIR / "scorecard_self_serve_productisation_audit.md"
BOUNDARY = (
    "Self-serve productisation sprint audit. PASS means the local/deployable "
    "first-run activation flow passed with documented limitations. It does not "
    "mean production authentication hardening, live billing, compliance "
    "approval, legal approval, external security certification, or external "
    "real-world validation."
)

REQUIRED_FILES = [
    ROOT / "docs" / "self_serve_productisation_sprint.md",
    ROOT / "docs" / "five_minute_quickstart.md",
    ROOT / "docs" / "domain_surface_migration_plan.md",
    ROOT / "docs" / "billing_entitlement_model.md",
    ROOT / "examples" / "run_self_serve_productisation_sprint.py",
    ROOT / "frontend" / "app" / "start" / "page.tsx",
    ROOT / "frontend" / "components" / "self-serve" / "StartFlow.tsx",
    ROOT / "frontend" / "components" / "dashboard" / "HostedSelfServeDashboard.tsx",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "playground" / "event" / "route.ts",
    ROOT / "frontend" / "app" / "api" / "dashboard" / "playground" / "packet" / "route.ts",
]


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def command(args: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0, (completed.stdout + "\n" + completed.stderr).strip()[-2600:]


def contains_secret(text: str) -> bool:
    patterns = [
        r"prmr_(?:alpha|live)_[A-Za-z0-9_\-]{24,}",
        r"sk-[A-Za-z0-9_\-]{16,}",
        r"github_pat_[A-Za-z0-9_]+",
        r"ghp_[A-Za-z0-9_]+",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "required_files_exist", all(path.exists() for path in REQUIRED_FILES), [str(path) for path in REQUIRED_FILES if not path.exists()])
    combined = "\n".join(file_text(path) for path in REQUIRED_FILES)
    add(checks, "welcome_and_continuity_copy_present", "Send events. Receive continuity." in combined and "Welcome to PRMR Memory Core" in combined, None)
    add(checks, "automatic_bootstrap_documented", all(term in combined for term in ["client ID", "vault ID", "namespace", "copy-once", "sandbox"]), None)
    add(checks, "quickstart_has_two_actions", "/v1/events/ingest" in combined and "/v1/continuity/packet" in combined, None)
    add(checks, "scope_headers_not_required", "Scope headers are optional assertions" in combined, None)
    add(checks, "billing_boundary_present", "Billing is not live" in combined and "payment collection is not live" in combined, None)
    add(checks, "subdomain_plan_present", "app.afternumindustries.co.uk" in combined and "api.afternumindustries.co.uk" in combined, None)
    add(checks, "no_secret_patterns_in_docs_or_frontend", not contains_secret(combined), None)
    unsafe_claims = [
        "production ready",
        "production-ready",
        "compliance approved",
        "legal approval granted",
        "security certified",
        "certified secure",
        "guaranteed results",
    ]
    add(checks, "no_unsafe_claims", not any(term in combined.lower() for term in unsafe_claims), None)

    runner_ok, runner_output = command(["python", "examples/run_self_serve_productisation_sprint.py"])
    add(checks, "self_serve_productisation_runner_passes", runner_ok, runner_output)

    npm = "npm.cmd" if os.name == "nt" else "npm"
    type_ok, type_output = command([npm, "run", "typecheck"], ROOT / "frontend")
    add(checks, "frontend_typecheck_passes", type_ok, type_output)
    build_ok, build_output = command([npm, "run", "build"], ROOT / "frontend")
    add(checks, "frontend_build_passes", build_ok, build_output)

    public_report_text = file_text(REPORT_DIR / "public_self_serve_productisation_sprint.json")
    add(checks, "public_report_has_no_secret_patterns", public_report_text != "" and not contains_secret(public_report_text), None)

    failures = [check for check in checks if not check["passed"]]
    result = "PASS" if not failures else "NEEDS_WORK"
    public = {
        "version": "self_serve_productisation_sprint",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Self-Serve Productisation Sprint Audit",
        "result": result,
        "checks_passed": len(checks) - len(failures),
        "checks_total": len(checks),
        "truth_label": "local/deployable first-run activation audit",
        "public_safe": True,
        "raw_keys_exposed": False,
        "billing_live": False,
        "boundary": BOUNDARY,
        "remaining_gaps": [
            "live billing/checkout",
            "production authentication hardening",
            "hosted load testing",
            "external stranger activation completion evidence",
            "custom API subdomain smoke after DNS migration",
        ],
    }
    private = {**public, "checks": checks, "public_safe": False}
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    SCORECARD.write_text(
        "\n".join(
            [
                "# Self-Serve Productisation Sprint Audit",
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
    print("PRMR Self-Serve Productisation Sprint Audit")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {result}")
    for failure in failures:
        print(f"FAIL: {failure['name']}")
        print(str(failure.get("detail"))[-800:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
