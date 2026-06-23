"""V0.65 domain and deployment preparation audit.

This audit checks that PRMR Memory Core has a clear domain/deployment prep
boundary without claiming a live hosted product, production readiness, billing,
or external validation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports" / "v065"

PUBLIC_REPORT = REPORTS / "public_domain_deployment_prep_v065.json"
PRIVATE_REPORT = REPORTS / "private_internal_domain_deployment_prep_v065.json"
ROUTE_POLICY = REPORTS / "route_policy_v065.json"
SCORECARD = REPORTS / "scorecard_v065.md"
ENV_EXAMPLE = ROOT / ".env.example"

REQUIRED_DOCS = {
    "deployment_prep": DOCS / "deployment_prep_v065.md",
    "environment_boundary": DOCS / "environment_boundary_v065.md",
    "public_private_route_policy": DOCS / "public_private_route_policy_v065.md",
    "secrets_policy": DOCS / "secrets_policy_v065.md",
    "domain_launch_checklist": DOCS / "domain_launch_checklist_v065.md",
}

BOUNDARY = (
    "V0.65 is domain/deployment preparation only. It is not a live deployment, "
    "not a connected domain, not hosted backend, not production onboarding, "
    "not billing, not live API access, not external validation, not bank "
    "approval, not compliance approval, not legal approval, not external "
    "security certification, and not real-world validation."
)

EXPECTED_PUBLIC_SAFE = {
    "/",
    "/demo",
    "/docs",
    "/alpha",
    "/book-demo",
    "/contact",
    "/demo-video",
    "/capabilities/[slug]",
}

EXPECTED_LOCAL_ONLY = {
    "/alpha/review",
    "/book-demo/review",
    "/api/alpha/review",
    "/api/demo/review",
}

EXPECTED_NEEDS_AUTH = {
    "/api/alpha/request",
    "/api/demo/book",
}

EXPECTED_DISABLE = {
    "/api/demo/scenarios",
    "/api/demo/run",
    "/api/demo/report",
    "/api/demo/health",
}

POSITIVE_OVERCLAIMS = [
    "production-ready",
    "production ready",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "externally certified",
    "external certification complete",
    "external validation complete",
    "real-world validated",
    "deployed live",
    "hosted api is live",
    "live api access granted",
    "keys issued",
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
    r"\bdebug_trace\b",
    r"\braw_request\b",
    r"\brequester_email\b",
    r"\brequester_phone\b",
    r"\breviewer_notes\b",
    r"\bsecret_value\b",
    r"\bkey_value\b",
    r"\bfull_api_key\b",
    r"\bprivate_engine_internals\b",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def lowered_blob(paths: list[Path]) -> str:
    chunks = []
    for path in paths:
        if path.exists():
            chunks.append(read_text(path))
    return "\n".join(chunks).lower()


def has_overclaim(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in POSITIVE_OVERCLAIMS if term in lower]


def has_punitive(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in PUNITIVE_TERMS if term in lower]


def public_restricted_hits(text: str) -> list[str]:
    hits = []
    for pattern in PUBLIC_RESTRICTED_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def env_example_is_placeholder_only(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, ".env.example missing"

    text = read_text(path)
    if re.search(r"sk-[A-Za-z0-9_-]+|pk_live_[A-Za-z0-9_-]+|-----BEGIN", text):
        return False, "secret-looking token found"

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        value = value.strip()
        if any(marker in name.upper() for marker in ("SECRET", "TOKEN", "KEY", "DATABASE_URL")):
            if value and value.lower() not in {"false", "true", "python"}:
                return False, f"non-placeholder value for {name}"

    return True, "placeholders only"


def route_set(policy: dict[str, Any], classification: str) -> set[str]:
    return set(policy.get("classifications", {}).get(classification, []))


def route_classification(policy: dict[str, Any], route: str) -> str | None:
    for item in policy.get("routes", []):
        if item.get("route") == route:
            return item.get("classification")
    return None


def write_reports(route_policy: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    public_payload = {
        "version": "0.65",
        "title": "Domain + Deployment Prep",
        "result": "PASS" if all(check["passed"] for check in checks) else "NEEDS_WORK",
        "generated_at": now,
        "purpose": "Prepare a safe future domain launch plan without launching a hosted product.",
        "boundary": BOUNDARY,
        "documents_created": [
            "docs/deployment_prep_v065.md",
            "docs/environment_boundary_v065.md",
            "docs/public_private_route_policy_v065.md",
            "docs/secrets_policy_v065.md",
            "docs/domain_launch_checklist_v065.md",
        ],
        "route_summary": {
            "public_safe_count": len(route_set(route_policy, "public_safe")),
            "local_only_count": len(route_set(route_policy, "local_only")),
            "needs_protection_before_domain_count": len(
                route_set(route_policy, "needs_auth_before_deploy")
            ),
            "disable_before_domain_count": len(route_set(route_policy, "disable_before_deploy")),
            "future_hosted_layer_count": len(route_set(route_policy, "future_hosted_backend")),
        },
        "public_safe_routes": sorted(route_set(route_policy, "public_safe")),
        "restricted_before_domain_routes": sorted(
            route_set(route_policy, "local_only")
            | route_set(route_policy, "needs_auth_before_deploy")
            | route_set(route_policy, "disable_before_deploy")
        ),
        "launch_gates_for_v066": [
            "public domain must expose only public-safe pages",
            "local review consoles must be disabled, removed, or protected",
            "local file-writing routes must not be exposed directly",
            "local demo bridge routes must be disabled or replaced with public-safe static outputs",
            "credentials must never appear in frontend code or public reports",
            "copy must preserve alpha/local evidence boundaries",
        ],
        "frontend_code_changed": False,
        "frontend_verification": {
            "npm_run_typecheck": "not run; frontend code was not changed in V0.65",
            "npm_run_build": "not run; frontend code was not changed in V0.65",
        },
    }

    private_payload = {
        "version": "0.65",
        "title": "Private Domain + Deployment Prep Audit Detail",
        "result": public_payload["result"],
        "generated_at": now,
        "boundary": BOUNDARY,
        "checks": checks,
        "route_policy": route_policy,
        "env_example": str(ENV_EXAMPLE.relative_to(ROOT)),
        "frontend_code_changed": False,
        "frontend_commands": {
            "npm run typecheck": "not run; no frontend code changed",
            "npm run build": "not run; no frontend code changed",
        },
    }

    dump_json(PUBLIC_REPORT, public_payload)
    dump_json(PRIVATE_REPORT, private_payload)


def write_scorecard(checks: list[dict[str, Any]]) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.65 Domain + Deployment Prep Scorecard",
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
            "- NOT RUN: npm run typecheck in frontend; frontend code was not changed.",
            "- NOT RUN: npm run build in frontend; frontend code was not changed.",
            "- RUN: python examples/audit_v065_domain_deployment_prep.py",
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

    policy_exists = ROUTE_POLICY.exists()
    add_check(checks, "route_policy_report_exists", policy_exists, str(ROUTE_POLICY.relative_to(ROOT)))
    route_policy = load_json(ROUTE_POLICY) if policy_exists else {"classifications": {}, "routes": []}

    add_check(
        checks,
        "public_safe_routes_identified",
        EXPECTED_PUBLIC_SAFE.issubset(route_set(route_policy, "public_safe")),
        ", ".join(sorted(route_set(route_policy, "public_safe"))),
    )
    add_check(
        checks,
        "local_only_routes_identified",
        EXPECTED_LOCAL_ONLY.issubset(route_set(route_policy, "local_only")),
        ", ".join(sorted(route_set(route_policy, "local_only"))),
    )
    add_check(
        checks,
        "future_hosted_routes_identified",
        bool(route_set(route_policy, "future_hosted_backend")),
        ", ".join(sorted(route_set(route_policy, "future_hosted_backend"))),
    )

    admin_not_public = all(
        route_classification(route_policy, route) != "public_safe" for route in EXPECTED_LOCAL_ONLY
    )
    add_check(checks, "admin_review_routes_not_public_safe", admin_not_public, "review routes blocked")

    file_write_routes = EXPECTED_LOCAL_ONLY | EXPECTED_NEEDS_AUTH
    file_write_not_public = all(
        route_classification(route_policy, route) != "public_safe" for route in file_write_routes
    )
    add_check(
        checks,
        "file_writing_api_routes_not_public_safe",
        file_write_not_public,
        "file-writing routes require local-only or protected handling",
    )

    disabled_routes_ok = all(
        route_classification(route_policy, route) == "disable_before_deploy"
        for route in EXPECTED_DISABLE
    )
    add_check(
        checks,
        "local_bridge_routes_disable_before_deploy",
        disabled_routes_ok,
        "demo bridge routes are disabled before domain deployment",
    )

    docs_blob = lowered_blob(list(REQUIRED_DOCS.values()))
    add_check(
        checks,
        "secrets_policy_blocks_frontend_secrets",
        "never expose api keys in frontend" in docs_blob
        or "no api keys in frontend" in docs_blob
        or "credentials must never appear in frontend" in docs_blob,
        "frontend credentials are forbidden",
    )

    env_ok, env_detail = env_example_is_placeholder_only(ENV_EXAMPLE)
    add_check(checks, "env_example_placeholders_only", env_ok, env_detail)

    doc_overclaims = has_overclaim(docs_blob)
    add_check(
        checks,
        "docs_have_no_positive_hosted_or_production_claims",
        not doc_overclaims,
        "none" if not doc_overclaims else ", ".join(doc_overclaims),
    )

    doc_punitive = has_punitive(docs_blob)
    add_check(
        checks,
        "docs_have_no_punitive_wording",
        not doc_punitive,
        "none" if not doc_punitive else ", ".join(doc_punitive),
    )

    add_check(
        checks,
        "frontend_typecheck_not_required",
        True,
        "frontend code was not changed in V0.65",
    )
    add_check(
        checks,
        "frontend_build_not_required",
        True,
        "frontend code was not changed in V0.65",
    )

    write_reports(route_policy, checks)

    public_text = read_text(PUBLIC_REPORT)
    public_hits = public_restricted_hits(public_text)
    add_check(
        checks,
        "public_report_contains_no_private_request_details_or_secrets",
        not public_hits,
        "none" if not public_hits else ", ".join(public_hits),
    )

    public_overclaims = has_overclaim(public_text)
    add_check(
        checks,
        "public_report_contains_no_positive_overclaims",
        not public_overclaims,
        "none" if not public_overclaims else ", ".join(public_overclaims),
    )

    public_punitive = has_punitive(public_text)
    add_check(
        checks,
        "public_report_uses_non_punitive_wording",
        not public_punitive,
        "none" if not public_punitive else ", ".join(public_punitive),
    )

    write_reports(route_policy, checks)
    write_scorecard(checks)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.65 DOMAIN + DEPLOYMENT PREP AUDIT")
    print("-----------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print("Frontend commands:")
    print("- npm run typecheck: NOT RUN (frontend code was not changed)")
    print("- npm run build: NOT RUN (frontend code was not changed)")
    print("Reports:")
    print(f"- {PUBLIC_REPORT.relative_to(ROOT)}")
    print(f"- {PRIVATE_REPORT.relative_to(ROOT)}")
    print(f"- {ROUTE_POLICY.relative_to(ROOT)}")
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
