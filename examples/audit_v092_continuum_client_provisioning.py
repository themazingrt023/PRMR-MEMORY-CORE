"""Audit V0.92 Continuum OS PRMR approved-client provisioning."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_continuum_client_provisioning_v092 import (
    PRIVATE_ENV_PACKET,
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    build_scorecard,
    contains_raw_key,
    run_smoke,
    write_json,
)
from prmr.product.continuum_client_provisioning_v092 import (
    API_BASE_URL,
    CLIENT_ID,
    CLIENT_STATUS,
    NAMESPACE,
    VAULT_ID,
)
from prmr.product.hosted_backend_foundation_v069 import safe_hash


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    v091 = ROOT / "reports" / "v091" / "public_first_internal_product_integration_v091.json"
    module = ROOT / "prmr" / "product" / "continuum_client_provisioning_v092.py"
    runner = ROOT / "examples" / "run_continuum_client_provisioning_v092.py"
    docs = ROOT / "docs" / "continuum_prmr_api_key_setup_v092.md"
    add(checks, "v091_internal_integration_evidence_exists", v091.exists())
    add(checks, "v092_module_runner_and_docs_exist", module.exists() and runner.exists() and docs.exists())

    public_report, private_report, smoke_report, env_packet, runner_checks = run_smoke()
    by_name = {check["name"]: check["passed"] for check in runner_checks}
    for audit_name, runner_name in [
        ("approved_client_record_created", "approved_continuum_client_created"),
        ("vault_and_namespace_created", "continuum_scope_created"),
        ("copy_once_key_behavior_works", "copy_once_alpha_key_issued"),
        ("hash_and_preview_exist", "private_hash_and_safe_preview_exist"),
        ("private_env_packet_complete", "private_env_packet_has_required_fields"),
        ("key_validates", "generated_key_validates_against_protected_logic"),
        ("all_prmr_routes_work", "all_required_prmr_routes_succeed"),
        ("all_required_continuum_events_ingested", "all_six_continuum_event_types_ingested"),
        ("continuity_outputs_returned", "continuity_outputs_exist"),
        ("owned_report_returned", "owned_report_is_public_safe"),
        ("usage_scoped_to_continuum", "usage_is_scoped_to_continuum_client"),
        ("dashboard_uses_safe_preview_only", "dashboard_shows_continuum_scope_and_safe_preview"),
        ("dashboard_reporting_is_visible", "dashboard_usage_reports_and_memory_health_are_visible"),
        ("non_packet_reports_have_no_raw_key", "non_packet_reports_contain_no_raw_key"),
        ("hosted_and_app_boundaries_are_honest", "hosted_and_actual_app_boundaries_are_honest"),
    ]:
        add(checks, audit_name, by_name.get(runner_name) is True)

    raw_key = str(env_packet.get("PRMR_API_KEY") or "")
    provisioning = private_report.get("provisioning_record", {})
    add(
        checks,
        "packet_values_match_required_scope",
        env_packet.get("PRMR_API_BASE_URL") == API_BASE_URL
        and env_packet.get("PRMR_CLIENT_ID") == CLIENT_ID
        and env_packet.get("PRMR_VAULT_ID") == VAULT_ID
        and env_packet.get("PRMR_NAMESPACE") == NAMESPACE
        and raw_key.startswith("prmr_alpha_"),
    )
    add(
        checks,
        "private_stored_hash_matches_copy_once_key",
        bool(raw_key)
        and provisioning.get("key_hash") == safe_hash(raw_key)
        and provisioning.get("status") == CLIENT_STATUS,
    )
    add(
        checks,
        "private_packet_is_classified_and_ignored",
        PRIVATE_ENV_PACKET.exists()
        and env_packet.get("local_private_only") is True
        and env_packet.get("do_not_commit") is True
        and env_packet.get("do_not_share") is True,
    )
    ignore = subprocess.run(
        ["git", "check-ignore", "-q", str(PRIVATE_ENV_PACKET.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    add(checks, "private_packet_is_git_ignored", ignore.returncode == 0)

    docs_text = re.sub(r"\s+", " ", docs.read_text(encoding="utf-8").lower().replace("**", ""))
    add(
        checks,
        "docs_separate_continuum_and_prmr",
        "continuum os and prmr memory core are separate products" in docs_text
        and "prmr memory core is the independent api infrastructure provider" in docs_text,
    )
    add(
        checks,
        "docs_require_server_side_key_and_non_sensitive_data",
        "continuum os server environment only" in docs_text
        and "no real continuum user data is permitted by default" in docs_text,
    )
    add(
        checks,
        "docs_disclose_hosted_registration_gap",
        "not yet registered in the currently deployed render backend" in docs_text
        and "do not place the packet into the actual continuum os application until" in docs_text,
    )
    add(
        checks,
        "public_and_internal_reports_are_credential_safe",
        not contains_raw_key(public_report, raw_key)
        and not contains_raw_key(private_report, raw_key)
        and not contains_raw_key(smoke_report, raw_key),
    )
    add(
        checks,
        "private_packet_contents_are_not_copied_to_public_report",
        raw_key not in json.dumps(public_report, sort_keys=True)
        and public_report["evidence"]["private_env_packet"]["contents_exposed"] is False,
    )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and public_report["result"] == "PASS" else "NEEDS_WORK"
    audit = {
        "version": "0.92",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "checks": checks,
        "runner_result": public_report["result"],
        "private_packet_checked_without_echoing_credential": True,
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
    print("PRMR Memory Core V0.92 Continuum Client Provisioning Audit")
    print(f"Runner result: {public_report['result']}")
    print(f"Private packet present and ignored: {'PASS' if ignore.returncode == 0 else 'FAIL'}")
    print("Raw credential echoed by audit: NO")
    print(f"Hosted key registration: {smoke_report['hosted_key_registration']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
