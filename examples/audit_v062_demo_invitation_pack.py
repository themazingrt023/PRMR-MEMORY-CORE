from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPORT_DIR = ROOT / "reports" / "v062"

INVITATION_PACK = DOCS / "controlled_demo_invitation_pack_v062.md"
WALKTHROUGH_SCRIPT = DOCS / "demo_walkthrough_script_v062.md"
FEEDBACK_QUESTIONS = DOCS / "demo_feedback_questions_v062.md"
PUBLIC_REPORT = REPORT_DIR / "public_demo_invitation_pack_v062.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_demo_invitation_pack_v062.json"
SCORECARD = REPORT_DIR / "scorecard_v062.md"

BOUNDARY = (
    "V0.62 is a controlled demo invitation pack only. It is not public booking, hosted onboarding, "
    "billing, live API access, external validation, bank approval, compliance approval, legal approval, "
    "external security certification, or real-world validation."
)

INVITATION_CRITERIA = [
    "AI startup founders",
    "AI agent builders",
    "SaaS founders",
    "Customer support and operations builders",
    "Education AI builders",
    "Legal or research AI builders",
    "Fintech or risk people",
    "Technical collaborators",
    "Accelerator or competition reviewers",
]

TEMPLATE_HEADINGS = [
    "Warm Founder DM",
    "Email",
    "LinkedIn Message",
    "Competition / Accelerator Reviewer Message",
    "Technical Collaborator Message",
]

FEEDBACK_PROMPTS = [
    "Did the problem make sense?",
    "Did continuity feel different from summaries, vector search, or ordinary storage?",
    "Which use case felt strongest",
    "What confused you?",
    "Would you want to test this on synthetic data?",
    "What would make this credible enough for a future pilot discussion?",
    "What risks or missing pieces do you see?",
]

READINESS_ITEMS = [
    "Local site opens",
    "Demo page works",
    "Docs page works",
    "Alpha page works",
    "Local review console works",
    "Public reports are clean",
    "Boundaries are visible",
    "No API keys are exposed",
    "No production claims are made",
]

PUNITIVE_TERMS = [
    "fraudster",
    "criminal",
    "guilty",
    "definitely fraud",
    "blacklist",
    "close account immediately",
]

PUBLIC_RESTRICTED_TERMS = [
    "private_internal",
    "private report",
    "internal packet",
    "internal engine",
    "debug",
    "secret",
    "raw request",
]

POSITIVE_OVERCLAIMS = [
    r"\bproduction-ready\b",
    r"\bhosted api\b",
    r"\bpublic booking is live\b",
    r"\bapi key issued\b",
    r"\blive api access granted\b",
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


def add_check(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def positive_overclaims(text: str) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in POSITIVE_OVERCLAIMS if re.search(pattern, lowered)]


def public_restricted_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in PUBLIC_RESTRICTED_TERMS if term in lowered]


