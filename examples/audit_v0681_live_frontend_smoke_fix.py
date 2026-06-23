"""V0.68.1 live frontend smoke fix audit.

This verifies local source/build fixes for public frontend route blocking and
restricted-pattern scanning. Live Vercel verification still requires redeploying
the patched frontend and rerunning V0.68 with PRMR_STAGING_DEPLOYMENT_URL set.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORTS = ROOT / "reports" / "v0681"

PUBLIC_REPORT = REPORTS / "public_live_frontend_smoke_fix_v0681.json"
PRIVATE_REPORT = REPORTS / "private_internal_live_frontend_smoke_fix_v0681.json"
SMOKE_FIX_REPORT = REPORTS / "live_route_smoke_fix_v0681.json"
SCORECARD = REPORTS / "scorecard_v0681.md"

ALPHA_REVIEW_PAGE = FRONTEND / "app" / "alpha" / "review" / "page.tsx"
BOOK_DEMO_REVIEW_PAGE = FRONTEND / "app" / "book-demo" / "review" / "page.tsx"
LAYOUT = FRONTEND / "app" / "layout.tsx"
V068_AUDIT = ROOT / "examples" / "audit_v068_staging_live_url.py"

API_REVIEW_ROUTES = [
    FRONTEND / "app" / "api" / "alpha" / "review" / "route.ts",
    FRONTEND / "app" / "api" / "demo" / "review" / "route.ts",
]

DEMO_BRIDGE_ROUTES = [
    FRONTEND / "app" / "api" / "demo" / "scenarios" / "route.ts",
    FRONTEND / "app" / "api" / "demo" / "run" / "route.ts",
    FRONTEND / "app" / "api" / "demo" / "report" / "route.ts",
    FRONTEND / "app" / "api" / "demo" / "health" / "route.ts",
]

FORM_ROUTES = [
    FRONTEND / "app" / "api" / "alpha" / "request" / "route.ts",
    FRONTEND / "app" / "api" / "demo" / "book" / "route.ts",
]

DEPLOYED_URL = "https://prmr-memory-core.vercel.app"

BOUNDARY = (
    "V0.68.1 is live frontend smoke fix only. It is not hosted backend, not live "
    "API access, not API key issuance, not billing, not production onboarding, "
    "not external validation, not bank approval, not compliance approval, not "
    "legal approval, not external security certification, and not real-world validation."
)

REALISTIC_SECRET_PATTERN = r"(?<![A-Za-z0-9])sk-(?:live|test|proj)?_?[A-Za-z0-9_-]{20,}\b"
OLD_BROAD_PATTERN = r"sk-[A-Za-z0-9_-]+"

OVERCLAIMS = [
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def visible_text(html: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_styles = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_scripts, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def fetch_live_homepage() -> dict[str, Any]:
    try:
        req = request.Request(DEPLOYED_URL, headers={"User-Agent": "PRMR-V0681-Smoke-Fix/1.0"})
        with request.urlopen(req, timeout=20) as response:
            body = response.read(250000).decode("utf-8", errors="replace")
            page_text = visible_text(body)
            broad_hits = sorted(set(re.findall(OLD_BROAD_PATTERN, body, flags=re.IGNORECASE)))
            realistic_hits = sorted(set(re.findall(REALISTIC_SECRET_PATTERN, page_text, flags=re.IGNORECASE)))
            return {
                "available": True,
                "status_code": response.status,
                "old_broad_sk_hits": broad_hits,
                "realistic_secret_hits": realistic_hits,
                "false_positive_assessment": (
                    "old broad pattern matched ordinary page text such as risk-review"
                    if "sk-review" in broad_hits and not realistic_hits
                    else "no old broad sk-review false positive observed"
                ),
            }
    except Exception as exc:  # pragma: no cover - network condition
        return {
            "available": False,
            "error": str(exc),
            "old_broad_sk_hits": [],
            "realistic_secret_hits": [],
            "false_positive_assessment": "live homepage fetch unavailable",
        }


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


def find_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term in lower]


def page_guard_exists(path: Path) -> bool:
    text = read_text(path)
    return "notFound" in text and "isLocalReviewEnabled" in text and "if (!isLocalReviewEnabled())" in text


def write_reports(
    checks: list[dict[str, Any]],
    typecheck: dict[str, Any],
    build: dict[str, Any],
    live_probe: dict[str, Any],
) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    now = datetime.now(timezone.utc).isoformat()

    smoke_payload = {
        "version": "0.68.1",
        "title": "Live Route Smoke Fix",
        "result": result,
        "generated_at": now,
        "route_blocking_fix": {
            "/alpha/review": "source now calls notFound() when local review is not enabled",
            "/book-demo/review": "source now calls notFound() when local review is not enabled",
        },
        "restricted_pattern_finding": {
            "old_pattern": OLD_BROAD_PATTERN,
            "refined_pattern": REALISTIC_SECRET_PATTERN,
            "live_homepage_probe": live_probe,
            "assessment": (
                "The observed sk-review hit is a false positive from ordinary text, not an exposed raw API key."
                if "sk-review" in live_probe.get("old_broad_sk_hits", []) and not live_probe.get("realistic_secret_hits")
                else "No actual raw secret was found by the refined visible-text scan."
            ),
        },
        "boundary": BOUNDARY,
    }
    dump_json(SMOKE_FIX_REPORT, smoke_payload)

    public_payload = {
        "version": "0.68.1",
        "title": "Live Frontend Smoke Fix + Public Route Blocking",
        "result": result,
        "generated_at": now,
        "boundary": BOUNDARY,
        "checks_passed": passed,
        "checks_total": total,
        "route_blocking_fix": {
            "alpha_review_page": "notFound guard in public frontend mode",
            "book_demo_review_page": "notFound guard in public frontend mode",
        },
        "restricted_pattern_finding": {
            "actual_raw_secret_found": bool(live_probe.get("realistic_secret_hits")),
            "false_positive_source": "risk-review text matched the old broad sk-* regex" if "sk-review" in live_probe.get("old_broad_sk_hits", []) else "none observed",
            "scanner_fix": "scan page-visible text/JSON bodies with realistic key-shaped regex while keeping restricted-pattern checks",
        },
        "metadata_copy": "Controlled-alpha frontend for PRMR Memory Core.",
        "frontend_commands": {
            "typecheck": {"command": typecheck["command"], "passed": typecheck["passed"]},
            "build": {"command": build["command"], "passed": build["passed"]},
        },
        "redeploy_required": True,
        "post_redeploy_command": '$env:PRMR_STAGING_DEPLOYMENT_URL="https://prmr-memory-core.vercel.app"; python examples/audit_v068_staging_live_url.py',
    }
    private_payload = {
        **public_payload,
        "title": "Private Live Frontend Smoke Fix Trace",
        "checks": checks,
        "live_homepage_probe": live_probe,
        "typecheck_output_tail": typecheck["output_tail"],
        "build_output_tail": build["output_tail"],
    }
    dump_json(PUBLIC_REPORT, public_payload)
    dump_json(PRIVATE_REPORT, private_payload)


def write_scorecard(checks: list[dict[str, Any]], typecheck: dict[str, Any], build: dict[str, Any]) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.68.1 Live Frontend Smoke Fix Scorecard",
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
            f"- {'PASS' if typecheck['passed'] else 'FAIL'}: {typecheck['command']}",
            f"- {'PASS' if build['passed'] else 'FAIL'}: {build['command']}",
            "- RUN: python examples/audit_v0681_live_frontend_smoke_fix.py",
            "",
            "After redeploy, run:",
            "",
            '$env:PRMR_STAGING_DEPLOYMENT_URL="https://prmr-memory-core.vercel.app"',
            "python examples/audit_v068_staging_live_url.py",
            "",
            BOUNDARY,
            "",
        ]
    )
    SCORECARD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "alpha_review_page_guard_exists", page_guard_exists(ALPHA_REVIEW_PAGE), str(ALPHA_REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "book_demo_review_page_guard_exists", page_guard_exists(BOOK_DEMO_REVIEW_PAGE), str(BOOK_DEMO_REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "local_review_page_routes_use_not_found", "notFound()" in read_text(ALPHA_REVIEW_PAGE) and "notFound()" in read_text(BOOK_DEMO_REVIEW_PAGE), "notFound guards")

    add_check(
        checks,
        "review_apis_still_blocked",
        all("localOnlyRouteDisabledResponse" in read_text(path) and "isLocalReviewEnabled" in read_text(path) for path in API_REVIEW_ROUTES),
        "review APIs use local-only disabled response",
    )
    add_check(
        checks,
        "demo_bridge_apis_still_disabled",
        all("demoBridgeDisabledResponse" in read_text(path) and "isLocalDemoBridgeEnabled" in read_text(path) for path in DEMO_BRIDGE_ROUTES),
        "demo bridge APIs use public disabled response",
    )
    add_check(
        checks,
        "form_apis_still_safe_disabled",
        all("formCaptureDisabledResponse" in read_text(path) and "isLocalFileWritesEnabled" in read_text(path) for path in FORM_ROUTES),
        "form APIs use capture-disabled response",
    )

    v068_text = read_text(V068_AUDIT)
    add_check(checks, "restricted_pattern_scan_still_exists", "restricted_hits" in v068_text and "sk-" in v068_text, "restricted scan present")
    add_check(
        checks,
        "restricted_pattern_scan_refined_for_false_positive",
        "page_visible_text" in v068_text and "{20,}" in v068_text and OLD_BROAD_PATTERN not in v068_text,
        "visible-text scan with realistic key-shaped regex",
    )

    live_probe = fetch_live_homepage()
    add_check(
        checks,
        "no_actual_raw_secret_in_public_visible_output",
        not live_probe.get("realistic_secret_hits"),
        live_probe.get("realistic_secret_hits"),
    )
    add_check(
        checks,
        "documented_sk_review_false_positive",
        "sk-review" in live_probe.get("old_broad_sk_hits", []) and not live_probe.get("realistic_secret_hits"),
        live_probe.get("false_positive_assessment"),
    )

    layout_text = read_text(LAYOUT)
    add_check(
        checks,
        "public_metadata_avoids_local_debug_wording",
        "Controlled-alpha frontend for PRMR Memory Core." in layout_text and "Local controlled-alpha product shell" not in layout_text,
        "metadata description updated",
    )

    public_source = "\n".join(
        read_text(path)
        for path in [LAYOUT, FRONTEND / "app" / "page.tsx", FRONTEND / "components" / "landing" / "HeroSection.tsx"]
        if path.exists()
    )
    add_check(checks, "no_hosted_backend_claims", not find_terms(public_source, ["hosted api is live", "hosted backend is live"]), "none")
    add_check(checks, "no_production_readiness_claims", not find_terms(public_source, ["production-ready", "production ready"]), "none")
    add_check(
        checks,
        "no_approval_or_certification_claims",
        not find_terms(public_source, ["bank-approved", "compliance-certified", "legal-approved", "security-certified", "external certification complete"]),
        "none",
    )
    add_check(checks, "no_punitive_wording", not find_terms(public_source, PUNITIVE_TERMS), "none")

    print("Running frontend typecheck in public frontend mode...")
    typecheck = run_frontend_command(["typecheck"])
    add_check(checks, "npm_run_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-600:] or "ok")

    print("Running frontend build in public frontend mode...")
    build = run_frontend_command(["build"])
    add_check(checks, "npm_run_build_passes", build["passed"], build["output_tail"][-600:] or "ok")

    write_reports(checks, typecheck, build, live_probe)
    public_text = read_text(PUBLIC_REPORT) + "\n" + read_text(SMOKE_FIX_REPORT)
    add_check(checks, "public_reports_have_no_actual_secret_values", not re.search(REALISTIC_SECRET_PATTERN, public_text), "none")
    add_check(checks, "public_reports_have_no_punitive_wording", not find_terms(public_text, PUNITIVE_TERMS), "none")
    add_check(checks, "public_reports_have_no_positive_overclaims", not find_terms(public_text, OVERCLAIMS), "none")

    write_reports(checks, typecheck, build, live_probe)
    write_scorecard(checks, typecheck, build)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.68.1 LIVE FRONTEND SMOKE FIX AUDIT")
    print("------------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Restricted pattern finding:")
    print(f"- old broad hits: {live_probe.get('old_broad_sk_hits')}")
    print(f"- realistic secret hits: {live_probe.get('realistic_secret_hits')}")
    print("Command results:")
    print(f"- npm run typecheck: {'PASS' if typecheck['passed'] else 'FAIL'}")
    print(f"- npm run build: {'PASS' if build['passed'] else 'FAIL'}")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {SMOKE_FIX_REPORT.relative_to(ROOT)}")
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
