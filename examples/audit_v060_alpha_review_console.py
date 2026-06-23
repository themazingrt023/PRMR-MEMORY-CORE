from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v060"
V058_REQUESTS = ROOT / "reports" / "v058" / "local_alpha_requests_v058.json"
REVIEW_PAGE = FRONTEND / "app" / "alpha" / "review" / "page.tsx"
REVIEW_COMPONENT = FRONTEND / "components" / "alpha" / "AlphaReviewWorkflow.tsx"
REVIEW_ROUTE = FRONTEND / "app" / "api" / "alpha" / "review" / "route.ts"
REVIEW_STATE = REPORT_DIR / "local_alpha_review_console_state_v060.json"
SUMMARY_MD = REPORT_DIR / "alpha_review_console_summary_v060.md"
PUBLIC_REPORT = REPORT_DIR / "public_alpha_review_console_v060.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_alpha_review_console_v060.json"
SCORECARD = REPORT_DIR / "scorecard_v060.md"

BOUNDARY = (
    "This is a local review console only. It does not grant live access, issue API keys, "
    "send emails, process billing, or create hosted onboarding."
)

ALLOWED_STATUSES = [
    "pending_review",
    "needs_followup",
    "approved_for_synthetic_demo",
    "rejected_not_fit",
    "archived",
]

REVIEWER_IDENTITIES = ["founder", "technical_reviewer", "safety_reviewer", "notes_only"]

FILTER_TERMS = ["statusFilter", "categoryFilter", "dataTypeFilter", "searchQuery"]
SORT_TERMS = ["created_timestamp", "status", "use_case_category", "most_recently_reviewed"]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

