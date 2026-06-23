"""Audit V0.71 controlled-alpha API surface."""

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

FOUNDATION = ROOT / "prmr" / "product" / "hosted_backend_foundation_v069.py"
LIFECYCLE = ROOT / "prmr" / "product" / "api_key_lifecycle_v070.py"
API_SURFACE = ROOT / "prmr" / "product" / "controlled_alpha_api_v071.py"
RUNNER = ROOT / "examples" / "run_controlled_alpha_api_v071.py"
REPORT_DIR = ROOT / "reports" / "v071"
PUBLIC_REPORT = REPORT_DIR / "public_controlled_alpha_api_v071.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_controlled_alpha_api_v071.json"
REQUEST_LOG = REPORT_DIR / "api_request_log_v071.json"
USAGE_SUMMARY = REPORT_DIR / "api_usage_summary_v071.json"
SCORECARD = REPORT_DIR / "scorecard_v071.md"

BOUNDARY = (
    "V0.71 is a local/deployable controlled-alpha API surface only. Unless "
    "actually hosted and smoke-tested, it is not live hosted API access, not "
    "production onboarding, not billing, not self-serve signup, not external "
    "validation, not bank approval, not compliance approval, not legal approval, "
    "not external security certification, and not real-world validation."
)

REQUIRED_HANDLERS = [
    "events_ingest",
    "continuity_packet",
    "memory_reconstruct",
    "explain",
    "least_harm_action",
    "get_report",
    "get_usage",
]

EXPECTED_CHECKS = [
    "valid_ingest_works",
    "continuity_packet_works",
    "memory_reconstruct_works",
    "explain_works",
    "least_harm_action_works",
    "report_read_works",
    "usage_read_works",
    "missing_key_blocked",
    "wrong_key_blocked",
    "revoked_key_blocked",
    "rotated_old_key_blocked",
    "rotated_new_key_validates",
    "wrong_client_blocked",
    "wrong_vault_blocked",
    "wrong_namespace_blocked",
    "usage_limit_enforced",
    "usage_logged",
    "request_log_created",
    "public_report_contains_no_raw_keys",
    "private_report_contains_no_raw_keys_persisted",
]

PRIVATE_TERMS_PUBLIC = [
    "raw_api_key",
    "full_api_key",
    "private_internal",
    "key_hash",
    "validation_outcomes",
    "debug",
    "private_trace",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted api is live",
    "is live hosted api access",
    "live api access granted",
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
        "# V0.71 Controlled-Alpha API Surface Audit Scorecard",
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
            f"- {'PASS' if runner['passed'] else 'FAIL'}: python examples/run_controlled_alpha_api_v071.py",
            "- RUN: python examples/audit_v071_controlled_alpha_api.py",
            "",
            BOUNDARY,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "v069_foundation_exists", FOUNDATION.exists(), str(FOUNDATION.relative_to(ROOT)))
    add_check(checks, "v070_lifecycle_exists", LIFECYCLE.exists(), str(LIFECYCLE.relative_to(ROOT)))
    add_check(checks, "v071_api_surface_exists", API_SURFACE.exists(), str(API_SURFACE.relative_to(ROOT)))

    module = importlib.import_module("prmr.product.controlled_alpha_api_v071")
    api_class = getattr(module, "PRMRControlledAlphaAPI", None)
    add_check(checks, "PRMRControlledAlphaAPI_exists", api_class is not None, "PRMRControlledAlphaAPI")
    for handler in REQUIRED_HANDLERS:
        add_check(checks, f"{handler}_handler_exists", hasattr(api_class, handler), handler)

    runner = run_runner()
    add_check(checks, "runner_executes", runner["passed"], runner["output"][-800:])

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, REQUEST_LOG, USAGE_SUMMARY, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    request_log = read_json(REQUEST_LOG) if REQUEST_LOG.exists() else {}
    usage_summary = read_json(USAGE_SUMMARY) if USAGE_SUMMARY.exists() else {}

    private_checks = {item.get("name"): item.get("passed") for item in private_report.get("checks", [])}
    for check_name in EXPECTED_CHECKS:
        add_check(checks, check_name, private_checks.get(check_name) is True, private_checks.get(check_name))

    public_text = json.dumps(public_report, sort_keys=True)
    private_text = json.dumps(private_report, sort_keys=True)
    request_text = json.dumps(request_log, sort_keys=True)
    usage_text = json.dumps(usage_summary, sort_keys=True)

    add_check(checks, "endpoint_coverage_complete", set(public_report.get("endpoint_coverage", [])) == set(module.ENDPOINTS), public_report.get("endpoint_coverage"))
    add_check(checks, "usage_logged_in_report", usage_summary.get("usage", {}).get("allowed_request_count", 0) >= 7, usage_summary.get("usage"))
    add_check(checks, "request_log_created", len(request_log.get("request_log", [])) >= 15, len(request_log.get("request_log", [])))
    blocked_reasons = {item.get("reason") for item in request_log.get("request_log", []) if item.get("status") == "blocked"}
    add_check(
        checks,
        "blocked_flow_reasons_logged",
        {"missing_key", "invalid_key", "revoked_key", "rotated_key", "key_client_mismatch", "vault_denied", "namespace_denied", "usage_limit_exceeded"}.issubset(blocked_reasons),
        sorted(blocked_reasons),
    )

    add_check(checks, "public_report_contains_no_raw_keys", not contains_full_dev_key(public_text), "none")
    add_check(checks, "private_report_contains_no_raw_keys_persisted", not contains_full_dev_key(private_text), "none")
    add_check(checks, "request_log_contains_no_raw_keys_persisted", not contains_full_dev_key(request_text), "none")
    add_check(checks, "usage_report_contains_no_raw_keys_persisted", not contains_full_dev_key(usage_text), "none")

    public_private_hits = find_terms(public_text, PRIVATE_TERMS_PUBLIC)
    add_check(checks, "public_report_contains_no_private_internals", not public_private_hits, public_private_hits)
    add_check(checks, "no_real_client_data_used", "example.test" in private_text and "real client data" not in public_text.lower(), "synthetic example.test only")

    overclaim_hits = find_terms(public_text, OVERCLAIMS)
    punitive_hits = find_terms(public_text, PUNITIVE_TERMS)
    add_check(checks, "no_production_or_live_hosted_claims", not overclaim_hits, overclaim_hits)
    add_check(checks, "no_billing_claims", "billing enabled" not in public_text.lower(), "billing not enabled")
    add_check(checks, "no_approval_or_certification_claims", not any("approved" in hit or "certified" in hit for hit in overclaim_hits), overclaim_hits)
    add_check(checks, "no_punitive_wording", not punitive_hits, punitive_hits)

    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.71 CONTROLLED-ALPHA API AUDIT")
    print("-------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Command results:")
    print(f"- python examples/run_controlled_alpha_api_v071.py: {'PASS' if runner['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {REQUEST_LOG.relative_to(ROOT)}")
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
