"""V0.67 staging deployment readiness and optional deployed URL smoke audit."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports" / "v067"

PUBLIC_REPORT = REPORTS / "public_staging_deployment_v067.json"
PRIVATE_REPORT = REPORTS / "private_internal_staging_deployment_v067.json"
SMOKE_REPORT = REPORTS / "deployed_route_smoke_check_v067.json"
SCORECARD = REPORTS / "scorecard_v067.md"

BOUNDARY = (
    "V0.67 is staging deployment readiness and/or deployed URL smoke testing only. "
    "It is not hosted backend, not production onboarding, not billing, not live API "
    "access, not API key issuance, not external validation, not bank approval, not "
    "compliance approval, not legal approval, not external security certification, "
    "and not real-world validation."
)

REQUIRED_DOCS = {
    "staging_deployment": DOCS / "staging_deployment_v067.md",
    "deployed_url_smoke_test": DOCS / "deployed_url_smoke_test_v067.md",
    "vercel_frontend_deploy": DOCS / "vercel_frontend_deploy_v067.md",
}

ENV_EXAMPLE = ROOT / ".env.example"
VERCEL_CONFIG = FRONTEND / "vercel.json"

REQUIRED_ENV_LINES = [
    "NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend",
    "LOCAL_REVIEW_ENABLED=false",
    "LOCAL_FILE_WRITES_ENABLED=false",
    "LOCAL_DEMO_BRIDGE_ENABLED=false",
    "PUBLIC_FORM_CAPTURE_ENABLED=false",
    "PUBLIC_DEMO_BRIDGE_ENABLED=false",
]

PUBLIC_SAFE_ROUTES = [
    "/",
    "/demo",
    "/docs",
    "/alpha",
    "/book-demo",
    "/contact",
    "/demo-video",
    "/capabilities/[slug]",
]

SMOKE_PUBLIC_ROUTES = ["/", "/docs", "/demo", "/alpha", "/book-demo", "/contact"]
SMOKE_BLOCKED_GET_ROUTES = ["/alpha/review", "/book-demo/review", "/api/alpha/review", "/api/demo/review"]
SMOKE_DISABLED_POST_ROUTES = ["/api/demo/run", "/api/alpha/request", "/api/demo/book"]

BLOCKED_LOCAL_ROUTES = [
    "/alpha/review",
    "/book-demo/review",
    "/api/alpha/review",
    "/api/demo/review",
]

DISABLED_DEMO_BRIDGE_ROUTES = [
    "/api/demo/scenarios",
    "/api/demo/run",
    "/api/demo/report",
    "/api/demo/health",
]

DISABLED_FORM_ROUTES = ["/api/alpha/request", "/api/demo/book"]

POSITIVE_OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted api is live",
    "hosted backend is live",
    "live api access granted",
    "api keys issued",
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
    "billing enabled",
    "deployed url verified",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

RESTRICTED_PATTERNS = [
    r"sk-[A-Za-z0-9_-]+",
    r"pk_live_[A-Za-z0-9_-]+",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"C:\\Users\\",
    r"\bprivate_internal_[A-Za-z0-9_./-]+",
    r"\blocal_alpha_requests_[A-Za-z0-9_./-]+",
    r"\blocal_demo_requests_[A-Za-z0-9_./-]+",
    r"\bdebug_trace\b",
    r"\brequest_details\b",
    r"\breviewer_notes\b",
    r"\bfull_api_key\b",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def blob(paths: list[Path]) -> str:
    return "\n".join(read_text(path) for path in paths if path.exists())


def overclaims(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in POSITIVE_OVERCLAIMS if term in lower]


def punitive_hits(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in PUNITIVE_TERMS if term in lower]


def restricted_hits(text: str) -> list[str]:
    hits = []
    for pattern in RESTRICTED_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def env_example_ok() -> tuple[bool, str]:
    if not ENV_EXAMPLE.exists():
        return False, ".env.example missing"
    text = read_text(ENV_EXAMPLE)
    required = [
        "NEXT_PUBLIC_DEPLOYMENT_MODE=local",
        "LOCAL_REVIEW_ENABLED=false",
        "LOCAL_FILE_WRITES_ENABLED=false",
        "LOCAL_DEMO_BRIDGE_ENABLED=false",
        "PUBLIC_FORM_CAPTURE_ENABLED=false",
        "PUBLIC_DEMO_BRIDGE_ENABLED=false",
    ]
    missing = [line for line in required if line not in text]
    if missing:
        return False, f"missing: {', '.join(missing)}"
    if re.search(r"sk-[A-Za-z0-9_-]+|pk_live_[A-Za-z0-9_-]+|-----BEGIN", text):
        return False, "secret-looking token found"
    return True, "placeholder-only flags present"


def vercel_config_ok() -> tuple[bool, str]:
    if not VERCEL_CONFIG.exists():
        return False, "frontend/vercel.json missing"
    try:
        config = json.loads(read_text(VERCEL_CONFIG))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    env = config.get("env", {})
    required = {
        "NEXT_PUBLIC_DEPLOYMENT_MODE": "public_frontend",
        "LOCAL_REVIEW_ENABLED": "false",
        "LOCAL_FILE_WRITES_ENABLED": "false",
        "LOCAL_DEMO_BRIDGE_ENABLED": "false",
        "PUBLIC_FORM_CAPTURE_ENABLED": "false",
        "PUBLIC_DEMO_BRIDGE_ENABLED": "false",
    }
    missing = [f"{key}={value}" for key, value in required.items() if env.get(key) != value]
    if missing:
        return False, f"missing/incorrect env: {', '.join(missing)}"
    if config.get("framework") != "nextjs":
        return False, "framework is not nextjs"
    if config.get("buildCommand") != "npm run build":
        return False, "buildCommand is not npm run build"
    return True, "frontend-only Vercel config with safe public defaults"


def run_frontend_command(args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "NEXT_PUBLIC_DEPLOYMENT_MODE": "public_frontend",
            "LOCAL_REVIEW_ENABLED": "false",
            "LOCAL_FILE_WRITES_ENABLED": "false",
            "LOCAL_DEMO_BRIDGE_ENABLED": "false",
            "PUBLIC_FORM_CAPTURE_ENABLED": "false",
            "PUBLIC_DEMO_BRIDGE_ENABLED": "false",
        }
    )
    npm = "npm.cmd" if os.name == "nt" else "npm"
    completed = subprocess.run(
        [npm, "run", *args],
        cwd=FRONTEND,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    output = (completed.stdout or "").strip()
    return {
        "command": f"npm run {' '.join(args)}",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output_tail": output[-4000:],
    }


def staging_url() -> str:
    return (os.environ.get("PRMR_STAGING_DEPLOYMENT_URL") or os.environ.get("STAGING_DEPLOYMENT_URL") or "").strip().rstrip("/")


def fetch_url(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": "PRMR-V067-Smoke-Test/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read(250000).decode("utf-8", errors="replace")
            return {"url": url, "method": method, "status_code": response.status, "body_excerpt": body[:1200]}
    except error.HTTPError as exc:
        body = exc.read(250000).decode("utf-8", errors="replace")
        return {"url": url, "method": method, "status_code": exc.code, "body_excerpt": body[:1200]}
    except Exception as exc:  # pragma: no cover - network condition
        return {"url": url, "method": method, "status_code": None, "error": str(exc), "body_excerpt": ""}


def smoke_check_deployed_url(base_url: str) -> dict[str, Any]:
    if not base_url:
        return {
            "deployment_url_available": False,
            "deployed_url_smoke_check": "not_run_no_url",
            "checked_routes": [],
            "boundary": BOUNDARY,
        }

    checks: list[dict[str, Any]] = []
    for route in SMOKE_PUBLIC_ROUTES:
        checks.append(fetch_url(f"{base_url}{route}"))
    for route in SMOKE_BLOCKED_GET_ROUTES:
        checks.append(fetch_url(f"{base_url}{route}"))
    checks.append(fetch_url(f"{base_url}/api/demo/run", method="POST", payload={"scenario_id": "ai_agent_memory"}))
    checks.append(fetch_url(f"{base_url}/api/alpha/request", method="POST", payload={"synthetic": True}))
    checks.append(fetch_url(f"{base_url}/api/demo/book", method="POST", payload={"synthetic": True}))

    public_ok = all(
        item["status_code"] is not None and 200 <= int(item["status_code"]) < 400
        for item in checks
        if item["url"].replace(base_url, "") in SMOKE_PUBLIC_ROUTES
    )
    blocked_ok = all(
        (
            item["status_code"] in {404, 405, 503}
            or "local_only_route_disabled" in item.get("body_excerpt", "")
            or "Local-only route disabled" in item.get("body_excerpt", "")
        )
        for item in checks
        if item["url"].replace(base_url, "") in SMOKE_BLOCKED_GET_ROUTES
    )
    demo_disabled_ok = any(
        item["url"].endswith("/api/demo/run")
        and (
            item["status_code"] in {404, 405, 503}
            or "demo_bridge_disabled_on_public_frontend" in item.get("body_excerpt", "")
        )
        for item in checks
    )
    forms_disabled_ok = all(
        (
            item["status_code"] in {404, 405, 503}
            or "request_capture_not_enabled_on_public_frontend" in item.get("body_excerpt", "")
        )
        for item in checks
        if item["url"].endswith("/api/alpha/request") or item["url"].endswith("/api/demo/book")
    )
    restricted = restricted_hits(json.dumps(checks))

    return {
        "deployment_url_available": True,
        "deployed_url": base_url,
        "deployed_url_smoke_check": "pass" if public_ok and blocked_ok and demo_disabled_ok and forms_disabled_ok and not restricted else "needs_work",
        "public_routes_ok": public_ok,
        "blocked_routes_ok": blocked_ok,
        "demo_bridge_disabled_ok": demo_disabled_ok,
        "forms_disabled_ok": forms_disabled_ok,
        "restricted_public_patterns_found": restricted,
        "checked_routes": checks,
        "boundary": BOUNDARY,
    }


def write_reports(
    checks: list[dict[str, Any]],
    typecheck_result: dict[str, Any],
    build_result: dict[str, Any],
    smoke: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    dump_json(SMOKE_REPORT, smoke)
    result = "PASS" if all(check["passed"] for check in checks) else "NEEDS_WORK"

    public_payload = {
        "version": "0.67",
        "title": "Staging Deployment Readiness",
        "result": result,
        "generated_at": now,
        "boundary": BOUNDARY,
        "preferred_deployment_target": "Vercel frontend-only deployment",
        "deployment_url_available": bool(smoke.get("deployment_url_available")),
        "deployed_url_smoke_check": smoke.get("deployed_url_smoke_check"),
        "required_public_frontend_env": {
            "NEXT_PUBLIC_DEPLOYMENT_MODE": "public_frontend",
            "LOCAL_REVIEW_ENABLED": "false",
            "LOCAL_FILE_WRITES_ENABLED": "false",
            "LOCAL_DEMO_BRIDGE_ENABLED": "false",
            "PUBLIC_FORM_CAPTURE_ENABLED": "false",
            "PUBLIC_DEMO_BRIDGE_ENABLED": "false",
        },
        "public_safe_routes": PUBLIC_SAFE_ROUTES,
        "blocked_local_routes": BLOCKED_LOCAL_ROUTES,
        "disabled_demo_bridge_routes": DISABLED_DEMO_BRIDGE_ROUTES,
        "disabled_form_routes": DISABLED_FORM_ROUTES,
        "frontend_commands": {
            "typecheck": {"command": typecheck_result["command"], "passed": typecheck_result["passed"]},
            "build": {"command": build_result["command"], "passed": build_result["passed"]},
        },
        "remaining_gaps_for_v068": [
            "provide and smoke-check a deployed staging URL if none exists",
            "hosted storage for request capture",
            "authentication and permissioned admin review",
            "rate limiting and abuse controls",
            "monitoring and deployed logs",
            "private report storage strategy",
        ],
    }
    if smoke.get("deployment_url_available"):
        public_payload["deployed_url"] = smoke.get("deployed_url")

    private_payload = {
        **public_payload,
        "title": "Private Staging Deployment Readiness Detail",
        "checks": checks,
        "typecheck_output_tail": typecheck_result["output_tail"],
        "build_output_tail": build_result["output_tail"],
        "smoke_detail": smoke,
    }

    dump_json(PUBLIC_REPORT, public_payload)
    dump_json(PRIVATE_REPORT, private_payload)


def write_scorecard(checks: list[dict[str, Any]], typecheck_result: dict[str, Any], build_result: dict[str, Any], smoke: dict[str, Any]) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.67 Staging Deployment + Deployed URL Smoke Test Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        f"Deployment URL available: {str(bool(smoke.get('deployment_url_available'))).lower()}",
        f"Deployed URL smoke check: {smoke.get('deployed_url_smoke_check')}",
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
            f"- {'PASS' if typecheck_result['passed'] else 'FAIL'}: {typecheck_result['command']}",
            f"- {'PASS' if build_result['passed'] else 'FAIL'}: {build_result['command']}",
            "- RUN: python examples/audit_v067_staging_deployment.py",
            "",
            BOUNDARY,
            "",
        ]
    )
    SCORECARD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []

    for name, path in REQUIRED_DOCS.items():
        add_check(checks, f"{name}_doc_exists", path.exists(), str(path.relative_to(ROOT)))

    docs_text = blob(list(REQUIRED_DOCS.values()))
    for env_line in REQUIRED_ENV_LINES:
        add_check(checks, f"doc_env_{env_line.split('=')[0].lower()}_exists", env_line in docs_text, env_line)

    add_check(checks, "public_safe_route_list_exists", all(route in docs_text for route in PUBLIC_SAFE_ROUTES), ", ".join(PUBLIC_SAFE_ROUTES))
    add_check(checks, "blocked_local_route_list_exists", all(route in docs_text for route in BLOCKED_LOCAL_ROUTES), ", ".join(BLOCKED_LOCAL_ROUTES))
    add_check(checks, "disabled_demo_bridge_route_list_exists", all(route in docs_text for route in DISABLED_DEMO_BRIDGE_ROUTES), ", ".join(DISABLED_DEMO_BRIDGE_ROUTES))
    add_check(checks, "disabled_form_api_behavior_documented", "request_capture_not_enabled_on_public_frontend" in docs_text, "disabled form code documented")

    vercel_ok, vercel_detail = vercel_config_ok()
    add_check(checks, "frontend_vercel_config_safe", vercel_ok, vercel_detail)

    env_ok, env_detail = env_example_ok()
    add_check(checks, "env_example_placeholders_only", env_ok, env_detail)

    add_check(
        checks,
        "docs_have_no_positive_hosted_or_production_claims",
        not overclaims(docs_text),
        "none" if not overclaims(docs_text) else ", ".join(overclaims(docs_text)),
    )
    add_check(
        checks,
        "docs_have_no_punitive_wording",
        not punitive_hits(docs_text),
        "none" if not punitive_hits(docs_text) else ", ".join(punitive_hits(docs_text)),
    )

    print("Running frontend typecheck in public frontend mode...")
    typecheck_result = run_frontend_command(["typecheck"])
    add_check(checks, "npm_run_typecheck_passes", typecheck_result["passed"], typecheck_result["output_tail"][-600:] or "ok")

    print("Running frontend build in public frontend mode...")
    build_result = run_frontend_command(["build"])
    add_check(checks, "npm_run_build_passes", build_result["passed"], build_result["output_tail"][-600:] or "ok")

    smoke = smoke_check_deployed_url(staging_url())
    if smoke.get("deployment_url_available"):
        add_check(checks, "deployed_public_routes_smoke_checked", bool(smoke.get("public_routes_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "deployed_blocked_routes_smoke_checked", bool(smoke.get("blocked_routes_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "deployed_demo_bridge_disabled", bool(smoke.get("demo_bridge_disabled_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "deployed_forms_disabled", bool(smoke.get("forms_disabled_ok")), smoke.get("deployed_url", ""))
        add_check(
            checks,
            "deployed_output_has_no_restricted_public_patterns",
            not smoke.get("restricted_public_patterns_found"),
            "none" if not smoke.get("restricted_public_patterns_found") else ", ".join(smoke["restricted_public_patterns_found"]),
        )
    else:
        add_check(checks, "deployed_url_smoke_check_not_run_no_url", True, "not_run_no_url")

    write_reports(checks, typecheck_result, build_result, smoke)

    public_text = read_text(PUBLIC_REPORT) + "\n" + read_text(SMOKE_REPORT)
    public_restricted = restricted_hits(public_text)
    add_check(
        checks,
        "public_reports_contain_no_secrets_or_private_request_details",
        not public_restricted,
        "none" if not public_restricted else ", ".join(public_restricted),
    )
    add_check(
        checks,
        "public_reports_have_no_positive_overclaims",
        not overclaims(public_text),
        "none" if not overclaims(public_text) else ", ".join(overclaims(public_text)),
    )
    add_check(
        checks,
        "public_reports_have_no_punitive_wording",
        not punitive_hits(public_text),
        "none" if not punitive_hits(public_text) else ", ".join(punitive_hits(public_text)),
    )

    write_reports(checks, typecheck_result, build_result, smoke)
    write_scorecard(checks, typecheck_result, build_result, smoke)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.67 STAGING DEPLOYMENT AUDIT")
    print("-----------------------------------")
    print(f"Deployment URL available: {bool(smoke.get('deployment_url_available'))}")
    print(f"Deployed URL smoke check: {smoke.get('deployed_url_smoke_check')}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Command results:")
    print(f"- npm run typecheck: {'PASS' if typecheck_result['passed'] else 'FAIL'}")
    print(f"- npm run build: {'PASS' if build_result['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {SMOKE_REPORT.relative_to(ROOT)}")
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
