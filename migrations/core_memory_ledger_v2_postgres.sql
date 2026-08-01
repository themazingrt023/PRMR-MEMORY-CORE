CREATE SCHEMA IF NOT EXISTS prmr_self_serve;

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_ledger_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_evolution_records (
    evolution_id TEXT PRIMARY KEY,
    evolution_type TEXT NOT NULL,
    evolution_status TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    replacement_event_id TEXT,
    conflict_id TEXT,
    resolution_event_id TEXT,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json JSONB NOT NULL,
    session_reference TEXT,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    system_effective_at TEXT NOT NULL,
    evolution_actor_type TEXT NOT NULL,
    evolution_actor_reference TEXT NOT NULL,
    evolution_reason TEXT NOT NULL,
    evolution_metadata_json JSONB NOT NULL,
    source_event_hash TEXT NOT NULL,
    replacement_event_hash TEXT,
    source_admission_id TEXT NOT NULL,
    replacement_admission_id TEXT,
    memory_ledger_schema_revision TEXT NOT NULL,
    memory_evolution_revision TEXT NOT NULL,
    bitemporal_policy_revision TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_ms DOUBLE PRECISION NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_conflicts (
    conflict_id TEXT PRIMARY KEY,
    conflict_status TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json JSONB NOT NULL,
    session_reference TEXT,
    conflicting_event_ids_json JSONB NOT NULL,
    event_set_fingerprint TEXT NOT NULL,
    conflict_key TEXT,
    conflict_type TEXT NOT NULL,
    declared_by TEXT NOT NULL,
    declaration_reason TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    resolution_event_id TEXT,
    resolved_at TEXT,
    resolution_reason TEXT,
    memory_conflict_revision TEXT NOT NULL,
    memory_ledger_schema_revision TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, event_set_fingerprint, memory_conflict_revision),
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_reconstructions (
    reconstruction_id TEXT PRIMARY KEY,
    reconstruction_identity TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    valid_at TEXT,
    known_at TEXT,
    reconstruction_hash TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_evolution_source_idx ON prmr_self_serve.prmr_memory_evolution_records(source_event_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_replacement_idx ON prmr_self_serve.prmr_memory_evolution_records(replacement_event_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_conflict_idx ON prmr_self_serve.prmr_memory_evolution_records(conflict_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_scope_idx ON prmr_self_serve.prmr_memory_evolution_records(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_evolution_type_idx ON prmr_self_serve.prmr_memory_evolution_records(evolution_type);
CREATE INDEX IF NOT EXISTS prmr_evolution_system_idx ON prmr_self_serve.prmr_memory_evolution_records(system_effective_at);
CREATE UNIQUE INDEX IF NOT EXISTS prmr_evolution_terminal_unique_idx
ON prmr_self_serve.prmr_memory_evolution_records(client_id,vault_id,namespace,source_event_id)
WHERE evolution_type IN ('correct','supersede','retract','invalidate')
AND evolution_status='completed';
CREATE UNIQUE INDEX IF NOT EXISTS prmr_evolution_conflict_resolution_unique_idx
ON prmr_self_serve.prmr_memory_evolution_records(client_id,vault_id,namespace,conflict_id)
WHERE evolution_type='resolve_contradiction' AND evolution_status='completed';
CREATE INDEX IF NOT EXISTS prmr_conflict_scope_idx ON prmr_self_serve.prmr_memory_conflicts(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_conflict_status_idx ON prmr_self_serve.prmr_memory_conflicts(conflict_status);
CREATE INDEX IF NOT EXISTS prmr_conflict_system_idx ON prmr_self_serve.prmr_memory_conflicts(system_effective_at);
CREATE INDEX IF NOT EXISTS prmr_conflict_resolution_idx ON prmr_self_serve.prmr_memory_conflicts(resolution_event_id);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_scope_idx ON prmr_self_serve.prmr_memory_reconstructions(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_valid_idx ON prmr_self_serve.prmr_memory_reconstructions(valid_at);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_known_idx ON prmr_self_serve.prmr_memory_reconstructions(known_at);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_hash_idx ON prmr_self_serve.prmr_memory_reconstructions(reconstruction_hash);

INSERT INTO prmr_self_serve.prmr_memory_ledger_schema_migrations(revision, applied_at)
VALUES ('memory_ledger_v2', CURRENT_TIMESTAMP::TEXT)
ON CONFLICT(revision) DO NOTHING;
