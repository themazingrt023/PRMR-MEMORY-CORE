"""Audit V0.77 hosted API deployment prep."""

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
BACKEND_README = ROOT / "backend" / "README.md"
DEPLOYMENT_DOC = ROOT / "docs" / "backend_deployment_v077.md"
SMOKE_DOC = ROOT / "docs" / "hosted_api_smoke_test_v077.md"
REQUIREMENTS = ROOT / "requirements-api.txt"
PROCFILE = ROOT / "Procfile"
RUNTIME = ROOT / "runtime.txt"
ENV_EXAMPLE = ROOT / ".env.example"
RUNNER = ROOT / "examples" / "run_hosted_api_deployment_prep_v077.py"
V076_RUNNER = ROOT / "examples" / "run_api_server_v076.py"
HOSTED_SMOKE = ROOT / "examples" / "audit_v077_hosted_api_smoke.py"

REPORT_DIR = ROOT / "reports" / "v077"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_api_deployment_prep_v077.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_api_deployment_prep_v077.json"
HOSTED_SMOKE_REPORT = REPORT_DIR / "hosted_api_smoke_v077.json"
DEPLOYMENT_CONFIG_REPORT = REPORT_DIR / "deployment_config_v077.json"
SCORECARD = REPORT_DIR / "scorecard_v077.md"

