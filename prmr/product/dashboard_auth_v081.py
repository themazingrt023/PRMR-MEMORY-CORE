"""V0.81 dashboard auth and scoped client access.

This module provides a local/deployable dashboard access layer for controlled
alpha evidence. It uses synthetic session tokens that are hashed internally and
scopes dashboard state to one client. It is not production authentication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import PRMRAPIKeyLifecycle
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now


BOUNDARY_V081 = (
    "V0.81 is dashboard scoped access evidence only. It proves local/deployable "
    "synthetic dashboard session scoping and cross-client denial. It is not full "
    "production authentication, self-serve login, billing, external validation, "
    "bank approval, compliance approval, legal approval, external security "
    "certification, or real-world validation."
)


@dataclass
class DashboardSession:
    session_id: str
    client_id: str
    token_hash: str
    safe_token_preview: str
    status: str
    created_at: str
    expires_at: str | None
    revoked_at: str | None


class DashboardAuthV081:
    """Synthetic dashboard session auth with per-client state scoping."""

    def __init__(self) -> None:
        self.lifecycle = PRMRAPIKeyLifecycle()
        self.sessions: dict[str, DashboardSession] = {}
        self.metrics: dict[str, dict[str, int]] = {}

    def safe_token_preview(self, raw_token: str) -> str:
        return f"dashboard_session_...{raw_token[-4:]}"

    def create_client_scope(
        self,
        *,
        client_id: str,
        organisation: str,
        contact_email: str,
        vault_id: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        client = self.lifecycle.create_client(
            organisation=organisation,
            contact_email=contact_email,
            status="active",
            client_id=client_id,
        )
        usage_limit = self.lifecycle.create_usage_limit(
            usage_limit_id=f"limit_v081_{client_id}",
            max_events_per_day=30,
            max_packets_per_day=30,
            max_reports_per_day=30,
            alpha_limit_reason="V0.81 synthetic dashboard scoped access limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=vault_id, status="active")
        namespace_record = self.lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace, status="active")
        issue = self.lifecycle.issue_alpha_key(
            client_id=client.client_id,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=usage_limit.usage_limit_id,
            operator_id="operator_v081_founder",
            approval_reason="approved for synthetic dashboard scoped access test",
        )
        self.metrics[client.client_id] = {
            "events_received": 0,
            "packets_generated": 0,
            "reports_visible": 0,
        }
        return {
            "client": asdict(client),
            "vault": asdict(vault),
            "namespace": asdict(namespace_record),
            "usage_limit": asdict(usage_limit),
            "issue": {
                "key_id": issue["key_id"],
                "safe_key_preview": issue["safe_key_preview"],
                "key_hash_prefix": safe_hash(issue["raw_api_key"])[:12],
            },
            "raw_api_key": issue["raw_api_key"],
        }

    def create_dashboard_session(
        self,
        *,
        client_id: str,
        expires_minutes: int | None = 60,
    ) -> dict[str, Any]:
        raw_token = f"dash_v081_{uuid4().hex}"
        created = datetime.now(timezone.utc)
        expires_at = (created + timedelta(minutes=expires_minutes)).isoformat() if expires_minutes else None
        session = DashboardSession(
            session_id=f"session_v081_{uuid4().hex[:12]}",
            client_id=client_id,
            token_hash=safe_hash(raw_token),
            safe_token_preview=self.safe_token_preview(raw_token),
            status="active",
            created_at=created.isoformat(),
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[session.session_id] = session
        return {
            "session_id": session.session_id,
            "client_id": client_id,
            "dashboard_token": raw_token,
            "safe_token_preview": session.safe_token_preview,
            "expires_at": session.expires_at,
            "returned_once": True,
            "public_safe": False,
            "boundary": BOUNDARY_V081,
        }

    def find_session_by_token(self, raw_token: str | None) -> DashboardSession | None:
        if not raw_token:
            return None
        hashed = safe_hash(raw_token)
        for session in self.sessions.values():
            if session.token_hash == hashed:
                return session
        return None

    def validate_dashboard_access(self, *, raw_token: str | None, requested_client_id: str) -> dict[str, Any]:
        if not raw_token:
            return self.error("missing_dashboard_token", "A dashboard session token is required.", 401)
        session = self.find_session_by_token(raw_token)
        if session is None:
            return self.error("invalid_dashboard_token", "The dashboard session token is not valid.", 401)
        if session.status == "revoked":
            return self.error("revoked_dashboard_token", "The dashboard session token is no longer active.", 403)
        if session.expires_at and datetime.fromisoformat(session.expires_at) < datetime.now(timezone.utc):
            session.status = "expired"
            return self.error("expired_dashboard_token", "The dashboard session token has expired.", 403)
        if session.client_id != requested_client_id:
            return self.error("client_scope_denied", "This dashboard session is not authorized for the requested client.", 403)
        return {
            "allowed": True,
            "status_code": 200,
            "reason": "allowed",
            "client_id": session.client_id,
            "session_id": session.session_id,
            "safe_token_preview": session.safe_token_preview,
            "public_safe": True,
        }

    def error(self, code: str, message: str, status_code: int) -> dict[str, Any]:
        return {
            "allowed": False,
            "status_code": status_code,
            "reason": code,
            "error": {"code": code, "message": message},
            "public_safe": True,
            "boundary": BOUNDARY_V081,
        }

    def revoke_session(self, *, session_id: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session is None:
            return self.error("session_not_found", "Dashboard session was not found.", 404)
        session.status = "revoked"
        session.revoked_at = utc_now()
        return {"ok": True, "status_code": 200, "session_id": session_id, "status": "revoked"}

    def record_synthetic_activity(self, *, client_id: str, vault_id: str, namespace: str, raw_api_key: str) -> dict[str, Any]:
        operations = [
            ("events_ingest", 2),
            ("continuity_packet", 1),
            ("memory_reconstruct", 1),
            ("explain", 1),
            ("least_harm_action", 1),
            ("report_read", 1),
        ]
        outcomes = []
        for operation, count in operations:
            decision = self.lifecycle.validate_key(
                client_id=client_id,
                raw_api_key=raw_api_key,
                vault_id=vault_id,
                namespace=namespace,
                operation=operation,
                count=count,
            )
            outcomes.append({"operation": operation, "allowed": decision.allowed, "reason": decision.reason})
        self.lifecycle.foundation.register_report(
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            report_id=f"report_v081_{client_id}",
            report_dir="reports/v081",
        )
        self.metrics[client_id] = {
            "events_received": 2,
            "packets_generated": 1,
            "reports_visible": 1,
        }
        return {"outcomes": outcomes}

    def dashboard_state(self, *, raw_token: str | None, requested_client_id: str) -> dict[str, Any]:
        access = self.validate_dashboard_access(raw_token=raw_token, requested_client_id=requested_client_id)
        if not access["allowed"]:
            return {
                "status": "error",
                "status_code": access["status_code"],
                "error": access["error"],
                "public_safe": True,
                "boundary": BOUNDARY_V081,
            }
        state = self.scoped_dashboard_state(requested_client_id, access)
        return {"status": "ok", "status_code": 200, "dashboard": state, "public_safe": True, "boundary": BOUNDARY_V081}

    def scoped_dashboard_state(self, client_id: str, access: dict[str, Any]) -> dict[str, Any]:
        foundation = self.lifecycle.foundation
        client = foundation.clients[client_id]
        vaults = [asdict(vault) for vault in foundation.vaults.values() if vault.client_id == client_id]
        namespaces = [asdict(ns) for ns in foundation.namespaces.values() if ns.client_id == client_id]
        lifecycle_keys = [
            record
            for record in self.lifecycle.lifecycle_keys.values()
            if record.client_id == client_id
        ]
        key_records = [
            {
                "key_id": record.key_id,
                "client_id": record.client_id,
                "safe_key_preview": record.safe_key_preview,
                "key_hash_prefix": record.key_hash[:12],
                "status": record.status,
                "vault_id": record.vault_id,
                "namespace": record.namespace,
                "last_used_at": record.last_used_at,
            }
            for record in lifecycle_keys
        ]
        request_logs = [
            {
                "timestamp": row.timestamp,
                "client_id": row.client_id,
                "operation": row.operation,
                "status": row.status,
                "reason": row.reason,
                "public_safe_message": row.public_safe_message,
            }
            for row in foundation.request_log
            if row.client_id == client_id
        ]
        reports = [
            {
                "report_id": report.report_id,
                "client_id": report.client_id,
                "vault_id": report.vault_id,
                "namespace": report.namespace,
                "public_safe": report.public_safe,
            }
            for report in foundation.report_registry.values()
            if report.client_id == client_id
        ]
        allowed = sum(1 for row in request_logs if row["status"] == "allowed")
        blocked = sum(1 for row in request_logs if row["status"] == "blocked")
        metrics = self.metrics.get(client_id, {})
        return {
            "version": "0.81",
            "client_overview": {
                "client_id": client.client_id,
                "organisation": client.organisation,
                "status": client.status,
                "synthetic_only": True,
                "active_vault_count": len(vaults),
                "active_namespace_count": len(namespaces),
            },
            "dashboard_session": {
                "session_id": access["session_id"],
                "safe_token_preview": access["safe_token_preview"],
                "raw_token_exposed": False,
            },
            "api_key_panel": {
                "records": key_records,
                "safe_key_previews_only": True,
                "raw_api_keys_exposed": False,
            },
            "vault_namespace_panel": {
                "vaults": vaults,
                "namespaces": namespaces,
            },
            "usage_overview": {
                "allowed_request_count": allowed,
                "blocked_request_count": blocked,
                "usage_log_count": len([event for event in foundation.usage_ledger if event.client_id == client_id]),
            },
            "request_log_summary": {
                "rows": request_logs,
                "blocked_reasons": sorted({row["reason"] for row in request_logs if row["status"] == "blocked"}),
            },
            "reports_panel": {
                "reports": reports,
                "public_safe_reports_only": True,
            },
            "memory_health_panel": {
                "status": "scoped_dashboard_access_verified",
                "events_received": metrics.get("events_received", 0),
                "packets_generated": metrics.get("packets_generated", 0),
                "reports_visible": metrics.get("reports_visible", 0),
                "blocked_request_count": blocked,
            },
            "boundary": BOUNDARY_V081,
        }
