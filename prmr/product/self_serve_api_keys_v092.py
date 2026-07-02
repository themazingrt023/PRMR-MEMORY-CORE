"""Generic client provisioning and copy-once API keys for V0.92."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from prmr.product.api_key_lifecycle_v070 import LifecycleKeyRecord
from prmr.product.controlled_alpha_api_v071 import PRMRControlledAlphaAPI
from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now
from prmr.product.self_serve_accounts_v092 import SelfServeAccount, SelfServeAccountsV092
from prmr.product.self_serve_plans_v092 import PlanDefinition, SelfServePlansV092


KEY_BOUNDARY_V092 = (
    "V0.92 provides generic local/deployable self-serve client scopes and "
    "copy-once alpha keys. Hosted durable registry deployment and production "
    "authentication remain separate work."
)


@dataclass
class SelfServeClientScope:
    user_id: str
    client_id: str
    vault_id: str
    namespace: str
    usage_limit_id: str
    plan_id: str
    status: str
    created_at: str


class SelfServeAPIKeysV092:
    def __init__(
        self,
        *,
        api: PRMRControlledAlphaAPI,
        accounts: SelfServeAccountsV092,
        plans: SelfServePlansV092,
    ) -> None:
        self.api = api
        self.lifecycle = api.lifecycle
        self.accounts = accounts
        self.plans = plans
        self.scopes_by_user: dict[str, SelfServeClientScope] = {}
        self.user_by_client: dict[str, str] = {}
        self.key_labels: dict[str, str] = {}

    def provision_default_scope(self, *, session_token: str) -> dict[str, Any]:
        account = self.accounts.validate_session(session_token)
        if account is None:
            return self.error(401, "valid_session_required")
        existing = self.scopes_by_user.get(account.user_id)
        if existing:
            return {"ok": True, "status_code": 200, "scope": self.public_scope(existing), "created": False}
        plan = self.plans.active_plan(account.user_id)
        if plan is None:
            return self.error(403, "active_plan_required")

        client_id = f"client_ss_{uuid4().hex[:12]}"
        vault_id = f"vault_ss_{uuid4().hex[:12]}"
        namespace = "default"
        usage_limit_id = f"limit_ss_{uuid4().hex[:10]}"
        client = self.lifecycle.create_client(
            organisation=account.name,
            contact_email=account.email,
            status="active",
            client_id=client_id,
        )
        legacy_limit = max(100, plan.requests_per_month or 100_000)
        self.lifecycle.create_usage_limit(
            usage_limit_id=usage_limit_id,
            max_events_per_day=legacy_limit,
            max_packets_per_day=legacy_limit,
            max_reports_per_day=legacy_limit,
            alpha_limit_reason=f"V0.92 {plan.plan_id} plan; monthly quota enforced by self-serve plan service.",
        )
        vault = self.lifecycle.create_vault(client.client_id, vault_id=vault_id, status="active")
        self.lifecycle.create_namespace(client.client_id, vault.vault_id, namespace=namespace, status="active")
        scope = SelfServeClientScope(
            user_id=account.user_id,
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            usage_limit_id=usage_limit_id,
            plan_id=plan.plan_id,
            status="active",
            created_at=utc_now(),
        )
        self.scopes_by_user[account.user_id] = scope
        self.user_by_client[client_id] = account.user_id
        return {
            "ok": True,
            "status_code": 201,
            "scope": self.public_scope(scope),
            "created": True,
            "boundary": KEY_BOUNDARY_V092,
        }

    def create_key(self, *, session_token: str, label: str) -> dict[str, Any]:
        account, scope, plan, error = self.authorized_context(session_token)
        if error:
            return error
        assert account and scope and plan
        clean_label = " ".join(label.split()).strip()
        if not 2 <= len(clean_label) <= 64:
            return self.error(400, "invalid_key_label")
        active_count = sum(
            1
            for record in self.lifecycle.lifecycle_keys.values()
            if record.client_id == scope.client_id and record.status == "active"
        )
        if active_count >= plan.max_active_keys:
            return self.error(409, "active_key_limit_reached")
        return self._create_key(account=account, scope=scope, label=clean_label)

    def _create_key(
        self,
        *,
        account: SelfServeAccount,
        scope: SelfServeClientScope,
        label: str,
    ) -> dict[str, Any]:
        raw_key = f"prmr_alpha_{secrets.token_urlsafe(32)}"
        key_id = f"key_ss_{uuid4().hex[:12]}"
        subscription = self.plans.subscriptions[account.user_id]
        record = LifecycleKeyRecord(
            key_id=key_id,
            client_id=scope.client_id,
            safe_key_preview=f"prmr_alpha_...{raw_key[-4:]}",
            key_hash=safe_hash(raw_key),
            status="active",
            created_at=utc_now(),
            rotated_at=None,
            revoked_at=None,
            last_used_at=None,
            usage_limit_id=scope.usage_limit_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
        )
        self.lifecycle.lifecycle_keys[key_id] = record
        self.lifecycle.foundation.create_test_key_record(
            client_id=scope.client_id,
            raw_key=raw_key,
            usage_limit_id=scope.usage_limit_id,
            key_id=key_id,
            status="active",
        )
        self.key_labels[key_id] = label
        return {
            "ok": True,
            "status_code": 201,
            "key_id": key_id,
            "label": label,
            "raw_api_key": raw_key,
            "safe_key_preview": record.safe_key_preview,
            "returned_once": True,
            "copy_warning": "Copy this key now. PRMR will not show it again.",
            "plan_id": subscription.plan_id,
            "boundary": KEY_BOUNDARY_V092,
        }

    def list_keys(self, *, session_token: str) -> dict[str, Any]:
        account, scope, _, error = self.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        keys = [
            {
                "key_id": record.key_id,
                "label": self.key_labels.get(record.key_id, "Unlabelled key"),
                "safe_key_preview": record.safe_key_preview,
                "status": record.status,
                "created_at": record.created_at,
                "last_used_at": record.last_used_at,
                "client_id": record.client_id,
                "vault_id": record.vault_id,
                "namespace": record.namespace,
            }
            for record in self.lifecycle.lifecycle_keys.values()
            if record.client_id == scope.client_id
        ]
        return {
            "ok": True,
            "status_code": 200,
            "keys": keys,
            "credential_values_returned": False,
            "safe_previews_only": True,
        }

    def rotate_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        account, scope, _, error = self.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        record = self.lifecycle.lifecycle_keys.get(key_id)
        if record is None or record.client_id != scope.client_id or record.status != "active":
            return self.error(404, "active_key_not_found")
        record.status = "rotated"
        record.rotated_at = utc_now()
        self.lifecycle.foundation.rotate_key(key_id)
        replacement = self._create_key(
            account=account,
            scope=scope,
            label=self.key_labels.get(key_id, "Rotated key"),
        )
        return {
            **replacement,
            "status_code": 200,
            "old_key_id": key_id,
            "new_key_id": replacement["key_id"],
        }

    def revoke_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        _, scope, _, error = self.authorized_context(session_token)
        if error:
            return error
        assert scope
        record = self.lifecycle.lifecycle_keys.get(key_id)
        if record is None or record.client_id != scope.client_id:
            return self.error(404, "key_not_found")
        record.status = "revoked"
        record.revoked_at = utc_now()
        self.lifecycle.foundation.revoke_key(key_id)
        return {"ok": True, "status_code": 200, "key_id": key_id, "status": "revoked"}

    def preflight_key(self, *, raw_key: str | None, client_id: str) -> tuple[bool, str]:
        record = self.lifecycle.find_lifecycle_key_by_raw(raw_key)
        if record is None:
            return False, "invalid_key" if raw_key else "missing_key"
        if record.client_id != client_id:
            return False, "key_client_mismatch"
        if record.status != "active":
            return False, f"{record.status}_key"
        return True, "allowed"

    def public_scope(self, scope: SelfServeClientScope) -> dict[str, Any]:
        return {
            "user_id": scope.user_id,
            "client_id": scope.client_id,
            "vault_id": scope.vault_id,
            "namespace": scope.namespace,
            "usage_limit_id": scope.usage_limit_id,
            "plan_id": scope.plan_id,
            "status": scope.status,
            "created_at": scope.created_at,
        }

    def authorized_context(
        self,
        session_token: str,
    ) -> tuple[SelfServeAccount | None, SelfServeClientScope | None, PlanDefinition | None, dict[str, Any] | None]:
        account = self.accounts.validate_session(session_token)
        if account is None:
            return None, None, None, self.error(401, "valid_session_required")
        scope = self.scopes_by_user.get(account.user_id)
        if scope is None:
            return account, None, None, self.error(404, "client_scope_not_provisioned")
        plan = self.plans.active_plan(account.user_id)
        if plan is None:
            return account, scope, None, self.error(403, "active_plan_required")
        return account, scope, plan, None

    def error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "error": {"code": code},
            "boundary": KEY_BOUNDARY_V092,
        }
