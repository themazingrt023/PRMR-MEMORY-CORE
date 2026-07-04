"""Generic self-serve product service for PRMR Memory Core V0.92.

This composes account, plan, client-scope, key, protected API, and dashboard
state. It is deliberately deployable-shaped while retaining explicit MVP
boundaries around email, billing, persistence, and authentication.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from prmr.product.controlled_alpha_api_v071 import APIRequestLog, PRMRControlledAlphaAPI
from prmr.product.hosted_backend_foundation_v069 import utc_now
from prmr.product.self_serve_accounts_v092 import SelfServeAccountsV092
from prmr.product.self_serve_api_keys_v092 import SelfServeAPIKeysV092
from prmr.product.self_serve_plans_v092 import PLANS, SelfServePlansV092


API_BASE_URL = "https://prmr-memory-core-api.onrender.com"
PRODUCT_BOUNDARY_V092 = (
    "V0.92 is a generic self-serve API product MVP using local/deployable state, "
    "local simulated email verification, Free-plan quota enforcement, and "
    "copy-once alpha keys. Real email delivery, payment processing, durable "
    "hosted persistence, and production authentication are not implemented."
)


class SelfServeDashboardV092:
    """One product-facing service over the existing protected PRMR API."""

    def __init__(self) -> None:
        self.accounts = SelfServeAccountsV092()
        self.plans = SelfServePlansV092()
        self.api = PRMRControlledAlphaAPI()
        self.keys = SelfServeAPIKeysV092(
            api=self.api,
            accounts=self.accounts,
            plans=self.plans,
        )
        self.api_key_diagnostics: list[dict[str, Any]] = []

    def signup(self, *, name: str, email: str, password: str) -> dict[str, Any]:
        return self.accounts.create_user(name=name, email=email, password=password)

    def verify_email_local(self, *, user_id: str) -> dict[str, Any]:
        return self.accounts.verify_email_local(user_id=user_id)

    def login(self, *, email: str, password: str) -> dict[str, Any]:
        return self.accounts.login(email=email, password=password)

    def choose_plan(self, *, session_token: str, plan_id: str) -> dict[str, Any]:
        account = self.accounts.validate_session(session_token)
        if account is None:
            return self.error(401, "valid_session_required")
        return self.plans.select_plan(
            user_id=account.user_id,
            plan_id=plan_id,
            account_verified=account.status == "verified",
        )

    def provision_default_scope(self, *, session_token: str) -> dict[str, Any]:
        return self.keys.provision_default_scope(session_token=session_token)

    def create_key(self, *, session_token: str, label: str) -> dict[str, Any]:
        return self.keys.create_key(session_token=session_token, label=label)

    def list_keys(self, *, session_token: str) -> dict[str, Any]:
        return self.keys.list_keys(session_token=session_token)

    def rotate_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        return self.keys.rotate_key(session_token=session_token, key_id=key_id)

    def revoke_key(self, *, session_token: str, key_id: str) -> dict[str, Any]:
        return self.keys.revoke_key(session_token=session_token, key_id=key_id)

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
        """Run one protected PRMR operation and enforce the selected plan."""

        resolved_scope, diagnostic = self.keys.resolve_request_scope(
            raw_key=api_key,
            client_id=client_id,
            vault_id=vault_id,
            namespace=namespace,
        )
        client_id = resolved_scope["client_id"]
        vault_id = resolved_scope["vault_id"]
        namespace = resolved_scope["namespace"]
        base_payload = {
            "api_key": api_key,
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
            **payload,
        }
        owner_user_id = self.keys.user_by_client.get(client_id)
        valid_key, _ = self.keys.preflight_key(raw_key=api_key, client_id=client_id)
        plan_allows_usage = False
        if valid_key and owner_user_id:
            allowed, reason = self.plans.can_consume(owner_user_id)
            plan_allows_usage = allowed
            if not allowed:
                diagnostic["planAllowsUsage"] = False
                diagnostic["rejectionReason"] = "plan_required"
                self.api_key_diagnostics.append(diagnostic)
                del self.api_key_diagnostics[:-200]
                endpoint = self.endpoint_for(operation)
                self.api.api_request_log.append(
                    APIRequestLog(
                        timestamp=utc_now(),
                        endpoint=endpoint,
                        client_id=client_id,
                        vault_id=vault_id,
                        namespace=namespace,
                        status="blocked",
                        reason=reason,
                        public_safe_message="The selected plan's monthly request limit has been reached.",
                    )
                )
                return {
                    "status_code": 429,
                    "body": {
                        "status": "error",
                        "error": {
                            "code": reason,
                            "message": "The selected plan's monthly request limit has been reached.",
                        },
                        "public_safe": True,
                        "boundary": PRODUCT_BOUNDARY_V092,
                    },
                }
        diagnostic["planAllowsUsage"] = plan_allows_usage
        if valid_key and diagnostic["rejectionReason"] == "allowed" and not plan_allows_usage:
            diagnostic["rejectionReason"] = "plan_required"
        self.api_key_diagnostics.append(diagnostic)
        del self.api_key_diagnostics[:-200]

        response = self.dispatch(operation, base_payload)
        if response.get("status_code") == 200 and owner_user_id:
            self.plans.consume(owner_user_id)
        return response

    def dispatch(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "events_ingest": self.api.events_ingest,
            "continuity_packet": self.api.continuity_packet,
            "memory_reconstruct": self.api.memory_reconstruct,
            "explain": self.api.explain,
            "least_harm_action": self.api.least_harm_action,
            "get_usage": self.api.get_usage,
        }
        if operation == "get_report":
            report_id = str(payload.pop("report_id", ""))
            return self.api.get_report(payload, report_id)
        handler = handlers.get(operation)
        if handler is None:
            return {
                "status_code": 404,
                "body": {
                    "status": "error",
                    "error": {"code": "operation_not_found"},
                    "public_safe": True,
                },
            }
        return handler(payload)

    def dashboard_state(self, *, session_token: str) -> dict[str, Any]:
        account = self.accounts.validate_session(session_token)
        if account is None:
            return self.error(401, "valid_session_required")
        scope = self.keys.scopes_by_user.get(account.user_id)
        subscription = self.plans.subscriptions.get(account.user_id)
        key_list = self.keys.list_keys(session_token=session_token) if scope else {"keys": []}
        request_logs = []
        reports = []
        if scope:
            request_logs = [
                {
                    "timestamp": row.timestamp,
                    "endpoint": row.endpoint,
                    "status": row.status,
                    "reason": row.reason,
                    "public_safe_message": row.public_safe_message,
                }
                for row in self.api.api_request_log
                if row.client_id == scope.client_id
            ]
            reports = [
                {
                    "report_id": report["report_id"],
                    "vault_id": report["vault_id"],
                    "namespace": report["namespace"],
                    "summary": report["summary"],
                    "public_safe": True,
                }
                for report in self.api.public_reports.values()
                if report["client_id"] == scope.client_id
            ]
        plan = PLANS.get(subscription.plan_id) if subscription else None
        dashboard = {
            "account": self.accounts.public_account(account),
            "plan": {
                "subscription": self.plans.public_subscription(subscription) if subscription else None,
                "definition": asdict(plan) if plan else None,
                "usage": self.plans.usage_summary(account.user_id),
                "payment_processed": False,
            },
            "client_scope": self.keys.public_scope(scope) if scope else None,
            "api_keys": key_list.get("keys", []),
            "request_logs": request_logs,
            "reports": reports,
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
            "billing": {
                "live": False,
                "status": subscription.billing_status if subscription else "no_plan_selected",
                "message": "Payment processing is not connected in V0.92.",
            },
            "support": {
                "mode": "manual_controlled_alpha",
                "automated_support_claimed": False,
            },
            "credential_values_exposed": False,
            "session_token_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }
        return {"ok": True, "status_code": 200, "dashboard": dashboard}

    def endpoint_for(self, operation: str) -> str:
        endpoints = {
            "events_ingest": "POST /v1/events/ingest",
            "continuity_packet": "POST /v1/continuity/packet",
            "memory_reconstruct": "POST /v1/memory/reconstruct",
            "explain": "POST /v1/explain",
            "least_harm_action": "POST /v1/actions/least-harm",
            "get_report": "GET /v1/reports/{report_id}",
            "get_usage": "GET /v1/usage",
        }
        return endpoints.get(operation, operation)

    def error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "error": {"code": code},
            "boundary": PRODUCT_BOUNDARY_V092,
        }
