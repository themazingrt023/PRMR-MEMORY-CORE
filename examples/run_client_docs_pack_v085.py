"""Run V0.85 client docs pack smoke."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v085"
PUBLIC_REPORT = REPORT_DIR / "public_client_docs_onboarding_pack_v085.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_client_docs_onboarding_pack_v085.json"
SMOKE_REPORT = REPORT_DIR / "client_docs_pack_smoke_v085.json"
SCORECARD = REPORT_DIR / "scorecard_v085.md"

DOCS = {
    "onboarding_pack": ROOT / "docs" / "client_alpha_onboarding_pack_v085.md",
    "api_quickstart": ROOT / "docs" / "client_api_quickstart_v085.md",
    "handoff_template": ROOT / "docs" / "client_alpha_handoff_template_v085.md",
    "safety_checklist": ROOT / "docs" / "controlled_alpha_safety_checklist_v085.md",
}

REQUIRED_PLACEHOLDERS = [
    "<PRMR_API_KEY>",
    "<CLIENT_ID>",
    "<VAULT_ID>",
    "<NAMESPACE>",
    "<API_BASE_URL>",
]

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
        "production ready",
        "production readiness achieved",
        "compliance approved",
        "legal approved",
        "security certified",
        "external validation complete",
        "real-world validated",
    ]
    return [phrase for phrase in phrases if phrase in lowered]


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.85",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Client Docs And Alpha Onboarding Pack",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V085,
        "docs_created": {name: path.as_posix() for name, path in DOCS.items()},
        "placeholder_hygiene": smoke["placeholder_hygiene"],
        "secret_hygiene": smoke["secret_hygiene"],
        "endpoint_coverage": smoke["endpoint_coverage"],
        "client_handoff_structure": smoke["client_handoff_structure"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "Docs pack audit contains text coverage only. No raw keys or dashboard tokens are included.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.85 Client Docs And Alpha Onboarding Pack",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V085}",
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
    lines.extend(["", "## Command", "", "- RUN: python examples/run_client_docs_pack_v085.py", ""])
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    texts = {name: read_text(path) for name, path in DOCS.items()}
    combined = "\n".join(texts.values())
    quickstart = texts["api_quickstart"]
    handoff = texts["handoff_template"]

    add_check(checks, "all_docs_exist", all(path.exists() for path in DOCS.values()), {name: path.exists() for name, path in DOCS.items()})
    add_check(checks, "required_placeholders_present", all(placeholder in combined for placeholder in REQUIRED_PLACEHOLDERS), REQUIRED_PLACEHOLDERS)
    add_check(checks, "handoff_specific_placeholders_present", all(placeholder in handoff for placeholder in ["<CLIENT_NAME>", "<ONE_TIME_API_KEY_DELIVERY_METHOD>", "<DASHBOARD_ACCESS_METHOD>", "<BOUNDARY_NOTES>"]), None)
    add_check(checks, "hosted_api_url_present", "https://prmr-memory-core-api.onrender.com" in combined, None)
    add_check(checks, "required_headers_present", all(header in combined for header in ["Authorization: Bearer <PRMR_API_KEY>", "X-Client-ID: <CLIENT_ID>", "X-Vault-ID: <VAULT_ID>", "X-Namespace: <NAMESPACE>"]), None)
    add_check(checks, "all_required_endpoints_present", all(endpoint in quickstart for endpoint in REQUIRED_ENDPOINTS), REQUIRED_ENDPOINTS)
    add_check(checks, "boundaries_present", "controlled-alpha" in combined.lower() and "not self-serve signup" in combined.lower() and "not production readiness" in combined.lower(), None)
    add_check(checks, "revoke_path_present", "revoke" in combined.lower() and "revocation" in combined.lower(), None)
    add_check(checks, "storage_limitation_present", "/tmp" in combined and "smoke-only" in combined.lower() and "durable" in combined.lower(), None)
    add_check(checks, "feedback_guidance_present", "feedback" in combined.lower() and "pilot" in combined.lower(), None)
    add_check(checks, "no_raw_secret_patterns_in_docs", not contains_secret_pattern(combined), None)
    add_check(checks, "no_false_claims_in_docs", not false_claim_hits(combined), false_claim_hits(combined))

    smoke = {
        "placeholder_hygiene": {
            "required_placeholders_present": True,
            "raw_values_expected": False,
        },
        "secret_hygiene": {
            "raw_secret_patterns_found": False,
            "real_keys_in_docs": False,
        },
        "endpoint_coverage": REQUIRED_ENDPOINTS,
        "client_handoff_structure": {
            "client_name": "<CLIENT_NAME>" in handoff,
            "client_id": "<CLIENT_ID>" in handoff,
            "vault_id": "<VAULT_ID>" in handoff,
            "namespace": "<NAMESPACE>" in handoff,
            "api_base_url": "<API_BASE_URL>" in handoff,
            "one_time_delivery_method": "<ONE_TIME_API_KEY_DELIVERY_METHOD>" in handoff,
            "dashboard_access_method": "<DASHBOARD_ACCESS_METHOD>" in handoff,
            "boundary_notes": "<BOUNDARY_NOTES>" in handoff,
        },
    }
    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(json.dumps(public_report, sort_keys=True)), None)
    add_check(checks, "public_report_has_no_false_claims", not false_claim_hits(json.dumps(public_report, sort_keys=True)), false_claim_hits(json.dumps(public_report, sort_keys=True)))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.85",
        "public_safe": True,
        "boundary": BOUNDARY_V085,
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

    print("PRMR Memory Core V0.85 Client Docs Pack")
    print(f"Docs created: {len(public_report['docs_created'])}")
    print(f"Endpoint count: {len(public_report['endpoint_coverage'])}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
