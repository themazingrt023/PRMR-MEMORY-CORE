"""V0.81 dashboard auth scoped access audit."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports" / "v081"
PUBLIC_REPORT = REPORT_DIR / "public_dashboard_auth_scoped_access_v081.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_dashboard_auth_scoped_access_v081.json"
SMOKE_REPORT = REPORT_DIR / "dashboard_auth_smoke_v081.json"
SCORECARD = REPORT_DIR / "scorecard_v081.md"

V080_PUBLIC = ROOT / "reports" / "v080" / "public_manual_client_onboarding_v080.json"
MODULE_PATH = ROOT / "prmr" / "product" / "dashboard_auth_v081.py"
RUNNER_PATH = ROOT / "examples" / "run_dashboard_auth_scoped_access_v081.py"
DOC_PATH = ROOT / "docs" / "dashboard_auth_scoped_access_v081.md"
FRONTEND_DASHBOARD = ROOT / "frontend" / "app" / "dashboard" / "page.tsx"

BOUNDARY_V081 = (
    "V0.81 is dashboard scoped access evidence only. It proves local/deployable "
    "synthetic dashboard session scoping and cross-client denial. It is not full "
    "production authentication, self-serve login, billing, external validation, "
    "bank approval, compliance approval, legal approval, external security "
    "certification, or real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v081_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def forbidden_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "self-serve login enabled",
        "production auth enabled",
        "production authentication enabled",
        "production authentication certified",
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
        "external certification",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_dashboard_auth_scoped_access_v081", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.81 dashboard runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.81",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Dashboard Auth Scoped Access Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V081,
        "runner_result": runner_public.get("result"),
        "client_a_access": runner_public.get("smoke_summary", {}).get("client_a_state", {}).get("status"),
        "client_b_with_a_token": runner_public.get("smoke_summary", {}).get("client_b_with_a_token", {}).get("error_code"),
        "missing_token": runner_public.get("smoke_summary", {}).get("missing_token", {}).get("error_code"),
        "invalid_token": runner_public.get("smoke_summary", {}).get("invalid_token", {}).get("error_code"),
        "revoked_token": runner_public.get("smoke_summary", {}).get("revoked_token", {}).get("error_code"),
        "frontend_dashboard_gating": {
            "public_frontend_locked_placeholder": True,
            "local_mode_synthetic_preview_allowed": True,
            "real_dashboard_data_without_auth": False,
        },
        "truth_label": "dashboard scoped access evidence only",
        "remaining_gaps": [
            "hosted dashboard connection",
            "durable hosted storage",
            "production authentication",
        ],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "restricted_note": "Private audit report excludes raw dashboard tokens and raw API keys.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.81 Dashboard Auth Scoped Access Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V081}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- RUN: python examples/run_dashboard_auth_scoped_access_v081.py",
            "- RUN: python examples/audit_v081_dashboard_auth_scoped_access.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v080 = read_json(V080_PUBLIC)
    module_source = read_text(MODULE_PATH)
    runner_source = read_text(RUNNER_PATH)
    doc_source = read_text(DOC_PATH)
    frontend_source = read_text(FRONTEND_DASHBOARD)

    add_check(checks, "v080_onboarding_evidence_exists", V080_PUBLIC.exists(), V080_PUBLIC.as_posix())
    add_check(checks, "v080_onboarding_passed", v080.get("result") == "PASS" and v080.get("credential_value_in_public_report") is False, v080.get("result"))
    add_check(checks, "dashboard_auth_module_exists", MODULE_PATH.exists(), MODULE_PATH.as_posix())
    add_check(checks, "dashboard_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "dashboard_docs_exist", DOC_PATH.exists(), DOC_PATH.as_posix())
    add_check(checks, "module_hashes_dashboard_tokens", "token_hash" in module_source and "safe_hash(raw_token)" in module_source, None)
    add_check(checks, "module_scopes_by_client_id", "session.client_id != requested_client_id" in module_source and "client_scope_denied" in module_source, None)
    add_check(checks, "module_blocks_missing_invalid_revoked", all(term in module_source for term in ["missing_dashboard_token", "invalid_dashboard_token", "revoked_dashboard_token"]), None)
    add_check(checks, "module_returns_safe_key_preview_hash_only", "safe_key_preview" in module_source and "key_hash_prefix" in module_source and "raw_api_keys_exposed" in module_source, None)
    add_check(checks, "frontend_dashboard_public_mode_locked", "isPublicFrontendMode()" in frontend_source and "Controlled-alpha dashboard access is locked" in frontend_source, None)
    add_check(checks, "frontend_copy_avoids_raw_keys", "raw API key access" in frontend_source and "does not expose real dashboard data without controlled auth" in frontend_source, None)
    add_check(checks, "docs_explain_not_production_auth", "not full production authentication" in doc_source and "not self-serve login" in doc_source, None)

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    summary = runner_public.get("smoke_summary", {})
    add_check(checks, "client_a_dashboard_access_works", summary.get("client_a_state", {}).get("status") == "ok", summary.get("client_a_state"))
    add_check(checks, "client_b_isolation_works", summary.get("client_b_with_a_token", {}).get("error_code") == "client_scope_denied", summary.get("client_b_with_a_token"))
    add_check(checks, "missing_token_blocked", summary.get("missing_token", {}).get("error_code") == "missing_dashboard_token", summary.get("missing_token"))
    add_check(checks, "invalid_token_blocked", summary.get("invalid_token", {}).get("error_code") == "invalid_dashboard_token", summary.get("invalid_token"))
    add_check(checks, "revoked_token_blocked", summary.get("revoked_token", {}).get("error_code") == "revoked_dashboard_token", summary.get("revoked_token"))
    panels = summary.get("client_a_state", {}).get("panels_present", {})
    add_check(checks, "dashboard_state_includes_required_panels", all(panels.get(name) for name in ["client_overview", "api_key_panel", "vault_namespace_panel", "usage_overview", "request_log_summary", "reports_panel", "memory_health_panel"]), panels)
    add_check(checks, "raw_api_key_absent_from_dashboard_state", any(check["name"] == "raw_api_key_absent_from_dashboard_state" and check["passed"] for check in runner_checks), None)
    add_check(checks, "raw_dashboard_token_absent_from_public_report", any(check["name"] == "raw_dashboard_token_absent_from_public_report" and check["passed"] for check in runner_checks), None)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(runner_public), None)
    add_check(checks, "public_report_has_no_false_claims", not forbidden_claim_hits(runner_public), forbidden_claim_hits(runner_public))
    add_check(checks, "no_real_client_data_used", any(check["name"] == "no_real_client_data_used" and check["passed"] for check in runner_checks), None)
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    public_report = build_public_report(checks, runner_public)
    add_check(checks, "audit_public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "audit_public_report_has_no_false_claims", not forbidden_claim_hits(public_report), forbidden_claim_hits(public_report))

    public_report = build_public_report(checks, runner_public)
    private_report = build_private_report(public_report, checks, runner_public)
    return public_report, private_report, smoke_report, checks


def maybe_run_frontend_checks() -> dict[str, Any]:
    frontend_changed = FRONTEND_DASHBOARD.exists()
    if not frontend_changed:
        return {"frontend_checked": False}
    results: dict[str, Any] = {"frontend_checked": True}
    for name, command in {
        "typecheck": ["npm", "run", "typecheck"],
        "build": ["npm", "run", "build"],
    }.items():
        process = subprocess.run(command, cwd=ROOT / "frontend", text=True, capture_output=True)
        results[name] = {
            "returncode": process.returncode,
            "stdout_tail": process.stdout[-2000:],
            "stderr_tail": process.stderr[-2000:],
        }
    return results


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.81 Dashboard Auth Scoped Access Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Client A access: {public_report.get('client_a_access')}")
    print(f"Client B with A token: {public_report.get('client_b_with_a_token')}")
    print(f"Missing token: {public_report.get('missing_token')}")
    print(f"Invalid token: {public_report.get('invalid_token')}")
    print(f"Revoked token: {public_report.get('revoked_token')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
