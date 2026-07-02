"""Audit V0.89 Whop offer and access-funnel readiness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.run_whop_offer_access_funnel_v089 import (
    PRIVATE_REPORT,
    PUBLIC_REPORT,
    SCORECARD,
    SMOKE_REPORT,
    contains_secret,
    run_smoke,
    scorecard,
    write_json,
)


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run_frontend(command: str) -> dict[str, Any]:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    result = subprocess.run(
        [executable, "run", command],
        cwd=FRONTEND,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return {"passed": result.returncode == 0, "returncode": result.returncode, "tail": output[-1800:]}


def main() -> int:
    checks: list[dict[str, Any]] = []
    v088 = ROOT / "reports" / "v088" / "public_api_client_dashboard_v088.json"
    add(checks, "v088_dashboard_evidence_exists", v088.exists())

    public_report, private_report, smoke_report, runner_checks = run_smoke()
    add(checks, "v089_runner_passes", public_report["result"] == "PASS")
    add(checks, "offer_route_exists", (FRONTEND / "app" / "whop" / "page.tsx").exists())
    add(checks, "offer_model_exists", (ROOT / "prmr" / "product" / "whop_offer_v089.py").exists())
    add(checks, "setup_docs_exist", (ROOT / "docs" / "whop_offer_access_funnel_v089.md").exists())
    add(
        checks,
        "external_state_is_not_falsely_claimed",
        smoke_report["external_state"]
        == {
            "whop_product_verified": False,
            "checkout_link_verified": False,
            "payment_verified": False,
            "webhook_verified": False,
        },
    )
    add(checks, "public_report_is_secret_safe", not contains_secret(public_report))

    typecheck = run_frontend("typecheck")
    add(checks, "frontend_typecheck_passes", typecheck["passed"], typecheck["tail"])
    build = run_frontend("build")
    add(checks, "frontend_build_passes", build["passed"], build["tail"])

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    audit = {
        "version": "0.89",
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "checks": checks,
        "runner_checks_passed": sum(1 for check in runner_checks if check["passed"]),
        "runner_checks_total": len(runner_checks),
        "frontend": {
            "typecheck": {"passed": typecheck["passed"], "returncode": typecheck["returncode"]},
            "build": {"passed": build["passed"], "returncode": build["returncode"]},
        },
    }
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, {**private_report, "audit": audit})
    write_json(SMOKE_REPORT, {**smoke_report, "audit_result": result})
    SCORECARD.write_text(
        scorecard(public_report, runner_checks)
        + "\n## Independent audit\n\n"
        + f"- Result: {result}\n"
        + f"- Passed checks: {passed}/{total}\n"
        + f"- Frontend typecheck: {'PASS' if typecheck['passed'] else 'FAIL'}\n"
        + f"- Frontend build: {'PASS' if build['passed'] else 'FAIL'}\n",
        encoding="utf-8",
    )

    print("PRMR Memory Core V0.89 Whop Offer + Access Funnel Audit")
    print(f"Runner result: {public_report['result']}")
    print(f"Frontend typecheck: {'PASS' if typecheck['passed'] else 'FAIL'}")
    print(f"Frontend build: {'PASS' if build['passed'] else 'FAIL'}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        for check in checks:
            if not check["passed"]:
                print(f"FAIL: {check['name']}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
