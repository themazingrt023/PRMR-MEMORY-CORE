from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
REPORT_DIR = ROOT / "reports" / "v061"
V058_REQUESTS = ROOT / "reports" / "v058" / "local_alpha_requests_v058.json"
V060_STATE = ROOT / "reports" / "v060" / "local_alpha_review_console_state_v060.json"
REVIEW_PAGE = FRONTEND / "app" / "alpha" / "review" / "page.tsx"
REVIEW_COMPONENT = FRONTEND / "components" / "alpha" / "AlphaReviewWorkflow.tsx"
REVIEW_ROUTE = FRONTEND / "app" / "api" / "alpha" / "review" / "route.ts"
REVIEW_STATE = REPORT_DIR / "local_alpha_review_ux_state_v061.json"
SUMMARY_MD = REPORT_DIR / "alpha_review_ux_export_summary_v061.md"
PUBLIC_SAFE_EXPORT = REPORT_DIR / "public_safe_alpha_review_export_v061.json"
PRIVATE_LOCAL_EXPORT = REPORT_DIR / "private_local_alpha_review_export_v061.json"
PUBLIC_REPORT = REPORT_DIR / "public_alpha_review_ux_export_v061.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_alpha_review_ux_export_v061.json"
SCORECARD = REPORT_DIR / "scorecard_v061.md"

BOUNDARY = (
    "This is a local review console only. It does not grant live access, issue API keys, "
    "send emails, process billing, or create hosted onboarding."
)

STATUSES = [
    "pending_review",
    "needs_followup",
    "approved_for_synthetic_demo",
    "rejected_not_fit",
    "archived",
]

REVIEWER_IDENTITIES = ["founder", "technical_reviewer", "safety_reviewer", "notes_only"]

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

