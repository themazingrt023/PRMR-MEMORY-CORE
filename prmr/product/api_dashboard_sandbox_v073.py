"""V0.73 end-to-end API + dashboard sandbox.

This module connects the V0.71 controlled-alpha API surface to a V0.72-shaped
dashboard refresh payload. It is local/deployable alpha evidence only, not a
hosted client API, production portal, billing system, or certification claim.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from prmr.product.client_dashboard_v072 import DASHBOARD_NOTICE
from prmr.product.controlled_alpha_api_v071 import PRMRControlledAlphaAPI


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "v073"

BOUNDARY_V073 = (
    "V0.73 is a local/deployable end-to-end API + dashboard sandbox only. It proves "
    "that local controlled-alpha API activity can refresh dashboard-visible synthetic "
    "state. It is not hosted client access, not a live public demo backend, not "
    "production readiness, not billing, not external validation, not bank approval, "
    "not compliance approval, not legal approval, not external security certification, "
    "and not real-world validation."
)

DEMO_BRIDGE_NOTE = (
    "The public frontend demo bridge remains disabled by design in public frontend mode. "
    "V0.73 proves the connected behavior through a local sandbox flow. A hosted demo/backend "
    "bridge is a later milestone."
)

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "secret",
    "private_internal",
    "key_hash",
    "validation_outcomes",
    "debug",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client api access is live",
    "live hosted api access",
    "live api access granted",
    "billing enabled",
    "self-serve access enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

REQUIRED_BLOCKED_REASONS = {
    "invalid_key",
    "vault_denied",
    "namespace_denied",
    "revoked_key",
    "usage_limit_exceeded",
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def sample_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_v073_001",
            "user_id": "synthetic_user_v073",
            "type": "project_memory",
            "content": "Synthetic client connects PRMR to preserve current project continuity outside the model.",
            "timestamp": "2026-06-23T09:00:00Z",
            "timestamp_index": 1,
        },
        {
            "event_id": "evt_v073_002",
            "user_id": "synthetic_user_v073",
            "type": "support_update",
            "content": "Synthetic follow-up state changed; dashboard should show usage, reports, and memory health.",
            "timestamp": "2026-06-23T09:05:00Z",
            "timestamp_index": 2,
        },
    ]


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def safe_key_panel(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    records = []
    status_counts: Counter[str] = Counter()
    for key_id, record in sorted(api.lifecycle.lifecycle_keys.items()):
        status_counts[record.status] += 1
        records.append(
            {
                "key_id": key_id,
                "client_id": record.client_id,
                "safe_key_preview": record.safe_key_preview,
                "status": record.status,
                "created_at": record.created_at,
                "last_used_at": record.last_used_at,
                "usage_limit_id": record.usage_limit_id,
                "vault_id": record.vault_id,
                "namespace": record.namespace,
                "operator_note": "Safe preview only. Full credential values are not present in dashboard refresh data.",
            }
        )
    return {
        "title": "API key lifecycle",
        "manual_operator_approval_required": True,
        "automatic_key_issuing": False,
        "safe_key_status_counts": dict(sorted(status_counts.items())),
        "records": records,
    }


def request_log_summary(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    rows = [asdict(item) for item in api.api_request_log]
    endpoint_counts: Counter[str] = Counter()
    blocked_reasons: Counter[str] = Counter()
    for row in rows:
        endpoint_counts[row["endpoint"]] += 1
        if row["status"] == "blocked":
            blocked_reasons[row["reason"]] += 1
    return {
        "title": "Request log",
        "rows": rows,
        "endpoint_counts": dict(sorted(endpoint_counts.items())),
        "blocked_reasons": dict(sorted(blocked_reasons.items())),
        "blocked_reason_policy": "Blocked calls are visible as safe denial rows. They do not create successful packets or reports.",
    }


def vault_namespace_panel(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    event_counts: Counter[tuple[str, str]] = Counter()
    packet_counts: Counter[tuple[str, str]] = Counter()
    report_counts: Counter[tuple[str, str]] = Counter()
    for scope, events in api.events.items():
        _client_id, vault_id, namespace = scope.split("::", 2)
        event_counts[(vault_id, namespace)] += len(events)
    for packet in api.packets.values():
        packet_counts[(packet.get("vault_id", ""), packet.get("namespace", ""))] += 1
    for report in api.public_reports.values():
        report_counts[(report.get("vault_id", ""), report.get("namespace", ""))] += 1

    namespaces = []
    for namespace_id, namespace in sorted(api.lifecycle.foundation.namespaces.items()):
        key = (namespace.vault_id, namespace.namespace)
        namespaces.append(
            {
                "namespace_id": namespace_id,
                "client_id": namespace.client_id,
                "vault_id": namespace.vault_id,
                "namespace": namespace.namespace,
                "status": namespace.status,
                "event_count": event_counts[key],
                "packet_count": packet_counts[key],
                "public_report_count": report_counts[key],
            }
        )
    return {
        "title": "Vaults and namespaces",
        "vaults": [asdict(vault) for vault in api.lifecycle.foundation.vaults.values()],
        "namespaces": namespaces,
        "cross_client_boundary": "Dashboard refresh data is scoped to synthetic owner records; blocked requests stay visible only as safe denial rows.",
    }


def reports_panel(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    return {
        "title": "Public-safe report previews",
        "reports": [
            {
                "report_id": report_id,
                "client_id": report.get("client_id"),
                "vault_id": report.get("vault_id"),
                "namespace": report.get("namespace"),
                "packet_id": report.get("packet_id"),
                "public_safe": report.get("public_safe") is True,
                "summary": report.get("summary"),
                "event_count": report.get("event_count"),
            }
            for report_id, report in sorted(api.public_reports.items())
        ],
        "public_private_boundary": "Dashboard previews use public-safe report summaries only.",
    }


def usage_overview(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    api_rows = [asdict(item) for item in api.api_request_log]
    allowed = sum(1 for row in api_rows if row["status"] == "ok")
    blocked = sum(1 for row in api_rows if row["status"] == "blocked")
    return {
        "title": "Usage overview",
        "current_source_version": "0.73",
        "allowed_request_count": allowed,
        "blocked_request_count": blocked,
        "total_request_count": allowed + blocked,
        "foundation_usage_summary": api.lifecycle.foundation.usage_summary(),
    }


def memory_health_panel(api: PRMRControlledAlphaAPI) -> dict[str, Any]:
    rows = [asdict(item) for item in api.api_request_log]
    ok_endpoints = {row["endpoint"] for row in rows if row["status"] == "ok"}
    return {
        "title": "Memory health",
        "status": "local_sandbox_connected",
        "events_received": sum(len(events) for events in api.events.values()),
        "packets_generated": len(api.packets),
        "reconstruction_available": "POST /v1/memory/reconstruct" in ok_endpoints,
        "explanation_available": "POST /v1/explain" in ok_endpoints,
        "least_harm_available": "POST /v1/actions/least-harm" in ok_endpoints,
        "public_report_available": bool(api.public_reports),
        "blocked_request_count": sum(1 for row in rows if row["status"] == "blocked"),
        "health_note": "Connected local sandbox state is visible in dashboard refresh data; this is not production readiness.",
    }


def build_dashboard_refresh_state(api: PRMRControlledAlphaAPI, setup: dict[str, Any]) -> dict[str, Any]:
    client = setup["client"]
    return {
        "version": "0.73",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "API + Dashboard Sandbox Refresh State",
        "result_basis": "local synthetic controlled-alpha API runtime",
        "boundary": BOUNDARY_V073,
        "dashboard_notice": DASHBOARD_NOTICE,
        "demo_bridge_note": DEMO_BRIDGE_NOTE,
        "source_versions": ["0.69", "0.70", "0.71", "0.72", "0.73"],
        "client_overview": {
            "client_id": client.client_id,
            "organisation": client.organisation,
            "status": client.status,
            "created_at": client.created_at,
            "synthetic_only": True,
            "active_vault_count": len(api.lifecycle.foundation.vaults),
            "active_namespace_count": len(api.lifecycle.foundation.namespaces),
            "public_mode_access": "blocked_or_placeholder",
            "local_mode_access": "enabled_for_api_dashboard_sandbox",
        },
        "api_key_panel": safe_key_panel(api),
        "vault_namespace_panel": vault_namespace_panel(api),
        "usage_overview": usage_overview(api),
        "request_log_summary": request_log_summary(api),
        "reports_panel": reports_panel(api),
        "memory_health_panel": memory_health_panel(api),
    }


class PRMRAPIDashboardSandbox:
    """Run the local V0.73 API-to-dashboard proof."""

    def __init__(self) -> None:
        self.api = PRMRControlledAlphaAPI()
        self.setup: dict[str, Any] = {}
        self.flow_results: dict[str, Any] = {}
        self.blocked_results: dict[str, Any] = {}
        self.dashboard_refresh_state: dict[str, Any] = {}
        self.runtime_safe: dict[str, Any] = {}

    def base_payload(self, api_key: str) -> dict[str, Any]:
        return {
            "client_id": self.setup["client"].client_id,
            "vault_id": self.setup["vault"].vault_id,
            "namespace": self.setup["namespace"].namespace,
            "api_key": api_key,
        }

    def setup_synthetic_scope(self) -> str:
        self.setup = self.api.setup_synthetic_client(
            client_id="client_v073_synthetic_alpha",
            vault_id="vault_v073_alpha",
            namespace="default",
            usage_limit_id="limit_v073_alpha",
        )
        raw_key = self.setup["raw_api_key"]
        self.runtime_safe["initial_key_preview"] = self.setup["issue"]["safe_key_preview"]
        return raw_key

    def run_valid_flow(self, raw_key: str) -> None:
        base = self.base_payload(raw_key)
        ingest = self.api.events_ingest({**base, "events": sample_events()})
        packet = self.api.continuity_packet(base)
        packet_id = packet["body"].get("packet_id")
        report_id = packet["body"].get("report_id")
        reconstruct = self.api.memory_reconstruct({**base, "packet_id": packet_id})
        explanation = self.api.explain({**base, "packet_id": packet_id})
        action = self.api.least_harm_action({**base, "packet_id": packet_id})
        report = self.api.get_report(base, str(report_id))
        usage = self.api.get_usage(base)
        self.flow_results = {
            "ingest": ingest,
            "packet": packet,
            "reconstruct": reconstruct,
            "explanation": explanation,
            "least_harm_action": action,
            "report": report,
            "usage": usage,
            "packet_id": packet_id,
            "report_id": report_id,
        }

    def run_blocked_flow(self, raw_key: str) -> None:
        base = self.base_payload(raw_key)
        wrong_key = self.api.events_ingest({**base, "api_key": "prmr_alpha_dev_wrong000000000000000000", "events": [sample_events()[0]]})
        wrong_vault = self.api.continuity_packet({**base, "vault_id": "vault_v073_wrong"})
        wrong_namespace = self.api.continuity_packet({**base, "namespace": "wrong_namespace"})

        revoked_issue = self.api.lifecycle.issue_alpha_key(
            client_id=base["client_id"],
            vault_id=base["vault_id"],
            namespace=base["namespace"],
            usage_limit_id="limit_v073_alpha",
            operator_id="operator_v073_founder",
            approval_reason="issue key for revoked-key blocked proof",
        )
        self.runtime_safe["revoked_key_preview"] = revoked_issue["safe_key_preview"]
        self.api.lifecycle.revoke_key(
            key_id=revoked_issue["key_id"],
            operator_id="operator_v073_founder",
            revoke_reason="revoked for V0.73 blocked request proof",
        )
        revoked = self.api.events_ingest({**base, "api_key": revoked_issue["raw_api_key"], "events": [sample_events()[0]]})

        self.api.lifecycle.create_namespace(base["client_id"], base["vault_id"], namespace="limit_test")
        limit_issue = self.api.lifecycle.issue_alpha_key(
            client_id=base["client_id"],
            vault_id=base["vault_id"],
            namespace="limit_test",
            usage_limit_id="limit_v073_alpha",
            operator_id="operator_v073_founder",
            approval_reason="issue key for usage-limit blocked proof",
        )
        self.runtime_safe["limit_key_preview"] = limit_issue["safe_key_preview"]
        limit_base = {**base, "api_key": limit_issue["raw_api_key"], "namespace": "limit_test"}
        limit_passes = [
            self.api.events_ingest({**limit_base, "events": [sample_events()[0]]}),
            self.api.events_ingest({**limit_base, "events": [sample_events()[0]]}),
            self.api.events_ingest({**limit_base, "events": [sample_events()[0]]}),
        ]
        usage_limit_exceeded = self.api.events_ingest({**limit_base, "events": [sample_events()[0]]})

        self.blocked_results = {
            "wrong_key": wrong_key,
            "wrong_vault": wrong_vault,
            "wrong_namespace": wrong_namespace,
            "revoked_key": revoked,
            "usage_limit_exceeded": usage_limit_exceeded,
            "usage_limit_allowed_setup_calls": limit_passes,
        }

    def run(self) -> dict[str, Any]:
        raw_key = self.setup_synthetic_scope()
        self.run_valid_flow(raw_key)
        self.run_blocked_flow(raw_key)
        self.dashboard_refresh_state = build_dashboard_refresh_state(self.api, self.setup)
        return {
            "api": self.api,
            "setup": self.setup,
            "flow_results": self.flow_results,
            "blocked_results": self.blocked_results,
            "dashboard_refresh_state": self.dashboard_refresh_state,
            "runtime_safe": self.runtime_safe,
        }


def validate_sandbox_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    flow = result["flow_results"]
    blocked = result["blocked_results"]
    dashboard = result["dashboard_refresh_state"]

    add_check(checks, "valid_ingest_updates_sandbox_state", flow["ingest"]["status_code"] == 200 and flow["ingest"]["body"].get("accepted_event_count") == 2, flow["ingest"]["body"])
    add_check(checks, "continuity_packet_generated", flow["packet"]["status_code"] == 200 and bool(flow.get("packet_id")), flow["packet"]["body"])
    add_check(checks, "reconstruction_generated", flow["reconstruct"]["status_code"] == 200 and "reconstructable_state" in flow["reconstruct"]["body"], flow["reconstruct"]["body"])
    add_check(checks, "explanation_generated", flow["explanation"]["status_code"] == 200 and flow["explanation"]["body"]["explanation"]["sensitive_details_included"] is False, flow["explanation"]["body"])
    add_check(checks, "least_harm_action_generated", flow["least_harm_action"]["status_code"] == 200 and flow["least_harm_action"]["body"].get("not_final_decision") is True, flow["least_harm_action"]["body"])
    add_check(checks, "report_generated", flow["report"]["status_code"] == 200 and flow["report"]["body"]["report"].get("public_safe") is True, flow["report"]["body"])
    add_check(checks, "usage_generated", flow["usage"]["status_code"] == 200 and "usage" in flow["usage"]["body"], flow["usage"]["body"])

    add_check(checks, "dashboard_refresh_state_generated", dashboard.get("version") == "0.73", dashboard.get("version"))
    add_check(checks, "dashboard_shows_client_overview", bool(dashboard.get("client_overview", {}).get("client_id")), dashboard.get("client_overview"))
    key_text = json.dumps(dashboard.get("api_key_panel", {}), sort_keys=True)
    add_check(checks, "dashboard_shows_safe_key_preview_only", "safe_key_preview" in key_text and "key_hash" not in key_text and not contains_full_dev_key(key_text), None)
    add_check(checks, "dashboard_shows_vault_namespace_summary", bool(dashboard.get("vault_namespace_panel", {}).get("namespaces")), dashboard.get("vault_namespace_panel"))
    add_check(checks, "dashboard_shows_events_received_count", dashboard.get("memory_health_panel", {}).get("events_received", 0) >= 5, dashboard.get("memory_health_panel"))
    add_check(checks, "dashboard_shows_packet_count", dashboard.get("memory_health_panel", {}).get("packets_generated", 0) >= 1, dashboard.get("memory_health_panel"))
    add_check(checks, "dashboard_shows_reconstruction_available", dashboard.get("memory_health_panel", {}).get("reconstruction_available") is True, dashboard.get("memory_health_panel"))
    add_check(checks, "dashboard_shows_explanation_report_available", dashboard.get("memory_health_panel", {}).get("explanation_available") is True and dashboard.get("memory_health_panel", {}).get("public_report_available") is True, dashboard.get("memory_health_panel"))
    add_check(checks, "dashboard_shows_allowed_request_count", dashboard.get("usage_overview", {}).get("allowed_request_count", 0) >= 10, dashboard.get("usage_overview"))
    add_check(checks, "dashboard_shows_blocked_request_count", dashboard.get("usage_overview", {}).get("blocked_request_count", 0) >= 5, dashboard.get("usage_overview"))
    add_check(checks, "dashboard_shows_request_log_entries", len(dashboard.get("request_log_summary", {}).get("rows", [])) >= 15, len(dashboard.get("request_log_summary", {}).get("rows", [])))
    add_check(checks, "dashboard_shows_report_references", bool(dashboard.get("reports_panel", {}).get("reports")), dashboard.get("reports_panel"))
    add_check(checks, "dashboard_shows_memory_health", dashboard.get("memory_health_panel", {}).get("status") == "local_sandbox_connected", dashboard.get("memory_health_panel"))

    blocked_reasons = set(dashboard.get("request_log_summary", {}).get("blocked_reasons", {}).keys())
    add_check(checks, "blocked_requests_reflected_safely", REQUIRED_BLOCKED_REASONS.issubset(blocked_reasons), sorted(blocked_reasons))
    add_check(checks, "wrong_key_blocked", blocked["wrong_key"]["status_code"] == 401 and blocked["wrong_key"]["body"]["error"]["code"] == "invalid_key", blocked["wrong_key"]["body"])
    add_check(checks, "wrong_vault_blocked", blocked["wrong_vault"]["status_code"] == 403 and blocked["wrong_vault"]["body"]["error"]["code"] == "vault_denied", blocked["wrong_vault"]["body"])
    add_check(checks, "wrong_namespace_blocked", blocked["wrong_namespace"]["status_code"] == 403 and blocked["wrong_namespace"]["body"]["error"]["code"] == "namespace_denied", blocked["wrong_namespace"]["body"])
    add_check(checks, "revoked_key_blocked", blocked["revoked_key"]["status_code"] == 403 and blocked["revoked_key"]["body"]["error"]["code"] == "revoked_key", blocked["revoked_key"]["body"])
    add_check(checks, "usage_limit_exceeded_blocked", blocked["usage_limit_exceeded"]["status_code"] == 429 and blocked["usage_limit_exceeded"]["body"]["error"]["code"] == "usage_limit_exceeded", blocked["usage_limit_exceeded"]["body"])

    add_check(checks, "no_raw_keys_in_dashboard_data", not contains_full_dev_key(dashboard), None)
    add_check(checks, "no_real_client_data_used", dashboard.get("client_overview", {}).get("synthetic_only") is True, dashboard.get("client_overview"))
    add_check(checks, "public_demo_bridge_note_present", DEMO_BRIDGE_NOTE in dashboard.get("demo_bridge_note", ""), dashboard.get("demo_bridge_note"))
    add_check(checks, "no_overclaims_in_dashboard_data", not scan_terms(dashboard, OVERCLAIMS), scan_terms(dashboard, OVERCLAIMS))
    add_check(checks, "no_punitive_terms_in_dashboard_data", not scan_terms(dashboard, PUNITIVE_TERMS), scan_terms(dashboard, PUNITIVE_TERMS))
    return checks


def build_public_report(dashboard: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.73",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "End-to-End API + Dashboard Sandbox",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V073,
        "demo_bridge_note": DEMO_BRIDGE_NOTE,
        "flow_summary": {
            "api_request_to_dashboard_refresh": True,
            "events_received": dashboard["memory_health_panel"]["events_received"],
            "packets_generated": dashboard["memory_health_panel"]["packets_generated"],
            "allowed_request_count": dashboard["usage_overview"]["allowed_request_count"],
            "blocked_request_count": dashboard["usage_overview"]["blocked_request_count"],
            "report_reference_count": len(dashboard["reports_panel"]["reports"]),
            "memory_health_status": dashboard["memory_health_panel"]["status"],
            "blocked_reasons": sorted(dashboard["request_log_summary"]["blocked_reasons"].keys()),
        },
    }


def build_private_report(result: dict[str, Any], checks: list[dict[str, Any]], public_report: dict[str, Any]) -> dict[str, Any]:
    api: PRMRControlledAlphaAPI = result["api"]
    return {
        **public_report,
        "public_safe": False,
        "title": "End-to-End API + Dashboard Sandbox Restricted Synthetic Evidence",
        "checks": checks,
        "runtime_safe": result["runtime_safe"],
        "flow_results": result["flow_results"],
        "blocked_results": result["blocked_results"],
        "dashboard_refresh_state": result["dashboard_refresh_state"],
        "synthetic_clients": {client_id: asdict(client) for client_id, client in api.lifecycle.foundation.clients.items()},
        "synthetic_vaults": {vault_id: asdict(vault) for vault_id, vault in api.lifecycle.foundation.vaults.items()},
        "synthetic_namespaces": {namespace_id: asdict(namespace) for namespace_id, namespace in api.lifecycle.foundation.namespaces.items()},
        "synthetic_packets": api.packets,
        "synthetic_public_reports": api.public_reports,
        "api_request_log": [asdict(item) for item in api.api_request_log],
        "restricted_note": "Restricted synthetic evidence excludes raw API key values; safe previews only.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.73 End-to-End API + Dashboard Sandbox",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V073}",
        "",
        f"Demo bridge note: {DEMO_BRIDGE_NOTE}",
        "",
        "## Flow",
        "",
        "- API request",
        "- event ingested",
        "- continuity packet generated",
        "- state reconstructed",
        "- explanation/report created",
        "- usage/request logs updated",
        "- dashboard data refreshed",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_api_dashboard_sandbox_v073.py", "", BOUNDARY_V073, ""])
    return "\n".join(lines)


def run_sandbox_and_build_reports() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    sandbox = PRMRAPIDashboardSandbox()
    result = sandbox.run()
    checks = validate_sandbox_result(result)
    public_report = build_public_report(result["dashboard_refresh_state"], checks)
    private_report = build_private_report(result, checks, public_report)
    return result, public_report, private_report, checks
