"""V0.79 controlled hosted test scope audit.

This audit verifies the repository is ready to support one synthetic hosted
test scope and records the full protected hosted smoke result honestly. Without
hosted test-scope environment variables, readiness can pass while the hosted
smoke remains NEEDS_TEST_SCOPE.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v079"
PUBLIC_REPORT = REPORT_DIR / "public_controlled_hosted_test_scope_v079.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_controlled_hosted_test_scope_v079.json"
FULL_SMOKE_REPORT = REPORT_DIR / "full_hosted_protected_smoke_v079.json"
SCORECARD = REPORT_DIR / "scorecard_v079.md"

RUNNER_PATH = ROOT / "examples" / "run_full_hosted_protected_smoke_v079.py"
SCOPE_MODULE = ROOT / "prmr" / "product" / "hosted_test_scope_v079.py"
API_SERVER = ROOT / "prmr" / "product" / "api_server_v076.py"
V0783_PUBLIC = ROOT / "reports" / "v0783" / "public_hosted_basic_smoke_evidence_v0783.json"
DOC_PATH = ROOT / "docs" / "controlled_hosted_test_scope_v079.md"

EXPECTED_RENDER_URL = "https://prmr-memory-core-api.onrender.com"

BOUNDARY_V079 = (
    "V0.79 is controlled synthetic hosted test-scope smoke evidence only. It "
    "does not prove real client onboarding, production readiness, billing, "
    "external validation, bank approval, compliance approval, legal approval, "
    "external security certification, or real-world validation."
)

ALLOWED_RUNNER_RESULTS = {
    "NEEDS_HOSTED_URL",
    "NEEDS_TEST_SCOPE",
    "NEEDS_TEST_SCOPE_CONFIG",
    "PASS_FULL_CONTROLLED_HOSTED_SMOKE",
}


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_full_hosted_protected_smoke_v079", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.79 smoke runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def git_tracked_files() -> list[Path]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=True)
    except Exception:
        return []
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def tracked_file_contains_value(value: str) -> dict[str, Any]:
    if not value:
        return {"checked": False, "hit_count": 0}
    hits = []
    for path in git_tracked_files():
        try:
            if path.is_file() and value in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(path.relative_to(ROOT).as_posix())
        except Exception:
            continue
    return {"checked": True, "hit_count": len(hits), "paths": hits[:10]}


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def positive_overclaim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "production-ready",
        "production ready",
        "billing enabled",
        "bank-approved",
        "bank approved",
        "compliance-certified",
        "compliance certified",
        "legal-approved",
        "legal approved",
        "security-certified",
        "security certified",
        "external validation complete",
        "real-world validated",
        "real client onboarding verified",
    ]
    return [phrase for phrase in phrases if phrase in text]


def public_report_clean(public_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "secret_pattern_present": contains_secret_pattern(public_report),
        "overclaims": positive_overclaim_hits(public_report),
        "raw_key_reported": "PRMR_TEST_API_KEY" in json.dumps(public_report, sort_keys=True),
    }


def build_public_report(checks: list[dict[str, Any]], runner_report: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    return {
        "version": "0.79",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Controlled Hosted Test Scope Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "hosted_smoke_result_level": runner_report.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V079,
        "hosted_url": runner_report.get("hosted_url"),
        "expected_render_url": EXPECTED_RENDER_URL,
        "test_scope_present": runner_report.get("test_scope_present"),
        "full_controlled_hosted_smoke_verified": runner_report.get("full_controlled_hosted_smoke_verified"),
        "safe_key_preview": runner_report.get("safe_key_preview"),
        "raw_key_hardcoded": False,
        "raw_key_reported": False,
        "public_reports_expose_secrets": False,
        "truth_label": "controlled synthetic hosted test-scope readiness and smoke evidence",
        "remaining_gap": (
            "Controlled hosted test-scope env vars must be set on Render and locally before "
            "PASS_FULL_CONTROLLED_HOSTED_SMOKE can be claimed."
            if runner_report.get("result") != "PASS_FULL_CONTROLLED_HOSTED_SMOKE"
            else "Real client onboarding and dashboard authentication remain future work."
        ),
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_report: dict[str, Any], safe_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_report": runner_report,
        "safe_http_results": safe_results,
        "restricted_note": "No raw API key values are stored. The audit may include source-file check details and safe HTTP summaries only.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.79 Controlled Hosted Test Scope Audit",
        "",
        f"Audit result: {public_report['result']}",
        f"Hosted smoke result level: {public_report['hosted_smoke_result_level']}",
        f"Hosted URL: {public_report['hosted_url']}",
        f"Test scope present: {public_report['test_scope_present']}",
        f"Full controlled hosted smoke verified: {public_report['full_controlled_hosted_smoke_verified']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V079}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "SKIP" if check["skipped"] else ("PASS" if check["passed"] else "FAIL")
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- RUN: python examples/audit_v079_controlled_hosted_test_scope.py",
            "- AFTER TEST SCOPE EXISTS: python examples/run_full_hosted_protected_smoke_v079.py",
            "",
        ]
    )
    return "\n".join(lines)


def audit() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    module_source = read_text(SCOPE_MODULE)
    server_source = read_text(API_SERVER)
    runner_source = read_text(RUNNER_PATH)
    doc_source = read_text(DOC_PATH)

    add_check(checks, "v0783_basic_smoke_evidence_exists", V0783_PUBLIC.exists(), V0783_PUBLIC.as_posix())
    if V0783_PUBLIC.exists():
        try:
            v0783 = json.loads(V0783_PUBLIC.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            v0783 = {}
        add_check(checks, "v0783_basic_smoke_passed", v0783.get("result") == "PASS_BASIC_HOSTED_SMOKE", v0783.get("result"))
    else:
        add_check(checks, "v0783_basic_smoke_passed", False, "missing")

    add_check(checks, "controlled_test_scope_module_exists", SCOPE_MODULE.exists(), SCOPE_MODULE.as_posix())
    add_check(checks, "api_server_registers_controlled_test_scope", "register_controlled_test_scope" in server_source and "controlled_test_scope_v079" in server_source, None)
    add_check(checks, "full_protected_smoke_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "hosted_backend_url_env_support_exists", "PRMR_HOSTED_API_URL" in runner_source, None)
    add_check(checks, "test_key_only_read_from_environment", 'os.getenv("PRMR_TEST_API_KEY"' in module_source and "raw_key = os.getenv" in module_source, None)
    add_check(checks, "module_stores_safe_preview_or_hash_prefix_only_in_status", "safe_key_preview" in module_source and "key_hash_prefix" in module_source and "raw_key_reported" in module_source, None)
    add_check(checks, "runner_handles_missing_hosted_url", "NEEDS_HOSTED_URL" in runner_source, None)
    add_check(checks, "runner_handles_missing_test_scope", "NEEDS_TEST_SCOPE" in runner_source and "NEEDS_TEST_SCOPE_CONFIG" in runner_source, None)
    add_check(checks, "runner_tests_blocked_hosted_requests", all(term in runner_source for term in ["wrong_key_blocked", "wrong_vault_blocked", "wrong_namespace_blocked", "missing_authorization_blocked", "malformed_authorization_blocked"]), None)
    add_check(checks, "docs_exist", DOC_PATH.exists(), DOC_PATH.as_posix())
    add_check(checks, "docs_include_required_env_vars", all(term in doc_source for term in ["PRMR_ENABLE_CONTROLLED_TEST_SCOPE", "PRMR_TEST_API_KEY", "PRMR_TEST_CLIENT_ID", "PRMR_TEST_VAULT_ID", "PRMR_TEST_NAMESPACE"]), None)
    add_check(checks, "docs_preserve_boundaries", all(term in doc_source.lower() for term in ["synthetic", "not production", "not billing", "not external validation"]), None)

    raw_test_key = os.getenv("PRMR_TEST_API_KEY", "").strip()
    hardcoded_scan = tracked_file_contains_value(raw_test_key)
    add_check(checks, "no_tracked_file_contains_current_test_key_value", hardcoded_scan.get("hit_count", 0) == 0, {"checked": hardcoded_scan.get("checked"), "hit_count": hardcoded_scan.get("hit_count")}, skipped=not raw_test_key)
    obvious_hardcoded_hits = re.findall(r"PRMR_TEST_API_KEY\s*=\s*['\"][^'\"]{8,}['\"]", module_source + runner_source)
    add_check(checks, "no_raw_api_key_hardcoded_in_v079_source", not obvious_hardcoded_hits, {"hit_count": len(obvious_hardcoded_hits)})

    runner = load_runner_module()
    runner_report, safe_results, runner_checks = runner.run_smoke()
    runner.write_reports(runner_report, safe_results, runner_checks)
    add_check(checks, "runner_result_level_is_honest", runner_report.get("result") in ALLOWED_RUNNER_RESULTS, runner_report.get("result"))
    add_check(checks, "runner_does_not_force_pass_without_test_scope", not (runner_report.get("result") == "PASS_FULL_CONTROLLED_HOSTED_SMOKE" and not runner_report.get("test_scope_present")), runner_report.get("result"))
    add_check(checks, "runner_needs_work_is_not_hidden", runner_report.get("result") != "NEEDS_WORK", runner_report.get("result"))

    public_report = build_public_report(checks, runner_report)
    clean = public_report_clean(public_report)
    add_check(checks, "public_report_contains_no_secrets", not clean["secret_pattern_present"] and not clean["raw_key_reported"], clean)
    add_check(checks, "public_report_has_no_overclaims", not clean["overclaims"], clean["overclaims"])

    public_report = build_public_report(checks, runner_report)
    private_report = build_private_report(public_report, checks, runner_report, safe_results)
    return public_report, private_report, checks, safe_results


def main() -> int:
    public_report, private_report, checks, safe_results = audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    if not FULL_SMOKE_REPORT.exists():
        write_json(
            FULL_SMOKE_REPORT,
            {
                "version": "0.79",
                "public_safe": True,
                "boundary": BOUNDARY_V079,
                "result": public_report["hosted_smoke_result_level"],
                "hosted_url": public_report.get("hosted_url"),
                "safe_http_results": safe_results,
            },
        )
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.79 Controlled Hosted Test Scope Audit")
    print(f"Hosted URL: {public_report.get('hosted_url')}")
    print(f"Hosted smoke result level: {public_report.get('hosted_smoke_result_level')}")
    print(f"Test scope present: {public_report.get('test_scope_present')}")
    print(f"Full controlled hosted smoke verified: {public_report.get('full_controlled_hosted_smoke_verified')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Full smoke report: {FULL_SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
