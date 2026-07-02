"""V0.92 approved-client provisioning for Continuum OS.

Continuum OS is provisioned as a separate PRMR client. A fresh alpha key is
held in memory until a one-time private environment packet is requested. Public
state exposes only a safe preview.
"""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import (
    LifecycleEvent,
    LifecycleKeyRecord,
    PRMRAPIKeyLifecycle,
)
from prmr.product.controlled_alpha_api_v071 import PRMRControlledAlphaAPI
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now


BOUNDARY_V092 = (
    "V0.92 is first internal-client provisioning evidence for Continuum OS "
    "using synthetic events and local protected PRMR logic. It is not open "
    "public signup, automatic billing, production authentication, compliance "
    "approval, or external security certification. The generated key is not "
    "usable against the hosted backend until its hashed record is installed in "
    "durable hosted PRMR storage and a hosted scoped smoke passes."
)

API_BASE_URL = "https://prmr-memory-core-api.onrender.com"
CLIENT_ID = "client_continuum_os"
VAULT_ID = "vault_continuum_os"
NAMESPACE = "default"
PRODUCT_NAME = "Continuum OS"
CLIENT_STATUS = "approved_internal_client"


@dataclass
class ContinuumProvisioningRecord:
    provisioning_id: str
    client_id: str
    product_name: str
    status: str
    access_runtime_status: str
    vault_id: str
    namespace: str
    usage_limit_id: str
    key_id: str
    safe_key_preview: str
    key_hash: str
    created_at: str
    synthetic_only: bool
    one_time_packet_released_at: str | None
    hosted_key_registration_verified: bool


