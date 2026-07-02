"""Audit V0.90 Whop event verification and manual approval boundaries."""

from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_whop_manual_approval_v090 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret_or_pii,
    run_smoke,
    write_json,
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    v089 = ROOT / "reports" / "v089" / "public_whop_offer_access_funnel_v089.json"
    module = ROOT / "prmr" / "product" / "whop_manual_approval_v090.py"
    entrypoint = ROOT / "prmr" / "product" / "api_server_v090.py"
    docs = ROOT / "docs" / "whop_manual_approval_workflow_v090.md"
    requirements = (ROOT / "requirements-api.txt").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    add(checks, "v089_offer_evidence_exists", v089.exists())
    add(checks, "workflow_module_and_entrypoint_exist", module.exists() and entrypoint.exists())
    add(checks, "workflow_docs_exist", docs.exists())
    try:
        verifier_version = importlib.metadata.version("standardwebhooks")
    except importlib.metadata.PackageNotFoundError:
        verifier_version = ""
    add(
        checks,
        "standard_webhooks_verifier_is_pinned_and_installed",
        "standardwebhooks==1.0.1" in requirements and verifier_version == "1.0.1",
        {"installed_version": verifier_version},
    )
    add(
        checks,
        "server_only_environment_placeholders_exist",
        all(
            key in env_example
            for key in [
                "WHOP_WEBHOOK_SECRET=",
                "WHOP_EXPECTED_COMPANY_ID=",
                "WHOP_EXPECTED_PRODUCT_ID=",
            ]
        )
        and "NEXT_PUBLIC_WHOP_WEBHOOK" not in env_example,
    )

    public_report, private_report, smoke_report, runner_checks = run_smoke()
    runner_by_name = {check["name"]: check["passed"] for check in runner_checks}
    for audit_name, runner_name in [
        ("missing_secret_fails_closed", "missing_webhook_secret_fails_closed"),
        ("invalid_signature_rejected", "invalid_signature_is_rejected"),
        ("failed_auth_does_not_mutate_state", "failed_verification_does_not_create_record"),
        ("company_product_scope_enforced", "wrong_product_scope_is_rejected"),
        ("valid_payment_is_pending_review", "valid_signed_payment_creates_pending_review"),
        ("delivery_is_idempotent", "duplicate_delivery_is_idempotent"),
        ("approval_is_manual_handoff_only", "operator_approval_creates_manual_handoff_only"),
        ("rejection_grants_no_access", "operator_rejection_grants_no_access"),
        ("adverse_events_require_review", "refund_or_adverse_event_requires_review"),
        ("raw_pii_and_payment_details_not_stored", "stored_records_exclude_raw_pii_and_payment_method"),
        ("sqlite_idempotency_store_present", "sqlite_idempotency_store_exists"),
        ("fastapi_route_verified", "fastapi_webhook_route_accepts_verified_event"),
    ]:
        add(checks, audit_name, runner_by_name.get(runner_name) is True)

    docs_text = re.sub(r"\s+", " ", docs.read_text(encoding="utf-8").lower())
    add(
        checks,
        "deployment_boundary_and_manual_steps_documented",
        all(
            phrase in docs_text
            for phrase in [
                "do not change the live render start command until",
                "does not start onboarding automatically",
                "a whop event can never create a prmr api key",
            ]
        ),
    )
    add(checks, "public_report_contains_no_secret_or_pii", not contains_secret_or_pii(public_report))
    add(
        checks,
        "external_state_remains_unverified",
        smoke_report["external_state"]
        == {
            "live_whop_product": False,
            "live_webhook_delivery": False,
            "real_payment": False,
            "hosted_v090_entrypoint": False,
        },
    )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.90",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "checks": checks,
        "runner_result": public_report["result"],
    }
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, {**private_report, "audit": audit})
    write_json(SMOKE_REPORT, {**smoke_report, "audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public_report, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.90 Whop Manual Approval Audit")
    print(f"Runner result: {public_report['result']}")
    print(f"Verifier: standardwebhooks {verifier_version or 'MISSING'}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
