"""SQLite repository for durable PRMR self-serve product state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator

from prmr.product.api_key_lifecycle_v070 import LifecycleEvent, LifecycleKeyRecord
from prmr.product.controlled_alpha_api_v071 import APIRequestLog
from prmr.product.hosted_backend_foundation_v069 import (
    APIKeyRecord,
    Client,
    ContinuityReportRef,
    Namespace,
    RequestLog,
    UsageEvent,
    UsageLimit,
    Vault,
    key_fingerprint,
    utc_now,
)
from prmr.product.self_serve_accounts_v092 import LocalSession, SelfServeAccount
from prmr.product.self_serve_api_keys_v092 import SelfServeApplication, SelfServeClientScope
from prmr.product.self_serve_dashboard_v092 import SelfServeDashboardV092
from prmr.product.self_serve_plans_v092 import PlanSubscription


SCHEMA_VERSION = "0.93.0"
TABLES = (
    "users",
    "sessions",
    "plans",
    "clients",
    "applications",
    "vaults",
    "namespaces",
    "usage_limits",
    "api_keys",
    "key_applications",
    "monthly_usage",
    "usage_events",
    "request_logs",
    "api_request_logs",
    "key_lifecycle_events",
    "events",
    "packets",
    "reports",
    "dashboard_snapshots",
    "audit_metadata",
    "prmr_sources",
    "prmr_source_segments",
    "prmr_candidate_extraction_runs",
    "prmr_candidate_memories",
    "prmr_candidate_evidence",
    "prmr_memory_admission_decisions",
    "prmr_admitted_memory_links",
    "prmr_memory_ledger_schema_migrations",
    "prmr_memory_evolution_records",
    "prmr_memory_conflicts",
    "prmr_memory_reconstructions",
    "prmr_memory_temporal_schema_migrations",
    "prmr_memory_importance_annotations",
    "prmr_memory_dynamics_snapshots",
    "prmr_memory_signal_dynamics",
    "prmr_entity_relationship_schema_migrations",
    "prmr_entity_candidates",
    "prmr_entity_evidence",
    "prmr_entities",
    "prmr_entity_identifiers",
    "prmr_entity_mentions",
    "prmr_entity_alias_assertions",
    "prmr_entity_resolution_decisions",
    "prmr_entity_distinctness_assertions",
    "prmr_entity_merges",
    "prmr_event_entity_links",
    "prmr_relationship_candidates",
    "prmr_relationship_evidence",
    "prmr_relationship_admission_decisions",
    "prmr_relationships",
    "prmr_relationship_evolution_records",
    "prmr_relationship_conflicts",
    "prmr_entity_relationship_reconstructions",
    "prmr_memory_query_schema_migrations",
    "prmr_memory_query_runs",
    "prmr_memory_query_results",
    "prmr_memory_evidence_bundles",
    "prmr_memory_query_evidence_items",
    "prmr_memory_explanations",
    "prmr_memory_query_result_comparisons",
)


class SelfServeRepositoryV093:
    """Persist and reconstruct V0.92 product state using explicit tables."""

    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @property
    def backend_name(self) -> str:
        return "sqlite"

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.storage_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    email_verification_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    verified_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS plans (
                    user_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    billing_status TEXT NOT NULL,
                    selected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS usage_limits (
                    usage_limit_id TEXT PRIMARY KEY,
                    max_events_per_day INTEGER NOT NULL,
                    max_packets_per_day INTEGER NOT NULL,
                    max_reports_per_day INTEGER NOT NULL,
                    alpha_limit_reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clients (
                    client_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    organisation TEXT NOT NULL,
                    contact_email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    usage_limit_id TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(usage_limit_id) REFERENCES usage_limits(usage_limit_id)
                );
                CREATE TABLE IF NOT EXISTS applications (
                    application_reference TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(application_reference, client_id),
                    FOREIGN KEY(client_id) REFERENCES clients(client_id)
                );
                CREATE TABLE IF NOT EXISTS vaults (
                    vault_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(client_id)
                );
                CREATE TABLE IF NOT EXISTS namespaces (
                    namespace_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(vault_id) REFERENCES vaults(vault_id),
                    FOREIGN KEY(client_id) REFERENCES clients(client_id)
                );
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    safe_key_preview TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    rotated_at TEXT,
                    revoked_at TEXT,
                    last_used_at TEXT,
                    usage_limit_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    label TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(client_id),
                    FOREIGN KEY(usage_limit_id) REFERENCES usage_limits(usage_limit_id)
                );
                CREATE TABLE IF NOT EXISTS key_applications (
                    key_id TEXT PRIMARY KEY,
                    application_reference TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    FOREIGN KEY(key_id) REFERENCES api_keys(key_id),
                    FOREIGN KEY(application_reference, client_id) REFERENCES applications(application_reference, client_id)
                );
                CREATE TABLE IF NOT EXISTS monthly_usage (
                    user_id TEXT NOT NULL,
                    month_key TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    PRIMARY KEY(user_id, month_key),
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    allowed INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS api_request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS key_lifecycle_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    key_id TEXT,
                    operator_id TEXT,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    scope_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS packets (
                    packet_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(report_id, visibility)
                );
                CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                    user_id TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS audit_metadata (
                    metadata_key TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            from prmr.core.source_ledger import initialize_sqlite_source_schema
            from prmr.core.candidate_engine import initialize_sqlite_candidate_schema
            from prmr.core.admission_service import initialize_sqlite_admission_schema
            from prmr.core.memory_ledger_service import initialize_sqlite_memory_ledger_schema
            from prmr.core.memory_importance import initialize_sqlite_temporal_schema
            from prmr.core.entity_store import initialize_sqlite_entity_relationship_schema
            from prmr.core.memory_query_store import initialize_sqlite_memory_query_schema

            initialize_sqlite_source_schema(connection)
            initialize_sqlite_candidate_schema(connection)
            initialize_sqlite_admission_schema(connection)
            initialize_sqlite_memory_ledger_schema(connection)
            initialize_sqlite_temporal_schema(connection)
            initialize_sqlite_entity_relationship_schema(connection)
            initialize_sqlite_memory_query_schema(connection)
            connection.execute(
                """
                INSERT INTO audit_metadata(metadata_key, metadata_json, updated_at)
                VALUES('schema_version', ?, ?)
                ON CONFLICT(metadata_key) DO UPDATE SET
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (json.dumps({"version": SCHEMA_VERSION}), utc_now()),
            )

    def save_product(self, product: SelfServeDashboardV092) -> None:
        """Atomically replace persisted state with the current product state."""

        foundation = product.api.lifecycle.foundation
        lifecycle = product.api.lifecycle
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._clear_state(connection)

            connection.executemany(
                """
                INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.user_id,
                        item.name,
                        item.email,
                        item.password_salt,
                        item.password_hash,
                        item.status,
                        item.email_verification_mode,
                        item.created_at,
                        item.verified_at,
                    )
                    for item in product.accounts.accounts.values()
                ],
            )
            connection.executemany(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                [
                    (item.session_id, item.user_id, item.token_hash, item.status, item.created_at)
                    for item in product.accounts.sessions.values()
                ],
            )
            connection.executemany(
                "INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.user_id,
                        item.plan_id,
                        item.status,
                        item.billing_status,
                        item.selected_at,
                        item.updated_at,
                    )
                    for item in product.plans.subscriptions.values()
                ],
            )
            connection.executemany(
                "INSERT INTO usage_limits VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        item.usage_limit_id,
                        item.max_events_per_day,
                        item.max_packets_per_day,
                        item.max_reports_per_day,
                        item.alpha_limit_reason,
                    )
                    for item in foundation.usage_limits.values()
                ],
            )
            connection.executemany(
                "INSERT INTO clients VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        client.client_id,
                        scope.user_id,
                        client.organisation,
                        client.contact_email,
                        client.status,
                        client.created_at,
                        scope.plan_id,
                        scope.usage_limit_id,
                    )
                    for scope in product.keys.scopes_by_user.values()
                    if (client := foundation.clients.get(scope.client_id)) is not None
                ],
            )
            connection.executemany(
                "INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        app.application_reference,
                        app.client_id,
                        app.name,
                        app.environment,
                        app.status,
                        app.created_at,
                    )
                    for applications in product.keys.applications_by_client.values()
                    for app in applications.values()
                ],
            )
            connection.executemany(
                "INSERT INTO vaults VALUES (?, ?, ?, ?)",
                [
                    (item.vault_id, item.client_id, item.status, item.created_at)
                    for item in foundation.vaults.values()
                ],
            )
            connection.executemany(
                "INSERT INTO namespaces VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        foundation.namespace_key(item.client_id, item.vault_id, item.namespace),
                        item.namespace,
                        item.vault_id,
                        item.client_id,
                        item.status,
                        item.created_at,
                    )
                    for item in foundation.namespaces.values()
                ],
            )
            connection.executemany(
                "INSERT INTO api_keys VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.key_id,
                        item.client_id,
                        item.safe_key_preview,
                        item.key_hash,
                        foundation.api_keys[item.key_id].key_fingerprint,
                        item.status,
                        item.created_at,
                        item.rotated_at,
                        item.revoked_at,
                        item.last_used_at,
                        item.usage_limit_id,
                        item.vault_id,
                        item.namespace,
                        product.keys.key_labels.get(item.key_id, "Unlabelled key"),
                    )
                    for item in lifecycle.lifecycle_keys.values()
                    if item.key_id in foundation.api_keys
                ],
            )
            connection.executemany(
                "INSERT INTO key_applications VALUES (?, ?, ?)",
                [
                    (
                        key_id,
                        application_reference,
                        lifecycle.lifecycle_keys[key_id].client_id,
                    )
                    for key_id, application_reference in product.keys.key_applications.items()
                    if key_id in lifecycle.lifecycle_keys
                ],
            )
            connection.executemany(
                "INSERT INTO monthly_usage VALUES (?, ?, ?)",
                [
                    (user_id, month_key, count)
                    for (user_id, month_key), count in product.plans.monthly_usage.items()
                ],
            )
            connection.executemany(
                """
                INSERT INTO usage_events(timestamp, client_id, vault_id, namespace, operation, count, allowed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.timestamp,
                        item.client_id,
                        item.vault_id,
                        item.namespace,
                        item.operation,
                        item.count,
                        int(item.allowed),
                    )
                    for item in foundation.usage_ledger
                ],
            )
            connection.executemany(
                """
                INSERT INTO request_logs(timestamp, client_id, operation, status, reason, public_safe_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.timestamp,
                        item.client_id,
                        item.operation,
                        item.status,
                        item.reason,
                        item.public_safe_message,
                    )
                    for item in foundation.request_log
                ],
            )
            connection.executemany(
                """
                INSERT INTO api_request_logs(
                    timestamp, endpoint, client_id, vault_id, namespace, status, reason, public_safe_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.timestamp,
                        item.endpoint,
                        item.client_id,
                        item.vault_id,
                        item.namespace,
                        item.status,
                        item.reason,
                        item.public_safe_message,
                    )
                    for item in product.api.api_request_log
                ],
            )
            connection.executemany(
                """
                INSERT INTO key_lifecycle_events(
                    timestamp, event_type, client_id, key_id, operator_id, reason, public_safe_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.timestamp,
                        item.event_type,
                        item.client_id,
                        item.key_id,
                        item.operator_id,
                        item.reason,
                        item.public_safe_message,
                    )
                    for item in lifecycle.lifecycle_events
                ],
            )
            connection.executemany(
                "INSERT INTO events VALUES (?, ?)",
                [(scope, self._json(payload)) for scope, payload in product.api.events.items()],
            )
            connection.executemany(
                "INSERT INTO packets VALUES (?, ?)",
                [(packet_id, self._json(payload)) for packet_id, payload in product.api.packets.items()],
            )
            report_rows = []
            for visibility, records in (
                ("public", product.api.public_reports),
                ("private", product.api.private_reports),
            ):
                report_rows.extend(
                    (
                        report_id,
                        visibility,
                        payload.get("client_id", ""),
                        payload.get("vault_id", ""),
                        payload.get("namespace", ""),
                        self._json(payload),
                    )
                    for report_id, payload in records.items()
                )
            connection.executemany("INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?)", report_rows)
            connection.executemany(
                "INSERT INTO dashboard_snapshots VALUES (?, ?, ?)",
                [
                    (
                        user_id,
                        self._json(self._safe_dashboard_snapshot(product, user_id)),
                        utc_now(),
                    )
                    for user_id in product.accounts.accounts
                ],
            )
            connection.execute(
                """
                INSERT INTO audit_metadata(metadata_key, metadata_json, updated_at)
                VALUES('validation_outcomes', ?, ?)
                """,
                (self._json(lifecycle.validation_outcomes), utc_now()),
            )
            connection.execute(
                """
                INSERT INTO audit_metadata(metadata_key, metadata_json, updated_at)
                VALUES('activation_events', ?, ?)
                """,
                (self._json({"events": product.activation_events}), utc_now()),
            )
            connection.execute(
                """
                INSERT INTO audit_metadata(metadata_key, metadata_json, updated_at)
                VALUES('saved_state', ?, ?)
                """,
                (
                    self._json(
                        {
                            "schema_version": SCHEMA_VERSION,
                            "raw_keys_persisted": False,
                            "raw_passwords_persisted": False,
                            "reconstructable_dashboard_state": True,
                        }
                    ),
                    utc_now(),
                ),
            )

    def load_product(self) -> SelfServeDashboardV092:
        product = SelfServeDashboardV092()
        foundation = product.api.lifecycle.foundation
        lifecycle = product.api.lifecycle
        with self.connect() as connection:
            for row in connection.execute("SELECT * FROM users"):
                account = SelfServeAccount(**dict(row))
                product.accounts.accounts[account.user_id] = account
                product.accounts.email_index[account.email] = account.user_id
            for row in connection.execute("SELECT * FROM sessions"):
                session = LocalSession(**dict(row))
                product.accounts.sessions[session.session_id] = session
            for row in connection.execute("SELECT * FROM plans"):
                subscription = PlanSubscription(**dict(row))
                product.plans.subscriptions[subscription.user_id] = subscription
            for row in connection.execute("SELECT * FROM monthly_usage"):
                product.plans.monthly_usage[(row["user_id"], row["month_key"])] = row["request_count"]
            for row in connection.execute("SELECT * FROM usage_limits"):
                limit = UsageLimit(**dict(row))
                foundation.usage_limits[limit.usage_limit_id] = limit
            for row in connection.execute("SELECT * FROM clients"):
                client = Client(
                    client_id=row["client_id"],
                    organisation=row["organisation"],
                    contact_email=row["contact_email"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                foundation.clients[client.client_id] = client
                vault_row = connection.execute(
                    "SELECT * FROM vaults WHERE client_id = ? ORDER BY created_at LIMIT 1",
                    (client.client_id,),
                ).fetchone()
                namespace_row = connection.execute(
                    "SELECT * FROM namespaces WHERE client_id = ? ORDER BY created_at LIMIT 1",
                    (client.client_id,),
                ).fetchone()
                if vault_row and namespace_row:
                    scope = SelfServeClientScope(
                        user_id=row["user_id"],
                        client_id=client.client_id,
                        vault_id=vault_row["vault_id"],
                        namespace=namespace_row["namespace"],
                        usage_limit_id=row["usage_limit_id"],
                        plan_id=row["plan_id"],
                        status=client.status,
                        created_at=client.created_at,
                    )
                    product.keys.scopes_by_user[scope.user_id] = scope
                    product.keys.user_by_client[scope.client_id] = scope.user_id
            for row in connection.execute("SELECT * FROM vaults"):
                vault = Vault(**dict(row))
                foundation.vaults[vault.vault_id] = vault
            for row in connection.execute("SELECT * FROM namespaces"):
                namespace = Namespace(
                    namespace=row["namespace"],
                    vault_id=row["vault_id"],
                    client_id=row["client_id"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                foundation.namespaces[row["namespace_id"]] = namespace
            for row in connection.execute("SELECT * FROM applications"):
                app = SelfServeApplication(**dict(row))
                product.keys.applications_by_client.setdefault(app.client_id, {})[app.application_reference] = app
            for row in connection.execute("SELECT * FROM api_keys"):
                lifecycle_record = LifecycleKeyRecord(
                    key_id=row["key_id"],
                    client_id=row["client_id"],
                    safe_key_preview=row["safe_key_preview"],
                    key_hash=row["key_hash"],
                    status=row["status"],
                    created_at=row["created_at"],
                    rotated_at=row["rotated_at"],
                    revoked_at=row["revoked_at"],
                    last_used_at=row["last_used_at"],
                    usage_limit_id=row["usage_limit_id"],
                    vault_id=row["vault_id"],
                    namespace=row["namespace"],
                )
                lifecycle.lifecycle_keys[lifecycle_record.key_id] = lifecycle_record
                foundation.api_keys[lifecycle_record.key_id] = APIKeyRecord(
                    key_id=lifecycle_record.key_id,
                    client_id=lifecycle_record.client_id,
                    key_hash=lifecycle_record.key_hash,
                    status=lifecycle_record.status,
                    created_at=lifecycle_record.created_at,
                    last_used_at=lifecycle_record.last_used_at,
                    usage_limit_id=lifecycle_record.usage_limit_id,
                    key_fingerprint=row["key_fingerprint"],
                )
                product.keys.key_labels[lifecycle_record.key_id] = row["label"]
            for row in connection.execute("SELECT * FROM key_applications"):
                product.keys.key_applications[row["key_id"]] = row["application_reference"]
            for scope in product.keys.scopes_by_user.values():
                product.keys.ensure_default_application(scope.client_id)
            for key_id, record in lifecycle.lifecycle_keys.items():
                product.keys.key_applications.setdefault(key_id, "app_main")
            for row in connection.execute("SELECT * FROM usage_events ORDER BY id"):
                foundation.usage_ledger.append(
                    UsageEvent(
                        timestamp=row["timestamp"],
                        client_id=row["client_id"],
                        vault_id=row["vault_id"],
                        namespace=row["namespace"],
                        operation=row["operation"],
                        count=row["count"],
                        allowed=bool(row["allowed"]),
                    )
                )
            for row in connection.execute("SELECT * FROM request_logs ORDER BY id"):
                foundation.request_log.append(
                    RequestLog(
                        timestamp=row["timestamp"],
                        client_id=row["client_id"],
                        operation=row["operation"],
                        status=row["status"],
                        reason=row["reason"],
                        public_safe_message=row["public_safe_message"],
                    )
                )
            for row in connection.execute("SELECT * FROM api_request_logs ORDER BY id"):
                product.api.api_request_log.append(
                    APIRequestLog(
                        timestamp=row["timestamp"],
                        endpoint=row["endpoint"],
                        client_id=row["client_id"],
                        vault_id=row["vault_id"],
                        namespace=row["namespace"],
                        status=row["status"],
                        reason=row["reason"],
                        public_safe_message=row["public_safe_message"],
                    )
                )
            for row in connection.execute("SELECT * FROM key_lifecycle_events ORDER BY id"):
                lifecycle.lifecycle_events.append(
                    LifecycleEvent(
                        timestamp=row["timestamp"],
                        event_type=row["event_type"],
                        client_id=row["client_id"],
                        key_id=row["key_id"],
                        operator_id=row["operator_id"],
                        reason=row["reason"],
                        public_safe_message=row["public_safe_message"],
                    )
                )
            for row in connection.execute("SELECT * FROM events"):
                product.api.events[row["scope_key"]] = json.loads(row["payload_json"])
            for row in connection.execute("SELECT * FROM packets"):
                product.api.packets[row["packet_id"]] = json.loads(row["payload_json"])
            for row in connection.execute("SELECT * FROM reports"):
                payload = json.loads(row["payload_json"])
                if row["visibility"] == "public":
                    product.api.public_reports[row["report_id"]] = payload
                else:
                    product.api.private_reports[row["report_id"]] = payload
            activation_row = connection.execute(
                "SELECT metadata_json FROM audit_metadata WHERE metadata_key = 'activation_events'"
            ).fetchone()
            if activation_row:
                activation_payload = json.loads(activation_row["metadata_json"])
                product.activation_events = list(activation_payload.get("events", []))[-500:]
            validation = connection.execute(
                "SELECT metadata_json FROM audit_metadata WHERE metadata_key = 'validation_outcomes'"
            ).fetchone()
            lifecycle.validation_outcomes = json.loads(validation["metadata_json"]) if validation else []
        return product

    def table_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in TABLES
            }

    def safe_key_rows(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                {
                    "key_id": row["key_id"],
                    "client_id": row["client_id"],
                    "safe_key_preview": row["safe_key_preview"],
                    "status": row["status"],
                    "vault_id": row["vault_id"],
                    "namespace": row["namespace"],
                }
                for row in connection.execute("SELECT * FROM api_keys ORDER BY created_at")
            ]

    def private_key_hashes(self) -> dict[str, str]:
        with self.connect() as connection:
            return {
                row["key_id"]: row["key_hash"]
                for row in connection.execute("SELECT key_id, key_hash FROM api_keys")
            }

    def raw_value_present(self, raw_value: str) -> bool:
        if not raw_value:
            return False
        with self.connect() as connection:
            for table in TABLES:
                columns = [
                    item["name"]
                    for item in connection.execute(f"PRAGMA table_info({table})")
                    if str(item["type"]).upper().startswith("TEXT")
                ]
                for column in columns:
                    found = connection.execute(
                        f"SELECT 1 FROM {table} WHERE {column} = ? OR {column} LIKE ? LIMIT 1",
                        (raw_value, f"%{raw_value}%"),
                    ).fetchone()
                    if found:
                        return True
        return False

    def read_dashboard_snapshot(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM dashboard_snapshots WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return json.loads(row["snapshot_json"]) if row else None

    def set_audit_metadata(self, key: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_metadata(metadata_key, metadata_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(metadata_key) DO UPDATE SET
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (key, self._json(payload), utc_now()),
            )

    def get_audit_metadata(self, key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT metadata_json FROM audit_metadata WHERE metadata_key = ?",
                (key,),
            ).fetchone()
        return json.loads(row["metadata_json"]) if row else None

    def _clear_state(self, connection: sqlite3.Connection) -> None:
        delete_order = (
            "dashboard_snapshots",
            "reports",
            "packets",
            "events",
            "key_lifecycle_events",
            "api_request_logs",
            "request_logs",
            "usage_events",
            "monthly_usage",
            "key_applications",
            "api_keys",
            "namespaces",
            "vaults",
            "applications",
            "clients",
            "usage_limits",
            "plans",
            "sessions",
            "users",
        )
        for table in delete_order:
            connection.execute(f"DELETE FROM {table}")
        connection.execute(
            "DELETE FROM audit_metadata WHERE metadata_key IN ('validation_outcomes', 'activation_events', 'saved_state')"
        )

    def _safe_dashboard_snapshot(
        self,
        product: SelfServeDashboardV092,
        user_id: str,
    ) -> dict[str, Any]:
        account = product.accounts.accounts[user_id]
        subscription = product.plans.subscriptions.get(user_id)
        scope = product.keys.scopes_by_user.get(user_id)
        key_rows = []
        report_count = 0
        request_count = 0
        if scope:
            key_rows = [
                {
                    "key_id": item.key_id,
                    "label": product.keys.key_labels.get(item.key_id, "Unlabelled key"),
                    "safe_key_preview": item.safe_key_preview,
                    "status": item.status,
                }
                for item in product.api.lifecycle.lifecycle_keys.values()
                if item.client_id == scope.client_id
            ]
            report_count = sum(
                1
                for item in product.api.public_reports.values()
                if item.get("client_id") == scope.client_id
            )
            request_count = sum(
                1 for item in product.api.api_request_log if item.client_id == scope.client_id
            )
        return {
            "account": product.accounts.public_account(account),
            "plan_id": subscription.plan_id if subscription else None,
            "plan_status": subscription.status if subscription else None,
            "client_scope": product.keys.public_scope(scope) if scope else None,
            "api_keys": key_rows,
            "usage": product.plans.usage_summary(user_id),
            "request_log_count": request_count,
            "public_report_count": report_count,
            "credential_values_exposed": False,
            "reconstructable": True,
        }

    def _json(self, payload: Any) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)