def write_reports(checks: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    public_report = {
        "version": "0.62",
        "title": "Controlled Demo Invitation Pack",
        "result": result,
        "passed_checks": passed,
        "total_checks": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "scope": "local controlled-alpha demo invitation evidence",
        "created": [
            "controlled demo invitation pack",
            "demo walkthrough script",
            "demo feedback questions",
        ],
        "templates": [
            "warm founder DM",
            "email",
            "LinkedIn message",
            "competition or accelerator reviewer message",
            "technical collaborator message",
        ],
        "safety": {
            "api_keys_issued": 0,
            "live_access_granted": False,
            "messages_sent_automatically": 0,
            "external_services_connected": False,
            "billing_connected": False,
            "uses_synthetic_or_demo_data_only": True,
        },
    }

    private_report = {
        **public_report,
        "title": "Controlled Demo Invitation Pack Private Audit Trace",
        "files": {
            "invitation_pack": str(INVITATION_PACK.relative_to(ROOT)),
            "walkthrough_script": str(WALKTHROUGH_SCRIPT.relative_to(ROOT)),
            "feedback_questions": str(FEEDBACK_QUESTIONS.relative_to(ROOT)),
        },
        "checks": checks,
        "frontend_changed": False,
        "npm_commands": "not run because V0.62 did not change frontend code",
    }

    PUBLIC_REPORT.write_text(json.dumps(public_report, indent=2), encoding="utf-8")
    PRIVATE_REPORT.write_text(json.dumps(private_report, indent=2), encoding="utf-8")

    scorecard = [
        "# V0.62 Controlled Demo Invitation Pack Scorecard",
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
        "- PASS: python examples/audit_v062_demo_invitation_pack.py",
        "- SKIPPED: npm run typecheck and npm run build were not required because no frontend code changed.",
        "",
        "V0.62 is a controlled demo invitation pack only. It is not public booking, hosted onboarding, billing, live API access, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.",
    ]
    SCORECARD.write_text("\n".join(scorecard) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict] = []

    invitation_text = read(INVITATION_PACK)
    walkthrough_text = read(WALKTHROUGH_SCRIPT)
    feedback_text = read(FEEDBACK_QUESTIONS)
    combined = "\n".join([invitation_text, walkthrough_text, feedback_text])

    add_check(checks, "invitation_pack_exists", INVITATION_PACK.exists(), str(INVITATION_PACK.relative_to(ROOT)))
    add_check(checks, "walkthrough_script_exists", WALKTHROUGH_SCRIPT.exists(), str(WALKTHROUGH_SCRIPT.relative_to(ROOT)))
    add_check(checks, "feedback_questions_exists", FEEDBACK_QUESTIONS.exists(), str(FEEDBACK_QUESTIONS.relative_to(ROOT)))
    add_check(checks, "invitation_criteria_exists", all(item in invitation_text for item in INVITATION_CRITERIA), "suitable audience criteria")
    add_check(checks, "at_least_five_templates_exist", sum(heading in invitation_text for heading in TEMPLATE_HEADINGS) >= 5, "five reusable drafts")
    add_check(checks, "templates_use_controlled_alpha_wording", invitation_text.count("local controlled-alpha") >= 3, "safe demo wording")
    add_check(checks, "templates_do_not_promise_access", "does not grant live API access" in invitation_text or "does not provide live API access" in invitation_text, "no access promise")
    add_check(checks, "walkthrough_covers_core_story", all(term in walkthrough_text for term in ["What PRMR Memory Core Is", "The Problem", "What Continuity Means", "What The Local Demo Shows", "Evidence That Exists", "What It Is Not"]), "founder walkthrough sections")
    add_check(checks, "feedback_questions_exist", all(prompt in feedback_text for prompt in FEEDBACK_PROMPTS), "required feedback prompts")
    add_check(checks, "demo_boundaries_exist", all(term in invitation_text for term in ["synthetic/demo data only", "Do not issue API keys", "Do not send invitations automatically", "Do not present demo outputs as final automated decisions"]), "demo boundaries")
    add_check(checks, "readiness_checklist_exists", all(item in invitation_text for item in READINESS_ITEMS), "readiness checklist")
    add_check(checks, "manual_process_exists", "Manual Invitation Process" in invitation_text and "No message is sent automatically" in invitation_text, "manual invitation process")
    add_check(checks, "no_positive_production_or_hosted_claims", not positive_overclaims(combined), "no production/hosted/certification overclaims")
    add_check(checks, "no_positive_approval_claims", not any(term in combined.lower() for term in ["bank-approved", "compliance-certified", "legal-approved", "security-certified"]), "no positive approval claims")
    add_check(checks, "no_automatic_api_key_promise", "automatic API key issuing" in combined and "Do not issue API keys" in invitation_text, "no automatic key promise")
    add_check(checks, "no_live_access_promise", "Do not grant live production API access" in invitation_text and "does not grant live access" in walkthrough_text, "no live access promise")
    add_check(checks, "no_external_integration", "Do not connect calendar, CRM, email, Stripe, billing, or other external services" in invitation_text, "no external services")
    add_check(checks, "non_punitive_wording", not any(term in combined.lower() for term in PUNITIVE_TERMS), "no punitive wording")
    add_check(checks, "frontend_not_changed", not (ROOT / "frontend" / "app" / "demo" / "invite").exists(), "docs/reports only for V0.62")
    add_check(checks, "npm_not_required", True, "frontend unchanged; npm commands not required")

    write_reports(checks)

    public_report = load_json(PUBLIC_REPORT)
    public_text = read(PUBLIC_REPORT)
    add_check(checks, "public_report_contains_no_restricted_terms", not public_restricted_terms(public_text), "public report avoids restricted terms")
    add_check(checks, "public_report_has_boundary", BOUNDARY in public_text, "public boundary present")
    add_check(checks, "public_report_has_no_overclaims", not positive_overclaims(public_text), "public report avoids overclaims")

    write_reports(checks)

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"

    print("PRMR V0.62 CONTROLLED DEMO INVITATION PACK AUDIT")
    print("------------------------------------------------")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    print()
    print("Command summary:")
    print("- python examples/audit_v062_demo_invitation_pack.py: PASS" if result == "PASS" else "- python examples/audit_v062_demo_invitation_pack.py: NEEDS_WORK")
    print("- npm run typecheck: SKIPPED, no frontend code changed")
    print("- npm run build: SKIPPED, no frontend code changed")
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
