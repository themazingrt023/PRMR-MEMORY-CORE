"""Audit V0.69 hosted backend foundation / product platform base."""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
MODULE_PATH = ROOT / "prmr" / "product" / "hosted_backend_foundation_v069.py"
RUNNER_PATH = ROOT / "examples" / "run_hosted_backend_foundation_v069.py"
REPORT_DIR = ROOT / "reports" / "v069"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_backend_foundation_v069.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_backend_foundation_v069.json"
USAGE_LEDGER = REPORT_DIR / "usage_ledger_v069.json"
REQUEST_LOG = REPORT_DIR / "request_log_v069.json"
SCORECARD = REPORT_DIR / "scorecard_v069.md"

BOUNDARY = (
    "V0.69 is hosted backend foundation/product platform base only. Unless "
    "actually deployed and smoke-tested, it is not a live hosted backend, not "
    "production onboarding, not billing, not live API access, not automatic API "
    "key issuing, not external validation, not bank approval, not compliance "
    "approval, not legal approval, not external security certification, and not "
    "real-world validation."
)

REQUIRED_CLASSES = [
    "Client",
    "APIKeyRecord",
    "Vault",
    "Namespace",
    "UsageLimit",
    "UsageEvent",
    "RequestLog",
    "ContinuityReportRef",
    "AccessDecision",
    "PRMRHostedBackendFoundation",
]

REQUIRED_METHODS = [
    "create_client",
    "create_test_key_record",
    "create_vault",
    "create_namespace",
    "validate_access",
    "log_usage",
    "log_request",
    "register_report",
    "usage_summary",
    "public_status_report",
    "private_status_report",
]

RAW_TEST_KEYS = [
    "prmr_v069_local_alpha_test_key_not_real",
    "prmr_v069_wrong_local_test_key_not_real",
    "prmr_v069_local_alpha_replacement_key_not_real",
]

PRIVATE_TERMS = [
    "key_hash",
    "validation_traces",
    "private_internal",
    "debug",
    "full_api_key",
    "raw_key",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted api is live",
    "is a live hosted backend",
    "live hosted backend is available",
    "live api access granted",
    "automatic api key issuing enabled",
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
        ["python", str(RUNNER_PATH)],
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
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def find_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def contains_raw_keys(text: str) -> bool:
    return any(key in text for key in RAW_TEST_KEYS)


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.69 Hosted Backend Foundation Audit Scorecard",
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
            f"- {'PASS' if runner['passed'] else 'FAIL'}: python examples/run_hosted_backend_foundation_v069.py",
            "- RUN: python examples/audit_v069_hosted_backend_foundation.py",
            "",
            BOUNDARY,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "backend_foundation_module_exists", MODULE_PATH.exists(), str(MODULE_PATH.relative_to(ROOT)))

    module = importlib.import_module("prmr.product.hosted_backend_foundation_v069")
    for class_name in REQUIRED_CLASSES:
        add_check(checks, f"{class_name}_exists", hasattr(module, class_name), class_name)

    foundation_class = getattr(module, "PRMRHostedBackendFoundation")
    for method in REQUIRED_METHODS:
        add_check(checks, f"{method}_exists", hasattr(foundation_class, method), method)

    runner = run_runner()
    add_check(checks, "runner_executes", runner["passed"], runner["output"][-800:])

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, USAGE_LEDGER, REQUEST_LOG, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    usage_ledger = read_json(USAGE_LEDGER) if USAGE_LEDGER.exists() else {}
    request_log = read_json(REQUEST_LOG) if REQUEST_LOG.exists() else {}

    public_text = json.dumps(public_report, sort_keys=True)
    private_text = json.dumps(private_report, sort_keys=True)
    usage_events = usage_ledger.get("usage_events", [])
    request_logs = request_log.get("request_logs", [])

    check_names = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}
    add_check(checks, "valid_key_allowed", check_names.get("valid_key_allowed") is True, check_names.get("valid_key_allowed"))
    add_check(checks, "missing_key_blocked", check_names.get("missing_key_blocked") is True, check_names.get("missing_key_blocked"))
    add_check(checks, "wrong_key_blocked", check_names.get("wrong_key_blocked") is True, check_names.get("wrong_key_blocked"))
    add_check(checks, "revoked_key_blocked", check_names.get("revoked_key_blocked") is True, check_names.get("revoked_key_blocked"))
    add_check(checks, "wrong_vault_blocked", check_names.get("wrong_vault_blocked") is True, check_names.get("wrong_vault_blocked"))
    add_check(checks, "wrong_namespace_blocked", check_names.get("wrong_namespace_blocked") is True, check_names.get("wrong_namespace_blocked"))
    add_check(checks, "usage_limit_enforced", check_names.get("usage_limit_enforced") is True, check_names.get("usage_limit_enforced"))
    add_check(checks, "usage_is_logged", len(usage_events) >= 8, len(usage_events))
    add_check(checks, "request_log_is_logged", len(request_logs) >= 8, len(request_logs))

    blocked_reasons = {item.get("reason") for item in request_logs if item.get("status") == "blocked"}
    add_check(
        checks,
        "blocked_request_reasons_logged",
        {"missing_key", "invalid_key", "revoked_key", "vault_denied", "namespace_denied", "usage_limit_exceeded"}.issubset(blocked_reasons),
        sorted(blocked_reasons),
    )

    add_check(checks, "public_report_contains_no_raw_keys", not contains_raw_keys(public_text), "raw key absent")
    private_hits = find_terms(public_text, PRIVATE_TERMS)
    add_check(checks, "public_report_contains_no_private_internals", not private_hits, private_hits)
    add_check(checks, "private_report_exists", bool(private_report), str(PRIVATE_REPORT.relative_to(ROOT)))
    add_check(checks, "private_report_has_validation_trace", "validation_traces" in private_text, "validation_traces")

    overclaim_hits = find_terms(public_text, OVERCLAIMS)
    punitive_hits = find_terms(public_text, PUNITIVE_TERMS)
    add_check(checks, "no_production_or_hosted_live_claims", not overclaim_hits, overclaim_hits)
    add_check(checks, "no_billing_claims", "billing enabled" not in public_text.lower(), "billing not enabled")
    add_check(checks, "no_approval_or_certification_claims", not any("approved" in hit or "certified" in hit for hit in overclaim_hits), overclaim_hits)
    add_check(checks, "no_punitive_wording", not punitive_hits, punitive_hits)
    add_check(checks, "no_real_client_data_used", "example.test" in private_text and "real client data" not in public_text.lower(), "synthetic example.test only")

    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.69 HOSTED BACKEND FOUNDATION AUDIT")
    print("------------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Command results:")
    print(f"- python examples/run_hosted_backend_foundation_v069.py: {'PASS' if runner['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {USAGE_LEDGER.relative_to(ROOT)}")
    print(f"- {REQUEST_LOG.relative_to(ROOT)}")
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
