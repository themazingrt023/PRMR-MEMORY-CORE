"""V0.89 Whop offer configuration and controlled access-funnel model.

This module validates a public Whop checkout URL and exports a public-safe offer
state. It does not call Whop, process payment, approve clients, or issue keys.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


BOUNDARY_V089 = (
    "V0.89 is a Whop offer page and controlled access-funnel package. A "
    "configured checkout link can collect payment or waitlist intent, but it "
    "does not automatically approve a client, issue an API key, grant dashboard "
    "access, or prove production billing. Manual founder review remains required."
)

OFFER_NAME = "PRMR Controlled Alpha Pilot"
OFFER_PRICE = "From GBP 250"
ALLOWED_WHOP_HOSTS = {"whop.com", "www.whop.com"}


@dataclass(frozen=True)
class WhopOfferState:
    offer_name: str
    price_label: str
    checkout_status: str
    checkout_url: str | None
    primary_action: str
    fallback_url: str
    manual_approval_required: bool
    automatic_key_issuing: bool
    automatic_dashboard_access: bool
    synthetic_or_approved_non_sensitive_data_only: bool
    boundary: str


def validate_whop_checkout_url(value: str | None) -> tuple[bool, str | None]:
    """Accept only public HTTPS URLs on Whop's official web host."""

    candidate = str(value or "").strip()
    if not candidate:
        return False, None
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_WHOP_HOSTS:
        return False, None
    if not parsed.path or parsed.path == "/":
        return False, None
    return True, candidate


def build_whop_offer_state(checkout_url: str | None) -> WhopOfferState:
    valid, safe_url = validate_whop_checkout_url(checkout_url)
    return WhopOfferState(
        offer_name=OFFER_NAME,
        price_label=OFFER_PRICE,
        checkout_status="configured" if valid else "needs_manual_configuration",
        checkout_url=safe_url,
        primary_action="Continue to Whop" if valid else "Request Pilot Access",
        fallback_url="/alpha?source=whop-pilot",
        manual_approval_required=True,
        automatic_key_issuing=False,
        automatic_dashboard_access=False,
        synthetic_or_approved_non_sensitive_data_only=True,
        boundary=BOUNDARY_V089,
    )


def public_offer_payload(checkout_url: str | None) -> dict[str, Any]:
    state = build_whop_offer_state(checkout_url)
    return {
        "version": "0.89",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "offer": asdict(state),
        "funnel": [
            {
                "stage": "understand",
                "result": "Review the PRMR pilot scope and controlled-alpha boundaries.",
            },
            {
                "stage": "checkout_or_waitlist",
                "result": "Use the configured Whop link or the manual application fallback.",
            },
            {
                "stage": "manual_review",
                "result": "Founder verifies fit, data safety, and capacity before approval.",
            },
            {
                "stage": "manual_onboarding",
                "result": "Approved clients receive scoped client, vault, namespace, and copy-once key setup.",
            },
            {
                "stage": "controlled_use",
                "result": "Client uses PRMR server-side and monitors scoped usage and public-safe reports.",
            },
        ],
        "payment_does_not_equal_access": True,
        "credential_values_in_payload": False,
    }

