-- PRMR Memory Core Source Ledger V1 migration for SQLite.
-- Non-destructive; source deletion cascades only to that source's segments.

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
