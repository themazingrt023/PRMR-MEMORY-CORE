"""Run V0.74 persistent storage layer proof."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prmr.product.api_dashboard_sandbox_v073 import run_sandbox_and_build_reports  # noqa: E402
from prmr.product.persistent_storage_v074 import (  # noqa: E402
    BOUNDARY_V074,
    DEFAULT_DB_PATH,
    OVERCLAIMS,
    PUBLIC_FORBIDDEN_TERMS,
    PRMRPersistentStorage,
    REPORT_DIR,
    contains_full_dev_key,
    scan_terms,
    snapshot_counts,
    utc_now,
    write_json,
)


PUBLIC_REPORT = REPORT_DIR / "public_persistent_storage_v074.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_persistent_storage_v074.json"
STORAGE_SNAPSHOT = REPORT_DIR / "storage_snapshot_v074.json"
STORAGE_SCHEMA = REPORT_DIR / "storage_schema_v074.json"
SCORECARD = REPORT_DIR / "scorecard_v074.md"


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def persist_v073_result(storage: PRMRPersistentStorage, result: dict[str, Any]) -> dict[str, Any]:
    api = result["api"]
    setup = result["setup"]
    dashboard = result["dashboard_refresh_state"]
    flow = result["flow_results"]

    for client in api.lifecycle.foundation.clients.values():
        storage.create_client_record(client.client_id, client.organisation, client.status, client.created_at)

    for vault in api.lifecycle.foundation.vaults.values():
        storage.create_vault_record(vault.vault_id, vault.client_id, vault.status, vault.created_at)

    for namespace in api.lifecycle.foundation.namespaces.values():
        storage.create_namespace_record(namespace.client_id, namespace.vault_id, namespace.namespace, namespace.status, namespace.created_at)

    for key in api.lifecycle.lifecycle_keys.values():
        storage.store_api_key_record(
            {
                "key_id": key.key_id,
                "client_id": key.client_id,
                "safe_key_preview": key.safe_key_preview,
                "key_hash": key.key_hash,
                "status": key.status,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at,
                "usage_limit_id": key.usage_limit_id,
            }
        )

    for scope, events in api.events.items():
        client_id, vault_id, namespace = scope.split("::", 2)
        for index, event in enumerate(events, start=1):
            storage.store_memory_event(
                {
                    "event_id": f"{client_id}__{vault_id}__{namespace}__{index:03d}__{event['event_id']}",
                    "client_id": client_id,
                    "vault_id": vault_id,
                    "namespace": namespace,
                    "entity_id": event.get("user_id", "synthetic_entity"),
                    "event_type": event.get("type", "memory_event"),
                    "content_summary": event.get("content", "")[:500],
                    "timestamp": event.get("timestamp") or utc_now(),
                    "synthetic_only": True,
                }
            )

    for packet in api.packets.values():
        storage.store_continuity_packet(
            {
                "packet_id": packet["packet_id"],
                "client_id": packet["client_id"],
                "vault_id": packet["vault_id"],
                "namespace": packet["namespace"],
                "source_event_count": packet["event_count"],
                "summary": packet["summary"],
                "created_at": utc_now(),
                "public_safe": packet.get("public_safe", True),
            }
        )

    packet_id = flow.get("packet_id")
    if packet_id:
        reconstruct_body = flow["reconstruct"]["body"]
        reconstructed = reconstruct_body.get("reconstructable_state", {})
        storage.store_reconstruction_record(
            {
                "packet_id": packet_id,
                "client_id": reconstruct_body["client_id"],
                "vault_id": reconstruct_body["vault_id"],
                "namespace": reconstruct_body["namespace"],
                "current_state": reconstructed.get("current_state", ""),
                "created_at": utc_now(),
            }
        )

        explanation_body = flow["explanation"]["body"]
        action_body = flow["least_harm_action"]["body"]
        storage.store_explanation_record(
            {
                "packet_id": packet_id,
                "client_id": explanation_body["client_id"],
                "vault_id": explanation_body["vault_id"],
                "namespace": explanation_body["namespace"],
                "explanation_summary": explanation_body["explanation"]["summary"],
                "action_label": action_body["recommended_action"],
                "not_final_decision": action_body["not_final_decision"],
                "created_at": utc_now(),
            }
        )

    for report_id, report in api.public_reports.items():
        storage.store_report_record(
            {
                "report_id": report_id,
                "packet_id": report["packet_id"],
                "client_id": report["client_id"],
                "vault_id": report["vault_id"],
                "namespace": report["namespace"],
                "report_type": "public_safe_continuity_report",
                "public_safe_summary": report["summary"],
                "created_at": utc_now(),
            }
        )

    for index, usage in enumerate(api.lifecycle.foundation.usage_ledger, start=1):
        storage.store_usage_log(
            {
                "log_id": f"usage_v074_{index:03d}",
                "client_id": usage.client_id,
                "vault_id": usage.vault_id,
                "namespace": usage.namespace,
                "operation": usage.operation,
                "status": "allowed" if usage.allowed else "blocked",
                "reason": "allowed" if usage.allowed else "blocked",
                "count": usage.count,
                "timestamp": usage.timestamp,
            }
        )

    for index, request in enumerate(api.api_request_log, start=1):
        storage.store_request_log(
            {
                "log_id": f"request_v074_{index:03d}",
                "client_id": request.client_id,
                "vault_id": request.vault_id,
                "namespace": request.namespace,
                "operation": request.endpoint,
                "status": "allowed" if request.status == "ok" else "blocked",
                "reason": request.reason,
                "public_safe_message": request.public_safe_message,
                "timestamp": request.timestamp,
            }
        )

    default_namespace = setup["namespace"].namespace
    storage.store_dashboard_refresh(
        {
            "refresh_id": "refresh_v074_latest",
            "client_id": setup["client"].client_id,
            "vault_id": setup["vault"].vault_id,
            "namespace": default_namespace,
            "allowed_request_count": dashboard["usage_overview"]["allowed_request_count"],
            "blocked_request_count": dashboard["usage_overview"]["blocked_request_count"],
            "events_received": dashboard["memory_health_panel"]["events_received"],
            "packets_generated": dashboard["memory_health_panel"]["packets_generated"],
            "reports_visible": len(dashboard["reports_panel"]["reports"]),
            "memory_health": dashboard["memory_health_panel"]["status"],
            "created_at": utc_now(),
        }
    )

    return {
        "client_id": setup["client"].client_id,
        "vault_id": setup["vault"].vault_id,
        "namespace": default_namespace,
        "packet_id": packet_id,
        "report_id": flow.get("report_id"),
    }


def validate_storage(storage: PRMRPersistentStorage, scope: dict[str, str], public_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    client_id = scope["client_id"]
    vault_id = scope["vault_id"]
    namespace = scope["namespace"]

    add_check(checks, "storage_initialized", storage.db_path.exists(), str(storage.db_path))
    add_check(checks, "schema_version_exists", storage.schema_version() and storage.schema_version().get("version") == "0.74.0", storage.schema_version())
    add_check(checks, "client_records_stored_reloaded", bool(storage.get_client_record(client_id)), storage.get_client_record(client_id))

    api_key_records = public_snapshot.get("api_key_records", [])
    restricted_key_records = storage.export_storage_snapshot(public_safe=False).get("api_key_records", [])
    add_check(checks, "api_key_metadata_stored_reloaded", len(api_key_records) >= 1 and all("safe_key_preview" in record for record in api_key_records), api_key_records)
    add_check(checks, "api_key_hash_stored_restricted_only", any(record.get("key_hash") for record in restricted_key_records) and all("key_hash" not in record for record in api_key_records), None)
    add_check(checks, "raw_api_keys_not_present_in_public_outputs", not contains_full_dev_key(public_snapshot), None)

    add_check(checks, "vault_records_stored_reloaded", bool(storage.get_vault_record(client_id, vault_id)), storage.get_vault_record(client_id, vault_id))
    add_check(checks, "namespace_records_stored_reloaded", bool(storage.get_namespace_record(client_id, vault_id, namespace)), storage.get_namespace_record(client_id, vault_id, namespace))

    events = storage.list_memory_events(client_id, vault_id, namespace)
    add_check(checks, "memory_events_stored_reloaded", len(events) >= 2, len(events))
    add_check(checks, "synthetic_only_flag_present", events and all(event.get("synthetic_only") is True for event in events), events)
    add_check(checks, "continuity_packets_stored_reloaded", bool(storage.get_continuity_packet(client_id, vault_id, namespace, scope["packet_id"])), storage.get_continuity_packet(client_id, vault_id, namespace, scope["packet_id"]))
    add_check(checks, "reconstruction_records_stored_reloaded", len(storage.list_reconstruction_records(client_id, vault_id, namespace)) >= 1, storage.list_reconstruction_records(client_id, vault_id, namespace))
    add_check(checks, "explanation_records_stored_reloaded", len(storage.list_explanation_records(client_id, vault_id, namespace)) >= 1, storage.list_explanation_records(client_id, vault_id, namespace))
    add_check(checks, "report_records_stored_reloaded", bool(storage.get_report_record(client_id, vault_id, namespace, scope["report_id"])), storage.get_report_record(client_id, vault_id, namespace, scope["report_id"]))
    add_check(checks, "usage_logs_stored_reloaded", len(storage.list_usage_logs(client_id)) >= 15, len(storage.list_usage_logs(client_id)))
    add_check(checks, "request_logs_stored_reloaded", len(storage.list_request_logs(client_id)) >= 15, len(storage.list_request_logs(client_id)))
    add_check(checks, "dashboard_refresh_stored_reloaded", bool(storage.get_latest_dashboard_refresh(client_id, vault_id, namespace)), storage.get_latest_dashboard_refresh(client_id, vault_id, namespace))

    wrong_client = "client_v074_wrong_scope"
    add_check(checks, "scoped_queries_respect_client_vault_namespace", len(storage.list_memory_events(client_id, vault_id, namespace)) > 0, None)
    add_check(checks, "wrong_client_scoped_access_returns_empty", storage.get_vault_record(wrong_client, vault_id) is None and storage.list_memory_events(wrong_client, vault_id, namespace) == [], None)
    add_check(checks, "storage_snapshot_generated", bool(public_snapshot.get("schema_version")) and bool(public_snapshot.get("clients")), snapshot_counts(public_snapshot))
    add_check(checks, "public_snapshot_contains_no_raw_secret_terms", not scan_terms(public_snapshot, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_snapshot, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "no_real_client_data_used", all(str(client.get("client_id", "")).startswith("client_v073_synthetic") for client in public_snapshot.get("clients", [])), public_snapshot.get("clients", []))
    add_check(checks, "no_hosted_production_storage_claims", not scan_terms(public_snapshot, OVERCLAIMS), scan_terms(public_snapshot, OVERCLAIMS))
    return checks


def build_public_report(public_snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    counts = snapshot_counts(public_snapshot)
    return {
        "version": "0.74",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "title": "Persistent Storage Layer",
        "result": "PASS" if passed == total else "NEEDS_WORK",
        "checks_passed": passed,
        "checks_total": total,
        "public_safe": True,
        "boundary": BOUNDARY_V074,
        "storage_backend": "sqlite",
        "database_path": str(DEFAULT_DB_PATH.as_posix()),
        "schema_version": public_snapshot.get("schema_version"),
        "stored_record_counts": counts,
    }


def build_private_report(storage: PRMRPersistentStorage, public_report: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **public_report,
        "public_safe": False,
        "title": "Persistent Storage Layer Restricted Synthetic Evidence",
        "checks": checks,
        "storage_snapshot_restricted": storage.export_storage_snapshot(public_safe=False),
        "restricted_note": "Restricted storage evidence may include key hashes. Raw API key values are not stored.",
    }


def build_scorecard(public_report: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = [
        "# V0.74 Persistent Storage Layer",
        "",
        f"Result: {public_report['result']}",
        f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}",
        "",
        f"Boundary: {BOUNDARY_V074}",
        "",
        "## Storage Backend",
        "",
        "- SQLite",
        f"- Database: {public_report['database_path']}",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']}")
    lines.extend(["", "## Command Results", "", "- RUN: python examples/run_persistent_storage_v074.py", "", BOUNDARY_V074, ""])
    return "\n".join(lines)


def run_storage_proof() -> tuple[PRMRPersistentStorage, dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    result, _v073_public, _v073_private, _v073_checks = run_sandbox_and_build_reports()
    storage = PRMRPersistentStorage(DEFAULT_DB_PATH, reset=True)
    scope = persist_v073_result(storage, result)
    public_snapshot = storage.export_storage_snapshot(public_safe=True)
    schema = storage.export_schema()
    checks = validate_storage(storage, scope, public_snapshot)
    public_report = build_public_report(public_snapshot, checks)
    private_report = build_private_report(storage, public_report, checks)
    return storage, public_snapshot, schema, private_report, checks


def main() -> int:
    storage, public_snapshot, schema, private_report, checks = run_storage_proof()
    public_report = build_public_report(public_snapshot, checks)

    write_json(PUBLIC_REPORT, public_report)
    write_json(PRIVATE_REPORT, private_report)
    write_json(STORAGE_SNAPSHOT, public_snapshot)
    write_json(STORAGE_SCHEMA, schema)
    SCORECARD.write_text(build_scorecard(public_report, checks), encoding="utf-8")

    print("PRMR Memory Core V0.74 Persistent Storage Layer")
    print(f"Storage backend: sqlite")
    print(f"Database: {storage.db_path.as_posix()}")
    print(f"Public report: {PUBLIC_REPORT.as_posix()}")
    print(f"Private report: {PRIVATE_REPORT.as_posix()}")
    print(f"Storage snapshot: {STORAGE_SNAPSHOT.as_posix()}")
    print(f"Storage schema: {STORAGE_SCHEMA.as_posix()}")
    print(f"Scorecard: {SCORECARD.as_posix()}")
    print(f"Stored counts: {json.dumps(snapshot_counts(public_snapshot), sort_keys=True)}")
    print(f"Passed checks: {public_report['checks_passed']}/{public_report['checks_total']}")
    print(f"Result: {public_report['result']}")

    if public_report["result"] != "PASS":
        print(json.dumps([check for check in checks if not check["passed"]], indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
