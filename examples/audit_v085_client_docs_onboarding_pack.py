"""V0.85 client docs and onboarding pack audit."""

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

REPORT_DIR = ROOT / "reports" / "v085"
PUBLIC_REPORT = REPORT_DIR / "public_client_docs_onboarding_pack_v085.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_client_docs_onboarding_pack_v085.json"
SMOKE_REPORT = REPORT_DIR / "client_docs_pack_smoke_v085.json"
SCORECARD = REPORT_DIR / "scorecard_v085.md"

V084_PUBLIC = ROOT / "reports" / "v084" / "public_multi_client_isolation_v084.json"
RUNNER_PATH = ROOT / "examples" / "run_client_docs_pack_v085.py"

DOCS = {
    "onboarding_pack": ROOT / "docs" / "client_alpha_onboarding_pack_v085.md",
    "api_quickstart": ROOT / "docs" / "client_api_quickstart_v085.md",
    "handoff_template": ROOT / "docs" / "client_alpha_handoff_template_v085.md",
    "safety_checklist": ROOT / "docs" / "controlled_alpha_safety_checklist_v085.md",
}

REQUIRED_ENDPOINTS = [
    "GET /health",
    "POST /v1/events/ingest",
    "POST /v1/continuity/packet",
    "POST /v1/memory/reconstruct",
    "POST /v1/explain",
    "POST /v1/actions/least-harm",
    "GET /v1/reports/{report_id}",
    "GET /v1/usage",
    "GET /v1/dashboard/state",
]

BOUNDARY_V085 = (
    "V0.85 is controlled-alpha onboarding documentation and client-readiness "
    "evidence only. It is not self-serve signup, billing, production readiness, "
    "external validation, compliance approval, legal approval, external security "
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
        r"dash_v08[12]_[a-f0-9]{16,}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def false_claim_hits(text: str) -> list[str]:
    lowered = text.lower()
    phrases = [
        "self-serve signup enabled",
        "billing enabled",
        "production readiness achieved",
        "compliance approved",
        "legal approved",
        "security certified",
        "external validation complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in lowered]


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_client_docs_pack_v085", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load V0.85 docs runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_public_report(checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check["passed"]]
    return {
        "version": "0.85",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Client Docs Onboarding Pack Audit",
        "result": "PASS" if not failures else "NEEDS_WORK",
        "runner_result": runner_public.get("result"),
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_total": len(checks),
        "public_safe": True,
        "boundary": BOUNDARY_V085,
        "docs_created": runner_public.get("docs_created"),
        "endpoint_coverage": runner_public.get("endpoint_coverage"),
        "client_handoff_structure": runner_public.get("client_handoff_structure"),
        "placeholder_hygiene": runner_public.get("placeholder_hygiene"),
        "secret_hygiene": runner_public.get("secret_hygiene"),
        "remaining_gaps": ["first external alpha test", "durable hosted persistence", "production auth"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], runner_public: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "runner_public_summary": runner_public,
        "restricted_note": "No raw keys or dashboard tokens are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.85 Client Docs Onboarding Pack Audit",
        "",
        f"Result: {public_report['result']}",
        f"Runner result: {public_report['runner_result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V085}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Commands", "", "- RUN: python examples/run_client_docs_pack_v085.py", "- RUN: python examples/audit_v085_client_docs_onboarding_pack.py", ""])
    return "\n".join(lines)


def run_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    v084 = read_json(V084_PUBLIC)
    texts = {name: read_text(path) for name, path in DOCS.items()}
    combined = "\n".join(texts.values())
    quickstart = texts["api_quickstart"]

    add_check(checks, "v084_evidence_exists", V084_PUBLIC.exists(), V084_PUBLIC.as_posix())
    add_check(checks, "v084_multi_client_isolation_passed", v084.get("result") == "PASS" and v084.get("isolation_summary", {}).get("usage_logs_scoped") is True, v084.get("result"))
    add_check(checks, "all_v085_docs_exist", all(path.exists() for path in DOCS.values()), {name: path.exists() for name, path in DOCS.items()})
    add_check(checks, "quickstart_includes_all_required_endpoints", all(endpoint in quickstart for endpoint in REQUIRED_ENDPOINTS), REQUIRED_ENDPOINTS)
    add_check(checks, "placeholders_used_instead_of_real_secrets", all(placeholder in combined for placeholder in ["<PRMR_API_KEY>", "<CLIENT_ID>", "<VAULT_ID>", "<NAMESPACE>", "<API_BASE_URL>"]), None)
    add_check(checks, "no_raw_api_keys_or_dashboard_tokens_in_docs", not contains_secret_pattern(combined), None)
    add_check(checks, "boundary_wording_present", "controlled-alpha" in combined.lower() and "not self-serve signup" in combined.lower() and "not production readiness" in combined.lower(), None)
    add_check(checks, "storage_limitation_present", "/tmp" in combined and "smoke-only" in combined.lower() and "durable" in combined.lower(), None)
    add_check(checks, "revoke_process_present", "revoke" in combined.lower() and "revocation" in combined.lower(), None)
    add_check(checks, "no_false_claims_in_docs", not false_claim_hits(combined), false_claim_hits(combined))

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

    print("PRMR Memory Core V0.85 Client Docs Onboarding Pack Audit")
    print(f"Runner result: {public_report.get('runner_result')}")
    print(f"Docs created: {len(public_report.get('docs_created') or {})}")
    print(f"Endpoint count: {len(public_report.get('endpoint_coverage') or [])}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
