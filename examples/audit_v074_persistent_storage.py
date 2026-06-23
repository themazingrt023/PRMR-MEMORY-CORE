"""Audit V0.74 persistent storage layer."""

from __future__ import annotations

import importlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

STORAGE_MODULE = ROOT / "prmr" / "product" / "persistent_storage_v074.py"
RUNNER = ROOT / "examples" / "run_persistent_storage_v074.py"
REPORT_DIR = ROOT / "reports" / "v074"
DB_PATH = REPORT_DIR / "prmr_storage_v074.sqlite"
PUBLIC_REPORT = REPORT_DIR / "public_persistent_storage_v074.json"
PRIVATE_REPORT = REPORT_DIR / "private_internal_persistent_storage_v074.json"
STORAGE_SNAPSHOT = REPORT_DIR / "storage_snapshot_v074.json"
STORAGE_SCHEMA = REPORT_DIR / "storage_schema_v074.json"
SCORECARD = REPORT_DIR / "scorecard_v074.md"

REQUIRED_REPORTS = [PUBLIC_REPORT, PRIVATE_REPORT, STORAGE_SNAPSHOT, STORAGE_SCHEMA, SCORECARD, DB_PATH]

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
]

OVERCLAIMS = [
    "production-ready",
    "production ready",
    "hosted client access is live",
    "live api access granted",
    "billing enabled",
    "bank-approved",
    "bank approved",
    "compliance-certified",
    "compliance certified",
    "legal-approved",
    "legal approved",
    "security-certified",
    "security certified",
    "external validation complete",
    "real-world validated",
    "real client data",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "output": completed.stdout,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any = None) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def sqlite_tables(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
    return [row[0] for row in rows]


def build_scorecard(checks: list[dict[str, Any]], runner: dict[str, Any]) -> str:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    lines = [
        "# V0.74 Persistent Storage Audit Scorecard",
        "",
        f"Result: {result}",
        f"Passed checks: {passed}/{total}",
        "",
        "Boundary: V0.74 is local SQLite storage evidence only. Hosted backend/client access comes later.",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    lines.extend(["", "## Command Results", "", f"- {'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}", ""])
    return "\n".join(lines)


def main() -> int:
    checks: list[dict[str, Any]] = []

    add_check(checks, "storage_module_exists", STORAGE_MODULE.exists(), str(STORAGE_MODULE.relative_to(ROOT)))
    module = importlib.import_module("prmr.product.persistent_storage_v074")
    storage_class = getattr(module, "PRMRPersistentStorage", None)
    add_check(checks, "PRMRPersistentStorage_exists", storage_class is not None, "PRMRPersistentStorage")
    add_check(checks, "initialize_storage_exists", hasattr(module, "initialize_storage"), "initialize_storage")
    for function_name in [
        "create_client_record",
        "get_client_record",
        "create_vault_record",
        "get_vault_record",
        "create_namespace_record",
        "get_namespace_record",
        "store_api_key_record",
        "get_api_key_record",
        "store_memory_event",
        "list_memory_events",
        "store_continuity_packet",
        "get_continuity_packet",
        "store_reconstruction_record",
        "store_explanation_record",
        "store_report_record",
        "get_report_record",
        "store_usage_log",
        "list_usage_logs",
        "store_request_log",
        "list_request_logs",
        "store_dashboard_refresh",
        "get_latest_dashboard_refresh",
        "export_storage_snapshot",
    ]:
        add_check(checks, f"{function_name}_exists", hasattr(storage_class, function_name), function_name)

    runner = run_command(["python", str(RUNNER)])
    add_check(checks, "runner_passes", runner["passed"], runner["output"][-1200:])

    for path in REQUIRED_REPORTS:
        add_check(checks, f"{path.name}_exists", path.exists(), str(path.relative_to(ROOT)))

    snapshot = read_json(STORAGE_SNAPSHOT) if STORAGE_SNAPSHOT.exists() else {}
    schema = read_json(STORAGE_SCHEMA) if STORAGE_SCHEMA.exists() else {}
    public_report = read_json(PUBLIC_REPORT) if PUBLIC_REPORT.exists() else {}
    private_report = read_json(PRIVATE_REPORT) if PRIVATE_REPORT.exists() else {}

    tables = sqlite_tables(DB_PATH) if DB_PATH.exists() else []
    required_tables = {
        "schema_version",
        "clients",
        "api_key_records",
        "vaults",
        "namespaces",
        "memory_events",
        "continuity_packets",
        "reconstruction_records",
        "explanation_records",
        "reports",
        "usage_logs",
        "request_logs",
        "dashboard_refresh_records",
    }
    add_check(checks, "storage_initialized", DB_PATH.exists(), str(DB_PATH))
    add_check(checks, "schema_tables_exist", required_tables.issubset(set(tables)), tables)
    add_check(checks, "schema_version_exists", snapshot.get("schema_version", {}).get("version") == "0.74.0", snapshot.get("schema_version"))

    clients = snapshot.get("clients", [])
    client_id = clients[0]["client_id"] if clients else ""
    vaults = snapshot.get("vaults", [])
    vault_id = vaults[0]["vault_id"] if vaults else ""
    namespace = "default"
    storage = storage_class(DB_PATH, reset=False) if storage_class else None

    add_check(checks, "client_records_stored_reloaded", bool(clients) and bool(storage.get_client_record(client_id)), clients)
    public_keys = snapshot.get("api_key_records", [])
    restricted_keys = private_report.get("storage_snapshot_restricted", {}).get("api_key_records", [])
    add_check(checks, "api_key_metadata_stored_reloaded", len(public_keys) >= 1 and all(record.get("safe_key_preview") for record in public_keys), public_keys)
    add_check(checks, "api_key_hash_restricted_not_public", all("key_hash" not in record for record in public_keys) and any(record.get("key_hash") for record in restricted_keys), None)
    add_check(checks, "raw_api_keys_not_present_in_public_outputs", not contains_full_dev_key({"public_report": public_report, "snapshot": snapshot}), None)
    add_check(checks, "vault_records_stored_reloaded", bool(vaults) and bool(storage.get_vault_record(client_id, vault_id)), vaults)
    add_check(checks, "namespace_records_stored_reloaded", bool(storage.get_namespace_record(client_id, vault_id, namespace)), snapshot.get("namespaces", []))

    events = storage.list_memory_events(client_id, vault_id, namespace) if storage else []
    add_check(checks, "memory_events_stored_reloaded", len(events) >= 2, len(events))
    add_check(checks, "synthetic_only_flag_present", events and all(event.get("synthetic_only") is True for event in events), events)

    packets = snapshot.get("continuity_packets", [])
    packet_id = packets[0]["packet_id"] if packets else ""
    reports = snapshot.get("reports", [])
    report_id = reports[0]["report_id"] if reports else ""
    add_check(checks, "continuity_packets_stored_reloaded", bool(storage.get_continuity_packet(client_id, vault_id, namespace, packet_id)), packets)
    add_check(checks, "reconstruction_explanation_report_stored_reloaded", len(storage.list_reconstruction_records(client_id, vault_id, namespace)) >= 1 and len(storage.list_explanation_records(client_id, vault_id, namespace)) >= 1 and bool(storage.get_report_record(client_id, vault_id, namespace, report_id)), None)
    add_check(checks, "usage_logs_stored_reloaded", len(storage.list_usage_logs(client_id)) >= 15, len(storage.list_usage_logs(client_id)))
    add_check(checks, "request_logs_stored_reloaded", len(storage.list_request_logs(client_id)) >= 15, len(storage.list_request_logs(client_id)))
    add_check(checks, "dashboard_refresh_stored_reloaded", bool(storage.get_latest_dashboard_refresh(client_id, vault_id, namespace)), storage.get_latest_dashboard_refresh(client_id, vault_id, namespace))
    add_check(checks, "scoped_queries_respect_client_vault_namespace", len(storage.list_memory_events(client_id, vault_id, namespace)) >= 2, None)
    add_check(checks, "wrong_client_scoped_access_blocked_or_empty", storage.get_vault_record("client_wrong_scope", vault_id) is None and storage.list_memory_events("client_wrong_scope", vault_id, namespace) == [], None)
    add_check(checks, "storage_snapshot_generated", bool(snapshot.get("clients")) and bool(snapshot.get("schema_version")), None)
    add_check(checks, "storage_schema_generated", schema.get("backend") == "sqlite" and required_tables.issubset(set(schema.get("tables", {}).keys())), schema.get("backend"))

    public_bundle = {"public_report": public_report, "storage_snapshot": snapshot}
    add_check(checks, "public_report_contains_no_raw_secret_terms", not scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS), scan_terms(public_bundle, PUBLIC_FORBIDDEN_TERMS))
    add_check(checks, "no_real_client_data_used", all(str(client.get("client_id", "")).startswith("client_v073_synthetic") for client in clients), clients)
    add_check(checks, "no_hosted_production_storage_claims", not scan_terms(public_bundle, ["production-ready", "production ready", "hosted client access is live"]), scan_terms(public_bundle, ["production-ready", "production ready", "hosted client access is live"]))
    add_check(checks, "no_billing_claims", not scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]), scan_terms(public_bundle, ["billing enabled", "stripe", "payment processed"]))
    add_check(checks, "no_certification_or_approval_claims", not scan_terms(public_bundle, OVERCLAIMS), scan_terms(public_bundle, OVERCLAIMS))

    private_checks = {check.get("name"): check.get("passed") for check in private_report.get("checks", [])}
    for required in [
        "storage_initialized",
        "schema_version_exists",
        "client_records_stored_reloaded",
        "api_key_metadata_stored_reloaded",
        "raw_api_keys_not_present_in_public_outputs",
        "vault_records_stored_reloaded",
        "namespace_records_stored_reloaded",
        "memory_events_stored_reloaded",
        "synthetic_only_flag_present",
        "continuity_packets_stored_reloaded",
        "reconstruction_records_stored_reloaded",
        "explanation_records_stored_reloaded",
        "report_records_stored_reloaded",
        "usage_logs_stored_reloaded",
        "request_logs_stored_reloaded",
        "dashboard_refresh_stored_reloaded",
        "wrong_client_scoped_access_returns_empty",
        "storage_snapshot_generated",
    ]:
        add_check(checks, f"runner_check_{required}", private_checks.get(required) is True, private_checks.get(required))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    result = "PASS" if passed == total else "NEEDS_WORK"
    SCORECARD.write_text(build_scorecard(checks, runner), encoding="utf-8")

    print("PRMR Memory Core V0.74 Persistent Storage Audit")
    print(f"{'PASS' if runner['passed'] else 'FAIL'}: {runner['command']}")
    print(f"Passed checks: {passed}/{total}")
    print(f"Result: {result}")
    if result != "PASS":
        failing = [check for check in checks if not check["passed"]]
        print(json.dumps(failing, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
