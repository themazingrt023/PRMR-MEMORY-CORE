from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v063"

BOOK_PAGE = FRONTEND / "app" / "book-demo" / "page.tsx"
BOOK_FORM = FRONTEND / "components" / "demo" / "BookDemoForm.tsx"
BOOK_ROUTE = FRONTEND / "app" / "api" / "demo" / "book" / "route.ts"
HERO = FRONTEND / "components" / "landing" / "HeroSection.tsx"
ALPHA_NOTICE = FRONTEND / "components" / "alpha" / "ControlledAlphaNotice.tsx"
DEMO_RUNNER = FRONTEND / "components" / "demo" / "LocalDemoRunner.tsx"

LOCAL_STORAGE = REPORT_DIR / "local_demo_requests_v063.json"
PUBLIC_REPORT = REPORT_DIR / "public_book_demo_form_v063.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_book_demo_form_v063.json"
SCORECARD = REPORT_DIR / "scorecard_v063.md"

BOUNDARY = (
    "V0.63 is a local controlled demo request form only. It is not calendar scheduling, "
    "hosted onboarding, billing, live API access, external validation, bank approval, "
    "compliance approval, legal approval, external security certification, or real-world validation."
)

FORM_FIELDS = [
    "name",
    "email",
    "organisation",
    "role",
    "use_case_category",
    "demo_purpose",
    "preferred_date",
    "preferred_time_window",
    "timezone",
    "technical_background",
    "what_they_want_to_see",
]

USE_CASE_CATEGORIES = [
    "AI agent memory",
    "Customer support continuity",
    "SaaS user-history continuity",
    "Education progress continuity",
    "Legal/research case continuity",
    "Fraud/risk sandbox evaluation",
    "Company knowledge continuity",
    "Accelerator / competition review",
    "Technical collaboration",
    "Other",
]

