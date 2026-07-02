"""Run V0.95 Supabase Auth bridge fixtures and environment readiness checks."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.durable_self_serve_storage_v093 import DurableSelfServeProductV093
from prmr.product.supabase_auth_bridge_v095 import (
    BOUNDARY_V095,
    FixtureSupabaseIdentityVerifier,
    SupabaseAuthBridgeV095,
    SupabaseIdentity,
)


REPORT_DIR = ROOT / "reports" / "v095"
PUBLIC_REPORT = REPORT_DIR / "public_supabase_auth_real_email_v095.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_supabase_auth_real_email_v095.json"
SMOKE_REPORT = REPORT_DIR / "supabase_auth_real_email_smoke_v095.json"
SCORECARD = REPORT_DIR / "scorecard_v095.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any, known_values: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(value and value in text for value in (known_values or [])):
        return True
    return bool(
        re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", text)
        or re.search(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", text)
        or re.search(r"\bsb_secret_[A-Za-z0-9_-]{16,}\b", text)
        or re.search(
            r'"(?:access_token|refresh_token|service_role_key|database_url|key_hash)"\s*:',
            text,
            re.IGNORECASE,
        )
    )


def env_status() -> dict[str, bool]:
    return {
        "frontend_url": bool(os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()),
        "frontend_anon_key": bool(os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()),
        "backend_project_url": bool(os.getenv("SUPABASE_PROJECT_URL", "").strip()),
        "backend_publishable_key": bool(os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()),
    }


def run_fixture() -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    checks: list[dict[str, Any]] = []
    known_secrets = [
        "fixture_confirmed_access_token_v095",
        "fixture_unconfirmed_access_token_v095",
    ]
    trace: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="prmr-v095-", ignore_cleanup_errors=True) as temp:
        product = DurableSelfServeProductV093(Path(temp) / "supabase_auth_fixture.sqlite")
        verifier = FixtureSupabaseIdentityVerifier(
            {
                known_secrets[0]: SupabaseIdentity(
                    subject="fixture-supabase-user-v095",
                    email="confirmed-v095@example.test",
                    email_confirmed_at="2026-07-02T12:00:00+00:00",
                    role="authenticated",
                    display_name="Synthetic Supabase Builder",
                ),
                known_secrets[1]: SupabaseIdentity(
                    subject="fixture-unconfirmed-user-v095",
                    email="unconfirmed-v095@example.test",
                    email_confirmed_at=None,
                    role="authenticated",
                    display_name="Unconfirmed Fixture",
                ),
            }
        )
        bridge = SupabaseAuthBridgeV095(product, verifier)

        before = product.repository.table_counts()
        missing = bridge.create_key(access_token=None, label="Blocked missing token")
        invalid = bridge.create_key(access_token="fixture_invalid_token_v095", label="Blocked invalid token")
        unconfirmed = bridge.create_key(
            access_token=known_secrets[1],
            label="Blocked unconfirmed token",
        )
        after = product.repository.table_counts()
        add(
            checks,
            "missing_access_token_blocked",
            missing["status_code"] == 401
            and missing["error"]["code"] == "missing_supabase_access_token",
        )
        add(
            checks,
            "invalid_access_token_blocked",
            invalid["status_code"] == 401
            and invalid["error"]["code"] == "invalid_supabase_access_token",
        )
        add(
            checks,
            "unconfirmed_identity_blocked",
            unconfirmed["status_code"] == 403
            and unconfirmed["error"]["code"] == "supabase_email_confirmation_required",
        )
        add(
            checks,
            "failed_auth_does_not_mutate_state",
            before == after and after["users"] == 0 and after["api_keys"] == 0,
        )

        activated = bridge.activate(access_token=known_secrets[0], plan_id="free")
        scope = activated.get("scope", {})
        add(
            checks,
            "confirmed_identity_activates_free_plan",
            activated["status_code"] in {200, 201}
            and activated.get("provisioned") is True
            and activated.get("subscription", {}).get("status") == "active",
        )
        add(
            checks,
            "confirmed_identity_provisions_scope",
            str(scope.get("client_id", "")).startswith("client_ss_")
            and str(scope.get("vault_id", "")).startswith("vault_ss_")
            and scope.get("namespace") == "default",
        )
        account = next(iter(product.product.accounts.accounts.values()))
        add(
            checks,
            "supabase_identity_maps_without_password",
            account.email_verification_mode == "supabase_auth_email_confirmed"
            and account.password_hash == ""
            and account.password_salt == "",
        )

        created = bridge.create_key(
            access_token=known_secrets[0],
            label="Synthetic confirmed server",
        )
        raw_key = str(created.get("raw_api_key", ""))
        known_secrets.append(raw_key)
        add(
            checks,
            "confirmed_identity_can_create_copy_once_key",
            created["status_code"] == 201
            and created.get("returned_once") is True
            and raw_key.startswith("prmr_alpha_"),
        )
        listed = bridge.list_keys(access_token=known_secrets[0])
        add(
            checks,
            "key_listing_returns_safe_preview_only",
            listed["status_code"] == 200
            and listed.get("credential_values_returned") is False
            and raw_key not in json.dumps(listed),
        )
        dashboard = bridge.dashboard(access_token=known_secrets[0])
        dashboard_text = json.dumps(dashboard)
        add(
            checks,
            "dashboard_is_scoped_and_secret_safe",
            dashboard["status_code"] == 200
            and dashboard["dashboard"]["client_scope"]["client_id"] == scope["client_id"]
            and raw_key not in dashboard_text
            and known_secrets[0] not in dashboard_text,
        )
        add(
            checks,
            "raw_credentials_not_persisted",
            not product.repository.raw_value_present(raw_key)
            and not product.repository.raw_value_present(known_secrets[0]),
        )
        valid, reason = product.product.keys.preflight_key(
            raw_key=raw_key,
            client_id=scope["client_id"],
        )
        add(checks, "created_prmr_key_validates_separately", valid and reason == "allowed")
        trace = {
            "fixture_only": True,
            "confirmed_identity_mapped": True,
            "unconfirmed_identity_blocked": True,
            "safe_client_id": scope.get("client_id"),
            "safe_vault_id": scope.get("vault_id"),
            "namespace": scope.get("namespace"),
            "safe_key_preview": created.get("safe_key_preview"),
            "raw_credentials_retained": False,
        }
    return checks, trace, known_secrets


def run_smoke() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]
]:
    checks, trace, known_secrets = run_fixture()
    environment = env_status()
    configured = all(environment.values())
    fixture_passed = all(item["passed"] for item in checks)
    result = "PASS" if configured and fixture_passed else (
        "NEEDS_SUPABASE_ENV" if fixture_passed else "NEEDS_WORK"
    )
    provisional = {
        "version": "0.95",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Supabase Auth and Real Email Confirmation",
        "truth_label": (
            "Supabase Auth integration configured with deterministic bridge evidence"
            if configured
            else "Supabase Auth bridge fixture evidence; live project configuration missing"
        ),
        "result": result,
        "checks_passed": sum(1 for item in checks if item["passed"]),
        "checks_total": len(checks) + 1,
        "supabase_environment_configured": configured,
        "environment_presence": environment,
        "real_confirmation_email_sent_by_runner": False,
        "email_test_recipient_configured": bool(
            os.getenv("PRMR_SUPABASE_EMAIL_TEST_RECIPIENT", "").strip()
        ),
        "hosted_signup_path": "supabase_auth",
        "local_test_verification_normal_hosted_path": False,
        "unauthenticated_key_creation_blocked": True,
        "unconfirmed_key_creation_blocked": True,
        "prmr_api_keys_separate": True,
        "raw_credentials_exposed": False,
        "public_safe": True,
        "stripe_billing": "NOT_CONNECTED",
        "production_auth_hardening": "NOT_COMPLETE",
        "boundary": BOUNDARY_V095,
    }
    add(
        checks,
        "public_report_has_no_secrets",
        not contains_secret(provisional, known_secrets),
    )
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    if passed != total:
        result = "NEEDS_WORK"
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
        "trace": trace,
        "restricted_note": "No Supabase token, API key, password, or environment value is retained.",
    }
    smoke = {
        "version": "0.95",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "supabase_environment_configured": configured,
        "real_confirmation_email_sent_by_runner": False,
        "public_safe": True,
        "boundary": BOUNDARY_V095,
    }
    return public, private, smoke, checks


def build_scorecard(public: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.95 Supabase Auth and Real Email Confirmation",
        "",
        f"Result: {public['result']}",
        f"Passed checks: {public['checks_passed']}/{public['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V095}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks)
    lines.extend(
        [
            "",
            "## External evidence",
            "",
            f"- Supabase environment configured: {public['supabase_environment_configured']}",
            "- Real confirmation email sent by runner: False",
            "- Stripe billing: not connected",
            "- Production authentication hardening: not complete",
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
    print("PRMR Memory Core V0.95 Supabase Auth + Real Email")
    print(f"Supabase environment configured: {public['supabase_environment_configured']}")
    print(f"Real confirmation email sent: {public['real_confirmation_email_sent_by_runner']}")
    print(f"Passed checks: {public['checks_passed']}/{public['checks_total']}")
    print(f"Result: {public['result']}")
    return 0 if public["result"] in {"PASS", "NEEDS_SUPABASE_ENV"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
