CREATE SCHEMA IF NOT EXISTS prmr_self_serve;

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_requests (
    interpretation_request_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    request_fingerprint_sha256 TEXT NOT NULL, provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL, request_status TEXT NOT NULL, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, payload_json JSONB NOT NULL,
    UNIQUE(client_id, vault_id, namespace, request_fingerprint_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_attempts (
    interpretation_attempt_id TEXT PRIMARY KEY, interpretation_request_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL, provider_id TEXT NOT NULL, model_id TEXT NOT NULL,
    attempt_status TEXT NOT NULL, response_record_id TEXT, created_at TEXT NOT NULL,
    payload_json JSONB NOT NULL, UNIQUE(interpretation_request_id, attempt_number)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_response_records (
    interpretation_response_record_id TEXT PRIMARY KEY,
    interpretation_attempt_id TEXT NOT NULL, provider_response_hash_sha256 TEXT NOT NULL,
    validated_output_hash_sha256 TEXT NOT NULL, validation_status TEXT NOT NULL,
    created_at TEXT NOT NULL, payload_json JSONB NOT NULL,
    UNIQUE(interpretation_attempt_id, validated_output_hash_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_unknown_results (
    unknown_result_id TEXT PRIMARY KEY, interpretation_response_record_id TEXT NOT NULL,
    source_id TEXT NOT NULL, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, unknown_type TEXT NOT NULL, created_at TEXT NOT NULL,
    payload_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_validation_failures (
    validation_failure_id TEXT PRIMARY KEY, interpretation_attempt_id TEXT NOT NULL,
    failure_code TEXT NOT NULL, proposal_index INTEGER NOT NULL, created_at TEXT NOT NULL,
    payload_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_interpretation_proposal_links (
    proposal_link_id TEXT PRIMARY KEY, interpretation_response_record_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    proposal_type TEXT NOT NULL, downstream_id TEXT NOT NULL, proposal_index INTEGER NOT NULL,
    proposal_fingerprint_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    UNIQUE(interpretation_response_record_id, proposal_fingerprint_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_signal_definitions (
    canonical_signal_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, canonical_signal_key TEXT NOT NULL, signal_status TEXT NOT NULL,
    valid_from TEXT NOT NULL, valid_until TEXT, system_known_from TEXT NOT NULL,
    system_known_until TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    UNIQUE(client_id, vault_id, namespace, canonical_signal_key, system_known_from)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_signal_proposals (
    canonical_signal_proposal_id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL, namespace TEXT NOT NULL, original_signal_key TEXT NOT NULL,
    proposed_canonical_signal_key TEXT NOT NULL, proposal_status TEXT NOT NULL,
    interpretation_response_record_id TEXT, evidence_manifest_hash TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_signal_decisions (
    canonical_signal_decision_id TEXT PRIMARY KEY, canonical_signal_proposal_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    decision_type TEXT NOT NULL, decision_idempotency_digest TEXT NOT NULL,
    system_effective_at TEXT NOT NULL, created_at TEXT NOT NULL, payload_json JSONB NOT NULL,
    UNIQUE(client_id, vault_id, namespace, decision_idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_signal_alias_assertions (
    signal_alias_assertion_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, original_signal_key TEXT NOT NULL,
    canonical_signal_id TEXT NOT NULL, assertion_status TEXT NOT NULL,
    valid_from TEXT NOT NULL, valid_until TEXT, system_known_from TEXT NOT NULL,
    system_known_until TEXT, alias_fingerprint_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL, payload_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_event_signal_projections (
    event_signal_projection_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    original_signal_key TEXT NOT NULL, canonical_signal_key TEXT NOT NULL,
    mapping_applied BOOLEAN NOT NULL, valid_at TEXT NOT NULL, known_at TEXT NOT NULL,
    projection_hash_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    UNIQUE(event_id, client_id, vault_id, namespace, valid_at, known_at, projection_hash_sha256)
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_artifact_invalidations (
    invalidation_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, mapping_decision_id TEXT NOT NULL,
    invalidation_type TEXT NOT NULL, created_at TEXT NOT NULL, payload_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_canonical_signal_artifacts (
    canonical_artifact_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL, artifact_type TEXT NOT NULL, valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL, mapping_manifest_hash TEXT NOT NULL, artifact_hash TEXT NOT NULL,
    artifact_status TEXT NOT NULL, created_at TEXT NOT NULL, payload_json JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS prmr_ireq_scope_idx ON
prmr_self_serve.prmr_interpretation_requests(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_csig_alias_scope_idx ON
prmr_self_serve.prmr_canonical_signal_alias_assertions(client_id, vault_id, namespace, original_signal_key, assertion_status);
CREATE INDEX IF NOT EXISTS prmr_esig_scope_idx ON
prmr_self_serve.prmr_event_signal_projections(client_id, vault_id, namespace, event_id);
