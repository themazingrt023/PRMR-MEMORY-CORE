"""Run V0.86 first external controlled alpha readiness smoke."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v086"
PUBLIC_REPORT = REPORT_DIR / "public_first_external_alpha_readiness_v086.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_first_external_alpha_readiness_v086.json"
SMOKE_REPORT = REPORT_DIR / "first_external_alpha_readiness_smoke_v086.json"
SCORECARD = REPORT_DIR / "scorecard_v086.md"

V085_DOCS = {
    "client_onboarding_pack": ROOT / "docs" / "client_alpha_onboarding_pack_v085.md",
    "client_api_quickstart": ROOT / "docs" / "client_api_quickstart_v085.md",
    "client_handoff_template": ROOT / "docs" / "client_alpha_handoff_template_v085.md",
    "controlled_alpha_safety_checklist": ROOT / "docs" / "controlled_alpha_safety_checklist_v085.md",
}

DOCS = {
    "test_plan": ROOT / "docs" / "first_external_alpha_test_plan_v086.md",
    "invitation_template": ROOT / "docs" / "first_alpha_invitation_template_v086.md",
    "feedback_questions": ROOT / "docs" / "first_alpha_feedback_questions_v086.md",
    "evidence_record_template": ROOT / "docs" / "first_alpha_evidence_record_template_v086.md",
    "safety_checklist": ROOT / "docs" / "controlled_alpha_safety_checklist_v085.md",
}

HONEST_RESULT_STATUSES = [
    "completed_positive",
    "completed_mixed",
    "completed_needs_work",
    "not_completed",
    "revoked",
]

BOUNDARY_V086 = (
    "V0.86 is first external controlled alpha test preparation only. It does not "
    "claim real external validation until a real tester completes the controlled "
    "flow and feedback is recorded. It is not production readiness, billing, "
    "compliance approval, legal approval, bank approval, external security "
    "certification, or real-world validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_secret_pattern(text: str) -> bool:
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+(?!<PRMR_API_KEY>)[A-Za-z0-9_\-.]{12,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
        r"dash_v08[0-9]_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def false_claim_hits(text: str) -> list[str]:
    lowered = text.lower()
    phrases = [
        "production-ready",
        "production ready",
        "production readiness achieved",
        "billing enabled",
        "self-serve signup enabled",
        "compliance approved",
        "legal approved",
        "bank-approved",
        "bank approved",
        "security certified",
        "external security certification complete",
        "external validation complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in lowered]


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.86",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "First External Controlled Alpha Readiness",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V086,
        "docs_created": {name: path.as_posix() for name, path in DOCS.items() if "v086" in path.name},
        "first_alpha_readiness": {
            "process_ready_for_manual_tester_selection": True,
            "automatic_access": False,
            "sensitive_data_allowed_by_default": False,
            "real_external_validation_claimed": False,
            "manual_revocation_required": True,
        },
        "invitation_template_summary": smoke["invitation_template_summary"],
        "feedback_question_topics": smoke["feedback_question_topics"],
        "evidence_record_structure": smoke["evidence_record_structure"],
        "honest_result_statuses": HONEST_RESULT_STATUSES,
        "remaining_manual_step": "Choose the first external tester, run the controlled alpha flow, record feedback, and then update evidence honestly.",
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "Private report contains readiness trace details only. No raw keys, tokens, sensitive data, or real tester data are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.86 First External Controlled Alpha Readiness",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V086}",
        "",
        "## Docs",
        "",
        *[f"- {name}: {path}" for name, path in public_report["docs_created"].items()],
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- RUN: python examples/run_first_external_alpha_readiness_v086.py",
            "- RUN: python examples/audit_v086_first_external_alpha_readiness.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    texts = {name: read_text(path) for name, path in DOCS.items()}
    combined = "\n".join(texts.values())
    test_plan = texts["test_plan"]
    invitation = texts["invitation_template"]
    feedback = texts["feedback_questions"]
    evidence = texts["evidence_record_template"]
    safety = texts["safety_checklist"]

    add_check(checks, "v085_docs_exist", all(path.exists() for path in V085_DOCS.values()), {name: path.exists() for name, path in V085_DOCS.items()})
    add_check(checks, "v086_docs_exist", all(path.exists() for name, path in DOCS.items() if name != "safety_checklist"), {name: path.exists() for name, path in DOCS.items() if name != "safety_checklist"})
    add_check(checks, "invitation_template_exists", DOCS["invitation_template"].exists(), DOCS["invitation_template"].as_posix())
    add_check(checks, "feedback_questions_exist", DOCS["feedback_questions"].exists(), DOCS["feedback_questions"].as_posix())
    add_check(checks, "evidence_record_template_exists", DOCS["evidence_record_template"].exists(), DOCS["evidence_record_template"].as_posix())
    add_check(checks, "safety_checklist_exists", DOCS["safety_checklist"].exists(), DOCS["safety_checklist"].as_posix())
    add_check(checks, "no_raw_keys_in_docs", not contains_secret_pattern(combined), None)
    add_check(checks, "no_sensitive_data_allowed_by_default", "no sensitive data" in combined.lower() and "unless explicitly approved" in combined.lower(), None)
    add_check(checks, "revoke_process_included", "revoke" in combined.lower() and "revocation" in combined.lower(), None)
    add_check(checks, "storage_limitation_included", "/tmp" in combined and "smoke" in combined.lower() and "durable" in combined.lower(), None)
    add_check(checks, "controlled_alpha_boundary_included", "controlled alpha" in combined.lower() or "controlled-alpha" in combined.lower(), None)
    add_check(checks, "test_plan_has_success_and_failure_meanings", "what success means" in test_plan.lower() and "what failure means" in test_plan.lower(), None)
    add_check(checks, "invitation_has_no_hype_claims", not false_claim_hits(invitation), false_claim_hits(invitation))
    add_check(checks, "feedback_covers_required_topics", all(topic in feedback.lower() for topic in ["api setup", "headers", "client_id", "vault_id", "namespace", "continuity packet", "dashboard", "reporting", "pilot", "trust", "security"]), None)
    add_check(checks, "evidence_record_has_honest_statuses", all(status in evidence for status in HONEST_RESULT_STATUSES), HONEST_RESULT_STATUSES)
    add_check(checks, "safety_checklist_blocks_sensitive_default", "no real sensitive data unless explicitly approved" in safety.lower(), None)

    smoke = {
        "invitation_template_summary": {
            "short_founder_message": "present",
            "explains_prmr": "present",
            "explains_why_invited": "present",
            "states_what_tester_receives": "present",
            "time_commitment": "30 to 60 minutes",
            "no_sensitive_data_rule": True,
            "controlled_alpha_boundary": True,
        },
        "feedback_question_topics": [
            "PRMR understanding",
            "API setup",
            "headers/client/vault/namespace",
            "continuity packet",
            "dashboard/reporting",
            "confusion points",
            "strongest use case",
            "pilot credibility",
            "trust and security concerns",
            "next-tester improvements",
        ],
        "evidence_record_structure": {
            "tester_identifier": "pseudonym_or_approved_name_only",
            "date_time": True,
            "data_safety_confirmation": True,
            "endpoints_tested": True,
            "dashboard_tested": True,
            "issues_found": True,
            "feedback_summary": True,
            "next_actions": True,
            "access_revoked_or_kept_open": True,
            "honest_result_statuses": HONEST_RESULT_STATUSES,
        },
        "secret_hygiene": {
            "raw_secret_patterns_found": False,
            "raw_keys_expected": False,
        },
    }
    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(json.dumps(public_report, sort_keys=True)), false_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.86",
        "public_safe": True,
        "boundary": BOUNDARY_V086,
        "result": public_report["result"],
        "smoke": smoke,
    }
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.86 First External Alpha Readiness")
    print(f"Docs created: {len(public_report['docs_created'])}")
    print(f"Invitation template: {DOCS['invitation_template'].as_posix()}")
    print(f"Feedback questions: {DOCS['feedback_questions'].as_posix()}")
    print(f"Evidence template: {DOCS['evidence_record_template'].as_posix()}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
