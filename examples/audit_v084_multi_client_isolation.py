"""V0.84 multi-client isolation audit."""

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

REPORT_DIR = ROOT / "reports" / "v084"
PUBLIC_REPORT = REPORT_DIR / "public_multi_client_isolation_v084.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_multi_client_isolation_v084.json"
SMOKE_REPORT = REPORT_DIR / "multi_client_isolation_smoke_v084.json"
SCORECARD = REPORT_DIR / "scorecard_v084.md"

V083_PUBLIC = ROOT / "reports" / "v083" / "public_storage_boundary_v083.json"
RUNNER_PATH = ROOT / "examples" / "run_multi_client_isolation_v084.py"
LIFECYCLE_PATH = ROOT / "prmr" / "product" / "api_key_lifecycle_v070.py"

BOUNDARY_V084 = (
    "V0.84 is controlled synthetic multi-client isolation evidence only. It "
    "tests scoped API access, reports, usage logs, request logs, and dashboard "
    "state for synthetic alpha clients. It is not external security "
    "certification, production auth, compliance approval, legal approval, or "
    "real-world validation."
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
        r"dash_v081_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def false_claim_hits(payload: Any) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    phrases = [
        "security certified",
        "external security certification complete",
        "production auth complete",
        "compliance approved",
        "legal approved",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in text]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_multi_client_isolation_v084", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.84 isolation runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.84",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Multi-Client Isolation Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V084,
        "truth_label": "controlled synthetic multi-client isolation evidence only",
        "clients_tested": runner_public.get("clients_tested"),
        "allowed_path_results": runner_public.get("allowed_path_results"),
        "blocked_cross_access_results": runner_public.get("blocked_cross_access_results"),
        "isolation_summary": runner_public.get("isolation_summary"),
        "remaining_gaps": ["durable hosted persistence", "external alpha testing"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "restricted_note": "No raw API keys or raw dashboard tokens are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.84 Multi-Client Isolation Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        f"Clients tested: {', '.join(public_report.get('clients_tested') or [])}",
        "",
        f"Boundary: {BOUNDARY_V084}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Commands", "", "- RUN: python examples/run_multi_client_isolation_v084.py", "- RUN: python examples/audit_v084_multi_client_isolation.py", ""])
    return "\n".join(lines)


