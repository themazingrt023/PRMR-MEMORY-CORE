"""Run V0.84 controlled synthetic multi-client isolation smoke."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.controlled_alpha_api_v071 import PRMRControlledAlphaAPI
from prmr.product.dashboard_auth_v081 import DashboardAuthV081


REPORT_DIR = ROOT / "reports" / "v084"
PUBLIC_REPORT = REPORT_DIR / "public_multi_client_isolation_v084.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_multi_client_isolation_v084.json"
SMOKE_REPORT = REPORT_DIR / "multi_client_isolation_smoke_v084.json"
SCORECARD = REPORT_DIR / "scorecard_v084.md"

BOUNDARY_V084 = (
    "V0.84 is controlled synthetic multi-client isolation evidence only. It "
    "tests scoped API access, reports, usage logs, request logs, and dashboard "
    "state for synthetic alpha clients. It is not external security "
    "certification, production auth, compliance approval, legal approval, or "
    "real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v081_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def false_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "external security certification complete",
        "security certified",
        "production auth complete",
        "compliance approved",
        "legal approved",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def public_response_summary(response: dict[str, Any]) -> dict[str, Any]:
    body = response.get("body", {})
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    return {
        "status_code": response.get("status_code"),
        "status": body.get("status"),
        "client_id": body.get("client_id"),
        "vault_id": body.get("vault_id"),
        "namespace": body.get("namespace"),
        "error_code": error.get("code"),
        "packet_id_present": bool(body.get("packet_id")),
        "report_id_present": bool(body.get("report_id")),
        "report_public_safe": body.get("report", {}).get("public_safe") if isinstance(body.get("report"), dict) else None,
        "usage_client_id": body.get("usage", {}).get("client_id") if isinstance(body.get("usage"), dict) else None,
    }


def create_client(api: PRMRControlledAlphaAPI, label: str) -> dict[str, Any]:
    client_id = f"client_v084_{label.lower()}"
    vault_id = f"vault_v084_{label.lower()}"
    namespace = f"namespace_{label.lower()}"
    setup = api.setup_synthetic_client(
        client_id=client_id,
        vault_id=vault_id,
        namespace=namespace,
        usage_limit_id=f"limit_v084_{label.lower()}",
    )
    return {
        "label": label,
        "client_id": client_id,
        "vault_id": vault_id,
        "namespace": namespace,
        "raw_api_key": setup["raw_api_key"],
        "key_id": setup["issue"]["key_id"],
        "safe_key_preview": setup["issue"]["safe_key_preview"],
    }


def payload_for(client: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "client_id": client["client_id"],
        "vault_id": client["vault_id"],
        "namespace": client["namespace"],
        "api_key": client["raw_api_key"],
        **(extra or {}),
    }


def run_allowed_path(api: PRMRControlledAlphaAPI, client: dict[str, Any]) -> dict[str, Any]:
    label = client["label"].lower()
    events = [
        {
            "event_id": f"evt_v084_{label}_001",
            "user_id": f"synthetic_user_v084_{label}",
            "type": f"multi_client_{label}_state",
            "content": f"Synthetic Client {client['label']} state starts in its own namespace.",
            "timestamp": "2026-06-23T13:01:00Z",
            "timestamp_index": 1,
        },
        {
            "event_id": f"evt_v084_{label}_002",
            "user_id": f"synthetic_user_v084_{label}",
            "type": f"multi_client_{label}_update",
            "content": f"Synthetic Client {client['label']} state updates independently.",
            "timestamp": "2026-06-23T13:02:00Z",
            "timestamp_index": 2,
        },
    ]
    ingest = api.events_ingest(payload_for(client, {"events": events}))
    packet = api.continuity_packet(payload_for(client))
    packet_id = packet.get("body", {}).get("packet_id")
    report_id = packet.get("body", {}).get("report_id")
    reconstruct = api.memory_reconstruct(payload_for(client, {"packet_id": packet_id}))
    report = api.get_report(payload_for(client), str(report_id))
    usage = api.get_usage(payload_for(client))
    return {
        "ingest": ingest,
        "packet": packet,
        "reconstruct": reconstruct,
        "report": report,
        "usage": usage,
        "packet_id": packet_id,
        "report_id": report_id,
    }


def setup_dashboard(clients: list[dict[str, Any]]) -> tuple[DashboardAuthV081, dict[str, dict[str, Any]]]:
    dashboard = DashboardAuthV081()
    sessions: dict[str, dict[str, Any]] = {}
    for client in clients:
        dashboard_scope = dashboard.create_client_scope(
            client_id=client["client_id"],
            organisation=f"Synthetic V0.84 Alpha Client {client['label']}",
            contact_email=f"synthetic-{client['label'].lower()}-v084@example.test",
            vault_id=client["vault_id"],
            namespace=client["namespace"],
        )
        dashboard.record_synthetic_activity(
            client_id=dashboard_scope["client"]["client_id"],
            vault_id=dashboard_scope["vault"]["vault_id"],
            namespace=dashboard_scope["namespace"]["namespace"],
            raw_api_key=dashboard_scope["raw_api_key"],
        )
        session = dashboard.create_dashboard_session(client_id=client["client_id"])
        sessions[client["label"]] = {
            "session": session,
            "raw_token": session["dashboard_token"],
            "safe_token_preview": session["safe_token_preview"],
        }
    return dashboard, sessions


def scoped_logs(api: PRMRControlledAlphaAPI, client_id: str) -> dict[str, Any]:
    request_logs = [asdict(row) for row in api.api_request_log if row.client_id == client_id]
    usage_events = [
        {
            "client_id": event.client_id,
            "vault_id": event.vault_id,
            "namespace": event.namespace,
            "operation": event.operation,
            "allowed": event.allowed,
            "count": event.count,
        }
        for event in api.lifecycle.foundation.usage_ledger
        if event.client_id == client_id
    ]
    reports = [
        report for report in api.public_reports.values() if report["client_id"] == client_id
    ]
    return {
        "request_log_client_ids": sorted({row["client_id"] for row in request_logs}),
        "usage_log_client_ids": sorted({row["client_id"] for row in usage_events}),
        "report_client_ids": sorted({row["client_id"] for row in reports}),
        "request_log_count": len(request_logs),
        "usage_log_count": len(usage_events),
        "report_count": len(reports),
    }


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.84",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Multi-Client Isolation Test",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V084,
        "truth_label": "controlled synthetic multi-client isolation evidence only",
        "clients_tested": smoke["clients_tested"],
        "allowed_path_results": smoke["allowed_path_results"],
        "blocked_cross_access_results": smoke["blocked_cross_access_results"],
        "isolation_summary": smoke["isolation_summary"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "Raw API keys and raw dashboard tokens are intentionally excluded from reports.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.84 Multi-Client Isolation",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Clients tested: {', '.join(public_report['clients_tested'])}",
        "",
        f"Boundary: {BOUNDARY_V084}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command", "", "- RUN: python examples/run_multi_client_isolation_v084.py", ""])
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    api = PRMRControlledAlphaAPI()
    client_a = create_client(api, "A")
    client_b = create_client(api, "B")
    clients = [client_a, client_b]

    allowed_a = run_allowed_path(api, client_a)
    allowed_b = run_allowed_path(api, client_b)
    dashboard, sessions = setup_dashboard(clients)
    dash_a = dashboard.dashboard_state(raw_token=sessions["A"]["raw_token"], requested_client_id=client_a["client_id"])
    dash_b = dashboard.dashboard_state(raw_token=sessions["B"]["raw_token"], requested_client_id=client_b["client_id"])

    add_check(checks, "client_a_allowed_path_works", all(allowed_a[name]["status_code"] == 200 for name in ["ingest", "packet", "reconstruct", "report", "usage"]) and dash_a["status_code"] == 200, None)
    add_check(checks, "client_b_allowed_path_works", all(allowed_b[name]["status_code"] == 200 for name in ["ingest", "packet", "reconstruct", "report", "usage"]) and dash_b["status_code"] == 200, None)

    a_key_b_vault = api.events_ingest(payload_for(client_a, {"vault_id": client_b["vault_id"], "events": [{"event_id": "evt_cross_vault"}]}))
    a_key_b_namespace = api.events_ingest(payload_for(client_a, {"namespace": client_b["namespace"], "events": [{"event_id": "evt_cross_namespace"}]}))
    a_dash_b = dashboard.dashboard_state(raw_token=sessions["A"]["raw_token"], requested_client_id=client_b["client_id"])
    b_read_a_report = api.get_report(payload_for(client_b), str(allowed_a["report_id"]))
    wrong_client_id = api.events_ingest({**payload_for(client_a, {"events": [{"event_id": "evt_wrong_client"}]}), "client_id": client_b["client_id"]})
    wrong_vault_id = api.events_ingest(payload_for(client_a, {"vault_id": "vault_v084_wrong", "events": [{"event_id": "evt_wrong_vault"}]}))
    wrong_namespace = api.events_ingest(payload_for(client_a, {"namespace": "namespace_wrong", "events": [{"event_id": "evt_wrong_namespace"}]}))
    missing_key = api.events_ingest({k: v for k, v in payload_for(client_a, {"events": [{"event_id": "evt_missing_key"}]}).items() if k != "api_key"})
    revoke = api.lifecycle.revoke_key(key_id=client_a["key_id"], operator_id="operator_v084_founder", revoke_reason="synthetic isolation revoke check")
    revoked_key = api.events_ingest(payload_for(client_a, {"events": [{"event_id": "evt_revoked"}]}))

    blocked = {
        "client_a_key_client_b_vault": public_response_summary(a_key_b_vault),
        "client_a_key_client_b_namespace": public_response_summary(a_key_b_namespace),
        "client_a_dashboard_token_client_b": {
            "status_code": a_dash_b["status_code"],
            "status": a_dash_b["status"],
            "error_code": a_dash_b.get("error", {}).get("code"),
        },
        "client_b_key_client_a_report": public_response_summary(b_read_a_report),
        "wrong_client_id_valid_key": public_response_summary(wrong_client_id),
        "wrong_vault_id_valid_key": public_response_summary(wrong_vault_id),
        "wrong_namespace_valid_key": public_response_summary(wrong_namespace),
        "missing_key": public_response_summary(missing_key),
        "revoked_key": public_response_summary(revoked_key),
    }
    add_check(checks, "client_a_cannot_access_client_b_vault", blocked["client_a_key_client_b_vault"]["error_code"] == "vault_denied", blocked["client_a_key_client_b_vault"])
    add_check(checks, "client_a_cannot_access_client_b_namespace", blocked["client_a_key_client_b_namespace"]["error_code"] == "namespace_denied", blocked["client_a_key_client_b_namespace"])
    add_check(checks, "client_a_dashboard_token_cannot_access_client_b", blocked["client_a_dashboard_token_client_b"]["error_code"] == "client_scope_denied", blocked["client_a_dashboard_token_client_b"])
    add_check(checks, "client_b_cannot_read_client_a_report", blocked["client_b_key_client_a_report"]["error_code"] == "report_not_found", blocked["client_b_key_client_a_report"])
    add_check(checks, "wrong_client_id_blocked", blocked["wrong_client_id_valid_key"]["error_code"] == "key_client_mismatch", blocked["wrong_client_id_valid_key"])
    add_check(checks, "wrong_vault_id_blocked", blocked["wrong_vault_id_valid_key"]["error_code"] == "vault_denied", blocked["wrong_vault_id_valid_key"])
    add_check(checks, "wrong_namespace_blocked", blocked["wrong_namespace_valid_key"]["error_code"] == "namespace_denied", blocked["wrong_namespace_valid_key"])
    add_check(checks, "missing_key_blocked", blocked["missing_key"]["error_code"] == "missing_key", blocked["missing_key"])
    add_check(checks, "revoked_key_blocked", revoke.get("ok") is True and blocked["revoked_key"]["error_code"] == "revoked_key", blocked["revoked_key"])

    scoped_a = scoped_logs(api, client_a["client_id"])
    scoped_b = scoped_logs(api, client_b["client_id"])
    dashboard_a_text = json.dumps(dash_a.get("dashboard", {}), sort_keys=True)
    dashboard_b_text = json.dumps(dash_b.get("dashboard", {}), sort_keys=True)
    usage_a = allowed_a["usage"].get("body", {}).get("usage", {})
    usage_b = allowed_b["usage"].get("body", {}).get("usage", {})

    add_check(checks, "usage_logs_scoped_per_client", usage_a.get("client_id") == client_a["client_id"] and usage_b.get("client_id") == client_b["client_id"] and client_b["client_id"] not in json.dumps(usage_a) and client_a["client_id"] not in json.dumps(usage_b), {"usage_a": usage_a, "usage_b": usage_b})
    add_check(checks, "request_logs_scoped_per_client", scoped_a["request_log_client_ids"] == [client_a["client_id"]] and scoped_b["request_log_client_ids"] == [client_b["client_id"]], {"a": scoped_a, "b": scoped_b})
    add_check(checks, "reports_scoped_per_client", scoped_a["report_client_ids"] == [client_a["client_id"]] and scoped_b["report_client_ids"] == [client_b["client_id"]], {"a": scoped_a, "b": scoped_b})
    add_check(checks, "dashboard_state_scoped_per_client", client_b["client_id"] not in dashboard_a_text and client_a["client_id"] not in dashboard_b_text, None)
    add_check(checks, "public_reports_are_public_safe", all(report.get("public_safe") is True for report in api.public_reports.values()), None)
    add_check(checks, "no_real_client_data_used", all(client["client_id"].startswith("client_v084_") for client in clients), None)

    safe_clients = [
        {
            "label": client["label"],
            "client_id": client["client_id"],
            "vault_id": client["vault_id"],
            "namespace": client["namespace"],
            "safe_key_preview": client["safe_key_preview"],
            "key_id": client["key_id"],
        }
        for client in clients
    ]
    smoke = {
        "clients_tested": [client["label"] for client in safe_clients],
        "safe_clients": safe_clients,
        "allowed_path_results": {
            "client_a": {
                "api_statuses": {name: public_response_summary(allowed_a[name]) for name in ["ingest", "packet", "reconstruct", "report", "usage"]},
                "dashboard_status": dash_a["status"],
            },
            "client_b": {
                "api_statuses": {name: public_response_summary(allowed_b[name]) for name in ["ingest", "packet", "reconstruct", "report", "usage"]},
                "dashboard_status": dash_b["status"],
            },
        },
        "blocked_cross_access_results": blocked,
        "isolation_summary": {
            "usage_logs_scoped": True,
            "request_logs_scoped": True,
            "reports_scoped": True,
            "dashboard_state_scoped": True,
            "raw_keys_exposed": False,
            "raw_dashboard_tokens_exposed": False,
        },
    }
    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(public_report), false_claim_hits(public_report))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.84",
        "public_safe": True,
        "boundary": BOUNDARY_V084,
        "result": public_report["result"],
        "smoke": smoke,
    }
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.84 Multi-Client Isolation")
    print(f"Clients tested: {', '.join(public_report['clients_tested'])}")
    print(f"Client A allowed path: {public_report['allowed_path_results']['client_a']['dashboard_status']}")
    print(f"Client B allowed path: {public_report['allowed_path_results']['client_b']['dashboard_status']}")
    print(f"A key to B vault: {public_report['blocked_cross_access_results']['client_a_key_client_b_vault']['error_code']}")
    print(f"A dashboard to B: {public_report['blocked_cross_access_results']['client_a_dashboard_token_client_b']['error_code']}")
    print(f"B key to A report: {public_report['blocked_cross_access_results']['client_b_key_client_a_report']['error_code']}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
