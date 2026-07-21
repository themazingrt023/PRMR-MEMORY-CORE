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
        self.activation_events: list[dict[str, Any]] = []
        self.playground_api = PRMRControlledAlphaAPI()
        self.playground_keys_by_user: dict[str, dict[str, str]] = {}

    def signup(self, *, name: str, email: str, password: str) -> dict[str, Any]:
        result = self.accounts.create_user(name=name, email=email, password=password)
        if result.get("ok") and result.get("account", {}).get("user_id"):
            self.record_activation(
                user_id=str(result["account"]["user_id"]),
                event_type="account_created",
                detail={"public_safe": True},
            )
        return result

    def verify_email_local(self, *, user_id: str) -> dict[str, Any]:
        result = self.accounts.verify_email_local(user_id=user_id)
        if result.get("ok"):
            self.record_activation(user_id=user_id, event_type="email_verified", detail={"public_safe": True})
        return result

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
        result = self.keys.provision_default_scope(session_token=session_token)
        account = self.accounts.validate_session(session_token)
        if result.get("ok") and account is not None:
            self.record_activation(
                user_id=account.user_id,
                event_type="default_scope_ready",
                detail={"created": bool(result.get("created")), "public_safe": True},
            )
        return result

    def bootstrap_account(self, *, session_token: str, plan_id: str = "free", create_key: bool = True) -> dict[str, Any]:
        """Idempotently prepare the default self-serve workspace and first sandbox key."""

        account = self.accounts.validate_session(session_token)
        if account is None:
            return self.error(401, "valid_session_required")
        if account.status != "verified":
            return self.error(403, "verified_account_required")
        selected = self.plans.select_plan(
            user_id=account.user_id,
            plan_id=plan_id,
            account_verified=True,
        )
        if not selected.get("ok"):
            return selected
        if plan_id != "free":
            return {
                "ok": True,
                "status_code": 200,
                "account": self.accounts.public_account(account),
                "subscription": selected.get("subscription"),
                "scope": None,
                "application": None,
                "api_key_created": False,
                "raw_api_key_returned_once": False,
                "payment_processed": False,
                "next_step": "manual_plan_follow_up",
                "activation": self.activation_summary(account.user_id),
                "boundary": PRODUCT_BOUNDARY_V092,
            }
        provisioned = self.provision_default_scope(session_token=session_token)
        if not provisioned.get("ok"):
            return provisioned
        scope_record = self.keys.scopes_by_user.get(account.user_id)
        if scope_record is None:
            return self.error(500, "scope_bootstrap_failed")
        app = self.keys.ensure_default_application(scope_record.client_id)
        existing_active_key = next(
            (
                record
                for record in self.api.lifecycle.lifecycle_keys.values()
                if record.client_id == scope_record.client_id and record.status == "active"
            ),
            None,
        )
        key_result: dict[str, Any] | None = None
        if create_key and existing_active_key is None:
            key_result = self.create_key(
                session_token=session_token,
                label="Sandbox server key",
                application_reference=app.application_reference,
                environment=app.environment,
            )
            if not key_result.get("ok"):
                return key_result
            self.record_activation(
                user_id=account.user_id,
                event_type="sandbox_key_created",
                detail={"safe_key_preview": key_result.get("safe_key_preview"), "public_safe": True},
            )
        else:
            self.record_activation(
                user_id=account.user_id,
                event_type="sandbox_key_ready",
                detail={"created": False, "public_safe": True},
            )
        safe_key = key_result or (
            {
                "key_id": existing_active_key.key_id,
                "safe_key_preview": existing_active_key.safe_key_preview,
            }
            if existing_active_key
            else {}
        )
        return {
            "ok": True,
            "status_code": 201 if key_result else 200,
            "account": self.accounts.public_account(account),
            "subscription": selected.get("subscription"),
            "scope": self.keys.public_scope(scope_record),
            "application": self.keys.public_application(app),
            "api_key_created": bool(key_result),
            "raw_api_key": key_result.get("raw_api_key") if key_result else None,
            "raw_api_key_returned_once": bool(key_result),
            "safe_key_preview": safe_key.get("safe_key_preview"),
            "key_id": safe_key.get("key_id"),
            "payment_processed": False,
            "next_step": "/dashboard",
            "activation": self.activation_summary(account.user_id),
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def create_application(
        self,
        *,
        session_token: str,
        name: str,
        application_reference: str = "",
        environment: str = "production",
    ) -> dict[str, Any]:
        return self.keys.create_application(
            session_token=session_token,
            name=name,
            application_reference=application_reference,
            environment=environment,
        )

    def list_applications(self, *, session_token: str) -> dict[str, Any]:
        return self.keys.list_applications(session_token=session_token)

    def create_key(
        self,
        *,
        session_token: str,
        label: str,
        application_reference: str = "app_main",
        environment: str = "",
    ) -> dict[str, Any]:
        result = self.keys.create_key(
            session_token=session_token,
            label=label,
            application_reference=application_reference,
            environment=environment,
        )
        account = self.accounts.validate_session(session_token)
        if result.get("ok") and account is not None:
            self.record_activation(
                user_id=account.user_id,
                event_type="api_key_created",
                detail={"safe_key_preview": result.get("safe_key_preview"), "public_safe": True},
            )
        return result

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
            if operation == "events_ingest":
                self.record_activation(
                    user_id=owner_user_id,
                    event_type="first_event_ingested",
                    detail={"endpoint": "POST /v1/events/ingest", "public_safe": True},
                    once=True,
                )
            if operation == "continuity_packet":
                self.record_activation(
                    user_id=owner_user_id,
                    event_type="first_continuity_packet_generated",
                    detail={"endpoint": "POST /v1/continuity/packet", "public_safe": True},
                    once=True,
                )
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
        application_list = self.keys.list_applications(session_token=session_token) if scope else {"applications": []}
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
            "applications": application_list.get("applications", []),
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
            "activation": self.activation_summary(account.user_id),
            "credential_values_exposed": False,
            "session_token_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }
        return {"ok": True, "status_code": 200, "dashboard": dashboard}

    def record_activation(
        self,
        *,
        user_id: str,
        event_type: str,
        detail: dict[str, Any] | None = None,
        once: bool = False,
    ) -> None:
        if once and any(row["user_id"] == user_id and row["event_type"] == event_type for row in self.activation_events):
            return
        self.activation_events.append(
            {
                "timestamp": utc_now(),
                "user_id": user_id,
                "event_type": event_type,
                "detail": detail or {"public_safe": True},
            }
        )
        del self.activation_events[:-500]

    def activation_summary(self, user_id: str) -> dict[str, Any]:
        rows = [row for row in self.activation_events if row["user_id"] == user_id]
        completed = {row["event_type"] for row in rows}
        steps = [
            ("account_created", "Account created"),
            ("email_verified", "Email verified"),
            ("default_scope_ready", "Default client/vault/namespace ready"),
            ("sandbox_key_created", "Sandbox key created"),
            ("first_event_ingested", "First event ingested"),
            ("first_continuity_packet_generated", "First continuity packet generated"),
        ]
        return {
            "steps": [
                {"event_type": event_type, "label": label, "completed": event_type in completed}
                for event_type, label in steps
            ],
            "completed_count": sum(1 for event_type, _ in steps if event_type in completed),
            "total_count": len(steps),
            "events_recorded": len(rows),
            "raw_keys_exposed": False,
            "public_safe": True,
        }

    def dashboard_request_logs(
        self,
        *,
        session_token: str,
        limit: int = 25,
        offset: int = 0,
        status: str = "",
        endpoint: str = "",
        method: str = "",
    ) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        safe_limit = max(1, min(int(limit or 25), 100))
        safe_offset = max(0, int(offset or 0))
        status_filter = status.strip().lower()
        endpoint_filter = endpoint.strip().lower()
        method_filter = method.strip().upper()
        scoped_logs = [
            row
            for row in self.api.api_request_log
            if row.client_id == scope.client_id
        ]
        rows = []
        for index, row in enumerate(reversed(scoped_logs)):
            row_method, row_path = self.split_endpoint(row.endpoint)
            allowed = row.status == "ok"
            if status_filter and status_filter not in {row.status.lower(), "allowed" if allowed else "denied"}:
                continue
            if endpoint_filter and endpoint_filter not in row.endpoint.lower():
                continue
            if method_filter and method_filter != row_method:
                continue
            rows.append(
                {
                    "log_id": f"log_{len(scoped_logs) - index}_{abs(hash((row.timestamp, row.endpoint, row.reason))) % 1000000}",
                    "timestamp": row.timestamp,
                    "method": row_method,
                    "endpoint": row_path,
                    "status": row.status,
                    "allowed": allowed,
                    "client_scope": {
                        "client_id": row.client_id,
                        "vault_id": row.vault_id,
                        "namespace": row.namespace,
                    },
                    "latency_ms": None,
                    "rejection_reason": row.reason if not allowed else None,
                    "reason": row.reason,
                    "public_safe_message": row.public_safe_message,
                }
            )
        return {
            "ok": True,
            "status_code": 200,
            "logs": rows[safe_offset:safe_offset + safe_limit],
            "total_count": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": safe_offset + safe_limit < len(rows),
            "raw_headers_exposed": False,
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_reports(
        self,
        *,
        session_token: str,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        safe_limit = max(1, min(int(limit or 25), 100))
        safe_offset = max(0, int(offset or 0))
        scoped = [
            report
            for report in self.api.public_reports.values()
            if report.get("client_id") == scope.client_id
            and report.get("vault_id") == scope.vault_id
            and report.get("namespace") == scope.namespace
        ]
        scoped.sort(key=lambda item: str(self.packet_for_report(item).get("last_updated") or item.get("report_id", "")), reverse=True)
        rows = [self.report_summary(report) for report in scoped]
        return {
            "ok": True,
            "status_code": 200,
            "reports": rows[safe_offset:safe_offset + safe_limit],
            "total_count": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": safe_offset + safe_limit < len(rows),
            "raw_payloads_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_report_detail(self, *, session_token: str, report_id: str) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        report = self.api.public_reports.get(report_id)
        if (
            report is None
            or report.get("client_id") != scope.client_id
            or report.get("vault_id") != scope.vault_id
            or report.get("namespace") != scope.namespace
        ):
            return self.error(404, "report_not_found")
        packet = self.packet_for_report(report)
        detail = {
            **self.report_summary(report),
            "older_report_format": not bool(packet),
            "older_report_message": "Older report format. Limited packet fields available." if not packet else None,
            "packet": self.safe_packet_detail(packet) if packet else None,
            "raw_payload_exposed": False,
        }
        return {"ok": True, "status_code": 200, "report": detail, "boundary": PRODUCT_BOUNDARY_V092}

    def dashboard_generate_packet(self, *, session_token: str, packet_scope: dict[str, Any] | None = None) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        context = {
            "client_id": scope.client_id,
            "vault_id": scope.vault_id,
            "namespace": scope.namespace,
            "raw_api_key": None,
        }
        response = self.api.create_continuity_packet_response(
            "POST /v1/continuity/packet",
            context,
            packet_scope or {},
        )
        return {
            "ok": response.get("status_code") == 200,
            "status_code": response.get("status_code", 500),
            **response.get("body", {}),
            "dashboard_authenticated": True,
            "raw_key_used": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_events(
        self,
        *,
        session_token: str,
        limit: int = 50,
        offset: int = 0,
        status: str = "",
        actor_reference: str = "",
        event_type: str = "",
        event_id: str = "",
    ) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert scope
        safe_limit = max(1, min(int(limit or 50), 100))
        safe_offset = max(0, int(offset or 0))
        wanted_status = status.strip().lower()
        wanted_actor = actor_reference.strip()
        wanted_type = event_type.strip()
        wanted_id = event_id.strip()
        rows = []
        for scope_key, events in self.api.events.items():
            if not scope_key.startswith(f"{scope.client_id}::{scope.vault_id}::{scope.namespace}"):
                continue
            for event in events:
                row = self.event_summary(event, "accepted")
                if wanted_status and wanted_status not in {"all", row["status"].lower()}:
                    continue
                if wanted_actor and row["actor_reference"] != wanted_actor:
                    continue
                if wanted_type and row["event_type"] != wanted_type:
                    continue
                if wanted_id and row["event_id"] != wanted_id:
                    continue
                rows.append(row)
        rows.sort(key=lambda row: (row["received_at"], row["event_id"]), reverse=True)
        return {
            "ok": True,
            "status_code": 200,
            "events": rows[safe_offset:safe_offset + safe_limit],
            "total_count": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": safe_offset + safe_limit < len(rows),
            "mode": "LIVE",
            "raw_payloads_redacted": False,
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_packets(self, *, session_token: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        result = self.dashboard_reports(session_token=session_token, limit=limit, offset=offset)
        if result.get("ok"):
            result["packets"] = [
                {
                    **row,
                    "status": "Ready",
                    "events_considered": row.get("event_count", 0),
                    "created": row.get("created_timestamp"),
                }
                for row in result.pop("reports", [])
            ]
            result["mode"] = "LIVE"
        return result

    def dashboard_packet_detail(self, *, session_token: str, packet_id: str) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert scope
        packet = self.api.packets.get(packet_id)
        if (
            not packet
            or packet.get("client_id") != scope.client_id
            or packet.get("vault_id") != scope.vault_id
            or packet.get("namespace") != scope.namespace
        ):
            return self.error(404, "packet_not_found")
        return {
            "ok": True,
            "status_code": 200,
            "packet": self.safe_packet_detail(packet),
            "mode": "LIVE",
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_actors(self, *, session_token: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        account, scope, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert scope
        actor_events: dict[str, list[dict[str, Any]]] = {}
        actor_packets: dict[str, list[dict[str, Any]]] = {}
        for scope_key, events in self.api.events.items():
            if not scope_key.startswith(f"{scope.client_id}::{scope.vault_id}::{scope.namespace}"):
                continue
            for event in events:
                actor = str(event.get("actor_reference") or "unknown_actor")
                actor_events.setdefault(actor, []).append(event)
        for packet in self.api.packets.values():
            if packet.get("client_id") == scope.client_id and packet.get("vault_id") == scope.vault_id and packet.get("namespace") == scope.namespace:
                actor = str(packet.get("actor_reference") or "unknown_actor")
                actor_packets.setdefault(actor, []).append(packet)
        rows = []
        for actor, events in actor_events.items():
            ordered = sorted(events, key=lambda event: str(event.get("timestamp", "")))
            packets = sorted(actor_packets.get(actor, []), key=lambda packet: str(packet.get("last_updated", "")), reverse=True)
            rows.append(
                {
                    "actor_reference": actor,
                    "first_seen": str(ordered[0].get("timestamp", "")) if ordered else None,
                    "latest_activity": str(ordered[-1].get("timestamp", "")) if ordered else None,
                    "event_count": len(events),
                    "packet_count": len(packets),
                    "latest_packet_id": packets[0].get("packet_id") if packets else None,
                    "current_continuity": packets[0].get("current_state") if packets else None,
                    "status": "active" if events else "empty",
                    "public_safe": True,
                }
            )
        rows.sort(key=lambda row: str(row.get("latest_activity") or ""), reverse=True)
        safe_limit = max(1, min(int(limit or 50), 100))
        safe_offset = max(0, int(offset or 0))
        return {
            "ok": True,
            "status_code": 200,
            "actors": rows[safe_offset:safe_offset + safe_limit],
            "total_count": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": safe_offset + safe_limit < len(rows),
            "mode": "LIVE",
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_usage(self, *, session_token: str) -> dict[str, Any]:
        account, scope, plan, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account and scope
        events = self.dashboard_events(session_token=session_token, limit=100, offset=0).get("events", [])
        packets = self.dashboard_packets(session_token=session_token, limit=100, offset=0).get("packets", [])
        actors = self.dashboard_actors(session_token=session_token, limit=100, offset=0).get("actors", [])
        request_logs = self.dashboard_request_logs(session_token=session_token, limit=100, offset=0).get("logs", [])
        usage = self.plans.usage_summary(account.user_id)
        return {
            "ok": True,
            "status_code": 200,
            "usage": {
                "events_received": len(events),
                "packets_generated": len(packets),
                "active_actors": len(actors),
                "api_requests": len(request_logs),
                "requests_used": usage["requests_used"],
                "requests_remaining": usage["requests_remaining"],
                "requests_limit": usage["requests_limit"],
                "storage_used": None,
                "storage_measured": False,
                "billing_live": False,
            },
            "mode": "LIVE",
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_playground_event(self, *, session_token: str, event_payload: dict[str, Any]) -> dict[str, Any]:
        account, _, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account
        context = self.playground_context(account.user_id)
        event = {
            "application_reference": "playground_test_session",
            "actor_reference": str(event_payload.get("actor_reference") or event_payload.get("actor_id") or "test_actor"),
            "workspace_reference": "playground_test_workspace",
            "entity_reference": str(event_payload.get("entity_reference") or event_payload.get("actor_reference") or event_payload.get("actor_id") or "test_actor"),
            "event_type": str(event_payload.get("event_type") or "playground.manual_event"),
            "signal": str(event_payload.get("signal") or event_payload.get("summary") or event_payload.get("payload") or "Manual playground event"),
            "occurred_at": str(event_payload.get("occurred_at") or event_payload.get("timestamp") or utc_now()),
            "idempotency_key": str(event_payload.get("idempotency_key") or f"playground_{account.user_id}_{len(self.playground_api.events)}_{utc_now()}"),
            "metadata": {"source_app": "prmr_console_playground", "test_mode": True},
        }
        response = self.playground_api.events_ingest({**context, "events": [event]})
        body = response.get("body", {})
        return {
            "ok": response.get("status_code") == 200,
            "status_code": response.get("status_code", 500),
            **body,
            "mode": "TEST_MODE",
            "test_mode": True,
            "isolated_from_live": True,
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_playground_packet(self, *, session_token: str, packet_scope: dict[str, Any]) -> dict[str, Any]:
        account, _, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account
        context = self.playground_context(account.user_id)
        response = self.playground_api.continuity_packet(
            {
                **context,
                "application_reference": "playground_test_session",
                "actor_reference": str(packet_scope.get("actor_reference") or packet_scope.get("actor_id") or "test_actor"),
                "workspace_reference": "playground_test_workspace",
                "entity_reference": str(packet_scope.get("entity_reference") or packet_scope.get("actor_reference") or packet_scope.get("actor_id") or "test_actor"),
            }
        )
        body = response.get("body", {})
        if "packet" in body:
            body["packet"] = self.safe_packet_detail(body["packet"])
        return {
            "ok": response.get("status_code") == 200,
            "status_code": response.get("status_code", 500),
            **body,
            "mode": "TEST_MODE",
            "test_mode": True,
            "isolated_from_live": True,
            "raw_keys_exposed": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def dashboard_playground_reset(self, *, session_token: str) -> dict[str, Any]:
        account, _, _, error = self.keys.authorized_context(session_token)
        if error:
            return error
        assert account
        context = self.playground_keys_by_user.pop(account.user_id, None)
        if context:
            prefix = f"{context['client_id']}::{context['vault_id']}::{context['namespace']}"
            self.playground_api.events = {
                key: value for key, value in self.playground_api.events.items() if not key.startswith(prefix)
            }
            self.playground_api.packets = {
                key: value for key, value in self.playground_api.packets.items() if value.get("client_id") != context["client_id"]
            }
            self.playground_api.public_reports = {
                key: value for key, value in self.playground_api.public_reports.items() if value.get("client_id") != context["client_id"]
            }
            self.playground_api.private_reports = {
                key: value for key, value in self.playground_api.private_reports.items() if value.get("client_id") != context["client_id"]
            }
        return {
            "ok": True,
            "status_code": 200,
            "mode": "TEST_MODE",
            "test_data_removed": True,
            "live_data_touched": False,
            "boundary": PRODUCT_BOUNDARY_V092,
        }

    def playground_context(self, user_id: str) -> dict[str, str]:
        existing = self.playground_keys_by_user.get(user_id)
        if existing:
            return existing
        client_id = f"client_playground_{user_id[-10:]}"
        vault_id = f"vault_playground_{user_id[-10:]}"
        namespace = "test"
        self.playground_api.lifecycle.create_client(
            organisation="PRMR Playground",
            contact_email="playground@example.test",
            status="active",
            client_id=client_id,
        )
        self.playground_api.lifecycle.create_usage_limit(
            usage_limit_id=f"limit_playground_{user_id[-10:]}",
            max_events_per_day=1000,
            max_packets_per_day=1000,
            max_reports_per_day=1000,
            alpha_limit_reason="Isolated dashboard playground test mode.",
        )
        self.playground_api.lifecycle.create_vault(client_id, vault_id=vault_id, status="active")
        self.playground_api.lifecycle.create_namespace(client_id, vault_id, namespace=namespace, status="active")
        key = self.playground_api.lifecycle.issue_alpha_key(
            client_id=client_id,
            usage_limit_id=f"limit_playground_{user_id[-10:]}",
            vault_id=vault_id,
            namespace=namespace,
            operator_id="dashboard_playground",
            approval_reason="Isolated playground test mode key.",
        )
        context = {
            "api_key": str(key["raw_api_key"]),
            "client_id": client_id,
            "vault_id": vault_id,
            "namespace": namespace,
        }
        self.playground_keys_by_user[user_id] = context
        return context

    def event_summary(self, event: dict[str, Any], status: str) -> dict[str, Any]:
        return {
            "event_id": str(event.get("event_id", "")),
            "actor_reference": str(event.get("actor_reference", "")),
            "entity_reference": str(event.get("entity_reference", "")),
            "event_type": str(event.get("type") or event.get("event_type") or ""),
            "status": status,
            "occurred_at": str(event.get("timestamp", "")),
            "received_at": str(event.get("received_at") or event.get("timestamp", "")),
            "readable_summary": str(event.get("content", "")),
            "payload": event.get("external_metadata", {}),
            "associated_packets": [
                packet.get("packet_id")
                for packet in self.api.packets.values()
                if str(event.get("event_id", "")) in packet.get("provenance", {}).get("source_event_ids", [])
            ],
            "public_safe": True,
        }

    def split_endpoint(self, endpoint: str) -> tuple[str, str]:
        parts = endpoint.split(" ", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", endpoint

    def packet_for_report(self, report: dict[str, Any]) -> dict[str, Any]:
        packet_id = str(report.get("packet_id", ""))
        return self.api.packets.get(packet_id, {})

    def report_summary(self, report: dict[str, Any]) -> dict[str, Any]:
        packet = self.packet_for_report(report)
        return {
            "report_id": report.get("report_id"),
            "created_timestamp": packet.get("last_updated"),
            "summary": report.get("summary"),
            "packet_id": report.get("packet_id"),
            "endpoint_source": "POST /v1/continuity/packet",
            "event_count": report.get("event_count"),
            "application_reference": report.get("application_reference"),
            "actor_reference": report.get("actor_reference"),
            "workspace_reference": report.get("workspace_reference"),
            "entity_reference": report.get("entity_reference"),
            "packet_version": report.get("packet_version"),
            "algorithm_revision": report.get("algorithm_revision"),
            "public_safe": True,
        }

    def safe_packet_detail(self, packet: dict[str, Any]) -> dict[str, Any]:
        allowed = [
            "packet_id",
            "report_id",
            "application_reference",
            "actor_reference",
            "workspace_reference",
            "entity_reference",
            "session_reference",
            "current_state",
            "active_information",
            "latent_information",
            "lineage_information",
            "causal_signature",
            "recursive_horizon",
            "coherence_score",
            "recoverability_score",
            "re_emergence_signals",
            "decayed_signals",
            "repeated_patterns",
            "state_transition_summary",
            "event_count",
            "source_event_count",
            "first_event_at",
            "last_updated",
            "packet_version",
            "algorithm_revision",
            "provenance",
            "summary",
            "active_signals",
            "stale_signals",
        ]
        return {key: packet.get(key) for key in allowed if key in packet}

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
