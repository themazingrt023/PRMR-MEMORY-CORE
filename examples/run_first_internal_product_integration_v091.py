"""Run V0.91 first internal server-side PRMR integration."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.integrations.internal_product_client_v091 import (
    BOUNDARY_V091,
    InternalPRMRClientV091,
    PRMRClientConfig,
)
from prmr.product.api_config_v075 import PRMRAPIConfig
from prmr.product.api_server_v076 import create_app
from prmr.product.client_api_dashboard_v088 import ClientAPIDashboardV088
from prmr.product.hosted_api_wrapper_v075 import PRMRHostedAPIWrapper


REPORT_DIR = ROOT / "reports" / "v091"
PUBLIC_REPORT = REPORT_DIR / "public_first_internal_product_integration_v091.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_first_internal_product_integration_v091.json"
SMOKE_REPORT = REPORT_DIR / "first_internal_product_integration_smoke_v091.json"
SCORECARD = REPORT_DIR / "scorecard_v091.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def synthetic_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_v091_internal_001",
            "user_id": "synthetic_afternum_internal",
            "type": "architecture_decision",
            "content": "The internal product integration will use a server-side PRMR client and synthetic events only.",
            "timestamp": "2026-07-01T20:00:00Z",
            "timestamp_index": 1,
        },
        {
            "event_id": "evt_v091_internal_002",
            "user_id": "synthetic_afternum_internal",
            "type": "security_boundary",
            "content": "The copy-once key moves through a temporary private environment file and never enters public output.",
            "timestamp": "2026-07-01T20:05:00Z",
            "timestamp_index": 2,
        },
        {
            "event_id": "evt_v091_internal_003",
            "user_id": "synthetic_afternum_internal",
            "type": "current_state",
            "content": "The integration can now ingest, reconstruct, explain, report, and read scoped usage through HTTP.",
            "timestamp": "2026-07-01T20:10:00Z",
            "timestamp_index": 3,
        },
    ]


def contains_credential(payload: Any, raw_key: str | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if raw_key and raw_key in text:
        return True
    patterns = [
        r"\bprmr_alpha_dev_[a-f0-9]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_.-]{20,}",
        r'"PRMR_API_KEY"\s*:\s*"[^<][^"]{12,}"',
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def response_summary(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {})
    return {
        "status_code": result.get("status_code"),
        "status": body.get("status"),
        "operation": body.get("operation"),
        "packet_id_present": bool(body.get("packet_id")),
        "report_id_present": bool(body.get("report_id")),
        "public_safe": body.get("public_safe"),
        "error_code": body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else None,
    }


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    env_path_after: Path | None = None
    raw_key_for_scan = ""
    with tempfile.TemporaryDirectory(prefix="prmr-v091-", ignore_cleanup_errors=True) as temp_dir:
        temp = Path(temp_dir)
        storage_path = temp / "internal-integration.sqlite"
        config = PRMRAPIConfig(
            api_mode="local_alpha",
            storage_path=storage_path,
            synthetic_only=True,
            public_reports_dir=temp / "public",
            private_reports_dir=temp / "private",
            allowed_alpha_mode=True,
            default_max_events_per_day=100,
            default_max_packets_per_day=50,
            default_max_reports_per_day=25,
            allowed_origins=["http://localhost:3000"],
        )

        dashboard = ClientAPIDashboardV088()
        client_id = "client_v091_afternum_internal"
        vault_id = "vault_v091_afternum_internal"
        approved = dashboard.approve_synthetic_client(
            client_id=client_id,
            organisation="Afternum Internal Synthetic Integration",
            vault_id=vault_id,
        )
        created = dashboard.create_api_key(
            client_id=client_id,
            label="Afternum internal product integration",
        )
        raw_key = str(created["raw_api_key"])
        raw_key_for_scan = raw_key
        add(checks, "v088_approved_client_and_copy_once_key_created", approved["ok"] and created["returned_once"] is True)

        wrapper = PRMRHostedAPIWrapper(config=config, reset_storage=True)
        wrapper.api.lifecycle = dashboard.lifecycle
        wrapper.persist_identity_state()
        app = create_app(wrapper=wrapper, config=config)

        env_path = temp / ".env"
        env_path_after = env_path
        env_path.write_text(
            "\n".join(
                [
                    "PRMR_API_BASE_URL=http://testserver",
                    f"PRMR_API_KEY={raw_key}",
                    f"PRMR_CLIENT_ID={client_id}",
                    f"PRMR_VAULT_ID={vault_id}",
                    "PRMR_NAMESPACE=default",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        add(
            checks,
            "credential_env_is_temporary_and_outside_repo",
            env_path.exists() and not env_path.is_relative_to(ROOT),
            {"inside_repo": env_path.is_relative_to(ROOT)},
        )
        environment = parse_env_file(env_path)
        client_config = PRMRClientConfig.from_environment(environment)
        add(
            checks,
            "server_side_environment_loads_complete_scope",
            client_config.client_id == client_id
            and client_config.vault_id == vault_id
            and client_config.namespace == "default",
        )

        with TestClient(app) as http_client:
            internal_client = InternalPRMRClientV091(client_config, http_client=http_client)
            workflow = internal_client.run_continuity_workflow(synthetic_events())

        route_names = ["ingest", "packet", "reconstruct", "explain", "least_harm", "report", "usage"]
        add(checks, "health_route_works", workflow["health"]["status_code"] == 200)
        add(
            checks,
            "all_scoped_http_routes_succeed",
            all(workflow[name]["status_code"] == 200 for name in route_names),
            {name: workflow[name]["status_code"] for name in route_names},
        )
        add(
            checks,
            "event_ingest_accepts_all_internal_events",
            workflow["ingest"]["body"].get("accepted_event_count") == len(synthetic_events()),
            {"accepted": workflow["ingest"]["body"].get("accepted_event_count")},
        )
        add(
            checks,
            "continuity_packet_and_reconstruction_exist",
            bool(workflow["packet_id"])
            and bool(workflow["reconstruct"]["body"].get("reconstructable_state")),
        )
        add(
            checks,
            "explanation_and_least_harm_outputs_exist",
            bool(workflow["explain"]["body"].get("explanation"))
            and bool(workflow["least_harm"]["body"].get("recommended_action")),
        )
        add(
            checks,
            "owned_public_report_is_readable",
            bool(workflow["report_id"])
            and workflow["report"]["body"].get("report", {}).get("public_safe") is True,
        )
        usage = workflow["usage"]["body"].get("usage", {})
        add(
            checks,
            "scoped_usage_is_visible",
            usage.get("client_id") == client_id
            and usage.get("allowed_request_count", 0) >= 1,
            {"client_id": usage.get("client_id"), "allowed": usage.get("allowed_request_count")},
        )
        safe_dashboard_state = dashboard.dashboard_state(client_id=client_id)
        add(
            checks,
            "dashboard_state_retains_preview_not_credential",
            raw_key not in json.dumps(safe_dashboard_state, sort_keys=True)
            and safe_dashboard_state["dashboard"]["credential_values_exposed"] is False,
        )
        add(
            checks,
            "workflow_outputs_do_not_echo_credential",
            not contains_credential(workflow, raw_key),
        )

        public_workflow = {
            "scope": workflow["scope"],
            "routes": {name: response_summary(workflow[name]) for name in route_names},
            "health_status": workflow["health"]["status_code"],
            "event_count": len(synthetic_events()),
            "packet_id_present": bool(workflow["packet_id"]),
            "report_id_present": bool(workflow["report_id"]),
            "usage": {
                "client_id": usage.get("client_id"),
                "allowed_request_count": usage.get("allowed_request_count"),
                "blocked_request_count": usage.get("blocked_request_count"),
            },
            "credential_value_exposed": False,
        }
        private_trace = {
            "public_workflow": public_workflow,
            "temporary_env_file_used": True,
            "temporary_env_inside_repo": False,
            "dashboard_key_list": dashboard.list_api_keys(client_id=client_id),
            "raw_credential_retained": False,
        }
    add(
        checks,
        "temporary_env_is_removed_after_run",
        env_path_after is not None and not env_path_after.exists(),
    )
    hosted_vars = [
        os.getenv("PRMR_INTERNAL_HOSTED_API_URL"),
        os.getenv("PRMR_INTERNAL_HOSTED_API_KEY"),
        os.getenv("PRMR_INTERNAL_HOSTED_CLIENT_ID"),
        os.getenv("PRMR_INTERNAL_HOSTED_VAULT_ID"),
        os.getenv("PRMR_INTERNAL_HOSTED_NAMESPACE"),
    ]
    hosted_status = "NOT_RUN_NEEDS_INTERNAL_SCOPE"
    add(
        checks,
        "hosted_status_is_reported_honestly",
        hosted_status == "NOT_RUN_NEEDS_INTERNAL_SCOPE" and not all(hosted_vars),
        {"hosted_status": hosted_status},
    )

    provisional = {
        "version": "0.91",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "First Internal Product Integration",
        "truth_label": "local controlled synthetic server-side PRMR integration evidence only",
        "boundary": BOUNDARY_V091,
        "integration": public_workflow,
        "hosted_internal_integration_status": hosted_status,
        "external_client_evidence": False,
    }
    add(checks, "public_report_contains_no_credential", not contains_credential(provisional, raw_key_for_scan))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public_report = {
        **provisional,
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
    }
    private_report = {
        **public_report,
        "public_safe": False,
        "checks": checks,
        "trace": private_trace,
        "restricted_note": "The private trace excludes the generated key and temporary environment contents.",
    }
    smoke_report = {
        "version": "0.91",
        "result": result,
        "public_safe": True,
        "boundary": BOUNDARY_V091,
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
        "local_http_integration": "PASS" if result == "PASS" else "NEEDS_WORK",
        "hosted_internal_integration": hosted_status,
    }
    return public_report, private_report, smoke_report, checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.91 First Internal Product Integration",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V091}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(
        [
            "",
            "## Evidence levels",
            "",
            "- Local controlled internal HTTP integration: PASS if all checks pass",
            "- Hosted dedicated internal scope: NOT RUN",
            "- External client evidence: NONE",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    public_report, private_report, smoke_report, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")
    print("PRMR Memory Core V0.91 First Internal Product Integration")
    print("Copy-once key -> temporary .env -> server-side HTTP client")
    print(f"Local HTTP integration: {smoke_report['local_http_integration']}")
    print(f"Hosted internal integration: {smoke_report['hosted_internal_integration']}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
