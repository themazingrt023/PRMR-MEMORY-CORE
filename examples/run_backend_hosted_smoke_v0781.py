"""V0.78.1 helper for running hosted backend smoke after deployment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "v0781"
HELPER_REPORT = REPORT_DIR / "backend_hosted_smoke_helper_v0781.json"
V078_RUNNER = ROOT / "examples" / "run_live_hosted_api_smoke_v078.py"
V078_PUBLIC = ROOT / "reports" / "v078" / "public_live_hosted_api_smoke_v078.json"

BOUNDARY_V0781 = (
    "V0.78.1 is backend host deployment execution prep. Hosted API access is "
    "only claimable after a real deployed backend URL passes V0.78 smoke. This "
    "helper does not issue keys, does not use real client data, and does not "
    "claim production readiness, billing, approval, certification, or external validation."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_v078() -> dict[str, Any]:
    completed = subprocess.run(
        ["python", str(V078_RUNNER)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=240,
        check=False,
    )
    return {
        "command": f"python {V078_RUNNER}",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def read_v078_public() -> dict[str, Any]:
    if not V078_PUBLIC.exists():
        return {}
    return json.loads(V078_PUBLIC.read_text(encoding="utf-8"))


def main() -> int:
    hosted_url = os.getenv("PRMR_HOSTED_API_URL", "").strip()
    if not hosted_url:
        payload = {
            "version": "0.78.1",
            "result": "NEEDS_HOSTED_URL",
            "public_safe": True,
            "boundary": BOUNDARY_V0781,
            "hosted_url_present": False,
            "next_step": "Deploy the FastAPI backend, copy the hosted backend URL, set PRMR_HOSTED_API_URL, then rerun this helper.",
            "exact_next_command": '$env:PRMR_HOSTED_API_URL="https://YOUR-HOSTED-BACKEND-URL"; python examples/run_backend_hosted_smoke_v0781.py',
        }
        write_json(HELPER_REPORT, payload)
        print("PRMR Memory Core V0.78.1 Backend Hosted Smoke Helper")
        print("Hosted URL present: False")
        print("Next step: set PRMR_HOSTED_API_URL to the deployed backend URL.")
        print(f"Report: {HELPER_REPORT.as_posix()}")
        print("Result: NEEDS_HOSTED_URL")
        return 0

    command_result = run_v078()
    v078_public = read_v078_public()
    payload = {
        "version": "0.78.1",
        "result": v078_public.get("result", "NEEDS_WORK"),
        "public_safe": True,
        "boundary": BOUNDARY_V0781,
        "hosted_url_present": True,
        "v078_smoke_result": v078_public.get("result"),
        "hosted_client_access_verified": v078_public.get("hosted_client_access_verified", False),
        "full_controlled_hosted_smoke_verified": v078_public.get("full_controlled_hosted_smoke_verified", False),
        "command": command_result["command"],
        "command_returncode": command_result["returncode"],
        "command_passed": command_result["passed"],
        "command_output_tail": command_result["output"][-2000:],
    }
    write_json(HELPER_REPORT, payload)

    print("PRMR Memory Core V0.78.1 Backend Hosted Smoke Helper")
    print("Hosted URL present: True")
    print(f"V0.78 smoke result: {payload['v078_smoke_result']}")
    print(f"Hosted client access verified: {payload['hosted_client_access_verified']}")
    print(f"Report: {HELPER_REPORT.as_posix()}")
    print(f"Result: {payload['result']}")
    return 0 if payload["result"] in {"PASS_BASIC_HOSTED_SMOKE", "PASS_FULL_CONTROLLED_HOSTED_SMOKE", "NEEDS_HOSTED_URL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