class ContinuumClientProvisioningV092:
    """Provision and exercise Continuum OS as an independent PRMR client."""

    def __init__(self) -> None:
        self.api = PRMRControlledAlphaAPI()
        self.lifecycle: PRMRAPIKeyLifecycle = self.api.lifecycle
        self.records: dict[str, ContinuumProvisioningRecord] = {}
        self._one_time_keys: dict[str, str] = {}
        self.release_log: list[dict[str, Any]] = []

    def provision(self) -> dict[str, Any]:
        provisioning_id = f"provision_v092_{uuid4().hex[:10]}"
        usage_limit_id = f"limit_v092_{uuid4().hex[:8]}"
        client = self.lifecycle.create_client(
            organisation=PRODUCT_NAME,
            contact_email="continuum-os-internal@example.test",
            status="active",
            client_id=CLIENT_ID,
        )
        limit = self.lifecycle.create_usage_limit(
            usage_limit_id=usage_limit_id,
            max_events_per_day=250,
            max_packets_per_day=100,
            max_reports_per_day=100,
            alpha_limit_reason="V0.92 Continuum OS internal synthetic alpha limit.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=VAULT_ID, status="active")
        namespace = self.lifecycle.create_namespace(
            client.client_id,
            vault.vault_id,
            namespace=NAMESPACE,
            status="active",
        )

        raw_key = f"prmr_alpha_{secrets.token_urlsafe(32)}"
        key_id = f"key_v092_{uuid4().hex[:12]}"
        key_record = LifecycleKeyRecord(
            key_id=key_id,
            client_id=CLIENT_ID,
            safe_key_preview=f"prmr_alpha_...{raw_key[-4:]}",
            key_hash=safe_hash(raw_key),
            status="active",
            created_at=utc_now(),
            rotated_at=None,
            revoked_at=None,
            last_used_at=None,
            usage_limit_id=limit.usage_limit_id,
            vault_id=VAULT_ID,
            namespace=NAMESPACE,
        )
        self.lifecycle.lifecycle_keys[key_id] = key_record
        self.lifecycle.foundation.create_test_key_record(
            client_id=CLIENT_ID,
            raw_key=raw_key,
            usage_limit_id=limit.usage_limit_id,
            key_id=key_id,
            status="active",
        )
        self.lifecycle.lifecycle_events.append(
            LifecycleEvent(
                timestamp=utc_now(),
                event_type="continuum_internal_key_issued",
                client_id=CLIENT_ID,
                key_id=key_id,
                operator_id="operator_v092_founder",
                reason="Approved Continuum OS as the first separate internal PRMR client.",
                public_safe_message="Continuum OS internal alpha client scope created with a copy-once key.",
            )
        )
        record = ContinuumProvisioningRecord(
            provisioning_id=provisioning_id,
            client_id=CLIENT_ID,
            product_name=PRODUCT_NAME,
            status=CLIENT_STATUS,
            access_runtime_status=client.status,
            vault_id=vault.vault_id,
            namespace=namespace.namespace,
            usage_limit_id=limit.usage_limit_id,
            key_id=key_id,
            safe_key_preview=key_record.safe_key_preview,
            key_hash=key_record.key_hash,
            created_at=utc_now(),
            synthetic_only=True,
            one_time_packet_released_at=None,
            hosted_key_registration_verified=False,
        )
        self.records[provisioning_id] = record
        self._one_time_keys[provisioning_id] = raw_key
        return {
            "ok": True,
            "status_code": 201,
            "provisioning_id": provisioning_id,
            "client": self.public_record(record),
            "one_time_env_packet_available": True,
            "credential_value_returned": False,
            "boundary": BOUNDARY_V092,
        }

    def one_time_env_packet(self, provisioning_id: str) -> dict[str, Any]:
        record = self.records[provisioning_id]
        raw_key = self._one_time_keys.pop(provisioning_id, None)
        if raw_key is not None:
            record.one_time_packet_released_at = utc_now()
        self.release_log.append(
            {
                "timestamp": utc_now(),
                "provisioning_id": provisioning_id,
                "key_id": record.key_id,
                "credential_released": raw_key is not None,
            }
        )
        return {
            "version": "0.92",
            "packet_type": "private_continuum_env_packet",
            "classification": "PRIVATE LOCAL ONLY. DO NOT COMMIT. DO NOT SHARE.",
            "public_safe": False,
            "local_private_only": True,
            "do_not_commit": True,
            "do_not_share": True,
            "returned_once": raw_key is not None,
            "PRMR_API_BASE_URL": API_BASE_URL,
            "PRMR_API_KEY": raw_key,
            "PRMR_CLIENT_ID": record.client_id,
            "PRMR_VAULT_ID": record.vault_id,
            "PRMR_NAMESPACE": record.namespace,
            "safe_key_preview": record.safe_key_preview,
            "key_id": record.key_id,
            "hosted_key_registration_verified": False,
            "activation_warning": (
                "Do not wire this packet into Continuum OS yet. The local key "
                "must first be installed in durable hosted PRMR storage and pass "
                "a hosted scoped smoke."
            ),
            "boundary": BOUNDARY_V092,
        }

    def validate_key(self, raw_key: str | None, operation: str = "events_ingest") -> dict[str, Any]:
        decision = self.lifecycle.validate_key(
            client_id=CLIENT_ID,
            raw_api_key=raw_key,
            vault_id=VAULT_ID,
            namespace=NAMESPACE,
            operation=operation,
        )
        return {
            "allowed": decision.allowed,
            "status_code": decision.status_code,
            "reason": decision.reason,
            "public_safe_message": decision.public_safe_message,
        }

    def public_record(self, record: ContinuumProvisioningRecord) -> dict[str, Any]:
        return {
            "provisioning_id": record.provisioning_id,
            "client_id": record.client_id,
            "product_name": record.product_name,
            "status": record.status,
            "vault_id": record.vault_id,
            "namespace": record.namespace,
            "key_id": record.key_id,
            "safe_key_preview": record.safe_key_preview,
            "synthetic_only": record.synthetic_only,
            "hosted_key_registration_verified": record.hosted_key_registration_verified,
        }

    def private_record(self, record: ContinuumProvisioningRecord) -> dict[str, Any]:
        return asdict(record)

    def dashboard_state(self) -> dict[str, Any]:
        record = next(iter(self.records.values()))
        key = self.lifecycle.lifecycle_keys[record.key_id]
        request_logs = [
            {
                "timestamp": row.timestamp,
                "endpoint": row.endpoint,
                "status": row.status,
                "reason": row.reason,
                "public_safe_message": row.public_safe_message,
            }
            for row in self.api.api_request_log
            if row.client_id == CLIENT_ID
        ]
        reports = [
            {
                "report_id": report["report_id"],
                "client_id": report["client_id"],
                "vault_id": report["vault_id"],
                "namespace": report["namespace"],
                "public_safe": report["public_safe"],
            }
            for report in self.api.public_reports.values()
            if report["client_id"] == CLIENT_ID
        ]
        event_count = len(self.api.events.get(self.api.scope_key(CLIENT_ID, VAULT_ID, NAMESPACE), []))
        return {
            "client_overview": self.public_record(record),
            "api_keys": [
                {
                    "key_id": key.key_id,
                    "safe_key_preview": key.safe_key_preview,
                    "status": key.status,
                    "last_used_at": key.last_used_at,
                }
            ],
            "vaults_and_namespaces": [
                {"vault_id": VAULT_ID, "namespace": NAMESPACE, "status": "active"}
            ],
            "usage": self.lifecycle.get_client_usage(CLIENT_ID),
            "request_logs": request_logs,
            "reports": reports,
            "memory_health": {
                "event_count": event_count,
                "packet_count": len(
                    [packet for packet in self.api.packets.values() if packet["client_id"] == CLIENT_ID]
                ),
                "report_count": len(reports),
                "reconstructable": bool(self.api.packets),
            },
            "credential_values_exposed": False,
            "boundary": BOUNDARY_V092,
        }

