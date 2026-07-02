"""V0.90 verified Whop event intake and manual approval workflow.

Whop events are verified before parsing, deduplicated by webhook ID, reduced to
minimal safe fields, and stored as pending manual review. No event in this
module can issue a PRMR API key or grant dashboard access.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from prmr.product.hosted_backend_foundation_v069 import utc_now

try:
    from standardwebhooks.webhooks import Webhook
except ImportError:  # pragma: no cover - exercised only in incomplete deployments
    Webhook = None  # type: ignore[assignment]


BOUNDARY_V090 = (
    "V0.90 is a verified Whop-event to manual-review workflow. A valid payment, "
    "membership, or waitlist event creates a review record only. It does not "
    "automatically approve a client, issue a PRMR API key, unlock a dashboard, "
    "or prove production billing."
)

REVIEWABLE_EVENTS = {"entry.created", "payment.succeeded", "membership.activated"}
ATTENTION_EVENTS = {"payment.failed", "membership.deactivated", "refund.created", "dispute.created"}


@dataclass
class WhopReviewRecord:
    webhook_id: str
    event_type: str
    event_created_at: str
    external_resource_id: str
    company_id: str
    product_id: str
    plan_id: str | None
    membership_id: str | None
    external_user_ref_hash: str | None
    amount: float | None
    currency: str | None
    review_status: str
    received_at: str
    reviewed_at: str | None
    reviewed_by: str | None
    review_reason: str | None
    onboarding_started: bool
    api_key_issued: bool
    dashboard_access_granted: bool


class WhopReviewStore:
    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.connection = sqlite3.connect(str(self.storage_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        with self._lock:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS whop_manual_review_v090 (
                    webhook_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    event_created_at TEXT NOT NULL,
                    external_resource_id TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    plan_id TEXT,
                    membership_id TEXT,
                    external_user_ref_hash TEXT,
                    amount REAL,
                    currency TEXT,
                    review_status TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    review_reason TEXT,
                    onboarding_started INTEGER NOT NULL,
                    api_key_issued INTEGER NOT NULL,
                    dashboard_access_granted INTEGER NOT NULL
                )
                """
            )
            self.connection.commit()

    def get(self, webhook_id: str) -> WhopReviewRecord | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM whop_manual_review_v090 WHERE webhook_id = ?",
                (webhook_id,),
            ).fetchone()
        return self.from_row(row) if row else None

    def insert(self, record: WhopReviewRecord) -> bool:
        with self._lock:
            try:
                self.connection.execute(
                    """
                    INSERT INTO whop_manual_review_v090 (
                        webhook_id, event_type, event_created_at,
                        external_resource_id, company_id, product_id, plan_id,
                        membership_id, external_user_ref_hash, amount, currency,
                        review_status, received_at, reviewed_at, reviewed_by,
                        review_reason, onboarding_started, api_key_issued,
                        dashboard_access_granted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.webhook_id,
                        record.event_type,
                        record.event_created_at,
                        record.external_resource_id,
                        record.company_id,
                        record.product_id,
                        record.plan_id,
                        record.membership_id,
                        record.external_user_ref_hash,
                        record.amount,
                        record.currency,
                        record.review_status,
                        record.received_at,
                        record.reviewed_at,
                        record.reviewed_by,
                        record.review_reason,
                        int(record.onboarding_started),
                        int(record.api_key_issued),
                        int(record.dashboard_access_granted),
                    ),
                )
                self.connection.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_review(
        self,
        webhook_id: str,
        *,
        status: str,
        operator_id: str,
        reason: str,
    ) -> WhopReviewRecord | None:
        with self._lock:
            self.connection.execute(
                """
                UPDATE whop_manual_review_v090
                SET review_status = ?, reviewed_at = ?, reviewed_by = ?, review_reason = ?
                WHERE webhook_id = ?
                """,
                (status, utc_now(), operator_id, reason, webhook_id),
            )
            self.connection.commit()
        return self.get(webhook_id)

    def list_records(self) -> list[WhopReviewRecord]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM whop_manual_review_v090 ORDER BY received_at"
            ).fetchall()
        return [self.from_row(row) for row in rows]

    def from_row(self, row: sqlite3.Row) -> WhopReviewRecord:
        payload = dict(row)
        payload["onboarding_started"] = bool(payload["onboarding_started"])
        payload["api_key_issued"] = bool(payload["api_key_issued"])
        payload["dashboard_access_granted"] = bool(payload["dashboard_access_granted"])
        return WhopReviewRecord(**payload)

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def __del__(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass


class WhopManualApprovalV090:
    def __init__(
        self,
        *,
        storage_path: str | Path,
        expected_company_id: str | None,
        expected_product_id: str | None,
    ) -> None:
        self.store = WhopReviewStore(storage_path)
        self.expected_company_id = str(expected_company_id or "").strip()
        self.expected_product_id = str(expected_product_id or "").strip()

    @property
    def configuration_complete(self) -> bool:
        return bool(self.expected_company_id and self.expected_product_id)

    def verify_signature(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        webhook_secret: str | None,
    ) -> tuple[bool, str]:
        secret = str(webhook_secret or "").strip()
        if not secret:
            return False, "webhook_secret_missing"
        if Webhook is None:
            return False, "standardwebhooks_dependency_missing"
        encoded_secret = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        try:
            Webhook(encoded_secret).verify(raw_body, dict(headers))
        except Exception:
            return False, "invalid_webhook_signature"
        return True, "verified"

    def ingest(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        webhook_secret: str | None,
    ) -> dict[str, Any]:
        if not self.configuration_complete:
            return self.error(503, "whop_scope_not_configured")
        verified, reason = self.verify_signature(
            raw_body=raw_body,
            headers=headers,
            webhook_secret=webhook_secret,
        )
        if not verified:
            status_code = 503 if reason in {"webhook_secret_missing", "standardwebhooks_dependency_missing"} else 401
            return self.error(status_code, reason)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.error(400, "invalid_json_payload")
        if not isinstance(payload, dict):
            return self.error(400, "invalid_event_payload")

        normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
        webhook_id = normalized_headers.get("webhook-id", "").strip()
        if not webhook_id:
            return self.error(400, "webhook_id_missing")
        if self.store.get(webhook_id):
            return {
                "ok": True,
                "status_code": 200,
                "status": "already_processed",
                "webhook_id": webhook_id,
                "idempotent_replay": True,
                "access_granted": False,
            }

        event_type = str(payload.get("type") or "")
        if event_type not in REVIEWABLE_EVENTS | ATTENTION_EVENTS:
            return {
                "ok": True,
                "status_code": 202,
                "status": "ignored_event_type",
                "event_type": event_type,
                "access_granted": False,
            }
        data = payload.get("data")
        if not isinstance(data, dict):
            return self.error(400, "event_data_missing")

        company_id = self.value_id(data.get("company")) or str(payload.get("company_id") or "")
        product_id = self.value_id(data.get("product"))
        if company_id != self.expected_company_id:
            return self.error(403, "company_scope_mismatch")
        if product_id != self.expected_product_id:
            return self.error(403, "product_scope_mismatch")

        resource_id = str(data.get("id") or "")
        if not resource_id:
            return self.error(400, "external_resource_id_missing")
        plan_id = self.value_id(data.get("plan"))
        membership_id = self.value_id(data.get("membership"))
        user_id = self.value_id(data.get("user"))
        status = "pending_manual_review" if event_type in REVIEWABLE_EVENTS else "access_review_required"
        amount = self.safe_float(data.get("total"))
        currency = str(data.get("currency") or "").upper() or None
        record = WhopReviewRecord(
            webhook_id=webhook_id,
            event_type=event_type,
            event_created_at=str(payload.get("timestamp") or ""),
            external_resource_id=resource_id,
            company_id=company_id,
            product_id=product_id,
            plan_id=plan_id,
            membership_id=membership_id,
            external_user_ref_hash=self.safe_reference_hash(user_id),
            amount=amount,
            currency=currency,
            review_status=status,
            received_at=utc_now(),
            reviewed_at=None,
            reviewed_by=None,
            review_reason=None,
            onboarding_started=False,
            api_key_issued=False,
            dashboard_access_granted=False,
        )
        inserted = self.store.insert(record)
        if not inserted:
            return {
                "ok": True,
                "status_code": 200,
                "status": "already_processed",
                "webhook_id": webhook_id,
                "idempotent_replay": True,
                "access_granted": False,
            }
        return {
            "ok": True,
            "status_code": 200,
            "status": status,
            "webhook_id": webhook_id,
            "event_type": event_type,
            "review_record": self.public_record(record),
            "access_granted": False,
            "api_key_issued": False,
            "boundary": BOUNDARY_V090,
        }

    def approve_for_manual_onboarding(
        self,
        *,
        webhook_id: str,
        operator_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if not operator_id.strip() or not reason.strip():
            return self.error(400, "operator_and_reason_required")
        record = self.store.get(webhook_id)
        if record is None:
            return self.error(404, "review_record_not_found")
        if record.review_status != "pending_manual_review":
            return self.error(409, "review_record_not_pending")
        updated = self.store.update_review(
            webhook_id,
            status="approved_for_manual_onboarding",
            operator_id=operator_id,
            reason=reason,
        )
        assert updated is not None
        return {
            "ok": True,
            "status_code": 200,
            "status": updated.review_status,
            "manual_onboarding_packet": {
                "webhook_id": updated.webhook_id,
                "event_type": updated.event_type,
                "company_id": updated.company_id,
                "product_id": updated.product_id,
                "external_user_ref_hash": updated.external_user_ref_hash,
                "next_step": "Run V0.80/V0.88 manual onboarding after confirming permitted client details.",
            },
            "api_key_issued": False,
            "dashboard_access_granted": False,
            "boundary": BOUNDARY_V090,
        }

    def reject(
        self,
        *,
        webhook_id: str,
        operator_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if not operator_id.strip() or not reason.strip():
            return self.error(400, "operator_and_reason_required")
        record = self.store.get(webhook_id)
        if record is None:
            return self.error(404, "review_record_not_found")
        updated = self.store.update_review(
            webhook_id,
            status="rejected",
            operator_id=operator_id,
            reason=reason,
        )
        assert updated is not None
        return {
            "ok": True,
            "status_code": 200,
            "status": "rejected",
            "api_key_issued": False,
            "dashboard_access_granted": False,
        }

    def public_records(self) -> list[dict[str, Any]]:
        return [self.public_record(record) for record in self.store.list_records()]

    def public_record(self, record: WhopReviewRecord) -> dict[str, Any]:
        return {
            "webhook_id": record.webhook_id,
            "event_type": record.event_type,
            "company_id": record.company_id,
            "product_id": record.product_id,
            "review_status": record.review_status,
            "received_at": record.received_at,
            "api_key_issued": False,
            "dashboard_access_granted": False,
        }

    def private_record(self, record: WhopReviewRecord) -> dict[str, Any]:
        return asdict(record)

    def error(self, status_code: int, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status_code": status_code,
            "status": "error",
            "error": {"code": code},
            "access_granted": False,
            "api_key_issued": False,
            "dashboard_access_granted": False,
        }

    def value_id(self, value: Any) -> str | None:
        if isinstance(value, dict):
            candidate = value.get("id")
        else:
            candidate = value
        text = str(candidate or "").strip()
        return text or None

    def safe_reference_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"

    def safe_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
