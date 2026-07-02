"""V0.82 hosted dashboard connection audit."""

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports" / "v082"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_dashboard_connection_v082.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_dashboard_connection_v082.json"
SMOKE_REPORT = REPORT_DIR / "hosted_dashboard_connection_smoke_v082.json"
SCORECARD = REPORT_DIR / "scorecard_v082.md"

V081_PUBLIC = ROOT / "reports" / "v081" / "public_dashboard_auth_scoped_access_v081.json"
MODULE_PATH = ROOT / "prmr" / "product" / "hosted_dashboard_connection_v082.py"
RUNNER_PATH = ROOT / "examples" / "run_hosted_dashboard_connection_v082.py"
DOC_PATH = ROOT / "docs" / "hosted_dashboard_connection_v082.md"
FRONTEND_PROXY = ROOT / "frontend" / "app" / "api" / "dashboard" / "state" / "route.ts"
FRONTEND_DASHBOARD = ROOT / "frontend" / "app" / "dashboard" / "page.tsx"
DASHBOARD_AUTH_MODULE = ROOT / "prmr" / "product" / "dashboard_auth_v081.py"

BOUNDARY_V082 = (
    "V0.82 is hosted dashboard connection evidence only. It proves a safe "
    "frontend/backend dashboard-state bridge can be scoped with synthetic "
    "dashboard session access. It is not production login, self-serve dashboard "
    "access, billing, external validation, bank approval, compliance approval, "
    "legal approval, external security certification, or real-world validation."
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
        r"dash_v08[12]_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def forbidden_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "production login enabled",
        "self-serve dashboard access enabled",
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
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_hosted_dashboard_connection_v082", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.82 dashboard connection runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frontend_command(command: list[str]) -> dict[str, Any]:
    resolved = list(command)
    if os.name == "nt" and resolved and resolved[0] == "npm":
        resolved[0] = "npm.cmd"
    process = subprocess.run(
        resolved,
        cwd=ROOT / "frontend",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return {
        "command": " ".join(command),
        "returncode": process.returncode,
        "stdout_tail": process.stdout[-2000:],
        "stderr_tail": process.stderr[-2000:],
    }


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any], frontend_results: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.82",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted Dashboard Connection Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V082,
        "truth_label": "hosted dashboard connection evidence only",
        "valid_dashboard_state": runner_public.get("smoke_summary", {}).get("valid", {}).get("status"),
        "missing_token": runner_public.get("smoke_summary", {}).get("missing_token", {}).get("error_code"),
        "invalid_token": runner_public.get("smoke_summary", {}).get("invalid_token", {}).get("error_code"),
        "wrong_client": runner_public.get("smoke_summary", {}).get("wrong_client", {}).get("error_code"),
        "revoked_token": runner_public.get("smoke_summary", {}).get("revoked_token", {}).get("error_code"),
        "frontend_proxy_locked_by_default": True,
        "frontend_build_returncode": frontend_results.get("build", {}).get("returncode"),
        "frontend_typecheck_returncode": frontend_results.get("typecheck", {}).get("returncode"),
        "remaining_gaps": ["durable hosted storage", "production authentication"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any], frontend_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "frontend_results": frontend_results,
        "restricted_note": "No raw dashboard tokens or raw API keys are stored in this audit report.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.82 Hosted Dashboard Connection Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Frontend build return code: {public_report['frontend_build_returncode']}",
        f"Frontend typecheck return code: {public_report['frontend_typecheck_returncode']}",
        "",
        f"Boundary: {BOUNDARY_V082}",
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
            "- RUN: python examples/run_hosted_dashboard_connection_v082.py",
            "- RUN: python examples/audit_v082_hosted_dashboard_connection.py",
            "- RUN: npm run build",
            "- RUN: npm run typecheck",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v081 = read_json(V081_PUBLIC)
    module_source = read_text(MODULE_PATH)
    auth_source = read_text(DASHBOARD_AUTH_MODULE)
    runner_source = read_text(RUNNER_PATH)
    doc_source = read_text(DOC_PATH)
    proxy_source = read_text(FRONTEND_PROXY)
    page_source = read_text(FRONTEND_DASHBOARD)

    add_check(checks, "v081_evidence_exists", V081_PUBLIC.exists(), V081_PUBLIC.as_posix())
    add_check(checks, "v081_dashboard_auth_passed", v081.get("result") == "PASS" and v081.get("client_b_with_a_token") == "client_scope_denied", v081.get("result"))
    add_check(checks, "hosted_dashboard_connection_module_exists", MODULE_PATH.exists(), MODULE_PATH.as_posix())
    add_check(checks, "hosted_dashboard_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "hosted_dashboard_docs_exist", DOC_PATH.exists(), DOC_PATH.as_posix())
    add_check(checks, "frontend_proxy_route_exists", FRONTEND_PROXY.exists(), FRONTEND_PROXY.as_posix())
    add_check(checks, "dashboard_page_updated", "/api/dashboard/state" in page_source and "Controlled-alpha dashboard access is locked" in page_source, None)
    combined_backend_source = module_source + "\n" + auth_source
    add_check(checks, "module_validates_dashboard_token_and_client", "X-Dashboard-Token" in module_source and "X-Client-ID" in module_source and "client_scope_denied" in combined_backend_source, None)
    add_check(checks, "module_blocks_missing_invalid_wrong_revoked", all(term in combined_backend_source for term in ["missing_dashboard_token", "invalid_dashboard_token", "client_scope_denied", "revoked_dashboard_token"]), None)
    add_check(checks, "frontend_proxy_locked_by_default_in_source", "CONTROLLED_DASHBOARD_ACCESS_ENABLED" in proxy_source and "lockedResponse()" in proxy_source, None)
    add_check(checks, "frontend_proxy_does_not_hardcode_raw_token", "PRMR_DASHBOARD_TOKEN" in proxy_source and "dash_v08" not in proxy_source, None)
    add_check(checks, "frontend_proxy_deletes_raw_credential_fields", all(term in proxy_source for term in ["delete payload.raw_api_key", "delete payload.raw_dashboard_token", "delete payload.dashboard_token", "delete payload.api_key"]), None)
    add_check(checks, "docs_explain_proxy_and_boundaries", "server-side proxy" in doc_source and "not production login" in doc_source and "not self-serve dashboard access" in doc_source, None)

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    summary = runner_public.get("smoke_summary", {})
    add_check(checks, "valid_scoped_dashboard_state_works", summary.get("valid", {}).get("status") == "ok", summary.get("valid"))
    add_check(checks, "missing_token_blocked", summary.get("missing_token", {}).get("error_code") == "missing_dashboard_token", summary.get("missing_token"))
    add_check(checks, "invalid_token_blocked", summary.get("invalid_token", {}).get("error_code") == "invalid_dashboard_token", summary.get("invalid_token"))
    add_check(checks, "wrong_client_blocked", summary.get("wrong_client", {}).get("error_code") == "client_scope_denied", summary.get("wrong_client"))
    add_check(checks, "revoked_token_blocked", summary.get("revoked_token", {}).get("error_code") == "revoked_dashboard_token", summary.get("revoked_token"))
    add_check(checks, "dashboard_state_contains_safe_fields", all(summary.get("valid", {}).get("panels_present", {}).values()), summary.get("valid", {}).get("panels_present"))
    add_check(checks, "runner_public_report_contains_no_secrets", not contains_secret_pattern(runner_public), None)
    add_check(checks, "runner_public_report_has_no_false_claims", not forbidden_claim_hits(runner_public), forbidden_claim_hits(runner_public))
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    frontend_results = {
        "build": frontend_command(["npm", "run", "build"]),
        "typecheck": frontend_command(["npm", "run", "typecheck"]),
    }
    add_check(checks, "frontend_build_passes", frontend_results["build"]["returncode"] == 0, frontend_results["build"]["stderr_tail"] or frontend_results["build"]["stdout_tail"][-500:])
    add_check(checks, "frontend_typecheck_passes", frontend_results["typecheck"]["returncode"] == 0, frontend_results["typecheck"]["stderr_tail"] or frontend_results["typecheck"]["stdout_tail"][-500:])

    public_report = build_public_report(checks, runner_public, frontend_results)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_claims", not forbidden_claim_hits(public_report), forbidden_claim_hits(public_report))

    public_report = build_public_report(checks, runner_public, frontend_results)
    private_report = build_private_report(public_report, checks, runner_public, frontend_results)
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.82 Hosted Dashboard Connection Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Valid dashboard state: {public_report.get('valid_dashboard_state')}")
    print(f"Wrong client: {public_report.get('wrong_client')}")
    print(f"Missing token: {public_report.get('missing_token')}")
    print(f"Invalid token: {public_report.get('invalid_token')}")
    print(f"Revoked token: {public_report.get('revoked_token')}")
    print(f"Frontend build return code: {public_report.get('frontend_build_returncode')}")
    print(f"Frontend typecheck return code: {public_report.get('frontend_typecheck_returncode')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
