"""Supabase Auth identity bridge for verified PRMR self-serve access."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx

from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now
from prmr.product.self_serve_accounts_v092 import LocalSession, SelfServeAccount


BOUNDARY_V095 = (
    "V0.95 uses Supabase Auth as the hosted email/password identity and email "
    "confirmation path. PRMR maps a confirmed Supabase identity to its own "
    "client scope and API-key lifecycle. This MVP is not Stripe billing, "
    "production authentication hardening, enterprise SSO, compliance approval, "
    "legal approval, or external security certification."
)


@dataclass(frozen=True)
class SupabaseIdentity:
    subject: str
    email: str
    email_confirmed_at: str | None
    role: str
    display_name: str

    @property
    def confirmed(self) -> bool:
        return bool(self.email_confirmed_at) and self.role == "authenticated"


class SupabaseIdentityVerifier(Protocol):
    def verify(self, access_token: str | None) -> tuple[SupabaseIdentity | None, str]:
        """Return a verified identity or a public-safe rejection reason."""


class SupabaseRemoteIdentityVerifier:
    """Validate a Supabase access token through the hosted Auth user endpoint."""

    def __init__(
        self,
        *,
        project_url: str,
        publishable_key: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.project_url = project_url.rstrip("/")
        self._publishable_key = publishable_key
        self.timeout_seconds = timeout_seconds
        if not self.project_url.startswith("https://"):
            raise ValueError("SUPABASE_PROJECT_URL must use HTTPS.")
        if not self._publishable_key:
            raise ValueError("SUPABASE_PUBLISHABLE_KEY is required.")

    @classmethod
    def from_environment(cls) -> "SupabaseRemoteIdentityVerifier":
        project_url = (
            os.getenv("SUPABASE_PROJECT_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
        )
        publishable_key = (
            os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
        )
        if not project_url or not publishable_key:
            raise ValueError(
                "SUPABASE_PROJECT_URL and SUPABASE_PUBLISHABLE_KEY are required "
                "for hosted Supabase Auth verification."
            )
        return cls(project_url=project_url, publishable_key=publishable_key)

    def verify(self, access_token: str | None) -> tuple[SupabaseIdentity | None, str]:
        if not access_token:
            return None, "missing_supabase_access_token"
        try:
            response = httpx.get(
                f"{self.project_url}/auth/v1/user",
                headers={
                    "apikey": self._publishable_key,
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError:
            return None, "supabase_auth_unavailable"
        if response.status_code != 200:
            return None, "invalid_supabase_access_token"
        try:
            payload = response.json()
        except ValueError:
            return None, "invalid_supabase_auth_response"
        email = str(payload.get("email") or "").strip().lower()
        subject = str(payload.get("id") or "").strip()
        role = str(payload.get("role") or "").strip()
        confirmed_at = payload.get("email_confirmed_at") or payload.get("confirmed_at")
        metadata = payload.get("user_metadata")
        display_name = ""
        if isinstance(metadata, dict):
            display_name = str(metadata.get("display_name") or metadata.get("name") or "")
        if not subject or "@" not in email:
            return None, "invalid_supabase_identity"
        identity = SupabaseIdentity(
            subject=subject,
            email=email,
            email_confirmed_at=str(confirmed_at) if confirmed_at else None,
            role=role,
            display_name=display_name,
        )
        if not identity.confirmed:
            return None, "supabase_email_confirmation_required"
        return identity, "allowed"


class FixtureSupabaseIdentityVerifier:
    """Deterministic verifier used only by local V0.95 integrity tests."""

    def __init__(self, identities: dict[str, SupabaseIdentity]) -> None:
        self.identities = dict(identities)

    def verify(self, access_token: str | None) -> tuple[SupabaseIdentity | None, str]:
        if not access_token:
            return None, "missing_supabase_access_token"
        identity = self.identities.get(access_token)
        if identity is None:
            return None, "invalid_supabase_access_token"
        if not identity.confirmed:
            return None, "supabase_email_confirmation_required"
        return identity, "allowed"


class SupabaseAuthBridgeV095:
    """Gate PRMR account, plan, scope, dashboard, and key actions by Supabase Auth."""

    def __init__(self, storage_product: Any, verifier: SupabaseIdentityVerifier) -> None:
        self.storage_product = storage_product
        self.product = storage_product.product
        self.verifier = verifier
        self._internal_sessions: dict[str, str] = {}

    @classmethod
    def from_environment(cls, storage_product: Any) -> "SupabaseAuthBridgeV095":
        return cls(
            storage_product,
            SupabaseRemoteIdentityVerifier.from_environment(),
        )

    def activate(self, *, access_token: str | None, plan_id: str) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        identity, account, internal_session = context
        if hasattr(self.storage_product, "bootstrap_account"):
            bootstrapped = self.storage_product.bootstrap_account(
                session_token=internal_session,
                plan_id=plan_id,
                create_key=True,
            )
            if not bootstrapped.get("ok"):
                return bootstrapped
            return {
                **bootstrapped,
                "identity": self._public_identity(identity, account),
                "provisioned": bool(bootstrapped.get("scope")),
                "boundary": BOUNDARY_V095,
            }
        selected = self.storage_product.choose_plan(
            session_token=internal_session,
            plan_id=plan_id,
        )
        if not selected.get("ok"):
            return selected
        if plan_id != "free":
            return {
                "ok": True,
                "status_code": 200,
                "identity": self._public_identity(identity, account),
                "subscription": selected.get("subscription"),
                "scope": None,
                "provisioned": False,
                "payment_processed": False,
                "next_step": (
                    "Builder is selectable but unbilled."
                    if plan_id == "builder"
                    else "Controlled Pilot requires manual approval."
                ),
                "boundary": BOUNDARY_V095,
            }
        provisioned = self.storage_product.provision_default_scope(
            session_token=internal_session,
        )
        return {
            "ok": bool(provisioned.get("ok")),
            "status_code": int(provisioned.get("status_code", 500)),
            "identity": self._public_identity(identity, account),
            "subscription": selected.get("subscription"),
            "scope": provisioned.get("scope"),
            "provisioned": bool(provisioned.get("ok")),
            "payment_processed": False,
            "next_step": "/dashboard",
            "boundary": BOUNDARY_V095,
        }

    def dashboard(self, *, access_token: str | None) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_state(session_token=internal_session)

    def dashboard_logs(
        self,
        *,
        access_token: str | None,
        limit: int = 25,
        offset: int = 0,
        status: str = "",
        endpoint: str = "",
        method: str = "",
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_request_logs(
            session_token=internal_session,
            limit=limit,
            offset=offset,
            status=status,
            endpoint=endpoint,
            method=method,
        )

    def dashboard_reports(
        self,
        *,
        access_token: str | None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_reports(
            session_token=internal_session,
            limit=limit,
            offset=offset,
        )

    def dashboard_report_detail(
        self,
        *,
        access_token: str | None,
        report_id: str,
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_report_detail(
            session_token=internal_session,
            report_id=report_id,
        )

    def dashboard_generate_packet(
        self,
        *,
        access_token: str | None,
        packet_scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_generate_packet(
            session_token=internal_session,
            packet_scope=packet_scope or {},
        )

    def dashboard_events(self, *, access_token: str | None, **filters: Any) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_events(session_token=internal_session, **filters)

    def dashboard_packets(self, *, access_token: str | None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_packets(session_token=internal_session, limit=limit, offset=offset)

    def dashboard_packet_detail(self, *, access_token: str | None, packet_id: str) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_packet_detail(session_token=internal_session, packet_id=packet_id)

    def dashboard_actors(self, *, access_token: str | None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_actors(session_token=internal_session, limit=limit, offset=offset)

    def dashboard_usage(self, *, access_token: str | None) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_usage(session_token=internal_session)

    def dashboard_playground_event(self, *, access_token: str | None, event_payload: dict[str, Any]) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_playground_event(session_token=internal_session, event_payload=event_payload)

    def dashboard_playground_packet(self, *, access_token: str | None, packet_scope: dict[str, Any]) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_playground_packet(session_token=internal_session, packet_scope=packet_scope)

    def dashboard_playground_reset(self, *, access_token: str | None) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.dashboard_playground_reset(session_token=internal_session)

    def create_key(
        self,
        *,
        access_token: str | None,
        label: str,
        application_reference: str = "app_main",
        environment: str = "",
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.create_key(
            session_token=internal_session,
            label=label,
            application_reference=application_reference,
            environment=environment,
        )

    def create_application(
        self,
        *,
        access_token: str | None,
        name: str,
        application_reference: str = "",
        environment: str = "production",
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.create_application(
            session_token=internal_session,
            name=name,
            application_reference=application_reference,
            environment=environment,
        )

    def list_applications(self, *, access_token: str | None) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.list_applications(session_token=internal_session)

    def list_keys(self, *, access_token: str | None) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.list_keys(session_token=internal_session)

    def rotate_key(
        self,
        *,
        access_token: str | None,
        key_id: str,
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.rotate_key(
            session_token=internal_session,
            key_id=key_id,
        )

    def revoke_key(
        self,
        *,
        access_token: str | None,
        key_id: str,
    ) -> dict[str, Any]:
        context, error = self._authenticated_context(access_token)
        if error:
            return error
        assert context
        _, _, internal_session = context
        return self.storage_product.revoke_key(
            session_token=internal_session,
            key_id=key_id,
        )

    def _authenticated_context(
        self,
        access_token: str | None,
    ) -> tuple[
        tuple[SupabaseIdentity, SelfServeAccount, str] | None,
        dict[str, Any] | None,
    ]:
        identity, reason = self.verifier.verify(access_token)
        if identity is None:
            status = 403 if reason == "supabase_email_confirmation_required" else 401
            return None, self._error(status, reason)
        account = self._map_identity(identity)
        internal_session = self._internal_session(identity, account)
        self.storage_product.repository.save_product(self.product)
        return (identity, account, internal_session), None

    def _map_identity(self, identity: SupabaseIdentity) -> SelfServeAccount:
        existing_id = self.product.accounts.email_index.get(identity.email)
        account = self.product.accounts.accounts.get(existing_id or "")
        if account is None:
            subject_hash = hashlib.sha256(identity.subject.encode("utf-8")).hexdigest()[:16]
            user_id = f"user_sb_{subject_hash}"
            account = SelfServeAccount(
                user_id=user_id,
                name=self._display_name(identity),
                email=identity.email,
                password_salt="",
                password_hash="",
                status="verified",
                email_verification_mode="supabase_auth_email_confirmed",
                created_at=utc_now(),
                verified_at=identity.email_confirmed_at,
            )
            self.product.accounts.accounts[user_id] = account
            self.product.accounts.email_index[identity.email] = user_id
            if hasattr(self.product, "record_activation"):
                self.product.record_activation(
                    user_id=user_id,
                    event_type="account_created",
                    detail={"identity_provider": "supabase", "public_safe": True},
                    once=True,
                )
                self.product.record_activation(
                    user_id=user_id,
                    event_type="email_verified",
                    detail={"identity_provider": "supabase", "public_safe": True},
                    once=True,
                )
        else:
            account.status = "verified"
            account.email_verification_mode = "supabase_auth_email_confirmed"
            account.verified_at = identity.email_confirmed_at
            account.password_salt = ""
            account.password_hash = ""
            if identity.display_name.strip():
                account.name = self._display_name(identity)
        return account

    def _internal_session(
        self,
        identity: SupabaseIdentity,
        account: SelfServeAccount,
    ) -> str:
        cached = self._internal_sessions.get(identity.subject)
        if cached and self.product.accounts.validate_session(cached):
            return cached
        raw_token = f"prmr_session_supabase_bridge_{secrets.token_urlsafe(32)}"
        session = LocalSession(
            session_id=f"session_sb_{uuid4().hex[:12]}",
            user_id=account.user_id,
            token_hash=safe_hash(raw_token),
            status="active",
            created_at=utc_now(),
        )
        self.product.accounts.sessions[session.session_id] = session
        self._internal_sessions[identity.subject] = raw_token
        return raw_token

    def _display_name(self, identity: SupabaseIdentity) -> str:
        clean = " ".join(identity.display_name.split()).strip()
        if 2 <= len(clean) <= 100:
            return clean
        local = identity.email.partition("@")[0].replace(".", " ").replace("_", " ")
        return " ".join(part.capitalize() for part in local.split())[:100] or "PRMR Builder"

    def _public_identity(
        self,
        identity: SupabaseIdentity,
        account: SelfServeAccount,
    ) -> dict[str, Any]:
        return {
            "user_id": account.user_id,
            "email": account.email,
            "status": account.status,
            "email_verification_mode": account.email_verification_mode,
            "supabase_subject_hash": hashlib.sha256(
                identity.subject.encode("utf-8")
            ).hexdigest()[:12],
            "access_token_exposed": False,
        }

    def _error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "error": {"code": code},
            "access_token_exposed": False,
            "boundary": BOUNDARY_V095,
        }


__all__ = [
    "BOUNDARY_V095",
    "FixtureSupabaseIdentityVerifier",
    "SupabaseAuthBridgeV095",
    "SupabaseIdentity",
    "SupabaseRemoteIdentityVerifier",
]
