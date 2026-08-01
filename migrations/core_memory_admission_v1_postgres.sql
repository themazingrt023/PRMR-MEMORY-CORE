-- PRMR Memory Core: durable memory admission and event-ledger bridge (PostgreSQL).
CREATE SCHEMA IF NOT EXISTS prmr_self_serve;

-- Core-owned event/packet bridge relations. These are required when the
-- migration registry runs without the separate product-account bootstrap.
CREATE TABLE IF NOT EXISTS prmr_self_serve.events (
    scope_key TEXT PRIMARY KEY,
    payload_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.packets (
    packet_id TEXT PRIMARY KEY,
    payload_json JSONB NOT NULL
);

ALTER TABLE prmr_self_serve.prmr_candidate_memories
    ADD COLUMN IF NOT EXISTS corrected_from_candidate_id TEXT,
    ADD COLUMN IF NOT EXISTS replacement_candidate_id TEXT,
    ADD COLUMN IF NOT EXISTS current_admission_state TEXT NOT NULL DEFAULT 'pending_review',
    ADD COLUMN IF NOT EXISTS accepted_admission_id TEXT,
    ADD COLUMN IF NOT EXISTS accepted_event_id TEXT,
    ADD COLUMN IF NOT EXISTS candidate_correction_revision TEXT;

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_admission_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_admission_decisions (
    admission_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
    extraction_run_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_sources(source_id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json JSONB NOT NULL,
    session_reference TEXT,
    decision_type TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    decision_actor_type TEXT NOT NULL,
    decision_actor_reference TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    decision_metadata_json JSONB NOT NULL,
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
    duration_ms DOUBLE PRECISION NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_admitted_memory_links (
    admitted_memory_link_id TEXT PRIMARY KEY,
    admission_id TEXT NOT NULL UNIQUE REFERENCES prmr_self_serve.prmr_memory_admission_decisions(admission_id),
    candidate_id TEXT NOT NULL UNIQUE REFERENCES prmr_self_serve.prmr_candidate_memories(candidate_id),
    extraction_run_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_candidate_extraction_runs(extraction_run_id),
    source_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_sources(source_id),
    admitted_event_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json JSONB NOT NULL,
    session_reference TEXT,
    epistemic_status TEXT NOT NULL,
    proposed_event_type TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    admission_policy_revision TEXT NOT NULL,
    admission_bridge_revision TEXT NOT NULL,
    admitted_event_metadata_revision TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_admissions_candidate_idx ON prmr_self_serve.prmr_memory_admission_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_source_idx ON prmr_self_serve.prmr_memory_admission_decisions(source_id);
CREATE INDEX IF NOT EXISTS prmr_admissions_scope_idx ON prmr_self_serve.prmr_memory_admission_decisions(client_id, vault_id, namespace);
CREATE INDEX IF NOT EXISTS prmr_links_source_idx ON prmr_self_serve.prmr_admitted_memory_links(source_id);
CREATE INDEX IF NOT EXISTS prmr_links_scope_idx ON prmr_self_serve.prmr_admitted_memory_links(client_id, vault_id, namespace);
