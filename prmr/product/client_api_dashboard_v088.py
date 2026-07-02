"""V0.88 approved-client API dashboard and key-management MVP.

This module composes the existing controlled-alpha client, vault, namespace,
usage, report, and API-key lifecycle models into one dashboard-facing service.
Generated key values are returned only by the create or rotate response. They
are never retained in dashboard state or report exports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import PRMRAPIKeyLifecycle
from prmr.product.hosted_backend_foundation_v069 import utc_now


BOUNDARY_V088 = (
    "V0.88 is an approved-client dashboard and key-management MVP using "
    "controlled synthetic evidence. It is not open public signup, unreviewed "
    "self-serve access, production authentication, production billing, "
    "compliance or legal approval, external security certification, or "
    "real-world client validation."
)

API_BASE_URL = "https://prmr-memory-core-api.onrender.com"


@dataclass
class ApprovedClientProfile:
    client_id: str
    organisation: str
    vault_id: str
    namespace: str
    usage_limit_id: str
    approval_status: str
    approved_at: str
    approved_by: str
    synthetic_only: bool


class ClientAPIDashboardV088:
    """Approved-client dashboard service with copy-once key responses."""

    def __init__(self) -> None:
        self.lifecycle = PRMRAPIKeyLifecycle()
        self.approved_clients: dict[str, ApprovedClientProfile] = {}
        self.key_labels: dict[str, str] = {}
        self.key_release_log: list[dict[str, Any]] = []
        self.memory_metrics: dict[str, dict[str, int | bool]] = {}

    def approve_synthetic_client(
        self,
        *,
        client_id: str = "client_v088_synthetic_alpha",
        organisation: str = "Synthetic V0.88 Approved Alpha Client",
        vault_id: str = "vault_v088_synthetic_alpha",
        namespace: str = "default",
        approved_by: str = "operator_v088_founder",
    ) -> dict[str, Any]:
        """Create a manually approved synthetic client scope without a key."""

        client = self.lifecycle.create_client(
            organisation=organisation,
            contact_email="synthetic-v088@example.test",
            status="active",
            client_id=client_id,
        )
        usage_limit = self.lifecycle.create_usage_limit(
            usage_limit_id=f"limit_v088_{uuid4().hex[:8]}",
            max_events_per_day=100,
            max_packets_per_day=50,
            max_reports_per_day=25,
            alpha_limit_reason="V0.88 controlled synthetic approved-client limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=vault_id, status="active")
        namespace_record = self.lifecycle.create_namespace(
            client.client_id,
            vault.vault_id,
            namespace=namespace,
            status="active",
        )
        profile = ApprovedClientProfile(
            client_id=client.client_id,
            organisation=client.organisation,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=usage_limit.usage_limit_id,
            approval_status="approved",
            approved_at=utc_now(),
            approved_by=approved_by,
            synthetic_only=True,
        )
        self.approved_clients[profile.client_id] = profile
        self.memory_metrics[profile.client_id] = {
            "events_received": 0,
            "packets_generated": 0,
            "reconstruction_available": False,
            "public_reports_visible": 0,
        }
        return {"ok": True, "status_code": 201, "profile": self.safe_profile(profile)}

    def require_approved(self, client_id: str) -> ApprovedClientProfile | None:
        profile = self.approved_clients.get(client_id)
        if profile is None or profile.approval_status != "approved":
            return None
        return profile

    def denied(self) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": 403,
            "error": {
                "code": "approved_client_required",
                "message": "Dashboard access is limited to manually approved controlled-alpha clients.",
            },
            "boundary": BOUNDARY_V088,
        }

    def create_api_key(self, *, client_id: str, label: str) -> dict[str, Any]:
        """Issue one key and return its credential value in this response only."""

        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        clean_label = " ".join(label.split()).strip()
        if not 2 <= len(clean_label) <= 64:
            return {
                "ok": False,
                "status_code": 400,
                "error": {"code": "invalid_key_label", "message": "Key label must be between 2 and 64 characters."},
            }
        issue = self.lifecycle.issue_alpha_key(
            client_id=profile.client_id,
            vault_id=profile.vault_id,
            namespace=profile.namespace,
            usage_limit_id=profile.usage_limit_id,
            operator_id=profile.approved_by,
            approval_reason=f"Approved-client dashboard key creation: {clean_label}",
        )
        key_id = str(issue["key_id"])
        self.key_labels[key_id] = clean_label
        self.key_release_log.append(
            {
                "timestamp": utc_now(),
                "event": "key_created_and_returned_once",
                "client_id": client_id,
                "key_id": key_id,
                "credential_retained_by_dashboard": False,
            }
        )
        return {
            "ok": True,
            "status_code": 201,
            "key_id": key_id,
            "label": clean_label,
            "safe_key_preview": issue["safe_key_preview"],
            "raw_api_key": issue["raw_api_key"],
            "returned_once": True,
            "copy_warning": "Copy this key now. PRMR will not show it again.",
            "server_side_only": True,
            "boundary": BOUNDARY_V088,
        }

    def list_api_keys(self, *, client_id: str) -> dict[str, Any]:
        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        records = [
            {
                "key_id": record.key_id,
                "label": self.key_labels.get(record.key_id, "Unlabelled key"),
                "safe_key_preview": record.safe_key_preview,
                "status": record.status,
                "created_at": record.created_at,
                "last_used_at": record.last_used_at,
                "vault_id": record.vault_id,
                "namespace": record.namespace,
            }
            for record in self.lifecycle.lifecycle_keys.values()
            if record.client_id == client_id
        ]
        return {
            "ok": True,
            "status_code": 200,
            "keys": records,
            "safe_previews_only": True,
            "credential_values_returned": False,
        }

    def validate_key(self, *, client_id: str, raw_api_key: str | None, operation: str = "events_ingest") -> dict[str, Any]:
        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        decision = self.lifecycle.validate_key(
            client_id=profile.client_id,
            raw_api_key=raw_api_key,
            vault_id=profile.vault_id,
            namespace=profile.namespace,
            operation=operation,
        )
        if decision.allowed:
            metrics = self.memory_metrics[client_id]
            if operation == "events_ingest":
                metrics["events_received"] = int(metrics["events_received"]) + 1
            elif operation == "continuity_packet":
                metrics["packets_generated"] = int(metrics["packets_generated"]) + 1
            elif operation == "memory_reconstruct":
                metrics["reconstruction_available"] = True
        return {
            "allowed": decision.allowed,
            "status_code": decision.status_code,
            "reason": decision.reason,
            "public_safe_message": decision.public_safe_message,
        }

    def rotate_api_key(self, *, client_id: str, key_id: str) -> dict[str, Any]:
        """Rotate by dashboard-authorized key ID and return the replacement once."""

        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        old_record = self.lifecycle.lifecycle_keys.get(key_id)
        if old_record is None or old_record.client_id != client_id or old_record.status != "active":
            return {
                "ok": False,
                "status_code": 404,
                "error": {"code": "active_key_not_found", "message": "An active key in this client scope is required."},
            }
        old_record.status = "rotated"
        old_record.rotated_at = utc_now()
        self.lifecycle.foundation.rotate_key(key_id)
        replacement = self.lifecycle.issue_alpha_key(
            client_id=client_id,
            vault_id=old_record.vault_id,
            namespace=old_record.namespace,
            usage_limit_id=old_record.usage_limit_id,
            operator_id=profile.approved_by,
            approval_reason=f"Approved-client dashboard rotation for {key_id}",
        )
        new_key_id = str(replacement["key_id"])
        self.key_labels[new_key_id] = self.key_labels.get(key_id, "Rotated key")
        self.key_release_log.append(
            {
                "timestamp": utc_now(),
                "event": "replacement_key_returned_once",
                "client_id": client_id,
                "key_id": new_key_id,
                "replaces_key_id": key_id,
                "credential_retained_by_dashboard": False,
            }
        )
        return {
            "ok": True,
            "status_code": 200,
            "old_key_id": key_id,
            "new_key_id": new_key_id,
            "label": self.key_labels[new_key_id],
            "safe_key_preview": replacement["safe_key_preview"],
            "raw_api_key": replacement["raw_api_key"],
            "returned_once": True,
            "copy_warning": "Copy this key now. PRMR will not show it again.",
        }

    def revoke_api_key(self, *, client_id: str, key_id: str) -> dict[str, Any]:
        if self.require_approved(client_id) is None:
            return self.denied()
        record = self.lifecycle.lifecycle_keys.get(key_id)
        if record is None or record.client_id != client_id:
            return {
                "ok": False,
                "status_code": 404,
                "error": {"code": "key_not_found", "message": "The key was not found in this client scope."},
            }
        return self.lifecycle.revoke_key(
            key_id=key_id,
            operator_id="approved_client_dashboard_v088",
            revoke_reason="Approved client requested key revocation.",
        )

    def register_public_report(self, *, client_id: str, report_id: str) -> dict[str, Any]:
        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        report = self.lifecycle.foundation.register_report(
            client_id=client_id,
            vault_id=profile.vault_id,
            namespace=profile.namespace,
            report_id=report_id,
            report_dir="reports/v088",
        )
        self.memory_metrics[client_id]["public_reports_visible"] = int(
            self.memory_metrics[client_id]["public_reports_visible"]
        ) + 1
        return {
            "ok": True,
            "report": {
                "report_id": report.report_id,
                "vault_id": report.vault_id,
                "namespace": report.namespace,
                "public_safe": report.public_safe,
            },
        }

    def dashboard_state(self, *, client_id: str) -> dict[str, Any]:
        profile = self.require_approved(client_id)
        if profile is None:
            return self.denied()
        foundation = self.lifecycle.foundation
        key_list = self.list_api_keys(client_id=client_id)
        usage = self.lifecycle.get_client_usage(client_id)
        request_logs = [
            {
                "timestamp": row.timestamp,
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
                "vault_id": report.vault_id,
                "namespace": report.namespace,
                "public_safe": report.public_safe,
            }
            for report in foundation.report_registry.values()
            if report.client_id == client_id and report.public_safe
        ]
        limits = foundation.usage_limits[profile.usage_limit_id]
        return {
            "ok": True,
            "status_code": 200,
            "dashboard": {
                "client_overview": self.safe_profile(profile),
                "api_keys": key_list["keys"],
                "vaults_and_namespaces": [
                    {
                        "vault_id": profile.vault_id,
                        "namespace": profile.namespace,
                        "status": "active",
                    }
                ],
                "usage_summary": {
                    **usage,
                    "limits": {
                        "events_per_day": limits.max_events_per_day,
                        "packets_per_day": limits.max_packets_per_day,
                        "reports_per_day": limits.max_reports_per_day,
                    },
                },
                "request_logs": request_logs,
                "continuity_reports": reports,
                "memory_health": {
                    **self.memory_metrics[client_id],
                    "status": "synthetic_dashboard_ready",
                    "durable_hosted_storage_verified": False,
                },
                "quickstart": {
                    "api_base_url": API_BASE_URL,
                    "environment": [
                        f"PRMR_API_BASE_URL={API_BASE_URL}",
                        "PRMR_API_KEY=<YOUR_PRMR_KEY>",
                        "PRMR_CLIENT_ID=<CLIENT_ID>",
                        "PRMR_VAULT_ID=<VAULT_ID>",
                        "PRMR_NAMESPACE=default",
                    ],
                    "server_side_only": True,
                },
                "credential_values_exposed": False,
                "boundary": BOUNDARY_V088,
            },
        }

    def safe_profile(self, profile: ApprovedClientProfile) -> dict[str, Any]:
        payload = asdict(profile)
        payload.pop("approved_by", None)
        return payload