def status(summary: dict[str, Any], path: str) -> Any:
    current: Any = summary
    for part in path.split("."):
        current = current.get(part) if isinstance(current, dict) else None
    return current


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v083 = read_json(V083_PUBLIC)
    runner_source = read_text(RUNNER_PATH)
    lifecycle_source = read_text(LIFECYCLE_PATH)

    add_check(checks, "v083_evidence_exists", V083_PUBLIC.exists(), V083_PUBLIC.as_posix())
    add_check(checks, "v083_storage_boundary_passed", v083.get("result") == "PASS" and v083.get("durable_storage_verified") is False, v083.get("result"))
    add_check(checks, "multi_client_runner_exists", RUNNER_PATH.exists(), RUNNER_PATH.as_posix())
    add_check(checks, "runner_creates_multiple_clients", 'create_client(api, "A")' in runner_source and 'create_client(api, "B")' in runner_source, None)
    add_check(checks, "usage_helper_scopes_client_summary", "client_usage_events" in lifecycle_source and '"by_client": {client_id:' in lifecycle_source, None)

    runner = load_runner_module()
    runner_public, runner_private, smoke_report, runner_checks = runner.run_smoke()
    runner.write_json(runner.PUBLIC_REPORT, runner_public)
    runner.write_json(runner.PRIVATE_REPORT, runner_private)
    runner.write_json(runner.SMOKE_REPORT, smoke_report)
    runner.SCORECARD.write_text(runner.build_scorecard(runner_public, runner_checks), encoding="utf-8")

    blocked = runner_public.get("blocked_cross_access_results", {})
    isolation = runner_public.get("isolation_summary", {})
    add_check(checks, "client_a_allowed_path_works", any(check["name"] == "client_a_allowed_path_works" and check["passed"] for check in runner_checks), None)
    add_check(checks, "client_b_allowed_path_works", any(check["name"] == "client_b_allowed_path_works" and check["passed"] for check in runner_checks), None)
    add_check(checks, "client_a_cannot_access_client_b_vault", blocked.get("client_a_key_client_b_vault", {}).get("error_code") == "vault_denied", blocked.get("client_a_key_client_b_vault"))
    add_check(checks, "client_a_cannot_access_client_b_namespace", blocked.get("client_a_key_client_b_namespace", {}).get("error_code") == "namespace_denied", blocked.get("client_a_key_client_b_namespace"))
    add_check(checks, "client_a_dashboard_token_cannot_access_client_b", blocked.get("client_a_dashboard_token_client_b", {}).get("error_code") == "client_scope_denied", blocked.get("client_a_dashboard_token_client_b"))
    add_check(checks, "client_b_cannot_access_client_a_report", blocked.get("client_b_key_client_a_report", {}).get("error_code") == "report_not_found", blocked.get("client_b_key_client_a_report"))
    add_check(checks, "wrong_client_id_blocked", blocked.get("wrong_client_id_valid_key", {}).get("error_code") == "key_client_mismatch", blocked.get("wrong_client_id_valid_key"))
    add_check(checks, "wrong_vault_id_blocked", blocked.get("wrong_vault_id_valid_key", {}).get("error_code") == "vault_denied", blocked.get("wrong_vault_id_valid_key"))
    add_check(checks, "wrong_namespace_blocked", blocked.get("wrong_namespace_valid_key", {}).get("error_code") == "namespace_denied", blocked.get("wrong_namespace_valid_key"))
    add_check(checks, "revoked_key_blocked", blocked.get("revoked_key", {}).get("error_code") == "revoked_key", blocked.get("revoked_key"))
    add_check(checks, "missing_key_blocked", blocked.get("missing_key", {}).get("error_code") == "missing_key", blocked.get("missing_key"))
    add_check(checks, "usage_logs_scoped_per_client", isolation.get("usage_logs_scoped") is True, isolation)
    add_check(checks, "request_logs_scoped_per_client", isolation.get("request_logs_scoped") is True, isolation)
    add_check(checks, "reports_scoped_per_client", isolation.get("reports_scoped") is True, isolation)
    add_check(checks, "dashboard_state_scoped_per_client", isolation.get("dashboard_state_scoped") is True, isolation)
    add_check(checks, "public_reports_contain_no_secrets", not contains_secret_pattern(runner_public), None)
    add_check(checks, "no_real_client_data_used", any(check["name"] == "no_real_client_data_used" and check["passed"] for check in runner_checks), None)
    add_check(checks, "no_false_certification_or_production_claim", not false_claim_hits(runner_public), false_claim_hits(runner_public))
    add_check(checks, "runner_result_passed", runner_public.get("result") == "PASS", runner_public.get("result"))

    public_report = build_public_report(checks, runner_public)
    add_check(checks, "audit_public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "audit_public_report_has_no_false_claims", not false_claim_hits(public_report), false_claim_hits(public_report))

    public_report = build_public_report(checks, runner_public)
    private_report = build_private_report(public_report, checks, runner_public)
    return public_report, private_report, smoke_report, checks


def main() -> int:
    public_report, private_report, smoke_report, checks = run_audit()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.84 Multi-Client Isolation Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Clients tested: {', '.join(public_report.get('clients_tested') or [])}")
    print(f"A key to B vault: {status(public_report, 'blocked_cross_access_results.client_a_key_client_b_vault.error_code')}")
    print(f"A dashboard to B: {status(public_report, 'blocked_cross_access_results.client_a_dashboard_token_client_b.error_code')}")
    print(f"B key to A report: {status(public_report, 'blocked_cross_access_results.client_b_key_client_a_report.error_code')}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
