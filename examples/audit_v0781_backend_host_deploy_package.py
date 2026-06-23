"""Audit V0.78.1 backend host deployment package."""

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

SERVER_MODULE = ROOT / "prmr" / "product" / "api_server_v076.py"
REQUIREMENTS = ROOT / "requirements-api.txt"
PROCFILE = ROOT / "Procfile"
RUNTIME = ROOT / "runtime.txt"
BACKEND_README = ROOT / "backend" / "README.md"
ENV_EXAMPLE = ROOT / ".env.example"
RUNBOOK = ROOT / "docs" / "backend_host_deploy_v0781.md"
HELPER = ROOT / "examples" / "run_backend_hosted_smoke_v0781.py"
V078_RUNNER = ROOT / "examples" / "run_live_hosted_api_smoke_v078.py"

REPORT_DIR = ROOT / "reports" / "v0781"
PUBLIC_REPORT = REPORT_DIR / "public_backend_host_deploy_package_v0781.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_backend_host_deploy_package_v0781.json"
READINESS_REPORT = REPORT_DIR / "host_deploy_readiness_v0781.json"
SCORECARD = REPORT_DIR / "scorecard_v0781.md"

PRIMARY_HOST = "Render Web Service"
START_COMMAND = "uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT"
BUILD_COMMAND = "pip install -r requirements-api.txt"
ENTRYPOINT = "prmr.product.api_server_v076:app"
FRONTEND_ORIGIN = "https://prmr-memory-core.vercel.app"
LOCAL_ORIGIN = "http://localhost:3000"

