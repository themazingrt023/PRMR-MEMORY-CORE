import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.alpha_api_sandbox_v0521 import scan_unsafe_public_language


VERSION = "0.58"
ROOT = Path(".")
FRONTEND_DIR = ROOT / "frontend"
REPORT_DIR = ROOT / "reports/v058"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_PATH = REPORT_DIR / "public_alpha_access_pipeline_v058.json"
PRIVATE_PATH = REPORT_DIR / "private_internal_alpha_access_pipeline_v058.json"
SCORECARD_PATH = REPORT_DIR / "scorecard_v058.md"
LOCAL_REQUESTS_PATH = REPORT_DIR / "local_alpha_requests_v058.json"

ALPHA_PAGE = FRONTEND_DIR / "app/alpha/page.tsx"
ALPHA_FORM = FRONTEND_DIR / "components/alpha/RequestAccessForm.tsx"
ALPHA_NOTICE = FRONTEND_DIR / "components/alpha/ControlledAlphaNotice.tsx"
ALPHA_REVIEW = FRONTEND_DIR / "app/alpha/review/page.tsx"
ALPHA_ROUTE = FRONTEND_DIR / "app/api/alpha/request/route.ts"

BOUNDARY = (
    "V0.58 is a local controlled-alpha request pipeline only. It is not hosted onboarding, not billing, "
    "not production access, not compliance approval, not legal approval, not bank approval, "
    "not external security certification, and not real-world validation."
)

REQUIRED_FIELDS = [
    "name",
    "email",
    "organisation",
    "role",
    "use_case_category",
    "use_case_description",
    "data_type_planned",
]

REQUIRED_CATEGORIES = [
    "AI agent memory",
    "Customer support continuity",
    "SaaS user-history continuity",
    "Education progress continuity",
    "Legal/research case continuity",
    "Fraud/risk sandbox evaluation",
    "Company knowledge continuity",
    "Other",
]

FORBIDDEN_CLAIMS = [
    "hosted api",
    "hosted production",
    "production-ready",
    "production ready",
    "start using production api now",
    "get api key instantly",
    "bank-grade",
    "bank approved",
    "bank approval",
    "compliance approved",
    "compliance approval",
    "legal approval",
    "external security certification",
    "external certification",
    "real-world validation",
    "real world validation",
    "real-world validated",
    "enterprise-ready",
    "certified",
    "guaranteed",
]

RESTRICTED_PUBLIC_TERMS = [
    "raw_api_key",
    "new_api_key",
    "private_internal",
    "private_packets",
    "internal packet",
    "private report",
    "internal engine",
    "engine_result_snapshot",
    "internal_rule_data",
]


def read_text(path):
    return path.read_text(encoding="utf-8")


def add_check(checks, name, passed, details=None):
    checks.append({"name": name, "passed": bool(passed), "details": details or {}})


def run_command(command, cwd):
    env = os.environ.copy()
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=True,
        env=env,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def public_checks(checks):
    return [{"name": check["name"], "passed": check["passed"]} for check in checks]


def missing_terms(text, terms):
    lower = text.lower()
    return [term for term in terms if term.lower() not in lower]


def claim_hits(text):
    hits = []
    for line in text.splitlines():
        lower = line.lower()
        for term in FORBIDDEN_CLAIMS:
            if term not in lower:
                continue
            negated = any(marker in lower for marker in [
                "not ",
                "no ",
                "never ",
                "do not ",
                "does not ",
                "without ",
                "avoid",
                "forbidden",
            ])
            if not negated:
                hits.append(line.strip())
    return sorted(set(hits))


def restricted_hits(text):
    lower = text.lower()
    return [term for term in RESTRICTED_PUBLIC_TERMS if term in lower]


