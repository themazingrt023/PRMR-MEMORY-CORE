"""Run V0.77 hosted API deployment prep checks."""

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

REPORT_DIR = ROOT / "reports" / "v077"
PUBLIC_REPORT = REPORT_DIR / "public_hosted_api_deployment_prep_v077.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_hosted_api_deployment_prep_v077.json"
DEPLOYMENT_CONFIG_REPORT = REPORT_DIR / "deployment_config_v077.json"
SCORECARD = REPORT_DIR / "scorecard_v077.md"

SERVER_MODULE = ROOT / "prmr" / "product" / "api_server_v076.py"
BACKEND_README = ROOT / "backend" / "README.md"
DEPLOYMENT_DOC = ROOT / "docs" / "backend_deployment_v077.md"
SMOKE_DOC = ROOT / "docs" / "hosted_api_smoke_test_v077.md"
REQUIREMENTS = ROOT / "requirements-api.txt"
PROCFILE = ROOT / "Procfile"
RUNTIME = ROOT / "runtime.txt"
ENV_EXAMPLE = ROOT / ".env.example"
V076_RUNNER = ROOT / "examples" / "run_api_server_v076.py"
HOSTED_SMOKE = ROOT / "examples" / "audit_v077_hosted_api_smoke.py"
HOSTED_SMOKE_REPORT = REPORT_DIR / "hosted_api_smoke_v077.json"

BOUNDARY_V077 = (
    "V0.77 is deployment prep plus a hosted API smoke harness. Hosted client "
    "access is only claimable after a real deployed backend URL passes smoke "
    "tests. This is not production readiness, billing, external validation, bank "
    "approval, compliance approval, legal approval, external security "
    "certification, or real-world validation."
)

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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run_command(command: list[str], extra_env: dict[str, str] | None = None, timeout: int = 300) -> dict[str, Any]:
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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


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


def build_public_report(checks: list[dict[str, Any]], hosted_smoke_result: dict[str, Any], v076_runner: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.77",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Hosted API Deployment Smoke Prep",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V077,
        "truth_label": "deployment prep plus smoke harness",
        "hosted_url_present": hosted_smoke_result.get("hosted_url_present", False),
        "hosted_client_access_verified": hosted_smoke_result.get("hosted_client_access_verified", False),
        "hosted_smoke_result": hosted_smoke_result.get("result"),
        "server_entrypoint": "prmr.product.api_server_v076:app",
        "server_framework": "FastAPI",
        "start_command": START_COMMAND,
        "local_fallback_command": LOCAL_FALLBACK_COMMAND,
        "cors": {
            "allowed_origins": [PUBLIC_FRONTEND_ORIGIN, LOCAL_FRONTEND_ORIGIN],
            "wildcard_origin": False,
        },
        "routes": sorted(REQUIRED_ROUTES),
        "v076_runner_passed": v076_runner["passed"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], command_results: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Hosted API Deployment Smoke Prep Restricted Evidence",
        "checks": checks,
        "command_results": command_results,
        "restricted_note": "Restricted evidence contains command outputs and local prep details. It does not include raw API key values.",
    }


def build_deployment_config_report() -> dict[str, Any]:
    return {
        "version": "0.77",
        "public_safe": True,
        "boundary": BOUNDARY_V077,
        "server_entrypoint": "prmr.product.api_server_v076:app",
        "start_command": START_COMMAND,
        "local_fallback_command": LOCAL_FALLBACK_COMMAND,
        "requirements_file": "requirements-api.txt",
        "procfile": "Procfile",
        "runtime": read(RUNTIME).strip(),
        "environment_plan": {
            "PRMR_API_MODE": "hosted_alpha",
            "PRMR_STORAGE_PATH": "host-managed writable path",
            "PRMR_SYNTHETIC_ONLY": "true",
            "PRMR_PUBLIC_REPORTS_DIR": "host-managed public report output path",
            "PRMR_PRIVATE_REPORTS_DIR": "host-managed restricted report output path",
            "PRMR_ALLOWED_ORIGINS": f"{PUBLIC_FRONTEND_ORIGIN},{LOCAL_FRONTEND_ORIGIN}",
            "PRMR_DEFAULT_REQUEST_LIMIT": "100",
        },
        "cors": {
            "allowed_origins": [PUBLIC_FRONTEND_ORIGIN, LOCAL_FRONTEND_ORIGIN],
            "wildcard_origin": False,
        },
        "hosted_url_required_for_live_claim": True,
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.77 Hosted API Deployment Prep",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V077}",
        "",
        "## Deployment",
        "",
        f"- Start command: `{START_COMMAND}`",
        f"- Local fallback: `{LOCAL_FALLBACK_COMMAND}`",
        f"- Hosted URL present: {public_report['hosted_url_present']}",
        f"- Hosted client access verified: {public_report['hosted_client_access_verified']}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_hosted_api_deployment_prep_v077.py", "- RUN: python examples/audit_v077_hosted_api_deployment_prep.py", ""])
    return "\n".join(lines)


