"""Manual API key lifecycle layer for PRMR Memory Core V0.70.

This is a local/simulated controlled-alpha key lifecycle service. Raw generated
keys are returned only at issue/rotation runtime and are never persisted in
reports or lifecycle history.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from uuid import uuid4
from typing import Any

from prmr.product.hosted_backend_foundation_v069 import (
    AccessDecision,
    PRMRHostedBackendFoundation,
    safe_hash,
    utc_now,
)


BOUNDARY_V070 = (
    "V0.70 is a local/simulated manual API key lifecycle layer only. Unless "
    "actually deployed and smoke-tested, it is not live hosted API access, not "
    "production onboarding, not billing, not self-serve signup, not external "
    "validation, not bank approval, not compliance approval, not legal approval, "
    "not external security certification, and not real-world validation."
)

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "secret",
    "private_internal",
    "key_hash",
    "approval_trace",
    "validation_trace",
    "debug",
]

UNSAFE_PUBLIC_LANGUAGE = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


def generate_dev_key() -> str:
    return f"prmr_alpha_dev_{uuid4().hex}"


def safe_key_preview(raw_key: str) -> str:
    return f"prmr_alpha_dev_...{raw_key[-4:]}"


@dataclass
class LifecycleKeyRecord:
    key_id: str
    client_id: str
    safe_key_preview: str
    key_hash: str
    status: str
    created_at: str
    rotated_at: str | None
    revoked_at: str | None
    last_used_at: str | None
    usage_limit_id: str
    vault_id: str
    namespace: str


@dataclass
class LifecycleEvent:
    timestamp: str
    event_type: str
    client_id: str
    key_id: str | None
    operator_id: str | None
    reason: str
    public_safe_message: str


class PRMRAPIKeyLifecycle:
    """Manual/operator-approved key lifecycle on top of V0.69 foundation."""

    def __init__(self) -> None:
        self.foundation = PRMRHostedBackendFoundation()
        self.lifecycle_keys: dict[str, LifecycleKeyRecord] = {}
        self.lifecycle_events: list[LifecycleEvent] = []
        self.validation_outcomes: list[dict[str, Any]] = []

    def create_client(self, organisation: str, contact_email: str, status: str = "pending", client_id: str | None = None):
        client = self.foundation.create_client(organisation, contact_email, status=status, client_id=client_id)
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="client_created",
                client_id=client.client_id,
                key_id=None,
                operator_id=None,
                reason=f"client status {status}",
                public_safe_message="Synthetic client record created for local controlled-alpha setup.",
            )
        )
        return client

    def create_usage_limit(self, **kwargs: Any):
        return self.foundation.create_usage_limit(**kwargs)

    def create_vault(self, client_id: str, vault_id: str | None = None, status: str = "active"):
        return self.foundation.create_vault(client_id, vault_id=vault_id, status=status)

    def create_namespace(self, client_id: str, vault_id: str, namespace: str = "default", status: str = "active"):
        return self.foundation.create_namespace(client_id, vault_id, namespace=namespace, status=status)

    def approval_missing(self, operator_id: str | None, approval_reason: str | None) -> bool:
        return not str(operator_id or "").strip() or not str(approval_reason or "").strip()

    def blocked_issue_response(self, client_id: str, reason: str) -> dict[str, Any]:
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="issue_blocked",
                client_id=client_id,
                key_id=None,
                operator_id=None,
                reason=reason,
                public_safe_message="Manual operator approval is required before an alpha key can be issued.",
            )
        )
        return {
            "ok": False,
            "status_code": 403,
            "reason": reason,
            "public_safe_message": "Manual operator approval is required before an alpha key can be issued.",
            "raw_api_key": None,
        }

    def issue_alpha_key(
        self,
        *,
        client_id: str,
        vault_id: str,
        namespace: str,
        usage_limit_id: str,
        operator_id: str | None,
        approval_reason: str | None,
    ) -> dict[str, Any]:
        if self.approval_missing(operator_id, approval_reason):
            return self.blocked_issue_response(client_id, "operator_approval_required")

        client = self.foundation.clients.get(client_id)
        if client is None:
            return self.blocked_issue_response(client_id, "client_not_found")

        if client.status not in {"pending", "active"}:
            return self.blocked_issue_response(client_id, "client_not_issuable")

        raw_key = generate_dev_key()
        key_id = f"key_v070_{uuid4().hex[:10]}"
        record = LifecycleKeyRecord(
            key_id=key_id,
            client_id=client_id,
            safe_key_preview=safe_key_preview(raw_key),
            key_hash=safe_hash(raw_key),
            status="active",
            created_at=utc_now(),
            rotated_at=None,
            revoked_at=None,
            last_used_at=None,
            usage_limit_id=usage_limit_id,
            vault_id=vault_id,
            namespace=namespace,
        )
        self.lifecycle_keys[key_id] = record
        self.foundation.create_test_key_record(
            client_id=client_id,
            raw_key=raw_key,
            usage_limit_id=usage_limit_id,
            key_id=key_id,
            status="active",
        )
        client.status = "active"
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="key_issued",
                client_id=client_id,
                key_id=key_id,
                operator_id=operator_id,
                reason=str(approval_reason),
                public_safe_message="Operator-approved local alpha key issued. Store the runtime value securely; reports keep only safe references.",
            )
        )
        return {
            "ok": True,
            "status_code": 201,
            "key_id": key_id,
            "client_id": client_id,
            "safe_key_preview": record.safe_key_preview,
            "raw_api_key": raw_key,
            "public_safe_message": "Operator-approved local alpha key issued.",
        }

    def find_lifecycle_key_by_raw(self, raw_key: str | None) -> LifecycleKeyRecord | None:
        if not raw_key:
            return None
        hashed = safe_hash(raw_key)
        for record in self.lifecycle_keys.values():
            if record.key_hash == hashed:
                return record
        return None

    def validate_key(
        self,
        *,
        client_id: str,
        raw_api_key: str | None,
        vault_id: str,
        namespace: str,
        operation: str = "events_ingest",
        count: int = 1,
    ) -> AccessDecision:
        decision = self.foundation.validate_access(
            client_id=client_id,
            raw_api_key=raw_api_key,
            vault_id=vault_id,
            namespace=namespace,
            operation=operation,
            count=count,
        )
        key_record = self.find_lifecycle_key_by_raw(raw_api_key)
        if key_record and decision.allowed:
            key_record.last_used_at = utc_now()
        self.validation_outcomes.append(
            {
                "timestamp": utc_now(),
                "client_id": client_id,
                "vault_id": vault_id,
                "namespace": namespace,
                "operation": operation,
                "key_id": key_record.key_id if key_record else None,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "public_safe_message": decision.public_safe_message,
            }
        )
        return decision

    def rotate_key(
        self,
        *,
        client_id: str,
        old_raw_api_key: str,
        operator_id: str,
        approval_reason: str,
    ) -> dict[str, Any]:
        old_record = self.find_lifecycle_key_by_raw(old_raw_api_key)
        if old_record is None or old_record.client_id != client_id or old_record.status != "active":
            return {
                "ok": False,
                "status_code": 403,
                "reason": "active_key_not_found",
                "public_safe_message": "An active key is required for rotation.",
            }

        old_record.status = "rotated"
        old_record.rotated_at = utc_now()
        self.foundation.rotate_key(old_record.key_id)

        raw_key = generate_dev_key()
        new_key_id = f"key_v070_{uuid4().hex[:10]}"
        new_record = LifecycleKeyRecord(
            key_id=new_key_id,
            client_id=client_id,
            safe_key_preview=safe_key_preview(raw_key),
            key_hash=safe_hash(raw_key),
            status="active",
            created_at=utc_now(),
            rotated_at=None,
            revoked_at=None,
            last_used_at=None,
            usage_limit_id=old_record.usage_limit_id,
            vault_id=old_record.vault_id,
            namespace=old_record.namespace,
        )
        self.lifecycle_keys[new_key_id] = new_record
        self.foundation.create_test_key_record(
            client_id=client_id,
            raw_key=raw_key,
            usage_limit_id=old_record.usage_limit_id,
            key_id=new_key_id,
            status="active",
        )
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="key_rotated",
                client_id=client_id,
                key_id=old_record.key_id,
                operator_id=operator_id,
                reason=approval_reason,
                public_safe_message="Old key rotated and replacement key issued for local controlled-alpha use.",
            )
        )
        return {
            "ok": True,
            "status_code": 200,
            "old_key_id": old_record.key_id,
            "new_key_id": new_key_id,
            "safe_key_preview": new_record.safe_key_preview,
            "raw_api_key": raw_key,
            "public_safe_message": "Replacement key generated. Raw value is returned once at runtime only.",
        }

    def revoke_key(self, *, key_id: str, operator_id: str, revoke_reason: str) -> dict[str, Any]:
        record = self.lifecycle_keys.get(key_id)
        if record is None:
            return {"ok": False, "status_code": 404, "reason": "key_not_found"}
        record.status = "revoked"
        record.revoked_at = utc_now()
        self.foundation.revoke_key(key_id)
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="key_revoked",
                client_id=record.client_id,
                key_id=key_id,
                operator_id=operator_id,
                reason=revoke_reason,
                public_safe_message="Key revoked for local controlled-alpha use.",
            )
        )
        return {"ok": True, "status_code": 200, "key_id": key_id, "status": "revoked"}

    def suspend_client(self, *, client_id: str, operator_id: str, reason: str) -> dict[str, Any]:
        client = self.foundation.clients.get(client_id)
        if client is None:
            return {"ok": False, "status_code": 404, "reason": "client_not_found"}
        client.status = "suspended"
        for key in self.lifecycle_keys.values():
            if key.client_id == client_id and key.status == "active":
                key.status = "suspended"
                if key.key_id in self.foundation.api_keys:
                    self.foundation.api_keys[key.key_id].status = "suspended"
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="client_suspended",
                client_id=client_id,
                key_id=None,
                operator_id=operator_id,
                reason=reason,
                public_safe_message="Client suspended; key validation is blocked while client is not active.",
            )
        )
        return {"ok": True, "status_code": 200, "client_id": client_id, "status": "suspended"}

    def reactivate_client(self, *, client_id: str, operator_id: str, reason: str) -> dict[str, Any]:
        client = self.foundation.clients.get(client_id)
        if client is None:
            return {"ok": False, "status_code": 404, "reason": "client_not_found"}
        client.status = "active"
        for key in self.lifecycle_keys.values():
            if key.client_id == client_id and key.status == "suspended":
                key.status = "active"
                if key.key_id in self.foundation.api_keys:
                    self.foundation.api_keys[key.key_id].status = "active"
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="client_reactivated",
                client_id=client_id,
                key_id=None,
                operator_id=operator_id,
                reason=reason,
                public_safe_message="Client reactivated by operator for local controlled-alpha use.",
            )
        )
        return {"ok": True, "status_code": 200, "client_id": client_id, "status": "active"}

    def get_client_usage(self, client_id: str) -> dict[str, Any]:
        client_usage_events = [
            event for event in self.foundation.usage_ledger if event.client_id == client_id
        ]
        summary: dict[str, Any] = {
            "allowed_request_count": sum(1 for event in client_usage_events if event.allowed),
            "blocked_request_count": sum(1 for event in client_usage_events if not event.allowed),
            "by_client": {client_id: sum(event.count for event in client_usage_events)},
            "by_vault": {},
            "by_namespace": {},
        }
        for event in client_usage_events:
            summary["by_vault"].setdefault(event.vault_id, 0)
            summary["by_vault"][event.vault_id] += event.count
            namespace_key = self.foundation.namespace_key(event.client_id, event.vault_id, event.namespace)
            summary["by_namespace"].setdefault(namespace_key, 0)
            summary["by_namespace"][namespace_key] += event.count
        client_logs = [log for log in self.foundation.request_log if log.client_id == client_id]
        return {
            "client_id": client_id,
            "allowed_request_count": sum(1 for log in client_logs if log.status == "allowed"),
            "blocked_request_count": sum(1 for log in client_logs if log.status == "blocked"),
            "last_request_status": client_logs[-1].status if client_logs else None,
            "usage_summary": summary,
        }

    def get_key_status(self, key_id: str) -> dict[str, Any]:
        record = self.lifecycle_keys.get(key_id)
        if record is None:
            return {"ok": False, "status_code": 404, "reason": "key_not_found"}
        payload = asdict(record)
        payload.pop("key_hash", None)
        return {"ok": True, "key": payload}

    def safe_key_record(self, record: LifecycleKeyRecord, include_hash: bool = False) -> dict[str, Any]:
        payload = asdict(record)
        if include_hash:
            payload["key_hash"] = f"sha256:{record.key_hash[:16]}..."
        else:
            payload.pop("key_hash", None)
        return payload

    def lifecycle_events_public(self) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "client_id": event.client_id,
                "key_id": event.key_id,
                "public_safe_message": event.public_safe_message,
            }
            for event in self.lifecycle_events
        ]

    def lifecycle_events_private(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self.lifecycle_events]

    def export_key_lifecycle_report(self, checks: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        passed = sum(1 for check in checks if check.get("passed"))
        total = len(checks)
        key_status_counts: dict[str, int] = {}
        for record in self.lifecycle_keys.values():
            key_status_counts.setdefault(record.status, 0)
            key_status_counts[record.status] += 1

        public_report = {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.70",
            "title": "Manual API Key Lifecycle Layer",
            "result": "PASS" if passed == total else "NEEDS_WORK",
            "checks_passed": passed,
            "checks_total": total,
            "public_safe": True,
            "boundary": BOUNDARY_V070,
            "lifecycle_functions": [
                "create_client",
                "create_vault",
                "create_namespace",
                "issue_alpha_key",
                "validate_key",
                "rotate_key",
                "revoke_key",
                "suspend_client",
                "reactivate_client",
                "get_client_usage",
                "get_key_status",
                "export_key_lifecycle_report",
            ],
            "safe_key_lifecycle_summary": {
                "manual_operator_approval_required": True,
                "self_serve_key_issuing": False,
                "automatic_real_key_issuing": False,
                "credential_values_in_public_report": False,
                "key_status_counts": key_status_counts,
            },
            "usage_summary": self.get_client_usage("client_v070_synthetic_alpha"),
            "lifecycle_event_summary": self.lifecycle_events_public(),
        }
        private_report = {
            **public_report,
            "public_safe": False,
            "title": "Manual API Key Lifecycle Private Local Trace",
            "checks": checks,
            "clients": {
                client_id: asdict(client)
                for client_id, client in self.foundation.clients.items()
            },
            "vaults": {
                vault_id: asdict(vault)
                for vault_id, vault in self.foundation.vaults.items()
            },
            "namespaces": {
                namespace_id: asdict(namespace)
                for namespace_id, namespace in self.foundation.namespaces.items()
            },
            "lifecycle_key_records": {
                key_id: self.safe_key_record(record, include_hash=True)
                for key_id, record in self.lifecycle_keys.items()
            },
            "lifecycle_events": self.lifecycle_events_private(),
            "validation_outcomes": self.validation_outcomes,
            "request_logs": [asdict(log) for log in self.foundation.request_log],
            "private_note": "Private report includes synthetic local traces and safe key references only; raw API key values are not persisted.",
        }
        return public_report, private_report


def scan_forbidden_public_terms(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in PUBLIC_FORBIDDEN_TERMS if term.lower() in text]


def scan_unsafe_public_language(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return [term for term in UNSAFE_PUBLIC_LANGUAGE if term.lower() in text]