STATUSES = [
    "pending_demo_review",
    "needs_followup",
    "demo_approved",
    "demo_declined",
    "demo_completed",
    "archived",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

EXTERNAL_INTEGRATION_TERMS = [
    "calendly",
    "google calendar",
    "nodemailer",
    "smtp",
    "sendgrid",
    "mailgun",
    "resend",
    "gmail",
    "stripe",
    "salesforce",
    "hubspot",
]

POSITIVE_OVERCLAIMS = [
    r"\bproduction-ready\b",
    r"\bhosted api\b",
    r"\bcalendar event created\b",
    r"\bemail sent\b",
    r"\bapi key issued\b",
    r"\blive access granted\b",
    r"\bbank-approved\b",
    r"\bcompliance-certified\b",
    r"\blegal-approved\b",
    r"\bsecurity-certified\b",
    r"\bexternally certified\b",
    r"\breal-world validated\b",
]


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_json(path: Path) -> dict:
    try:
        return json.loads(read(path))
    except json.JSONDecodeError:
        return {}


def run_command(command: list[str], cwd: Path) -> dict:
    if os.name == "nt" and command and command[0] == "npm":
        command = ["npm.cmd", *command[1:]]
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return {
        "command": " ".join(command),
        "cwd": str(cwd.relative_to(ROOT)),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output_tail": output[-4000:],
    }


def add_check(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def positive_overclaims(text: str) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in POSITIVE_OVERCLAIMS if re.search(pattern, lowered)]


def public_has_personal_details(report: dict) -> bool:
    blob = json.dumps(report, sort_keys=True).lower()
    personal_markers = [
        "local demo tester",
        "tester@example.com",
        "synthetic demo lab",
        "demo_purpose",
        "technical_background",
        "what_they_want_to_see",
        "demo_request_id",
    ]
    return any(marker in blob for marker in personal_markers)


def write_reports(checks: list[dict], command_results: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    storage = load_json(LOCAL_STORAGE)
    requests = storage.get("requests", [])
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    counts = {status: 0 for status in STATUSES}
    for item in requests:
        status = item.get("status")
        if status in counts:
            counts[status] += 1

    public_report = {
        "version": "0.63",
        "title": "Book Demo Form",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "scope": "local controlled demo request capture evidence",
        "total_demo_requests": len(requests),
        "statuses": STATUSES,
        "counts_by_status": counts,
        "safety": {
            "calendar_events_created": 0,
            "emails_sent": 0,
            "api_keys_issued": 0,
            "live_access_granted": False,
            "billing_connected": False,
            "external_services_connected": False,
            "public_report_excludes_personal_details": True,
        },
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
    }

    private_report = {
        **public_report,
        "title": "Book Demo Form Private Local Trace",
        "request_details": requests,
        "checks": checks,
        "command_results": command_results,
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    scorecard = [
        "# V0.63 Book Demo Form Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Checks",
        "",
        *[f"- {'PASS' if check['passed'] else 'NEEDS_WORK'}: {check['name']} - {check['detail']}" for check in checks],
        "",
        "## Command Results",
        "",
        *[
            f"- {'PASS' if item['passed'] else 'NEEDS_WORK'}: {item['command']} in {item['cwd']}"
            for item in command_results
        ],
        "",
        "V0.63 is a local controlled demo request form only. It is not calendar scheduling, hosted onboarding, billing, live API access, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.",
    ]
    SCORECARD.write_text("\n".join(scorecard) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []
    command_results: list[dict] = []

    page_text = read(BOOK_PAGE)
    form_text = read(BOOK_FORM)
    route_text = read(BOOK_ROUTE)
    hero_text = read(HERO)
    alpha_text = read(ALPHA_NOTICE)
    demo_text = read(DEMO_RUNNER)
    storage_text = read(LOCAL_STORAGE)
    combined = "\n".join([page_text, form_text, route_text, hero_text, alpha_text, demo_text, storage_text])

    add_check(checks, "book_demo_route_exists", BOOK_PAGE.exists(), str(BOOK_PAGE.relative_to(ROOT)))
    add_check(checks, "book_demo_form_fields_exist", all(field in form_text and field in route_text for field in FORM_FIELDS), "all required form fields")
    add_check(checks, "boundary_checkboxes_exist", "confirm_controlled_demo_only" in form_text and "confirm_no_sensitive_data" in form_text, "controlled demo and no-sensitive-data confirmations")
    add_check(checks, "api_demo_book_route_exists", BOOK_ROUTE.exists() and "export async function POST" in route_text, str(BOOK_ROUTE.relative_to(ROOT)))
    add_check(checks, "local_storage_exists", LOCAL_STORAGE.exists(), str(LOCAL_STORAGE.relative_to(ROOT)))
    add_check(checks, "request_validation_exists", all(term in route_text for term in ["validation_failed", "invalid_email", "invalid_use_case_category", "invalid_demo_time_preference", "sensitive_data_not_allowed"]), "validation branches")
    add_check(checks, "pending_demo_review_returned", "pending_demo_review" in route_text and "demo_request_status" in route_text, "pending status response")
    add_check(checks, "demo_request_statuses_defined", all(status in route_text + storage_text for status in STATUSES), "status list")
    add_check(checks, "use_case_categories_defined", all(category in form_text and category in route_text for category in USE_CASE_CATEGORIES), "allowed categories")
    add_check(checks, "ctas_added", 'href="/book-demo"' in hero_text and 'href="/book-demo"' in alpha_text and 'href="/book-demo"' in demo_text, "hero/alpha/demo CTAs")
    add_check(checks, "hero_view_local_demo_preserved", 'href="/demo"' in hero_text and "View Local Demo" in hero_text, "hero demo CTA unchanged")
    add_check(checks, "no_calendar_creation", "calendar_event_created: false" in route_text and "calendar_integration_enabled: false" in route_text, "no calendar event creation")
    add_check(checks, "no_email_sending", "email_sent: false" in route_text and "email_sending_enabled: false" in route_text, "no email sending")
    add_check(checks, "no_api_key_issuance", "api_key_issued: false" in route_text and "api_key_issuing_enabled: false" in route_text, "no API key issuing")
    add_check(checks, "no_live_access_granted", "live_access_granted: false" in route_text and "live_access_granting_enabled: false" in route_text, "no live access")
    add_check(checks, "no_billing_integration", "billing_connected: false" in route_text and "billing_enabled: false" in route_text, "no billing")
    add_check(checks, "public_report_avoids_personal_details", not public_has_personal_details(load_json(PUBLIC_REPORT)), "public report excludes request detail fields")
    add_check(checks, "public_boundary_wording_exists", BOUNDARY in read(PUBLIC_REPORT) + route_text + form_text, "boundary present")
    add_check(checks, "no_positive_hosted_or_production_claims", not positive_overclaims(combined), "no positive hosted/production/certification claims")
    add_check(checks, "no_positive_approval_claims", not any(term in combined.lower() for term in ["bank-approved", "compliance-certified", "legal-approved", "security-certified"]), "no positive approval claims")
    add_check(checks, "no_external_certification_claims", not any(term in combined.lower() for term in ["externally certified", "external certification granted"]), "no external certification claim")
    add_check(checks, "no_punitive_wording", not any(term in combined.lower() for term in PUNITIVE_TERMS), "no punitive wording")
    add_check(checks, "frontend_does_not_expose_api_keys", "sk-" not in form_text.lower() and "api_key_" not in form_text.lower(), "frontend has no raw keys")
    add_check(checks, "no_external_integrations", not any(term in route_text.lower() for term in EXTERNAL_INTEGRATION_TERMS), "no external integration packages or calls")

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND)
    command_results.append(typecheck)
    add_check(checks, "npm_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-500:])

    build = run_command(["npm", "run", "build"], FRONTEND)
    command_results.append(build)
    add_check(checks, "npm_build_passes", build["passed"], build["output_tail"][-500:])

    write_reports(checks, command_results)

    public_report_text = read(PUBLIC_REPORT)
    add_check(checks, "public_report_contains_no_personal_details_after_write", not public_has_personal_details(load_json(PUBLIC_REPORT)), "public report remains summary-only")
    add_check(checks, "public_report_contains_no_overclaims", not positive_overclaims(public_report_text), "public report avoids overclaims")

    write_reports(checks, command_results)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.63 BOOK DEMO FORM AUDIT")
    print("-------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print()
    print("Command summary:")
    for item in command_results:
        status = "PASS" if item["passed"] else "NEEDS_WORK"
        print(f"- {item['command']} ({item['cwd']}): {status}")
    print()
    print("Created:")
    print(PUBLIC_REPORT.relative_to(ROOT))
    print(PRIVATE_REPORT.relative_to(ROOT))
    print(SCORECARD.relative_to(ROOT))

    if result != "PASS":
        print()
        print("Failing checks:")
        for check in checks:
            if not check["passed"]:
                print(f"- {check['name']}: {check['detail']}")

    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
