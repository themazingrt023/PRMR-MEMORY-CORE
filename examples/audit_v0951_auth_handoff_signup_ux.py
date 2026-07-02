"""Audit V0.95.1 auth handoff, customer copy, navigation, and build evidence."""

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

from examples.run_auth_handoff_signup_ux_v0951 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret,
    run_smoke,
    write_json,
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def command_passes(command: list[str], cwd: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return completed.returncode == 0, output[-1200:]


def has_unqualified_claim(text: str) -> bool:
    pattern = re.compile(
        r"\b(?:production[- ]ready|production auth(?:entication)? complete|"
        r"compliance approved|security certified|stripe billing connected)\b",
        re.IGNORECASE,
    )
    for paragraph in re.split(r"\n\s*\n", text):
        if pattern.search(paragraph) and not re.search(
            r"\b(?:not|no|does not|is not|without|unfinished|future|pending)\b",
            paragraph,
            re.IGNORECASE,
        ):
            return True
    return False


def main() -> int:
    checks: list[dict[str, Any]] = []
    v095 = ROOT / "reports" / "v095" / "public_supabase_auth_real_email_v095.json"
    callback = ROOT / "frontend" / "app" / "auth" / "callback" / "route.ts"
    signup = ROOT / "frontend" / "components" / "self-serve" / "SignupForm.tsx"
    login = ROOT / "frontend" / "components" / "self-serve" / "LoginForm.tsx"
    start = ROOT / "frontend" / "components" / "self-serve" / "StartFlow.tsx"
    navigation = ROOT / "frontend" / "components" / "landing" / "Navigation.tsx"
    docs = ROOT / "docs" / "supabase_auth_real_email_v095.md"

    add(checks, "v095_evidence_exists", v095.exists())
    public, private, smoke, runner_checks = run_smoke()
    by_name = {item["name"]: item["passed"] for item in runner_checks}
    for audit_name, runner_name in [
        ("auth_callback_handles_session", "callback_exchanges_code_and_checks_session"),
        ("auth_callback_has_verified_fallback", "callback_has_start_verified_and_failure_routes"),
        ("auth_cookie_headers_are_preserved", "callback_carries_cookies_and_no_cache_headers"),
        ("signup_copy_is_professional", "signup_copy_is_professional"),
        ("login_copy_is_professional", "login_copy_is_professional"),
        ("start_copy_is_professional", "start_copy_is_professional"),
        ("public_auth_copy_hides_provider", "public_auth_copy_hides_provider_name"),
        ("auth_pages_are_visually_clean", "auth_pages_use_clean_background"),
        ("navigation_is_updated", "primary_navigation_is_product_focused"),
        ("api_key_gate_is_preserved", "api_key_creation_requires_verified_identity"),
        ("runner_public_report_is_safe", "public_report_has_no_secrets"),
    ]:
        add(checks, audit_name, by_name.get(runner_name) is True)

    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.suffix in {".ts", ".tsx", ".js", ".mjs", ".json"}
    )
    add(
        checks,
        "service_role_key_not_used_in_frontend",
        "SUPABASE_SERVICE_ROLE" not in frontend_text
        and "sb_secret_" not in frontend_text
        and "service_role_key" not in frontend_text.lower(),
    )
    docs_text = docs.read_text(encoding="utf-8")
    add(
        checks,
        "production_and_preview_redirects_documented",
        "https://prmr-memory-core.vercel.app/auth/callback" in docs_text
        and "https://<preview-domain>/auth/callback" in docs_text,
    )
    add(
        checks,
        "public_reports_are_secret_safe",
        not contains_secret(public) and not contains_secret(smoke),
    )
    combined_public = "\n".join(
        [
            signup.read_text(encoding="utf-8"),
            login.read_text(encoding="utf-8"),
            start.read_text(encoding="utf-8"),
            navigation.read_text(encoding="utf-8"),
            json.dumps(public, sort_keys=True),
        ]
    )
    add(
        checks,
        "no_fake_billing_or_certification_claim",
        public["stripe_billing"] == "NOT_CONNECTED"
        and public["production_auth_hardening"] == "NOT_COMPLETE"
        and not has_unqualified_claim(combined_public),
    )

    npm = "npm.cmd" if os.name == "nt" else "npm"
    typecheck_ok, typecheck_output = command_passes([npm, "run", "typecheck"], ROOT / "frontend")
    add(checks, "frontend_typecheck_passes", typecheck_ok, typecheck_output)
    build_ok, build_output = command_passes([npm, "run", "build"], ROOT / "frontend")
    add(checks, "frontend_build_passes", build_ok, build_output)

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    audit = {
        "version": "0.95.1",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "runner_result": public["result"],
        "live_v095_bridge": public["live_backend"]["v095_bridge_live"],
        "public_safe": True,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "truth_label": (
            "Auth handoff and professional public UX audit. A PASS does not "
            "claim the V0.95 bridge is live when Render health reports otherwise."
        ),
    }
    write_json(PUBLIC_REPORT, {**public, "audit": audit})
    write_json(PRIVATE_REPORT, {**private, "audit": {**audit, "checks": checks}})
    write_json(SMOKE_REPORT, {**smoke, "audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Runner result: {public['result']}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.95.1 Auth Handoff + Signup UX Audit")
    print(f"Runner result: {public['result']}")
    print(f"Live Render auth bridge: {public['live_backend']['v095_bridge_live']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for item in checks:
            if not item["passed"]:
                print(f"FAIL: {item['name']}")
                if item.get("detail"):
                    print(str(item["detail"])[-800:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
