"""Audit V0.70 manual API key lifecycle layer."""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

FOUNDATION_MODULE = ROOT / "prmr" / "product" / "hosted_backend_foundation_v069.py"
LIFECYCLE_MODULE = ROOT / "prmr" / "product" / "api_key_lifecycle_v070.py"
RUNNER = ROOT / "examples" / "run_api_key_lifecycle_v070.py"
REPORT_DIR = ROOT / "reports" / "v070"
PUBLIC_REPORT = REPORT_DIR / "public_api_key_lifecycle_v070.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_key_lifecycle_v070.json"
LIFECYCLE_EVENTS = REPORT_DIR / "key_lifecycle_events_v070.json"
USAGE_SUMMARY = REPORT_DIR / "usage_summary_v070.json"
SCORECARD = REPORT_DIR / "scorecard_v070.md"

BOUNDARY = (
    "V0.70 is a local/simulated manual API key lifecycle layer only. Unless "
    "actually deployed and smoke-tested, it is not live hosted API access, not "
    "production onboarding, not billing, not self-serve signup, not external "
    "validation, not bank approval, not compliance approval, not legal approval, "
    "not external security certification, and not real-world validation."
)

REQUIRED_FUNCTIONS = [
    "create_client",
    "create_vault",
    "create_namespace",
    "issue_alpha_key",
    "validate_key",
    "rotate_key",
    "revoke_key",
    "suspend_client",
    "reactivate_client",
    "get_client_usage",
    "get_key_status",
    "export_key_lifecycle_report",
]

EXPECTED_CHECKS = [
    "create_synthetic_client",
    "create_vault",
    "create_namespace",
    "issue_without_operator_approval_blocked",
    "issue_with_operator_approval_works",
    "active_key_validates",
    "missing_key_blocked",
    "wrong_key_blocked",
    "rotate_key_works",
    "old_rotated_key_blocked",
    "rotated_new_key_validates",
    "revoked_key_blocked",
    "suspended_client_blocks_validation",
    "reactivated_client_key_validates",
    "usage_logs_allowed_and_blocked",
    "lifecycle_event_history_exists",
    "public_report_contains_no_raw_keys",
    "private_report_contains_no_raw_keys_persisted",
]

