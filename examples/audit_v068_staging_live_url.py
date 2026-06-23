"""V0.68 actual staging deploy / live URL smoke readiness audit.

This milestone does not claim a live deployment unless a deployed URL is
explicitly provided via PRMR_STAGING_DEPLOYMENT_URL or STAGING_DEPLOYMENT_URL.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from html import unescape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports" / "v068"

PUBLIC_REPORT = REPORTS / "public_staging_live_url_v068.json"
PRIVATE_REPORT = REPORTS / "private_internal_staging_live_url_v068.json"
SMOKE_REPORT = REPORTS / "live_url_route_smoke_check_v068.json"
SCORECARD = REPORTS / "scorecard_v068.md"

BOUNDARY = (
    "V0.68 is actual staging deployment verification and/or live URL smoke-test "
    "readiness only. It is not hosted backend, not production onboarding, not "
    "billing, not live API access, not API key issuance, not external validation, "
    "not bank approval, not compliance approval, not legal approval, not external "
    "security certification, and not real-world validation."
)

V067_DOCS = {
    "staging_deployment": DOCS / "staging_deployment_v067.md",
    "deployed_url_smoke_test": DOCS / "deployed_url_smoke_test_v067.md",
    "vercel_frontend_deploy": DOCS / "vercel_frontend_deploy_v067.md",
}

ENV_EXAMPLE = ROOT / ".env.example"
VERCEL_CONFIG = FRONTEND / "vercel.json"

REQUIRED_ENV = {
    "NEXT_PUBLIC_DEPLOYMENT_MODE": "public_frontend",
    "LOCAL_REVIEW_ENABLED": "false",
    "LOCAL_FILE_WRITES_ENABLED": "false",
    "LOCAL_DEMO_BRIDGE_ENABLED": "false",
    "PUBLIC_FORM_CAPTURE_ENABLED": "false",
    "PUBLIC_DEMO_BRIDGE_ENABLED": "false",
}

PUBLIC_SAFE_ROUTES = ["/", "/demo", "/docs", "/alpha", "/book-demo", "/contact", "/demo-video"]
BLOCKED_ROUTES = ["/alpha/review", "/book-demo/review", "/api/alpha/review", "/api/demo/review"]
DEMO_BRIDGE_ROUTES = ["/api/demo/scenarios", "/api/demo/run", "/api/demo/report", "/api/demo/health"]
FORM_ROUTES = ["/api/alpha/request", "/api/demo/book"]

MANUAL_DEPLOYMENT_STEPS = [
    "Create or open a Vercel project for the frontend only.",
    "Set the Vercel project root directory to frontend.",
    "Use framework preset Next.js.",
    "Use install command npm install.",
    "Use build command npm run build.",
    "Let Vercel handle the Next.js output from .next.",
    "Set NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend.",
    "Set LOCAL_REVIEW_ENABLED=false.",
    "Set LOCAL_FILE_WRITES_ENABLED=false.",
    "Set LOCAL_DEMO_BRIDGE_ENABLED=false.",
    "Set PUBLIC_FORM_CAPTURE_ENABLED=false.",
    "Set PUBLIC_DEMO_BRIDGE_ENABLED=false.",
    "Do not add secrets; public frontend mode requires no secrets.",
    "After deployment, set PRMR_STAGING_DEPLOYMENT_URL or STAGING_DEPLOYMENT_URL to the deployed URL and rerun this audit.",
]

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
    r"(?<![A-Za-z0-9])sk-(?:live|test|proj)?_?[A-Za-z0-9_-]{20,}\b",
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
    r"\bengine internals\b",
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


def restricted_hits(text: str) -> list[str]:
    return [pattern for pattern in RESTRICTED_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]


def page_visible_text(html: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_styles = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_scripts, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def overclaims(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in POSITIVE_OVERCLAIMS if term in lower]


def punitive_hits(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in PUNITIVE_TERMS if term in lower]


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
        return False, "missing placeholders: " + ", ".join(missing)
    if restricted_hits(text):
        return False, "secret/private-looking pattern found"
    return True, "placeholder-only flags present"


def vercel_config_ok() -> tuple[bool, str]:
    if not VERCEL_CONFIG.exists():
        return False, "frontend/vercel.json missing"
    try:
        config = json.loads(read_text(VERCEL_CONFIG))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    env = config.get("env", {})
    missing = [f"{key}={value}" for key, value in REQUIRED_ENV.items() if env.get(key) != value]
    if missing:
        return False, "missing/incorrect env: " + ", ".join(missing)
    if config.get("framework") != "nextjs":
        return False, "framework is not nextjs"
    if config.get("buildCommand") != "npm run build":
        return False, "buildCommand is not npm run build"
    if config.get("installCommand") != "npm install":
        return False, "installCommand is not npm install"
    return True, "frontend-only Vercel config is present with public-safe defaults"


def run_frontend_command(args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(REQUIRED_ENV)
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


def deployed_url() -> str:
    return (os.environ.get("PRMR_STAGING_DEPLOYMENT_URL") or os.environ.get("STAGING_DEPLOYMENT_URL") or "").strip().rstrip("/")


def fetch_url(base_url: str, route: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": "PRMR-V068-Live-URL-Smoke/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = f"{base_url}{route}"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read(250000).decode("utf-8", errors="replace")
            scan_body = body if "application/json" in response.headers.get("content-type", "") else page_visible_text(body)
            return {
                "route": route,
                "method": method,
                "status_code": response.status,
                "body_excerpt": body[:1200],
                "restricted_patterns": restricted_hits(scan_body),
                "overclaim_terms": overclaims(scan_body),
                "punitive_terms": punitive_hits(scan_body),
            }
    except error.HTTPError as exc:
        body = exc.read(250000).decode("utf-8", errors="replace")
        scan_body = body if "application/json" in exc.headers.get("content-type", "") else page_visible_text(body)
        return {
            "route": route,
            "method": method,
            "status_code": exc.code,
            "body_excerpt": body[:1200],
            "restricted_patterns": restricted_hits(scan_body),
            "overclaim_terms": overclaims(scan_body),
            "punitive_terms": punitive_hits(scan_body),
        }
    except Exception as exc:  # pragma: no cover - depends on live network
        return {
            "route": route,
            "method": method,
            "status_code": None,
            "error": str(exc),
            "body_excerpt": "",
            "restricted_patterns": [],
            "overclaim_terms": [],
            "punitive_terms": [],
        }


def run_live_smoke(base_url: str) -> dict[str, Any]:
    if not base_url:
        return {
            "deployment_url_available": False,
            "live_url_smoke_check": "not_run_no_url",
            "live_url_result": "NEEDS_DEPLOYED_URL",
            "checked_routes": [],
            "manual_deployment_steps": MANUAL_DEPLOYMENT_STEPS,
            "boundary": BOUNDARY,
        }

    route_checks: list[dict[str, Any]] = []
    for route in PUBLIC_SAFE_ROUTES:
        route_checks.append(fetch_url(base_url, route))
    for route in BLOCKED_ROUTES:
        route_checks.append(fetch_url(base_url, route))
    for route in DEMO_BRIDGE_ROUTES:
        if route == "/api/demo/run":
            route_checks.append(fetch_url(base_url, route, method="POST", payload={"scenario_id": "ai_agent_memory"}))
        else:
            route_checks.append(fetch_url(base_url, route))
    for route in FORM_ROUTES:
        route_checks.append(fetch_url(base_url, route, method="POST", payload={"synthetic": True}))

    public_ok = all(
        item["status_code"] is not None
        and 200 <= int(item["status_code"]) < 400
        and not item["restricted_patterns"]
        and not item["overclaim_terms"]
        and not item["punitive_terms"]
        for item in route_checks
        if item["route"] in PUBLIC_SAFE_ROUTES
    )
    blocked_ok = all(
        item["status_code"] in {404, 405, 503}
        or "local_only_route_disabled" in item.get("body_excerpt", "")
        or "Local-only route disabled" in item.get("body_excerpt", "")
        for item in route_checks
        if item["route"] in BLOCKED_ROUTES
    )
    demo_bridge_ok = all(
        item["status_code"] in {404, 405, 503}
        or "demo_bridge_disabled_on_public_frontend" in item.get("body_excerpt", "")
        for item in route_checks
        if item["route"] in DEMO_BRIDGE_ROUTES
    )
    forms_ok = all(
        item["status_code"] in {404, 405, 503}
        or "request_capture_not_enabled_on_public_frontend" in item.get("body_excerpt", "")
        for item in route_checks
        if item["route"] in FORM_ROUTES
    )
    no_restricted = not any(
        item["restricted_patterns"] or item["overclaim_terms"] or item["punitive_terms"] for item in route_checks
    )
    live_pass = public_ok and blocked_ok and demo_bridge_ok and forms_ok and no_restricted

    return {
        "deployment_url_available": True,
        "deployed_url": base_url,
        "live_url_smoke_check": "pass" if live_pass else "needs_work",
        "live_url_result": "PASS" if live_pass else "NEEDS_WORK",
        "public_routes_ok": public_ok,
        "blocked_routes_ok": blocked_ok,
        "demo_bridge_disabled_ok": demo_bridge_ok,
        "form_apis_safe_ok": forms_ok,
        "no_restricted_public_patterns": no_restricted,
        "checked_routes": route_checks,
        "boundary": BOUNDARY,
    }


def audit_result(all_checks_passed: bool, smoke: dict[str, Any]) -> str:
    if not all_checks_passed:
        return "NEEDS_WORK"
    if not smoke.get("deployment_url_available"):
        return "PASS_READINESS_NEEDS_DEPLOYED_URL"
    return "PASS" if smoke.get("live_url_result") == "PASS" else "NEEDS_WORK"


def write_reports(
    checks: list[dict[str, Any]],
    typecheck_result: dict[str, Any],
    build_result: dict[str, Any],
    smoke: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    readiness_pass = all(check["passed"] for check in checks)
    result = audit_result(readiness_pass, smoke)
    dump_json(SMOKE_REPORT, smoke)

    public_payload: dict[str, Any] = {
        "version": "0.68",
        "title": "Actual Staging Deploy + Live URL Smoke Check",
        "result": "NEEDS_DEPLOYED_URL" if not smoke.get("deployment_url_available") else result,
        "readiness_result": "PASS" if readiness_pass else "NEEDS_WORK",
        "live_url_result": smoke.get("live_url_result"),
        "generated_at": now,
        "boundary": BOUNDARY,
        "deployment_url_available": bool(smoke.get("deployment_url_available")),
        "live_url_smoke_check": smoke.get("live_url_smoke_check"),
        "deployment_target": "Vercel frontend deployment from frontend/",
        "required_public_frontend_env": REQUIRED_ENV,
        "public_safe_routes": PUBLIC_SAFE_ROUTES,
        "blocked_local_routes": BLOCKED_ROUTES,
        "disabled_demo_bridge_routes": DEMO_BRIDGE_ROUTES,
        "disabled_form_routes": FORM_ROUTES,
        "manual_deployment_steps": MANUAL_DEPLOYMENT_STEPS,
        "frontend_commands": {
            "typecheck": {"command": typecheck_result["command"], "passed": typecheck_result["passed"]},
            "build": {"command": build_result["command"], "passed": build_result["passed"]},
        },
        "remaining_gaps_for_v069": [
            "provide a deployed staging URL and rerun live URL smoke checks if none was provided",
            "hosted request capture storage",
            "authentication and permissioned admin review",
            "secure deployed monitoring and logs",
            "rate limiting and abuse controls",
            "private report storage strategy",
        ],
    }
    if smoke.get("deployment_url_available"):
        public_payload.update(
            {
                "deployed_url": smoke.get("deployed_url"),
                "route_status_summary": {
                    "public_routes_ok": smoke.get("public_routes_ok"),
                    "blocked_routes_ok": smoke.get("blocked_routes_ok"),
                    "demo_bridge_disabled_ok": smoke.get("demo_bridge_disabled_ok"),
                    "form_apis_safe_ok": smoke.get("form_apis_safe_ok"),
                    "no_restricted_public_patterns": smoke.get("no_restricted_public_patterns"),
                },
            }
        )

    private_payload = {
        **public_payload,
        "title": "Private Staging Live URL Smoke Detail",
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
    result = audit_result(passed == total, smoke)
    lines = [
        "# V0.68 Actual Staging Deploy + Live URL Smoke Check Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        f"Deployment URL available: {str(bool(smoke.get('deployment_url_available'))).lower()}",
        f"Live URL smoke check: {smoke.get('live_url_smoke_check')}",
        f"Live URL result: {smoke.get('live_url_result')}",
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
            "- RUN: python examples/audit_v068_staging_live_url.py",
            "",
            "## Manual Deployment Steps If URL Is Missing",
            "",
            *[f"- {step}" for step in MANUAL_DEPLOYMENT_STEPS],
            "",
            BOUNDARY,
            "",
        ]
    )
    SCORECARD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []

    for name, path in V067_DOCS.items():
        add_check(checks, f"v067_{name}_doc_still_exists", path.exists(), str(path.relative_to(ROOT)))

    v067_docs_text = blob(list(V067_DOCS.values()))
    add_check(checks, "staging_env_vars_documented", all(f"{k}={v}" in v067_docs_text for k, v in REQUIRED_ENV.items()), "required public frontend env vars")
    add_check(checks, "public_safe_route_smoke_logic_exists", bool(PUBLIC_SAFE_ROUTES), ", ".join(PUBLIC_SAFE_ROUTES))
    add_check(checks, "blocked_route_smoke_logic_exists", bool(BLOCKED_ROUTES), ", ".join(BLOCKED_ROUTES))
    add_check(checks, "demo_bridge_disabled_smoke_logic_exists", bool(DEMO_BRIDGE_ROUTES), ", ".join(DEMO_BRIDGE_ROUTES))
    add_check(checks, "form_api_safe_behavior_smoke_logic_exists", bool(FORM_ROUTES), ", ".join(FORM_ROUTES))

    vercel_ok, vercel_detail = vercel_config_ok()
    add_check(checks, "frontend_vercel_config_ready", vercel_ok, vercel_detail)

    env_ok, env_detail = env_example_ok()
    add_check(checks, "env_example_placeholders_only", env_ok, env_detail)

    add_check(
        checks,
        "docs_have_no_positive_hosted_or_production_claims",
        not overclaims(v067_docs_text),
        "none" if not overclaims(v067_docs_text) else ", ".join(overclaims(v067_docs_text)),
    )
    add_check(
        checks,
        "docs_have_no_punitive_wording",
        not punitive_hits(v067_docs_text),
        "none" if not punitive_hits(v067_docs_text) else ", ".join(punitive_hits(v067_docs_text)),
    )

    print("Running frontend typecheck in public frontend mode...")
    typecheck_result = run_frontend_command(["typecheck"])
    add_check(checks, "npm_run_typecheck_passes", typecheck_result["passed"], typecheck_result["output_tail"][-600:] or "ok")

    print("Running frontend build in public frontend mode...")
    build_result = run_frontend_command(["build"])
    add_check(checks, "npm_run_build_passes", build_result["passed"], build_result["output_tail"][-600:] or "ok")

    smoke = run_live_smoke(deployed_url())
    if smoke.get("deployment_url_available"):
        add_check(checks, "live_public_routes_smoke_checked", bool(smoke.get("public_routes_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "live_blocked_routes_smoke_checked", bool(smoke.get("blocked_routes_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "live_demo_bridge_routes_disabled", bool(smoke.get("demo_bridge_disabled_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "live_form_apis_safe", bool(smoke.get("form_apis_safe_ok")), smoke.get("deployed_url", ""))
        add_check(checks, "live_output_has_no_restricted_public_patterns", bool(smoke.get("no_restricted_public_patterns")), smoke.get("deployed_url", ""))
    else:
        add_check(checks, "no_url_report_honestly_marks_not_run", smoke.get("live_url_smoke_check") == "not_run_no_url", "not_run_no_url")
        add_check(checks, "no_url_live_result_needs_deployed_url", smoke.get("live_url_result") == "NEEDS_DEPLOYED_URL", "NEEDS_DEPLOYED_URL")

    write_reports(checks, typecheck_result, build_result, smoke)

    public_text = read_text(PUBLIC_REPORT) + "\n" + read_text(SMOKE_REPORT)
    public_restricted = restricted_hits(public_text)
    add_check(
        checks,
        "public_reports_contain_no_secrets_or_private_details",
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
    result = audit_result(passed == total, smoke)

    print("PRMR V0.68 STAGING LIVE URL AUDIT")
    print("---------------------------------")
    print(f"Deployment URL available: {bool(smoke.get('deployment_url_available'))}")
    print(f"Live URL smoke check: {smoke.get('live_url_smoke_check')}")
    print(f"Live URL result: {smoke.get('live_url_result')}")
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

    if result == "NEEDS_WORK":
        print("Failures:")
        for check in checks:
            if not check["passed"]:
                print(f"- {check['name']}: {check['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