def build_public_report(checks, command_results):
    passed_count = sum(1 for check in checks if check["passed"])
    total_checks = len(checks)
    result = "PASS" if passed_count == total_checks else "NEEDS_WORK"
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": VERSION,
        "report_type": "alpha_access_pipeline",
        "timestamp": datetime.now().isoformat(),
        "result": result,
        "passed_checks": passed_count,
        "total_checks": total_checks,
        "all_checks_passed": passed_count == total_checks,
        "purpose": "Local controlled-alpha request workflow with pending review status and local request storage.",
        "files": [
            str(ALPHA_PAGE),
            str(ALPHA_FORM),
            str(ALPHA_NOTICE),
            str(ALPHA_ROUTE),
            str(ALPHA_REVIEW),
            str(LOCAL_REQUESTS_PATH),
        ],
        "form_fields": REQUIRED_FIELDS + ["confirm_no_sensitive_data", "confirm_alpha_boundary"],
        "storage": "Local JSON review queue under reports/v058/local_alpha_requests_v058.json",
        "api_route": "/api/alpha/request",
        "command_summary": {
            name: "PASS" if data["returncode"] == 0 else "NEEDS_WORK"
            for name, data in command_results.items()
        },
        "checks": public_checks(checks),
        "boundary": BOUNDARY,
        "remaining_gaps": [
            "V0.59 can define follow-up workflow, reviewer notes, and email drafting without external service integration.",
            "Real account creation, credential issuing, billing, hosted onboarding, and external validation remain future work.",
        ],
    }


def build_scorecard(public_report):
    lines = [
        "# PRMR V0.58 Alpha Access Pipeline",
        "",
        "Company: Afternum Industries  ",
        "Product: PRMR Memory Core  ",
        "Version: V0.58  ",
        "",
        "## Result",
        "",
        f"**{public_report['result']}**",
        "",
        f"Passed checks: **{public_report['passed_checks']}/{public_report['total_checks']}**",
        "",
        "## Form Fields",
        "",
    ]
    for field in public_report["form_fields"]:
        lines.append(f"- {field}")
    lines.extend(["", "## Checks", ""])
    for check in public_report["checks"]:
        lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'}")
    lines.extend(["", "## Boundary", "", public_report["boundary"], "", "## Remaining Gaps", ""])
    for gap in public_report["remaining_gaps"]:
        lines.append(f"- {gap}")
    return "\n".join(lines)


def public_artifacts_are_clean(public_report, scorecard_text):
    text = json.dumps({"public_report": public_report, "scorecard": scorecard_text}, sort_keys=True)
    return {
        "unsafe_language": scan_unsafe_public_language({"text": text}),
        "claim_hits": claim_hits(text),
        "restricted_hits": restricted_hits(text),
    }


