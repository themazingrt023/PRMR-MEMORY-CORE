"""Run the generic PRMR V0.92 self-serve API product MVP."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.self_serve_dashboard_v092 import (
    API_BASE_URL,
    PRODUCT_BOUNDARY_V092,
    SelfServeDashboardV092,
)


REPORT_DIR = ROOT / "reports" / "v092"
PUBLIC_REPORT = REPORT_DIR / "public_self_serve_api_product_v092.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_self_serve_api_product_v092.json"
SMOKE_REPORT = REPORT_DIR / "self_serve_api_product_smoke_v092.json"
SCORECARD = REPORT_DIR / "scorecard_v092.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any, known_keys: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(key and key in text for key in (known_keys or [])):
        return True
    patterns = [
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b",
        r"\bprmr_session_local_[A-Za-z0-9_-]{24,}\b",
        r'"password"\s*:\s*"[^"]+"',
        r'"session_token"\s*:\s*"[^"]+"',
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def synthetic_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_ss_001",
            "user_id": "synthetic_builder",
            "type": "project_created",
            "content": "A synthetic project was created with an initial planning state.",
            "timestamp_index": 1,
        },
        {
            "event_id": "evt_ss_002",
            "user_id": "synthetic_builder",
            "type": "project_updated",
            "content": "The synthetic project moved from planning to review.",
            "timestamp_index": 2,
        },
    ]


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    product = SelfServeDashboardV092()
    checks: list[dict[str, Any]] = []

    signup = product.signup(
        name="Synthetic API Builder",
        email="builder-v092@example.test",
        password="synthetic-password-v092",
    )
    add(checks, "create_new_user", signup["status_code"] == 201)
    user_id = signup["account"]["user_id"]
    add(checks, "email_starts_unverified", signup["account"]["status"] == "unverified" and signup["email_sent"] is False)

    verified = product.verify_email_local(user_id=user_id)
    add(
        checks,
        "verify_email_state",
        verified["account"]["status"] == "verified"
        and verified["verification_simulated"] is True
        and verified["email_sent"] is False,
    )
    login = product.login(email="builder-v092@example.test", password="synthetic-password-v092")
    session_token = str(login["session_token"])

    plan = product.choose_plan(session_token=session_token, plan_id="free")
    add(
        checks,
        "choose_free_plan",
        plan["subscription"]["status"] == "active"
        and plan["plan"]["requests_per_month"] == 100
        and plan["payment_processed"] is False,
    )

    provisioned = product.provision_default_scope(session_token=session_token)
    scope = provisioned["scope"]
    add(checks, "provision_client", provisioned["status_code"] == 201 and scope["client_id"].startswith("client_ss_"))
    add(checks, "provision_vault", scope["vault_id"].startswith("vault_ss_"))
    add(checks, "provision_namespace", scope["namespace"] == "default")

    created = product.create_key(session_token=session_token, label="Development server")
    raw_key = str(created["raw_api_key"])
    key_id = str(created["key_id"])
    add(checks, "create_api_key", created["status_code"] == 201 and created["safe_key_preview"].startswith("prmr_alpha_..."))
    add(
        checks,
        "raw_key_returned_once",
        created["returned_once"] is True and raw_key.startswith("prmr_alpha_") and len(raw_key) > 32,
    )

    listed = product.list_keys(session_token=session_token)
    add(
        checks,
        "key_list_is_safe_preview_only",
        listed["safe_previews_only"] is True
        and listed["credential_values_returned"] is False
        and not contains_secret(listed, [raw_key]),
    )

    dashboard_before = product.dashboard_state(session_token=session_token)
    env_lines = dashboard_before["dashboard"]["quickstart"]["environment"]
    add(
        checks,
        "env_quickstart_generated",
        env_lines
        == [
            f"PRMR_API_BASE_URL={API_BASE_URL}",
            "PRMR_API_KEY=<YOUR_PRMR_KEY>",
            "PRMR_CLIENT_ID=<CLIENT_ID>",
            "PRMR_VAULT_ID=<VAULT_ID>",
            "PRMR_NAMESPACE=default",
        ],
    )

    valid, validation_reason = product.keys.preflight_key(
        raw_key=raw_key,
        client_id=scope["client_id"],
    )
    add(checks, "key_validates", valid and validation_reason == "allowed")

    common = {
        "api_key": raw_key,
        "client_id": scope["client_id"],
        "vault_id": scope["vault_id"],
        "namespace": scope["namespace"],
    }
    ingest = product.execute("events_ingest", **common, events=synthetic_events())
    add(
        checks,
        "event_ingest_works",
        ingest["status_code"] == 200 and ingest["body"]["accepted_event_count"] == len(synthetic_events()),
    )
    packet = product.execute("continuity_packet", **common)
    packet_id = packet.get("body", {}).get("packet_id")
    report_id = packet.get("body", {}).get("report_id")
    add(checks, "continuity_packet_works", packet["status_code"] == 200 and bool(packet_id) and bool(report_id))

    reconstruct = product.execute("memory_reconstruct", **common, packet_id=packet_id)
    add(
        checks,
        "memory_reconstruct_works",
        reconstruct["status_code"] == 200
        and reconstruct["body"]["reconstructable_state"]["current_state"]
        == "The synthetic project moved from planning to review.",
    )
    explain = product.execute("explain", **common, packet_id=packet_id)
    least_harm = product.execute("least_harm_action", **common, packet_id=packet_id)
    add(
        checks,
        "explain_works",
        explain["status_code"] == 200
        and explain["body"]["explanation"]["sensitive_details_included"] is False
        and least_harm["status_code"] == 200
        and least_harm["body"]["not_final_decision"] is True,
    )
    report = product.execute("get_report", **common, report_id=report_id)
    add(
        checks,
        "get_report_works",
        report["status_code"] == 200 and report["body"]["report"]["public_safe"] is True,
    )
    usage = product.execute("get_usage", **common)
    dashboard_after = product.dashboard_state(session_token=session_token)
    requests_used = dashboard_after["dashboard"]["plan"]["usage"]["requests_used"]
    add(
        checks,
        "usage_count_increments",
        usage["status_code"] == 200 and requests_used == 7,
        {"requests_used": requests_used},
    )

    product.plans.monthly_usage[(user_id, product.plans.month_key())] = 100
    quota_block = product.execute("get_usage", **common)
    add(
        checks,
        "free_plan_limit_enforced",
        quota_block["status_code"] == 429
        and quota_block["body"]["error"]["code"] == "monthly_request_limit_exceeded",
    )

    rotated = product.rotate_key(session_token=session_token, key_id=key_id)
    replacement_key = str(rotated["raw_api_key"])
    add(
        checks,
        "rotate_key_works",
        rotated["status_code"] == 200
        and rotated["old_key_id"] == key_id
        and rotated["new_key_id"] != key_id
        and rotated["returned_once"] is True,
    )
    old_blocked = product.execute("get_usage", **common)
    add(
        checks,
        "old_key_blocked_after_rotate",
        old_blocked["status_code"] == 403 and old_blocked["body"]["error"]["code"] == "rotated_key",
    )

    replacement_id = str(rotated["new_key_id"])
    revoked = product.revoke_key(session_token=session_token, key_id=replacement_id)
    add(checks, "revoke_key_works", revoked["status_code"] == 200 and revoked["status"] == "revoked")
    revoked_blocked = product.execute(
        "get_usage",
        api_key=replacement_key,
        client_id=scope["client_id"],
        vault_id=scope["vault_id"],
        namespace=scope["namespace"],
    )
    add(
        checks,
        "revoked_key_blocked",
        revoked_blocked["status_code"] == 403 and revoked_blocked["body"]["error"]["code"] == "revoked_key",
    )

    safe_dashboard = product.dashboard_state(session_token=session_token)
    add(
        checks,
        "dashboard_state_has_no_raw_key",
        safe_dashboard["dashboard"]["credential_values_exposed"] is False
        and safe_dashboard["dashboard"]["session_token_exposed"] is False
        and not contains_secret(safe_dashboard, [raw_key, replacement_key, session_token]),
    )

    passed_before_public = sum(1 for check in checks if check["passed"])
    total_with_public = len(checks) + 1
    provisional_result = "PASS" if passed_before_public == len(checks) else "NEEDS_WORK"
    public_report = {
        "version": "0.92",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Self-Serve API Product MVP",
        "truth_label": "local/deployable generic self-serve API product MVP evidence",
        "result": provisional_result,
        "checks_passed": passed_before_public,
        "checks_total": total_with_public,
        "public_safe": True,
        "flow": [
            "signup",
            "local verification",
            "plan selection",
            "generic client scope",
            "copy-once key",
            "protected PRMR operations",
            "safe dashboard",
        ],
        "plan_model": {
            "free": "100 requests/month; locally active",
            "builder": "10,000 requests/month; billing not connected",
            "controlled_pilot": "manual approval; from GBP 250",
        },
        "scope": {
            "client_id_generated": True,
            "vault_id_generated": True,
            "namespace": "default",
        },
        "protected_flow": {
            "events_ingested": ingest["body"].get("accepted_event_count"),
            "packet_created": bool(packet_id),
            "reconstruction_created": reconstruct["status_code"] == 200,
            "explanation_created": explain["status_code"] == 200,
            "least_harm_boundary_created": least_harm["status_code"] == 200,
            "public_report_read": report["status_code"] == 200,
            "usage_read": usage["status_code"] == 200,
        },
        "key_lifecycle": {
            "copy_once": True,
            "safe_preview_only_after_creation": True,
            "rotation_blocks_old_key": True,
            "revocation_blocks_key": True,
            "credential_value_exposed": False,
        },
        "hosted_self_serve_registry": "NOT_DEPLOYED",
        "real_email_delivery": "NOT_CONNECTED",
        "real_payment_processing": "NOT_CONNECTED",
        "durable_account_storage": "NOT_CONNECTED",
        "boundary": PRODUCT_BOUNDARY_V092,
    }
    public_safe = not contains_secret(public_report, [raw_key, replacement_key, session_token])
    add(checks, "public_report_has_no_secrets", public_safe)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public_report.update(result=result, checks_passed=passed, checks_total=total)
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "safe_account_id": user_id,
        "safe_client_id": scope["client_id"],
        "safe_vault_id": scope["vault_id"],
        "key_hashes_retained": True,
        "credential_values_retained": False,
        "session_token_retained": False,
        "request_log": [asdict_log(row) for row in product.api.api_request_log],
    }
    smoke_report = {
        "version": "0.92",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
        "hosted_self_serve_status": "NOT_DEPLOYED",
        "boundary": PRODUCT_BOUNDARY_V092,
    }
    return public_report, private_report, smoke_report, checks


def asdict_log(row: Any) -> dict[str, Any]:
    return {
        "timestamp": row.timestamp,
        "endpoint": row.endpoint,
        "client_id": row.client_id,
        "vault_id": row.vault_id,
        "namespace": row.namespace,
        "status": row.status,
        "reason": row.reason,
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.92 Self-Serve API Product MVP",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {PRODUCT_BOUNDARY_V092}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks)
    lines.extend(
        [
            "",
            "## Evidence levels",
            "",
            "- Generic local/deployable self-serve product flow: tested",
            "- Protected PRMR operations: tested through the existing scoped API logic",
            "- Hosted self-serve account/key registry: not deployed",
            "- Real email and payments: not connected",
            "- External launch validation: none",
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
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")
    print("PRMR Memory Core V0.92 Self-Serve API Product MVP")
    print("Flow: signup -> local verify -> plan -> scope -> copy-once key -> protected API -> dashboard")
    print("Email delivery: NOT_CONNECTED")
    print("Payment processing: NOT_CONNECTED")
    print("Hosted self-serve registry: NOT_DEPLOYED")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    if public_report["result"] != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
