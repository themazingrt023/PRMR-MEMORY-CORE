-- PRMR Memory Core: durable memory admission and event-ledger bridge (SQLite).
-- Runtime initialization applies candidate ALTERs idempotently before this file.
CREATE TABLE IF NOT EXISTS events (
    scope_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packets (
    packet_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_admission_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_admission_decisions (
    admission_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    extraction_run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    decision_type TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    decision_actor_type TEXT NOT NULL,
    decision_actor_reference TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    decision_metadata_json TEXT NOT NULL,
    admission_policy_id TEXT NOT NULL,
    admission_policy_revision TEXT NOT NULL,
    admission_schema_revision TEXT NOT NULL,
    admission_bridge_revision TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    candidate_evidence_manifest_hash_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    source_segment_manifest_hash_sha256 TEXT NOT NULL,
    admitted_event_id TEXT,
    replacement_candidate_id TEXT,
    decision_idempotency_digest TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_admitted_memory_links (
    admitted_memory_link_id TEXT PRIMARY KEY,
    admission_id TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL UNIQUE,
    extraction_run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    admitted_event_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    epistemic_status TEXT NOT NULL,
    proposed_event_type TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    admission_policy_revision TEXT NOT NULL,
    admission_bridge_revision TEXT NOT NULL,
    admitted_event_metadata_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(admission_id) REFERENCES prmr_memory_admission_decisions(admission_id),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id),
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id),
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id)
);

CREATE INDEX IF NOT EXISTS prmr_admissions_candidate_idx ON prmr_memory_admission_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_source_idx ON prmr_memory_admission_decisions(source_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_scope_idx ON prmr_memory_admission_decisions(client_id, vault_id, namespace);
CREATE INDEX IF NOT EXISTS prmr_links_source_idx ON prmr_admitted_memory_links(source_id);
CREATE INDEX IF NOT EXISTS prmr_links_scope_idx ON prmr_admitted_memory_links(client_id, vault_id, namespace);
