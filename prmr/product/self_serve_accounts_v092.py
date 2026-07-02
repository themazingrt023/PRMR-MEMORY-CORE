"""Generic self-serve account model for PRMR Memory Core V0.92.

Passwords are PBKDF2 hashed. Email verification and sessions are local MVP
state only; no email provider or production identity service is claimed.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from prmr.product.hosted_backend_foundation_v069 import safe_hash, utc_now


ACCOUNT_BOUNDARY_V092 = (
    "V0.92 accounts use local/deployable MVP state with PBKDF2 password hashing, "
    "simulated email verification, and local session tokens. This is not "
    "production authentication or real email delivery."
)


@dataclass
class SelfServeAccount:
    user_id: str
    name: str
    email: str
    password_salt: str
    password_hash: str
    status: str
    email_verification_mode: str
    created_at: str
    verified_at: str | None


@dataclass
class LocalSession:
    session_id: str
    user_id: str
    token_hash: str
    status: str
    created_at: str


class SelfServeAccountsV092:
    def __init__(self) -> None:
        self.accounts: dict[str, SelfServeAccount] = {}
        self.email_index: dict[str, str] = {}
        self.sessions: dict[str, LocalSession] = {}

    def create_user(self, *, name: str, email: str, password: str) -> dict[str, Any]:
        clean_name = " ".join(name.split()).strip()
        normalized_email = email.strip().lower()
        if len(clean_name) < 2:
            return self.error(400, "name_required")
        if "@" not in normalized_email or len(normalized_email) > 254:
            return self.error(400, "valid_email_required")
        if normalized_email in self.email_index:
            return self.error(409, "email_already_registered")
        if len(password) < 10:
            return self.error(400, "password_too_short")

        salt = secrets.token_hex(16)
        account = SelfServeAccount(
            user_id=f"user_ss_{uuid4().hex[:12]}",
            name=clean_name,
            email=normalized_email,
            password_salt=salt,
            password_hash=self.hash_password(password, salt),
            status="unverified",
            email_verification_mode="local_simulated_no_email_sent",
            created_at=utc_now(),
            verified_at=None,
        )
        self.accounts[account.user_id] = account
        self.email_index[account.email] = account.user_id
        return {
            "ok": True,
            "status_code": 201,
            "account": self.public_account(account),
            "email_sent": False,
            "next_step": "Use the local MVP verification action. No email was sent.",
            "boundary": ACCOUNT_BOUNDARY_V092,
        }

    def verify_email_local(self, *, user_id: str) -> dict[str, Any]:
        account = self.accounts.get(user_id)
        if account is None:
            return self.error(404, "account_not_found")
        if account.status == "suspended":
            return self.error(403, "account_suspended")
        account.status = "verified"
        account.verified_at = utc_now()
        return {
            "ok": True,
            "status_code": 200,
            "account": self.public_account(account),
            "verification_simulated": True,
            "email_sent": False,
            "boundary": ACCOUNT_BOUNDARY_V092,
        }

    def login(self, *, email: str, password: str) -> dict[str, Any]:
        user_id = self.email_index.get(email.strip().lower())
        account = self.accounts.get(user_id or "")
        if account is None or not self.verify_password(password, account.password_salt, account.password_hash):
            return self.error(401, "invalid_login")
        if account.status != "verified":
            return self.error(403, "email_verification_required")
        raw_token = f"prmr_session_local_{secrets.token_urlsafe(32)}"
        session = LocalSession(
            session_id=f"session_ss_{uuid4().hex[:12]}",
            user_id=account.user_id,
            token_hash=safe_hash(raw_token),
            status="active",
            created_at=utc_now(),
        )
        self.sessions[session.session_id] = session
        return {
            "ok": True,
            "status_code": 200,
            "session_token": raw_token,
            "returned_once": True,
            "account": self.public_account(account),
            "boundary": ACCOUNT_BOUNDARY_V092,
        }

    def validate_session(self, raw_token: str | None) -> SelfServeAccount | None:
        if not raw_token:
            return None
        token_hash = safe_hash(raw_token)
        for session in self.sessions.values():
            if session.token_hash == token_hash and session.status == "active":
                account = self.accounts.get(session.user_id)
                if account and account.status == "verified":
                    return account
        return None

    def suspend(self, *, user_id: str) -> dict[str, Any]:
        account = self.accounts.get(user_id)
        if account is None:
            return self.error(404, "account_not_found")
        account.status = "suspended"
        for session in self.sessions.values():
            if session.user_id == user_id:
                session.status = "revoked"
        return {"ok": True, "status_code": 200, "account": self.public_account(account)}

    def public_account(self, account: SelfServeAccount) -> dict[str, Any]:
        return {
            "user_id": account.user_id,
            "name": account.name,
            "email": account.email,
            "status": account.status,
            "email_verification_mode": account.email_verification_mode,
            "created_at": account.created_at,
            "verified_at": account.verified_at,
            "password_exposed": False,
        }

    def hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            310_000,
        ).hex()

    def verify_password(self, password: str, salt: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.hash_password(password, salt), expected_hash)

    def error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "error": {"code": code},
            "boundary": ACCOUNT_BOUNDARY_V092,
        }