PRIVATE_TERMS_PUBLIC = [
    "raw_api_key",
    "full_api_key",
    "key_hash",
    "validation_outcomes",
    "approval_trace",
    "private_internal",
    "debug",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted api is live",
    "is live hosted api access",
    "live api access granted",
    "automatic key issuing enabled",
    "billing enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external certification complete",
    "external validation complete",
    "real-world validated",
    "real client data",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run_runner() -> dict[str, Any]:
    completed = subprocess.run(
        ["python", str(RUNNER)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "output": completed.stdout,
    }


def find_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def contains_full_dev_key(text: str) -> bool:
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.70 Manual API Key Lifecycle Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    lines.extend(
        [
            "",
            "## Command Results",
            "",
            f"- {'PASS' if runner['passed'] else 'FAIL'}: python examples/run_api_key_lifecycle_v070.py",
            "- RUN: python examples/audit_v070_api_key_lifecycle.py",
            "",
            BOUNDARY,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "v069_foundation_module_exists", FOUNDATION_MODULE.exists(), str(FOUNDATION_MODULE.relative_to(ROOT)))
    add_check(checks, "v070_lifecycle_module_exists", LIFECYCLE_MODULE.exists(), str(LIFECYCLE_MODULE.relative_to(ROOT)))

    module = importlib.import_module("prmr.product.api_key_lifecycle_v070")
    lifecycle_class = getattr(module, "PRMRAPIKeyLifecycle", None)
    add_check(checks, "PRMRAPIKeyLifecycle_exists", lifecycle_class is not None, "PRMRAPIKeyLifecycle")
    for func in REQUIRED_FUNCTIONS:
        add_check(checks, f"{func}_exists", hasattr(lifecycle_class, func), func)

    runner = run_runner()
    add_check(checks, "runner_executes", runner["passed"], runner["output"][-800:])

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, LIFECYCLE_EVENTS, USAGE_SUMMARY, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    lifecycle_events = read_json(LIFECYCLE_EVENTS) if LIFECYCLE_EVENTS.exists() else {}
    usage_summary = read_json(USAGE_SUMMARY) if USAGE_SUMMARY.exists() else {}

    public_text = json.dumps(public_report, sort_keys=True)
    private_text = json.dumps(private_report, sort_keys=True)
    event_text = json.dumps(lifecycle_events, sort_keys=True)
    usage_text = json.dumps(usage_summary, sort_keys=True)

    private_checks = {item.get("name"): item.get("passed") for item in private_report.get("checks", [])}
    for check_name in EXPECTED_CHECKS:
        add_check(checks, check_name, private_checks.get(check_name) is True, private_checks.get(check_name))

    key_records = private_report.get("lifecycle_key_records", {})
    add_check(
        checks,
        "key_hash_stored_as_safe_hash_reference",
        bool(key_records) and all(str(record.get("key_hash", "")).startswith("sha256:") for record in key_records.values()),
        list(key_records),
    )
    add_check(
        checks,
        "safe_key_preview_stored",
        bool(key_records) and all("..." in str(record.get("safe_key_preview", "")) for record in key_records.values()),
        [record.get("safe_key_preview") for record in key_records.values()],
    )
    add_check(
        checks,
        "lifecycle_event_history_exists",
        len(lifecycle_events.get("events", [])) >= 7,
        len(lifecycle_events.get("events", [])),
    )

    usage = usage_summary.get("usage", {})
    add_check(checks, "usage_logs_allowed_requests", usage.get("allowed_request_count", 0) >= 3, usage.get("allowed_request_count"))
    add_check(checks, "usage_logs_blocked_requests", usage.get("blocked_request_count", 0) >= 5, usage.get("blocked_request_count"))

    add_check(checks, "public_report_contains_no_raw_keys", not contains_full_dev_key(public_text), "none")
    add_check(checks, "private_report_contains_no_raw_keys_persisted", not contains_full_dev_key(private_text), "none")
    add_check(checks, "event_report_contains_no_raw_keys_persisted", not contains_full_dev_key(event_text), "none")
    add_check(checks, "usage_report_contains_no_raw_keys_persisted", not contains_full_dev_key(usage_text), "none")

    public_private_hits = find_terms(public_text, PRIVATE_TERMS_PUBLIC)
    add_check(checks, "public_report_contains_no_private_internals", not public_private_hits, public_private_hits)

    overclaim_hits = find_terms(public_text, OVERCLAIMS)
    punitive_hits = find_terms(public_text, PUNITIVE_TERMS)
    add_check(checks, "no_production_or_live_hosted_claims", not overclaim_hits, overclaim_hits)
    add_check(checks, "no_billing_claims", "billing enabled" not in public_text.lower(), "billing not enabled")
    add_check(checks, "no_approval_or_certification_claims", not any("approved" in hit or "certified" in hit for hit in overclaim_hits), overclaim_hits)
    add_check(checks, "no_punitive_wording", not punitive_hits, punitive_hits)
    add_check(checks, "no_real_client_data_used", "example.test" in private_text and "real client data" not in public_text.lower(), "synthetic example.test only")

    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.70 API KEY LIFECYCLE AUDIT")
    print("----------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Command results:")
    print(f"- python examples/run_api_key_lifecycle_v070.py: {'PASS' if runner['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {LIFECYCLE_EVENTS.relative_to(ROOT)}")
    print(f"- {USAGE_SUMMARY.relative_to(ROOT)}")
    print(f"- {SCORECARD.relative_to(ROOT)}")

    if result != "PASS":
        print("Failures:")
        for check in checks:
            if not check["passed"]:
                print(f"- {check['name']}: {check['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
