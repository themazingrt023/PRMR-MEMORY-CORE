from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v064"

REVIEW_PAGE = FRONTEND / "app" / "book-demo" / "review" / "page.tsx"
REVIEW_COMPONENT = FRONTEND / "components" / "demo" / "DemoReviewWorkflow.tsx"
REVIEW_ROUTE = FRONTEND / "app" / "api" / "demo" / "review" / "route.ts"
V063_STORAGE = ROOT / "reports" / "v063" / "local_demo_requests_v063.json"
STATE = REPORT_DIR / "local_demo_review_state_v064.json"
PUBLIC_REPORT = REPORT_DIR / "public_demo_review_flow_v064.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_demo_review_flow_v064.json"
SUMMARY = REPORT_DIR / "demo_review_summary_v064.md"
SCORECARD = REPORT_DIR / "scorecard_v064.md"

BOUNDARY = (
    "V0.64 is a local demo scheduling/review workflow only. It is not calendar integration, "
    "automatic email sending, hosted onboarding, billing, live API access, external validation, "
    "bank approval, compliance approval, legal approval, external security certification, or real-world validation."
)

STATUSES = [
    "pending_demo_review",
    "needs_followup",
    "demo_approved",
    "demo_declined",
    "demo_scheduled_manually",
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

EXTERNAL_TERMS = [
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
    return any(
        marker in blob
        for marker in [
            "local demo tester",
            "demo.tester@example.com",
            "synthetic demo lab",
            "demo_purpose",
            "technical_background",
            "what_they_want_to_see",
            "demo_request_id",
        ]
    )


def status_counts(requests: list[dict], reviews: list[dict]) -> dict:
    counts = {status: 0 for status in STATUSES}
    by_id = {item.get("demo_request_id"): item for item in reviews if isinstance(item, dict)}
    for request in requests:
        status = by_id.get(request.get("demo_request_id"), {}).get("status", request.get("status", "pending_demo_review"))
        if status in counts:
            counts[status] += 1
    return counts


def write_reports(checks: list[dict], command_results: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    requests = load_json(V063_STORAGE).get("requests", [])
    reviews = load_json(STATE).get("reviews", [])
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    public_report = {
        "version": "0.64",
        "title": "Demo Scheduling / Review Flow",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "scope": "local manual demo review workflow evidence",
        "total_demo_requests": len(requests),
        "statuses": STATUSES,
        "counts_by_status": status_counts(requests, reviews),
        "safety": {
            "calendar_events_created": 0,
            "emails_sent": 0,
            "api_keys_issued": 0,
            "live_access_granted": False,
            "billing_connected": False,
            "public_report_excludes_personal_details": True,
        },
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
    }

    private_report = {
        **public_report,
        "title": "Demo Scheduling / Review Flow Private Local Trace",
        "request_details": requests,
        "review_records": reviews,
        "checks": checks,
        "command_results": command_results,
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    scorecard = [
        "# V0.64 Demo Scheduling / Review Flow Scorecard",
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
        "V0.64 is a local demo scheduling/review workflow only. It is not calendar integration, not automatic email sending, not hosted onboarding, not billing, not live API access, not external validation, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.",
    ]
    SCORECARD.write_text("\n".join(scorecard) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []
    command_results: list[dict] = []

    page_text = read(REVIEW_PAGE)
    component_text = read(REVIEW_COMPONENT)
    route_text = read(REVIEW_ROUTE)
    state_text = read(STATE)
    public_text = read(PUBLIC_REPORT)
    combined = "\n".join([page_text, component_text, route_text, state_text])

    add_check(checks, "book_demo_review_route_exists", REVIEW_PAGE.exists(), str(REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "api_demo_review_route_exists", REVIEW_ROUTE.exists() and "export async function POST" in route_text, str(REVIEW_ROUTE.relative_to(ROOT)))
    add_check(checks, "v063_local_demo_request_storage_exists", V063_STORAGE.exists(), str(V063_STORAGE.relative_to(ROOT)))
    add_check(checks, "required_statuses_defined", all(status in route_text + component_text + state_text for status in STATUSES), "required statuses")
    add_check(checks, "filtering_exists", all(term in component_text for term in ["statusFilter", "categoryFilter", "timezoneFilter", "searchQuery"]), "status/category/timezone/search filters")
    add_check(checks, "sorting_exists", all(term in component_text for term in ["created_timestamp", "preferred_date", "status", "use_case_category", "most_recently_reviewed"]), "sort modes")
    add_check(checks, "reviewer_notes_supported", "reviewer_notes" in route_text and "Reviewer notes" in component_text, "reviewer notes")
    add_check(checks, "manual_scheduling_notes_supported", "manual_scheduling_notes" in route_text and "Manual scheduling notes" in component_text, "manual scheduling notes")
    add_check(checks, "proposed_demo_slot_supported", "proposed_demo_slot" in route_text and "Proposed demo slot" in component_text, "proposed slot")
    add_check(checks, "review_history_supported", "review_history" in route_text and "review_history_count" in component_text + route_text, "history append")
    add_check(checks, "draft_response_library_exists", "draftResponseLibrary" in route_text and all(status in route_text for status in STATUSES), "drafts")
    add_check(checks, "draft_boundaries_exist", all(term in route_text for term in ["No live API access", "no API key", "no production access", "no calendar invite", "not sent automatically"]), "draft boundaries")
    add_check(checks, "local_review_state_exists", STATE.exists(), str(STATE.relative_to(ROOT)))
    add_check(checks, "public_safe_export_exists", PUBLIC_REPORT.exists(), str(PUBLIC_REPORT.relative_to(ROOT)))
    add_check(checks, "private_local_export_exists", PRIVATE_REPORT.exists(), str(PRIVATE_REPORT.relative_to(ROOT)))
    add_check(checks, "markdown_summary_exists", SUMMARY.exists(), str(SUMMARY.relative_to(ROOT)))
    add_check(checks, "no_calendar_creation", "calendar_event_created: false" in route_text and "calendar_integration_enabled: false" in route_text, "no calendar events")
    add_check(checks, "no_email_sending", "email_sent: false" in route_text and "email_sending_enabled: false" in route_text, "no email")
    add_check(checks, "no_api_key_issuance", "api_key_issued: false" in route_text and "api_key_issuing_enabled: false" in route_text, "no keys")
    add_check(checks, "no_live_access_granted", "live_access_granted: false" in route_text and "live_access_granting_enabled: false" in route_text, "no live access")
    add_check(checks, "no_billing_integration", "billing_connected: false" in route_text and "billing_enabled: false" in route_text, "no billing")
    add_check(checks, "public_report_avoids_personal_details", not public_has_personal_details(load_json(PUBLIC_REPORT)), "public summary only")
    add_check(checks, "public_boundary_wording_exists", BOUNDARY in public_text + route_text + page_text, "boundary")
    add_check(checks, "no_positive_hosted_or_production_claims", not positive_overclaims(combined), "no positive overclaims")
    add_check(checks, "no_positive_approval_claims", not any(term in combined.lower() for term in ["bank-approved", "compliance-certified", "legal-approved", "security-certified"]), "no positive approval claims")
    add_check(checks, "no_external_certification_claims", not any(term in combined.lower() for term in ["externally certified", "external certification granted"]), "no external certification")
    add_check(checks, "no_punitive_wording", not any(term in combined.lower() for term in PUNITIVE_TERMS), "no punitive wording")
    add_check(checks, "frontend_does_not_expose_api_keys", "sk-" not in component_text.lower() and "api_key_" not in component_text.lower(), "no key values")
    add_check(checks, "no_external_integrations", not any(term in route_text.lower() for term in EXTERNAL_TERMS), "no external connectors")

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND)
    command_results.append(typecheck)
    add_check(checks, "npm_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-500:])

    build = run_command(["npm", "run", "build"], FRONTEND)
    command_results.append(build)
    add_check(checks, "npm_build_passes", build["passed"], build["output_tail"][-500:])

    write_reports(checks, command_results)

    add_check(checks, "public_report_contains_no_personal_details_after_write", not public_has_personal_details(load_json(PUBLIC_REPORT)), "public report remains summary-only")
    add_check(checks, "public_report_contains_no_overclaims", not positive_overclaims(read(PUBLIC_REPORT)), "public report avoids overclaims")

    write_reports(checks, command_results)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.64 DEMO SCHEDULING / REVIEW AUDIT")
    print("-----------------------------------------")
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
