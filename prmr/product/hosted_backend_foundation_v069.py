"""Local hosted-backend foundation model for PRMR Memory Core V0.69.

This module is a local/simulated product platform base. It is not a deployed
hosted backend and does not issue real client credentials.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


BOUNDARY_V069 = (
    "V0.69 is a local hosted-backend foundation/product platform base only. "
    "It is not a live hosted backend, not production onboarding, not billing, "
    "not live API access, not automatic API key issuing, not external validation, "
    "not bank approval, not compliance approval, not legal approval, not external "
    "security certification, and not real-world validation."
)

VALID_OPERATIONS = {
    "events_ingest",
    "continuity_packet",
    "memory_reconstruct",
    "explain",
    "least_harm_action",
    "report_read",
}

PUBLIC_FORBIDDEN_TERMS = [
    "raw_key",
    "api_secret",
    "private_key",
    "full_api_key",
    "private_internal",
    "validation_trace",
    "key_hash",
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_hash(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def key_fingerprint(raw_value: str) -> str:
    return safe_hash(raw_value)[:12]


@dataclass
class Client:
    client_id: str
    organisation: str
    contact_email: str
    status: str
    created_at: str


@dataclass
class APIKeyRecord:
    key_id: str
    client_id: str
    key_hash: str
    status: str
    created_at: str
    last_used_at: str | None
    usage_limit_id: str
    key_fingerprint: str


@dataclass
class Vault:
    vault_id: str
    client_id: str
    status: str
    created_at: str


@dataclass
class Namespace:
    namespace: str
    vault_id: str
    client_id: str
    status: str
    created_at: str


@dataclass
class UsageLimit:
    usage_limit_id: str
    max_events_per_day: int
    max_packets_per_day: int
    max_reports_per_day: int
    alpha_limit_reason: str


@dataclass
class UsageEvent:
    timestamp: str
    client_id: str
    vault_id: str
    namespace: str
    operation: str
    count: int
    allowed: bool


@dataclass
class RequestLog:
    timestamp: str
    client_id: str
    operation: str
    status: str
    reason: str
    public_safe_message: str


@dataclass
class ContinuityReportRef:
    report_id: str
    client_id: str
    vault_id: str
    namespace: str
    public_report_path: str
    private_report_path: str
    public_safe: bool


@dataclass
class AccessDecision:
    allowed: bool
    status_code: int
    reason: str
    public_safe_message: str


@dataclass
class PlatformState:
    clients: dict[str, Client] = field(default_factory=dict)
    api_keys: dict[str, APIKeyRecord] = field(default_factory=dict)
    vaults: dict[str, Vault] = field(default_factory=dict)
    namespaces: dict[str, Namespace] = field(default_factory=dict)
    usage_limits: dict[str, UsageLimit] = field(default_factory=dict)
    usage_ledger: list[UsageEvent] = field(default_factory=list)
    request_log: list[RequestLog] = field(default_factory=list)
    report_registry: dict[str, ContinuityReportRef] = field(default_factory=dict)


class PRMRHostedBackendFoundation:
    """Local/simulated backend foundation for product-platform behavior."""

    def __init__(self) -> None:
        self.state = PlatformState()
        self.validation_traces: list[dict[str, Any]] = []

    @property
    def clients(self) -> dict[str, Client]:
        return self.state.clients

    @property
    def api_keys(self) -> dict[str, APIKeyRecord]:
        return self.state.api_keys

    @property
    def vaults(self) -> dict[str, Vault]:
        return self.state.vaults

    @property
    def namespaces(self) -> dict[str, Namespace]:
        return self.state.namespaces

    @property
    def usage_limits(self) -> dict[str, UsageLimit]:
        return self.state.usage_limits

    @property
    def usage_ledger(self) -> list[UsageEvent]:
        return self.state.usage_ledger

    @property
    def request_log(self) -> list[RequestLog]:
        return self.state.request_log

    @property
    def report_registry(self) -> dict[str, ContinuityReportRef]:
        return self.state.report_registry

    def create_client(
        self,
        organisation: str,
        contact_email: str,
        status: str = "active",
        client_id: str | None = None,
    ) -> Client:
        client = Client(
            client_id=client_id or f"client_{uuid4().hex[:10]}",
            organisation=organisation,
            contact_email=contact_email,
            status=status,
            created_at=utc_now(),
        )
        self.clients[client.client_id] = client
        return client

    def create_usage_limit(
        self,
        max_events_per_day: int = 3,
        max_packets_per_day: int = 2,
        max_reports_per_day: int = 2,
        alpha_limit_reason: str = "local alpha safety limit",
        usage_limit_id: str | None = None,
    ) -> UsageLimit:
        limit = UsageLimit(
            usage_limit_id=usage_limit_id or f"limit_{uuid4().hex[:10]}",
            max_events_per_day=max_events_per_day,
            max_packets_per_day=max_packets_per_day,
            max_reports_per_day=max_reports_per_day,
            alpha_limit_reason=alpha_limit_reason,
        )
        self.usage_limits[limit.usage_limit_id] = limit
        return limit

    def create_vault(self, client_id: str, vault_id: str | None = None, status: str = "active") -> Vault:
        vault = Vault(
            vault_id=vault_id or f"vault_{uuid4().hex[:10]}",
            client_id=client_id,
            status=status,
            created_at=utc_now(),
        )
        self.vaults[vault.vault_id] = vault
        return vault

    def create_namespace(
        self,
        client_id: str,
        vault_id: str,
        namespace: str = "default",
        status: str = "active",
    ) -> Namespace:
        record = Namespace(
            namespace=namespace,
            vault_id=vault_id,
            client_id=client_id,
            status=status,
            created_at=utc_now(),
        )
        self.namespaces[self.namespace_key(client_id, vault_id, namespace)] = record
        return record

    def create_test_key_record(
        self,
        client_id: str,
        raw_key: str,
        usage_limit_id: str,
        key_id: str | None = None,
        status: str = "active",
    ) -> APIKeyRecord:
        record = APIKeyRecord(
            key_id=key_id or f"key_{uuid4().hex[:10]}",
            client_id=client_id,
            key_hash=safe_hash(raw_key),
            status=status,
            created_at=utc_now(),
            last_used_at=None,
            usage_limit_id=usage_limit_id,
            key_fingerprint=key_fingerprint(raw_key),
        )
        self.api_keys[record.key_id] = record
        return record

    def revoke_key(self, key_id: str) -> None:
        if key_id in self.api_keys:
            self.api_keys[key_id].status = "revoked"

    def rotate_key(self, key_id: str) -> None:
        if key_id in self.api_keys:
            self.api_keys[key_id].status = "rotated"

    def namespace_key(self, client_id: str, vault_id: str, namespace: str) -> str:
        return f"{client_id}::{vault_id}::{namespace}"

    def active_key_for_raw(self, raw_key: str | None) -> APIKeyRecord | None:
        if not raw_key:
            return None
        hashed = safe_hash(raw_key)
        for record in self.api_keys.values():
            if record.key_hash == hashed:
                return record
        return None

    def public_message_for_reason(self, reason: str) -> str:
        messages = {
            "missing_key": "A valid access key is required.",
            "invalid_key": "The provided access key is not valid for this request.",
            "revoked_key": "The provided access key is no longer active.",
            "rotated_key": "The provided access key has been rotated.",
            "client_not_found": "The requested client is not available.",
            "client_not_active": "The requested client is not active.",
            "key_client_mismatch": "The access key is not valid for this client.",
            "vault_denied": "The requested vault is outside the authorized scope.",
            "namespace_denied": "The requested namespace is outside the authorized scope.",
            "usage_limit_exceeded": "The local alpha usage limit has been reached.",
            "operation_invalid": "The requested operation is not supported.",
            "allowed": "Request allowed for the scoped local alpha client.",
        }
        return messages.get(reason, "Request is not allowed.")

    def access_decision(self, allowed: bool, status_code: int, reason: str) -> AccessDecision:
        return AccessDecision(
            allowed=allowed,
            status_code=status_code,
            reason=reason,
            public_safe_message=self.public_message_for_reason(reason),
        )

    def usage_limit_for_key(self, key_record: APIKeyRecord) -> UsageLimit | None:
        return self.usage_limits.get(key_record.usage_limit_id)

    def current_allowed_usage_count(
        self,
        client_id: str,
        vault_id: str,
        namespace: str,
        operation: str,
    ) -> int:
        return sum(
            event.count
            for event in self.usage_ledger
            if event.client_id == client_id
            and event.vault_id == vault_id
            and event.namespace == namespace
            and event.operation == operation
            and event.allowed
        )

    def operation_limit(self, limit: UsageLimit, operation: str) -> int | None:
        if operation == "events_ingest":
            return limit.max_events_per_day
        if operation in {"continuity_packet", "memory_reconstruct", "explain", "least_harm_action"}:
            return limit.max_packets_per_day
        if operation == "report_read":
            return limit.max_reports_per_day
        return None

    def limit_allows(
        self,
        limit: UsageLimit | None,
        client_id: str,
        vault_id: str,
        namespace: str,
        operation: str,
        count: int,
    ) -> bool:
        if limit is None:
            return False
        max_allowed = self.operation_limit(limit, operation)
        if max_allowed is None:
            return True
        current = self.current_allowed_usage_count(client_id, vault_id, namespace, operation)
        return current + count <= max_allowed

    def validate_access(
        self,
        *,
        client_id: str,
        raw_api_key: str | None,
        vault_id: str,
        namespace: str,
        operation: str,
        count: int = 1,
    ) -> AccessDecision:
        if operation not in VALID_OPERATIONS:
            decision = self.access_decision(False, 400, "operation_invalid")
            self.log_request(client_id, operation, decision)
            return decision

        if not raw_api_key:
            decision = self.access_decision(False, 401, "missing_key")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        key_record = self.active_key_for_raw(raw_api_key)
        if key_record is None:
            decision = self.access_decision(False, 401, "invalid_key")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        if key_record.status == "revoked":
            decision = self.access_decision(False, 403, "revoked_key")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        if key_record.status == "rotated":
            decision = self.access_decision(False, 403, "rotated_key")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        if key_record.client_id != client_id:
            decision = self.access_decision(False, 403, "key_client_mismatch")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        client = self.clients.get(client_id)
        if client is None:
            decision = self.access_decision(False, 404, "client_not_found")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        if client.status != "active":
            decision = self.access_decision(False, 403, "client_not_active")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        vault = self.vaults.get(vault_id)
        if vault is None or vault.client_id != client_id or vault.status != "active":
            decision = self.access_decision(False, 403, "vault_denied")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        namespace_record = self.namespaces.get(self.namespace_key(client_id, vault_id, namespace))
        if namespace_record is None or namespace_record.status != "active":
            decision = self.access_decision(False, 403, "namespace_denied")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        limit = self.usage_limit_for_key(key_record)
        if not self.limit_allows(limit, client_id, vault_id, namespace, operation, count):
            decision = self.access_decision(False, 429, "usage_limit_exceeded")
            self.log_request(client_id, operation, decision)
            self.log_usage(client_id, vault_id, namespace, operation, count, False)
            return decision

        key_record.last_used_at = utc_now()
        decision = self.access_decision(True, 200, "allowed")
        self.log_request(client_id, operation, decision)
        self.log_usage(client_id, vault_id, namespace, operation, count, True)
        self.validation_traces.append(
            {
                "timestamp": utc_now(),
                "client_id": client_id,
                "vault_id": vault_id,
                "namespace": namespace,
                "operation": operation,
                "key_id": key_record.key_id,
                "key_fingerprint": key_record.key_fingerprint,
                "decision": asdict(decision),
            }
        )
        return decision

    def log_usage(
        self,
        client_id: str,
        vault_id: str,
        namespace: str,
        operation: str,
        count: int,
        allowed: bool,
    ) -> UsageEvent:
        event = UsageEvent(
            timestamp=utc_now(),
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            operation=operation,
            count=count,
            allowed=allowed,
        )
        self.usage_ledger.append(event)
        return event

    def log_request(self, client_id: str, operation: str, decision: AccessDecision) -> RequestLog:
        record = RequestLog(
            timestamp=utc_now(),
            client_id=client_id,
            operation=operation,
            status="allowed" if decision.allowed else "blocked",
            reason=decision.reason,
            public_safe_message=decision.public_safe_message,
        )
        self.request_log.append(record)
        return record

    def register_report(
        self,
        client_id: str,
        vault_id: str,
        namespace: str,
        report_id: str | None = None,
        report_dir: str = "reports/v069",
    ) -> ContinuityReportRef:
        ref = ContinuityReportRef(
            report_id=report_id or f"report_{uuid4().hex[:12]}",
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            public_report_path=str(Path(report_dir) / "public_hosted_backend_foundation_v069.json"),
            private_report_path=str(Path(report_dir) / "private_internal_hosted_backend_foundation_v069.json"),
            public_safe=True,
        )
        self.report_registry[ref.report_id] = ref
        return ref

    def usage_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "allowed_request_count": 0,
            "blocked_request_count": 0,
            "by_client": {},
            "by_vault": {},
            "by_namespace": {},
        }
        for event in self.usage_ledger:
            if event.allowed:
                summary["allowed_request_count"] += 1
            else:
                summary["blocked_request_count"] += 1
            summary["by_client"].setdefault(event.client_id, 0)
            summary["by_client"][event.client_id] += event.count
            summary["by_vault"].setdefault(event.vault_id, 0)
            summary["by_vault"][event.vault_id] += event.count
            ns_key = self.namespace_key(event.client_id, event.vault_id, event.namespace)
            summary["by_namespace"].setdefault(ns_key, 0)
            summary["by_namespace"][ns_key] += event.count
        return summary

    def public_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for check in checks if check.get("passed"))
        total = len(checks)
        return {
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "version": "0.69",
            "title": "Hosted Backend Foundation / Product Platform Base",
            "result": "PASS" if passed == total else "NEEDS_WORK",
            "public_safe": True,
            "boundary": BOUNDARY_V069,
            "checks_passed": passed,
            "checks_total": total,
            "foundation_objects": [
                "Client",
                "APIKeyRecord",
                "Vault",
                "Namespace",
                "UsageLimit",
                "UsageEvent",
                "RequestLog",
                "ContinuityReportRef",
                "AccessDecision",
            ],
            "registries": [
                "client registry",
                "API key registry",
                "vault registry",
                "namespace registry",
                "usage ledger",
                "request log ledger",
                "report registry",
                "access policy checks",
            ],
            "usage_summary": self.usage_summary(),
            "safe_key_handling": {
                "credential_values_in_public_report": False,
                "stored_key_material": "sha256 hash and short fingerprint only",
                "automatic_real_key_issuing": False,
            },
            "report_boundary": {
                "public_report_safe_summary_only": True,
                "restricted_report_available": True,
            },
        }

    def private_status_report(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            **self.public_status_report(checks),
            "public_safe": False,
            "title": "Hosted Backend Foundation Private Local Trace",
            "checks": checks,
            "clients": {key: asdict(value) for key, value in self.clients.items()},
            "api_key_records": {key: self.safe_key_record_for_private(value) for key, value in self.api_keys.items()},
            "vaults": {key: asdict(value) for key, value in self.vaults.items()},
            "namespaces": {key: asdict(value) for key, value in self.namespaces.items()},
            "usage_limits": {key: asdict(value) for key, value in self.usage_limits.items()},
            "usage_ledger": [asdict(event) for event in self.usage_ledger],
            "request_log": [asdict(record) for record in self.request_log],
            "report_registry": {key: asdict(value) for key, value in self.report_registry.items()},
            "validation_traces": self.validation_traces,
            "private_note": "Private report contains local synthetic validation traces but no raw API keys or real client data.",
        }

    def safe_key_record_for_private(self, record: APIKeyRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["key_hash"] = f"sha256:{record.key_hash[:16]}..."
        return payload


def dataclass_list(items: list[Any]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def scan_public_forbidden_terms(obj: Any) -> list[str]:
    text = repr(obj).lower()
    return [term for term in PUBLIC_FORBIDDEN_TERMS if term.lower() in text]


def scan_unsafe_public_language(obj: Any) -> list[str]:
    text = repr(obj).lower()
    return [term for term in UNSAFE_PUBLIC_LANGUAGE if term.lower() in text]
