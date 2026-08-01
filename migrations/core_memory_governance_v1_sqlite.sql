CREATE TABLE IF NOT EXISTS prmr_memory_governance_requests (
    governance_request_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, action_type TEXT NOT NULL, target_type TEXT NOT NULL,
    target_reference_digest TEXT NOT NULL, request_status TEXT NOT NULL,
    request_idempotency_digest TEXT NOT NULL, approved_plan_id TEXT,
    completed_execution_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id,vault_id,namespace,request_idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_dependency_graphs (
    dependency_graph_id TEXT PRIMARY KEY, governance_request_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    graph_manifest_hash TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL,
    UNIQUE(governance_request_id,graph_manifest_hash)
);
CREATE TABLE IF NOT EXISTS prmr_memory_governance_plans (
    governance_plan_id TEXT PRIMARY KEY, governance_request_id TEXT NOT NULL,
    dependency_graph_id TEXT NOT NULL, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, action_type TEXT NOT NULL, target_type TEXT NOT NULL,
    target_reference_digest TEXT NOT NULL, plan_status TEXT NOT NULL,
    plan_hash_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, approved_at TEXT,
    payload_json TEXT NOT NULL, UNIQUE(governance_request_id,plan_hash_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_memory_governance_plan_items (
    plan_item_id TEXT PRIMARY KEY, governance_plan_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    item_action TEXT NOT NULL, node_type TEXT NOT NULL, storage_table TEXT NOT NULL,
    storage_key TEXT NOT NULL, sequence_index INTEGER NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_governance_executions (
    governance_execution_id TEXT PRIMARY KEY, governance_request_id TEXT NOT NULL,
    governance_plan_id TEXT NOT NULL UNIQUE, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, action_type TEXT NOT NULL, target_type TEXT NOT NULL,
    execution_status TEXT NOT NULL, phase TEXT NOT NULL,
    execution_idempotency_digest TEXT NOT NULL, started_at TEXT NOT NULL,
    completed_at TEXT, updated_at TEXT NOT NULL, payload_json TEXT NOT NULL,
    UNIQUE(client_id,vault_id,namespace,execution_idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_governance_execution_items (
    execution_item_id TEXT PRIMARY KEY, governance_execution_id TEXT NOT NULL,
    plan_item_id TEXT NOT NULL, item_status TEXT NOT NULL, batch_sequence INTEGER NOT NULL,
    updated_at TEXT NOT NULL, payload_json TEXT NOT NULL,
    UNIQUE(governance_execution_id,plan_item_id)
);
CREATE TABLE IF NOT EXISTS prmr_memory_governance_verifications (
    governance_verification_id TEXT PRIMARY KEY, governance_execution_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    verification_status TEXT NOT NULL, verification_manifest_hash TEXT NOT NULL,
    created_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_erasure_tombstones (
    erasure_tombstone_id TEXT PRIMARY KEY, governance_execution_id TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    target_type TEXT NOT NULL, target_reference_digest TEXT NOT NULL,
    tombstone_status TEXT NOT NULL, completed_at TEXT NOT NULL,
    verification_hash TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_preservation_holds (
    preservation_hold_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, target_type TEXT NOT NULL, target_reference_digest TEXT NOT NULL,
    hold_status TEXT NOT NULL, hold_idempotency_digest TEXT NOT NULL,
    applied_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_json TEXT NOT NULL,
    UNIQUE(client_id,vault_id,namespace,hold_idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_retention_annotations (
    retention_annotation_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, target_type TEXT NOT NULL, target_reference_digest TEXT NOT NULL,
    retention_mode TEXT NOT NULL, retain_until TEXT, system_effective_at TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL,
    UNIQUE(client_id,vault_id,namespace,idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_export_requests (
    memory_export_request_id TEXT PRIMARY KEY, governance_request_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    target_type TEXT NOT NULL, target_reference_digest TEXT NOT NULL,
    export_status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_export_bundles (
    memory_export_bundle_id TEXT PRIMARY KEY, memory_export_request_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    target_type TEXT NOT NULL, target_reference_digest TEXT NOT NULL,
    bundle_manifest_hash_sha256 TEXT NOT NULL, expires_at TEXT, created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL, UNIQUE(memory_export_request_id,bundle_manifest_hash_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_memory_correction_requests (
    memory_correction_request_id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL, namespace TEXT NOT NULL, target_type TEXT NOT NULL,
    target_reference_digest TEXT NOT NULL, request_status TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT,
    payload_json TEXT NOT NULL, UNIQUE(client_id,vault_id,namespace,idempotency_digest)
);

CREATE INDEX IF NOT EXISTS prmr_gov_request_scope_idx ON prmr_memory_governance_requests(client_id,vault_id,namespace,created_at);
CREATE INDEX IF NOT EXISTS prmr_gov_request_target_idx ON prmr_memory_governance_requests(client_id,vault_id,namespace,target_type,target_reference_digest);
CREATE INDEX IF NOT EXISTS prmr_gov_request_status_idx ON prmr_memory_governance_requests(action_type,request_status,created_at);
CREATE INDEX IF NOT EXISTS prmr_gov_graph_request_idx ON prmr_memory_dependency_graphs(governance_request_id,created_at);
CREATE INDEX IF NOT EXISTS prmr_gov_plan_request_idx ON prmr_memory_governance_plans(governance_request_id,plan_status,created_at);
CREATE INDEX IF NOT EXISTS prmr_gov_plan_item_idx ON prmr_memory_governance_plan_items(governance_plan_id,sequence_index);
CREATE INDEX IF NOT EXISTS prmr_gov_exec_plan_idx ON prmr_memory_governance_executions(governance_plan_id,execution_status,updated_at);
CREATE INDEX IF NOT EXISTS prmr_gov_exec_item_idx ON prmr_memory_governance_execution_items(governance_execution_id,item_status,batch_sequence);
CREATE INDEX IF NOT EXISTS prmr_gov_hold_target_idx ON prmr_memory_preservation_holds(client_id,vault_id,namespace,target_type,target_reference_digest,hold_status);
CREATE INDEX IF NOT EXISTS prmr_gov_retention_idx ON prmr_memory_retention_annotations(client_id,vault_id,namespace,retention_mode,retain_until);
CREATE INDEX IF NOT EXISTS prmr_gov_export_target_idx ON prmr_memory_export_bundles(client_id,vault_id,namespace,target_type,target_reference_digest,created_at);
CREATE INDEX IF NOT EXISTS prmr_gov_correction_target_idx ON prmr_memory_correction_requests(client_id,vault_id,namespace,target_type,target_reference_digest,created_at);