def main():
    checks = []

    add_check(checks, "alpha_page_exists", ALPHA_PAGE.exists())
    add_check(checks, "api_alpha_request_route_exists", ALPHA_ROUTE.exists())
    add_check(checks, "alpha_review_page_or_report_exists", ALPHA_REVIEW.exists() or LOCAL_REQUESTS_PATH.exists())
    add_check(checks, "local_request_storage_exists", LOCAL_REQUESTS_PATH.exists())

    form_text = read_text(ALPHA_FORM) if ALPHA_FORM.exists() else ""
    route_text = read_text(ALPHA_ROUTE) if ALPHA_ROUTE.exists() else ""
    notice_text = read_text(ALPHA_NOTICE) if ALPHA_NOTICE.exists() else ""
    review_text = read_text(ALPHA_REVIEW) if ALPHA_REVIEW.exists() else ""
    combined_public_source = "\n".join([form_text, route_text, notice_text, review_text, read_text(ALPHA_PAGE) if ALPHA_PAGE.exists() else ""])

    add_check(checks, "alpha_form_fields_exist", not missing_terms(form_text + route_text, REQUIRED_FIELDS), {"missing": missing_terms(form_text + route_text, REQUIRED_FIELDS)})
    add_check(checks, "use_case_categories_exist", not missing_terms(form_text + route_text, REQUIRED_CATEGORIES), {"missing": missing_terms(form_text + route_text, REQUIRED_CATEGORIES)})
    add_check(
        checks,
        "required_checkboxes_exist",
        "confirm_no_sensitive_data" in form_text
        and "confirm_alpha_boundary" in form_text
        and "no real sensitive data" in form_text.lower()
        and "not production or certified access" in form_text.lower(),
    )
    add_check(
        checks,
        "request_validation_exists",
        all(term in route_text for term in ["validEmail", "validation_failed", "invalid_email", "sensitive_data_not_allowed", "allowedCategories"]),
    )
    add_check(
        checks,
        "submission_produces_pending_review_state",
        "pending_review" in route_text and "Request received locally" in form_text and "founder/team review" in route_text,
    )
    add_check(
        checks,
        "no_automatic_api_key_issuance",
        "api_key_issued: false" in route_text
        and "real_credential_issued: false" in route_text
        and "automatic_access_granted: false" in route_text
        and "Get API key instantly" not in combined_public_source,
    )
    add_check(
        checks,
        "no_external_service_integration",
        not any(term in route_text.lower() for term in ["stripe", "sendgrid", "mailchimp", "hubspot", "salesforce", "fetch(\"https://", "smtp"]),
    )
    add_check(
        checks,
        "public_copy_contains_alpha_boundary_wording",
        all(term.lower() in combined_public_source.lower() for term in [
            "Request controlled alpha access",
            "Pending founder/team review",
            "Synthetic, anonymised, or approved data only",
            "No live service access is granted by this form",
        ]),
    )
    add_check(
        checks,
        "review_summary_shows_counts_and_no_auto_access",
        all(term in review_text for term in ["Total requests", "Pending requests", "Automatic access", "No automatic access is granted"]),
    )

    add_check(checks, "no_hosted_production_or_forbidden_claims", not claim_hits(combined_public_source), {"claim_hits": claim_hits(combined_public_source)})
    add_check(checks, "no_punitive_or_certain_guilt_wording", not scan_unsafe_public_language({"text": combined_public_source}), {"unsafe": scan_unsafe_public_language({"text": combined_public_source})})
    add_check(checks, "frontend_does_not_expose_api_keys", not any(term in combined_public_source for term in ["ALPHA_SANDBOX_KEYS", "prmr_v0521_alpha_seed_key", "prmr_v0521_beta_seed_key", "raw_api_key", "new_api_key"]))
    add_check(checks, "no_restricted_public_terms", not restricted_hits(combined_public_source), {"restricted_hits": restricted_hits(combined_public_source)})

    command_results = {}
    for name, command in {
        "frontend_typecheck": "npm run typecheck",
        "frontend_build": "npm run build",
    }.items():
        completed = run_command(command, FRONTEND_DIR)
        command_results[name] = {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout.splitlines()[-40:],
            "stderr_tail": completed.stderr.splitlines()[-40:],
        }
        add_check(checks, f"{name}_passes", completed.returncode == 0, command_results[name])

    public_report = build_public_report(checks, command_results)
    scorecard_text = build_scorecard(public_report)
    clean = public_artifacts_are_clean(public_report, scorecard_text)
    add_check(
        checks,
        "public_report_and_scorecard_are_claim_safe",
        not clean["unsafe_language"] and not clean["claim_hits"] and not clean["restricted_hits"],
        clean,
    )

    public_report = build_public_report(checks, command_results)
    scorecard_text = build_scorecard(public_report)
    final_clean = public_artifacts_are_clean(public_report, scorecard_text)
    if final_clean["unsafe_language"] or final_clean["claim_hits"] or final_clean["restricted_hits"]:
        add_check(checks, "final_public_artifact_hygiene_holds", False, final_clean)
        public_report = build_public_report(checks, command_results)
        scorecard_text = build_scorecard(public_report)

    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "command_results": command_results,
        "local_storage_snapshot": json.loads(read_text(LOCAL_REQUESTS_PATH)) if LOCAL_REQUESTS_PATH.exists() else None,
    }

    PUBLIC_PATH.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    PRIVATE_PATH.write_text(json.dumps(private_report, indent=4), encoding="utf-8")
    SCORECARD_PATH.write_text(scorecard_text, encoding="utf-8")

    print("PRMR V0.58 ALPHA ACCESS PIPELINE AUDIT")
    print("--------------------------------------")
    print(f"Passed checks: {public_report['passed_checks']}/{public_report['total_checks']}")
    print("Result:", public_report["result"])
    print()
    print("Command summary:")
    for name, data in command_results.items():
        print(f"- {name}: {'PASS' if data['returncode'] == 0 else 'NEEDS_WORK'}")
    print()
    print("Created:")
    print(PUBLIC_PATH)
    print(PRIVATE_PATH)
    print(SCORECARD_PATH)

    if public_report["result"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
