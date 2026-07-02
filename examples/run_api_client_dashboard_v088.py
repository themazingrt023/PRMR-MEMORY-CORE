"""Run the V0.88 approved-client dashboard and key lifecycle smoke."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.client_api_dashboard_v088 import (
    API_BASE_URL,
    BOUNDARY_V088,
    ClientAPIDashboardV088,
)


REPORT_DIR = ROOT / "reports" / "v088"
PUBLIC_REPORT = REPORT_DIR / "public_api_client_dashboard_v088.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_client_dashboard_v088.json"
SMOKE_REPORT = REPORT_DIR / "api_client_dashboard_smoke_v088.json"
SCORECARD = REPORT_DIR / "scorecard_v088.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_credential(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bprmr_alpha_dev_[a-f0-9]{20,}\b",
        r"\bprmr_alpha_local_[a-f0-9]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_.-]{20,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def false_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "open public signup is available",
        "production authentication complete",
        "production billing enabled",
        "compliance approved",
        "legal approved",
        "externally security certified",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def safe_key_response(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": response.get("ok"),
        "status_code": response.get("status_code"),
        "key_id": response.get("key_id") or response.get("new_key_id"),
        "safe_key_preview": response.get("safe_key_preview"),
        "returned_once": response.get("returned_once"),
    }


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    service = ClientAPIDashboardV088()
    client_id = "client_v088_synthetic_alpha"

    approved = service.approve_synthetic_client(client_id=client_id)
    initial_state = service.dashboard_state(client_id=client_id)
    denied_state = service.dashboard_state(client_id="client_v088_unapproved_random")
    add_check(
        checks,
        "approved_client_dashboard_loads",
        approved["ok"] and initial_state["status_code"] == 200,
        {"client_id": client_id},
    )
    add_check(
        checks,
        "unapproved_random_client_blocked",
        denied_state["status_code"] == 403
        and denied_state["error"]["code"] == "approved_client_required",
        {"status_code": denied_state["status_code"], "error_code": denied_state["error"]["code"]},
    )

    created = service.create_api_key(client_id=client_id, label="Development server")
    first_raw_key = str(created.get("raw_api_key") or "")
    add_check(
        checks,
        "create_api_key_works",
        created.get("status_code") == 201 and bool(first_raw_key),
        safe_key_response(created),
    )
    add_check(
        checks,
        "credential_returned_once_in_create_response",
        created.get("returned_once") is True
        and first_raw_key.startswith("prmr_alpha_dev_")
        and not hasattr(service, "_one_time_credentials"),
        {"returned_once": created.get("returned_once"), "service_retains_release_cache": False},
    )

    key_list = service.list_api_keys(client_id=client_id)
    state_after_create = service.dashboard_state(client_id=client_id)
    serialized_list = json.dumps(key_list, sort_keys=True)
    serialized_state = json.dumps(state_after_create, sort_keys=True)
    add_check(
        checks,
        "key_list_uses_safe_previews_only",
        key_list["safe_previews_only"]
        and first_raw_key not in serialized_list
        and all("safe_key_preview" in row for row in key_list["keys"]),
        {"key_count": len(key_list["keys"])},
    )
    add_check(
        checks,
        "dashboard_state_contains_no_credential_value",
        first_raw_key not in serialized_state
        and state_after_create["dashboard"]["credential_values_exposed"] is False,
        None,
    )

    validation = service.validate_key(client_id=client_id, raw_api_key=first_raw_key, operation="events_ingest")
    service.validate_key(client_id=client_id, raw_api_key=first_raw_key, operation="continuity_packet")
    service.validate_key(client_id=client_id, raw_api_key=first_raw_key, operation="memory_reconstruct")
    report = service.register_public_report(client_id=client_id, report_id="report_v088_synthetic_001")
    populated_state = service.dashboard_state(client_id=client_id)["dashboard"]
    add_check(checks, "created_key_validates", validation["allowed"] is True, validation)
    add_check(
        checks,
        "usage_summary_visible",
        populated_state["usage_summary"]["allowed_request_count"] >= 3
        and "limits" in populated_state["usage_summary"],
        populated_state["usage_summary"],
    )
    add_check(
        checks,
        "request_logs_visible",
        len(populated_state["request_logs"]) >= 3
        and all("public_safe_message" in row for row in populated_state["request_logs"]),
        {"row_count": len(populated_state["request_logs"])},
    )
    add_check(
        checks,
        "report_references_visible",
        report["ok"] and populated_state["continuity_reports"][0]["report_id"] == "report_v088_synthetic_001",
        populated_state["continuity_reports"],
    )
    add_check(
        checks,
        "memory_health_visible",
        populated_state["memory_health"]["events_received"] == 1
        and populated_state["memory_health"]["packets_generated"] == 1
        and populated_state["memory_health"]["reconstruction_available"] is True,
        populated_state["memory_health"],
    )

    first_key_id = str(created["key_id"])
    rotated = service.rotate_api_key(client_id=client_id, key_id=first_key_id)
    replacement_raw_key = str(rotated.get("raw_api_key") or "")
    old_key_after_rotate = service.validate_key(
        client_id=client_id,
        raw_api_key=first_raw_key,
        operation="events_ingest",
    )
    replacement_validation = service.validate_key(
        client_id=client_id,
        raw_api_key=replacement_raw_key,
        operation="events_ingest",
    )
    add_check(
        checks,
        "rotate_returns_one_replacement",
        rotated.get("ok") is True
        and rotated.get("returned_once") is True
        and bool(replacement_raw_key),
        safe_key_response(rotated),
    )
    add_check(
        checks,
        "old_rotated_key_is_blocked",
        old_key_after_rotate["allowed"] is False and old_key_after_rotate["reason"] == "rotated_key",
        old_key_after_rotate,
    )
    add_check(
        checks,
        "replacement_key_validates",
        replacement_validation["allowed"] is True,
        replacement_validation,
    )

    replacement_key_id = str(rotated["new_key_id"])
    revoke = service.revoke_api_key(client_id=client_id, key_id=replacement_key_id)
    revoked_validation = service.validate_key(
        client_id=client_id,
        raw_api_key=replacement_raw_key,
        operation="events_ingest",
    )
    add_check(checks, "revoke_works", revoke.get("ok") is True and revoke.get("status") == "revoked", revoke)
    add_check(
        checks,
        "revoked_key_is_blocked",
        revoked_validation["allowed"] is False and revoked_validation["reason"] == "revoked_key",
        revoked_validation,
    )

    final_state = service.dashboard_state(client_id=client_id)["dashboard"]
    public_evidence = {
        "approved_client": approved["profile"],
        "dashboard_sections": [
            "Overview",
            "API Keys",
            "Vaults & Namespaces",
            "Usage",
            "Request Logs",
            "Continuity Reports",
            "Memory Health",
            "Quickstart",
        ],
        "key_creation": safe_key_response(created),
        "key_rotation": safe_key_response(rotated),
        "key_statuses": [
            {
                "key_id": key["key_id"],
                "label": key["label"],
                "safe_key_preview": key["safe_key_preview"],
                "status": key["status"],
            }
            for key in final_state["api_keys"]
        ],
        "usage": {
            "allowed_request_count": final_state["usage_summary"]["allowed_request_count"],
            "blocked_request_count": final_state["usage_summary"]["blocked_request_count"],
            "limits": final_state["usage_summary"]["limits"],
        },
        "request_log_count": len(final_state["request_logs"]),
        "report_count": len(final_state["continuity_reports"]),
        "memory_health": final_state["memory_health"],
        "quickstart": final_state["quickstart"],
        "credential_value_exposed": False,
        "public_dashboard_locked_without_controlled_auth": True,
    }
    add_check(
        checks,
        "quickstart_contains_required_environment",
        final_state["quickstart"]["environment"]
        == [
            f"PRMR_API_BASE_URL={API_BASE_URL}",
            "PRMR_API_KEY=<YOUR_PRMR_KEY>",
            "PRMR_CLIENT_ID=<CLIENT_ID>",
            "PRMR_VAULT_ID=<VAULT_ID>",
            "PRMR_NAMESPACE=default",
        ],
        None,
    )

    passed_before_hygiene = sum(1 for check in checks if check["passed"])
    provisional_public = {
        "version": "0.88",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "API Client Dashboard + Key Creation MVP",
        "result": "PASS" if passed_before_hygiene == len(checks) else "NEEDS_WORK",
        "checks_passed": passed_before_hygiene,
        "checks_total": len(checks),
        "public_safe": True,
        "truth_label": "approved-client dashboard and key-management MVP using controlled synthetic evidence only",
        "boundary": BOUNDARY_V088,
        "evidence": public_evidence,
    }
    add_check(checks, "public_report_contains_no_credentials", not contains_credential(provisional_public), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(provisional_public), false_claim_hits(provisional_public))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    public_report = {
        **provisional_public,
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
    }
    private_report = {
        **public_report,
        "public_safe": False,
        "title": "API Client Dashboard Private Synthetic Integrity Trace",
        "checks": checks,
        "key_release_log": service.key_release_log,
        "stored_key_records": [
            {
                "key_id": record.key_id,
                "client_id": record.client_id,
                "status": record.status,
                "safe_key_preview": record.safe_key_preview,
                "hash_stored": bool(record.key_hash),
                "credential_value_stored": False,
            }
            for record in service.lifecycle.lifecycle_keys.values()
        ],
        "restricted_note": "This trace records lifecycle outcomes but intentionally excludes generated credential values.",
    }
    smoke_report = {
        "version": "0.88",
        "result": public_report["result"],
        "public_safe": True,
        "boundary": BOUNDARY_V088,
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
        "summary": {
            "approved_client_dashboard": "allowed",
            "unapproved_client_dashboard": "blocked",
            "key_create": "copy_once",
            "rotate": "old_blocked_replacement_copy_once",
            "revoke": "revoked_key_blocked",
            "credential_value_in_reports": False,
        },
    }
    return public_report, private_report, smoke_report, checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.88 API Client Dashboard + Key Creation MVP",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V088}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- `python examples/run_api_client_dashboard_v088.py`",
            "- `python examples/audit_v088_api_client_dashboard.py`",
            "- `cd frontend && npm run typecheck`",
            "- `cd frontend && npm run build`",
            "",
            "## Remaining gaps",
            "",
            "- Durable hosted key/dashboard persistence.",
            "- Production identity and session authentication.",
            "- Whop payment-to-manual-approval workflow.",
            "- Billing automation and open self-serve signup.",
            "- Real external alpha client evidence.",
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

    print("PRMR Memory Core V0.88 API Client Dashboard + Key Creation MVP")
    print("Approved client dashboard: allowed")
    print("Unapproved client dashboard: blocked")
    print("Key creation: copy-once response; safe preview retained")
    print("Rotation: old key blocked; replacement returned once")
    print("Revocation: revoked key blocked")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

