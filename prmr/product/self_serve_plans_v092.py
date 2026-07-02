"""Generic self-serve plan and monthly quota model for V0.92."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from prmr.product.hosted_backend_foundation_v069 import utc_now


PLAN_BOUNDARY_V092 = (
    "V0.92 includes real plan and quota state for the local/deployable MVP. "
    "Free access can activate locally. Builder billing is not connected, and "
    "Controlled Pilot still requires manual approval."
)


@dataclass(frozen=True)
class PlanDefinition:
    plan_id: str
    name: str
    requests_per_month: int | None
    max_clients: int
    max_vaults: int
    max_namespaces: int
    max_active_keys: int
    report_level: str
    price_label: str
    activation_mode: str


@dataclass
class PlanSubscription:
    user_id: str
    plan_id: str
    status: str
    billing_status: str
    selected_at: str
    updated_at: str


PLANS: dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        plan_id="free",
        name="Free",
        requests_per_month=100,
        max_clients=1,
        max_vaults=1,
        max_namespaces=1,
        max_active_keys=1,
        report_level="basic",
        price_label="£0",
        activation_mode="instant_local_mvp",
    ),
    "builder": PlanDefinition(
        plan_id="builder",
        name="Builder",
        requests_per_month=10_000,
        max_clients=1,
        max_vaults=5,
        max_namespaces=10,
        max_active_keys=5,
        report_level="dashboard",
        price_label="Pricing not live",
        activation_mode="requires_future_payment",
    ),
    "controlled_pilot": PlanDefinition(
        plan_id="controlled_pilot",
        name="Controlled Pilot",
        requests_per_month=None,
        max_clients=1,
        max_vaults=10,
        max_namespaces=25,
        max_active_keys=10,
        report_level="custom",
        price_label="From £250",
        activation_mode="manual_approval",
    ),
}


class SelfServePlansV092:
    def __init__(self) -> None:
        self.subscriptions: dict[str, PlanSubscription] = {}
        self.monthly_usage: dict[tuple[str, str], int] = {}

    def list_plans(self) -> list[dict[str, Any]]:
        return [asdict(plan) for plan in PLANS.values()]

    def select_plan(self, *, user_id: str, plan_id: str, account_verified: bool) -> dict[str, Any]:
        if not account_verified:
            return self.error(403, "verified_account_required")
        plan = PLANS.get(plan_id)
        if plan is None:
            return self.error(404, "plan_not_found")
        if plan_id == "free":
            status = "active"
            billing_status = "not_required"
        elif plan_id == "builder":
            status = "selected_billing_not_live"
            billing_status = "simulated_not_charged"
        else:
            status = "pending_manual_approval"
            billing_status = "manual_not_charged"
        subscription = PlanSubscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            billing_status=billing_status,
            selected_at=utc_now(),
            updated_at=utc_now(),
        )
        self.subscriptions[user_id] = subscription
        return {
            "ok": True,
            "status_code": 200,
            "subscription": self.public_subscription(subscription),
            "plan": asdict(plan),
            "payment_processed": False,
            "boundary": PLAN_BOUNDARY_V092,
        }

    def change_plan(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        return self.select_plan(user_id=user_id, plan_id=plan_id, account_verified=True)

    def active_plan(self, user_id: str) -> PlanDefinition | None:
        subscription = self.subscriptions.get(user_id)
        if subscription is None or subscription.status != "active":
            return None
        return PLANS[subscription.plan_id]

    def can_consume(self, user_id: str) -> tuple[bool, str]:
        plan = self.active_plan(user_id)
        if plan is None:
            return False, "active_plan_required"
        if plan.requests_per_month is None:
            return True, "allowed"
        used = self.monthly_usage.get((user_id, self.month_key()), 0)
        if used >= plan.requests_per_month:
            return False, "monthly_request_limit_exceeded"
        return True, "allowed"

    def consume(self, user_id: str, count: int = 1) -> None:
        key = (user_id, self.month_key())
        self.monthly_usage[key] = self.monthly_usage.get(key, 0) + count

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        subscription = self.subscriptions.get(user_id)
        plan = PLANS.get(subscription.plan_id) if subscription else None
        used = self.monthly_usage.get((user_id, self.month_key()), 0)
        limit = plan.requests_per_month if plan else 0
        return {
            "month": self.month_key(),
            "requests_used": used,
            "requests_limit": limit,
            "requests_remaining": None if limit is None else max(0, limit - used),
            "limit_enforced": limit is not None,
        }

    def public_subscription(self, subscription: PlanSubscription) -> dict[str, Any]:
        return {
            "user_id": subscription.user_id,
            "plan_id": subscription.plan_id,
            "status": subscription.status,
            "billing_status": subscription.billing_status,
            "selected_at": subscription.selected_at,
            "updated_at": subscription.updated_at,
        }

    def month_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "error": {"code": code},
            "payment_processed": False,
            "boundary": PLAN_BOUNDARY_V092,
        }

