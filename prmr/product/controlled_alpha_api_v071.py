"""Controlled-alpha HTTP-style API surface for PRMR Memory Core V0.71.

This module exposes local callable endpoint handlers. It is deployable-shaped,
but it is not a live hosted API unless separately deployed and smoke-tested.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import PRMRAPIKeyLifecycle
from prmr.product.hosted_backend_foundation_v069 import utc_now


BOUNDARY_V071 = (
    "V0.71 is a local/deployable controlled-alpha API surface only. Unless "
    "actually hosted and smoke-tested, it is not live hosted API access, not "
    "production onboarding, not billing, not self-serve signup, not external "
    "validation, not bank approval, not compliance approval, not legal approval, "
    "not external security certification, and not real-world validation."
)

ENDPOINTS = [
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
]

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "key_hash",
    "validation_outcomes",
    "debug",
    "private_trace",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


@dataclass
class APIRequestLog:
    timestamp: str
    endpoint: str
    client_id: str
    vault_id: str
    namespace: str
    status: str
    reason: str
    public_safe_message: str


class PRMRControlledAlphaAPI:
    """Local HTTP-style controlled-alpha API surface."""

    def __init__(self) -> None:
        self.lifecycle = PRMRAPIKeyLifecycle()
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.packets: dict[str, dict[str, Any]] = {}
        self.public_reports: dict[str, dict[str, Any]] = {}
        self.private_reports: dict[str, dict[str, Any]] = {}
        self.api_request_log: list[APIRequestLog] = []

    def scope_key(self, client_id: str, vault_id: str, namespace: str) -> str:
        return f"{client_id}::{vault_id}::{namespace}"

    def setup_synthetic_client(
        self,
        *,
        client_id: str = "client_v071_synthetic_alpha",
        vault_id: str = "vault_v071_alpha",
        namespace: str = "default",
        usage_limit_id: str = "limit_v071_alpha",
    ) -> dict[str, Any]:
        client = self.lifecycle.create_client(
            organisation="Synthetic V0.71 Alpha Client",
            contact_email="synthetic-v071@example.test",
            client_id=client_id,
        )
        limit = self.lifecycle.create_usage_limit(
            usage_limit_id=usage_limit_id,
            max_events_per_day=3,
            max_packets_per_day=4,
            max_reports_per_day=3,
            alpha_limit_reason="V0.71 local controlled-alpha API usage limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=vault_id)
        namespace_record = self.lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace)
        issue = self.lifecycle.issue_alpha_key(
            client_id=client.client_id,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=limit.usage_limit_id,
            operator_id="operator_v071_founder",
            approval_reason="approved for synthetic controlled-alpha API test",
        )
        return {
            "client": client,
            "vault": vault,
            "namespace": namespace_record,
            "usage_limit": limit,
            "issue": issue,
            "raw_api_key": issue["raw_api_key"],
        }

    def auth_context(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "client_id": str(request_payload.get("client_id", "")),
            "vault_id": str(request_payload.get("vault_id", "")),
            "namespace": str(request_payload.get("namespace", "")),
            "raw_api_key": request_payload.get("api_key"),
        }

    def response(self, status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status_code": status_code, "body": payload}

    def public_error(self, decision: Any, endpoint: str, context: dict[str, Any]) -> dict[str, Any]:
        self.api_request_log.append(
            APIRequestLog(
                timestamp=utc_now(),
                endpoint=endpoint,
                client_id=context.get("client_id", ""),
                vault_id=context.get("vault_id", ""),
                namespace=context.get("namespace", ""),
                status="blocked",
                reason=decision.reason,
                public_safe_message=decision.public_safe_message,
            )
        )
        return self.response(
            decision.status_code,
            {
                "status": "error",
                "error": {
                    "code": decision.reason,
                    "message": decision.public_safe_message,
                },
                "public_safe": True,
                "boundary": BOUNDARY_V071,
            },
        )

    def public_ok(self, endpoint: str, context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.api_request_log.append(
            APIRequestLog(
                timestamp=utc_now(),
                endpoint=endpoint,
                client_id=context["client_id"],
                vault_id=context["vault_id"],
                namespace=context["namespace"],
                status="ok",
                reason="allowed",
                public_safe_message="Request completed for scoped controlled-alpha client.",
            )
        )
        return self.response(
            200,
            {
                "status": "ok",
                "client_id": context["client_id"],
                "vault_id": context["vault_id"],
                "namespace": context["namespace"],
                "public_safe": True,
                **payload,
            },
        )

    def require_access(self, endpoint: str, request_payload: dict[str, Any], operation: str, count: int = 1):
        context = self.auth_context(request_payload)
        decision = self.lifecycle.validate_key(
            client_id=context["client_id"],
            raw_api_key=context["raw_api_key"],
            vault_id=context["vault_id"],
            namespace=context["namespace"],
            operation=operation,
            count=count,
        )
        if not decision.allowed:
            return context, self.public_error(decision, endpoint, context)
        return context, None

    def events_ingest(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/events/ingest"
        events = request_payload.get("events")
        count = len(events) if isinstance(events, list) else 1
        context, error = self.require_access(endpoint, request_payload, "events_ingest", count=count)
        if error:
            return error
        if not isinstance(events, list) or not events:
            return self.response(400, {"status": "error", "error": {"code": "payload_invalid", "message": "events must be a non-empty list."}, "public_safe": True})

        safe_events = []
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                return self.response(400, {"status": "error", "error": {"code": "payload_invalid", "message": "each event must be an object."}, "public_safe": True})
            safe_events.append(
                {
                    "event_id": str(event.get("event_id") or f"evt_{uuid4().hex[:12]}")[:120],
                    "user_id": str(event.get("user_id", "synthetic_user"))[:120],
                    "type": str(event.get("type", "memory_event"))[:120],
                    "content": str(event.get("content", ""))[:1200],
                    "timestamp": str(event.get("timestamp", utc_now()))[:120],
                    "timestamp_index": int(event.get("timestamp_index", index + 1)),
                    "synthetic": True,
                }
            )
        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        self.events.setdefault(scope, []).extend(safe_events)
        return self.public_ok(
            endpoint,
            context,
            {
                "accepted_event_count": len(safe_events),
                "total_event_count": len(self.events[scope]),
                "summary": "Synthetic events accepted into the scoped controlled-alpha namespace.",
            },
        )

    def continuity_packet(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/continuity/packet"
        context, error = self.require_access(endpoint, request_payload, "continuity_packet")
        if error:
            return error
        scope = self.scope_key(context["client_id"], context["vault_id"], context["namespace"])
        events = self.events.get(scope, [])
        if not events:
            return self.response(404, {"status": "error", "error": {"code": "events_not_found", "message": "No scoped events are available."}, "public_safe": True})

        packet_id = f"packet_{uuid4().hex[:12]}"
        latest = sorted(events, key=lambda item: item.get("timestamp_index", 0))[-1]
        packet = {
            "packet_id": packet_id,
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            "event_count": len(events),
            "current_state": latest["content"],
            "summary": "Continuity packet generated from synthetic events.",
            "active_signals": sorted({event["type"] for event in events}),
            "stale_signals": [],
            "public_safe": True,
        }
        self.packets[packet_id] = packet
        report_id = f"report_{uuid4().hex[:12]}"
        public_report = {
            "report_id": report_id,
            "packet_id": packet_id,
            "client_id": context["client_id"],
            "vault_id": context["vault_id"],
            "namespace": context["namespace"],
            "summary": "Public-safe controlled-alpha continuity report generated from synthetic events.",
            "event_count": len(events),
            "public_safe": True,
            "boundary": BOUNDARY_V071,
        }
        private_report = {
            **public_report,
            "public_safe": False,
            "synthetic_event_trace": events,
            "private_note": "Private report contains synthetic event trace only; no raw API keys are persisted.",
        }
        self.public_reports[report_id] = public_report
        self.private_reports[report_id] = private_report
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet_id,
                "report_id": report_id,
                "summary": packet["summary"],
            },
        )

    def memory_reconstruct(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/memory/reconstruct"
        context, error = self.require_access(endpoint, request_payload, "memory_reconstruct")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "reconstructable_state": {
                    "current_state": packet["current_state"],
                    "active_signals": packet["active_signals"],
                    "stale_signals": packet["stale_signals"],
                },
                "summary": "Current state reconstructed from scoped synthetic continuity events.",
            },
        )

    def explain(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/explain"
        context, error = self.require_access(endpoint, request_payload, "explain")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "explanation": {
                    "summary": "This state reflects the latest synthetic continuity event in the scoped namespace.",
                    "review_boundary": "This is controlled-alpha review support, not a final decision.",
                    "sensitive_details_included": False,
                },
            },
        )

    def least_harm_action(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "POST /v1/actions/least-harm"
        context, error = self.require_access(endpoint, request_payload, "least_harm_action")
        if error:
            return error
        packet = self.packets.get(str(request_payload.get("packet_id", "")))
        if not packet or not self.packet_owned_by(packet, context):
            return self.response(404, {"status": "error", "error": {"code": "packet_not_found", "message": "Packet was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(
            endpoint,
            context,
            {
                "packet_id": packet["packet_id"],
                "recommended_action": "human_review",
                "allowed_actions": ["do_nothing", "request_evidence", "human_review", "keep_dormant"],
                "not_final_decision": True,
                "summary": "Use proportionate review before taking action.",
            },
        )

    def get_report(self, request_payload: dict[str, Any], report_id: str) -> dict[str, Any]:
        endpoint = "GET /v1/reports/{report_id}"
        context, error = self.require_access(endpoint, request_payload, "report_read")
        if error:
            return error
        report = self.public_reports.get(report_id)
        if not report or not self.report_owned_by(report, context):
            return self.response(404, {"status": "error", "error": {"code": "report_not_found", "message": "Report was not found in the authorized scope."}, "public_safe": True})
        return self.public_ok(endpoint, context, {"report": report})

    def get_usage(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "GET /v1/usage"
        context, error = self.require_access(endpoint, request_payload, "report_read")
        if error:
            return error
        return self.public_ok(endpoint, context, {"usage": self.lifecycle.get_client_usage(context["client_id"])})

    def packet_owned_by(self, packet: dict[str, Any], context: dict[str, Any]) -> bool:
        return packet.get("client_id") == context["client_id"] and packet.get("vault_id") == context["vault_id"] and packet.get("namespace") == context["namespace"]

    def report_owned_by(self, report: dict[str, Any], context: dict[str, Any]) -> bool:
        return report.get("client_id") == context["client_id"] and report.get("vault_id") == context["vault_id"] and report.get("namespace") == context["namespace"]

    def request_log_report(self) -> dict[str, Any]:
        return {
            "version": "0.71",
            "boundary": BOUNDARY_V071,
            "request_log": [asdict(item) for item in self.api_request_log],
            "foundation_request_log": [asdict(item) for item in self.lifecycle.foundation.request_log],
        }

    def usage_summary_report(self) -> dict[str, Any]:
        return {
            "version": "0.71",
            "boundary": BOUNDARY_V071,
            "usage": self.lifecycle.foundation.usage_summary(),
        }

    def public_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for check in checks if check.get("passed"))
        total = len(checks)
        return {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.71",
            "title": "Hosted Controlled-Alpha API Surface",
            "result": "PASS" if passed == total else "NEEDS_WORK",
            "checks_passed": passed,
            "checks_total": total,
            "public_safe": True,
            "boundary": BOUNDARY_V071,
            "endpoint_coverage": ENDPOINTS,
            "safe_response_summary": {
                "valid_flow_public_safe": True,
                "blocked_flow_public_safe": True,
                "credential_values_in_public_report": False,
                "restricted_details_in_public_report": False,
            },
            "usage_summary": self.lifecycle.foundation.usage_summary(),
        }

    def private_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            **self.public_status_report(checks),
            "public_safe": False,
            "title": "Controlled-Alpha API Surface Private Synthetic Trace",
            "checks": checks,
            "synthetic_clients": {
                client_id: asdict(client)
                for client_id, client in self.lifecycle.foundation.clients.items()
            },
            "synthetic_vaults": {
                vault_id: asdict(vault)
                for vault_id, vault in self.lifecycle.foundation.vaults.items()
            },
            "synthetic_namespaces": {
                namespace_id: asdict(namespace)
                for namespace_id, namespace in self.lifecycle.foundation.namespaces.items()
            },
            "synthetic_packets": self.packets,
            "synthetic_public_reports": self.public_reports,
            "synthetic_private_reports": self.private_reports,
            "api_request_log": [asdict(item) for item in self.api_request_log],
            "validation_outcomes": self.lifecycle.validation_outcomes,
            "private_note": "Private report contains synthetic traces only; raw API keys are not persisted.",
        }


def scan_forbidden_public_terms(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in PUBLIC_FORBIDDEN_TERMS if term.lower() in text]


def scan_unsafe_public_language(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in UNSAFE_PUBLIC_LANGUAGE if term.lower() in text]
