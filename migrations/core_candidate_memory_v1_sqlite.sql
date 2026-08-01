PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prmr_candidate_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_candidate_extraction_runs (
    extraction_run_id TEXT PRIMARY KEY,
    extraction_identity_sha256 TEXT NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    source_content_hash_sha256 TEXT NOT NULL,
    source_canonical_hash_sha256 TEXT NOT NULL,
    source_segment_manifest_hash_sha256 TEXT NOT NULL,
    candidate_extractor_revision TEXT NOT NULL,
    candidate_rule_revision TEXT NOT NULL,
    candidate_claim_splitter_revision TEXT NOT NULL,
    epistemic_policy_revision TEXT NOT NULL,
    extraction_policy_json TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    explicit_count INTEGER NOT NULL,
    derived_count INTEGER NOT NULL,
    inferred_count INTEGER NOT NULL,
    unknown_count INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    candidate_manifest_hash_sha256 TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_candidate_memories (
    candidate_id TEXT PRIMARY KEY,
    candidate_order INTEGER NOT NULL,
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
    proposed_event_type TEXT,
    proposed_signal TEXT NOT NULL,
    proposed_occurred_at TEXT,
    epistemic_status TEXT NOT NULL,
    extraction_confidence REAL NOT NULL CHECK(extraction_confidence >= 0 AND extraction_confidence <= 1),
    confidence_basis TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    primary_rule_id TEXT NOT NULL,
    matched_rule_ids_json TEXT NOT NULL,
    duplicate_match_count INTEGER NOT NULL,
    candidate_status TEXT NOT NULL,
    candidate_fingerprint_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    normalisation_details_json TEXT NOT NULL,
    candidate_schema_revision TEXT NOT NULL,
    candidate_extractor_revision TEXT NOT NULL,
    candidate_rule_revision TEXT NOT NULL,
    epistemic_policy_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(extraction_run_id, candidate_fingerprint_sha256),
    UNIQUE(extraction_run_id, candidate_order),
    FOREIGN KEY(extraction_run_id) REFERENCES prmr_candidate_extraction_runs(extraction_run_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_candidate_evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    source_start_offset INTEGER,
    source_end_offset INTEGER,
    segment_start_offset INTEGER,
    segment_end_offset INTEGER,
    start_line INTEGER,
    end_line INTEGER,
    json_pointer TEXT,
    evidence_text_hash_sha256 TEXT NOT NULL,
    segment_content_hash_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    extraction_rule_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(candidate_id, sequence_index),
    FOREIGN KEY(candidate_id) REFERENCES prmr_candidate_memories(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES prmr_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY(segment_id) REFERENCES prmr_source_segments(segment_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS prmr_candidate_runs_source_idx ON prmr_candidate_extraction_runs(source_id);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_scope_idx ON prmr_candidate_extraction_runs(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_status_idx ON prmr_candidate_extraction_runs(status);
CREATE INDEX IF NOT EXISTS prmr_candidate_runs_created_idx ON prmr_candidate_extraction_runs(created_at);
CREATE INDEX IF NOT EXISTS prmr_candidates_scope_idx ON prmr_candidate_memories(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_candidates_fingerprint_idx ON prmr_candidate_memories(candidate_fingerprint_sha256);
CREATE INDEX IF NOT EXISTS prmr_candidates_event_type_idx ON prmr_candidate_memories(proposed_event_type);
CREATE INDEX IF NOT EXISTS prmr_candidates_epistemic_idx ON prmr_candidate_memories(epistemic_status);
CREATE INDEX IF NOT EXISTS prmr_candidates_status_idx ON prmr_candidate_memories(candidate_status);
CREATE INDEX IF NOT EXISTS prmr_candidates_created_idx ON prmr_candidate_memories(created_at);
CREATE INDEX IF NOT EXISTS prmr_evidence_candidate_idx ON prmr_candidate_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS prmr_evidence_source_idx ON prmr_candidate_evidence(source_id);
CREATE INDEX IF NOT EXISTS prmr_evidence_segment_idx ON prmr_candidate_evidence(segment_id);
