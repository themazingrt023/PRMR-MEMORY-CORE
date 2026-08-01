"""Durable, scope-isolated source ledger for PRMR Memory Core."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import logging
import sqlite3
import time
from typing import Any
from uuid import uuid4

from .source_adapters import materialize_segments, prepare_source, sanitize_reference
from .source_integrity import canonical_json, segment_manifest_hash, sha256_text
from .source_models import (
    AuthenticatedScope,
    CANONICALISATION_REVISION,
    IntegrityResult,
    MaintenanceContext,
    SANITISATION_REVISION,
    SEGMENTER_REVISION,
    SOURCE_SCHEMA_REVISION,
    SanitisationReport,
    SegmentPage,
    SourceIngestResult,
    SourceInput,
    SourceLedgerError,
    SourcePage,
    SourceRecord,
    SourceSegment,
)
from .source_retention import is_expired, normalize_timestamp, validate_retention


LOGGER = logging.getLogger("prmr.core.source_ledger")
POSTGRES_SCHEMA = "prmr_self_serve"
SOURCE_TABLE = "prmr_sources"
SEGMENT_TABLE = "prmr_source_segments"


SQLITE_SOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS prmr_source_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    occurred_at TEXT,
    ingested_at TEXT NOT NULL,
    sanitised_payload_json TEXT NOT NULL,
    payload_encoding TEXT NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    canonical_payload_hash_sha256 TEXT NOT NULL,
    segment_manifest_hash_sha256 TEXT NOT NULL,
    idempotency_key_digest TEXT,
    input_fingerprint_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    retention_policy TEXT NOT NULL,
    expires_at TEXT,
    sanitisation_report_json TEXT NOT NULL,
    source_schema_revision TEXT NOT NULL,
    canonicalisation_revision TEXT NOT NULL,
    segmenter_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_key_digest)
);
CREATE TABLE IF NOT EXISTS prmr_source_segments (
    segment_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    parent_segment_id TEXT,
    segment_type TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    start_line INTEGER,
    end_line INTEGER,
    json_pointer TEXT,
    speaker TEXT,
    occurred_at TEXT,
    label TEXT,
    metadata_json TEXT NOT NULL,
    segmenter_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(source_id, sequence_index),
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY(parent_segment_id) REFERENCES prmr_source_segments(segment_id)
);
CREATE INDEX IF NOT EXISTS prmr_sources_scope_idx
    ON prmr_sources(client_id, vault_id, namespace, ingested_at, source_id);
CREATE INDEX IF NOT EXISTS prmr_sources_idempotency_idx
    ON prmr_sources(client_id, vault_id, namespace, idempotency_key_digest);
CREATE INDEX IF NOT EXISTS prmr_sources_type_idx ON prmr_sources(source_type);
CREATE INDEX IF NOT EXISTS prmr_sources_occurred_idx ON prmr_sources(occurred_at);
CREATE INDEX IF NOT EXISTS prmr_sources_ingested_idx ON prmr_sources(ingested_at);
CREATE INDEX IF NOT EXISTS prmr_sources_expires_idx ON prmr_sources(expires_at);
CREATE INDEX IF NOT EXISTS prmr_source_segments_source_idx ON prmr_source_segments(source_id);
CREATE INDEX IF NOT EXISTS prmr_source_segments_occurred_idx ON prmr_source_segments(occurred_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_log(event: str, **fields: Any) -> None:
    allowed = {
        "source_id",
        "source_type",
        "client_id",
        "vault_id",
        "namespace",
        "segment_count",
        "duration_ms",
        "content_size",
        "redaction_count",
        "source_schema_revision",
        "canonicalisation_revision",
        "segmenter_revision",
        "sanitisation_revision",
        "error_code",
        "deleted_source_count",
        "deleted_segment_count",
    }
    payload = {"event": event, **{key: value for key, value in fields.items() if key in allowed}}
    LOGGER.info("%s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def initialize_sqlite_source_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SQLITE_SOURCE_SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO prmr_source_schema_migrations(revision, applied_at) VALUES (?, ?)",
        (SOURCE_SCHEMA_REVISION, utc_now()),
    )


def initialize_postgres_source_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.prmr_source_schema_migrations (
            revision TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{SOURCE_TABLE} (
            source_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            client_id TEXT NOT NULL,
            vault_id TEXT NOT NULL,
            namespace TEXT NOT NULL,
            application_reference TEXT,
            actor_reference TEXT,
            workspace_reference TEXT,
            entity_references_json JSONB NOT NULL,
            session_reference TEXT,
            occurred_at TEXT,
            ingested_at TEXT NOT NULL,
            sanitised_payload_json JSONB NOT NULL,
            payload_encoding TEXT NOT NULL,
            content_hash_sha256 TEXT NOT NULL,
            canonical_payload_hash_sha256 TEXT NOT NULL,
            segment_manifest_hash_sha256 TEXT NOT NULL,
            idempotency_key_digest TEXT,
            input_fingerprint_sha256 TEXT NOT NULL,
            metadata_json JSONB NOT NULL,
            retention_policy TEXT NOT NULL,
            expires_at TEXT,
            sanitisation_report_json JSONB NOT NULL,
            source_schema_revision TEXT NOT NULL,
            canonicalisation_revision TEXT NOT NULL,
            segmenter_revision TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(client_id, vault_id, namespace, idempotency_key_digest)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.{SEGMENT_TABLE} (
            segment_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES {POSTGRES_SCHEMA}.{SOURCE_TABLE}(source_id) ON DELETE CASCADE,
            sequence_index INTEGER NOT NULL,
            parent_segment_id TEXT REFERENCES {POSTGRES_SCHEMA}.{SEGMENT_TABLE}(segment_id),
            segment_type TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash_sha256 TEXT NOT NULL,
            start_offset INTEGER,
            end_offset INTEGER,
            start_line INTEGER,
            end_line INTEGER,
            json_pointer TEXT,
            speaker TEXT,
            occurred_at TEXT,
            label TEXT,
            metadata_json JSONB NOT NULL,
            segmenter_revision TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(source_id, sequence_index)
        )
        """
    )
    indexes = (
        ("prmr_sources_scope_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(client_id, vault_id, namespace, ingested_at, source_id)"),
        ("prmr_sources_idempotency_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(client_id, vault_id, namespace, idempotency_key_digest)"),
        ("prmr_sources_type_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(source_type)"),
        ("prmr_sources_occurred_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(occurred_at)"),
        ("prmr_sources_ingested_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(ingested_at)"),
        ("prmr_sources_expires_idx", f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}(expires_at)"),
        ("prmr_source_segments_source_idx", f"{POSTGRES_SCHEMA}.{SEGMENT_TABLE}(source_id)"),
        ("prmr_source_segments_occurred_idx", f"{POSTGRES_SCHEMA}.{SEGMENT_TABLE}(occurred_at)"),
    )
    for name, expression in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {expression}")
    cursor.execute(
        f"""
        INSERT INTO {POSTGRES_SCHEMA}.prmr_source_schema_migrations(revision, applied_at)
        VALUES (%s, %s)
        ON CONFLICT(revision) DO NOTHING
        """,
        (SOURCE_SCHEMA_REVISION, utc_now()),
    )