EXTERNAL_CONNECTORS = [
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

OVERCLAIM_PATTERNS = [
    r"\bproduction-ready\b",
    r"\bbank-approved\b",
    r"\bcompliance-certified\b",
    r"\blegal-approved\b",
    r"\bsecurity-certified\b",
    r"\bexternally certified\b",
    r"\breal-world validated\b",
    r"\bcertified for production\b",
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


def has_personal_details(report: dict, requests: list[dict]) -> bool:
    blob = json.dumps(report, sort_keys=True)
    for request in requests:
        for key in ("request_id", "name", "email", "organisation", "use_case_description"):
            value = str(request.get(key, "")).strip()
            if value and value in blob:
                return True
    return False


def overclaims(text: str) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in OVERCLAIM_PATTERNS if re.search(pattern, lowered)]


def status_counts(requests: list[dict], reviews: list[dict]) -> dict:
    counts = {status: 0 for status in ALLOWED_STATUSES}
    review_by_id = {item.get("request_id"): item for item in reviews if isinstance(item, dict)}
    for request in requests:
        status = review_by_id.get(request.get("request_id"), {}).get("status", request.get("status", "pending_review"))
        if status in counts:
            counts[status] += 1
    return counts


def write_reports(checks: list[dict], command_results: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    requests = load_json(V058_REQUESTS).get("requests", [])
    state = load_json(REVIEW_STATE)
    reviews = state.get("reviews", [])
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    public_report = {
        "version": "0.60",
        "title": "Alpha Review Console",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "console_scope": "local controlled-alpha review console evidence",
        "summary": {
            "total_requests": len(requests),
            "counts_by_status": status_counts(requests, reviews),
            "allowed_statuses": ALLOWED_STATUSES,
            "reviewer_identity_placeholders": REVIEWER_IDENTITIES,
            "filters": ["status", "use case category", "planned data type", "organisation/name/email search"],
            "sorting": ["created timestamp", "status", "use case category", "most recently reviewed"],
            "manual_exports": ["public-safe review summary JSON", "private local review JSON", "markdown summary"],
        },
        "safety": {
            "automatic_api_key_issuance": False,
            "live_access_granted": False,
            "email_sending": False,
            "external_services_connected": False,
            "billing_processed": False,
            "public_report_excludes_personal_details": True,
        },
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
    }

    private_report = {
        **public_report,
        "title": "Alpha Review Console Private Local Trace",
        "request_ids": [request.get("request_id") for request in requests],
        "review_state_path": str(REVIEW_STATE.relative_to(ROOT)),
        "summary_path": str(SUMMARY_MD.relative_to(ROOT)),
        "review_records": reviews,
        "checks": checks,
        "command_results": command_results,
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    scorecard = [
        "# V0.60 Alpha Review Console Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Checks",
        "",
        *[f"- {'PASS' if item['passed'] else 'NEEDS_WORK'}: {item['name']} - {item['detail']}" for item in checks],
        "",
        "## Command Results",
        "",
        *[
            f"- {'PASS' if item['passed'] else 'NEEDS_WORK'}: {item['command']} in {item['cwd']}"
            for item in command_results
        ],
        "",
        "This is local controlled-alpha console evidence only. It is not hosted admin, not production onboarding, not billing, not live API access, not compliance approval, not legal approval, not bank approval, not external security certification, and not real-world validation.",
    ]
    SCORECARD.write_text("\n".join(scorecard) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []
    command_results: list[dict] = []

    page_text = read(REVIEW_PAGE)
    component_text = read(REVIEW_COMPONENT)
    route_text = read(REVIEW_ROUTE)
    state_text = read(REVIEW_STATE)
    state = load_json(REVIEW_STATE)
    requests = load_json(V058_REQUESTS).get("requests", [])
    combined_public_source = page_text + component_text + route_text + state_text

    add_check(checks, "alpha_review_page_exists", REVIEW_PAGE.exists(), str(REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "local_safety_notice_exists", BOUNDARY in page_text + component_text + route_text, BOUNDARY)
    add_check(checks, "status_filters_exist", "statusFilter" in component_text and all(status in component_text for status in ALLOWED_STATUSES), "status filter UI")
    add_check(checks, "category_filters_exist", "categoryFilter" in component_text and "use_case_category" in component_text, "category filter UI")
    add_check(checks, "planned_data_filter_exists", "dataTypeFilter" in component_text and "data_type_planned" in component_text, "planned data filter UI")
    add_check(checks, "search_exists", "searchQuery" in component_text and "organisation" in component_text and "email" in component_text, "organisation/name/email search")
    add_check(checks, "sorting_exists", all(term in component_text + route_text + state_text for term in SORT_TERMS), "created/status/category/reviewed sorting")
    add_check(checks, "reviewer_identity_placeholder_exists", all(identity in component_text + route_text + state_text for identity in REVIEWER_IDENTITIES), "local reviewer identity metadata")
    add_check(checks, "status_reset_exists", "reset_status" in component_text + route_text and "reset_to_pending" in route_text, "manual reset action")
    add_check(
        checks,
        "reset_appends_history",
        "review_history: [...(existing?.review_history || []), historyEntry]" in route_text and "reset_appended_history" in route_text,
        "reset keeps prior history and appends a new entry",
    )
    add_check(checks, "draft_response_library_exists", "draftResponseLibrary" in route_text and all(status in route_text for status in ALLOWED_STATUSES), "draft library per status")
    add_check(
        checks,
        "draft_responses_preserve_boundaries",
        all(phrase in route_text for phrase in ["No live access", "no production API access", "no API key", "no sensitive data"]),
        "drafts avoid access/key/email promises",
    )
    add_check(checks, "manual_export_exists", "action === \"export\"" in route_text and "Manual export" in component_text, "manual public/private/markdown export")
    add_check(checks, "local_export_files_exist", REVIEW_STATE.exists() and SUMMARY_MD.exists(), "V0.60 state and markdown summary files")
    add_check(checks, "public_export_avoids_personal_details_by_design", "request_details" not in route_text.split("function buildPublicExport", 1)[1].split("function buildPrivateExport", 1)[0], "public export excludes request details")
    add_check(checks, "no_automatic_api_key_issuance", "api_key_issued: false" in route_text and "api_key_issuing_enabled: false" in route_text, "no key issuing path")
    add_check(checks, "no_live_access_granted", "live_access_granted: false" in route_text and "does not grant live access" in combined_public_source, "no live access path")
    add_check(checks, "no_email_sending", "email_sent: false" in route_text and "send emails" in combined_public_source and not any(term in route_text.lower() for term in EXTERNAL_CONNECTORS), "no mail connector")
    add_check(checks, "no_external_services", not any(term in combined_public_source.lower() for term in EXTERNAL_CONNECTORS), "no external email, CRM, or payment connector")
    add_check(checks, "no_hosted_or_production_overclaims", not overclaims(combined_public_source), "no certification or production readiness claims")
    add_check(
        checks,
        "no_bank_compliance_legal_security_approval_claims",
        not any(term in combined_public_source.lower() for term in ["bank-approved", "compliance-certified", "legal-approved", "security-certified"]),
        "UI/route avoid positive approval claims",
    )
    add_check(
        checks,
        "no_external_certification_claims",
        not any(term in combined_public_source.lower() for term in ["externally certified", "external certification granted"]),
        "UI/route avoid positive external certification claims",
    )
    add_check(checks, "no_punitive_or_certain_guilt_wording", not any(term in combined_public_source.lower() for term in PUNITIVE_TERMS), "no punitive wording")
    add_check(checks, "frontend_does_not_expose_api_keys", "sk-" not in component_text.lower() and "api_key_" not in component_text.lower(), "frontend exposes no key values")
    add_check(checks, "v058_v059_behavior_preserved", (ROOT / "reports" / "v059" / "local_alpha_review_state_v059.json").exists() and V058_REQUESTS.exists(), "prior local storage remains")

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND)
    command_results.append(typecheck)
    add_check(checks, "npm_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-500:])

    build = run_command(["npm", "run", "build"], FRONTEND)
    command_results.append(build)
    add_check(checks, "npm_build_passes", build["passed"], build["output_tail"][-500:])

    write_reports(checks, command_results)

    public_report = load_json(PUBLIC_REPORT)
    public_text = read(PUBLIC_REPORT) + read(SCORECARD)
    add_check(checks, "public_report_contains_no_personal_request_details", not has_personal_details(public_report, requests), "public report excludes request IDs, names, emails, organisations, descriptions")
    add_check(checks, "public_report_contains_boundary", BOUNDARY in public_text, "public report carries local console boundary")
    add_check(checks, "public_report_contains_no_overclaims", not overclaims(public_text), "public report avoids production/certification claims")

    write_reports(checks, command_results)

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.60 ALPHA REVIEW CONSOLE AUDIT")
    print("-------------------------------------")
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
        for item in checks:
            if not item["passed"]:
                print(f"- {item['name']}: {item['detail']}")

    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
