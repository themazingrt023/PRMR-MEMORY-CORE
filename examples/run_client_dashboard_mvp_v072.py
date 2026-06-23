"""Run V0.72 client dashboard MVP aggregation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.client_dashboard_v072 import (  # noqa: E402
    REPORT_DIR,
    build_scorecard,
    generate_dashboard_reports,
    write_json,
)


DASHBOARD_DATA = REPORT_DIR / "dashboard_data_v072.json"
PUBLIC_REPORT = REPORT_DIR / "public_client_dashboard_mvp_v072.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_client_dashboard_mvp_v072.json"
SCORECARD = REPORT_DIR / "scorecard_v072.md"


def main() -> int:
    dashboard_data, public_report, private_report, checks = generate_dashboard_reports()

    write_json(DASHBOARD_DATA, dashboard_data)
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    passed = public_report["checks_passed"]
    total = public_report["checks_total"]
    result = public_report["result"]

    print("PRMR Memory Core V0.72 Client Dashboard MVP")
    print(f"Dashboard data: {DASHBOARD_DATA.as_posix()}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")

    if result != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print("Failing checks:")
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
