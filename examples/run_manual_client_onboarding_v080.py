"""Run V0.80 manual client onboarding locally.

This creates one synthetic/manual alpha client, issues one fresh key, writes a
private one-time key packet, and writes public-safe onboarding evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.manual_client_onboarding_v080 import BOUNDARY_V080, ManualClientOnboarding


REPORT_DIR = ROOT / "reports" / "v080"
PUBLIC_REPORT = REPORT_DIR / "public_manual_client_onboarding_v080.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_manual_client_onboarding_v080.json"
PRIVATE_KEY_PACKET = REPORT_DIR / "private_one_time_key_packet_v080.json"
SCORECARD = REPORT_DIR / "scorecard_v080.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.80 Manual Client Onboarding",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Private one-time key packet: {PRIVATE_KEY_PACKET.as_posix()}",
        "",
        f"Boundary: {BOUNDARY_V080}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command", "", "- RUN: python examples/run_manual_client_onboarding_v080.py", ""])
    return "\n".join(lines)


def run_onboarding() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    onboarding = ManualClientOnboarding()
    trace: dict[str, Any] = {}

    create_result = onboarding.create_manual_alpha_client()
    onboarding_id = create_result["onboarding_id"]
    record = create_result["record"]
    trace["create_result_safe"] = create_result
    add_check(checks, "client_record_created", create_result["ok"] and bool(record["client_id"]), record["client_id"])
    add_check(checks, "vault_created", bool(record["vault_id"]), record["vault_id"])
    add_check(checks, "namespace_created", bool(record["namespace"]), record["namespace"])
    add_check(checks, "fresh_key_issued", bool(record["key_id"]) and bool(record["safe_key_preview"]), record["safe_key_preview"])
    add_check(checks, "safe_key_hash_prefix_present", bool(record["key_hash_prefix"]), record["key_hash_prefix"])
    add_check(checks, "initial_status_pending_manual_delivery", record["status"] == "pending_manual_delivery", record["status"])

    one_time_packet = onboarding.one_time_key_packet(onboarding_id)
    raw_key = one_time_packet.get("alpha_api_key")
    second_packet = onboarding.one_time_key_packet(onboarding_id)
    add_check(checks, "private_one_time_packet_contains_key_once", bool(raw_key) and second_packet.get("alpha_api_key") is None, {"first_returned": bool(raw_key), "second_returned": bool(second_packet.get("alpha_api_key"))})
    add_check(checks, "private_packet_marked_local_private_only", one_time_packet.get("local_private_only") is True and one_time_packet.get("do_not_commit") is True, None)

    delivered = onboarding.mark_delivered(
        onboarding_id,
        operator_id="operator_v080_founder",
        delivery_note="Synthetic packet marked delivered for local workflow verification.",
    )
    add_check(checks, "status_can_be_marked_delivered", delivered.get("status") == "delivered", delivered.get("status"))

    validation = onboarding.validate_key(onboarding_id=onboarding_id, raw_key=raw_key, operation="events_ingest", count=1)
    trace["validation_before_revoke"] = validation
    add_check(checks, "issued_key_validates_locally", validation.get("allowed") is True and validation.get("status_code") == 200, validation)

    revoke = onboarding.revoke(onboarding_id, operator_id="operator_v080_founder", reason="Synthetic revoke path verification.")
    add_check(checks, "revoke_path_works", revoke.get("ok") is True and revoke.get("status") == "revoked", revoke)

    validation_after_revoke = onboarding.validate_key(onboarding_id=onboarding_id, raw_key=raw_key, operation="events_ingest", count=1)
    trace["validation_after_revoke"] = validation_after_revoke
    add_check(checks, "revoked_key_is_blocked", validation_after_revoke.get("allowed") is False and validation_after_revoke.get("reason") == "revoked_key", validation_after_revoke)

    public_report = onboarding.public_onboarding_summary(checks)
    add_check(checks, "raw_key_absent_from_public_report", raw_key not in json.dumps(public_report, sort_keys=True), None)
    add_check(checks, "public_report_contains_no_secret_patterns", not contains_secret_pattern(public_report), None)
    add_check(checks, "no_real_client_data_used_by_default", "Synthetic V0.80" in record["organisation"] and record["contact_email"].endswith(".test"), record["organisation"])
    add_check(checks, "no_self_serve_or_billing_claim", public_report["workflow"]["self_serve_signup"] is False and public_report["workflow"]["billing_enabled"] is False, public_report["workflow"])

    public_report = onboarding.public_onboarding_summary(checks)
    private_report = onboarding.private_onboarding_report(checks, trace)
    return public_report, private_report, one_time_packet, checks


def main() -> int:
    public_report, private_report, one_time_packet, checks = run_onboarding()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(PRIVATE_KEY_PACKET, one_time_packet)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.80 Manual Client Onboarding")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Private one-time key packet: {PRIVATE_KEY_PACKET.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Onboarding records: {len(public_report.get('onboarding_records', []))}")
    print(f"Private packet contains credential value: {one_time_packet.get('credential_value_present')}")
    print(f"Public report contains credential value: {public_report.get('workflow', {}).get('credential_value_in_public_report')}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
