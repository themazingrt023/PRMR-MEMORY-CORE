"""V0.82 hosted dashboard connection adapter.

This adapter models the safe dashboard-session path for a hosted dashboard
state request. It uses V0.81 dashboard auth and accepts deployable-style
headers, but it is still controlled synthetic evidence rather than production
login.
"""

from __future__ import annotations

import json
import re
from typing import Any

from prmr.product.dashboard_auth_v081 import BOUNDARY_V081, DashboardAuthV081


BOUNDARY_V082 = (
    "V0.82 is hosted dashboard connection evidence only. It proves a safe "
    "frontend/backend dashboard-state bridge can be scoped with synthetic "
    "dashboard session access. It is not production login, self-serve dashboard "
    "access, billing, external validation, bank approval, compliance approval, "
    "legal approval, external security certification, or real-world validation."
)

REQUIRED_HEADERS = ["X-Dashboard-Token", "X-Client-ID"]


class HostedDashboardConnectionV082:
    """Deployable-style adapter for dashboard-token-scoped state access."""

    def __init__(self) -> None:
        self.auth = DashboardAuthV081()
        self.runtime: dict[str, Any] = {}

    def response(self, status_code: int, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "status_code": status_code,
            "body": {
                "public_safe": True,
                "boundary": BOUNDARY_V082,
                **body,
            },
        }

    def provision_synthetic_demo_scope(self) -> dict[str, Any]:
        client_a = self.auth.create_client_scope(
            client_id="client_v082_alpha_a",
            organisation="Synthetic V0.82 Alpha Client A",
            contact_email="synthetic-a-v082@example.test",
            vault_id="vault_v082_alpha_a",
        )
        client_b = self.auth.create_client_scope(
            client_id="client_v082_alpha_b",
            organisation="Synthetic V0.82 Alpha Client B",
            contact_email="synthetic-b-v082@example.test",
            vault_id="vault_v082_alpha_b",
        )
        self.auth.record_synthetic_activity(
            client_id=client_a["client"]["client_id"],
            vault_id=client_a["vault"]["vault_id"],
            namespace=client_a["namespace"]["namespace"],
            raw_api_key=client_a["raw_api_key"],
        )
        self.auth.record_synthetic_activity(
            client_id=client_b["client"]["client_id"],
            vault_id=client_b["vault"]["vault_id"],
            namespace=client_b["namespace"]["namespace"],
            raw_api_key=client_b["raw_api_key"],
        )
        session_a = self.auth.create_dashboard_session(client_id=client_a["client"]["client_id"])
        self.runtime = {
            "client_a": {
                "client_id": client_a["client"]["client_id"],
                "vault_id": client_a["vault"]["vault_id"],
                "namespace": client_a["namespace"]["namespace"],
                "safe_key_preview": client_a["issue"]["safe_key_preview"],
                "key_hash_prefix": client_a["issue"]["key_hash_prefix"],
            },
            "client_b": {
                "client_id": client_b["client"]["client_id"],
                "vault_id": client_b["vault"]["vault_id"],
                "namespace": client_b["namespace"]["namespace"],
                "safe_key_preview": client_b["issue"]["safe_key_preview"],
                "key_hash_prefix": client_b["issue"]["key_hash_prefix"],
            },
            "session_a": {
                "session_id": session_a["session_id"],
                "safe_token_preview": session_a["safe_token_preview"],
                "raw_token_available_for_runner_only": True,
            },
            "boundary": BOUNDARY_V082,
        }
        return {
            "client_a": client_a,
            "client_b": client_b,
            "session_a": session_a,
            "safe_runtime": self.runtime,
        }

    def get_dashboard_state(self, headers: dict[str, str]) -> dict[str, Any]:
        token = str(headers.get("X-Dashboard-Token") or "").strip()
        client_id = str(headers.get("X-Client-ID") or "").strip()
        if not token:
            return self.response(
                401,
                {
                    "status": "error",
                    "error": {"code": "missing_dashboard_token", "message": "A dashboard session token is required."},
                },
            )
        if not client_id:
            return self.response(
                400,
                {
                    "status": "error",
                    "error": {"code": "missing_client_id", "message": "A client ID is required for dashboard state."},
                },
            )
        state = self.auth.dashboard_state(raw_token=token, requested_client_id=client_id)
        if state["status"] != "ok":
            return self.response(
                int(state["status_code"]),
                {
                    "status": "error",
                    "error": state["error"],
                },
            )
        return self.response(
            200,
            {
                "status": "ok",
                "dashboard": state["dashboard"],
                "dashboard_connection": {
                    "source": "hosted_dashboard_connection_v082",
                    "raw_dashboard_token_returned": False,
                    "raw_api_keys_returned": False,
                    "client_scoped": True,
                },
            },
        )

    def revoke_session(self, session_id: str) -> dict[str, Any]:
        return self.auth.revoke_session(session_id=session_id)


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v08[12]_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def public_dashboard_summary(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {})
    dashboard = body.get("dashboard", {}) if isinstance(body, dict) else {}
    return {
        "status_code": result.get("status_code"),
        "status": body.get("status"),
        "client_id": dashboard.get("client_overview", {}).get("client_id"),
        "error_code": body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else None,
        "panels_present": {
            "client_overview": bool(dashboard.get("client_overview")),
            "api_key_panel": bool(dashboard.get("api_key_panel")),
            "vault_namespace_panel": bool(dashboard.get("vault_namespace_panel")),
            "usage_overview": bool(dashboard.get("usage_overview")),
            "request_log_summary": bool(dashboard.get("request_log_summary")),
            "reports_panel": bool(dashboard.get("reports_panel")),
            "memory_health_panel": bool(dashboard.get("memory_health_panel")),
        },
        "raw_api_keys_returned": body.get("dashboard_connection", {}).get("raw_api_keys_returned"),
        "raw_dashboard_token_returned": body.get("dashboard_connection", {}).get("raw_dashboard_token_returned"),
        "public_safe": body.get("public_safe"),
    }
