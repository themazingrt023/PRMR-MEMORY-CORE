"""Postgres repository for durable PRMR self-serve product state."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any, Iterator

from prmr.product.api_key_lifecycle_v070 import LifecycleEvent, LifecycleKeyRecord
from prmr.product.controlled_alpha_api_v071 import APIRequestLog
from prmr.product.hosted_backend_foundation_v069 import (
    APIKeyRecord,
    Client,
    Namespace,
    RequestLog,
    UsageEvent,
    UsageLimit,
    Vault,
    utc_now,
)
from prmr.product.self_serve_accounts_v092 import LocalSession, SelfServeAccount
from prmr.product.self_serve_api_keys_v092 import SelfServeClientScope
from prmr.product.self_serve_dashboard_v092 import SelfServeDashboardV092
from prmr.product.self_serve_plans_v092 import PlanSubscription


SCHEMA_NAME = "prmr_self_serve"
SCHEMA_VERSION = "0.94.1"
TABLES = (
    "users",
    "sessions",
    "plans",
    "clients",
    "vaults",
    "namespaces",
    "usage_limits",
    "api_keys",
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
)


class PostgresDriverUnavailable(RuntimeError):
    """Raised when the optional Postgres driver is not installed."""


def _driver() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise PostgresDriverUnavailable(
            'Postgres mode requires the "psycopg[binary]" package.'
        ) from exc
    return psycopg, dict_row


class SelfServeRepositoryPostgresV0941:
    """Persist and reconstruct V0.92 product state in private Postgres tables."""

    def __init__(self, database_url: str, *, initialize: bool = True) -> None:
        self._database_url = database_url.strip()
        if not self._database_url:
            raise ValueError("DATABASE_URL is required for Postgres storage.")
        if initialize:
            self.initialize()

    @property
    def backend_name(self) -> str:
        return "postgres"

    @contextmanager
    def connect(self) -> Iterator[Any]:
        psycopg, dict_row = _driver()
        connection = psycopg.connect(
            self._database_url,
            row_factory=dict_row,
            prepare_threshold=None,
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the private schema, tables, and indexes without deleting data."""

        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    email_verification_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    verified_at TEXT
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.users(user_id),
                    token_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.plans (
                    user_id TEXT PRIMARY KEY REFERENCES {SCHEMA_NAME}.users(user_id),
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    billing_status TEXT NOT NULL,
                    selected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.usage_limits (
                    usage_limit_id TEXT PRIMARY KEY,
                    max_events_per_day INTEGER NOT NULL,
                    max_packets_per_day INTEGER NOT NULL,
                    max_reports_per_day INTEGER NOT NULL,
                    alpha_limit_reason TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.clients (
                    client_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE REFERENCES {SCHEMA_NAME}.users(user_id),
                    organisation TEXT NOT NULL,
                    contact_email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    usage_limit_id TEXT NOT NULL
                        REFERENCES {SCHEMA_NAME}.usage_limits(usage_limit_id)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.vaults (
                    vault_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.clients(client_id),
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.namespaces (
                    namespace_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    vault_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.vaults(vault_id),
                    client_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.clients(client_id),
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.api_keys (
                    key_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.clients(client_id),
                    safe_key_preview TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    rotated_at TEXT,
                    revoked_at TEXT,
                    last_used_at TEXT,
                    usage_limit_id TEXT NOT NULL
                        REFERENCES {SCHEMA_NAME}.usage_limits(usage_limit_id),
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    label TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.monthly_usage (
                    user_id TEXT NOT NULL REFERENCES {SCHEMA_NAME}.users(user_id),
                    month_key TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    PRIMARY KEY(user_id, month_key)
                )
                """
            )
            for table, columns in (
                (
                    "usage_events",
                    """
                    timestamp TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    allowed BOOLEAN NOT NULL
                    """,
                ),
                (
                    "request_logs",
                    """
                    timestamp TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                    """,
                ),
                (
                    "api_request_logs",
                    """
                    timestamp TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                    """,
                ),
                (
                    "key_lifecycle_events",
                    """
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    key_id TEXT,
                    operator_id TEXT,
                    reason TEXT NOT NULL,
                    public_safe_message TEXT NOT NULL
                    """,
                ),
            ):
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.{table} (
                        event_key TEXT PRIMARY KEY,
                        row_order BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
                        {columns}
                    )
                    """
                )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.events (
                    scope_key TEXT PRIMARY KEY,
                    payload_json JSONB NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.packets (
                    packet_id TEXT PRIMARY KEY,
                    payload_json JSONB NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.reports (
                    report_id TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    PRIMARY KEY(report_id, visibility)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.dashboard_snapshots (
                    user_id TEXT PRIMARY KEY REFERENCES {SCHEMA_NAME}.users(user_id),
                    snapshot_json JSONB NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.audit_metadata (
                    metadata_key TEXT PRIMARY KEY,
                    metadata_json JSONB NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            for index_name, table, column in (
                ("sessions_user_id_idx", "sessions", "user_id"),
                ("clients_usage_limit_id_idx", "clients", "usage_limit_id"),
                ("vaults_client_id_idx", "vaults", "client_id"),
                ("namespaces_vault_id_idx", "namespaces", "vault_id"),
                ("namespaces_client_id_idx", "namespaces", "client_id"),
                ("api_keys_client_id_idx", "api_keys", "client_id"),
                ("api_keys_usage_limit_id_idx", "api_keys", "usage_limit_id"),
                ("monthly_usage_user_id_idx", "monthly_usage", "user_id"),
                ("reports_client_id_idx", "reports", "client_id"),
            ):
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {SCHEMA_NAME}.{table} ({column})"
                )
            self._upsert_metadata(
                cursor,
                "schema_version",
                {"version": SCHEMA_VERSION, "destructive_migration": False},
            )

    def save_product(self, product: SelfServeDashboardV092) -> None:
        """Upsert current product state without table-wide deletes or truncation."""

        foundation = product.api.lifecycle.foundation
        lifecycle = product.api.lifecycle
        with self.connect() as connection:
            cursor = connection.cursor()
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.users(
                    user_id, name, email, password_salt, password_hash, status,
                    email_verification_mode, created_at, verified_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    name=EXCLUDED.name,
                    email=EXCLUDED.email,
                    password_salt=EXCLUDED.password_salt,
                    password_hash=EXCLUDED.password_hash,
                    status=EXCLUDED.status,
                    email_verification_mode=EXCLUDED.email_verification_mode,
                    verified_at=EXCLUDED.verified_at
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.sessions(
                    session_id, user_id, token_hash, status, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=EXCLUDED.user_id,
                    token_hash=EXCLUDED.token_hash,
                    status=EXCLUDED.status
                """,
                [
                    (item.session_id, item.user_id, item.token_hash, item.status, item.created_at)
                    for item in product.accounts.sessions.values()
                ],
            )
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.plans(
                    user_id, plan_id, status, billing_status, selected_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id=EXCLUDED.plan_id,
                    status=EXCLUDED.status,
                    billing_status=EXCLUDED.billing_status,
                    updated_at=EXCLUDED.updated_at
                """,
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.usage_limits(
                    usage_limit_id, max_events_per_day, max_packets_per_day,
                    max_reports_per_day, alpha_limit_reason
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(usage_limit_id) DO UPDATE SET
                    max_events_per_day=EXCLUDED.max_events_per_day,
                    max_packets_per_day=EXCLUDED.max_packets_per_day,
                    max_reports_per_day=EXCLUDED.max_reports_per_day,
                    alpha_limit_reason=EXCLUDED.alpha_limit_reason
                """,
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.clients(
                    client_id, user_id, organisation, contact_email, status,
                    created_at, plan_id, usage_limit_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(client_id) DO UPDATE SET
                    organisation=EXCLUDED.organisation,
                    contact_email=EXCLUDED.contact_email,
                    status=EXCLUDED.status,
                    plan_id=EXCLUDED.plan_id,
                    usage_limit_id=EXCLUDED.usage_limit_id
                """,
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.vaults(vault_id, client_id, status, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(vault_id) DO UPDATE SET
                    client_id=EXCLUDED.client_id,
                    status=EXCLUDED.status
                """,
                [
                    (item.vault_id, item.client_id, item.status, item.created_at)
                    for item in foundation.vaults.values()
                ],
            )
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.namespaces(
                    namespace_id, namespace, vault_id, client_id, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(namespace_id) DO UPDATE SET
                    namespace=EXCLUDED.namespace,
                    vault_id=EXCLUDED.vault_id,
                    client_id=EXCLUDED.client_id,
                    status=EXCLUDED.status
                """,
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.api_keys(
                    key_id, client_id, safe_key_preview, key_hash, key_fingerprint,
                    status, created_at, rotated_at, revoked_at, last_used_at,
                    usage_limit_id, vault_id, namespace, label
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(key_id) DO UPDATE SET
                    safe_key_preview=EXCLUDED.safe_key_preview,
                    key_hash=EXCLUDED.key_hash,
                    key_fingerprint=EXCLUDED.key_fingerprint,
                    status=EXCLUDED.status,
                    rotated_at=EXCLUDED.rotated_at,
                    revoked_at=EXCLUDED.revoked_at,
                    last_used_at=EXCLUDED.last_used_at,
                    usage_limit_id=EXCLUDED.usage_limit_id,
                    vault_id=EXCLUDED.vault_id,
                    namespace=EXCLUDED.namespace,
                    label=EXCLUDED.label
                """,
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.monthly_usage(user_id, month_key, request_count)
                VALUES (%s, %s, %s)
                ON CONFLICT(user_id, month_key) DO UPDATE SET
                    request_count=EXCLUDED.request_count
                """,
                [
                    (user_id, month_key, count)
                    for (user_id, month_key), count in product.plans.monthly_usage.items()
                ],
            )
            self._save_history(cursor, product)
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.events(scope_key, payload_json)
                VALUES (%s, %s::jsonb)
                ON CONFLICT(scope_key) DO UPDATE SET payload_json=EXCLUDED.payload_json
                """,
                [(scope, self._json(payload)) for scope, payload in product.api.events.items()],
            )
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.packets(packet_id, payload_json)
                VALUES (%s, %s::jsonb)
                ON CONFLICT(packet_id) DO UPDATE SET payload_json=EXCLUDED.payload_json
                """,
                [(packet_id, self._json(payload)) for packet_id, payload in product.api.packets.items()],
            )
            report_rows: list[tuple[Any, ...]] = []
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
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.reports(
                    report_id, visibility, client_id, vault_id, namespace, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT(report_id, visibility) DO UPDATE SET
                    client_id=EXCLUDED.client_id,
                    vault_id=EXCLUDED.vault_id,
                    namespace=EXCLUDED.namespace,
                    payload_json=EXCLUDED.payload_json
                """,
                report_rows,
            )
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.dashboard_snapshots(
                    user_id, snapshot_json, updated_at
                ) VALUES (%s, %s::jsonb, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    snapshot_json=EXCLUDED.snapshot_json,
                    updated_at=EXCLUDED.updated_at
                """,
                [
                    (
                        user_id,
                        self._json(self._safe_dashboard_snapshot(product, user_id)),
                        utc_now(),
                    )
                    for user_id in product.accounts.accounts
                ],
            )
            self._upsert_metadata(cursor, "validation_outcomes", lifecycle.validation_outcomes)
            self._upsert_metadata(
                cursor,
                "saved_state",
                {
                    "schema_version": SCHEMA_VERSION,
                    "raw_keys_persisted": False,
                    "raw_passwords_persisted": False,
                    "reconstructable_dashboard_state": True,
                    "save_strategy": "idempotent_upsert_without_table_wipe",
                },
            )

    def load_product(self) -> SelfServeDashboardV092:
        product = SelfServeDashboardV092()
        foundation = product.api.lifecycle.foundation
        lifecycle = product.api.lifecycle
        with self.connect() as connection:
            cursor = connection.cursor()
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.users"):
                account = SelfServeAccount(**row)
                product.accounts.accounts[account.user_id] = account
                product.accounts.email_index[account.email] = account.user_id
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.sessions"):
                session = LocalSession(**row)
                product.accounts.sessions[session.session_id] = session
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.plans"):
                subscription = PlanSubscription(**row)
                product.plans.subscriptions[subscription.user_id] = subscription
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.monthly_usage"):
                product.plans.monthly_usage[(row["user_id"], row["month_key"])] = row["request_count"]
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.usage_limits"):
                limit = UsageLimit(**row)
                foundation.usage_limits[limit.usage_limit_id] = limit
            clients = self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.clients")
            for row in clients:
                client = Client(
                    client_id=row["client_id"],
                    organisation=row["organisation"],
                    contact_email=row["contact_email"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                foundation.clients[client.client_id] = client
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA_NAME}.vaults
                    WHERE client_id = %s ORDER BY created_at LIMIT 1
                    """,
                    (client.client_id,),
                )
                vault_row = cursor.fetchone()
                cursor.execute(
                    f"""
                    SELECT * FROM {SCHEMA_NAME}.namespaces
                    WHERE client_id = %s ORDER BY created_at LIMIT 1
                    """,
                    (client.client_id,),
                )
                namespace_row = cursor.fetchone()
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
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.vaults"):
                vault = Vault(**row)
                foundation.vaults[vault.vault_id] = vault
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.namespaces"):
                namespace = Namespace(
                    namespace=row["namespace"],
                    vault_id=row["vault_id"],
                    client_id=row["client_id"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                foundation.namespaces[row["namespace_id"]] = namespace
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.api_keys"):
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
            for row in self._fetchall(
                cursor, f"SELECT * FROM {SCHEMA_NAME}.usage_events ORDER BY row_order"
            ):
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
            for row in self._fetchall(
                cursor, f"SELECT * FROM {SCHEMA_NAME}.request_logs ORDER BY row_order"
            ):
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
            for row in self._fetchall(
                cursor, f"SELECT * FROM {SCHEMA_NAME}.api_request_logs ORDER BY row_order"
            ):
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
            for row in self._fetchall(
                cursor, f"SELECT * FROM {SCHEMA_NAME}.key_lifecycle_events ORDER BY row_order"
            ):
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
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.events"):
                product.api.events[row["scope_key"]] = self._json_value(row["payload_json"])
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.packets"):
                product.api.packets[row["packet_id"]] = self._json_value(row["payload_json"])
            for row in self._fetchall(cursor, f"SELECT * FROM {SCHEMA_NAME}.reports"):
                payload = self._json_value(row["payload_json"])
                target = (
                    product.api.public_reports
                    if row["visibility"] == "public"
                    else product.api.private_reports
                )
                target[row["report_id"]] = payload
            cursor.execute(
                f"""
                SELECT metadata_json FROM {SCHEMA_NAME}.audit_metadata
                WHERE metadata_key = %s
                """,
                ("validation_outcomes",),
            )
            validation = cursor.fetchone()
            lifecycle.validation_outcomes = (
                self._json_value(validation["metadata_json"]) if validation else []
            )
        return product

    def table_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            cursor = connection.cursor()
            counts: dict[str, int] = {}
            for table in TABLES:
                cursor.execute(f"SELECT COUNT(*) AS count FROM {SCHEMA_NAME}.{table}")
                counts[table] = int(cursor.fetchone()["count"])
            return counts

    def safe_key_rows(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"""
                SELECT key_id, client_id, safe_key_preview, status, vault_id, namespace
                FROM {SCHEMA_NAME}.api_keys ORDER BY created_at
                """
            )
            return list(cursor.fetchall())

    def private_key_hashes(self) -> dict[str, str]:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT key_id, key_hash FROM {SCHEMA_NAME}.api_keys")
            return {row["key_id"]: row["key_hash"] for row in cursor.fetchall()}

    def raw_value_present(self, raw_value: str) -> bool:
        if not raw_value:
            return False
        with self.connect() as connection:
            cursor = connection.cursor()
            for table in TABLES:
                cursor.execute(
                    f"""
                    SELECT 1 FROM {SCHEMA_NAME}.{table} AS record
                    WHERE to_jsonb(record)::text LIKE %s LIMIT 1
                    """,
                    (f"%{raw_value}%",),
                )
                if cursor.fetchone():
                    return True
        return False

    def read_dashboard_snapshot(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"""
                SELECT snapshot_json FROM {SCHEMA_NAME}.dashboard_snapshots
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        return self._json_value(row["snapshot_json"]) if row else None

    def set_audit_metadata(self, key: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            self._upsert_metadata(connection.cursor(), key, payload)

    def get_audit_metadata(self, key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"""
                SELECT metadata_json FROM {SCHEMA_NAME}.audit_metadata
                WHERE metadata_key = %s
                """,
                (key,),
            )
            row = cursor.fetchone()
        return self._json_value(row["metadata_json"]) if row else None

    def _save_history(self, cursor: Any, product: SelfServeDashboardV092) -> None:
        foundation = product.api.lifecycle.foundation
        lifecycle = product.api.lifecycle
        history_sets = (
            (
                "usage_events",
                [
                    (
                        self._history_key("usage", index, item),
                        item.timestamp,
                        item.client_id,
                        item.vault_id,
                        item.namespace,
                        item.operation,
                        item.count,
                        bool(item.allowed),
                    )
                    for index, item in enumerate(foundation.usage_ledger)
                ],
                "event_key, timestamp, client_id, vault_id, namespace, operation, count, allowed",
                8,
            ),
            (
                "request_logs",
                [
                    (
                        self._history_key("request", index, item),
                        item.timestamp,
                        item.client_id,
                        item.operation,
                        item.status,
                        item.reason,
                        item.public_safe_message,
                    )
                    for index, item in enumerate(foundation.request_log)
                ],
                "event_key, timestamp, client_id, operation, status, reason, public_safe_message",
                7,
            ),
            (
                "api_request_logs",
                [
                    (
                        self._history_key("api_request", index, item),
                        item.timestamp,
                        item.endpoint,
                        item.client_id,
                        item.vault_id,
                        item.namespace,
                        item.status,
                        item.reason,
                        item.public_safe_message,
                    )
                    for index, item in enumerate(product.api.api_request_log)
                ],
                (
                    "event_key, timestamp, endpoint, client_id, vault_id, namespace, "
                    "status, reason, public_safe_message"
                ),
                9,
            ),
            (
                "key_lifecycle_events",
                [
                    (
                        self._history_key("key_lifecycle", index, item),
                        item.timestamp,
                        item.event_type,
                        item.client_id,
                        item.key_id,
                        item.operator_id,
                        item.reason,
                        item.public_safe_message,
                    )
                    for index, item in enumerate(lifecycle.lifecycle_events)
                ],
                (
                    "event_key, timestamp, event_type, client_id, key_id, operator_id, "
                    "reason, public_safe_message"
                ),
                8,
            ),
        )
        for table, rows, columns, value_count in history_sets:
            placeholders = ", ".join(["%s"] * value_count)
            self._executemany(
                cursor,
                f"""
                INSERT INTO {SCHEMA_NAME}.{table}({columns})
                VALUES ({placeholders})
                ON CONFLICT(event_key) DO NOTHING
                """,
                rows,
            )

    def _safe_dashboard_snapshot(
        self,
        product: SelfServeDashboardV092,
        user_id: str,
    ) -> dict[str, Any]:
        account = product.accounts.accounts[user_id]
        subscription = product.plans.subscriptions.get(user_id)
        scope = product.keys.scopes_by_user.get(user_id)
        key_rows: list[dict[str, Any]] = []
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

    def _upsert_metadata(self, cursor: Any, key: str, payload: Any) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA_NAME}.audit_metadata(metadata_key, metadata_json, updated_at)
            VALUES (%s, %s::jsonb, %s)
            ON CONFLICT(metadata_key) DO UPDATE SET
                metadata_json=EXCLUDED.metadata_json,
                updated_at=EXCLUDED.updated_at
            """,
            (key, self._json(payload), utc_now()),
        )

    def _history_key(self, kind: str, index: int, item: Any) -> str:
        payload = json.dumps(
            {"kind": kind, "index": index, "record": vars(item)},
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _executemany(self, cursor: Any, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if rows:
            cursor.executemany(sql, rows)

    def _fetchall(self, cursor: Any, sql: str) -> list[dict[str, Any]]:
        cursor.execute(sql)
        return list(cursor.fetchall())

    def _json(self, payload: Any) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def _json_value(self, payload: Any) -> Any:
        return json.loads(payload) if isinstance(payload, str) else payload


def initialize_postgres_schema(database_url: str) -> None:
    """Initialize V0.94.1 schema without dropping, truncating, or deleting data."""

    SelfServeRepositoryPostgresV0941(database_url, initialize=True)
