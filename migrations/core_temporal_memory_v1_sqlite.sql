CREATE TABLE IF NOT EXISTS prmr_memory_temporal_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_importance_annotations (
    importance_annotation_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_references_json TEXT NOT NULL,
    session_reference TEXT,
    importance_level TEXT,
    importance_weight REAL NOT NULL CHECK(importance_weight >= 0.50 AND importance_weight <= 2.00),
    annotation_actor_type TEXT NOT NULL,
    annotation_actor_reference TEXT NOT NULL,
    annotation_reason TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    memory_importance_revision TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_memory_dynamics_snapshots (
    dynamics_snapshot_id TEXT PRIMARY KEY,
    dynamics_snapshot_identity TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_reference TEXT,
    session_reference TEXT,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    dynamics_mode TEXT NOT NULL,
    temporal_policy_id TEXT NOT NULL,
    resolved_event_manifest_hash TEXT NOT NULL,
    importance_annotation_manifest_hash TEXT NOT NULL,
    signal_dynamics_manifest_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_signal_dynamics (
    signal_dynamics_id TEXT PRIMARY KEY,
    dynamics_snapshot_id TEXT NOT NULL,
    signal_key TEXT NOT NULL,
    memory_phase TEXT NOT NULL CHECK(memory_phase IN ('active','latent','dormant','decayed')),
    reinforced INTEGER NOT NULL CHECK(reinforced IN (0,1)),
    re_emerging INTEGER NOT NULL CHECK(re_emerging IN (0,1)),
    final_influence REAL NOT NULL CHECK(final_influence >= 0.0 AND final_influence <= 1.0),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(dynamics_snapshot_id, signal_key),
    FOREIGN KEY(dynamics_snapshot_id)
        REFERENCES prmr_memory_dynamics_snapshots(dynamics_snapshot_id)
);

CREATE INDEX IF NOT EXISTS prmr_importance_event_idx
    ON prmr_memory_importance_annotations(event_id);
CREATE INDEX IF NOT EXISTS prmr_importance_scope_idx
    ON prmr_memory_importance_annotations(client_id, vault_id, namespace);
CREATE INDEX IF NOT EXISTS prmr_importance_system_idx
    ON prmr_memory_importance_annotations(system_effective_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_scope_idx
    ON prmr_memory_dynamics_snapshots(client_id, vault_id, namespace);
CREATE INDEX IF NOT EXISTS prmr_dynamics_valid_idx
    ON prmr_memory_dynamics_snapshots(valid_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_known_idx
    ON prmr_memory_dynamics_snapshots(known_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_policy_idx
    ON prmr_memory_dynamics_snapshots(temporal_policy_id);
CREATE INDEX IF NOT EXISTS prmr_dynamics_event_manifest_idx
    ON prmr_memory_dynamics_snapshots(resolved_event_manifest_hash);
CREATE INDEX IF NOT EXISTS prmr_signal_snapshot_idx
    ON prmr_memory_signal_dynamics(dynamics_snapshot_id);
CREATE INDEX IF NOT EXISTS prmr_signal_key_idx
    ON prmr_memory_signal_dynamics(signal_key);
CREATE INDEX IF NOT EXISTS prmr_signal_phase_idx
    ON prmr_memory_signal_dynamics(memory_phase);
CREATE INDEX IF NOT EXISTS prmr_signal_reinforced_idx
    ON prmr_memory_signal_dynamics(reinforced);
CREATE INDEX IF NOT EXISTS prmr_signal_reemerging_idx
    ON prmr_memory_signal_dynamics(re_emerging);

INSERT OR IGNORE INTO prmr_memory_temporal_schema_migrations(revision, applied_at)
VALUES('memory_temporal_v1', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