BOUNDARY_V0781 = (
    "V0.78.1 is backend host deployment execution prep. Hosted API access is "
    "only claimable after a real deployed backend URL passes V0.78 smoke. It is "
    "not live hosted API evidence by itself, not production readiness, not billing, "
    "not bank approval, not compliance approval, not legal approval, not external "
    "security certification, and not real-world validation."
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(command: list[str], extra_env: dict[str, str] | None = None, timeout: int = 240) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        env=env,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def has_nonempty_secret_assignment(text: str) -> bool:
    secret_names = [
        "PRMR_TEST_API_KEY",
        "PRMR_HOSTED_API_KEY",
        "SERVER_ONLY_API_SECRET",
        "BILLING_PROVIDER_SECRET",
    ]
    for name in secret_names:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{name}=") and stripped.split("=", 1)[1].strip():
                return True
    return False


def positive_overclaim_hits(text: str) -> list[str]:
    lower = text.lower()
    phrases = [
        "is production ready",
        "production-ready service",
        "billing enabled",
        "bank approved",
        "bank-approved",
        "compliance certified",
        "compliance-certified",
        "legal approved",
        "legal-approved",
        "security certified",
        "security-certified",
        "external validation complete",
        "live hosted api access is verified",
    ]
    return [phrase for phrase in phrases if phrase in lower]


def build_public_report(checks: list[dict[str, Any]], helper_result: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.78.1",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Backend Host Deploy Package",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V0781,
        "chosen_host_path": PRIMARY_HOST,
        "entrypoint": ENTRYPOINT,
        "build_command": BUILD_COMMAND,
        "start_command": START_COMMAND,
        "runbook": "docs/backend_host_deploy_v0781.md",
        "hosted_url_present": helper_result.get("hosted_url_present", False),
        "hosted_smoke_helper_result": helper_result.get("result", "NEEDS_HOSTED_URL"),
        "hosted_api_access_claimed": False,
    }


def build_readiness_report(helper_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "0.78.1",
        "public_safe": True,
        "boundary": BOUNDARY_V0781,
        "chosen_host_path": PRIMARY_HOST,
        "deploy_from": "repository root",
        "entrypoint": ENTRYPOINT,
        "build_command": BUILD_COMMAND,
        "start_command": START_COMMAND,
        "required_env": {
            "PRMR_API_MODE": "hosted_alpha",
            "PRMR_STORAGE_PATH": "/tmp/prmr_api_server_v0781.sqlite or host-safe writable path",
            "PRMR_SYNTHETIC_ONLY": "true",
            "PRMR_PUBLIC_REPORTS_DIR": "/tmp/prmr-reports-public or host-safe path",
            "PRMR_PRIVATE_REPORTS_DIR": "/tmp/prmr-reports-private or host-safe path",
            "PRMR_ALLOWED_ORIGINS": f"{FRONTEND_ORIGIN},{LOCAL_ORIGIN}",
            "PRMR_DEFAULT_REQUEST_LIMIT": "100",
        },
        "cors": {
            "frontend_origin": FRONTEND_ORIGIN,
            "localhost_origin": LOCAL_ORIGIN,
            "wildcard_cors_allowed": False,
        },
        "storage_note": "First hosted smoke may use ephemeral storage. Durable hosted persistence is later work.",
        "helper_result": helper_result.get("result", "NEEDS_HOSTED_URL"),
        "hosted_url_present": helper_result.get("hosted_url_present", False),
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], command_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Backend Host Deploy Package Restricted Evidence",
        "checks": checks,
        "command_results": command_results,
        "restricted_note": "No raw API key values are written. Command outputs are local audit evidence.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.78.1 Backend Host Deploy Package",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Chosen host path: {PRIMARY_HOST}",
        f"Start command: `{START_COMMAND}`",
        f"Boundary: {BOUNDARY_V0781}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/audit_v0781_backend_host_deploy_package.py", ""])
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []
    command_results: dict[str, Any] = {}

    runbook = read(RUNBOOK)
    backend_readme = read(BACKEND_README)
    env_text = read(ENV_EXAMPLE)
    requirements = read(REQUIREMENTS)
    procfile = read(PROCFILE)
    runtime = read(RUNTIME)
    docs_bundle = "\n".join([runbook, backend_readme, env_text, requirements, procfile, runtime])

    add_check(checks, "fastapi_entrypoint_exists", SERVER_MODULE.exists() and hasattr(importlib.import_module("prmr.product.api_server_v076"), "app"), ENTRYPOINT)
    add_check(checks, "requirements_api_exists", REQUIREMENTS.exists() and "fastapi" in requirements and "uvicorn" in requirements, requirements.strip())
    add_check(checks, "procfile_exists", PROCFILE.exists() and START_COMMAND in procfile, procfile.strip())
    add_check(checks, "runtime_exists", RUNTIME.exists() and "python" in runtime.lower(), runtime.strip())
    add_check(checks, "backend_host_guide_exists", RUNBOOK.exists(), str(RUNBOOK.relative_to(ROOT)))
    add_check(checks, "primary_host_path_documented", PRIMARY_HOST in runbook and "Render" in runbook, PRIMARY_HOST)
    add_check(checks, "deploy_from_documented", "repository root" in runbook.lower() and str(ROOT) in runbook, None)
    add_check(checks, "build_command_documented", BUILD_COMMAND in runbook and BUILD_COMMAND in backend_readme, BUILD_COMMAND)
    add_check(checks, "start_command_documented", START_COMMAND in runbook and START_COMMAND in backend_readme and START_COMMAND in procfile, START_COMMAND)
    add_check(checks, "env_vars_documented", all(term in runbook for term in ["PRMR_API_MODE=hosted_alpha", "PRMR_STORAGE_PATH", "PRMR_SYNTHETIC_ONLY=true", "PRMR_PUBLIC_REPORTS_DIR", "PRMR_PRIVATE_REPORTS_DIR", "PRMR_ALLOWED_ORIGINS", "PRMR_DEFAULT_REQUEST_LIMIT=100"]), None)
    add_check(checks, "storage_path_documented", "/tmp/prmr_api_server_v0781.sqlite" in runbook and "ephemeral" in runbook.lower(), None)
    add_check(checks, "allowed_origins_include_frontend", FRONTEND_ORIGIN in runbook and FRONTEND_ORIGIN in env_text, FRONTEND_ORIGIN)
    add_check(checks, "allowed_origins_include_localhost", LOCAL_ORIGIN in runbook and LOCAL_ORIGIN in env_text, LOCAL_ORIGIN)
    add_check(checks, "no_wildcard_cors_claim", "PRMR_ALLOWED_ORIGINS=*" not in docs_bundle and "wildcard CORS" in runbook, None)
    add_check(checks, "logs_instructions_documented", "host dashboard logs" in runbook.lower() and "build failures" in runbook.lower(), None)
    add_check(checks, "copy_hosted_url_documented", "copy the generated public backend URL" in runbook, None)
    add_check(checks, "v078_smoke_command_documented", "python examples/run_live_hosted_api_smoke_v078.py" in runbook, None)
    add_check(checks, "v0781_helper_exists", HELPER.exists(), str(HELPER.relative_to(ROOT)))

    command_results["helper_missing_url"] = run_command(
        ["python", str(HELPER)],
        extra_env={
            "PRMR_HOSTED_API_URL": "",
            "PRMR_TEST_API_KEY": "",
            "PRMR_TEST_CLIENT_ID": "",
            "PRMR_TEST_VAULT_ID": "",
            "PRMR_TEST_NAMESPACE": "",
        },
    )
    helper_report_path = REPORT_DIR / "backend_hosted_smoke_helper_v0781.json"
    helper_report = json.loads(helper_report_path.read_text(encoding="utf-8")) if helper_report_path.exists() else {}
    add_check(checks, "helper_handles_missing_url", command_results["helper_missing_url"]["passed"] and helper_report.get("result") == "NEEDS_HOSTED_URL", helper_report)

    add_check(checks, "no_hosted_api_claim_without_url", "Hosted API access is only claimable after" in runbook and helper_report.get("hosted_url_present") is False, None)
    add_check(checks, "no_raw_secrets_in_docs", not contains_full_dev_key(docs_bundle) and not has_nonempty_secret_assignment(docs_bundle), None)
    add_check(checks, "no_raw_secrets_in_helper_report", not contains_full_dev_key(helper_report) and not has_nonempty_secret_assignment(json.dumps(helper_report)), None)
    add_check(checks, "no_positive_production_billing_certification_claims", not positive_overclaim_hits(docs_bundle), positive_overclaim_hits(docs_bundle))

    public_report = build_public_report(checks, helper_report)
    readiness_report = build_readiness_report(helper_report)
    private_report = build_private_report(public_report, checks, command_results)

    public_bundle = json.dumps({"public": public_report, "readiness": readiness_report}, sort_keys=True)
    add_check(checks, "public_reports_have_no_raw_secrets", not contains_full_dev_key(public_bundle) and not has_nonempty_secret_assignment(public_bundle), None)

    public_report = build_public_report(checks, helper_report)
    readiness_report = build_readiness_report(helper_report)
    private_report = build_private_report(public_report, checks, command_results)
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(READINESS_REPORT, readiness_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.78.1 Backend Host Deploy Package Audit")
    print(f"Chosen host path: {PRIMARY_HOST}")
    print(f"Runbook: {RUNBOOK.as_posix()}")
    print(f"Start command: {START_COMMAND}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
