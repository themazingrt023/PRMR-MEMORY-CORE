"""V0.66 live frontend readiness audit.

This audit verifies that PRMR Memory Core can be prepared for a public frontend
deployment mode without exposing local review consoles, local file-writing APIs,
local demo bridge execution, secrets, private reports, or inflated claims.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports" / "v066"

PUBLIC_REPORT = REPORTS / "public_live_frontend_readiness_v066.json"
PRIVATE_REPORT = REPORTS / "private_internal_live_frontend_readiness_v066.json"
ROUTE_CHECK = REPORTS / "public_mode_route_check_v066.json"
SCORECARD = REPORTS / "scorecard_v066.md"

BOUNDARY = (
    "V0.66 is live frontend readiness and public-safe deployment switching only. "
    "It is not hosted backend, not production onboarding, not billing, not live "
    "API access, not API key issuance, not external validation, not bank approval, "
    "not compliance approval, not legal approval, not external security "
    "certification, and not real-world validation."
)

REQUIRED_DOCS = {
    "live_frontend_domain_readiness": DOCS / "live_frontend_domain_readiness_v066.md",
    "public_frontend_mode": DOCS / "public_frontend_mode_v066.md",
    "deployment_smoke_check": DOCS / "deployment_smoke_check_v066.md",
}

DEPLOYMENT_MODE_FILE = FRONTEND / "lib" / "deploymentMode.ts"
ENV_EXAMPLE = ROOT / ".env.example"

PUBLIC_SAFE_PAGE_FILES = [
    FRONTEND / "app" / "page.tsx",
    FRONTEND / "app" / "demo" / "page.tsx",
    FRONTEND / "app" / "docs" / "page.tsx",
    FRONTEND / "app" / "alpha" / "page.tsx",
    FRONTEND / "app" / "book-demo" / "page.tsx",
    FRONTEND / "app" / "contact" / "page.tsx",
    FRONTEND / "app" / "demo-video" / "page.tsx",
    FRONTEND / "app" / "capabilities" / "[slug]" / "page.tsx",
]

LOCAL_REVIEW_ROUTES = {
    "/alpha/review": FRONTEND / "app" / "alpha" / "review" / "page.tsx",
    "/book-demo/review": FRONTEND / "app" / "book-demo" / "review" / "page.tsx",
    "/api/alpha/review": FRONTEND / "app" / "api" / "alpha" / "review" / "route.ts",
    "/api/demo/review": FRONTEND / "app" / "api" / "demo" / "review" / "route.ts",
}

DEMO_BRIDGE_ROUTES = {
    "/api/demo/scenarios": FRONTEND / "app" / "api" / "demo" / "scenarios" / "route.ts",
    "/api/demo/run": FRONTEND / "app" / "api" / "demo" / "run" / "route.ts",
    "/api/demo/report": FRONTEND / "app" / "api" / "demo" / "report" / "route.ts",
    "/api/demo/health": FRONTEND / "app" / "api" / "demo" / "health" / "route.ts",
}

FORM_CAPTURE_ROUTES = {
    "/api/alpha/request": FRONTEND / "app" / "api" / "alpha" / "request" / "route.ts",
    "/api/demo/book": FRONTEND / "app" / "api" / "demo" / "book" / "route.ts",
}

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

PUBLIC_RESTRICTED_PATTERNS = [
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


def contains_all(path: Path, needles: list[str]) -> bool:
    if not path.exists():
        return False
    text = read_text(path)
    return all(needle in text for needle in needles)


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
    for pattern in PUBLIC_RESTRICTED_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def env_example_ok() -> tuple[bool, str]:
    if not ENV_EXAMPLE.exists():
        return False, ".env.example missing"
    text = read_text(ENV_EXAMPLE)
    required_flags = [
        "NEXT_PUBLIC_DEPLOYMENT_MODE=local",
        "LOCAL_REVIEW_ENABLED=false",
        "LOCAL_FILE_WRITES_ENABLED=false",
        "LOCAL_DEMO_BRIDGE_ENABLED=false",
        "PUBLIC_FORM_CAPTURE_ENABLED=false",
        "PUBLIC_DEMO_BRIDGE_ENABLED=false",
    ]
    missing = [flag for flag in required_flags if flag not in text]
    if missing:
        return False, f"missing flags: {', '.join(missing)}"
    if re.search(r"sk-[A-Za-z0-9_-]+|pk_live_[A-Za-z0-9_-]+|-----BEGIN", text):
        return False, "secret-looking token found"
    return True, "placeholder-only deployment flags present"


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


def write_reports(
    checks: list[dict[str, Any]],
    typecheck_result: dict[str, Any],
    build_result: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    route_check = {
        "version": "0.66",
        "title": "Public Mode Route Check",
        "deployment_mode": "public_frontend",
        "public_safe_routes": PUBLIC_SAFE_ROUTES,
        "blocked_local_review_routes": sorted(LOCAL_REVIEW_ROUTES),
        "disabled_demo_bridge_routes": sorted(DEMO_BRIDGE_ROUTES),
        "disabled_or_safe_form_routes": sorted(FORM_CAPTURE_ROUTES),
        "expected_disabled_codes": [
            "local_only_route_disabled",
            "demo_bridge_disabled_on_public_frontend",
            "request_capture_not_enabled_on_public_frontend",
        ],
        "boundary": BOUNDARY,
    }
    dump_json(ROUTE_CHECK, route_check)

    result = "PASS" if all(check["passed"] for check in checks) else "NEEDS_WORK"
    public_payload = {
        "version": "0.66",
        "title": "Live Frontend Domain Readiness",
        "result": result,
        "generated_at": now,
        "boundary": BOUNDARY,
        "deployment_mode": "public_frontend",
        "deployment_flags": {
            "NEXT_PUBLIC_DEPLOYMENT_MODE": "public_frontend",
            "LOCAL_REVIEW_ENABLED": "false",
            "LOCAL_FILE_WRITES_ENABLED": "false",
            "LOCAL_DEMO_BRIDGE_ENABLED": "false",
            "PUBLIC_FORM_CAPTURE_ENABLED": "false",
            "PUBLIC_DEMO_BRIDGE_ENABLED": "false",
        },
        "public_safe_routes": PUBLIC_SAFE_ROUTES,
        "blocked_local_route_behavior": "local-only review pages and APIs are disabled unless explicitly enabled for local use",
        "demo_bridge_behavior": "local demo bridge APIs are disabled in public frontend mode",
        "form_submission_behavior": "local file-writing form APIs return a safe disabled response in public frontend mode",
        "frontend_commands": {
            "typecheck": {
                "command": typecheck_result["command"],
                "passed": typecheck_result["passed"],
            },
            "build": {
                "command": build_result["command"],
                "passed": build_result["passed"],
            },
        },
        "remaining_gaps_for_actual_domain": [
            "deployed URL smoke check",
            "hosted storage for form capture",
            "authentication and permissioned admin review",
            "rate limiting and abuse controls",
            "secure deployed logging and monitoring",
            "private report storage policy",
        ],
    }
    private_payload = {
        **public_payload,
        "title": "Private Live Frontend Readiness Audit Detail",
        "checks": checks,
        "typecheck_output_tail": typecheck_result["output_tail"],
        "build_output_tail": build_result["output_tail"],
        "route_check": route_check,
    }

    dump_json(PUBLIC_REPORT, public_payload)
    dump_json(PRIVATE_REPORT, private_payload)


def write_scorecard(checks: list[dict[str, Any]], typecheck_result: dict[str, Any], build_result: dict[str, Any]) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.66 Live Frontend Domain Readiness Scorecard",
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
            f"- {'PASS' if typecheck_result['passed'] else 'FAIL'}: {typecheck_result['command']}",
            f"- {'PASS' if build_result['passed'] else 'FAIL'}: {build_result['command']}",
            "- RUN: python examples/audit_v066_live_frontend_readiness.py",
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

    add_check(checks, "deployment_mode_module_exists", DEPLOYMENT_MODE_FILE.exists(), str(DEPLOYMENT_MODE_FILE.relative_to(ROOT)))
    add_check(
        checks,
        "deployment_mode_flags_exist",
        contains_all(
            DEPLOYMENT_MODE_FILE,
            [
                "NEXT_PUBLIC_DEPLOYMENT_MODE",
                "LOCAL_REVIEW_ENABLED",
                "LOCAL_FILE_WRITES_ENABLED",
                "LOCAL_DEMO_BRIDGE_ENABLED",
                "PUBLIC_FORM_CAPTURE_ENABLED",
                "PUBLIC_DEMO_BRIDGE_ENABLED",
                "PUBLIC_FRONTEND_BOUNDARY",
            ],
        ),
        "shared deployment mode guard module",
    )

    env_ok, env_detail = env_example_ok()
    add_check(checks, "env_example_contains_safe_placeholders", env_ok, env_detail)

    local_review_ok = all(
        path.exists() and "isLocalReviewEnabled" in read_text(path) and "localOnlyRouteDisabledResponse" in read_text(path)
        for path in LOCAL_REVIEW_ROUTES.values()
        if path.name == "route.ts"
    )
    page_review_ok = all(
        path.exists() and "isLocalReviewEnabled" in read_text(path) and "Local-only route disabled" in read_text(path)
        for path in LOCAL_REVIEW_ROUTES.values()
        if path.name == "page.tsx"
    )
    add_check(checks, "local_review_routes_blocked_in_public_mode", local_review_ok and page_review_ok, "review pages/APIs use local review guard")

    demo_bridge_ok = all(
        path.exists()
        and "isLocalDemoBridgeEnabled" in read_text(path)
        and "demoBridgeDisabledResponse" in read_text(path)
        for path in DEMO_BRIDGE_ROUTES.values()
    )
    add_check(checks, "local_demo_bridge_apis_disabled_in_public_mode", demo_bridge_ok, "demo bridge APIs use disabled response guard")

    form_capture_ok = all(
        path.exists()
        and "isLocalFileWritesEnabled" in read_text(path)
        and "formCaptureDisabledResponse" in read_text(path)
        for path in FORM_CAPTURE_ROUTES.values()
    )
    add_check(checks, "file_writing_form_apis_disabled_or_safe_in_public_mode", form_capture_ok, "form APIs use local file write guard")

    public_pages_exist = all(path.exists() for path in PUBLIC_SAFE_PAGE_FILES)
    add_check(checks, "public_safe_page_files_exist", public_pages_exist, ", ".join(PUBLIC_SAFE_ROUTES))

    public_page_text = blob(PUBLIC_SAFE_PAGE_FILES)
    public_page_restricted = restricted_hits(public_page_text)
    add_check(
        checks,
        "public_pages_have_no_secrets_or_private_report_details",
        not public_page_restricted,
        "none" if not public_page_restricted else ", ".join(public_page_restricted),
    )
    add_check(
        checks,
        "public_pages_avoid_positive_hosted_or_production_claims",
        not overclaims(public_page_text),
        "none" if not overclaims(public_page_text) else ", ".join(overclaims(public_page_text)),
    )
    add_check(
        checks,
        "public_pages_use_non_punitive_wording",
        not punitive_hits(public_page_text),
        "none" if not punitive_hits(public_page_text) else ", ".join(punitive_hits(public_page_text)),
    )

    docs_text = blob(list(REQUIRED_DOCS.values()))
    add_check(
        checks,
        "docs_explain_public_frontend_mode",
        "public_frontend" in docs_text and "request_capture_not_enabled_on_public_frontend" in docs_text,
        "public frontend mode and disabled form behavior documented",
    )
    add_check(
        checks,
        "docs_have_no_positive_overclaims",
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

    write_reports(checks, typecheck_result, build_result)

    public_text = read_text(PUBLIC_REPORT) + "\n" + read_text(ROUTE_CHECK)
    public_restricted = restricted_hits(public_text)
    add_check(
        checks,
        "public_reports_have_no_private_details_or_secrets",
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
        "public_reports_use_non_punitive_wording",
        not punitive_hits(public_text),
        "none" if not punitive_hits(public_text) else ", ".join(punitive_hits(public_text)),
    )

    write_reports(checks, typecheck_result, build_result)
    write_scorecard(checks, typecheck_result, build_result)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.66 LIVE FRONTEND READINESS AUDIT")
    print("----------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Command results:")
    print(f"- npm run typecheck: {'PASS' if typecheck_result['passed'] else 'FAIL'}")
    print(f"- npm run build: {'PASS' if build_result['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {ROUTE_CHECK.relative_to(ROOT)}")
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
