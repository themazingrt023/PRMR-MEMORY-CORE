"""Audit the generic V0.92 self-serve API product MVP."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_self_serve_api_product_v092 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_secret,
    run_smoke,
    write_json,
)
from prmr.product.self_serve_dashboard_v092 import SelfServeDashboardV092


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run_frontend(command: str) -> tuple[bool, str]:
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        return False, "npm executable not found"
    completed = subprocess.run(
        [executable, "run", command],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    return completed.returncode == 0, output[-1200:]


def has_unqualified_claim(text: str) -> bool:
    claim = re.compile(
        r"\b(?:production[- ]ready|production certified|security certified|compliance certified|bank approved|guaranteed scale)\b",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if claim.search(line) and not re.search(r"\b(?:not|no|does not|is not|without)\b", line, re.IGNORECASE):
            return True
    return False


def main() -> int:
    checks: list[dict[str, Any]] = []
    required_files = [
        ROOT / "prmr" / "product" / "self_serve_accounts_v092.py",
        ROOT / "prmr" / "product" / "self_serve_plans_v092.py",
        ROOT / "prmr" / "product" / "self_serve_api_keys_v092.py",
        ROOT / "prmr" / "product" / "self_serve_dashboard_v092.py",
        ROOT / "frontend" / "app" / "signup" / "page.tsx",
        ROOT / "frontend" / "app" / "login" / "page.tsx",
        ROOT / "frontend" / "app" / "start" / "page.tsx",
        ROOT / "frontend" / "app" / "dashboard" / "page.tsx",
        ROOT / "docs" / "self_serve_api_product_v092.md",
        ROOT / "docs" / "self_serve_user_flow_v092.md",
        ROOT / "docs" / "self_serve_key_quickstart_v092.md",
        ROOT / "examples" / "run_self_serve_api_product_v092.py",
    ]
    add(
        checks,
        "required_product_files_exist",
        all(path.exists() for path in required_files),
        [str(path.relative_to(ROOT)) for path in required_files if not path.exists()],
    )
    new_product_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in required_files
        if path.exists() and path.suffix in {".py", ".md", ".tsx"}
    )
    add(
        checks,
        "product_layer_is_generic_not_client_specific",
        "continuum" not in new_product_text.lower(),
    )

    isolation_probe = SelfServeDashboardV092()
    limit_ids: list[str] = []
    key_limit_ids: list[str] = []
    for index in range(2):
        email = f"scope-{index}@example.test"
        created_account = isolation_probe.signup(
            name=f"Synthetic Scope {index}",
            email=email,
            password=f"synthetic-scope-password-{index}",
        )
        probe_user_id = created_account["account"]["user_id"]
        isolation_probe.verify_email_local(user_id=probe_user_id)
        probe_login = isolation_probe.login(email=email, password=f"synthetic-scope-password-{index}")
        probe_session = probe_login["session_token"]
        isolation_probe.choose_plan(session_token=probe_session, plan_id="free")
        probe_scope = isolation_probe.provision_default_scope(session_token=probe_session)["scope"]
        probe_key = isolation_probe.create_key(session_token=probe_session, label=f"Scope {index} key")
        limit_ids.append(probe_scope["usage_limit_id"])
        key_limit_ids.append(
            isolation_probe.api.lifecycle.lifecycle_keys[probe_key["key_id"]].usage_limit_id
        )
    add(
        checks,
        "each_client_key_uses_its_own_usage_limit",
        len(set(limit_ids)) == 2 and key_limit_ids == limit_ids,
        {"distinct_scope_limits": len(set(limit_ids))},
    )

    nested_routes = [
        ROOT / "frontend" / "app" / "dashboard" / name / "page.tsx"
        for name in ["api-keys", "usage", "docs", "billing"]
    ]
    add(checks, "dashboard_subroutes_exist", all(path.exists() for path in nested_routes))

    public_report, private_report, smoke_report, runner_checks = run_smoke()
    runner_by_name = {item["name"]: item["passed"] for item in runner_checks}
    required_runner_checks = [
        "create_new_user",
        "email_starts_unverified",
        "verify_email_state",
        "choose_free_plan",
        "provision_client",
        "provision_vault",
        "provision_namespace",
        "create_api_key",
        "raw_key_returned_once",
        "key_list_is_safe_preview_only",
        "env_quickstart_generated",
        "key_validates",
        "event_ingest_works",
        "continuity_packet_works",
        "memory_reconstruct_works",
        "explain_works",
        "get_report_works",
        "usage_count_increments",
        "free_plan_limit_enforced",
        "rotate_key_works",
        "old_key_blocked_after_rotate",
        "revoke_key_works",
        "revoked_key_blocked",
        "dashboard_state_has_no_raw_key",
        "public_report_has_no_secrets",
    ]
    add(
        checks,
        "all_25_functional_checks_pass",
        len(runner_checks) == 25 and all(runner_by_name.get(name) is True for name in required_runner_checks),
        {"passed": sum(1 for item in runner_checks if item["passed"]), "total": len(runner_checks)},
    )

    for audit_name, runner_name in [
        ("account_signup_and_verified_state_work", "verify_email_state"),
        ("free_plan_selection_works", "choose_free_plan"),
        ("generic_client_scope_is_created", "provision_namespace"),
        ("copy_once_key_behavior_works", "raw_key_returned_once"),
        ("safe_key_listing_works", "key_list_is_safe_preview_only"),
        ("key_validation_works", "key_validates"),
        ("protected_continuity_flow_works", "continuity_packet_works"),
        ("usage_limit_is_enforced", "free_plan_limit_enforced"),
        ("rotation_blocks_old_key", "old_key_blocked_after_rotate"),
        ("revocation_blocks_key", "revoked_key_blocked"),
        ("dashboard_is_secret_safe", "dashboard_state_has_no_raw_key"),
    ]:
        add(checks, audit_name, runner_by_name.get(runner_name) is True)

    docs_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in required_files
        if path.suffix == ".md" and path.exists()
    )
    add(
        checks,
        "docs_cover_complete_user_flow",
        all(
            phrase in docs_text.lower()
            for phrase in [
                "sign up",
                "verify",
                "choose a plan",
                "copy-once",
                "server-side",
                "rotation",
                "revocation",
                "request logs",
            ]
        ),
    )
    add(
        checks,
        "quickstart_contains_required_environment",
        all(
            phrase in docs_text
            for phrase in [
                "PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com",
                "PRMR_API_KEY=<YOUR_PRMR_KEY>",
                "PRMR_CLIENT_ID=<CLIENT_ID>",
                "PRMR_VAULT_ID=<VAULT_ID>",
                "PRMR_NAMESPACE=default",
            ]
        ),
    )
    add(
        checks,
        "email_simulation_is_disclosed",
        "no email is sent" in docs_text.lower() and public_report["real_email_delivery"] == "NOT_CONNECTED",
    )
    add(
        checks,
        "billing_simulation_is_disclosed",
        "payment processing is not connected" in docs_text.lower()
        and public_report["real_payment_processing"] == "NOT_CONNECTED",
    )
    add(
        checks,
        "durable_hosted_registry_gap_is_disclosed",
        public_report["hosted_self_serve_registry"] == "NOT_DEPLOYED"
        and public_report["durable_account_storage"] == "NOT_CONNECTED",
    )

    public_text = json.dumps(public_report, sort_keys=True)
    add(checks, "public_report_contains_no_secret", not contains_secret(public_text))
    add(
        checks,
        "no_false_production_or_certification_claim",
        not has_unqualified_claim(docs_text + "\n" + public_text),
    )

    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx"} and ".next" not in path.parts
    )
    add(
        checks,
        "frontend_does_not_embed_credential",
        not re.search(r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b", frontend_text),
    )
    add(
        checks,
        "frontend_contains_product_entry_cta",
        "Get API Key" in frontend_text and 'href="/signup"' in frontend_text,
    )
    add(
        checks,
        "dashboard_contains_all_required_sections",
        all(
            phrase in frontend_text
            for phrase in [
                "Overview",
                "API Keys",
                "Usage",
                "Logs",
                "Reports",
                "Vaults",
                "Quickstart",
                "Billing / Plan",
                "Account",
                "Support",
            ]
        ),
    )

    typecheck_ok, typecheck_output = run_frontend("typecheck")
    add(checks, "frontend_typecheck_passes", typecheck_ok, typecheck_output)
    build_ok, build_output = run_frontend("build")
    add(checks, "frontend_build_passes", build_ok, build_output)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.92",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "runner_result": public_report["result"],
        "public_safe": True,
        "checks": [
            {"name": item["name"], "passed": item["passed"]}
            for item in checks
        ],
    }
    write_json(PUBLIC_REPORT, {**public_report, "audit_result": result})
    write_json(PRIVATE_REPORT, {**private_report, "audit": {**audit, "checks": checks}})
    write_json(SMOKE_REPORT, {**smoke_report, "audit_result": result})
    SCORECARD.write_text(
        build_scorecard(public_report, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Frontend typecheck: {'PASS' if typecheck_ok else 'FAIL'}\n"
        + f"- Frontend build: {'PASS' if build_ok else 'FAIL'}\n",
        encoding="utf-8",
    )
    print("PRMR Memory Core V0.92 Self-Serve API Product Audit")
    print(f"Runner result: {public_report['result']} ({public_report['checks_passed']}/{public_report['checks_total']})")
    print(f"Frontend typecheck: {'PASS' if typecheck_ok else 'FAIL'}")
    print(f"Frontend build: {'PASS' if build_ok else 'FAIL'}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
                if check.get("detail"):
                    print(str(check["detail"])[-600:])
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
