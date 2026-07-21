"""Durable SQLite adapter for the PRMR V0.92 self-serve product."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from prmr.product.self_serve_dashboard_v092 import SelfServeDashboardV092
from prmr.product.self_serve_repository_v093 import SelfServeRepositoryV093
from prmr.product.storage_mode_v083 import classify_storage_mode


BOUNDARY_V093 = (
    "V0.93 provides durable SQLite persistence and restart/reload evidence for "
    "the self-serve product. Hosted durability is claimed only for a durable-path "
    "classification with explicit verification. This is not production auth, "
    "real email delivery, payment integration, compliance approval, legal "
    "approval, or external security certification."
)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def storage_status_v093(
    *,
    storage_path: str | Path | None,
    api_mode: str,
    durable_storage_verified: bool,
) -> dict[str, Any]:
    classification = classify_storage_mode(
        storage_path=storage_path,
        api_mode=api_mode,
        durable_storage_verified=durable_storage_verified,
    )
    mode = classification["storage_mode"]
    categories = {
        "local_sqlite": "local_development_sqlite",
        "hosted_ephemeral_sqlite": "ephemeral_smoke_only",
        "hosted_durable_sqlite": "hosted_persistent_path_candidate",
        "hosted_managed_database_planned": "managed_database_future",
        "unknown_storage_mode": "unsafe_or_incomplete",
    }
    return {
        "storage_backend": "sqlite",
        "storage_mode": mode,
        "storage_path_category": categories[mode],
        "durable_storage_verified": classification["durable_storage_verified"],
        "durable_storage_claim_allowed": classification["durable_storage_claim_allowed"],
        "ephemeral_storage": classification["ephemeral_storage"],
        "tmp_warning": (
            "Configured /tmp storage is ephemeral and must not be presented as durable."
            if classification["ephemeral_storage"]
            else None
        ),
        "local_restart_persistence_supported": mode == "local_sqlite",
        "hosted_storage_boundary": classification["hosted_storage_boundary"],
        "public_safe": True,
        "boundary": BOUNDARY_V093,
    }


class DurableSelfServeProductV093:
    """Persist every mutating V0.92 product operation to SQLite."""

    def __init__(
        self,
        storage_path: str | Path,
        *,
        api_mode: str = "local_alpha",
        durable_storage_verified: bool = False,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.api_mode = api_mode
        self.durable_storage_verified = durable_storage_verified
        self.repository = SelfServeRepositoryV093(self.storage_path)
        self.product = self.repository.load_product()
        self.storage_status = storage_status_v093(
            storage_path=self.storage_path,
            api_mode=self.api_mode,
            durable_storage_verified=self.durable_storage_verified,
        )

    @classmethod
    def from_environment(cls) -> "DurableSelfServeProductV093":
        path = os.getenv("PRMR_SELF_SERVE_STORAGE_PATH", "").strip()
        if not path:
            raise ValueError("PRMR_SELF_SERVE_STORAGE_PATH is required.")
        return cls(
            path,
            api_mode=os.getenv("PRMR_API_MODE", "local_alpha"),
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

    def dashboard_events(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_events(**kwargs)

    def dashboard_packets(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_packets(**kwargs)

    def dashboard_packet_detail(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_packet_detail(**kwargs)

    def dashboard_actors(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_actors(**kwargs)

    def dashboard_usage(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_usage(**kwargs)

    def dashboard_playground_event(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_playground_event(**kwargs)

    def dashboard_playground_packet(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_playground_packet(**kwargs)

    def dashboard_playground_reset(self, **kwargs: Any) -> dict[str, Any]:
        return self.product.dashboard_playground_reset(**kwargs)

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
            "boundary": BOUNDARY_V093,
        }

    def _save(self, response: dict[str, Any]) -> dict[str, Any]:
        self.repository.save_product(self.product)
        return response
