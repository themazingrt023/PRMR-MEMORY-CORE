"""Run V0.90 verified Whop event intake and manual-review smoke."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from standardwebhooks.webhooks import Webhook

from prmr.product.api_config_v075 import PRMRAPIConfig
from prmr.product.whop_manual_approval_v090 import (
    BOUNDARY_V090,
    WhopManualApprovalV090,
)


REPORT_DIR = ROOT / "reports" / "v090"
PUBLIC_REPORT = REPORT_DIR / "public_whop_manual_approval_v090.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_whop_manual_approval_v090.json"
SMOKE_REPORT = REPORT_DIR / "whop_manual_approval_smoke_v090.json"
SCORECARD = REPORT_DIR / "scorecard_v090.md"

SYNTHETIC_SECRET = "synthetic-v090-standard-webhook-secret"
COMPANY_ID = "biz_v090_synthetic"
PRODUCT_ID = "prod_v090_synthetic"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def event_payload(
    *,
    webhook_id: str,
    event_type: str = "payment.succeeded",
    product_id: str = PRODUCT_ID,
    resource_id: str = "pay_v090_synthetic_001",
) -> dict[str, Any]:
    return {
        "id": webhook_id,
        "api_version": "v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "company_id": COMPANY_ID,
        "data": {
            "id": resource_id,
            "company": {"id": COMPANY_ID},
            "product": {"id": product_id, "title": "PRMR Controlled Alpha Pilot"},
            "plan": {"id": "plan_v090_synthetic"},
            "membership": {"id": "mem_v090_synthetic"},
            "user": {
                "id": "user_v090_synthetic",
                "name": "Synthetic Tester",
                "email": "synthetic-v090@example.test",
            },
            "total": 250,
            "currency": "gbp",
            "payment_method": {"card": {"last4": "4242"}},
        },
    }


def signed_request(payload: dict[str, Any], secret: str = SYNTHETIC_SECRET) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    webhook_id = str(payload["id"])
    timestamp = datetime.now(timezone.utc)
    encoded_secret = base64.b64encode(secret.encode("utf-8")).decode("ascii")
    signature = Webhook(encoded_secret).sign(
        msg_id=webhook_id,
        timestamp=timestamp,
        data=body.decode("utf-8"),
    )
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": str(int(timestamp.timestamp())),
        "webhook-signature": signature,
        "content-type": "application/json",
    }
    return body, headers


@contextmanager
def temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def contains_secret_or_pii(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        re.escape(SYNTHETIC_SECRET),
        r"synthetic-v090@example\.test",
        r"Synthetic Tester",
        r'"last4"\s*:',
        r"\bprmr_alpha_(?:dev|local)_[a-f0-9]{20,}\b",
        r"\bwhsec_[A-Za-z0-9_-]{12,}\b",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="prmr-v090-", ignore_cleanup_errors=True) as temp_dir:
        storage_path = Path(temp_dir) / "v090.sqlite"
        workflow = WhopManualApprovalV090(
            storage_path=storage_path,
            expected_company_id=COMPANY_ID,
            expected_product_id=PRODUCT_ID,
        )
        payload = event_payload(webhook_id="msg_v090_payment_001")
        body, headers = signed_request(payload)

        missing_secret = workflow.ingest(raw_body=body, headers=headers, webhook_secret=None)
        add(
            checks,
            "missing_webhook_secret_fails_closed",
            missing_secret["status_code"] == 503
            and missing_secret["error"]["code"] == "webhook_secret_missing",
        )
        invalid_headers = {**headers, "webhook-signature": "v1,ZmFrZS1zaWduYXR1cmU="}
        invalid = workflow.ingest(
            raw_body=body,
            headers=invalid_headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        add(
            checks,
            "invalid_signature_is_rejected",
            invalid["status_code"] == 401 and invalid["error"]["code"] == "invalid_webhook_signature",
        )
        add(checks, "failed_verification_does_not_create_record", workflow.public_records() == [])

        wrong_payload = event_payload(
            webhook_id="msg_v090_wrong_product",
            product_id="prod_v090_wrong",
            resource_id="pay_v090_wrong",
        )
        wrong_body, wrong_headers = signed_request(wrong_payload)
        wrong_scope = workflow.ingest(
            raw_body=wrong_body,
            headers=wrong_headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        add(
            checks,
            "wrong_product_scope_is_rejected",
            wrong_scope["status_code"] == 403 and wrong_scope["error"]["code"] == "product_scope_mismatch",
        )

        accepted = workflow.ingest(
            raw_body=body,
            headers=headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        add(
            checks,
            "valid_signed_payment_creates_pending_review",
            accepted["status_code"] == 200
            and accepted["status"] == "pending_manual_review"
            and accepted["access_granted"] is False,
            {"status": accepted.get("status")},
        )
        add(
            checks,
            "verified_event_does_not_issue_access",
            accepted["api_key_issued"] is False
            and accepted["review_record"]["api_key_issued"] is False
            and accepted["review_record"]["dashboard_access_granted"] is False,
        )

        duplicate = workflow.ingest(
            raw_body=body,
            headers=headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        add(
            checks,
            "duplicate_delivery_is_idempotent",
            duplicate["status"] == "already_processed"
            and duplicate["idempotent_replay"] is True
            and len(workflow.public_records()) == 1,
        )

        approval = workflow.approve_for_manual_onboarding(
            webhook_id="msg_v090_payment_001",
            operator_id="operator_v090_founder",
            reason="Synthetic scope reviewed for manual onboarding smoke.",
        )
        add(
            checks,
            "operator_approval_creates_manual_handoff_only",
            approval["status"] == "approved_for_manual_onboarding"
            and approval["api_key_issued"] is False
            and approval["dashboard_access_granted"] is False
            and approval["manual_onboarding_packet"]["next_step"].startswith("Run V0.80/V0.88"),
        )

        rejected_payload = event_payload(
            webhook_id="msg_v090_payment_002",
            resource_id="pay_v090_synthetic_002",
        )
        rejected_body, rejected_headers = signed_request(rejected_payload)
        workflow.ingest(
            raw_body=rejected_body,
            headers=rejected_headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        rejection = workflow.reject(
            webhook_id="msg_v090_payment_002",
            operator_id="operator_v090_founder",
            reason="Synthetic rejection path.",
        )
        add(
            checks,
            "operator_rejection_grants_no_access",
            rejection["status"] == "rejected"
            and rejection["api_key_issued"] is False
            and rejection["dashboard_access_granted"] is False,
        )

        attention_payload = event_payload(
            webhook_id="msg_v090_refund_001",
            event_type="refund.created",
            resource_id="refund_v090_synthetic_001",
        )
        attention_body, attention_headers = signed_request(attention_payload)
        attention = workflow.ingest(
            raw_body=attention_body,
            headers=attention_headers,
            webhook_secret=SYNTHETIC_SECRET,
        )
        add(
            checks,
            "refund_or_adverse_event_requires_review",
            attention["status"] == "access_review_required"
            and attention["api_key_issued"] is False,
        )

        records = workflow.store.list_records()
        private_records = [workflow.private_record(record) for record in records]
        public_records = workflow.public_records()
        add(
            checks,
            "stored_records_exclude_raw_pii_and_payment_method",
            not contains_secret_or_pii(private_records)
            and all(record.external_user_ref_hash for record in records),
        )
        add(checks, "sqlite_idempotency_store_exists", storage_path.exists() and len(records) == 3)

        config = PRMRAPIConfig(
            api_mode="local_alpha",
            storage_path=Path(temp_dir) / "v090-http.sqlite",
            synthetic_only=True,
            public_reports_dir=Path(temp_dir) / "public",
            private_reports_dir=Path(temp_dir) / "private",
            allowed_alpha_mode=True,
            default_max_events_per_day=10,
            default_max_packets_per_day=10,
            default_max_reports_per_day=10,
            allowed_origins=["http://localhost:3000"],
        )
        http_payload = event_payload(
            webhook_id="msg_v090_http_001",
            resource_id="pay_v090_http_001",
        )
        http_body, http_headers = signed_request(http_payload)
        with temporary_environment(
            {
                "WHOP_WEBHOOK_SECRET": SYNTHETIC_SECRET,
                "WHOP_EXPECTED_COMPANY_ID": COMPANY_ID,
                "WHOP_EXPECTED_PRODUCT_ID": PRODUCT_ID,
            }
        ):
            from fastapi.testclient import TestClient
            from prmr.product.api_server_v090 import create_app_v090

            app = create_app_v090(config=config)
            with TestClient(app) as client:
                http_response = client.post(
                    "/v1/integrations/whop/webhook",
                    content=http_body,
                    headers=http_headers,
                )
            app.state.whop_manual_approval_v090.store.close()
        add(
            checks,
            "fastapi_webhook_route_accepts_verified_event",
            http_response.status_code == 200
            and http_response.json()["status"] == "pending_manual_review",
            {"status_code": http_response.status_code},
        )

        public_evidence = {
            "signature_verification": "standardwebhooks_1_0_1",
            "storage": "sqlite_idempotent_webhook_id",
            "reviewable_events": [
                "entry.created",
                "payment.succeeded",
                "membership.activated",
            ],
            "attention_events": [
                "payment.failed",
                "membership.deactivated",
                "refund.created",
                "dispute.created",
            ],
            "records": public_records,
            "accepted_event_status": accepted["status"],
            "duplicate_status": duplicate["status"],
            "approval_status": approval["status"],
            "rejection_status": rejection["status"],
            "http_route_status": http_response.status_code,
            "automatic_key_issuing": False,
            "automatic_dashboard_access": False,
            "live_whop_event_verified": False,
            "hosted_v090_deployment_verified": False,
        }
        provisional = {
            "version": "0.90",
            "company": "Afternum Industries",
            "product": "PRMR Memory Core",
            "title": "Whop to Manual Approval Workflow",
            "truth_label": "local verified synthetic Whop-event and manual-review evidence only",
            "boundary": BOUNDARY_V090,
            "evidence": public_evidence,
        }
        add(checks, "public_report_contains_no_secret_or_pii", not contains_secret_or_pii(provisional))

        passed = sum(1 for check in checks if check["passed"])
        total = len(checks)
        result = "PASS" if passed == total else "NEEDS_WORK"
        public_report = {
            **provisional,
            "result": result,
            "checks_passed": passed,
            "checks_total": total,
            "public_safe": True,
        }
        private_report = {
            **public_report,
            "public_safe": False,
            "checks": checks,
            "records": private_records,
            "restricted_note": "Synthetic private trace excludes webhook secrets, raw PII, payment-method details, and PRMR credentials.",
        }
        smoke_report = {
            "version": "0.90",
            "result": result,
            "public_safe": True,
            "boundary": BOUNDARY_V090,
            "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
            "external_state": {
                "live_whop_product": False,
                "live_webhook_delivery": False,
                "real_payment": False,
                "hosted_v090_entrypoint": False,
            },
        }
        workflow.store.close()
    return public_report, private_report, smoke_report, checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.90 Whop to Manual Approval Workflow",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V090}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(
        [
            "",
            "## External state",
            "",
            "- Live Whop webhook: NOT VERIFIED",
            "- Real payment: NOT VERIFIED",
            "- V0.90 hosted entrypoint: NOT DEPLOYED",
            "- Automatic API key issuing: DISABLED",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")
    print("PRMR Memory Core V0.90 Whop to Manual Approval Workflow")
    print("Signed synthetic event: verified")
    print("Duplicate delivery: idempotent")
    print("Payment result: pending manual review")
    print("Automatic key/dashboard access: disabled")
    print("Live Whop event: NOT VERIFIED")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
