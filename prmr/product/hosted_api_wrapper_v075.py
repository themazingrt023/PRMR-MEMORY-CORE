"""V0.75 local/deployable hosted-backend API wrapper.

This is a server-shaped local router around the V0.71 controlled-alpha API and
V0.74 SQLite storage. It is not live hosted client access until separately
deployed and smoke-tested.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from prmr.product.api_config_v075 import PRMRAPIConfig, load_api_config
from prmr.product.controlled_alpha_api_v071 import PRMRControlledAlphaAPI
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now
from prmr.product.persistent_storage_v074 import PRMRPersistentStorage, write_json


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "v075"

BOUNDARY_V075 = (
    "V0.75 is a local/deployable backend API wrapper only. It wraps PRMR local "
    "controlled-alpha routes and SQLite persistence in server-shaped handlers. It is "
    "not live hosted client access until deployed and smoke-tested, not production "
    "readiness, not billing, not external validation, not bank approval, not "
    "compliance approval, not legal approval, not external security certification, "
    "and not real-world validation."
)

ROUTES = {
    "GET /health": "health",
    "POST /v1/events/ingest": "events_ingest",
    "POST /v1/continuity/packet": "continuity_packet",
    "POST /v1/memory/reconstruct": "memory_reconstruct",
    "POST /v1/explain": "explain",
    "POST /v1/actions/least-harm": "least_harm_action",
    "GET /v1/reports/{report_id}": "get_report",
    "GET /v1/usage": "get_usage",
    "GET /v1/dashboard/state": "get_dashboard_state",
}

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
    "key_hash",
    "validation_outcomes",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client access is live",
    "live api access granted",
    "billing enabled",
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


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def sample_event(index: int = 1) -> dict[str, Any]:
    return {
        "event_id": f"evt_v075_{index:03d}",
        "user_id": "synthetic_user_v075",
        "type": "api_wrapper_memory",
        "content": f"Synthetic V0.75 API wrapper event {index} updates continuity state for dashboard persistence.",
        "timestamp": f"2026-06-23T11:{index:02d}:00Z",
        "timestamp_index": index,
    }


class PRMRHostedAPIWrapper:
    """HTTP-shaped local route wrapper."""

    def __init__(self, config: PRMRAPIConfig | None = None, reset_storage: bool = False) -> None:
        self.config = config or load_api_config()
        self.api = PRMRControlledAlphaAPI()
        self.storage = PRMRPersistentStorage(self.config.storage_path, reset=reset_storage)
        self.runtime: dict[str, Any] = {}

    def response(self, status_code: int, body: dict[str, Any]) -> dict[str, Any]:
        return {"status_code": status_code, "body": {"public_safe": True, "boundary": BOUNDARY_V075, **body}}

    def health(self) -> dict[str, Any]:
        return self.response(
            200,
            {
                "status": "ok",
                "api_mode": self.config.api_mode,
                "synthetic_only": self.config.synthetic_only,
                "storage_path": str(self.config.storage_path),
                "routes": sorted(ROUTES.keys()),
            },
        )

    def setup_synthetic_client(self) -> dict[str, Any]:
        setup = self.api.setup_synthetic_client(
            client_id="client_v075_synthetic_alpha",
            vault_id="vault_v075_alpha",
            namespace="default",
            usage_limit_id="limit_v075_alpha",
        )
        self.runtime["setup"] = {
            "client_id": setup["client"].client_id,
            "vault_id": setup["vault"].vault_id,
            "namespace": setup["namespace"].namespace,
            "safe_key_preview": setup["issue"]["safe_key_preview"],
        }
        self.persist_identity_state()
        return setup

    def auth_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "client_id": payload.get("client_id"),
            "vault_id": payload.get("vault_id"),
            "namespace": payload.get("namespace"),
            "api_key": payload.get("api_key") or payload.get("authorization"),
        }

    def persist_identity_state(self) -> None:
        for client in self.api.lifecycle.foundation.clients.values():
            self.storage.create_client_record(client.client_id, client.organisation, client.status, client.created_at)
        for vault in self.api.lifecycle.foundation.vaults.values():
            self.storage.create_vault_record(vault.vault_id, vault.client_id, vault.status, vault.created_at)
        for namespace in self.api.lifecycle.foundation.namespaces.values():
            self.storage.create_namespace_record(namespace.client_id, namespace.vault_id, namespace.namespace, namespace.status, namespace.created_at)
        for record in self.api.lifecycle.lifecycle_keys.values():
            self.storage.store_api_key_record(
                {
                    "key_id": record.key_id,
                    "client_id": record.client_id,
                    "safe_key_preview": record.safe_key_preview,
                    "key_hash": record.key_hash,
                    "status": record.status,
                    "created_at": record.created_at,
                    "last_used_at": record.last_used_at,
                    "usage_limit_id": record.usage_limit_id,
                }
            )

    def persist_events(self) -> None:
        for scope, events in self.api.events.items():
            client_id, vault_id, namespace = scope.split("::", 2)
            for index, event in enumerate(events, start=1):
                self.storage.store_memory_event(
                    {
                        "event_id": f"{client_id}__{vault_id}__{namespace}__{index:03d}__{event['event_id']}",
                        "client_id": client_id,
                        "vault_id": vault_id,
                        "namespace": namespace,
                        "entity_id": event.get("user_id", "synthetic_entity"),
                        "event_type": event.get("type", "memory_event"),
                        "content_summary": event.get("content", "")[:500],
                        "timestamp": event.get("timestamp") or utc_now(),
                        "synthetic_only": True,
                    }
                )

    def persist_packets_reports(self) -> None:
        for packet in self.api.packets.values():
            self.storage.store_continuity_packet(
                {
                    "packet_id": packet["packet_id"],
                    "client_id": packet["client_id"],
                    "vault_id": packet["vault_id"],
                    "namespace": packet["namespace"],
                    "source_event_count": packet["event_count"],
                    "summary": packet["summary"],
                    "created_at": utc_now(),
                    "public_safe": packet.get("public_safe", True),
                }
            )
        for report_id, report in self.api.public_reports.items():
            self.storage.store_report_record(
                {
                    "report_id": report_id,
                    "packet_id": report["packet_id"],
                    "client_id": report["client_id"],
                    "vault_id": report["vault_id"],
                    "namespace": report["namespace"],
                    "report_type": "public_safe_continuity_report",
                    "public_safe_summary": report["summary"],
                    "created_at": utc_now(),
                }
            )

    def persist_logs(self) -> None:
        for index, usage in enumerate(self.api.lifecycle.foundation.usage_ledger, start=1):
            self.storage.store_usage_log(
                {
                    "log_id": f"usage_v075_{index:03d}",
                    "client_id": usage.client_id,
                    "vault_id": usage.vault_id,
                    "namespace": usage.namespace,
                    "operation": usage.operation,
                    "status": "allowed" if usage.allowed else "blocked",
                    "reason": "allowed" if usage.allowed else "blocked",
                    "count": usage.count,
                    "timestamp": usage.timestamp,
                }
            )
        for index, request in enumerate(self.api.api_request_log, start=1):
            self.storage.store_request_log(
                {
                    "log_id": f"request_v075_{index:03d}",
                    "client_id": request.client_id,
                    "vault_id": request.vault_id,
                    "namespace": request.namespace,
                    "operation": request.endpoint,
                    "status": "allowed" if request.status == "ok" else "blocked",
                    "reason": request.reason,
                    "public_safe_message": request.public_safe_message,
                    "timestamp": request.timestamp,
                }
            )

    def persist_dashboard_refresh(self, client_id: str, vault_id: str, namespace: str) -> None:
        state = self.build_dashboard_state(client_id, vault_id, namespace)
        self.storage.store_dashboard_refresh(
            {
                "refresh_id": "refresh_v075_latest",
                "client_id": client_id,
                "vault_id": vault_id,
                "namespace": namespace,
                "allowed_request_count": state["usage_overview"]["allowed_request_count"],
                "blocked_request_count": state["usage_overview"]["blocked_request_count"],
                "events_received": state["memory_health_panel"]["events_received"],
                "packets_generated": state["memory_health_panel"]["packets_generated"],
                "reports_visible": len(state["reports_panel"]["reports"]),
                "memory_health": state["memory_health_panel"]["status"],
                "created_at": utc_now(),
            }
        )

    def sync_storage(self, client_id: str | None = None, vault_id: str | None = None, namespace: str | None = None) -> None:
        self.persist_identity_state()
        self.persist_events()
        self.persist_packets_reports()
        self.persist_logs()
        if client_id and vault_id and namespace:
            self.persist_dashboard_refresh(client_id, vault_id, namespace)

    def events_ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.events_ingest(payload)
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def continuity_packet(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.continuity_packet(payload)
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def memory_reconstruct(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.memory_reconstruct(payload)
        if response["status_code"] == 200:
            body = response["body"]
            self.storage.store_reconstruction_record(
                {
                    "packet_id": body["packet_id"],
                    "client_id": body["client_id"],
                    "vault_id": body["vault_id"],
                    "namespace": body["namespace"],
                    "current_state": body["reconstructable_state"]["current_state"],
                    "created_at": utc_now(),
                }
            )
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def explain(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.explain(payload)
        if response["status_code"] == 200:
            body = response["body"]
            self.storage.store_explanation_record(
                {
                    "packet_id": body["packet_id"],
                    "client_id": body["client_id"],
                    "vault_id": body["vault_id"],
                    "namespace": body["namespace"],
                    "explanation_summary": body["explanation"]["summary"],
                    "action_label": "pending_action_route",
                    "not_final_decision": True,
                    "created_at": utc_now(),
                }
            )
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def least_harm_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.least_harm_action(payload)
        if response["status_code"] == 200:
            body = response["body"]
            self.storage.store_explanation_record(
                {
                    "packet_id": body["packet_id"],
                    "client_id": body["client_id"],
                    "vault_id": body["vault_id"],
                    "namespace": body["namespace"],
                    "explanation_summary": body["summary"],
                    "action_label": body["recommended_action"],
                    "not_final_decision": body["not_final_decision"],
                    "created_at": utc_now(),
                }
            )
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def get_report(self, payload: dict[str, Any], report_id: str) -> dict[str, Any]:
        response = self.api.get_report(payload, report_id)
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def get_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.api.get_usage(payload)
        context = self.auth_payload(payload)
        self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
        return response

    def get_dashboard_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.auth_payload(payload)
        decision = self.api.lifecycle.validate_key(
            client_id=str(context.get("client_id") or ""),
            raw_api_key=context.get("api_key"),
            vault_id=str(context.get("vault_id") or ""),
            namespace=str(context.get("namespace") or ""),
            operation="report_read",
            count=1,
        )
        if not decision.allowed:
            self.api.public_error(decision, "GET /v1/dashboard/state", context)
            self.sync_storage(context.get("client_id"), context.get("vault_id"), context.get("namespace"))
            return self.response(
                decision.status_code,
                {
                    "status": "error",
                    "error": {"code": decision.reason, "message": decision.public_safe_message},
                },
            )
        self.api.public_ok("GET /v1/dashboard/state", context, {"dashboard_state_read": True})
        self.sync_storage(context["client_id"], context["vault_id"], context["namespace"])
        return self.response(200, {"status": "ok", "dashboard": self.build_dashboard_state(context["client_id"], context["vault_id"], context["namespace"])})

    def build_dashboard_state(self, client_id: str, vault_id: str, namespace: str) -> dict[str, Any]:
        clients = [client for client in self.storage.export_storage_snapshot(public_safe=True)["clients"] if client["client_id"] == client_id]
        vaults = [vault for vault in self.storage.export_storage_snapshot(public_safe=True)["vaults"] if vault["client_id"] == client_id]
        namespaces = self.storage.query_all("SELECT * FROM namespaces WHERE client_id = ? AND vault_id = ? ORDER BY namespace", (client_id, vault_id))
        key_records = [
            record
            for record in self.storage.export_storage_snapshot(public_safe=True)["api_key_records"]
            if record["client_id"] == client_id
        ]
        request_logs = self.storage.list_request_logs(client_id)
        usage_logs = self.storage.list_usage_logs(client_id)
        reports = self.storage.query_all("SELECT * FROM reports WHERE client_id = ? AND vault_id = ? ORDER BY created_at, report_id", (client_id, vault_id))
        events_received = len(self.storage.list_memory_events(client_id, vault_id, namespace))
        all_events = self.storage.query_all("SELECT * FROM memory_events WHERE client_id = ? AND vault_id = ?", (client_id, vault_id))
        packets = self.storage.query_all("SELECT * FROM continuity_packets WHERE client_id = ? AND vault_id = ?", (client_id, vault_id))
        blocked = sum(1 for row in request_logs if row["status"] == "blocked")
        allowed = sum(1 for row in request_logs if row["status"] == "allowed")
        return {
            "version": "0.75",
            "boundary": BOUNDARY_V075,
            "client_overview": {
                "client_id": client_id,
                "organisation": clients[0]["organisation"] if clients else "Synthetic V0.75 Alpha Client",
                "status": clients[0]["status"] if clients else "active",
                "synthetic_only": True,
                "active_vault_count": len(vaults),
                "active_namespace_count": len(namespaces),
            },
            "api_key_panel": {
                "records": key_records,
                "safe_key_previews_only": True,
            },
            "vault_namespace_panel": {
                "vaults": vaults,
                "namespaces": namespaces,
            },
            "usage_overview": {
                "allowed_request_count": allowed,
                "blocked_request_count": blocked,
                "usage_log_count": len(usage_logs),
            },
            "request_log_summary": {
                "rows": request_logs,
                "blocked_reasons": sorted({row["reason"] for row in request_logs if row["status"] == "blocked"}),
            },
            "reports_panel": {
                "reports": reports,
            },
            "memory_health_panel": {
                "status": "api_wrapper_connected",
                "events_received": len(all_events),
                "packets_generated": len(packets),
                "reports_visible": len(reports),
                "reconstruction_available": bool(self.storage.list_reconstruction_records(client_id, vault_id, namespace)),
                "explanation_available": bool(self.storage.list_explanation_records(client_id, vault_id, namespace)),
                "blocked_request_count": blocked,
            },
        }


def build_public_report(checks: list[dict[str, Any]], dashboard_state: dict[str, Any], config: PRMRAPIConfig) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.75",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Backend API Wrapper",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V075,
        "router_approach": "local server-shaped route handler abstraction",
        "routes": sorted(ROUTES.keys()),
        "config": config.public_safe(),
        "dashboard_summary": {
            "allowed_request_count": dashboard_state.get("usage_overview", {}).get("allowed_request_count", 0),
            "blocked_request_count": dashboard_state.get("usage_overview", {}).get("blocked_request_count", 0),
            "events_received": dashboard_state.get("memory_health_panel", {}).get("events_received", 0),
            "packets_generated": dashboard_state.get("memory_health_panel", {}).get("packets_generated", 0),
            "reports_visible": dashboard_state.get("memory_health_panel", {}).get("reports_visible", 0),
            "memory_health": dashboard_state.get("memory_health_panel", {}).get("status"),
        },
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], wrapper: PRMRHostedAPIWrapper, route_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Hosted Backend API Wrapper Restricted Synthetic Evidence",
        "checks": checks,
        "route_results": route_results,
        "storage_snapshot_restricted": wrapper.storage.export_storage_snapshot(public_safe=False),
        "restricted_note": "Restricted synthetic evidence may include key hashes. Raw API key values are not persisted or reported.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.75 Hosted Backend API Wrapper",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V075}",
        "",
        "## Routes",
        "",
        *[f"- {route}" for route in public_report["routes"]],
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_hosted_api_wrapper_v075.py", "", BOUNDARY_V075, ""])
    return "\n".join(lines)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})
