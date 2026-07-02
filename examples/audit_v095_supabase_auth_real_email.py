"""Audit V0.95 Supabase Auth integration, gates, and public claim boundaries."""

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

from examples.run_supabase_auth_real_email_v095 import (
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
        r"compliance approved|security certified|externally validated|"
        r"stripe billing connected|enterprise sso ready)\b",
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
    paths = {
        "v094": ROOT / "reports" / "v094" / "public_hosted_self_serve_key_activation_v094.json",
        "client": ROOT / "frontend" / "lib" / "supabaseClient.ts",
        "server": ROOT / "frontend" / "lib" / "supabaseServer.ts",
        "signup": ROOT / "frontend" / "components" / "self-serve" / "SignupForm.tsx",
        "login": ROOT / "frontend" / "components" / "self-serve" / "LoginForm.tsx",
        "callback": ROOT / "frontend" / "app" / "auth" / "callback" / "route.ts",
        "verify": ROOT / "frontend" / "app" / "verify-email" / "page.tsx",
        "verify_panel": ROOT / "frontend" / "components" / "self-serve" / "VerifyEmailPanel.tsx",
        "activate_proxy": ROOT / "frontend" / "app" / "api" / "self-serve" / "activate" / "route.ts",
        "bridge": ROOT / "prmr" / "product" / "supabase_auth_bridge_v095.py",
        "api": ROOT / "prmr" / "product" / "api_server_v094.py",
        "docs": ROOT / "docs" / "supabase_auth_real_email_v095.md",
        "env": ROOT / ".env.example",
    }
    sources = {
        name: path.read_text(encoding="utf-8")
        for name, path in paths.items()
        if path.exists() and path.is_file()
    }
    docs_normalized = " ".join(sources.get("docs", "").split())
    frontend_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.suffix in {".ts", ".tsx", ".js", ".mjs", ".json"}
    )

    add(checks, "v094_hosted_evidence_exists", paths["v094"].exists())
    add(checks, "supabase_browser_client_exists", paths["client"].exists())
    add(checks, "supabase_server_client_exists", paths["server"].exists())
    add(
        checks,
        "signup_uses_supabase_auth",
        "auth.signUp" in sources.get("signup", "")
        and "emailRedirectTo" in sources.get("signup", "")
        and "/api/self-serve/activate" not in sources.get("signup", ""),
    )
    add(
        checks,
        "login_uses_supabase_auth",
        "auth.signInWithPassword" in sources.get("login", "")
        and "email_confirmed_at" in sources.get("login", ""),
    )
    add(
        checks,
        "confirmation_callback_and_verify_page_exist",
        paths["callback"].exists()
        and paths["verify"].exists()
        and "exchangeCodeForSession" in sources.get("callback", "")
        and "auth.resend" in sources.get("verify_panel", ""),
    )
    add(
        checks,
        "local_test_verification_removed_from_hosted_frontend",
        "/v1/self-serve/verify" not in frontend_sources
        and "Verify in local MVP" not in frontend_sources
        and "local/test verification" not in sources.get("signup", ""),
    )
    add(
        checks,
        "backend_supabase_bridge_exists",
        paths["bridge"].exists()
        and "SupabaseRemoteIdentityVerifier" in sources.get("bridge", "")
        and "/auth/v1/user" in sources.get("bridge", ""),
    )
    add(
        checks,
        "backend_requires_confirmed_authenticated_identity",
        "email_confirmed_at" in sources.get("bridge", "")
        and 'role == "authenticated"' in sources.get("bridge", "")
        and "supabase_email_confirmation_required" in sources.get("bridge", ""),
    )
    add(
        checks,
        "hosted_local_auth_routes_are_disabled_in_supabase_mode",
        "local_mvp_auth_disabled" in sources.get("api", "")
        and "PRMR_AUTH_BACKEND" in sources.get("api", ""),
    )
    add(
        checks,
        "frontend_does_not_expose_service_role",
        "SUPABASE_SERVICE_ROLE" not in frontend_sources
        and "sb_secret_" not in frontend_sources
        and "service_role_key" not in frontend_sources.lower(),
    )
    add(
        checks,
        "required_environment_placeholders_exist",
        all(
            name in sources.get("env", "")
            for name in [
                "NEXT_PUBLIC_SUPABASE_URL",
                "NEXT_PUBLIC_SUPABASE_ANON_KEY",
                "SUPABASE_PROJECT_URL",
                "SUPABASE_PUBLISHABLE_KEY",
                "PRMR_AUTH_BACKEND",
            ]
        ),
    )
    add(
        checks,
        "docs_cover_redirects_mapping_and_boundaries",
        all(
            phrase in docs_normalized
            for phrase in [
                "https://prmr-memory-core.vercel.app/auth/callback",
                "email confirmations",
                "PRMR_AUTH_BACKEND=supabase",
                "PRMR does not store the Supabase password",
                "Stripe billing",
                "custom SMTP",
            ]
        ),
    )

    public, private, smoke, runner_checks = run_smoke()
    by_name = {item["name"]: item["passed"] for item in runner_checks}
    add(
        checks,
        "unauthenticated_key_creation_blocked",
        by_name.get("missing_access_token_blocked") is True
        and by_name.get("invalid_access_token_blocked") is True,
    )
    add(
        checks,
        "unconfirmed_key_creation_blocked",
        by_name.get("unconfirmed_identity_blocked") is True,
    )
    add(
        checks,
        "confirmed_fixture_provisions_and_creates_key",
        by_name.get("confirmed_identity_activates_free_plan") is True
        and by_name.get("confirmed_identity_provisions_scope") is True
        and by_name.get("confirmed_identity_can_create_copy_once_key") is True,
    )
    add(
        checks,
        "fixture_public_outputs_are_secret_safe",
        by_name.get("key_listing_returns_safe_preview_only") is True
        and by_name.get("dashboard_is_scoped_and_secret_safe") is True
        and by_name.get("raw_credentials_not_persisted") is True,
    )
    add(
        checks,
        "public_reports_contain_no_supabase_secrets",
        not contains_secret(public) and not contains_secret(smoke),
    )
    add(
        checks,
        "no_fake_email_or_billing_claim",
        public["real_confirmation_email_sent_by_runner"] is False
        and public["stripe_billing"] == "NOT_CONNECTED"
        and not has_unqualified_claim(
            sources.get("docs", "") + "\n" + json.dumps(public, sort_keys=True)
        ),
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
        "version": "0.95",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "integration_runner_result": public["result"],
        "supabase_environment_configured": public["supabase_environment_configured"],
        "real_confirmation_email_sent": False,
        "public_safe": True,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "truth_label": (
            "Supabase Auth integration and deterministic verified-identity gate audit. "
            "A PASS does not prove live email delivery when environment values are absent."
        ),
    }
    write_json(PUBLIC_REPORT, {**public, "audit": audit})
    write_json(
        PRIVATE_REPORT,
        {**private, "audit": {**audit, "checks": checks}},
    )
    write_json(SMOKE_REPORT, {**smoke, "audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Integration runner: {public['result']}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.95 Supabase Auth Audit")
    print(f"Integration runner: {public['result']}")
    print(f"Supabase environment configured: {public['supabase_environment_configured']}")
    print("Real confirmation email sent: False")
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
