CREATE TABLE IF NOT EXISTS prmr_memory_query_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_query_runs (
    query_run_id TEXT PRIMARY KEY,
    query_type TEXT NOT NULL,
    query_mode TEXT NOT NULL,
    query_policy_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_id TEXT,
    relationship_id TEXT,
    event_id TEXT,
    signal_key TEXT,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    query_fingerprint_sha256 TEXT NOT NULL,
    query_plan_hash_sha256 TEXT NOT NULL,
    resolved_event_manifest_hash TEXT NOT NULL,
    relevant_memory_manifest_hash TEXT NOT NULL,
    query_status TEXT NOT NULL,
    result_status TEXT,
    result_id TEXT,
    result_hash_sha256 TEXT,
    evidence_bundle_id TEXT,
    truncated INTEGER NOT NULL,
    memory_query_schema_revision TEXT NOT NULL,
    memory_query_policy_revision TEXT NOT NULL,
    memory_query_planner_revision TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, query_fingerprint_sha256)
);

CREATE TABLE IF NOT EXISTS prmr_memory_query_results (
    query_result_id TEXT PRIMARY KEY,
    query_run_id TEXT NOT NULL UNIQUE,
    query_type TEXT NOT NULL,
    result_status TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    result_manifest_hash_sha256 TEXT NOT NULL,
    result_hash_sha256 TEXT NOT NULL,
    memory_query_result_revision TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(query_run_id) REFERENCES prmr_memory_query_runs(query_run_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_evidence_bundles (
    evidence_bundle_id TEXT PRIMARY KEY,
    query_run_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    completeness_status TEXT NOT NULL,
    evidence_item_count INTEGER NOT NULL,
    truncated INTEGER NOT NULL,
    memory_evidence_bundle_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(query_run_id) REFERENCES prmr_memory_query_runs(query_run_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_query_evidence_items (
    evidence_item_id TEXT PRIMARY KEY,
    evidence_bundle_id TEXT NOT NULL,
    query_run_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT,
    event_id TEXT,
    entity_id TEXT,
    relationship_id TEXT,
    candidate_id TEXT,
    admission_id TEXT,
    evidence_type TEXT NOT NULL,
    integrity_status TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(evidence_bundle_id) REFERENCES prmr_memory_evidence_bundles(evidence_bundle_id),
    FOREIGN KEY(query_run_id) REFERENCES prmr_memory_query_runs(query_run_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_explanations (
    explanation_id TEXT PRIMARY KEY,
    query_run_id TEXT NOT NULL,
    query_result_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    explanation_type TEXT NOT NULL,
    explanation_status TEXT NOT NULL,
    explanation_hash_sha256 TEXT NOT NULL,
    memory_explanation_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(query_result_id, memory_explanation_revision),
    FOREIGN KEY(query_run_id) REFERENCES prmr_memory_query_runs(query_run_id),
    FOREIGN KEY(query_result_id) REFERENCES prmr_memory_query_results(query_result_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_query_result_comparisons (
    comparison_hash_sha256 TEXT PRIMARY KEY,
    first_result_id TEXT NOT NULL,
    second_result_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    comparison_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_scope_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_type_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, query_type, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_entity_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, entity_id, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_relationship_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, relationship_id, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_event_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, event_id, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_signal_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, signal_key, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_temporal_idx
    ON prmr_memory_query_runs(client_id, vault_id, namespace, valid_at, known_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_runs_status_idx
    ON prmr_memory_query_runs(query_status, result_status, created_at);
CREATE INDEX IF NOT EXISTS prmr_memory_query_results_hash_idx
    ON prmr_memory_query_results(client_id, vault_id, namespace, result_hash_sha256);
CREATE INDEX IF NOT EXISTS prmr_memory_evidence_items_source_idx
    ON prmr_memory_query_evidence_items(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_memory_evidence_items_event_idx
    ON prmr_memory_query_evidence_items(client_id, vault_id, namespace, event_id);
