"""V0.80 manual client onboarding audit."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports" / "v080"
PUBLIC_REPORT = REPORT_DIR / "public_manual_client_onboarding_v080.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_manual_client_onboarding_v080.json"
PRIVATE_KEY_PACKET = REPORT_DIR / "private_one_time_key_packet_v080.json"
SCORECARD = REPORT_DIR / "scorecard_v080.md"

V079_PUBLIC = ROOT / "reports" / "v079" / "public_controlled_hosted_test_scope_v079.json"
MODULE_PATH = ROOT / "prmr" / "product" / "manual_client_onboarding_v080.py"
RUNNER_PATH = ROOT / "examples" / "run_manual_client_onboarding_v080.py"
DOC_PATH = ROOT / "docs" / "manual_alpha_onboarding_v080.md"

BOUNDARY_V080 = (
    "V0.80 is a local/manual controlled-alpha onboarding workflow. It supports "
    "founder/operator-created synthetic alpha clients and one-time private key "
    "delivery evidence. It is not self-serve signup, billing, automatic access, "
    "production readiness, external validation, bank approval, compliance "
    "approval, legal approval, external security certification, or real-world "
    "validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None, skipped: bool = False) -> None:
    checks.append({"name": name, "passed": bool(passed), "skipped": bool(skipped), "detail": detail})


def contains_secret_pattern(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    patterns = [
        r"\bsk-[A-Za-z0-9_\-]{16,}\b",
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"prmr_alpha_dev_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def positive_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "self-serve signup enabled",
        "billing enabled",
        "automatic access granted",
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
        "external validation complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_manual_client_onboarding_v080", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.80 onboarding runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git_ls_files() -> set[str]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=True)
    except Exception:
        return set()
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


def build_audit_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"] and not check["skipped"]]
    check_lookup = {check["name"]: check for check in checks}
    v079_verified = bool(check_lookup.get("v079_full_hosted_smoke_passed", {}).get("passed"))
    packet_committed = not bool(check_lookup.get("private_one_time_packet_not_tracked", {}).get("passed", True))
    return {
        "version": "0.80",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Manual Client Onboarding Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V080,
        "runner_result": runner_public.get("result"),
        "onboarding_record_count": len(runner_public.get("onboarding_records", [])),
        "workflow": runner_public.get("workflow", {}),
        "safe_onboarding_records": runner_public.get("onboarding_records", []),
        "credential_value_in_public_report": False,
        "private_one_time_packet_path": PRIVATE_KEY_PACKET.as_posix(),
        "private_one_time_packet_committed": packet_committed,
        "v079_full_hosted_smoke_required": True,
        "v079_full_hosted_smoke_verified": v079_verified,
        "honest_status": "PASS" if not failures else "NEEDS_WORK",
        "remaining_gaps": [
            "dashboard authentication",
            "durable hosted account storage",
            "billing",
            "real external alpha client testing",
        ],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    safe_records = runner_public.get("onboarding_records", [])
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "safe_onboarding_records": safe_records,
        "restricted_note": "The private one-time key packet is separate. This audit private report intentionally excludes the raw credential value.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.80 Manual Client Onboarding Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Private one-time key packet: {PRIVATE_KEY_PACKET.as_posix()}",
        "",
        f"Boundary: {BOUNDARY_V080}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "SKIP" if check["skipped"] else ("PASS" if check["passed"] else "FAIL")
        lines.append(f"- {status}: {check['name']}")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "- RUN: python examples/run_manual_client_onboarding_v080.py",
            "- RUN: python examples/audit_v080_manual_client_onboarding.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    module_source = read_text(MODULE_PATH)
    runner_source = read_text(RUNNER_PATH)
    doc_source = read_text(DOC_PATH)

    v079 = read_json(V079_PUBLIC)
    add_check(checks, "v079_full_hosted_smoke_evidence_exists", V079_PUBLIC.exists(), V079_PUBLIC.as_posix())
    add_check(checks, "v079_full_hosted_smoke_passed", v079.get("hosted_smoke_result_level") == "PASS_FULL_CONTROLLED_HOSTED_SMOKE" and v079.get("full_controlled_hosted_smoke_verified") is True, v079.get("hosted_smoke_result_level"))

    add_check(checks, "onboarding_module_exists", MODULE_PATH.exists(), MODULE_PATH.as_posix())
    add_check(checks, "onboarding_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "onboarding_docs_exist", DOC_PATH.exists(), DOC_PATH.as_posix())
    add_check(checks, "module_supports_required_statuses", all(status in module_source for status in ["pending_manual_delivery", "delivered", "revoked", "archived"]), None)
    add_check(checks, "module_returns_key_through_one_time_packet", "one_time_key_packet" in module_source and "_one_time_credentials.pop" in module_source, None)
    add_check(checks, "runner_verifies_revoke", "revoked_key_is_blocked" in runner_source and "revoke_path_works" in runner_source, None)
    add_check(checks, "docs_define_manual_approval", "Manual Approval Steps" in doc_source and "founder/operator" in doc_source, None)
    add_check(checks, "docs_define_safe_delivery_and_revoke", "Deliver the key through a private approved channel" in doc_source and "Revoke" in doc_source, None)

    runner = load_runner_module()
    runner_public, runner_private, one_time_packet, runner_checks = runner.run_onboarding()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.PRIVATE_KEY_PACKET, one_time_packet)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    records = runner_public.get("onboarding_records", [])
    first = records[0] if records else {}
    add_check(checks, "creates_client_vault_namespace", bool(first.get("client_id")) and bool(first.get("vault_id")) and bool(first.get("namespace")), first)
    add_check(checks, "issues_fresh_key", bool(first.get("key_id")) and bool(first.get("safe_key_preview")), {"key_id": first.get("key_id"), "safe_key_preview": first.get("safe_key_preview")})
    add_check(checks, "safe_key_preview_hash_present", bool(first.get("safe_key_preview")) and bool(first.get("key_hash_prefix")), None)
    add_check(checks, "raw_key_returned_only_once", any(check["name"] == "private_one_time_packet_contains_key_once" and check["passed"] for check in runner_checks), None)
    add_check(checks, "key_validates_before_revoke", any(check["name"] == "issued_key_validates_locally" and check["passed"] for check in runner_checks), None)
    add_check(checks, "revoke_path_works", any(check["name"] == "revoked_key_is_blocked" and check["passed"] for check in runner_checks), None)
    add_check(checks, "no_real_client_data_used_by_default", first.get("synthetic_only") is True and str(first.get("client_id", "")).startswith("client_v080_"), first.get("client_id"))

    public_text = json.dumps(runner_public, sort_keys=True)
    raw_key = one_time_packet.get("alpha_api_key")
    add_check(checks, "private_one_time_packet_contains_credential_value", bool(raw_key), {"credential_value_present": bool(raw_key)})
    add_check(checks, "private_one_time_packet_marked_private_local_only", one_time_packet.get("local_private_only") is True and one_time_packet.get("do_not_commit") is True and one_time_packet.get("public_safe") is False, None)
    tracked_files = git_ls_files()
    add_check(checks, "private_one_time_packet_not_tracked", "reports/v080/private_one_time_key_packet_v080.json" not in tracked_files, None)
    add_check(checks, "raw_key_absent_from_public_report", bool(raw_key) and raw_key not in public_text, None)
    add_check(checks, "public_report_contains_no_secret_patterns", not contains_secret_pattern(runner_public), None)
    add_check(checks, "public_report_has_no_automatic_signup_or_billing_claim", runner_public.get("workflow", {}).get("self_serve_signup") is False and runner_public.get("workflow", {}).get("billing_enabled") is False, runner_public.get("workflow"))
    add_check(checks, "public_report_has_no_production_or_certification_claims", not positive_claim_hits(runner_public), positive_claim_hits(runner_public))
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    audit_public = build_audit_public_report(checks, runner_public)
    clean = {
        "secret_pattern_present": contains_secret_pattern(audit_public),
        "positive_claim_hits": positive_claim_hits(audit_public),
    }
    add_check(checks, "audit_public_report_contains_no_secrets", not clean["secret_pattern_present"], clean)
    add_check(checks, "audit_public_report_has_no_false_claims", not clean["positive_claim_hits"], clean["positive_claim_hits"])

    audit_public = build_audit_public_report(checks, runner_public)
    audit_private = build_private_report(audit_public, checks, runner_public)
    return audit_public, audit_private, checks


def main() -> int:
    public_report, private_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.80 Manual Client Onboarding Audit")
    print(f"V0.79 full hosted smoke verified: {public_report.get('v079_full_hosted_smoke_verified')}")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Onboarding records: {public_report.get('onboarding_record_count')}")
    print(f"Private one-time key packet: {PRIVATE_KEY_PACKET.as_posix()}")
    print(f"Private packet committed: {public_report.get('private_one_time_packet_committed')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
