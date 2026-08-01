CREATE TABLE IF NOT EXISTS prmr_memory_consolidation_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_consolidation_plans (
    consolidation_plan_id TEXT PRIMARY KEY,
    consolidation_run_identity_hash TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    plan_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_consolidation_runs (
    consolidation_run_id TEXT PRIMARY KEY,
    consolidation_plan_id TEXT NOT NULL,
    run_identity_hash TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_id TEXT,
    relationship_id TEXT,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    status TEXT NOT NULL,
    checkpoint_id TEXT,
    consolidation_manifest_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, run_identity_hash)
);

CREATE TABLE IF NOT EXISTS prmr_consolidated_memories (
    consolidated_memory_id TEXT PRIMARY KEY,
    consolidation_run_id TEXT NOT NULL,
    consolidation_type TEXT NOT NULL,
    consolidation_key TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_id TEXT,
    relationship_id TEXT,
    signal_key TEXT,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    status TEXT NOT NULL,
    contributor_manifest_hash_sha256 TEXT NOT NULL,
    consolidated_memory_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(consolidation_run_id, consolidation_key)
);

CREATE TABLE IF NOT EXISTS prmr_consolidated_memory_members (
    consolidated_memory_member_id TEXT PRIMARY KEY,
    consolidated_memory_id TEXT NOT NULL,
    consolidation_run_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    member_type TEXT NOT NULL,
    event_id TEXT,
    source_id TEXT,
    candidate_id TEXT,
    admission_id TEXT,
    evolution_id TEXT,
    conflict_id TEXT,
    entity_id TEXT,
    relationship_id TEXT,
    sequence_index INTEGER NOT NULL,
    member_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(consolidated_memory_id, member_hash_sha256)
);

CREATE TABLE IF NOT EXISTS prmr_memory_checkpoints (
    memory_checkpoint_id TEXT PRIMARY KEY,
    consolidation_run_id TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    checkpoint_identity_hash TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_id TEXT,
    relationship_id TEXT,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    checkpoint_status TEXT NOT NULL,
    authoritative_event_manifest_hash TEXT NOT NULL,
    checkpoint_hash_sha256 TEXT NOT NULL,
    previous_checkpoint_id TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, checkpoint_identity_hash)
);

CREATE TABLE IF NOT EXISTS prmr_memory_checkpoint_deltas (
    checkpoint_delta_id TEXT PRIMARY KEY,
    base_checkpoint_id TEXT NOT NULL,
    target_checkpoint_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    delta_manifest_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(base_checkpoint_id, target_checkpoint_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_consolidation_invalidations (
    invalidation_id TEXT PRIMARY KEY,
    consolidation_run_id TEXT NOT NULL,
    consolidated_memory_id TEXT,
    checkpoint_id TEXT,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    invalidation_type TEXT NOT NULL,
    triggering_object_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_consolidation_equivalence_proofs (
    equivalence_proof_id TEXT PRIMARY KEY,
    consolidation_run_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    proof_type TEXT NOT NULL,
    query_type TEXT,
    equivalent INTEGER NOT NULL,
    canonical_result_hash TEXT,
    accelerated_result_hash TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_mc_runs_scope_status_idx
    ON prmr_memory_consolidation_runs(client_id, vault_id, namespace, status, created_at);
CREATE INDEX IF NOT EXISTS prmr_mc_runs_temporal_idx
    ON prmr_memory_consolidation_runs(client_id, vault_id, namespace, valid_at, known_at);
CREATE INDEX IF NOT EXISTS prmr_mc_memories_scope_type_idx
    ON prmr_consolidated_memories(client_id, vault_id, namespace, consolidation_type, status);
CREATE INDEX IF NOT EXISTS prmr_mc_memories_signal_idx
    ON prmr_consolidated_memories(client_id, vault_id, namespace, signal_key);
CREATE INDEX IF NOT EXISTS prmr_mc_memories_entity_idx
    ON prmr_consolidated_memories(client_id, vault_id, namespace, entity_id);
CREATE INDEX IF NOT EXISTS prmr_mc_memories_relationship_idx
    ON prmr_consolidated_memories(client_id, vault_id, namespace, relationship_id);
CREATE INDEX IF NOT EXISTS prmr_mc_members_event_idx
    ON prmr_consolidated_memory_members(client_id, vault_id, namespace, event_id);
CREATE INDEX IF NOT EXISTS prmr_mc_members_origin_idx
    ON prmr_consolidated_memory_members(source_id, candidate_id, admission_id);
CREATE INDEX IF NOT EXISTS prmr_mc_checkpoints_scope_status_idx
    ON prmr_memory_checkpoints(client_id, vault_id, namespace, checkpoint_status, created_at);
CREATE INDEX IF NOT EXISTS prmr_mc_checkpoints_temporal_idx
    ON prmr_memory_checkpoints(client_id, vault_id, namespace, valid_at, known_at);
CREATE INDEX IF NOT EXISTS prmr_mc_checkpoints_hash_idx
    ON prmr_memory_checkpoints(checkpoint_hash_sha256);