class SourceLedger:
    """Store and verify sources using an existing PRMR repository connection."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        if not hasattr(repository, "connect"):
            raise TypeError("SourceLedger requires an existing PRMR repository with connect().")
        self.repository = repository
        self.backend = str(getattr(repository, "backend_name", "sqlite"))
        if self.backend not in {"sqlite", "postgres"}:
            self.backend = "sqlite" if hasattr(repository, "storage_path") else "postgres"
        self.source_table = f"{POSTGRES_SCHEMA}.{SOURCE_TABLE}" if self.backend == "postgres" else SOURCE_TABLE
        self.segment_table = f"{POSTGRES_SCHEMA}.{SEGMENT_TABLE}" if self.backend == "postgres" else SEGMENT_TABLE
        if initialize:
            with self.repository.connect() as connection:
                if self.backend == "postgres":
                    initialize_postgres_source_schema(connection)
                else:
                    initialize_sqlite_source_schema(connection)

    def ingest_source(
        self,
        authenticated_scope: AuthenticatedScope,
        source_input: SourceInput,
    ) -> SourceIngestResult:
        started = time.perf_counter()
        scope = self._validate_scope(authenticated_scope)
        _safe_log(
            "source_ingest_started",
            source_type=str(getattr(source_input.source_type, "value", source_input.source_type)),
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            source_schema_revision=SOURCE_SCHEMA_REVISION,
        )
        try:
            prepared = prepare_source(source_input.source_type, source_input.payload, source_input.metadata)
            references, reference_redactions = self._resolve_references(scope, source_input)
            retention_policy, expires_at = validate_retention(
                source_input.retention_policy,
                source_input.expires_at,
            )
            occurred_at = normalize_timestamp(source_input.occurred_at, field_name="occurred_at")
            idempotency_digest = self._idempotency_digest(source_input.idempotency_key)
            report = self._merge_sanitisation_report(prepared.sanitisation_report, reference_redactions)
            content_hash = sha256_text(prepared.stored_representation)
            canonical_hash = sha256_text(prepared.canonical_representation)
            material = {
                "source_type": prepared.source_type,
                "canonical_payload_hash_sha256": canonical_hash,
                "occurred_at": occurred_at,
                **references,
                "metadata": prepared.sanitised_metadata,
                "retention_policy": retention_policy,
                "expires_at": expires_at,
                "source_schema_revision": SOURCE_SCHEMA_REVISION,
                "canonicalisation_revision": CANONICALISATION_REVISION,
                "segmenter_revision": SEGMENTER_REVISION,
                "sanitisation_revision": SANITISATION_REVISION,
            }
            input_fingerprint = sha256_text(canonical_json(material))
            now = utc_now()
            source_id = f"src_{uuid4().hex}"
            segments = materialize_segments(source_id, prepared.segment_drafts, now)
            manifest_hash = segment_manifest_hash(segments)
            record = SourceRecord(
                source_id=source_id,
                source_type=prepared.source_type,
                client_id=scope.client_id,
                vault_id=scope.vault_id,
                namespace=scope.namespace,
                application_reference=references["application_reference"],
                actor_reference=references["actor_reference"],
                workspace_reference=references["workspace_reference"],
                entity_references=references["entity_references"],
                session_reference=references["session_reference"],
                occurred_at=occurred_at,
                ingested_at=now,
                sanitised_payload=prepared.sanitised_payload,
                payload_encoding=(
                    "utf-8"
                    if isinstance(prepared.sanitised_payload, str)
                    else "canonical-json-utf-8"
                ),
                content_hash_sha256=content_hash,
                canonical_payload_hash_sha256=canonical_hash,
                segment_manifest_hash_sha256=manifest_hash,
                idempotency_key_digest=idempotency_digest,
                input_fingerprint_sha256=input_fingerprint,
                metadata=prepared.sanitised_metadata,
                retention_policy=retention_policy,
                expires_at=expires_at,
                sanitisation_report=report,
                source_schema_revision=SOURCE_SCHEMA_REVISION,
                canonicalisation_revision=CANONICALISATION_REVISION,
                segmenter_revision=SEGMENTER_REVISION,
                created_at=now,
                updated_at=now,
            )
            result = self._insert_or_replay(record, segments)
            _safe_log(
                "source_ingest_created" if result.created else "source_ingest_replayed",
                source_id=result.source.source_id,
                source_type=result.source.source_type,
                client_id=scope.client_id,
                vault_id=scope.vault_id,
                namespace=scope.namespace,
                segment_count=result.segment_count,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                content_size=len(prepared.stored_representation.encode("utf-8")),
                redaction_count=report.redaction_count,
                source_schema_revision=SOURCE_SCHEMA_REVISION,
                canonicalisation_revision=CANONICALISATION_REVISION,
                segmenter_revision=SEGMENTER_REVISION,
                sanitisation_revision=SANITISATION_REVISION,
            )
            return result
        except SourceLedgerError as exc:
            _safe_log(
                "source_ingest_conflict" if exc.code == "SOURCE_IDEMPOTENCY_CONFLICT" else "source_ingest_failed",
                source_type=str(getattr(source_input.source_type, "value", source_input.source_type)),
                client_id=scope.client_id,
                vault_id=scope.vault_id,
                namespace=scope.namespace,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                error_code=exc.code,
            )
            raise

    def get_source(self, authenticated_scope: AuthenticatedScope, source_id: str) -> SourceRecord:
        scope = self._validate_scope(authenticated_scope)
        with self.repository.connect() as connection:
            record = self._find_scoped_record(connection, scope, source_id)
        self._require_available(record)
        return record

    def list_sources(
        self,
        authenticated_scope: AuthenticatedScope,
        cursor: str | None = None,
        limit: int = 50,
    ) -> SourcePage:
        scope = self._validate_scope(authenticated_scope)
        offset, safe_limit = self._page(cursor, limit)
        placeholder = "%s" if self.backend == "postgres" else "?"
        sql = f"""
            SELECT * FROM {self.source_table}
            WHERE client_id={placeholder} AND vault_id={placeholder} AND namespace={placeholder}
              AND (expires_at IS NULL OR expires_at > {placeholder})
            ORDER BY ingested_at, source_id
            LIMIT {placeholder} OFFSET {placeholder}
        """
        params = (*scope.memory_boundary(), utc_now(), safe_limit + 1, offset)
        with self.repository.connect() as connection:
            rows = list(connection.execute(sql, params).fetchall())
        records = [self._record_from_row(row) for row in rows]
        records = [record for record in records if self._subject_access_allowed(scope, record)]
        items = records[:safe_limit]
        next_cursor = str(offset + safe_limit) if len(records) > safe_limit else None
        return SourcePage(items=items, next_cursor=next_cursor)

    def list_source_segments(
        self,
        authenticated_scope: AuthenticatedScope,
        source_id: str,
        cursor: str | None = None,
        limit: int = 200,
    ) -> SegmentPage:
        record = self.get_source(authenticated_scope, source_id)
        offset, safe_limit = self._page(cursor, limit, maximum=1000)
        placeholder = "%s" if self.backend == "postgres" else "?"
        with self.repository.connect() as connection:
            rows = list(
                connection.execute(
                    f"""
                    SELECT * FROM {self.segment_table}
                    WHERE source_id={placeholder}
                    ORDER BY sequence_index
                    LIMIT {placeholder} OFFSET {placeholder}
                    """,
                    (record.source_id, safe_limit + 1, offset),
                ).fetchall()
            )
        segments = [self._segment_from_row(row) for row in rows]
        return SegmentPage(
            items=segments[:safe_limit],
            next_cursor=str(offset + safe_limit) if len(segments) > safe_limit else None,
        )

    def verify_source_integrity(
        self,
        authenticated_scope: AuthenticatedScope,
        source_id: str,
    ) -> IntegrityResult:
        scope = self._validate_scope(authenticated_scope)
        with self.repository.connect() as connection:
            record = self._find_scoped_record(connection, scope, source_id)
            self._require_available(record)
            segments = self._segments_for_source(connection, record.source_id)

        stored_representation = self._stored_representation(record)
        canonical_representation = self._canonical_representation(record)
        ordered = sorted(segments, key=lambda item: item.sequence_index)
        checks = {
            "content_hash": sha256_text(stored_representation) == record.content_hash_sha256,
            "canonical_payload_hash": (
                sha256_text(canonical_representation) == record.canonical_payload_hash_sha256
            ),
            "segment_content_hashes": all(
                sha256_text(segment.content) == segment.content_hash_sha256 for segment in ordered
            ),
            "segment_ordering": [segment.sequence_index for segment in ordered] == list(range(len(ordered))),
            "segment_manifest_hash": segment_manifest_hash(ordered) == record.segment_manifest_hash_sha256,
            "segment_source_ownership": all(segment.source_id == record.source_id for segment in ordered),
            "segment_ids": all(self._expected_segment_id(segment) == segment.segment_id for segment in ordered),
        }
        failures = [name for name, passed in checks.items() if not passed]
        result = IntegrityResult(
            source_id=record.source_id,
            verified=not failures,
            checks=checks,
            failures=failures,
            source_schema_revision=record.source_schema_revision,
            segmenter_revision=record.segmenter_revision,
        )
        _safe_log(
            "source_integrity_verified" if result.verified else "source_integrity_failed",
            source_id=record.source_id,
            source_type=record.source_type,
            client_id=record.client_id,
            vault_id=record.vault_id,
            namespace=record.namespace,
            segment_count=len(segments),
            error_code=None if result.verified else "SOURCE_INTEGRITY_FAILED",
        )
        return result

    def delete_source(
        self,
        authenticated_scope: AuthenticatedScope,
        source_id: str,
        reason: str,
    ) -> dict[str, Any]:
        scope = self._validate_scope(authenticated_scope)
        if not isinstance(reason, str) or not reason.strip():
            raise SourceLedgerError("SOURCE_DELETE_FAILED", "A non-empty deletion reason is required.")
        placeholder = "%s" if self.backend == "postgres" else "?"
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            record = self._find_scoped_record(connection, scope, source_id)
            accepted_memory_count = self._accepted_memory_count(
                connection, record.source_id
            )
            entity_relationship_counts = self._entity_relationship_dependency_counts(
                connection, record.source_id
            )
            if accepted_memory_count or any(entity_relationship_counts.values()):
                dependency_counts = {
                    **self._memory_dependency_counts(connection, record.source_id),
                    **entity_relationship_counts,
                    **self._query_dependency_counts(connection, record.source_id),
                }
                raise SourceLedgerError(
                    (
                        "SOURCE_HAS_ADMITTED_MEMORY"
                        if accepted_memory_count
                        else "SOURCE_HAS_ENTITY_RELATIONSHIP_MEMORY"
                    ),
                    "Source is protected because durable memory depends on its provenance.",
                    details={
                        "accepted_memory_count": accepted_memory_count,
                        **dependency_counts,
                    },
                )
            segment_count = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM {self.segment_table} WHERE source_id={placeholder}",
                    (record.source_id,),
                ).fetchone()["count"]
            )
            connection.execute(
                f"DELETE FROM {self.source_table} WHERE source_id={placeholder}",
                (record.source_id,),
            )
        _safe_log(
            "source_deleted",
            source_id=record.source_id,
            source_type=record.source_type,
            client_id=record.client_id,
            vault_id=record.vault_id,
            namespace=record.namespace,
            deleted_source_count=1,
            deleted_segment_count=segment_count,
        )
        return {
            "deleted": True,
            "source_id": record.source_id,
            "deleted_source_count": 1,
            "deleted_segment_count": segment_count,
            "reason_recorded_in_log": True,
            "source_content_exposed": False,
        }

    def purge_expired_sources(
        self,
        maintenance_context: MaintenanceContext,
        now: datetime,
    ) -> dict[str, Any]:
        if not maintenance_context.privileged and maintenance_context.scope is None:
            raise SourceLedgerError("SOURCE_ACCESS_DENIED", "Explicit maintenance authority is required.")
        now_utc = now.astimezone(timezone.utc)
        now_text = now_utc.isoformat().replace("+00:00", "Z")
        where = "expires_at IS NOT NULL AND expires_at <= " + ("%s" if self.backend == "postgres" else "?")
        params: list[Any] = [now_text]
        if maintenance_context.scope is not None:
            scope = self._validate_scope(maintenance_context.scope)
            placeholder = "%s" if self.backend == "postgres" else "?"
            where += f" AND client_id={placeholder} AND vault_id={placeholder} AND namespace={placeholder}"
            params.extend(scope.memory_boundary())
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            rows = list(connection.execute(f"SELECT source_id FROM {self.source_table} WHERE {where}", tuple(params)).fetchall())
            candidate_source_ids = [str(row["source_id"]) for row in rows]
            source_ids: list[str] = []
            skipped_admitted_source_ids: list[str] = []
            for source_id in candidate_source_ids:
                if self._accepted_memory_count(connection, source_id):
                    skipped_admitted_source_ids.append(source_id)
                else:
                    source_ids.append(source_id)
            segment_count = 0
            placeholder = "%s" if self.backend == "postgres" else "?"
            for source_id in source_ids:
                segment_count += int(
                    connection.execute(
                        f"SELECT COUNT(*) AS count FROM {self.segment_table} WHERE source_id={placeholder}",
                        (source_id,),
                    ).fetchone()["count"]
                )
            for source_id in source_ids:
                connection.execute(
                    f"DELETE FROM {self.source_table} WHERE source_id={placeholder}",
                    (source_id,),
                )
        for source_id in source_ids:
            _safe_log("source_expired", source_id=source_id)
        _safe_log(
            "source_purge_completed",
            deleted_source_count=len(source_ids),
            deleted_segment_count=segment_count,
        )
        return {
            "deleted_source_count": len(source_ids),
            "deleted_segment_count": segment_count,
            "skipped_admitted_source_count": len(skipped_admitted_source_ids),
            "source_content_exposed": False,
        }

    def _accepted_memory_count(self, connection: Any, source_id: str) -> int:
        table = (
            f"{POSTGRES_SCHEMA}.prmr_admitted_memory_links"
            if self.backend == "postgres"
            else "prmr_admitted_memory_links"
        )
        placeholder = "%s" if self.backend == "postgres" else "?"
        try:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table} WHERE source_id={placeholder}",
                (source_id,),
            ).fetchone()
        except Exception as exc:
            message = str(exc).lower()
            if (
                "does not exist" in message
                or "no such table" in message
                or "undefinedtable" in type(exc).__name__.lower()
            ):
                return 0
            raise
        return int(row["count"]) if row else 0

    def _query_dependency_counts(
        self, connection: Any, source_id: str
    ) -> dict[str, int]:
        """Report derived query references without making them deletion authority."""

        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        placeholder = "%s" if self.backend == "postgres" else "?"
        empty = {
            "query_evidence_item_count": 0,
            "query_evidence_bundle_count": 0,
            "query_result_count": 0,
        }
        try:
            evidence = connection.execute(
                f"SELECT query_run_id,evidence_bundle_id FROM "
                f"{prefix}prmr_memory_query_evidence_items "
                f"WHERE source_id={placeholder}",
                (source_id,),
            ).fetchall()
            query_runs = {str(row["query_run_id"]) for row in evidence}
            bundle_ids = {str(row["evidence_bundle_id"]) for row in evidence}
            result_count = 0
            if query_runs:
                markers = ",".join([placeholder] * len(query_runs))
                row = connection.execute(
                    f"SELECT COUNT(*) AS count FROM "
                    f"{prefix}prmr_memory_query_results "
                    f"WHERE query_run_id IN ({markers})",
                    tuple(sorted(query_runs)),
                ).fetchone()
                result_count = int(row["count"]) if row else 0
            return {
                "query_evidence_item_count": len(evidence),
                "query_evidence_bundle_count": len(bundle_ids),
                "query_result_count": result_count,
            }
        except Exception as exc:
            message = str(exc).lower()
            if (
                "does not exist" in message
                or "no such table" in message
                or "undefinedtable" in type(exc).__name__.lower()
            ):
                return empty
            raise

    def _entity_relationship_dependency_counts(
        self, connection: Any, source_id: str
    ) -> dict[str, int]:
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        placeholder = "%s" if self.backend == "postgres" else "?"
        empty = {
            "entity_count": 0,
            "identifier_count": 0,
            "alias_count": 0,
            "event_link_count": 0,
            "relationship_count": 0,
            "relationship_evolution_count": 0,
            "entity_reconstruction_count": 0,
        }
        try:
            def count(table: str, column: str) -> int:
                row = connection.execute(
                    f"SELECT COUNT(*) AS count FROM {prefix}{table} "
                    f"WHERE {column}={placeholder}",
                    (source_id,),
                ).fetchone()
                return int(row["count"]) if row else 0

            relationship_rows = connection.execute(
                f"SELECT relationship_id FROM {prefix}prmr_relationships "
                f"WHERE originating_source_id={placeholder}",
                (source_id,),
            ).fetchall()
            relationship_ids = [str(row["relationship_id"]) for row in relationship_rows]
            evolution_count = 0
            if relationship_ids:
                markers = ",".join([placeholder] * len(relationship_ids))
                row = connection.execute(
                    f"SELECT COUNT(*) AS count FROM "
                    f"{prefix}prmr_relationship_evolution_records "
                    f"WHERE source_relationship_id IN ({markers}) "
                    f"OR replacement_relationship_id IN ({markers}) "
                    f"OR resolution_relationship_id IN ({markers})",
                    tuple(relationship_ids) * 3,
                ).fetchone()
                evolution_count = int(row["count"]) if row else 0
            reconstruction_rows = connection.execute(
                f"SELECT source_ids_json FROM "
                f"{prefix}prmr_entity_relationship_reconstructions"
            ).fetchall()
            reconstruction_count = 0
            for row in reconstruction_rows:
                raw = row["source_ids_json"]
                source_ids = json.loads(raw) if isinstance(raw, str) else raw or []
                if source_id in source_ids:
                    reconstruction_count += 1
            return {
                "entity_count": count("prmr_entities", "originating_source_id"),
                "identifier_count": count("prmr_entity_identifiers", "source_id"),
                "alias_count": count("prmr_entity_alias_assertions", "source_id"),
                "event_link_count": count("prmr_event_entity_links", "source_id"),
                "relationship_count": len(relationship_ids),
                "relationship_evolution_count": evolution_count,
                "entity_reconstruction_count": reconstruction_count,
            }
        except Exception as exc:
            message = str(exc).lower()
            if (
                "does not exist" in message
                or "no such table" in message
                or "undefinedtable" in type(exc).__name__.lower()
            ):
                return empty
            raise
    def _memory_dependency_counts(
        self, connection: Any, source_id: str
    ) -> dict[str, int]:
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        placeholder = "%s" if self.backend == "postgres" else "?"
        empty = {
            "evolution_link_count": 0,
            "conflict_count": 0,
            "reconstruction_count": 0,
        }
        try:
            rows = connection.execute(
                f"SELECT admitted_event_id FROM {prefix}prmr_admitted_memory_links "
                f"WHERE source_id={placeholder}",
                (source_id,),
            ).fetchall()
            event_ids = {str(row["admitted_event_id"]) for row in rows}
            if not event_ids:
                return empty
            marker_list = ",".join([placeholder] * len(event_ids))
            params = tuple(sorted(event_ids))
            evolution = connection.execute(
                f"SELECT COUNT(*) AS count FROM {prefix}prmr_memory_evolution_records "
                f"WHERE source_event_id IN ({marker_list}) "
                f"OR replacement_event_id IN ({marker_list}) "
                f"OR resolution_event_id IN ({marker_list})",
                params + params + params,
            ).fetchone()
            conflicts = connection.execute(
                f"SELECT conflicting_event_ids_json,resolution_event_id "
                f"FROM {prefix}prmr_memory_conflicts"
            ).fetchall()
            conflict_count = 0
            for row in conflicts:
                raw = row["conflicting_event_ids_json"]
                linked = set(json.loads(raw) if isinstance(raw, str) else raw or [])
                if linked & event_ids or str(row["resolution_event_id"] or "") in event_ids:
                    conflict_count += 1
            reconstructions = connection.execute(
                f"SELECT payload_json FROM {prefix}prmr_memory_reconstructions"
            ).fetchall()
            reconstruction_count = 0
            for row in reconstructions:
                raw = row["payload_json"]
                payload = json.loads(raw) if isinstance(raw, str) else raw or {}
                references = payload.get("provenance_references", [])
                if any(
                    str(item.get("event_id", "")) in event_ids
                    for item in references
                    if isinstance(item, dict)
                ):
                    reconstruction_count += 1
            return {
                "evolution_link_count": int(evolution["count"]) if evolution else 0,
                "conflict_count": conflict_count,
                "reconstruction_count": reconstruction_count,
            }
        except Exception as exc:
            message = str(exc).lower()
            if (
                "does not exist" in message
                or "no such table" in message
                or "undefinedtable" in type(exc).__name__.lower()
            ):
                return empty
            raise

    def _insert_or_replay(
        self,
        record: SourceRecord,
        segments: list[SourceSegment],
    ) -> SourceIngestResult:
        with self.repository.connect() as connection:
            if self.backend == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            if record.idempotency_key_digest:
                existing = self._find_by_idempotency(connection, record)
                if existing:
                    return self._replay_result(connection, existing, record.input_fingerprint_sha256)

            inserted = self._insert_record(connection, record)
            if not inserted:
                existing = self._find_by_idempotency(connection, record)
                if existing:
                    return self._replay_result(connection, existing, record.input_fingerprint_sha256)
                raise SourceLedgerError("SOURCE_STORAGE_FAILED", "Source could not be stored.", retryable=True)
            self._insert_segments(connection, segments)
        return SourceIngestResult(
            source=record,
            created=True,
            replayed=False,
            segment_count=len(segments),
            integrity_status="verified",
        )

    def _insert_record(self, connection: Any, record: SourceRecord) -> bool:
        columns = (
            "source_id", "source_type", "client_id", "vault_id", "namespace",
            "application_reference", "actor_reference", "workspace_reference",
            "entity_references_json", "session_reference", "occurred_at", "ingested_at",
            "sanitised_payload_json", "payload_encoding", "content_hash_sha256",
            "canonical_payload_hash_sha256", "segment_manifest_hash_sha256",
            "idempotency_key_digest", "input_fingerprint_sha256", "metadata_json",
            "retention_policy", "expires_at", "sanitisation_report_json",
            "source_schema_revision", "canonicalisation_revision", "segmenter_revision",
            "created_at", "updated_at",
        )
        values = (
            record.source_id,
            record.source_type,
            record.client_id,
            record.vault_id,
            record.namespace,
            record.application_reference,
            record.actor_reference,
            record.workspace_reference,
            self._json(record.entity_references),
            record.session_reference,
            record.occurred_at,
            record.ingested_at,
            self._json(record.sanitised_payload),
            record.payload_encoding,
            record.content_hash_sha256,
            record.canonical_payload_hash_sha256,
            record.segment_manifest_hash_sha256,
            record.idempotency_key_digest,
            record.input_fingerprint_sha256,
            self._json(record.metadata),
            record.retention_policy,
            record.expires_at,
            self._json(record.sanitisation_report.to_dict()),
            record.source_schema_revision,
            record.canonicalisation_revision,
            record.segmenter_revision,
            record.created_at,
            record.updated_at,
        )
        placeholders = ",".join(["%s"] * len(columns)) if self.backend == "postgres" else ",".join(["?"] * len(columns))
        sql = f"INSERT INTO {self.source_table} ({','.join(columns)}) VALUES ({placeholders})"
        if self.backend == "postgres":
            sql += " ON CONFLICT (client_id, vault_id, namespace, idempotency_key_digest) DO NOTHING RETURNING source_id"
            return connection.execute(sql, values).fetchone() is not None
        try:
            connection.execute(sql, values)
            return True
        except sqlite3.IntegrityError:
            return False

    def _insert_segments(self, connection: Any, segments: list[SourceSegment]) -> None:
        columns = (
            "segment_id", "source_id", "sequence_index", "parent_segment_id", "segment_type",
            "content", "content_hash_sha256", "start_offset", "end_offset", "start_line",
            "end_line", "json_pointer", "speaker", "occurred_at", "label", "metadata_json",
            "segmenter_revision", "created_at",
        )
        placeholders = ",".join(["%s"] * len(columns)) if self.backend == "postgres" else ",".join(["?"] * len(columns))
        sql = f"INSERT INTO {self.segment_table} ({','.join(columns)}) VALUES ({placeholders})"
        rows = [
            (
                item.segment_id, item.source_id, item.sequence_index, item.parent_segment_id,
                item.segment_type, item.content, item.content_hash_sha256, item.start_offset,
                item.end_offset, item.start_line, item.end_line, item.json_pointer, item.speaker,
                item.occurred_at, item.label, self._json(item.metadata), item.segmenter_revision,
                item.created_at,
            )
            for item in segments
        ]
        connection.cursor().executemany(sql, rows)

    def _find_by_idempotency(self, connection: Any, record: SourceRecord) -> SourceRecord | None:
        placeholder = "%s" if self.backend == "postgres" else "?"
        row = connection.execute(
            f"""
            SELECT * FROM {self.source_table}
            WHERE client_id={placeholder} AND vault_id={placeholder} AND namespace={placeholder}
              AND idempotency_key_digest={placeholder}
            """,
            (
                record.client_id,
                record.vault_id,
                record.namespace,
                record.idempotency_key_digest,
            ),
        ).fetchone()
        return self._record_from_row(row) if row else None

    def _replay_result(
        self,
        connection: Any,
        existing: SourceRecord,
        input_fingerprint: str,
    ) -> SourceIngestResult:
        if existing.input_fingerprint_sha256 != input_fingerprint:
            raise SourceLedgerError(
                "SOURCE_IDEMPOTENCY_CONFLICT",
                "The idempotency key was already used for different source input in this scope.",
            )
        count = len(self._segments_for_source(connection, existing.source_id))
        return SourceIngestResult(
            source=existing,
            created=False,
            replayed=True,
            segment_count=count,
            integrity_status="verified",
        )

    def _find_scoped_record(
        self,
        connection: Any,
        scope: AuthenticatedScope,
        source_id: str,
    ) -> SourceRecord:
        placeholder = "%s" if self.backend == "postgres" else "?"
        row = connection.execute(
            f"""
            SELECT * FROM {self.source_table}
            WHERE source_id={placeholder} AND client_id={placeholder}
              AND vault_id={placeholder} AND namespace={placeholder}
            """,
            (source_id, *scope.memory_boundary()),
        ).fetchone()
        if not row:
            raise SourceLedgerError("SOURCE_NOT_FOUND", "Source was not found in the authenticated scope.")
        record = self._record_from_row(row)
        if not self._subject_access_allowed(scope, record):
            raise SourceLedgerError("SOURCE_NOT_FOUND", "Source was not found in the authenticated scope.")
        return record

    def _segments_for_source(self, connection: Any, source_id: str) -> list[SourceSegment]:
        placeholder = "%s" if self.backend == "postgres" else "?"
        rows = connection.execute(
            f"SELECT * FROM {self.segment_table} WHERE source_id={placeholder} ORDER BY sequence_index",
            (source_id,),
        ).fetchall()
        return [self._segment_from_row(row) for row in rows]

    def _resolve_references(
        self,
        scope: AuthenticatedScope,
        source_input: SourceInput,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        redactions: Counter[str] = Counter()

        def clean(value: Any, field: str) -> str | None:
            cleaned, categories = sanitize_reference(value, field_name=field)
            redactions.update(categories)
            return cleaned

        references = {
            "application_reference": clean(source_input.application_reference, "application_reference"),
            "actor_reference": clean(source_input.actor_reference, "actor_reference"),
            "workspace_reference": clean(source_input.workspace_reference, "workspace_reference"),
            "session_reference": clean(source_input.session_reference, "session_reference"),
        }
        if not isinstance(source_input.entity_references, list):
            raise SourceLedgerError("SOURCE_SCOPE_INVALID", "entity_references must be a list.")
        entities = []
        for value in source_input.entity_references:
            cleaned = clean(value, "entity_reference")
            if cleaned and cleaned not in entities:
                entities.append(cleaned)
        if len(entities) > 100:
            raise SourceLedgerError("SOURCE_SCOPE_INVALID", "entity_references exceeds the configured limit.")

        assertions = {
            "application_reference": scope.application_reference,
            "actor_reference": scope.actor_reference,
            "workspace_reference": scope.workspace_reference,
            "session_reference": scope.session_reference,
        }
        for field, assertion in assertions.items():
            if assertion:
                asserted = clean(assertion, field)
                if not asserted or (references[field] and references[field] != asserted):
                    raise SourceLedgerError("SOURCE_SCOPE_INVALID", f"{field} conflicts with authenticated assertion.")
                references[field] = asserted
        if scope.entity_reference:
            asserted_entity = clean(scope.entity_reference, "entity_reference")
            if not asserted_entity or (entities and asserted_entity not in entities):
                raise SourceLedgerError("SOURCE_SCOPE_INVALID", "entity_reference conflicts with authenticated assertion.")
            if asserted_entity not in entities:
                entities.append(asserted_entity)
        references["entity_references"] = entities
        return references, dict(redactions)

    def _subject_access_allowed(self, scope: AuthenticatedScope, record: SourceRecord) -> bool:
        scalar_assertions = (
            (scope.application_reference, record.application_reference),
            (scope.actor_reference, record.actor_reference),
            (scope.workspace_reference, record.workspace_reference),
            (scope.session_reference, record.session_reference),
        )
        if any(asserted is not None and asserted != stored for asserted, stored in scalar_assertions):
            return False
        if scope.entity_reference is not None and scope.entity_reference not in record.entity_references:
            return False
        return True

    def _validate_scope(self, scope: AuthenticatedScope) -> AuthenticatedScope:
        if not isinstance(scope, AuthenticatedScope):
            raise SourceLedgerError("SOURCE_SCOPE_INVALID", "Authenticated scope is required.")
        for field in ("client_id", "vault_id", "namespace"):
            value = getattr(scope, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise SourceLedgerError("SOURCE_SCOPE_INVALID", "Authenticated memory scope is invalid.")
        return scope

    def _require_available(self, record: SourceRecord) -> None:
        if is_expired(record.expires_at, datetime.now(timezone.utc)):
            raise SourceLedgerError("SOURCE_EXPIRED", "Source retention period has expired.")

    def _idempotency_digest(self, key: Any) -> str | None:
        if key is None:
            return None
        if not isinstance(key, str) or not key.strip() or len(key) > 500:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "idempotency_key must be a non-empty string.")
        try:
            key.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "idempotency_key must be valid UTF-8.") from exc
        return sha256_text(key)

    def _merge_sanitisation_report(
        self,
        report: SanitisationReport,
        reference_redactions: dict[str, int],
    ) -> SanitisationReport:
        categories = Counter(report.redaction_categories)
        categories.update(reference_redactions)
        return SanitisationReport(
            redaction_count=sum(categories.values()),
            redaction_categories=dict(sorted(categories.items())),
            affected_segment_count=report.affected_segment_count,
            null_character_count=report.null_character_count,
            sanitisation_revision=report.sanitisation_revision,
        )

    def _record_from_row(self, row: Any) -> SourceRecord:
        report_data = self._json_value(row["sanitisation_report_json"])
        return SourceRecord(
            source_id=str(row["source_id"]),
            source_type=str(row["source_type"]),
            client_id=str(row["client_id"]),
            vault_id=str(row["vault_id"]),
            namespace=str(row["namespace"]),
            application_reference=row["application_reference"],
            actor_reference=row["actor_reference"],
            workspace_reference=row["workspace_reference"],
            entity_references=list(self._json_value(row["entity_references_json"])),
            session_reference=row["session_reference"],
            occurred_at=row["occurred_at"],
            ingested_at=str(row["ingested_at"]),
            sanitised_payload=self._json_value(row["sanitised_payload_json"]),
            payload_encoding=str(row["payload_encoding"]),
            content_hash_sha256=str(row["content_hash_sha256"]),
            canonical_payload_hash_sha256=str(row["canonical_payload_hash_sha256"]),
            segment_manifest_hash_sha256=str(row["segment_manifest_hash_sha256"]),
            idempotency_key_digest=row["idempotency_key_digest"],
            input_fingerprint_sha256=str(row["input_fingerprint_sha256"]),
            metadata=dict(self._json_value(row["metadata_json"])),
            retention_policy=str(row["retention_policy"]),
            expires_at=row["expires_at"],
            sanitisation_report=SanitisationReport(**report_data),
            source_schema_revision=str(row["source_schema_revision"]),
            canonicalisation_revision=str(row["canonicalisation_revision"]),
            segmenter_revision=str(row["segmenter_revision"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _segment_from_row(self, row: Any) -> SourceSegment:
        return SourceSegment(
            segment_id=str(row["segment_id"]),
            source_id=str(row["source_id"]),
            sequence_index=int(row["sequence_index"]),
            parent_segment_id=row["parent_segment_id"],
            segment_type=str(row["segment_type"]),
            content=str(row["content"]),
            content_hash_sha256=str(row["content_hash_sha256"]),
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            json_pointer=row["json_pointer"],
            speaker=row["speaker"],
            occurred_at=row["occurred_at"],
            label=row["label"],
            metadata=dict(self._json_value(row["metadata_json"])),
            segmenter_revision=str(row["segmenter_revision"]),
            created_at=str(row["created_at"]),
        )

    def _stored_representation(self, record: SourceRecord) -> str:
        return record.sanitised_payload if record.payload_encoding == "utf-8" else canonical_json(record.sanitised_payload)

    def _canonical_representation(self, record: SourceRecord) -> str:
        return record.sanitised_payload if record.payload_encoding == "utf-8" else canonical_json(record.sanitised_payload)

    def _expected_segment_id(self, segment: SourceSegment) -> str:
        identity = canonical_json(
            {
                "source_id": segment.source_id,
                "segmenter_revision": segment.segmenter_revision,
                "sequence_index": segment.sequence_index,
                "segment_type": segment.segment_type,
                "content_hash_sha256": segment.content_hash_sha256,
                "start_offset": segment.start_offset,
                "end_offset": segment.end_offset,
                "start_line": segment.start_line,
                "end_line": segment.end_line,
                "json_pointer": segment.json_pointer,
                "speaker": segment.speaker,
                "occurred_at": segment.occurred_at,
                "label": segment.label,
            }
        )
        return f"seg_{sha256_text(identity)[:24]}"

    def _page(self, cursor: str | None, limit: int, *, maximum: int = 200) -> tuple[int, int]:
        try:
            offset = int(cursor or 0)
            safe_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Pagination values are invalid.") from exc
        if offset < 0 or safe_limit < 1 or safe_limit > maximum:
            raise SourceLedgerError("SOURCE_PAYLOAD_INVALID", "Pagination values are outside allowed bounds.")
        return offset, safe_limit

    def _json(self, value: Any) -> str:
        return canonical_json(value)

    def _json_value(self, value: Any) -> Any:
        # psycopg returns JSONB values already decoded, including JSON string
        # scalars. SQLite stores the same values as serialized JSON text.
        if getattr(self.repository, "backend_name", "sqlite") == "postgres":
            return value
        return json.loads(value) if isinstance(value, str) else value


__all__ = [
    "POSTGRES_SCHEMA",
    "SEGMENT_TABLE",
    "SOURCE_TABLE",
    "SQLITE_SOURCE_SCHEMA",
    "SourceLedger",
    "initialize_postgres_source_schema",
    "initialize_sqlite_source_schema",
]
