"""V0.79 controlled hosted synthetic test scope registration.

This module lets a deployed FastAPI process register one synthetic test scope
from environment variables so hosted protected-route smoke tests can run. Raw
test keys are read from the process environment only; reports and health output
receive safe previews and hash prefixes, never full key values.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from prmr.product.api_key_lifecycle_v070 import LifecycleEvent, LifecycleKeyRecord
from prmr.product.hosted_api_wrapper_v075 import PRMRHostedAPIWrapper
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now


BOUNDARY_V079 = (
    "V0.79 controlled hosted test scope is synthetic hosted smoke support only. "
    "It does not grant real client onboarding, billing, production readiness, "
    "external validation, bank approval, compliance approval, legal approval, "
    "external security certification, or real-world validation."
)

ENABLE_ENV = "PRMR_ENABLE_CONTROLLED_TEST_SCOPE"
TEST_SCOPE_ENV_NAMES = [
    "PRMR_TEST_API_KEY",
    "PRMR_TEST_CLIENT_ID",
    "PRMR_TEST_VAULT_ID",
    "PRMR_TEST_NAMESPACE",
]

TEST_SCOPE_KEY_ID = "key_v079_controlled_hosted_test_scope"
TEST_SCOPE_LIMIT_ID = "limit_v079_controlled_hosted_test_scope"


def enabled_from_env() -> bool:
    return os.getenv(ENABLE_ENV, "").strip().lower() == "true"


def safe_key_preview(raw_key: str | None) -> str | None:
    if not raw_key:
        return None
    suffix = raw_key[-4:] if len(raw_key) >= 4 else "short"
    return f"controlled_test_key_...{suffix}"


def key_hash_prefix(raw_key: str | None) -> str | None:
    if not raw_key:
        return None
    return safe_hash(raw_key)[:12]


def env_snapshot() -> dict[str, Any]:
    values = {name: os.getenv(name, "").strip() for name in TEST_SCOPE_ENV_NAMES}
    missing = [name for name, value in values.items() if not value]
    raw_key = values.get("PRMR_TEST_API_KEY")
    return {
        "enabled": enabled_from_env(),
        "status": "DISABLED" if not enabled_from_env() else ("NEEDS_TEST_SCOPE_CONFIG" if missing else "READY_TO_REGISTER"),
        "missing_env": missing,
        "client_id": values.get("PRMR_TEST_CLIENT_ID") or None,
        "vault_id": values.get("PRMR_TEST_VAULT_ID") or None,
        "namespace": values.get("PRMR_TEST_NAMESPACE") or None,
        "safe_key_preview": safe_key_preview(raw_key),
        "key_hash_prefix": key_hash_prefix(raw_key),
        "raw_key_from_env_only": True,
        "boundary": BOUNDARY_V079,
    }


def register_controlled_test_scope(wrapper: PRMRHostedAPIWrapper) -> dict[str, Any]:
    """Register the synthetic hosted test scope if the env flag is enabled."""

    snapshot = env_snapshot()
    if not snapshot["enabled"]:
        wrapper.runtime["controlled_test_scope_v079"] = snapshot
        return snapshot
    if snapshot["missing_env"]:
        wrapper.runtime["controlled_test_scope_v079"] = snapshot
        return snapshot

    raw_key = os.getenv("PRMR_TEST_API_KEY", "").strip()
    client_id = str(snapshot["client_id"])
    vault_id = str(snapshot["vault_id"])
    namespace = str(snapshot["namespace"])
    lifecycle = wrapper.api.lifecycle

    client = lifecycle.create_client(
        organisation="Synthetic V0.79 Controlled Hosted Test Scope",
        contact_email="synthetic-v079@example.test",
        status="active",
        client_id=client_id,
    )
    limit = lifecycle.create_usage_limit(
        usage_limit_id=TEST_SCOPE_LIMIT_ID,
        max_events_per_day=50,
        max_packets_per_day=50,
        max_reports_per_day=50,
        alpha_limit_reason="V0.79 synthetic hosted protected-route smoke limit.",
    )
    vault = lifecycle.create_vault(client.client_id, vault_id=vault_id, status="active")
    namespace_record = lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace, status="active")

    foundation_record = lifecycle.foundation.create_test_key_record(
        client_id=client.client_id,
        raw_key=raw_key,
        usage_limit_id=limit.usage_limit_id,
        key_id=TEST_SCOPE_KEY_ID,
        status="active",
    )
    lifecycle.lifecycle_keys[TEST_SCOPE_KEY_ID] = LifecycleKeyRecord(
        key_id=TEST_SCOPE_KEY_ID,
        client_id=client.client_id,
        safe_key_preview=str(snapshot["safe_key_preview"]),
        key_hash=foundation_record.key_hash,
        status="active",
        created_at=foundation_record.created_at,
        rotated_at=None,
        revoked_at=None,
        last_used_at=None,
        usage_limit_id=limit.usage_limit_id,
        vault_id=vault.vault_id,
        namespace=namespace_record.namespace,
    )
    lifecycle.lifecycle_events.append(
        LifecycleEvent(
            timestamp=utc_now(),
            event_type="controlled_hosted_test_scope_registered",
            client_id=client.client_id,
            key_id=TEST_SCOPE_KEY_ID,
            operator_id=None,
            reason="registered from controlled hosted test scope environment",
            public_safe_message="Synthetic hosted test scope registered from environment-only test credentials.",
        )
    )
    wrapper.persist_identity_state()

    registered = {
        **snapshot,
        "status": "REGISTERED",
        "missing_env": [],
        "usage_limit_id": limit.usage_limit_id,
        "key_id": TEST_SCOPE_KEY_ID,
        "client": asdict(client),
        "vault": asdict(vault),
        "namespace_record": asdict(namespace_record),
        "raw_key_persisted": False,
        "raw_key_reported": False,
    }
    wrapper.runtime["controlled_test_scope_v079"] = registered
    return registered
