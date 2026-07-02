"""Run V0.92 Continuum OS approved-client provisioning and PRMR flow."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from prmr.integrations.internal_product_client_v091 import InternalPRMRClientV091, PRMRClientConfig
from prmr.product.api_config_v075 import PRMRAPIConfig
from prmr.product.api_server_v076 import create_app
from prmr.product.continuum_client_provisioning_v092 import (
    API_BASE_URL,
    BOUNDARY_V092,
    CLIENT_ID,
    CLIENT_STATUS,
    NAMESPACE,
    PRODUCT_NAME,
    VAULT_ID,
    ContinuumClientProvisioningV092,
)
from prmr.product.hosted_api_wrapper_v075 import PRMRHostedAPIWrapper


REPORT_DIR = ROOT / "reports" / "v092"
PUBLIC_REPORT = REPORT_DIR / "public_continuum_client_provisioning_v092.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_continuum_client_provisioning_v092.json"
SMOKE_REPORT = REPORT_DIR / "continuum_client_provisioning_smoke_v092.json"
PRIVATE_ENV_PACKET = REPORT_DIR / "private_continuum_env_packet_v092.json"
SCORECARD = REPORT_DIR / "scorecard_v092.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def continuum_events() -> list[dict[str, Any]]:
    event_types = [
        "mission_created",
        "mission_completed",
        "project_updated",
        "habit_completed",
        "money_action_logged",
        "sunday_reset_completed",
    ]
    return [
        {
            "event_id": f"continuum-v092-{index:03d}",
            "user_id": "synthetic_continuum_user",
            "type": event_type,
            "content": f"Synthetic Continuum OS event: {event_type.replace('_', ' ')}.",
            "timestamp": f"2026-07-01T09:{index:02d}:00Z",
            "timestamp_index": index,
        }
        for index, event_type in enumerate(event_types, start=1)
    ]


def contains_raw_key(payload: Any, raw_key: str | None = None) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    if raw_key and raw_key in text:
        return True
    patterns = [
        r"\bprmr_alpha_[A-Za-z0-9_-]{20,}\b",
        r"\bprmr_live_[A-Za-z0-9_-]{20,}\b",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_.-]{20,}",
        r'"PRMR_API_KEY"\s*:\s*"[^<][^"]{12,}"',
        r"\bdash_v[0-9]+_[A-Za-z0-9_-]{16,}\b",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def response_summary(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {})
    return {
        "status_code": result.get("status_code"),
        "status": body.get("status"),
        "operation": body.get("operation"),
        "public_safe": body.get("public_safe"),
        "packet_id_present": bool(body.get("packet_id")),
        "report_id_present": bool(body.get("report_id")),
        "error_code": body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else None,
    }


def run_smoke() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    service = ContinuumClientProvisioningV092()
    provisioned = service.provision()
    provisioning_id = str(provisioned["provisioning_id"])
    record = service.records[provisioning_id]

    add(
        checks,
        "approved_continuum_client_created",
        record.client_id == CLIENT_ID
        and record.product_name == PRODUCT_NAME
        and record.status == CLIENT_STATUS
        and record.access_runtime_status == "active",
        {"client_id": record.client_id, "status": record.status},
    )
    add(
        checks,
        "continuum_scope_created",
        record.vault_id == VAULT_ID and record.namespace == NAMESPACE,
        {"vault_id": record.vault_id, "namespace": record.namespace},
    )

    env_packet = service.one_time_env_packet(provisioning_id)
    raw_key = str(env_packet.get("PRMR_API_KEY") or "")
    second_packet = service.one_time_env_packet(provisioning_id)
    add(
        checks,
        "copy_once_alpha_key_issued",
        raw_key.startswith("prmr_alpha_")
        and env_packet["returned_once"] is True
        and second_packet["returned_once"] is False
        and second_packet["PRMR_API_KEY"] is None,
        {"prefix": "prmr_alpha_", "second_release": second_packet["returned_once"]},
    )
    add(
        checks,
        "private_hash_and_safe_preview_exist",
        bool(record.key_hash)
        and record.safe_key_preview.startswith("prmr_alpha_...")
        and raw_key not in record.safe_key_preview,
        {"safe_key_preview": record.safe_key_preview},
    )

    write_json(PRIVATE_ENV_PACKET, env_packet)
    add(
        checks,
        "private_env_packet_has_required_fields",
        env_packet["classification"] == "PRIVATE LOCAL ONLY. DO NOT COMMIT. DO NOT SHARE."
        and all(
            env_packet.get(field)
            for field in [
                "PRMR_API_BASE_URL",
                "PRMR_API_KEY",
                "PRMR_CLIENT_ID",
                "PRMR_VAULT_ID",
                "PRMR_NAMESPACE",
            ]
        )
        and env_packet["PRMR_API_BASE_URL"] == API_BASE_URL,
        {"path": PRIVATE_ENV_PACKET.as_posix()},
    )
    validation = service.validate_key(raw_key)
    add(
        checks,
        "generated_key_validates_against_protected_logic",
        validation["allowed"] is True and validation["reason"] == "allowed",
        validation,
    )

    with tempfile.TemporaryDirectory(prefix="prmr-v092-", ignore_cleanup_errors=True) as temp_dir:
        temp = Path(temp_dir)
        config = PRMRAPIConfig(
            api_mode="local_alpha",
            storage_path=temp / "continuum-v092.sqlite",
            synthetic_only=True,
            public_reports_dir=temp / "public",
            private_reports_dir=temp / "private",
            allowed_alpha_mode=True,
            default_max_events_per_day=250,
            default_max_packets_per_day=100,
            default_max_reports_per_day=100,
            allowed_origins=["http://localhost:3000"],
        )
        wrapper = PRMRHostedAPIWrapper(config=config, reset_storage=True)
        wrapper.api = service.api
        wrapper.persist_identity_state()
        app = create_app(wrapper=wrapper, config=config)
        client_config = PRMRClientConfig.from_environment(
            {
                "PRMR_API_BASE_URL": "http://testserver",
                "PRMR_API_KEY": raw_key,
                "PRMR_CLIENT_ID": CLIENT_ID,
                "PRMR_VAULT_ID": VAULT_ID,
                "PRMR_NAMESPACE": NAMESPACE,
            }
        )
        with TestClient(app) as http_client:
            continuum_client = InternalPRMRClientV091(client_config, http_client=http_client)
            workflow = continuum_client.run_continuity_workflow(continuum_events())

    routes = ["ingest", "packet", "reconstruct", "explain", "least_harm", "report", "usage"]
    add(
        checks,
        "all_required_prmr_routes_succeed",
        all(workflow[name]["status_code"] == 200 for name in routes),
        {name: workflow[name]["status_code"] for name in routes},
    )
    add(
        checks,
        "all_six_continuum_event_types_ingested",
        workflow["ingest"]["body"].get("accepted_event_count") == 6
        and {event["type"] for event in continuum_events()}
        == {
            "mission_created",
            "mission_completed",
            "project_updated",
            "habit_completed",
            "money_action_logged",
            "sunday_reset_completed",
        },
        {"accepted_event_count": workflow["ingest"]["body"].get("accepted_event_count")},
    )
    add(
        checks,
        "continuity_outputs_exist",
        bool(workflow["packet_id"])
        and bool(workflow["reconstruct"]["body"].get("reconstructable_state"))
        and bool(workflow["explain"]["body"].get("explanation"))
        and bool(workflow["least_harm"]["body"].get("recommended_action")),
    )
    add(
        checks,
        "owned_report_is_public_safe",
        bool(workflow["report_id"])
        and workflow["report"]["body"].get("report", {}).get("client_id") == CLIENT_ID
        and workflow["report"]["body"].get("report", {}).get("public_safe") is True,
    )
    usage = workflow["usage"]["body"].get("usage", {})
    add(
        checks,
        "usage_is_scoped_to_continuum_client",
        usage.get("client_id") == CLIENT_ID
        and CLIENT_ID in json.dumps(usage)
        and "client_v079_controlled_hosted" not in json.dumps(usage),
        {"client_id": usage.get("client_id"), "allowed": usage.get("allowed_request_count")},
    )

    dashboard = service.dashboard_state()
    dashboard_text = json.dumps(dashboard, sort_keys=True)
    add(
        checks,
        "dashboard_shows_continuum_scope_and_safe_preview",
        dashboard["client_overview"]["client_id"] == CLIENT_ID
        and dashboard["vaults_and_namespaces"][0]["vault_id"] == VAULT_ID
        and dashboard["api_keys"][0]["safe_key_preview"] == record.safe_key_preview
        and dashboard["credential_values_exposed"] is False
        and raw_key not in dashboard_text,
    )
    add(
        checks,
        "dashboard_usage_reports_and_memory_health_are_visible",
        dashboard["usage"]["client_id"] == CLIENT_ID
        and len(dashboard["reports"]) == 1
        and dashboard["memory_health"]["event_count"] == 6
        and dashboard["memory_health"]["reconstructable"] is True,
        {
            "report_count": len(dashboard["reports"]),
            "event_count": dashboard["memory_health"]["event_count"],
        },
    )

    public_evidence = {
        "client": service.public_record(record),
        "scope": {
            "client_id": CLIENT_ID,
            "vault_id": VAULT_ID,
            "namespace": NAMESPACE,
        },
        "key": {
            "key_id": record.key_id,
            "safe_key_preview": record.safe_key_preview,
            "prefix": "prmr_alpha_",
            "copy_once_verified": True,
            "credential_value_exposed": False,
        },
        "private_env_packet": {
            "path": PRIVATE_ENV_PACKET.as_posix(),
            "classification": env_packet["classification"],
            "contents_exposed": False,
        },
        "flow": {name: response_summary(workflow[name]) for name in routes},
        "events_tested": [event["type"] for event in continuum_events()],
        "usage": {
            "client_id": usage.get("client_id"),
            "allowed_request_count": usage.get("allowed_request_count"),
            "blocked_request_count": usage.get("blocked_request_count"),
        },
        "dashboard": {
            "client_visible": True,
            "safe_preview_only": True,
            "usage_visible": True,
            "reports_visible": True,
            "memory_health_visible": True,
        },
        "hosted_key_registration_verified": False,
        "actual_continuum_app_wired": False,
    }
    provisional_public = {
        "version": "0.92",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Continuum OS PRMR API Key Provisioning",
        "truth_label": "first internal-client provisioning evidence using local protected PRMR logic",
        "boundary": BOUNDARY_V092,
        "evidence": public_evidence,
        "public_safe": True,
    }
    private_record = service.private_record(record)
    private_report = {
        **provisional_public,
        "public_safe": False,
        "title": "Continuum OS Provisioning Private Internal Trace",
        "provisioning_record": private_record,
        "release_log": service.release_log,
        "validation": validation,
        "checks": checks,
        "restricted_note": (
            "This private trace stores the key hash and lifecycle evidence but "
            "not the raw key. The raw value exists only in the separate ignored "
            "private environment packet."
        ),
    }
    add(
        checks,
        "non_packet_reports_contain_no_raw_key",
        not contains_raw_key(provisional_public, raw_key)
        and not contains_raw_key(private_report, raw_key),
    )
    add(
        checks,
        "hosted_and_actual_app_boundaries_are_honest",
        public_evidence["hosted_key_registration_verified"] is False
        and public_evidence["actual_continuum_app_wired"] is False,
    )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    public_report = {
        **provisional_public,
        "result": result,
        "checks_passed": passed,
        "checks_total": total,
    }
    private_report.update(
        {
            "result": result,
            "checks_passed": passed,
            "checks_total": total,
            "checks": checks,
        }
    )
    smoke_report = {
        "version": "0.92",
        "result": result,
        "public_safe": True,
        "boundary": BOUNDARY_V092,
        "checks": [{"name": check["name"], "passed": check["passed"]} for check in checks],
        "local_protected_flow": "PASS" if result == "PASS" else "NEEDS_WORK",
        "hosted_key_registration": "NOT_VERIFIED",
        "continuum_os_application_wiring": "NOT_RUN",
    }
    return public_report, private_report, smoke_report, env_packet, checks


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.92 Continuum OS PRMR API Key Provisioning",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V092}",
        "",
        "## Provisioned scope",
        "",
        f"- Client: {CLIENT_ID}",
        f"- Product: {PRODUCT_NAME}",
        f"- Status: {CLIENT_STATUS}",
        f"- Vault: {VAULT_ID}",
        f"- Namespace: {NAMESPACE}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(
        [
            "",
            "## Remaining activation work",
            "",
            "- Install the key hash and scope in durable hosted PRMR storage.",
            "- Pass hosted Continuum-scoped protected-route smoke.",
            "- Transfer the one-time packet privately into the actual Continuum OS server environment.",
            "- Run Continuum OS integration evidence without real sensitive data.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    public_report, private_report, smoke_report, _, checks = run_smoke()
    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(SMOKE_REPORT, smoke_report)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")
    print("PRMR Memory Core V0.92 Continuum OS Client Provisioning")
    print(f"Client: {CLIENT_ID}")
    print(f"Vault: {VAULT_ID}")
    print(f"Namespace: {NAMESPACE}")
    print("Key: copy-once prmr_alpha_ credential; safe preview retained")
    print(f"Private environment packet: {PRIVATE_ENV_PACKET.as_posix()}")
    print(f"Local protected PRMR flow: {smoke_report['local_protected_flow']}")
    print(f"Hosted key registration: {smoke_report['hosted_key_registration']}")
    print(f"Continuum OS application wiring: {smoke_report['continuum_os_application_wiring']}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")
    return 0 if public_report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