POSITIVE_OVERCLAIMS = [
    r"\bproduction-ready\b",
    r"\bbank-approved\b",
    r"\bcompliance-certified\b",
    r"\blegal-approved\b",
    r"\bsecurity-certified\b",
    r"\bexternally certified\b",
    r"\breal-world validated\b",
    r"\bcertified for production\b",
    r"\blive api access granted\b",
    r"\bapi key issued\b",
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


def public_has_personal_details(report: dict, requests: list[dict]) -> bool:
    blob = json.dumps(report, sort_keys=True)
    for request in requests:
        for key in ("request_id", "name", "email", "organisation", "use_case_description"):
            value = str(request.get(key, "")).strip()
            if value and value in blob:
                return True
    return False


def status_counts(requests: list[dict], reviews: list[dict]) -> dict:
    counts = {status: 0 for status in STATUSES}
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
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    public_report = {
        "version": "0.61",
        "title": "Alpha Review UX + Export Hardening",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "scope": "local alpha review UX/export hardening evidence",
        "summary": {
            "total_requests": len(requests),
            "counts_by_status": status_counts(requests, reviews),
            "status_confirmation": "UI requires CONFIRM for reset, archive, and not-fit changes.",
            "exports": {
                "public_safe_json": "reports/v061/public_safe_alpha_review_export_v061.json",
                "private_local_json": "reports/v061/private_local_alpha_review_export_v061.json",
                "markdown_summary": "reports/v061/alpha_review_ux_export_summary_v061.md",
            },
            "reviewer_identity_placeholders": REVIEWER_IDENTITIES,
            "lock_policy": "Simple local lock file and atomic rename; not database locking or hosted multi-user admin security.",
            "local_vs_hosted_admin_boundary": "Future hosted admin would need auth, database, permissions, audit logs, encryption, and deployment security.",
        },
        "safety": {
            "api_keys_issued": 0,
            "live_access_granted": False,
            "emails_sent": 0,
            "external_services_connected": False,
            "billing_processed": False,
            "public_report_excludes_personal_details": True,
        },
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
    }

    private_report = {
        **public_report,
        "title": "Alpha Review UX + Export Private Local Trace",
        "request_ids": [request.get("request_id") for request in requests],
        "review_state_path": str(REVIEW_STATE.relative_to(ROOT)),
        "public_safe_export_path": str(PUBLIC_SAFE_EXPORT.relative_to(ROOT)),
        "private_local_export_path": str(PRIVATE_LOCAL_EXPORT.relative_to(ROOT)),
        "summary_path": str(SUMMARY_MD.relative_to(ROOT)),
        "review_records": reviews,
        "checks": checks,
        "command_results": command_results,
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    scorecard = [
        "# V0.61 Alpha Review UX + Export Hardening Scorecard",
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
        "V0.61 is local alpha review UX/export hardening only. It is not hosted admin, not production onboarding, not billing, not live API access, not compliance approval, not legal approval, not bank approval, not external security certification, and not real-world validation.",
    ]
    SCORECARD.write_text("\n".join(scorecard) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []
    command_results: list[dict] = []

    page_text = read(REVIEW_PAGE)
    component_text = read(REVIEW_COMPONENT)
    route_text = read(REVIEW_ROUTE)
    state_text = read(REVIEW_STATE)
    summary_text = read(SUMMARY_MD)
    requests = load_json(V058_REQUESTS).get("requests", [])
    combined = page_text + component_text + route_text + state_text + summary_text

    add_check(checks, "alpha_review_page_exists", REVIEW_PAGE.exists(), str(REVIEW_PAGE.relative_to(ROOT)))
    add_check(checks, "ux_polish_markers_exist", all(term in component_text for term in ["Review controls", "History timeline", "Draft response preview", "Manual export area"]), "clearer filter/history/draft/export sections")
    add_check(checks, "status_change_confirmation_exists", "pendingConfirmation" in component_text and "Type CONFIRM" in component_text and "Confirm local change" in component_text, "local confirmation step")
    add_check(checks, "export_buttons_or_actions_exist", all(term in component_text for term in ["public_safe_json", "private_local_json", "markdown_summary"]), "three export buttons")
    add_check(checks, "public_safe_export_exists", "public_safe_alpha_review_export_v061.json" in route_text + component_text, "public-safe export path")
    add_check(checks, "private_local_export_exists", "private_local_alpha_review_export_v061.json" in route_text + component_text, "private export path")
    add_check(checks, "markdown_export_exists", "alpha_review_ux_export_summary_v061.md" in route_text + component_text, "markdown export path")
    add_check(checks, "lock_or_limitation_documented", "withLocalWriteLock" in route_text and "not database locking" in route_text + summary_text, "simple lock plus honest limitation")
    add_check(checks, "local_vs_future_hosted_boundary_present", "Future hosted admin would need authentication" in component_text + route_text + summary_text and "V0.61 does not provide" in component_text + summary_text, "local vs hosted admin separation")
    add_check(checks, "reviewer_identity_metadata_not_auth", "metadata labels only" in component_text and "not login, authentication, permissions" in component_text, "reviewer identities documented")
    add_check(checks, "draft_responses_present", "draftResponseLibrary" in route_text and all(status in route_text for status in STATUSES), "draft library covers statuses")
    add_check(checks, "drafts_do_not_claim_access_keys_email", all(term in route_text for term in ["No live access", "no production API access", "no API key"]) and "This draft is not sent automatically" in route_text, "draft boundaries present")
    add_check(checks, "no_automatic_api_key_issuance", "api_key_issued: false" in route_text and "api_key_issuing_enabled: false" in route_text, "no key issuing")
    add_check(checks, "no_live_access_granted", "live_access_granted: false" in route_text and "does not grant live access" in combined, "no live access")
    add_check(checks, "no_email_sending", "email_sent: false" in route_text and "This draft is not sent automatically" in route_text, "no email sending")
    add_check(checks, "no_external_services", not any(term in combined.lower() for term in EXTERNAL_CONNECTORS), "no external connectors")
    add_check(checks, "no_hosted_or_production_overclaims", not positive_overclaims(combined), "no positive hosted/production/certification claims")
    add_check(checks, "no_bank_compliance_legal_security_approval_claims", not any(term in combined.lower() for term in ["bank-approved", "compliance-certified", "legal-approved", "security-certified"]), "no positive approval claims")
    add_check(checks, "no_external_certification_claims", not any(term in combined.lower() for term in ["externally certified", "external certification granted"]), "no external certification claim")
    add_check(checks, "no_punitive_or_certain_guilt_wording", not any(term in combined.lower() for term in PUNITIVE_TERMS), "no punitive wording")
    add_check(checks, "frontend_does_not_expose_api_keys", "sk-" not in component_text.lower() and "api_key_" not in component_text.lower(), "frontend exposes no key values")
    add_check(checks, "v060_behavior_preserved", V060_STATE.exists() and "reset_appended_history" in route_text and "public_safe_review_summary_json" in route_text, "V0.60 behaviors remain")

    typecheck = run_command(["npm", "run", "typecheck"], FRONTEND)
    command_results.append(typecheck)
    add_check(checks, "npm_typecheck_passes", typecheck["passed"], typecheck["output_tail"][-500:])

    build = run_command(["npm", "run", "build"], FRONTEND)
    command_results.append(build)
    add_check(checks, "npm_build_passes", build["passed"], build["output_tail"][-500:])

    write_reports(checks, command_results)

    public_report = load_json(PUBLIC_REPORT)
    public_text = read(PUBLIC_REPORT) + read(SCORECARD)
    add_check(checks, "public_report_contains_no_personal_details", not public_has_personal_details(public_report, requests), "public report excludes request details")
    add_check(checks, "public_report_contains_boundary", BOUNDARY in public_text, "public report boundary present")
    add_check(checks, "public_report_contains_no_overclaims", not positive_overclaims(public_text), "public report avoids overclaims")

    write_reports(checks, command_results)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.61 ALPHA REVIEW UX + EXPORT AUDIT")
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
