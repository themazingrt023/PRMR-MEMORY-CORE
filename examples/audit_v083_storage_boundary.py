"""V0.83 storage boundary audit."""

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

REPORT_DIR = ROOT / "reports" / "v083"
PUBLIC_REPORT = REPORT_DIR / "public_storage_boundary_v083.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_storage_boundary_v083.json"
SMOKE_REPORT = REPORT_DIR / "storage_mode_smoke_v083.json"
SCORECARD = REPORT_DIR / "scorecard_v083.md"

V082_PUBLIC = ROOT / "reports" / "v082" / "public_hosted_dashboard_connection_v082.json"
MODULE_PATH = ROOT / "prmr" / "product" / "storage_mode_v083.py"
API_SERVER = ROOT / "prmr" / "product" / "api_server_v076.py"
DOC_PATH = ROOT / "docs" / "durable_hosted_storage_v083.md"
RUNNER_PATH = ROOT / "examples" / "run_storage_boundary_v083.py"

BOUNDARY_V083 = (
    "V0.83 is storage boundary and durable-hosting readiness evidence only. "
    "It classifies local/hosted storage modes and documents durable storage "
    "requirements. It is not a full production database migration, paid managed "
    "storage, compliance approval, legal approval, external security "
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


def false_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "production persistence ready",
        "durable hosted records guaranteed",
        "real client data supported",
        "billing enabled",
        "compliance approved",
        "legal approved",
        "security certified",
        "managed database migration complete",
        "paid managed storage enabled",
    ]
    return [phrase for phrase in phrases if phrase in text]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_storage_boundary_v083", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.83 storage runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.83",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Storage Boundary Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V083,
        "truth_label": "storage boundary and durable-hosting readiness evidence only",
        "storage_classifications": runner_public.get("storage_classifications"),
        "current_hosted_storage_status": runner_public.get("current_hosted_storage_status"),
        "durable_storage_verified": runner_public.get("durable_storage_verified"),
        "recommended_durable_path": runner_public.get("recommended_durable_path"),
        "remaining_gaps": ["durable hosted database or persistent disk", "restart/redeploy persistence smoke", "real external alpha storage approval"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "restricted_note": "Storage audit contains configuration classifications only, not secrets or client data.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.83 Storage Boundary Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Current hosted storage status: {public_report['current_hosted_storage_status']}",
        f"Recommended durable path: {public_report['recommended_durable_path']}",
        "",
        f"Boundary: {BOUNDARY_V083}",
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
            "- RUN: python examples/run_storage_boundary_v083.py",
            "- RUN: python examples/audit_v083_storage_boundary.py",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v082 = read_json(V082_PUBLIC)
    module_source = read_text(MODULE_PATH)
    api_server_source = read_text(API_SERVER)
    doc_source = read_text(DOC_PATH)
    runner_source = read_text(RUNNER_PATH)

    add_check(checks, "v082_evidence_exists", V082_PUBLIC.exists(), V082_PUBLIC.as_posix())
    add_check(checks, "v082_passed", v082.get("result") == "PASS" and v082.get("frontend_proxy_locked_by_default") is True, v082.get("result"))
    add_check(checks, "storage_mode_module_exists", MODULE_PATH.exists(), MODULE_PATH.as_posix())
    add_check(checks, "durable_storage_doc_exists", DOC_PATH.exists(), DOC_PATH.as_posix())
    add_check(checks, "storage_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "classifier_defines_required_modes", all(term in module_source for term in ["local_sqlite", "hosted_ephemeral_sqlite", "hosted_durable_sqlite", "hosted_managed_database_planned", "unknown_storage_mode"]), None)
    add_check(checks, "classifier_detects_tmp_as_ephemeral", "/tmp" in module_source and "hosted_ephemeral_sqlite" in module_source, None)
    add_check(checks, "classifier_handles_missing_path", "missing_storage_path" in module_source and "unknown_storage_mode" in module_source, None)
    add_check(checks, "api_health_includes_storage_boundary", "storage_boundary_v083" in api_server_source and "public_storage_health_payload" in api_server_source, None)
    add_check(checks, "docs_explain_tmp_limitation", "/tmp" in doc_source and "ephemeral" in doc_source.lower() and "smoke tests only" in doc_source.lower(), None)
    add_check(checks, "docs_recommend_durable_path", "Render persistent disk" in doc_source and "/var/data" in doc_source and "managed Postgres" in doc_source, None)
    add_check(checks, "runner_tests_core_classifications", all(term in runner_source for term in ["local_sqlite_classified", "hosted_tmp_classified_ephemeral", "missing_path_unknown_safe", "tmp_health_does_not_claim_durable"]), None)
    add_check(checks, "docs_avoid_false_claims", not false_claim_hits(doc_source), false_claim_hits(doc_source))

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    classifications = runner_public.get("storage_classifications", {})
    add_check(checks, "local_sqlite_classified_correctly", classifications.get("local_sqlite") == "local_sqlite", classifications)
    add_check(checks, "hosted_tmp_classified_ephemeral", classifications.get("hosted_tmp") == "hosted_ephemeral_sqlite", classifications)
    add_check(checks, "missing_storage_path_handled_safely", classifications.get("missing_path") == "unknown_storage_mode", classifications)
    add_check(checks, "public_health_report_no_durable_tmp_claim", runner_public.get("smoke_summary", {}).get("tmp_durable_claim_allowed") is False and runner_public.get("durable_storage_verified") is False, runner_public.get("smoke_summary"))
    add_check(checks, "runner_public_report_contains_no_secrets", not contains_secret_pattern(runner_public), None)
    add_check(checks, "runner_public_report_has_no_false_claims", not false_claim_hits(runner_public), false_claim_hits(runner_public))
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    public_report = build_public_report(checks, runner_public)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(public_report), false_claim_hits(public_report))

    public_report = build_public_report(checks, runner_public)
    private_report = build_private_report(public_report, checks, runner_public)
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.83 Storage Boundary Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Local SQLite: {public_report.get('storage_classifications', {}).get('local_sqlite')}")
    print(f"Hosted /tmp: {public_report.get('storage_classifications', {}).get('hosted_tmp')}")
    print(f"Missing path: {public_report.get('storage_classifications', {}).get('missing_path')}")
    print(f"Durable storage verified: {public_report.get('durable_storage_verified')}")
    print(f"Recommended durable path: {public_report.get('recommended_durable_path')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