def run_prep() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    command_results: dict[str, Any] = {}

    add_check(checks, "v076_server_exists", SERVER_MODULE.exists(), str(SERVER_MODULE.relative_to(ROOT)))
    server_module = importlib.import_module("prmr.product.api_server_v076")
    create_app = getattr(server_module, "create_app", None)
    add_check(checks, "fastapi_app_imports", callable(create_app), "create_app")
    routes = set(getattr(server_module, "ROUTES", {}).keys())
    add_check(checks, "required_routes_exist", REQUIRED_ROUTES.issubset(routes), sorted(routes))

    backend_readme = read(BACKEND_README)
    deployment_doc = read(DEPLOYMENT_DOC)
    smoke_doc = read(SMOKE_DOC)
    procfile = read(PROCFILE)
    requirements = read(REQUIREMENTS)
    env_text = read(ENV_EXAMPLE)

    add_check(checks, "backend_deployment_docs_exist", BACKEND_README.exists() and DEPLOYMENT_DOC.exists() and SMOKE_DOC.exists(), None)
    add_check(checks, "backend_start_command_documented", START_COMMAND in backend_readme and START_COMMAND in deployment_doc and START_COMMAND in procfile, START_COMMAND)
    add_check(checks, "local_fallback_command_documented", LOCAL_FALLBACK_COMMAND in backend_readme and LOCAL_FALLBACK_COMMAND in deployment_doc, LOCAL_FALLBACK_COMMAND)
    add_check(checks, "requirements_api_exists", REQUIREMENTS.exists() and "fastapi" in requirements.lower() and "uvicorn" in requirements.lower(), requirements.strip())
    add_check(checks, "runtime_or_start_plan_exists", RUNTIME.exists() and "python" in read(RUNTIME).lower(), read(RUNTIME).strip())
    add_check(checks, "procfile_exists", PROCFILE.exists() and START_COMMAND in procfile, procfile.strip())
    for line in REQUIRED_ENV_LINES:
        add_check(checks, f"env_{line.split('=')[0].lower()}_documented", line in env_text, line)
    add_check(checks, "allowed_origins_include_frontend_and_localhost", f"{PUBLIC_FRONTEND_ORIGIN},{LOCAL_FRONTEND_ORIGIN}" in env_text and PUBLIC_FRONTEND_ORIGIN in deployment_doc and LOCAL_FRONTEND_ORIGIN in deployment_doc, None)
    add_check(checks, "wildcard_cors_not_enabled", "PRMR_ALLOWED_ORIGINS=*" not in env_text and "wildcard_origin\": false" not in env_text.lower(), None)
    add_check(checks, "storage_path_env_documented", "PRMR_STORAGE_PATH" in env_text and "PRMR_STORAGE_PATH" in deployment_doc, None)
    add_check(checks, "synthetic_only_documented", "PRMR_SYNTHETIC_ONLY=true" in env_text and "synthetic-only mode" in deployment_doc.lower(), None)
    add_check(checks, "hosted_smoke_script_exists", HOSTED_SMOKE.exists(), str(HOSTED_SMOKE.relative_to(ROOT)))
    add_check(checks, "hosted_smoke_docs_exist", "PASS_READINESS_NEEDS_HOSTED_URL" in smoke_doc and "PRMR_HOSTED_API_URL" in smoke_doc, None)

    command_results["hosted_smoke"] = run_command(["python", str(HOSTED_SMOKE)])
    hosted_smoke_result = json.loads(HOSTED_SMOKE_REPORT.read_text(encoding="utf-8")) if HOSTED_SMOKE_REPORT.exists() else {}
    add_check(
        checks,
        "hosted_smoke_handles_missing_url_or_runs_live",
        command_results["hosted_smoke"]["passed"] and hosted_smoke_result.get("result") in {"PASS_READINESS_NEEDS_HOSTED_URL", "PASS_HOSTED_HEALTH_AND_AUTH_BOUNDARY"},
        hosted_smoke_result.get("result"),
    )
    add_check(
        checks,
        "missing_url_is_readiness_not_fake_live_pass",
        (hosted_smoke_result.get("hosted_url_present") is True)
        or (hosted_smoke_result.get("result") == "PASS_READINESS_NEEDS_HOSTED_URL" and hosted_smoke_result.get("hosted_client_access_verified") is False),
        hosted_smoke_result,
    )

    command_results["v076_runner"] = run_command(["python", str(V076_RUNNER)])
    add_check(checks, "v076_runner_still_passes", command_results["v076_runner"]["passed"], command_results["v076_runner"]["output"][-1000:])

    public_report = build_public_report(checks, hosted_smoke_result, command_results["v076_runner"])
    deployment_config = build_deployment_config_report()
    public_bundle = strip_boundary_fields({"public_report": public_report, "deployment_config": deployment_config, "hosted_smoke": hosted_smoke_result})
    add_check(checks, "public_outputs_have_no_raw_keys", not contains_full_dev_key(public_bundle) and not scan_terms(public_bundle, ["raw_api_key", "full_api_key", "api_secret", "private_key"]), None)
    add_check(checks, "no_real_client_data_used", True, "V0.77 uses docs/config/readiness checks and V0.76 synthetic smoke only.")
    add_check(checks, "no_live_hosted_claim_without_url", public_report["hosted_client_access_verified"] is False or hosted_smoke_result.get("hosted_url_present") is True, hosted_smoke_result)
    add_check(checks, "no_production_billing_certification_claims", not scan_terms(public_bundle, ["production-ready", "production ready", "billing enabled", "bank-approved", "compliance-certified", "legal-approved", "security-certified", "external validation complete"]), None)

    public_report = build_public_report(checks, hosted_smoke_result, command_results["v076_runner"])
    private_report = build_private_report(public_report, checks, command_results)
    deployment_config = build_deployment_config_report()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(DEPLOYMENT_CONFIG_REPORT, deployment_config)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")
    return public_report, command_results, checks


def main() -> int:
    public_report, _commands, checks = run_prep()
    print("PRMR Memory Core V0.77 Hosted API Deployment Prep")
    print(f"Start command: {START_COMMAND}")
    print(f"Hosted URL present: {public_report['hosted_url_present']}")
    print(f"Hosted client access verified: {public_report['hosted_client_access_verified']}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Hosted smoke report: {HOSTED_SMOKE_REPORT.as_posix()}")
    print(f"Deployment config: {DEPLOYMENT_CONFIG_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
