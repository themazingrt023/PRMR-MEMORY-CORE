"""V0.86 first external controlled alpha readiness audit."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports" / "v086"
PUBLIC_REPORT = REPORT_DIR / "public_first_external_alpha_readiness_v086.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_first_external_alpha_readiness_v086.json"
SMOKE_REPORT = REPORT_DIR / "first_external_alpha_readiness_smoke_v086.json"
SCORECARD = REPORT_DIR / "scorecard_v086.md"

V085_PUBLIC = ROOT / "reports" / "v085" / "public_client_docs_onboarding_pack_v085.json"
RUNNER_PATH = ROOT / "examples" / "run_first_external_alpha_readiness_v086.py"

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


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_first_external_alpha_readiness_v086", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.86 readiness runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.86",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "First External Controlled Alpha Readiness Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V086,
        "docs_created": runner_public.get("docs_created"),
        "first_alpha_readiness": runner_public.get("first_alpha_readiness"),
        "invitation_template_summary": runner_public.get("invitation_template_summary"),
        "feedback_question_topics": runner_public.get("feedback_question_topics"),
        "evidence_record_structure": runner_public.get("evidence_record_structure"),
        "honest_result_statuses": runner_public.get("honest_result_statuses"),
        "remaining_manual_step": runner_public.get("remaining_manual_step"),
        "remaining_gaps": ["choose first external tester", "run controlled alpha", "record feedback and evidence"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "restricted_note": "No raw keys, dashboard tokens, sensitive data, or real tester data are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.86 First External Controlled Alpha Readiness Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V086}",
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


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v085 = read_json(V085_PUBLIC)
    texts = {name: read_text(path) for name, path in DOCS.items()}
    combined = "\n".join(texts.values())
    test_plan = texts["test_plan"]
    invitation = texts["invitation_template"]
    feedback = texts["feedback_questions"]
    evidence = texts["evidence_record_template"]
    safety = texts["safety_checklist"]

    add_check(checks, "v085_evidence_exists", V085_PUBLIC.exists(), V085_PUBLIC.as_posix())
    add_check(checks, "v085_client_docs_passed", v085.get("result") == "PASS", v085.get("result"))
    add_check(checks, "all_v086_docs_exist", all(path.exists() for name, path in DOCS.items() if name != "safety_checklist"), {name: path.exists() for name, path in DOCS.items() if name != "safety_checklist"})
    add_check(checks, "invitation_template_public_safe", all(term in invitation.lower() for term in ["controlled-alpha", "no sensitive data", "feedback"]) and not contains_secret_pattern(invitation) and not false_claim_hits(invitation), false_claim_hits(invitation))
    add_check(checks, "feedback_questions_complete", all(topic in feedback.lower() for topic in ["api setup", "headers", "client_id", "vault_id", "namespace", "continuity packet", "dashboard", "reporting", "pilot", "trust", "security", "before next tester"]), None)
    add_check(checks, "evidence_record_template_complete", all(topic in evidence.lower() for topic in ["tester/project identifier", "date", "time", "synthetic or approved non-sensitive data", "endpoints tested", "dashboard tested", "issues found", "feedback summary", "next actions", "access revoked", "access kept open"]), None)
    add_check(checks, "no_raw_api_keys_or_tokens_in_docs", not contains_secret_pattern(combined), None)
    add_check(checks, "no_false_claims_in_docs", not false_claim_hits(combined), false_claim_hits(combined))
    add_check(checks, "no_real_client_data_in_templates", "<tester_pseudonym_or_approved_name>" in evidence.lower() and "<client_id>" in evidence.lower() and "<vault_id>" in evidence.lower(), None)
    add_check(checks, "safety_checklist_blocks_sensitive_data_by_default", "no real sensitive data unless explicitly approved" in safety.lower(), None)
    add_check(checks, "revoke_path_included", "revoke" in combined.lower() and "revocation" in combined.lower(), None)
    add_check(checks, "storage_limitation_included", "/tmp" in combined and "smoke" in combined.lower() and "durable" in combined.lower(), None)
    add_check(checks, "honest_result_status_labels_present", all(status in evidence for status in HONEST_RESULT_STATUSES), HONEST_RESULT_STATUSES)
    add_check(checks, "does_not_claim_real_external_validation", "do not treat a first alpha attempt as validation" in test_plan.lower() and "does not claim real external validation" in test_plan.lower(), None)

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))
    add_check(checks, "runner_public_report_contains_no_secrets", not contains_secret_pattern(json.dumps(runner_public, sort_keys=True)), None)
    add_check(checks, "runner_public_report_has_no_false_claims", not false_claim_hits(json.dumps(runner_public, sort_keys=True)), false_claim_hits(json.dumps(runner_public, sort_keys=True)))

    public_report = build_public_report(checks, runner_public)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(json.dumps(public_report, sort_keys=True)), false_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, runner_public)
    private_report = build_private_report(public_report, checks, runner_public)
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.86 First External Alpha Readiness Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Docs created: {len(public_report.get('docs_created') or {})}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
