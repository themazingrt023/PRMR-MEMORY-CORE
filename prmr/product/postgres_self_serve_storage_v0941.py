"""Durable Postgres adapter for the PRMR V0.94 self-serve product."""

from __future__ import annotations

import os
from typing import Any

from prmr.product.durable_self_serve_storage_v093 import env_flag
from prmr.product.self_serve_repository_postgres_v0941 import (
    SelfServeRepositoryPostgresV0941,
    initialize_postgres_schema,
)


BOUNDARY_V0941 = (
    "V0.94.1 adds a server-side Postgres persistence option for the self-serve "
    "MVP. Durable hosted persistence is reported only after a database connection "
    "and schema initialization succeed with explicit verification enabled. This "
    "is not real email delivery, Stripe billing, production authentication "
    "hardening, compliance approval, legal approval, or external security "
    "certification."
)


def postgres_storage_status(
    *,
    database_connected: bool,
    durable_storage_verified: bool,
) -> dict[str, Any]:
    durable = bool(database_connected and durable_storage_verified)
    return {
        "storage_backend": "postgres",
        "storage_mode": "hosted_managed_postgres",
        "storage_path_category": "server_side_pooled_database_url",
        "database_connected": bool(database_connected),
        "database_url_exposed": False,
        "durable_storage_verified": durable,
        "durable_storage_claim_allowed": durable,
        "ephemeral_storage": False,
        "local_restart_persistence_supported": False,
        "hosted_storage_boundary": (
            "A Postgres connection and non-destructive schema initialization were verified."
            if durable
            else "Postgres durability has not been verified for this process."
        ),
        "public_safe": True,
        "boundary": BOUNDARY_V0941,
    }


class PostgresSelfServeProductV0941:
    """Persist every mutating V0.92 product operation to Postgres."""

    def __init__(
        self,
        database_url: str,
        *,
        api_mode: str = "hosted_alpha",
        durable_storage_verified: bool = False,
    ) -> None:
        self.api_mode = api_mode
        self.durable_storage_verified = durable_storage_verified
        self.repository = SelfServeRepositoryPostgresV0941(database_url)
        self.product = self.repository.load_product()
        self.storage_status = postgres_storage_status(
            database_connected=True,
            durable_storage_verified=self.durable_storage_verified,
        )

    @classmethod
    def from_environment(cls) -> "PostgresSelfServeProductV0941":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required when PRMR_STORAGE_BACKEND=postgres.")
        return cls(
            database_url,
            api_mode=os.getenv("PRMR_API_MODE", "hosted_alpha"),
            durable_storage_verified=env_flag("PRMR_DURABLE_STORAGE_VERIFIED", False),
        )

    def signup(self, *, name: str, email: str, password: str) -> dict[str, Any]:
        return self._save(self.product.signup(name=name, email=email, password=password))

    def verify_email_local(self, *, user_id: str) -> dict[str, Any]:
        return self._save(self.product.verify_email_local(user_id=user_id))

    def login(self, *, email: str, password: str) -> dict[str, Any]:
        return self._save(self.product.login(email=email, password=password))

    def choose_plan(self, *, session_token: str, plan_id: str) -> dict[str, Any]:
        return self._save(self.product.choose_plan(session_token=session_token, plan_id=plan_id))

    def provision_default_scope(self, *, session_token: str) -> dict[str, Any]:
        return self._save(self.product.provision_default_scope(session_token=session_token))

    def bootstrap_account(self, *, session_token: str, plan_id: str = "free", create_key: bool = True) -> dict[str, Any]:
        return self._save(
            self.product.bootstrap_account(
                session_token=session_token,
                plan_id=plan_id,
                create_key=create_key,
            )
        )

    def create_application(self, **kwargs: Any) -> dict[str, Any]:
        return self._save(self.product.create_application(**kwargs))

    def list_applications(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.list_applications(**kwargs)

    def create_key(self, **kwargs: Any) -> dict[str, Any]:
        return self._save(self.product.create_key(**kwargs))

    def list_keys(self, *, session_token: str) -> dict[str, Any]:
        return self.product.list_keys(session_token=session_token)

    def rotate_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        return self._save(self.product.rotate_key(session_token=session_token, key_id=key_id))

    def revoke_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        return self._save(self.product.revoke_key(session_token=session_token, key_id=key_id))

    def execute(
        self,
        operation: str,
        *,
        api_key: str | None,
        client_id: str,
        vault_id: str,
        namespace: str,
        **payload: Any,
    ) -> dict[str, Any]:
        response = self.product.execute(
            operation,
            api_key=api_key,
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
            **payload,
        )
        return self._save(response)

    def dashboard_state(self, *, session_token: str) -> dict[str, Any]:
        response = self.product.dashboard_state(session_token=session_token)
        if response.get("ok"):
            response["storage"] = self.storage_status
        return response

    def dashboard_request_logs(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_request_logs(**kwargs)

    def dashboard_reports(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_reports(**kwargs)

    def dashboard_report_detail(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_report_detail(**kwargs)

    def dashboard_generate_packet(self, **kwargs: Any) -> dict[str, Any]:
        return self._save(self.product.dashboard_generate_packet(**kwargs))

    def health(self) -> dict[str, Any]:
        counts = self.repository.table_counts()
        return {
            "status": "ok",
            "storage": self.storage_status,
            "persisted_entity_counts": {
                "users": counts["users"],
                "clients": counts["clients"],
                "api_keys": counts["api_keys"],
                "request_logs": counts["api_request_logs"],
                "reports": counts["reports"],
            },
            "raw_key_storage": False,
            "raw_password_storage": False,
            "boundary": BOUNDARY_V0941,
        }

    def _save(self, response: dict[str, Any]) -> dict[str, Any]:
        self.repository.save_product(self.product)
        return response


__all__ = [
    "BOUNDARY_V0941",
    "PostgresSelfServeProductV0941",
    "initialize_postgres_schema",
    "postgres_storage_status",
]