REQUIRED_ROUTES = {
    "GET /health",
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "GET /v1/dashboard/state",
}
REQUIRED_ENV_LINES = [
    "PRMR_API_MODE=hosted_alpha",
    "PRMR_STORAGE_PATH=reports/v077/prmr_api_server_hosted_alpha.sqlite",
    "PRMR_SYNTHETIC_ONLY=true",
    "PRMR_PUBLIC_REPORTS_DIR=reports/v077/public",
    "PRMR_PRIVATE_REPORTS_DIR=reports/v077/private",
    "PRMR_ALLOWED_ORIGINS=https://prmr-memory-core.vercel.app,http://localhost:3000",
    "PRMR_DEFAULT_REQUEST_LIMIT=100",
    "PRMR_HOSTED_API_URL=",
]
START_COMMAND = "uvicorn prmr.product.api_server_v076:app --host 0.0.0.0 --port $PORT"
LOCAL_FALLBACK_COMMAND = "uvicorn prmr.product.api_server_v076:app --host 127.0.0.1 --port 8000"
PUBLIC_FRONTEND_ORIGIN = "https://prmr-memory-core.vercel.app"
LOCAL_FRONTEND_ORIGIN = "http://localhost:3000"

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
]
OVERCLAIMS = [
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
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], extra_env: dict[str, str] | None = None, timeout: int = 360) -> dict[str, Any]:
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


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def strip_boundary_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: strip_boundary_fields(value) for key, value in payload.items() if key != "boundary"}
    if isinstance(payload, list):
        return [strip_boundary_fields(item) for item in payload]
    return payload


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any], smoke_missing_url: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.77 Hosted API Deployment Prep Audit",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.77 is deployment prep plus a hosted smoke harness. Hosted client access requires a real deployed URL that passes smoke tests.",
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
            f"- {'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}",
            f"- {'PASS' if smoke_missing_url['passed'] else 'FAIL'}: {smoke_missing_url['command']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "v076_server_exists", SERVER_MODULE.exists(), str(SERVER_MODULE.relative_to(ROOT)))
    server_module = importlib.import_module("prmr.product.api_server_v076")
    add_check(checks, "fastapi_app_imports", hasattr(server_module, "app") and callable(getattr(server_module, "create_app", None)), "app/create_app")
    routes = set(getattr(server_module, "ROUTES", {}).keys())
    add_check(checks, "required_routes_exist", REQUIRED_ROUTES.issubset(routes), sorted(routes))

    backend_readme = read(BACKEND_README)
    deployment_doc = read(DEPLOYMENT_DOC)
    smoke_doc = read(SMOKE_DOC)
    env_text = read(ENV_EXAMPLE)
    procfile = read(PROCFILE)
    requirements = read(REQUIREMENTS)

    add_check(checks, "backend_deployment_docs_exist", BACKEND_README.exists() and DEPLOYMENT_DOC.exists() and SMOKE_DOC.exists(), None)
    add_check(checks, "backend_start_command_documented", START_COMMAND in backend_readme and START_COMMAND in deployment_doc and START_COMMAND in procfile, START_COMMAND)
    add_check(checks, "local_fallback_documented", LOCAL_FALLBACK_COMMAND in backend_readme and LOCAL_FALLBACK_COMMAND in deployment_doc, LOCAL_FALLBACK_COMMAND)
    add_check(checks, "requirements_api_dependency_file_exists", REQUIREMENTS.exists() and "fastapi" in requirements.lower() and "uvicorn" in requirements.lower(), requirements.strip())
    add_check(checks, "procfile_exists", PROCFILE.exists() and START_COMMAND in procfile, procfile.strip())
    add_check(checks, "runtime_exists", RUNTIME.exists() and "python" in read(RUNTIME).lower(), read(RUNTIME).strip())

    for line in REQUIRED_ENV_LINES:
        add_check(checks, f"env_{line.split('=')[0].lower()}_present", line in env_text, line)
    add_check(checks, "allowed_origins_include_vercel_and_localhost", PUBLIC_FRONTEND_ORIGIN in env_text and LOCAL_FRONTEND_ORIGIN in env_text, None)
    add_check(checks, "wildcard_cors_not_enabled", "PRMR_ALLOWED_ORIGINS=*" not in env_text and "allow_origins=[\"*\"]" not in read(SERVER_MODULE), None)
    add_check(checks, "storage_path_env_documented", "PRMR_STORAGE_PATH" in env_text and "PRMR_STORAGE_PATH" in deployment_doc, None)
    add_check(checks, "synthetic_only_mode_documented", "PRMR_SYNTHETIC_ONLY=true" in env_text and "synthetic-only mode" in deployment_doc.lower(), None)

    add_check(checks, "hosted_smoke_script_exists", HOSTED_SMOKE.exists(), str(HOSTED_SMOKE.relative_to(ROOT)))
    smoke_missing_url = run_command(["python", str(HOSTED_SMOKE)], extra_env={"PRMR_HOSTED_API_URL": "", "PRMR_HOSTED_API_KEY": "", "PRMR_HOSTED_CLIENT_ID": "", "PRMR_HOSTED_VAULT_ID": "", "PRMR_HOSTED_NAMESPACE": ""})
    missing_url_report = read_json(HOSTED_SMOKE_REPORT) if HOSTED_SMOKE_REPORT.exists() else {}
    add_check(checks, "hosted_smoke_missing_url_readiness_result", smoke_missing_url["passed"] and missing_url_report.get("result") == "PASS_READINESS_NEEDS_HOSTED_URL", missing_url_report.get("result"))
    add_check(checks, "hosted_smoke_does_not_fake_live_without_url", missing_url_report.get("hosted_url_present") is False and missing_url_report.get("hosted_client_access_verified") is False, missing_url_report)

    runner = run_command(["python", str(RUNNER)], extra_env={"PRMR_HOSTED_API_URL": "", "PRMR_HOSTED_API_KEY": "", "PRMR_HOSTED_CLIENT_ID": "", "PRMR_HOSTED_VAULT_ID": "", "PRMR_HOSTED_NAMESPACE": ""})
    add_check(checks, "prep_runner_passes", runner["passed"], runner["output"][-1500:])

    for path in [PUBLIC_REPORT, PRIVATE_REPORT, HOSTED_SMOKE_REPORT, DEPLOYMENT_CONFIG_REPORT, SCORECARD]:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}
    hosted_smoke = read_json(HOSTED_SMOKE_REPORT) if HOSTED_SMOKE_REPORT.exists() else {}
    deployment_config = read_json(DEPLOYMENT_CONFIG_REPORT) if DEPLOYMENT_CONFIG_REPORT.exists() else {}
    private_checks = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}

    for check_name in [
        "v076_server_exists",
        "fastapi_app_imports",
        "required_routes_exist",
        "backend_deployment_docs_exist",
        "backend_start_command_documented",
        "requirements_api_exists",
        "allowed_origins_include_frontend_and_localhost",
        "hosted_smoke_script_exists",
        "hosted_smoke_handles_missing_url_or_runs_live",
        "missing_url_is_readiness_not_fake_live_pass",
        "v076_runner_still_passes",
        "public_outputs_have_no_raw_keys",
        "no_real_client_data_used",
        "no_live_hosted_claim_without_url",
        "no_production_billing_certification_claims",
    ]:
        add_check(checks, f"runner_{check_name}", private_checks.get(check_name) is True, private_checks.get(check_name))

    v076_runner = run_command(["python", str(V076_RUNNER)])
    add_check(checks, "v076_runner_still_passes_direct", v076_runner["passed"], v076_runner["output"][-1000:])

    public_bundle = strip_boundary_fields({"public_report": public_report, "hosted_smoke": hosted_smoke, "deployment_config": deployment_config})
    add_check(checks, "public_reports_contain_no_raw_keys", not contains_full_dev_key(public_bundle), None)
    add_check(checks, "public_reports_contain_no_key_terms", not scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "no_live_hosted_api_claim_without_url", public_report.get("hosted_client_access_verified") is False and hosted_smoke.get("hosted_client_access_verified") is False, {"public": public_report.get("hosted_client_access_verified"), "smoke": hosted_smoke.get("hosted_client_access_verified")})
    add_check(checks, "no_production_billing_certification_claims", not scan_terms(public_bundle, OVERCLAIMS), scan_terms(public_bundle, OVERCLAIMS))
    add_check(checks, "deployment_config_has_explicit_cors", deployment_config.get("cors", {}).get("allowed_origins") == [PUBLIC_FRONTEND_ORIGIN, LOCAL_FRONTEND_ORIGIN] and deployment_config.get("cors", {}).get("wildcard_origin") is False, deployment_config.get("cors"))
    add_check(checks, "deployment_config_has_start_command", deployment_config.get("start_command") == START_COMMAND and deployment_config.get("local_fallback_command") == LOCAL_FALLBACK_COMMAND, deployment_config)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, runner, smoke_missing_url), encoding="utf-8")

    print("PRMR Memory Core V0.77 Hosted API Deployment Prep Audit")
    print(f"{'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}")
    print(f"Hosted smoke missing-url result: {missing_url_report.get('result')}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
