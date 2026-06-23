from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v059"
V058_REQUESTS = ROOT / "reports" / "v058" / "local_alpha_requests_v058.json"
REVIEW_PAGE = FRONTEND / "app" / "alpha" / "review" / "page.tsx"
REVIEW_COMPONENT = FRONTEND / "components" / "alpha" / "AlphaReviewWorkflow.tsx"
REVIEW_ROUTE = FRONTEND / "app" / "api" / "alpha" / "review" / "route.ts"
REQUEST_ROUTE = FRONTEND / "app" / "api" / "alpha" / "request" / "route.ts"
REVIEW_STATE = REPORT_DIR / "local_alpha_review_state_v059.json"
SUMMARY_MD = REPORT_DIR / "alpha_review_summary_v059.md"
PUBLIC_REPORT = REPORT_DIR / "public_alpha_review_workflow_v059.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_alpha_review_workflow_v059.json"
SCORECARD = REPORT_DIR / "scorecard_v059.md"

BOUNDARY = (
    "This is a local review workflow only. No live access, billing, production API keys, "
    "or hosted onboarding are granted here."
)

ALLOWED_STATUSES = [
    "pending_review",
    "needs_followup",
    "approved_for_synthetic_demo",
    "rejected_not_fit",
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

FORBIDDEN_EXTERNAL_CONNECTORS = [
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

POSITIVE_CLAIM_PATTERNS = [
    r"\bhosted admin dashboard\b",
    r"\bproduction onboarding\b",
    r"\bproduction-ready\b",
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


def public_report_has_personal_details(report: dict, requests: list[dict]) -> bool:
    blob = json.dumps(report, sort_keys=True)
    for request in requests:
        for key in ("request_id", "name", "email", "organisation"):
            value = str(request.get(key, "")).strip()
            if value and value in blob:
                return True
    return False


def has_positive_claims(text: str) -> list[str]:
    lowered = text.lower()
    matches = []
    for pattern in POSITIVE_CLAIM_PATTERNS:
        if re.search(pattern, lowered):
            matches.append(pattern)
    return matches


def write_reports(checks: list[dict], command_results: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    requests = load_json(V058_REQUESTS).get("requests", [])
    review_state = load_json(REVIEW_STATE)
    reviews = review_state.get("reviews", [])
    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    status_counts = {status: 0 for status in ALLOWED_STATUSES}
    review_by_id = {item.get("request_id"): item for item in reviews if isinstance(item, dict)}
    for request in requests:
      status = review_by_id.get(request.get("request_id"), {}).get("status", request.get("status", "pending_review"))
      if status in status_counts:
          status_counts[status] += 1

    public_report = {
        "version": "0.59",
        "title": "Alpha Review Workflow",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "workflow": {
            "scope": "local controlled-alpha review workflow",
            "automatic_access_granted": False,
            "live_access_granted": False,
            "api_keys_issued": 0,
            "emails_sent": 0,
            "external_services_connected": False,
            "request_details_excluded": True,
        },
        "request_summary": {
            "total_requests": len(requests),
            "statuses_available": ALLOWED_STATUSES,
            "counts_by_status": status_counts,
        },
        "checks": [{"name": item["name"], "passed": item["passed"]} for item in checks],
    }

    private_report = {
        **public_report,
        "title": "Alpha Review Workflow Private Trace",
        "request_ids": [request.get("request_id") for request in requests],
        "review_state_path": str(REVIEW_STATE.relative_to(ROOT)),
        "summary_path": str(SUMMARY_MD.relative_to(ROOT)),
        "checks": checks,
        "command_results": command_results,
        "review_records": reviews,
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    score_lines = [
        "# V0.59 Alpha Review Workflow Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        f"Boundary: {BOUNDARY}",
        "",
        "## Review Statuses",
        "",
        *[f"- {status}" for status in ALLOWED_STATUSES],
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
        "This is local controlled-alpha workflow evidence only. It does not grant live access, billing, production API keys, hosted onboarding, bank approval, compliance approval, legal approval, external security certification, or real-world validation.",
    ]
    SCORECARD.write_text("\n".join(score_lines) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []
    command_results: list[dict] = []

    page_text = read(REVIEW_PAGE)
    component_text = read(REVIEW_COMPONENT)
    route_text = read(REVIEW_ROUTE)
    request_route_text = read(REQUEST_ROUTE)
    state = load_json(REVIEW_STATE)
    requests = load_json(V058_REQUESTS).get("requests", [])

    add_check(checks, "alpha_review_page_exists", REVIEW_PAGE.exists(), str(REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "v058_local_request_storage_exists", V058_REQUESTS.exists(), str(V058_REQUESTS.relative_to(ROOT)))
    add_check(
        checks,
        "allowed_statuses_defined",
        all(status in page_text + component_text + route_text + json.dumps(state) for status in ALLOWED_STATUSES),
        ", ".join(ALLOWED_STATUSES),
    )
    add_check(
        checks,
        "status_update_path_exists",
        REVIEW_ROUTE.exists() and "export async function POST" in route_text and "/api/alpha/review" in component_text,
        "local POST route plus client caller",
    )
    add_check(
        checks,
        "reviewer_notes_supported",
        "reviewer_notes" in route_text and "Reviewer notes" in component_text,
        "notes stored in local review state",
    )
    add_check(
        checks,
        "review_history_supported",
        "review_history" in route_text and "Review history entries" in component_text,
        "history appended per local update",
    )
    add_check(
        checks,
        "draft_response_generation_exists",
        "draftResponseFor" in route_text and "needs_followup" in route_text and "approved_for_synthetic_demo" in route_text,
        "status-specific local draft responses",
    )
    add_check(
        checks,
        "no_actual_email_sending",
        "email_sent: false" in route_text and not any(term in route_text.lower() for term in FORBIDDEN_EXTERNAL_CONNECTORS),
        "no mail connector or send path",
    )
    add_check(
        checks,
        "no_automatic_api_key_issuing",
        "api_key_issued: false" in route_text
        and "api_key_issuing_enabled: false" in route_text
        and "automatic_access_granted: false" in route_text,
        "updates never issue access credentials",
    )
    add_check(
        checks,
        "no_live_access_granted",
        "live_access_granted: false" in route_text and "No live access" in page_text + route_text,
        "review states are not live access states",
    )
    add_check(
        checks,
        "local_export_files_exist",
        REVIEW_STATE.exists() and SUMMARY_MD.exists(),
        "local JSON state and markdown summary",
    )
    add_check(
        checks,
        "boundary_wording_present",
        BOUNDARY in page_text and BOUNDARY in route_text and BOUNDARY in json.dumps(state),
        "required V0.59 boundary appears in page, route, and local state",
    )
    add_check(
        checks,
        "no_external_service_connectors",
        not any(term in (route_text + component_text + page_text).lower() for term in FORBIDDEN_EXTERNAL_CONNECTORS),
        "no email, CRM, or payment connector terms",
    )
    add_check(
        checks,
        "no_punitive_or_certain_guilt_wording",
        not any(term in (route_text + component_text + page_text).lower() for term in PUNITIVE_TERMS),
        "public-facing review UI avoids punitive wording",
    )
    add_check(
        checks,
        "frontend_does_not_expose_api_keys",
        "real_credential" not in component_text.lower() and "sk-" not in component_text.lower(),
        "frontend has no raw keys or credential values",
    )
    add_check(
        checks,
        "v058_request_pipeline_preserved",
        REQUEST_ROUTE.exists() and "pending_review" in request_route_text and "api_key_issued: false" in request_route_text,
        "V0.58 request route still exists and keeps pending review semantics",
    )

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND)
    command_results.append(typecheck)
    add_check(checks, "npm_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-500:])

    build = run_command(["npm", "run", "build"], FRONTEND)
    command_results.append(build)
    add_check(checks, "npm_build_passes", build["passed"], build["output_tail"][-500:])

    write_reports(checks, command_results)

    public_report = load_json(PUBLIC_REPORT)
    public_text = read(PUBLIC_REPORT) + read(SCORECARD)
    add_check(
        checks,
        "public_report_contains_no_personal_request_details",
        not public_report_has_personal_details(public_report, requests),
        "public report keeps request details out",
    )
    add_check(
        checks,
        "public_report_contains_no_positive_overclaims",
        not has_positive_claims(public_text),
        "public report uses boundary wording without certification or hosted claims",
    )

    write_reports(checks, command_results)

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.59 ALPHA REVIEW WORKFLOW AUDIT")
    print("--------------------------------------")
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
