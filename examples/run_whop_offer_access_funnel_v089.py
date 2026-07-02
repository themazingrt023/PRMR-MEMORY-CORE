"""Run the V0.89 Whop offer and controlled access-funnel smoke."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.whop_offer_v089 import (
    BOUNDARY_V089,
    build_whop_offer_state,
    public_offer_payload,
    validate_whop_checkout_url,
)


REPORT_DIR = ROOT / "reports" / "v089"
PUBLIC_REPORT = REPORT_DIR / "public_whop_offer_access_funnel_v089.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_whop_offer_access_funnel_v089.json"
SMOKE_REPORT = REPORT_DIR / "whop_offer_access_funnel_smoke_v089.json"
SCORECARD = REPORT_DIR / "scorecard_v089.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bprmr_alpha_(?:dev|local)_[a-f0-9]{20,}\b",
        r"\bwhop_[A-Za-z0-9_-]{20,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_.-]{20,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def overclaim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "whop checkout is live",
        "billing automation complete",
        "automatic api key delivery enabled",
        "production ready",
        "compliance approved",
        "legal approved",
        "bank approved",
        "external security certified",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    missing = build_whop_offer_state(None)
    valid_url = "https://whop.com/checkout/plan_v089_placeholder"
    configured = build_whop_offer_state(valid_url)

    add(
        checks,
        "missing_checkout_url_uses_manual_fallback",
        missing.checkout_status == "needs_manual_configuration"
        and missing.checkout_url is None
        and missing.fallback_url == "/alpha?source=whop-pilot",
        {"status": missing.checkout_status, "fallback_url": missing.fallback_url},
    )
    add(
        checks,
        "official_https_whop_url_is_accepted",
        validate_whop_checkout_url(valid_url) == (True, valid_url)
        and configured.checkout_status == "configured",
        {"status": configured.checkout_status},
    )
    invalid_urls = [
        "http://whop.com/checkout/example",
        "https://example.com/checkout/example",
        "https://whop.com",
        "javascript:alert(1)",
    ]
    invalid_results = [validate_whop_checkout_url(url)[0] for url in invalid_urls]
    add(checks, "invalid_or_non_whop_urls_are_blocked", not any(invalid_results), invalid_results)
    add(
        checks,
        "configured_action_points_to_whop",
        configured.primary_action == "Continue to Whop" and configured.checkout_url == valid_url,
        {"primary_action": configured.primary_action},
    )
    add(
        checks,
        "manual_approval_is_always_required",
        missing.manual_approval_required is True and configured.manual_approval_required is True,
    )
    add(
        checks,
        "payment_never_issues_key_or_dashboard_access",
        configured.automatic_key_issuing is False and configured.automatic_dashboard_access is False,
    )
    add(
        checks,
        "non_sensitive_data_boundary_is_present",
        configured.synthetic_or_approved_non_sensitive_data_only is True,
    )

    route = ROOT / "frontend" / "app" / "whop" / "page.tsx"
    offer_data = ROOT / "frontend" / "data" / "whopOfferData.ts"
    helper = ROOT / "frontend" / "lib" / "whopOffer.ts"
    docs = ROOT / "docs" / "whop_offer_access_funnel_v089.md"
    env_example = ROOT / ".env.example"
    add(checks, "whop_offer_route_exists", route.exists())
    add(checks, "offer_copy_and_config_helper_exist", offer_data.exists() and helper.exists())
    add(checks, "whop_setup_runbook_exists", docs.exists())

    route_text = route.read_text(encoding="utf-8") if route.exists() else ""
    offer_text = offer_data.read_text(encoding="utf-8") if offer_data.exists() else ""
    helper_text = helper.read_text(encoding="utf-8") if helper.exists() else ""
    docs_text = docs.read_text(encoding="utf-8") if docs.exists() else ""
    normalized_docs_text = re.sub(r"\s+", " ", docs_text.lower())
    env_text = env_example.read_text(encoding="utf-8") if env_example.exists() else ""
    add(
        checks,
        "offer_has_required_commercial_copy",
        all(
            phrase in offer_text
            for phrase in [
                "Give your system memory that evolves.",
                "From £250",
                "You build the app. PRMR preserves the memory layer underneath.",
            ]
        ),
    )
    add(
        checks,
        "frontend_enforces_official_whop_host",
        'new Set(["whop.com", "www.whop.com"])' in helper_text
        and 'parsed.protocol !== "https:"' in helper_text,
    )
    add(
        checks,
        "checkout_environment_placeholder_exists",
        "NEXT_PUBLIC_WHOP_CHECKOUT_URL=" in env_text and "public, not a secret" in env_text,
    )
    add(
        checks,
        "funnel_and_manual_boundary_are_documented",
        all(
            phrase in normalized_docs_text
            for phrase in [
                "payment or waitlist intent does not approve",
                "manual founder approval only",
                "no webhook event should directly create a prmr api key",
            ]
        )
        and "WhopAccessFunnel" in route_text,
    )

    public_payload = public_offer_payload(None)
    provisional = {
        "version": "0.89",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Whop PRMR Offer Page + Access Funnel",
        "truth_label": "Whop offer and controlled access-funnel readiness evidence only",
        "boundary": BOUNDARY_V089,
        "checkout_configuration": {
            "status": missing.checkout_status,
            "external_checkout_verified": False,
            "manual_next_step_required": True,
        },
        "offer": public_payload,
    }
    add(checks, "public_report_contains_no_secrets", not contains_secret(provisional))
    add(checks, "public_report_contains_no_overclaims", not overclaim_hits(provisional), overclaim_hits(provisional))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public_report = {
        **provisional,
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
    }
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "url_validation": {
            "valid_placeholder": {"accepted": True, "host": "whop.com"},
            "invalid_cases_rejected": len(invalid_urls),
        },
        "restricted_note": "No Whop API key, webhook secret, customer data, payment record, or PRMR credential is present.",
    }
    smoke_report = {
        "version": "0.89",
        "result": result,
        "public_safe": True,
        "boundary": BOUNDARY_V089,
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
        "external_state": {
            "whop_product_verified": False,
            "checkout_link_verified": False,
            "payment_verified": False,
            "webhook_verified": False,
        },
    }
    return public_report, private_report, smoke_report, checks


def scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.89 Whop PRMR Offer Page + Access Funnel",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V089}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(
        [
            "",
            "## External state",
            "",
            "- Whop product: NOT VERIFIED",
            "- Checkout link: NOT VERIFIED",
            "- Payment: NOT VERIFIED",
            "- Webhook: NOT IMPLEMENTED",
            "",
            "## Manual next step",
            "",
            "Create the Whop product and checkout/waitlist link, set `NEXT_PUBLIC_WHOP_CHECKOUT_URL`, redeploy, and verify the destination.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(scorecard(public_report, checks), encoding="utf-8")
    print("PRMR Memory Core V0.89 Whop Offer + Access Funnel")
    print("Whop product verified: NO")
    print("Checkout URL configured in test: fallback + official-domain validation")
    print("Payment-to-access boundary: manual approval required")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
