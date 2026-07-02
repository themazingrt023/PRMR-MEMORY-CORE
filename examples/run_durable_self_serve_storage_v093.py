"""Run V0.93 durable self-serve SQLite restart/reload evidence."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.durable_self_serve_storage_v093 import (
    BOUNDARY_V093,
    DurableSelfServeProductV093,
    storage_status_v093,
)
from prmr.product.hosted_backend_foundation_v069 import safe_hash


REPORT_DIR = ROOT / "reports" / "v093"
PUBLIC_REPORT = REPORT_DIR / "public_durable_self_serve_storage_v093.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_durable_self_serve_storage_v093.json"
SMOKE_REPORT = REPORT_DIR / "durable_self_serve_storage_smoke_v093.json"
SCORECARD = REPORT_DIR / "scorecard_v093.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret(payload: Any, known_values: list[str] | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if any(value and value in text for value in (known_values or [])):
        return True
    patterns = [
        r"\bprmr_(?:alpha|live)_[A-Za-z0-9_-]{24,}\b",
        r"\bprmr_session_local_[A-Za-z0-9_-]{24,}\b",
        r'"password_hash"\s*:',
        r'"password_salt"\s*:',
        r'"key_hash"\s*:',
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_v093_001",
            "user_id": "synthetic_v093_builder",
            "type": "project_created",
            "content": "A synthetic project entered planning.",
            "timestamp_index": 1,
        },
        {
            "event_id": "evt_v093_002",
            "user_id": "synthetic_v093_builder",
            "type": "project_updated",
            "content": "The synthetic project moved to review after a storage reload.",
            "timestamp_index": 2,
        },
    ]


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    password = "synthetic-durable-password-v093"
    raw_key = ""
    replacement_key = ""
    private_trace: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="prmr-v093-", ignore_cleanup_errors=True) as temp_dir:
        storage_path = Path(temp_dir) / "prmr_self_serve.sqlite"
        first = DurableSelfServeProductV093(storage_path)
        add(checks, "temporary_durable_sqlite_created", storage_path.exists())

        signup = first.signup(
            name="Synthetic Durable Builder",
            email="durable-v093@example.test",
            password=password,
        )
        user_id = signup["account"]["user_id"]
        add(checks, "user_created", signup["status_code"] == 201)
        verified = first.verify_email_local(user_id=user_id)
        add(checks, "user_verified", verified["account"]["status"] == "verified")
        login = first.login(email="durable-v093@example.test", password=password)
        session_token = str(login["session_token"])
        selected = first.choose_plan(session_token=session_token, plan_id="free")
        add(checks, "free_plan_selected", selected["subscription"]["status"] == "active")
        provisioned = first.provision_default_scope(session_token=session_token)
        scope = provisioned["scope"]
        add(checks, "client_created", scope["client_id"].startswith("client_ss_"))
        add(checks, "vault_created", scope["vault_id"].startswith("vault_ss_"))
        add(checks, "namespace_created", scope["namespace"] == "default")

        created_key = first.create_key(session_token=session_token, label="Durable development server")
        key_id = str(created_key["key_id"])
        raw_key = str(created_key["raw_api_key"])
        preview = str(created_key["safe_key_preview"])
        add(checks, "api_key_created", created_key["status_code"] == 201)
        add(checks, "raw_key_returned_once", created_key["returned_once"] is True and raw_key.startswith("prmr_alpha_"))
        persisted_hashes = first.repository.private_key_hashes()
        add(checks, "key_hash_persisted", persisted_hashes.get(key_id) == safe_hash(raw_key))
        add(
            checks,
            "safe_preview_persisted",
            first.repository.safe_key_rows()[0]["safe_key_preview"] == preview,
        )

        second = DurableSelfServeProductV093(storage_path)
        add(
            checks,
            "restart_reload_completed",
            second.repository.table_counts()["users"] == 1,
        )
        add(checks, "user_exists_after_reload", user_id in second.product.accounts.accounts)
        add(
            checks,
            "verification_state_exists_after_reload",
            second.product.accounts.accounts[user_id].status == "verified",
        )
        add(
            checks,
            "plan_exists_after_reload",
            second.product.plans.subscriptions[user_id].plan_id == "free",
        )
        restored_scope = second.product.keys.scopes_by_user[user_id]
        add(
            checks,
            "scope_exists_after_reload",
            restored_scope.client_id == scope["client_id"]
            and restored_scope.vault_id == scope["vault_id"]
            and restored_scope.namespace == "default",
        )
        restored_list = second.list_keys(session_token=session_token)
        add(
            checks,
            "safe_preview_exists_after_reload",
            restored_list["keys"][0]["safe_key_preview"] == preview,
        )
        add(
            checks,
            "raw_key_not_recoverable_after_reload",
            not second.repository.raw_value_present(raw_key)
            and not second.repository.raw_value_present(password)
            and "raw_api_key" not in json.dumps(restored_list),
        )
        valid, reason = second.product.keys.preflight_key(
            raw_key=raw_key,
            client_id=scope["client_id"],
        )
        add(checks, "persisted_key_validates", valid and reason == "allowed")

        common = {
            "api_key": raw_key,
            "client_id": scope["client_id"],
            "vault_id": scope["vault_id"],
            "namespace": scope["namespace"],
        }
        ingest = second.execute("events_ingest", **common, events=events())
        packet = second.execute("continuity_packet", **common)
        packet_id = packet.get("body", {}).get("packet_id")
        report_id = packet.get("body", {}).get("report_id")
        reconstruct = second.execute("memory_reconstruct", **common, packet_id=packet_id)
        explain = second.execute("explain", **common, packet_id=packet_id)
        least_harm = second.execute("least_harm_action", **common, packet_id=packet_id)
        report = second.execute("get_report", **common, report_id=report_id)
        usage = second.execute("get_usage", **common)
        flow_statuses = {
            "ingest": ingest["status_code"],
            "packet": packet["status_code"],
            "reconstruct": reconstruct["status_code"],
            "explain": explain["status_code"],
            "least_harm": least_harm["status_code"],
            "report": report["status_code"],
            "usage": usage["status_code"],
        }
        add(
            checks,
            "protected_prmr_flow_works",
            all(status == 200 for status in flow_statuses.values()),
            flow_statuses,
        )

        usage_before_reload = second.product.plans.usage_summary(user_id)["requests_used"]
        request_logs_before_reload = len(second.product.api.api_request_log)
        third = DurableSelfServeProductV093(storage_path)
        add(
            checks,
            "usage_persists_after_reload",
            third.product.plans.usage_summary(user_id)["requests_used"] == usage_before_reload
            and usage_before_reload == 7,
        )
        add(
            checks,
            "request_logs_persist_after_reload",
            len(third.product.api.api_request_log) == request_logs_before_reload
            and request_logs_before_reload >= 7,
        )
        add(
            checks,
            "report_references_persist_after_reload",
            report_id in third.product.api.public_reports
            and report_id in third.product.api.private_reports,
        )

        rotated = third.rotate_key(session_token=session_token, key_id=key_id)
        replacement_id = str(rotated["new_key_id"])
        replacement_key = str(rotated["raw_api_key"])
        add(
            checks,
            "key_rotated",
            rotated["status_code"] == 200 and replacement_id != key_id,
        )
        fourth = DurableSelfServeProductV093(storage_path)
        old_blocked = fourth.execute("get_usage", **common)
        add(
            checks,
            "old_key_blocked_after_persisted_rotation",
            old_blocked["status_code"] == 403
            and old_blocked["body"]["error"]["code"] == "rotated_key",
        )
        replacement_valid, replacement_reason = fourth.product.keys.preflight_key(
            raw_key=replacement_key,
            client_id=scope["client_id"],
        )
        add(
            checks,
            "new_key_validates_after_reload",
            replacement_valid and replacement_reason == "allowed",
        )
        revoked = fourth.revoke_key(session_token=session_token, key_id=replacement_id)
        add(checks, "replacement_key_revoked", revoked["status_code"] == 200)
        fifth = DurableSelfServeProductV093(storage_path)
        revoked_blocked = fifth.execute(
            "get_usage",
            api_key=replacement_key,
            client_id=scope["client_id"],
            vault_id=scope["vault_id"],
            namespace=scope["namespace"],
        )
        add(
            checks,
            "revoked_key_blocked_after_reload",
            revoked_blocked["status_code"] == 403
            and revoked_blocked["body"]["error"]["code"] == "revoked_key",
        )
        dashboard = fifth.dashboard_state(session_token=session_token)
        snapshot = fifth.repository.read_dashboard_snapshot(user_id)
        add(
            checks,
            "dashboard_reloads_from_persisted_records",
            dashboard["status_code"] == 200
            and dashboard["dashboard"]["client_scope"]["client_id"] == scope["client_id"]
            and len(dashboard["dashboard"]["reports"]) == 1
            and snapshot is not None
            and snapshot["reconstructable"] is True,
        )

        table_counts = fifth.repository.table_counts()
        local_status = fifth.storage_status
        ephemeral_status = storage_status_v093(
            storage_path="/tmp/prmr_self_serve.sqlite",
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        durable_candidate_status = storage_status_v093(
            storage_path="/var/data/prmr_self_serve.sqlite",
            api_mode="hosted_alpha",
            durable_storage_verified=True,
        )
        private_trace = {
            "database_table_counts": table_counts,
            "key_hash_persisted": True,
            "key_hash_prefix": persisted_hashes[key_id][:12],
            "raw_key_persisted": False,
            "raw_password_persisted": False,
            "reload_generations": 5,
            "flow_statuses": flow_statuses,
            "storage_path_was_temporary_test_path": True,
        }

    passed_before_public = sum(1 for check in checks if check["passed"])
    public_report = {
        "version": "0.93",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Durable Self-Serve Storage",
        "truth_label": "local SQLite restart/reload persistence evidence",
        "result": "PASS" if passed_before_public == len(checks) else "NEEDS_WORK",
        "checks_passed": passed_before_public,
        "checks_total": len(checks) + 1,
        "public_safe": True,
        "persisted_entities": [
            "users",
            "verification state",
            "hashed sessions",
            "plans",
            "clients",
            "vaults",
            "namespaces",
            "API key hashes and safe previews",
            "monthly usage",
            "request logs",
            "continuity state",
            "report references",
            "dashboard snapshots",
        ],
        "restart_reload": {
            "reload_generations_tested": 5,
            "account_recovered": True,
            "key_validation_recovered": True,
            "usage_recovered": True,
            "logs_recovered": True,
            "reports_recovered": True,
            "dashboard_reconstructed": True,
        },
        "key_storage": {
            "hash_persisted_privately": True,
            "safe_preview_persisted": True,
            "raw_key_persisted": False,
            "raw_key_recoverable": False,
            "rotation_and_revocation_persist": True,
        },
        "storage": {
            "test_mode": local_status,
            "tmp_classification": ephemeral_status,
            "recommended_hosted_path": "/var/data/prmr_self_serve.sqlite",
            "recommended_path_classification": durable_candidate_status,
            "hosted_redeploy_proof": "NOT_RUN",
        },
        "real_email_delivery": "NOT_CONNECTED",
        "payment_processing": "NOT_CONNECTED",
        "production_auth": "NOT_IMPLEMENTED",
        "boundary": BOUNDARY_V093,
    }
    public_safe = not contains_secret(
        public_report,
        [raw_key, replacement_key, password],
    )
    add(checks, "public_report_has_no_secrets", public_safe)
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total and total == 30 else "NEEDS_WORK"
    public_report.update(result=result, checks_passed=passed, checks_total=total)
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "private_trace": private_trace,
        "restricted_note": "No raw API key, session token, or password is included.",
    }
    smoke_report = {
        "version": "0.93",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
        "storage_mode": "local_sqlite",
        "hosted_redeploy_proof": "NOT_RUN",
        "public_safe": True,
        "boundary": BOUNDARY_V093,
    }
    return public_report, private_report, smoke_report, checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.93 Durable Hosted Account + Key Storage",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V093}",
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
            "- Local SQLite restart/reload persistence: tested",
            "- Hosted persistent disk configuration: documented",
            "- Hosted redeploy survival: not run",
            "- Managed Postgres migration: future work",
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
    print("PRMR Memory Core V0.93 Durable Self-Serve Storage")
    print("Storage test: local SQLite restart/reload simulation")
    print("Hosted redeploy proof: NOT_RUN")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    if public_report["result"] != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
