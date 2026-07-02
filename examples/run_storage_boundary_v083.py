"""Run V0.83 storage boundary smoke."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prmr.product.storage_mode_v083 import BOUNDARY_V083, classify_storage_mode, public_storage_health_payload


REPORT_DIR = ROOT / "reports" / "v083"
PUBLIC_REPORT = REPORT_DIR / "public_storage_boundary_v083.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_storage_boundary_v083.json"
SMOKE_REPORT = REPORT_DIR / "storage_mode_smoke_v083.json"
SCORECARD = REPORT_DIR / "scorecard_v083.md"


class FakeConfig:
    def __init__(self, api_mode: str, storage_path: str) -> None:
        self.api_mode = api_mode
        self.storage_path = Path(storage_path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    ]
    return [phrase for phrase in phrases if phrase in text]


def build_public_report(checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "version": "0.83",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Storage Boundary And Durable Hosted Storage Readiness",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V083,
        "truth_label": "storage boundary and durable-hosting readiness evidence only",
        "storage_classifications": {
            name: value["storage_mode"]
            for name, value in smoke["classifications"].items()
        },
        "current_hosted_storage_status": "hosted /tmp SQLite is ephemeral smoke storage only unless durable storage is separately configured and verified",
        "durable_storage_verified": False,
        "recommended_durable_path": "Render persistent disk at /var/data for near-term SQLite, then managed Postgres before broader external alpha.",
        "smoke_summary": smoke["summary"],
    }


def build_private_report(public_report: dict[str, Any], checks: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "smoke": smoke,
        "restricted_note": "No secrets or client data are included. Storage paths are configuration evidence only.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.83 Storage Boundary",
        "",
        f"Result: {public_report['result']}",
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
    lines.extend(["", "## Command", "", "- RUN: python examples/run_storage_boundary_v083.py", ""])
    return "\n".join(lines)


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    classifications = {
        "local_sqlite": classify_storage_mode(storage_path="reports/v083/prmr_storage_v083.sqlite", api_mode="local_alpha"),
        "hosted_tmp": classify_storage_mode(storage_path="/tmp/prmr_api_server_v083.sqlite", api_mode="hosted_alpha"),
        "missing_path": classify_storage_mode(storage_path="", api_mode="hosted_alpha"),
        "durable_candidate": classify_storage_mode(
            storage_path="/var/data/prmr_api_server.sqlite",
            api_mode="hosted_alpha",
            storage_mode_override="hosted_durable_sqlite",
            durable_storage_verified=False,
        ),
        "managed_database_planned": classify_storage_mode(
            storage_path="postgres://planned-managed-database-placeholder",
            api_mode="hosted_alpha",
            storage_mode_override="hosted_managed_database_planned",
            durable_storage_verified=False,
        ),
    }
    tmp_health = public_storage_health_payload(FakeConfig("hosted_alpha", "/tmp/prmr_api_server_v083.sqlite"))
    local_health = public_storage_health_payload(FakeConfig("local_alpha", "reports/v083/prmr_storage_v083.sqlite"))

    add_check(checks, "local_sqlite_classified", classifications["local_sqlite"]["storage_mode"] == "local_sqlite", classifications["local_sqlite"])
    add_check(checks, "hosted_tmp_classified_ephemeral", classifications["hosted_tmp"]["storage_mode"] == "hosted_ephemeral_sqlite" and classifications["hosted_tmp"]["ephemeral_storage"] is True, classifications["hosted_tmp"])
    add_check(checks, "missing_path_unknown_safe", classifications["missing_path"]["storage_mode"] == "unknown_storage_mode" and classifications["missing_path"]["missing_storage_path"] is True, classifications["missing_path"])
    add_check(checks, "durable_candidate_not_verified", classifications["durable_candidate"]["storage_mode"] == "hosted_durable_sqlite" and classifications["durable_candidate"]["durable_storage_verified"] is False, classifications["durable_candidate"])
    add_check(checks, "managed_database_planned_not_completed", classifications["managed_database_planned"]["storage_mode"] == "hosted_managed_database_planned" and classifications["managed_database_planned"]["durable_storage_verified"] is False, classifications["managed_database_planned"])
    add_check(checks, "tmp_health_does_not_claim_durable", tmp_health["storage_mode"] == "hosted_ephemeral_sqlite" and tmp_health["durable_storage_verified"] is False and tmp_health["durable_storage_claim_allowed"] is False, tmp_health)
    add_check(checks, "local_health_not_hosted_durable_claim", local_health["storage_mode"] == "local_sqlite" and local_health["durable_storage_verified"] is False, local_health)

    smoke = {
        "classifications": classifications,
        "health_payloads": {
            "tmp": tmp_health,
            "local": local_health,
        },
        "summary": {
            "local_sqlite": classifications["local_sqlite"]["storage_mode"],
            "hosted_tmp": classifications["hosted_tmp"]["storage_mode"],
            "missing_path": classifications["missing_path"]["storage_mode"],
            "durable_candidate_verified": classifications["durable_candidate"]["durable_storage_verified"],
            "tmp_durable_claim_allowed": tmp_health["durable_storage_claim_allowed"],
        },
    }
    public_report = build_public_report(checks, smoke)
    add_check(checks, "public_report_contains_no_secrets", not contains_secret_pattern(public_report), None)
    add_check(checks, "public_report_has_no_false_storage_claims", not false_claim_hits(public_report), false_claim_hits(public_report))

    public_report = build_public_report(checks, smoke)
    private_report = build_private_report(public_report, checks, smoke)
    smoke_report = {
        "version": "0.83",
        "public_safe": True,
        "boundary": BOUNDARY_V083,
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

    print("PRMR Memory Core V0.83 Storage Boundary")
    print(f"Local SQLite: {public_report['storage_classifications']['local_sqlite']}")
    print(f"Hosted /tmp: {public_report['storage_classifications']['hosted_tmp']}")
    print(f"Missing path: {public_report['storage_classifications']['missing_path']}")
    print(f"Durable storage verified: {public_report['durable_storage_verified']}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Smoke report: {SMOKE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {public_report.get('checks_passed')}/{public_report.get('checks_total')}")
    print(f"Result: {public_report.get('result')}")
    return 0 if public_report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
