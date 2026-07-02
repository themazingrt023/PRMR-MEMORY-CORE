"""Audit V0.91 first internal PRMR API integration."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_first_internal_product_integration_v091 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_credential,
    run_smoke,
    write_json,
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    v088 = ROOT / "reports" / "v088" / "public_api_client_dashboard_v088.json"
    v090 = ROOT / "reports" / "v090" / "public_whop_manual_approval_v090.json"
    module = ROOT / "prmr" / "integrations" / "internal_product_client_v091.py"
    docs = ROOT / "docs" / "first_internal_product_integration_v091.md"
    add(checks, "v088_and_v090_evidence_exists", v088.exists() and v090.exists())
    add(checks, "internal_integration_client_exists", module.exists())
    add(checks, "integration_docs_exist", docs.exists())

    public_report, private_report, smoke_report, runner_checks = run_smoke()
    by_name = {check["name"]: check["passed"] for check in runner_checks}
    for audit_name, runner_name in [
        ("copy_once_key_created", "v088_approved_client_and_copy_once_key_created"),
        ("temporary_env_outside_repo", "credential_env_is_temporary_and_outside_repo"),
        ("environment_scope_loads", "server_side_environment_loads_complete_scope"),
        ("all_api_routes_succeed", "all_scoped_http_routes_succeed"),
        ("continuity_and_reconstruction_exist", "continuity_packet_and_reconstruction_exist"),
        ("explanation_and_action_exist", "explanation_and_least_harm_outputs_exist"),
        ("report_is_owner_readable", "owned_public_report_is_readable"),
        ("usage_is_scoped", "scoped_usage_is_visible"),
        ("dashboard_does_not_reveal_key", "dashboard_state_retains_preview_not_credential"),
        ("workflow_does_not_echo_key", "workflow_outputs_do_not_echo_credential"),
        ("temporary_env_removed", "temporary_env_is_removed_after_run"),
        ("hosted_status_is_honest", "hosted_status_is_reported_honestly"),
    ]:
        add(checks, audit_name, by_name.get(runner_name) is True)

    docs_text = re.sub(r"\s+", " ", docs.read_text(encoding="utf-8").lower())
    add(
        checks,
        "server_side_secret_guidance_present",
        all(
            phrase in docs_text
            for phrase in [
                "never put `prmr_api_key` in",
                "temporary directory outside the repository",
                "a local pass must not be relabelled as a hosted pass",
            ]
        ),
    )
    add(checks, "public_report_is_credential_safe", not contains_credential(public_report))
    add(
        checks,
        "hosted_and_external_evidence_not_claimed",
        smoke_report["hosted_internal_integration"] == "NOT_RUN_NEEDS_INTERNAL_SCOPE"
        and public_report["external_client_evidence"] is False,
    )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.91",
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
    print("PRMR Memory Core V0.91 Internal Product Integration Audit")
    print(f"Runner result: {public_report['result']}")
    print(f"Hosted internal scope: {smoke_report['hosted_internal_integration']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
