"""V0.80 manual client onboarding and safe alpha key issuing.

This is a founder/operator-controlled local workflow for synthetic/manual
alpha onboarding. It is not self-serve signup, billing, automatic access, or
production onboarding. Raw generated key values are available only through a
one-time private packet method.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import PRMRAPIKeyLifecycle
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now


BOUNDARY_V080 = (
    "V0.80 is a local/manual controlled-alpha onboarding workflow. It supports "
    "founder/operator-created synthetic alpha clients and one-time private key "
    "delivery evidence. It is not self-serve signup, billing, automatic access, "
    "production readiness, external validation, bank approval, compliance "
    "approval, legal approval, external security certification, or real-world "
    "validation."
)

ONBOARDING_STATUSES = {"pending_manual_delivery", "delivered", "revoked", "archived"}


@dataclass
class ManualOnboardingRecord:
    onboarding_id: str
    client_id: str
    organisation: str
    contact_email: str
    vault_id: str
    namespace: str
    usage_limit_id: str
    key_id: str
    safe_key_preview: str
    key_hash_prefix: str
    status: str
    created_at: str
    delivered_at: str | None
    revoked_at: str | None
    archived_at: str | None
    synthetic_only: bool
    boundary: str


class ManualClientOnboarding:
    """Manual alpha client onboarding wrapper around the key lifecycle layer."""

    def __init__(self) -> None:
        self.lifecycle = PRMRAPIKeyLifecycle()
        self.records: dict[str, ManualOnboardingRecord] = {}
        self._one_time_credentials: dict[str, str] = {}
        self.one_time_release_log: list[dict[str, Any]] = []

    def create_manual_alpha_client(
        self,
        *,
        organisation: str = "Synthetic V0.80 Manual Alpha Client",
        contact_email: str = "synthetic-v080@example.test",
        client_id: str | None = None,
        vault_id: str | None = None,
        namespace: str = "default",
        operator_id: str = "operator_v080_founder",
        approval_reason: str = "approved for synthetic/manual controlled-alpha onboarding test",
    ) -> dict[str, Any]:
        """Create client, vault, namespace, usage limit, and one fresh key."""

        selected_client_id = client_id or f"client_v080_{uuid4().hex[:8]}"
        selected_vault_id = vault_id or f"vault_v080_{uuid4().hex[:8]}"
        usage_limit_id = f"limit_v080_{uuid4().hex[:8]}"
        onboarding_id = f"onboarding_v080_{uuid4().hex[:10]}"

        client = self.lifecycle.create_client(
            organisation=organisation,
            contact_email=contact_email,
            status="active",
            client_id=selected_client_id,
        )
        usage_limit = self.lifecycle.create_usage_limit(
            usage_limit_id=usage_limit_id,
            max_events_per_day=20,
            max_packets_per_day=20,
            max_reports_per_day=20,
            alpha_limit_reason="V0.80 manual controlled-alpha safety limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=selected_vault_id, status="active")
        namespace_record = self.lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace, status="active")
        issue = self.lifecycle.issue_alpha_key(
            client_id=client.client_id,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=usage_limit.usage_limit_id,
            operator_id=operator_id,
            approval_reason=approval_reason,
        )
        raw_key = str(issue["raw_api_key"])
        record = ManualOnboardingRecord(
            onboarding_id=onboarding_id,
            client_id=client.client_id,
            organisation=client.organisation,
            contact_email=client.contact_email,
            vault_id=vault.vault_id,
            namespace=namespace_record.namespace,
            usage_limit_id=usage_limit.usage_limit_id,
            key_id=str(issue["key_id"]),
            safe_key_preview=str(issue["safe_key_preview"]),
            key_hash_prefix=safe_hash(raw_key)[:12],
            status="pending_manual_delivery",
            created_at=utc_now(),
            delivered_at=None,
            revoked_at=None,
            archived_at=None,
            synthetic_only=True,
            boundary=BOUNDARY_V080,
        )
        self.records[onboarding_id] = record
        self._one_time_credentials[onboarding_id] = raw_key
        return {
            "ok": True,
            "onboarding_id": onboarding_id,
            "record": asdict(record),
            "one_time_key_available": True,
            "credential_value_returned_here": False,
            "public_safe": False,
            "boundary": BOUNDARY_V080,
        }

    def one_time_key_packet(self, onboarding_id: str) -> dict[str, Any]:
        """Return the raw key once for private/local delivery, then consume it."""

        record = self.records[onboarding_id]
        raw_key = self._one_time_credentials.pop(onboarding_id, None)
        packet = {
            "version": "0.80",
            "packet_type": "private_local_one_time_alpha_key_packet",
            "public_safe": False,
            "local_private_only": True,
            "do_not_commit": True,
            "onboarding_id": onboarding_id,
            "client_id": record.client_id,
            "vault_id": record.vault_id,
            "namespace": record.namespace,
            "key_id": record.key_id,
            "safe_key_preview": record.safe_key_preview,
            "key_hash_prefix": record.key_hash_prefix,
            "alpha_api_key": raw_key,
            "credential_value_present": raw_key is not None,
            "returned_once": raw_key is not None,
            "boundary": BOUNDARY_V080,
            "delivery_note": "Deliver through a private approved channel only. Do not paste into public reports, commits, screenshots, or shared docs.",
        }
        self.one_time_release_log.append(
            {
                "timestamp": utc_now(),
                "onboarding_id": onboarding_id,
                "key_id": record.key_id,
                "credential_value_released": raw_key is not None,
            }
        )
        return packet

    def mark_delivered(self, onboarding_id: str, *, operator_id: str, delivery_note: str) -> dict[str, Any]:
        record = self.records[onboarding_id]
        record.status = "delivered"
        record.delivered_at = utc_now()
        return {
            "ok": True,
            "onboarding_id": onboarding_id,
            "status": record.status,
            "operator_id": operator_id,
            "delivery_note": delivery_note,
            "public_safe": False,
        }

    def revoke(self, onboarding_id: str, *, operator_id: str, reason: str) -> dict[str, Any]:
        record = self.records[onboarding_id]
        result = self.lifecycle.revoke_key(key_id=record.key_id, operator_id=operator_id, revoke_reason=reason)
        if result.get("ok"):
            record.status = "revoked"
            record.revoked_at = utc_now()
            self._one_time_credentials.pop(onboarding_id, None)
        return {"onboarding_id": onboarding_id, **result}

    def archive(self, onboarding_id: str, *, operator_id: str, reason: str) -> dict[str, Any]:
        record = self.records[onboarding_id]
        record.status = "archived"
        record.archived_at = utc_now()
        self._one_time_credentials.pop(onboarding_id, None)
        return {"ok": True, "onboarding_id": onboarding_id, "status": "archived", "operator_id": operator_id, "reason": reason}

    def validate_key(
        self,
        *,
        onboarding_id: str,
        raw_key: str | None,
        operation: str = "events_ingest",
        count: int = 1,
    ) -> dict[str, Any]:
        record = self.records[onboarding_id]
        decision = self.lifecycle.validate_key(
            client_id=record.client_id,
            raw_api_key=raw_key,
            vault_id=record.vault_id,
            namespace=record.namespace,
            operation=operation,
            count=count,
        )
        return {
            "allowed": decision.allowed,
            "status_code": decision.status_code,
            "reason": decision.reason,
            "public_safe_message": decision.public_safe_message,
        }

    def public_onboarding_summary(self, checks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        checks = checks or []
        passed = sum(1 for check in checks if check.get("passed"))
        total = len(checks)
        return {
            "version": "0.80",
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "title": "Manual Client Onboarding And Safe Alpha Key Issuing",
            "result": "PASS" if checks and passed == total else "NEEDS_WORK",
            "checks_passed": passed,
            "checks_total": total,
            "public_safe": True,
            "boundary": BOUNDARY_V080,
            "workflow": {
                "manual_operator_approval_required": True,
                "self_serve_signup": False,
                "billing_enabled": False,
                "automatic_access": False,
                "synthetic_only_default": True,
                "credential_value_in_public_report": False,
                "one_time_private_key_packet_created": bool(self.one_time_release_log),
            },
            "onboarding_records": [
                {
                    "onboarding_id": record.onboarding_id,
                    "client_id": record.client_id,
                    "vault_id": record.vault_id,
                    "namespace": record.namespace,
                    "key_id": record.key_id,
                    "safe_key_preview": record.safe_key_preview,
                    "key_hash_prefix": record.key_hash_prefix,
                    "status": record.status,
                    "synthetic_only": record.synthetic_only,
                }
                for record in self.records.values()
            ],
        }

    def private_onboarding_report(self, checks: list[dict[str, Any]], trace: dict[str, Any]) -> dict[str, Any]:
        return {
            **self.public_onboarding_summary(checks),
            "public_safe": False,
            "title": "Manual Client Onboarding Private Local Trace",
            "checks": checks,
            "records": [asdict(record) for record in self.records.values()],
            "one_time_release_log": self.one_time_release_log,
            "validation_outcomes": self.lifecycle.validation_outcomes,
            "trace": trace,
            "restricted_note": "Private trace excludes the raw key except for the separate private one-time packet.",
        }
