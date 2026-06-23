"""V0.74 durable local persistent storage layer for PRMR Memory Core.

SQLite is used as a local product-state store. This is not hosted production
storage and does not store raw API keys.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from prmr.product.hosted_backend_foundation_v069 import utc_now


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "v074"
DEFAULT_DB_PATH = REPORT_DIR / "prmr_storage_v074.sqlite"
SCHEMA_VERSION = "0.74.0"

BOUNDARY_V074 = (
    "V0.74 is a durable local persistent storage layer only. It stores synthetic/dev-only "
    "PRMR product state in a local SQLite database. It is not hosted production storage, "
    "not hosted client access, not billing, not external validation, not bank approval, "
    "not compliance approval, not legal approval, not external security certification, "
    "and not real-world validation."
)

PUBLIC_FORBIDDEN_TERMS = [
    "raw_api_key",
    "full_api_key",
    "api_secret",
    "private_key",
    "secret",
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


SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
      version TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clients (
      client_id TEXT PRIMARY KEY,
      organisation TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_key_records (
      key_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      safe_key_preview TEXT NOT NULL,
      key_hash TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_used_at TEXT,
      usage_limit_id TEXT NOT NULL,
      FOREIGN KEY(client_id) REFERENCES clients(client_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vaults (
      vault_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(client_id) REFERENCES clients(client_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS namespaces (
      namespace_id TEXT PRIMARY KEY,
      namespace TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(vault_id) REFERENCES vaults(vault_id),
      FOREIGN KEY(client_id) REFERENCES clients(client_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_events (
      event_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      content_summary TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      synthetic_only INTEGER NOT NULL,
      FOREIGN KEY(client_id) REFERENCES clients(client_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_packets (
      packet_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      source_event_count INTEGER NOT NULL,
      summary TEXT NOT NULL,
      created_at TEXT NOT NULL,
      public_safe INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reconstruction_records (
      reconstruction_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      current_state TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS explanation_records (
      explanation_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      explanation_summary TEXT NOT NULL,
      action_label TEXT NOT NULL,
      not_final_decision INTEGER NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
      report_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      report_type TEXT NOT NULL,
      public_safe_summary TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_logs (
      log_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      operation TEXT NOT NULL,
      status TEXT NOT NULL,
      reason TEXT NOT NULL,
      count INTEGER NOT NULL,
      timestamp TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS request_logs (
      log_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      operation TEXT NOT NULL,
      status TEXT NOT NULL,
      reason TEXT NOT NULL,
      public_safe_message TEXT NOT NULL,
      timestamp TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dashboard_refresh_records (
      refresh_id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      vault_id TEXT NOT NULL,
      namespace TEXT NOT NULL,
      allowed_request_count INTEGER NOT NULL,
      blocked_request_count INTEGER NOT NULL,
      events_received INTEGER NOT NULL,
      packets_generated INTEGER NOT NULL,
      reports_visible INTEGER NOT NULL,
      memory_health TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
]


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def initialize_storage(db_path: Path = DEFAULT_DB_PATH, reset: bool = False) -> Path:
    if reset and db_path.exists():
        db_path.unlink()
    with connect(db_path) as connection:
        for statement in SCHEMA_SQL:
            connection.execute(statement)
        connection.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now()),
        )
        connection.commit()
    return db_path


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = dict(row)
    for key, value in list(payload.items()):
        if key in {"synthetic_only", "public_safe", "not_final_decision"}:
            payload[key] = bool(value)
    return payload


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def namespace_key(client_id: str, vault_id: str, namespace: str) -> str:
    return f"{client_id}::{vault_id}::{namespace}"


class PRMRPersistentStorage:
    """SQLite-backed local storage helper with scoped reads."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, reset: bool = False) -> None:
        self.db_path = initialize_storage(db_path, reset=reset)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with connect(self.db_path) as connection:
            connection.execute(sql, params)
            connection.commit()

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            return row_to_dict(connection.execute(sql, params).fetchone())

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            return rows_to_dicts(connection.execute(sql, params).fetchall())

    def schema_version(self) -> dict[str, Any] | None:
        return self.query_one("SELECT version, applied_at FROM schema_version ORDER BY applied_at DESC LIMIT 1")

    def create_client_record(self, client_id: str, organisation: str, status: str, created_at: str | None = None) -> dict[str, Any]:
        self.execute(
            "INSERT OR REPLACE INTO clients (client_id, organisation, status, created_at) VALUES (?, ?, ?, ?)",
            (client_id, organisation, status, created_at or utc_now()),
        )
        return self.get_client_record(client_id) or {}

    def get_client_record(self, client_id: str) -> dict[str, Any] | None:
        return self.query_one("SELECT * FROM clients WHERE client_id = ?", (client_id,))

    def create_vault_record(self, vault_id: str, client_id: str, status: str, created_at: str | None = None) -> dict[str, Any]:
        self.execute(
            "INSERT OR REPLACE INTO vaults (vault_id, client_id, status, created_at) VALUES (?, ?, ?, ?)",
            (vault_id, client_id, status, created_at or utc_now()),
        )
        return self.get_vault_record(client_id, vault_id) or {}

    def get_vault_record(self, client_id: str, vault_id: str) -> dict[str, Any] | None:
        return self.query_one("SELECT * FROM vaults WHERE client_id = ? AND vault_id = ?", (client_id, vault_id))

    def create_namespace_record(self, client_id: str, vault_id: str, namespace: str, status: str, created_at: str | None = None) -> dict[str, Any]:
        self.execute(
            "INSERT OR REPLACE INTO namespaces (namespace_id, namespace, vault_id, client_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (namespace_key(client_id, vault_id, namespace), namespace, vault_id, client_id, status, created_at or utc_now()),
        )
        return self.get_namespace_record(client_id, vault_id, namespace) or {}

    def get_namespace_record(self, client_id: str, vault_id: str, namespace: str) -> dict[str, Any] | None:
        return self.query_one(
            "SELECT * FROM namespaces WHERE client_id = ? AND vault_id = ? AND namespace = ?",
            (client_id, vault_id, namespace),
        )

    def store_api_key_record(self, record: dict[str, Any]) -> dict[str, Any]:
        self.execute(
            """
            INSERT OR REPLACE INTO api_key_records
            (key_id, client_id, safe_key_preview, key_hash, status, created_at, last_used_at, usage_limit_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["key_id"],
                record["client_id"],
                record["safe_key_preview"],
                record["key_hash"],
                record["status"],
                record["created_at"],
                record.get("last_used_at"),
                record["usage_limit_id"],
            ),
        )
        return self.get_api_key_record(record["client_id"], record["key_id"], include_hash=True) or {}

    def get_api_key_record(self, client_id: str, key_id: str, include_hash: bool = False) -> dict[str, Any] | None:
        record = self.query_one("SELECT * FROM api_key_records WHERE client_id = ? AND key_id = ?", (client_id, key_id))
        if record and not include_hash:
            record.pop("key_hash", None)
        return record

    def store_memory_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.execute(
            """
            INSERT OR REPLACE INTO memory_events
            (event_id, client_id, vault_id, namespace, entity_id, event_type, content_summary, timestamp, synthetic_only)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["client_id"],
                event["vault_id"],
                event["namespace"],
                event.get("entity_id") or event.get("user_id") or "synthetic_entity",
                event["event_type"],
                event["content_summary"],
                event["timestamp"],
                1 if event.get("synthetic_only", True) else 0,
            ),
        )
        return self.query_one("SELECT * FROM memory_events WHERE event_id = ?", (event["event_id"],)) or {}

    def list_memory_events(self, client_id: str, vault_id: str, namespace: str) -> list[dict[str, Any]]:
        return self.query_all(
            "SELECT * FROM memory_events WHERE client_id = ? AND vault_id = ? AND namespace = ? ORDER BY timestamp, event_id",
            (client_id, vault_id, namespace),
        )

    def store_continuity_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        self.execute(
            """
            INSERT OR REPLACE INTO continuity_packets
            (packet_id, client_id, vault_id, namespace, source_event_count, summary, created_at, public_safe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet["packet_id"],
                packet["client_id"],
                packet["vault_id"],
                packet["namespace"],
                int(packet["source_event_count"]),
                packet["summary"],
                packet.get("created_at") or utc_now(),
                1 if packet.get("public_safe", True) else 0,
            ),
        )
        return self.get_continuity_packet(packet["client_id"], packet["vault_id"], packet["namespace"], packet["packet_id"]) or {}

    def get_continuity_packet(self, client_id: str, vault_id: str, namespace: str, packet_id: str) -> dict[str, Any] | None:
        return self.query_one(
            "SELECT * FROM continuity_packets WHERE client_id = ? AND vault_id = ? AND namespace = ? AND packet_id = ?",
            (client_id, vault_id, namespace, packet_id),
        )

    def store_reconstruction_record(self, record: dict[str, Any]) -> dict[str, Any]:
        reconstruction_id = record.get("reconstruction_id") or f"recon_{uuid4().hex[:12]}"
        self.execute(
            """
            INSERT OR REPLACE INTO reconstruction_records
            (reconstruction_id, packet_id, client_id, vault_id, namespace, current_state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reconstruction_id,
                record["packet_id"],
                record["client_id"],
                record["vault_id"],
                record["namespace"],
                record["current_state"],
                record.get("created_at") or utc_now(),
            ),
        )
        return self.query_one("SELECT * FROM reconstruction_records WHERE reconstruction_id = ?", (reconstruction_id,)) or {}

    def store_explanation_record(self, record: dict[str, Any]) -> dict[str, Any]:
        explanation_id = record.get("explanation_id") or f"explain_{uuid4().hex[:12]}"
        self.execute(
            """
            INSERT OR REPLACE INTO explanation_records
            (explanation_id, packet_id, client_id, vault_id, namespace, explanation_summary, action_label, not_final_decision, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                explanation_id,
                record["packet_id"],
                record["client_id"],
                record["vault_id"],
                record["namespace"],
                record["explanation_summary"],
                record["action_label"],
                1 if record.get("not_final_decision", True) else 0,
                record.get("created_at") or utc_now(),
            ),
        )
        return self.query_one("SELECT * FROM explanation_records WHERE explanation_id = ?", (explanation_id,)) or {}

    def list_reconstruction_records(self, client_id: str, vault_id: str, namespace: str) -> list[dict[str, Any]]:
        return self.query_all(
            "SELECT * FROM reconstruction_records WHERE client_id = ? AND vault_id = ? AND namespace = ?",
            (client_id, vault_id, namespace),
        )

    def list_explanation_records(self, client_id: str, vault_id: str, namespace: str) -> list[dict[str, Any]]:
        return self.query_all(
            "SELECT * FROM explanation_records WHERE client_id = ? AND vault_id = ? AND namespace = ?",
            (client_id, vault_id, namespace),
        )

    def store_report_record(self, report: dict[str, Any]) -> dict[str, Any]:
        self.execute(
            """
            INSERT OR REPLACE INTO reports
            (report_id, packet_id, client_id, vault_id, namespace, report_type, public_safe_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["report_id"],
                report["packet_id"],
                report["client_id"],
                report["vault_id"],
                report["namespace"],
                report["report_type"],
                report["public_safe_summary"],
                report.get("created_at") or utc_now(),
            ),
        )
        return self.get_report_record(report["client_id"], report["vault_id"], report["namespace"], report["report_id"]) or {}

    def get_report_record(self, client_id: str, vault_id: str, namespace: str, report_id: str) -> dict[str, Any] | None:
        return self.query_one(
            "SELECT * FROM reports WHERE client_id = ? AND vault_id = ? AND namespace = ? AND report_id = ?",
            (client_id, vault_id, namespace, report_id),
        )

    def store_usage_log(self, log: dict[str, Any]) -> dict[str, Any]:
        log_id = log.get("log_id") or f"usage_{uuid4().hex[:12]}"
        self.execute(
            """
            INSERT OR REPLACE INTO usage_logs
            (log_id, client_id, vault_id, namespace, operation, status, reason, count, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                log["client_id"],
                log["vault_id"],
                log["namespace"],
                log["operation"],
                log["status"],
                log["reason"],
                int(log.get("count", 1)),
                log.get("timestamp") or utc_now(),
            ),
        )
        return self.query_one("SELECT * FROM usage_logs WHERE log_id = ?", (log_id,)) or {}

    def list_usage_logs(self, client_id: str, vault_id: str | None = None, namespace: str | None = None) -> list[dict[str, Any]]:
        if vault_id is None:
            return self.query_all("SELECT * FROM usage_logs WHERE client_id = ? ORDER BY timestamp, log_id", (client_id,))
        if namespace is None:
            return self.query_all("SELECT * FROM usage_logs WHERE client_id = ? AND vault_id = ? ORDER BY timestamp, log_id", (client_id, vault_id))
        return self.query_all(
            "SELECT * FROM usage_logs WHERE client_id = ? AND vault_id = ? AND namespace = ? ORDER BY timestamp, log_id",
            (client_id, vault_id, namespace),
        )

    def store_request_log(self, log: dict[str, Any]) -> dict[str, Any]:
        log_id = log.get("log_id") or f"request_{uuid4().hex[:12]}"
        self.execute(
            """
            INSERT OR REPLACE INTO request_logs
            (log_id, client_id, vault_id, namespace, operation, status, reason, public_safe_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                log["client_id"],
                log["vault_id"],
                log["namespace"],
                log["operation"],
                log["status"],
                log["reason"],
                log["public_safe_message"],
                log.get("timestamp") or utc_now(),
            ),
        )
        return self.query_one("SELECT * FROM request_logs WHERE log_id = ?", (log_id,)) or {}

    def list_request_logs(self, client_id: str, vault_id: str | None = None, namespace: str | None = None) -> list[dict[str, Any]]:
        if vault_id is None:
            return self.query_all("SELECT * FROM request_logs WHERE client_id = ? ORDER BY timestamp, log_id", (client_id,))
        if namespace is None:
            return self.query_all("SELECT * FROM request_logs WHERE client_id = ? AND vault_id = ? ORDER BY timestamp, log_id", (client_id, vault_id))
        return self.query_all(
            "SELECT * FROM request_logs WHERE client_id = ? AND vault_id = ? AND namespace = ? ORDER BY timestamp, log_id",
            (client_id, vault_id, namespace),
        )

    def store_dashboard_refresh(self, refresh: dict[str, Any]) -> dict[str, Any]:
        refresh_id = refresh.get("refresh_id") or f"refresh_{uuid4().hex[:12]}"
        self.execute(
            """
            INSERT OR REPLACE INTO dashboard_refresh_records
            (refresh_id, client_id, vault_id, namespace, allowed_request_count, blocked_request_count, events_received,
             packets_generated, reports_visible, memory_health, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                refresh_id,
                refresh["client_id"],
                refresh["vault_id"],
                refresh["namespace"],
                int(refresh["allowed_request_count"]),
                int(refresh["blocked_request_count"]),
                int(refresh["events_received"]),
                int(refresh["packets_generated"]),
                int(refresh["reports_visible"]),
                refresh["memory_health"],
                refresh.get("created_at") or utc_now(),
            ),
        )
        return self.get_latest_dashboard_refresh(refresh["client_id"], refresh["vault_id"], refresh["namespace"]) or {}

    def get_latest_dashboard_refresh(self, client_id: str, vault_id: str, namespace: str) -> dict[str, Any] | None:
        return self.query_one(
            """
            SELECT * FROM dashboard_refresh_records
            WHERE client_id = ? AND vault_id = ? AND namespace = ?
            ORDER BY created_at DESC, refresh_id DESC
            LIMIT 1
            """,
            (client_id, vault_id, namespace),
        )

    def export_storage_snapshot(self, public_safe: bool = True) -> dict[str, Any]:
        snapshot = {
            "version": "0.74",
            "schema_version": self.schema_version(),
            "boundary": BOUNDARY_V074,
            "public_safe": public_safe,
            "clients": self.query_all("SELECT * FROM clients ORDER BY client_id"),
            "api_key_records": self.query_all("SELECT * FROM api_key_records ORDER BY key_id"),
            "vaults": self.query_all("SELECT * FROM vaults ORDER BY vault_id"),
            "namespaces": self.query_all("SELECT * FROM namespaces ORDER BY namespace_id"),
            "memory_events": self.query_all("SELECT * FROM memory_events ORDER BY timestamp, event_id"),
            "continuity_packets": self.query_all("SELECT * FROM continuity_packets ORDER BY created_at, packet_id"),
            "reconstruction_records": self.query_all("SELECT * FROM reconstruction_records ORDER BY created_at, reconstruction_id"),
            "explanation_records": self.query_all("SELECT * FROM explanation_records ORDER BY created_at, explanation_id"),
            "reports": self.query_all("SELECT * FROM reports ORDER BY created_at, report_id"),
            "usage_logs": self.query_all("SELECT * FROM usage_logs ORDER BY timestamp, log_id"),
            "request_logs": self.query_all("SELECT * FROM request_logs ORDER BY timestamp, log_id"),
            "dashboard_refresh_records": self.query_all("SELECT * FROM dashboard_refresh_records ORDER BY created_at, refresh_id"),
        }
        if public_safe:
            for record in snapshot["api_key_records"]:
                record.pop("key_hash", None)
        return snapshot

    def export_schema(self) -> dict[str, Any]:
        tables = {}
        for table in [
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
        ]:
            tables[table] = self.query_all(f"PRAGMA table_info({table})")
        return {
            "version": "0.74",
            "backend": "sqlite",
            "database_path": str(self.db_path.relative_to(ROOT)),
            "schema_version": self.schema_version(),
            "tables": tables,
            "boundary": BOUNDARY_V074,
        }


def scan_terms(payload: Any, terms: list[str]) -> list[str]:
    text = payload.lower() if isinstance(payload, str) else json.dumps(payload, sort_keys=True).lower()
    return [term for term in terms if term.lower() in text]


def contains_full_dev_key(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return bool(re.search(r"prmr_alpha_dev_[a-f0-9]{16,}", text))


def snapshot_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    return {
        key: len(value)
        for key, value in snapshot.items()
        if isinstance(value, list)
    }
