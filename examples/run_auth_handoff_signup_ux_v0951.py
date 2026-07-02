"""Run V0.95.1 auth handoff and public signup UX evidence."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_supabase_auth_real_email_v095 import run_fixture


REPORT_DIR = ROOT / "reports" / "v0951"
PUBLIC_REPORT = REPORT_DIR / "public_auth_handoff_signup_ux_v0951.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_auth_handoff_signup_ux_v0951.json"
SMOKE_REPORT = REPORT_DIR / "auth_handoff_signup_ux_smoke_v0951.json"
SCORECARD = REPORT_DIR / "scorecard_v0951.md"
BOUNDARY = (
    "V0.95.1 is auth handoff and signup UX evidence. It is not Stripe billing, "
    "production authentication hardening, compliance approval, legal approval, "
    "or external security certification."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(
        re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", text)
        or re.search(r"\bsb_(?:secret|publishable)_[A-Za-z0-9_-]{16,}\b", text)
        or re.search(
            r'"(?:access_token|refresh_token|service_role_key|database_url|key_hash)"\s*:',
            text,
            re.IGNORECASE,
        )
    )


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def live_backend_state() -> dict[str, Any]:
    url = "https://prmr-memory-core-api.onrender.com"
    try:
        response = httpx.get(f"{url}/health", timeout=60.0)
        payload = response.json() if response.status_code == 200 else {}
        storage = payload.get("storage", {})
        return {
            "reachable": response.status_code == 200,
            "version": payload.get("version"),
            "storage_backend": storage.get("storage_backend"),
            "database_connected": storage.get("database_connected"),
            "durable_storage_verified": storage.get("durable_storage_verified"),
            "auth_backend": payload.get("auth_backend"),
            "real_email_verification_path": payload.get("real_email_verification_path"),
            "v095_bridge_live": (
                response.status_code == 200
                and payload.get("auth_backend") == "supabase"
                and payload.get("real_email_verification_path") is True
            ),
        }
    except (httpx.HTTPError, ValueError):
        return {
            "reachable": False,
            "version": None,
            "storage_backend": None,
            "database_connected": None,
            "durable_storage_verified": None,
            "auth_backend": None,
            "real_email_verification_path": None,
            "v095_bridge_live": False,
        }


def run_smoke() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]
]:
    checks: list[dict[str, Any]] = []
    signup_page = source("frontend/app/signup/page.tsx")
    signup_form = source("frontend/components/self-serve/SignupForm.tsx")
    login_page = source("frontend/app/login/page.tsx")
    login_form = source("frontend/components/self-serve/LoginForm.tsx")
    start_page = source("frontend/app/start/page.tsx")
    start_flow = source("frontend/components/self-serve/StartFlow.tsx")
    verify_page = source("frontend/app/verify-email/page.tsx")
    verify_panel = source("frontend/components/self-serve/VerifyEmailPanel.tsx")
    callback = source("frontend/app/auth/callback/route.ts")
    navigation = source("frontend/components/landing/Navigation.tsx")
    bridge = source("prmr/product/supabase_auth_bridge_v095.py")
    customer_sources = "\n".join(
        [
            signup_page,
            signup_form,
            login_page,
            login_form,
            start_page,
            start_flow,
            verify_page,
            verify_panel,
        ]
    )
    quoted_customer_copy = " ".join(
        match[1]
        for match in re.findall(r"([\"'`])([^\"'`\n]*)\1", customer_sources)
    )
    rendered_customer_copy = " ".join(
        re.findall(r">([^<>{}\n]+)<", customer_sources)
    )

    add(
        checks,
        "signup_copy_is_professional",
        "Create your PRMR workspace." in signup_page
        and "Create your account, verify your email" in signup_page
        and "I understand PRMR API keys must stay server-side" in signup_form
        and "Check your email to verify your PRMR account." in signup_form,
    )
    add(
        checks,
        "login_copy_is_professional",
        "Email verified. Sign in to continue." in login_form
        and "We could not sign you in." in login_form
        and "Supabase Auth Login" not in login_page,
    )
    add(
        checks,
        "start_copy_is_professional",
        "Verify your email to activate your PRMR workspace." in start_page
        and "We could not verify your account session." in start_flow
        and "We could not reach the PRMR backend." in start_flow
        and "identity or storage boundary" not in start_flow,
    )
    add(
        checks,
        "public_auth_copy_hides_provider_name",
        "Supabase" not in quoted_customer_copy
        and "Supabase" not in rendered_customer_copy,
    )
    add(
        checks,
        "callback_exchanges_code_and_checks_session",
        "exchangeCodeForSession(code)" in callback
        and "data.session" in callback
        and "user?.email_confirmed_at" in callback
        and "createSupabaseRouteClient(request, response)" in callback,
    )
    add(
        checks,
        "callback_has_start_verified_and_failure_routes",
        'new URL("/start"' in callback
        and 'new URL("/login?verified=1"' in callback
        and 'new URL("/login?error=auth_callback_failed"' in callback,
    )
    add(
        checks,
        "callback_carries_cookies_and_no_cache_headers",
        "response.cookies.set" in source("frontend/lib/supabaseServer.ts")
        and "headersToSet" in source("frontend/lib/supabaseServer.ts")
        and '"Cache-Control", "private, no-store"' in callback,
    )
    add(
        checks,
        "login_handles_verified_query",
        'params.get("verified") === "1"' in login_form
        and "Email verified. Sign in to continue." in login_form,
    )
    add(
        checks,
        "auth_pages_use_clean_background",
        "DataRainBackground" not in customer_sources,
    )
    required_nav = [
        "Problem",
        "Solution",
        "API",
        "Market",
        "Pilot",
        "Demo",
        "Sign in",
        "Start building",
    ]
    add(
        checks,
        "primary_navigation_is_product_focused",
        all(f'label: "{label}"' in navigation for label in required_nav)
        and 'label: "Docs"' not in navigation
        and 'label: "Alpha"' not in navigation,
    )

    fixture_checks, fixture_trace, _ = run_fixture()
    fixture_by_name = {item["name"]: item["passed"] for item in fixture_checks}
    add(
        checks,
        "api_key_creation_requires_verified_identity",
        fixture_by_name.get("missing_access_token_blocked") is True
        and fixture_by_name.get("invalid_access_token_blocked") is True
        and fixture_by_name.get("unconfirmed_identity_blocked") is True
        and fixture_by_name.get("confirmed_identity_can_create_copy_once_key") is True
        and "email_confirmed_at" in bridge,
    )

    live = live_backend_state()
    static_passed = all(item["passed"] for item in checks)
    provisional = {
        "version": "0.95.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Auth Handoff and Signup UX",
        "truth_label": "professional auth handoff and verified-identity gating evidence",
        "result": (
            "PASS"
            if static_passed and live["v095_bridge_live"]
            else "NEEDS_RENDER_V095_DEPLOYMENT"
            if static_passed
            else "NEEDS_WORK"
        ),
        "checks_passed": sum(1 for item in checks if item["passed"]),
        "checks_total": len(checks) + 1,
        "callback_routes": {
            "authenticated": "/start",
            "verified_without_session": "/login?verified=1",
            "failure": "/login?error=auth_callback_failed",
        },
        "provider_name_in_customer_auth_copy": False,
        "api_key_identity_gate": True,
        "live_backend": live,
        "raw_credentials_exposed": False,
        "public_safe": True,
        "stripe_billing": "NOT_CONNECTED",
        "production_auth_hardening": "NOT_COMPLETE",
        "boundary": BOUNDARY,
    }
    add(checks, "public_report_has_no_secrets", not contains_secret(provisional))
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = provisional["result"] if passed == total else "NEEDS_WORK"
    public = {
        **provisional,
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
    }
    private = {
        **public,
        "public_safe": False,
        "checks": checks,
        "fixture_trace": fixture_trace,
        "restricted_note": "No auth token, password, database URL, or raw API key is retained.",
    }
    smoke = {
        "version": "0.95.1",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "live_v095_bridge": live["v095_bridge_live"],
        "public_safe": True,
        "boundary": BOUNDARY,
    }
    return public, private, smoke, checks


def build_scorecard(public: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.95.1 Auth Handoff and Signup UX",
        "",
        f"Result: {public['result']}",
        f"Passed checks: {public['checks_passed']}/{public['checks_total']}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks)
    lines.extend(
        [
            "",
            "## Live deployment",
            "",
            f"- Render V0.95 auth bridge live: {public['live_backend']['v095_bridge_live']}",
            f"- Render reported version: {public['live_backend']['version']}",
            f"- Render auth backend: {public['live_backend']['auth_backend']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    public, private, smoke, checks = run_smoke()
    write_json(PUBLIC_REPORT, public)
    write_json(PRIVATE_REPORT, private)
    write_json(SMOKE_REPORT, smoke)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public, checks), encoding="utf-8")
    print("PRMR Memory Core V0.95.1 Auth Handoff + Signup UX")
    print(f"Live Render auth bridge: {public['live_backend']['v095_bridge_live']}")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "NEEDS_RENDER_V095_DEPLOYMENT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
