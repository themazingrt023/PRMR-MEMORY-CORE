"""Run V0.73 end-to-end API + dashboard sandbox."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.api_dashboard_sandbox_v073 import (  # noqa: E402
    REPORT_DIR,
    build_scorecard,
    run_sandbox_and_build_reports,
    write_json,
)


PUBLIC_REPORT = REPORT_DIR / "public_api_dashboard_sandbox_v073.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_api_dashboard_sandbox_v073.json"
DASHBOARD_REFRESH = REPORT_DIR / "dashboard_refresh_state_v073.json"
REQUEST_LOG = REPORT_DIR / "api_dashboard_request_log_v073.json"
SCORECARD = REPORT_DIR / "scorecard_v073.md"


def main() -> int:
    result, public_report, private_report, checks = run_sandbox_and_build_reports()
    dashboard = result["dashboard_refresh_state"]

    request_log_payload = {
        "version": "0.73",
        "boundary": public_report["boundary"],
        "demo_bridge_note": public_report["demo_bridge_note"],
        "request_log": dashboard["request_log_summary"]["rows"],
        "blocked_reasons": dashboard["request_log_summary"]["blocked_reasons"],
    }

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(DASHBOARD_REFRESH, dashboard)
    write_json(REQUEST_LOG, request_log_payload)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    passed = public_report["checks_passed"]
    total = public_report["checks_total"]
    result_status = public_report["result"]

    print("PRMR Memory Core V0.73 API + Dashboard Sandbox")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Dashboard refresh: {DASHBOARD_REFRESH.as_posix()}")
    print(f"Request log: {REQUEST_LOG.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Allowed requests: {dashboard['usage_overview']['allowed_request_count']}")
    print(f"Blocked requests: {dashboard['usage_overview']['blocked_request_count']}")
    print(f"Events received: {dashboard['memory_health_panel']['events_received']}")
    print(f"Packets generated: {dashboard['memory_health_panel']['packets_generated']}")
    print(f"Reports visible: {len(dashboard['reports_panel']['reports'])}")
    print(f"Memory health: {dashboard['memory_health_panel']['status']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result_status}")

    if result_status != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
