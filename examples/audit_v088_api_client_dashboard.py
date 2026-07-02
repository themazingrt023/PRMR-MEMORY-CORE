"""Audit the V0.88 API client dashboard and key-creation MVP."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_api_client_dashboard_v088 import (
    PUBLIC_REPORT,
    REPORT_DIR,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_credential,
    run_smoke,
    write_json,
)


PRIVATE_REPORT = REPORT_DIR / "private_internal_api_client_dashboard_v088.json"
MODULE = ROOT / "prmr" / "product" / "client_api_dashboard_v088.py"
DOCS = ROOT / "docs" / "api_client_dashboard_v088.md"
PAGE = FRONTEND / "app" / "dashboard" / "page.tsx"
KEY_PANEL = FRONTEND / "components" / "dashboard" / "ApiKeyPanel.tsx"
QUICKSTART = FRONTEND / "components" / "dashboard" / "QuickstartPanel.tsx"
KEY_ROUTE = FRONTEND / "app" / "api" / "dashboard" / "keys" / "route.ts"


def run_frontend(command: str) -> dict[str, Any]:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    result = subprocess.run(
        [executable, "run", command],
        cwd=FRONTEND,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return {"passed": result.returncode == 0, "returncode": result.returncode, "tail": output[-1800:]}


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def claim_hits(text: str) -> list[str]:
    phrases = [
        "open public signup is available",
        "production authentication complete",
        "production billing enabled",
        "compliance approved",
        "legal approved",
        "external security certified",
    ]
    lowered = text.lower()
    return [phrase for phrase in phrases if phrase in lowered]


def main() -> int:
    checks: list[dict[str, Any]] = []
    v084 = ROOT / "reports" / "v084" / "public_multi_client_isolation_v084.json"
    v085 = ROOT / "reports" / "v085" / "public_client_docs_onboarding_pack_v085.json"
    add(checks, "v084_and_v085_evidence_exists", v084.exists() and v085.exists())
    add(checks, "dashboard_module_exists", MODULE.exists())
    add(checks, "dashboard_docs_exist", DOCS.exists())
    add(checks, "frontend_dashboard_files_exist", all(path.exists() for path in [PAGE, KEY_PANEL, QUICKSTART, KEY_ROUTE]))

    public_report, private_report, smoke_report, smoke_checks = run_smoke()
    smoke_by_name = {check["name"]: check for check in smoke_checks}
    for audit_name, smoke_name in [
        ("approved_client_dashboard_works", "approved_client_dashboard_loads"),
        ("unapproved_client_is_blocked", "unapproved_random_client_blocked"),
        ("key_creation_works", "create_api_key_works"),
        ("credential_is_returned_once_only", "credential_returned_once_in_create_response"),
        ("safe_preview_is_shown_later", "key_list_uses_safe_previews_only"),
        ("dashboard_state_is_credential_safe", "dashboard_state_contains_no_credential_value"),
        ("rotate_works", "rotate_returns_one_replacement"),
        ("old_rotated_key_is_blocked", "old_rotated_key_is_blocked"),
        ("revoke_and_revoked_blocking_work", "revoked_key_is_blocked"),
    ]:
        add(checks, audit_name, smoke_by_name.get(smoke_name, {}).get("passed") is True)

    docs_text = DOCS.read_text(encoding="utf-8") if DOCS.exists() else ""
    page_text = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
    key_route_text = KEY_ROUTE.read_text(encoding="utf-8") if KEY_ROUTE.exists() else ""
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8") for path in [PAGE, KEY_PANEL, QUICKSTART, KEY_ROUTE] if path.exists()
    )
    normalized_frontend_text = re.sub(r"\s+", " ", frontend_text)
    quickstart_lines = [
        "PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com",
        "PRMR_API_KEY=<YOUR_PRMR_KEY>",
        "PRMR_CLIENT_ID=<CLIENT_ID>",
        "PRMR_VAULT_ID=<VAULT_ID>",
        "PRMR_NAMESPACE=default",
    ]
    add(
        checks,
        "env_quickstart_exists",
        all(line in docs_text and line in frontend_text for line in quickstart_lines),
    )
    add(
        checks,
        "server_side_only_warning_exists",
        "Do not expose PRMR API keys in frontend or browser code. Use them server-side only." in docs_text
        and "Do not expose PRMR API keys in frontend or browser code. Use them server-side only."
        in normalized_frontend_text,
    )
    add(
        checks,
        "public_mode_remains_locked",
        "if (isPublicFrontendMode())" in page_text
        and "return <DashboardDisabled />" in page_text
        and 'getDeploymentMode() === "local"' in key_route_text,
    )
    add(checks, "public_reports_contain_no_credentials", not contains_credential(public_report))

    all_public_text = json.dumps(public_report, sort_keys=True) + "\n" + docs_text + "\n" + frontend_text
    add(checks, "no_open_public_signup_claim", "open public signup is available" not in all_public_text.lower())
    add(checks, "no_production_billing_claim", "production billing enabled" not in all_public_text.lower())
    add(checks, "no_certification_or_approval_claim", not claim_hits(all_public_text), claim_hits(all_public_text))

    typecheck = run_frontend("typecheck")
    add(checks, "frontend_typecheck_passes", typecheck["passed"], typecheck["tail"])
    build = run_frontend("build")
    add(checks, "frontend_build_passes", build["passed"], build["tail"])

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.88",
        "title": "API Client Dashboard + Key Creation MVP Audit",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "checks": checks,
        "runner_result": public_report["result"],
        "frontend": {
            "typecheck": {"passed": typecheck["passed"], "returncode": typecheck["returncode"]},
            "build": {"passed": build["passed"], "returncode": build["returncode"]},
        },
    }

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, {**private_report, "audit": audit})
    write_json(SMOKE_REPORT, {**smoke_report, "audit_result": result})
    scorecard = build_scorecard(public_report, smoke_checks)
    scorecard += (
        "\n## Independent audit\n\n"
        f"- Result: {result}\n"
        f"- Passed checks: {passed}/{total}\n"
        f"- Frontend typecheck: {'PASS' if typecheck['passed'] else 'FAIL'}\n"
        f"- Frontend build: {'PASS' if build['passed'] else 'FAIL'}\n"
    )
    SCORECARD.write_text(scorecard, encoding="utf-8")

    print("PRMR Memory Core V0.88 API Client Dashboard Audit")
    print(f"Runner result: {public_report['result']}")
    print(f"Frontend typecheck: {'PASS' if typecheck['passed'] else 'FAIL'}")
    print(f"Frontend build: {'PASS' if build['passed'] else 'FAIL'}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
