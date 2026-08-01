CREATE TABLE IF NOT EXISTS prmr_entity_relationship_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_entity_candidates (
    entity_candidate_id TEXT PRIMARY KEY,
    extraction_run_id TEXT,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    proposed_entity_type TEXT NOT NULL,
    proposed_label TEXT,
    candidate_status TEXT NOT NULL,
    entity_candidate_fingerprint_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    entity_candidate_revision TEXT NOT NULL,
    entity_extractor_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, entity_candidate_fingerprint_sha256, entity_candidate_revision)
);

CREATE TABLE IF NOT EXISTS prmr_entity_evidence (
    entity_evidence_id TEXT PRIMARY KEY,
    entity_candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    evidence_text_hash_sha256 TEXT NOT NULL,
    segment_content_hash_sha256 TEXT NOT NULL,
    source_content_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(entity_candidate_id) REFERENCES prmr_entity_candidates(entity_candidate_id)
);

CREATE TABLE IF NOT EXISTS prmr_entities (
    entity_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    canonical_entity_type TEXT NOT NULL,
    canonical_label TEXT,
    entity_status TEXT NOT NULL,
    originating_entity_candidate_id TEXT NOT NULL,
    originating_source_id TEXT NOT NULL,
    originating_admission_id TEXT NOT NULL,
    identity_fingerprint_sha256 TEXT NOT NULL,
    identity_basis TEXT NOT NULL,
    first_known_at TEXT NOT NULL,
    first_valid_at TEXT NOT NULL,
    retired_at TEXT,
    merged_into_entity_id TEXT,
    entity_schema_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, identity_fingerprint_sha256)
);

CREATE TABLE IF NOT EXISTS prmr_entity_identifiers (
    entity_identifier_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    identifier_namespace TEXT NOT NULL,
    identifier_value_digest TEXT NOT NULL,
    identifier_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    system_known_from TEXT NOT NULL,
    system_known_until TEXT,
    identifier_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES prmr_entities(entity_id)
);

CREATE TABLE IF NOT EXISTS prmr_entity_mentions (
    entity_mention_id TEXT PRIMARY KEY,
    entity_id TEXT,
    entity_candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    occurred_at TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(entity_candidate_id) REFERENCES prmr_entity_candidates(entity_candidate_id)
);

CREATE TABLE IF NOT EXISTS prmr_entity_alias_assertions (
    alias_assertion_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    alias_normalised TEXT NOT NULL,
    alias_hash_sha256 TEXT NOT NULL,
    source_id TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    system_effective_at TEXT NOT NULL,
    alias_status TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest),
    FOREIGN KEY(entity_id) REFERENCES prmr_entities(entity_id)
);

CREATE TABLE IF NOT EXISTS prmr_entity_resolution_decisions (
    entity_resolution_decision_id TEXT PRIMARY KEY,
    entity_candidate_id TEXT,
    entity_mention_id TEXT,
    selected_entity_id TEXT,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    resolution_type TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_entity_distinctness_assertions (
    distinctness_assertion_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_ids_json TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_reference TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_entity_merges (
    entity_merge_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_reference TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_event_entity_links (
    event_entity_link_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_role TEXT NOT NULL,
    source_id TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    system_known_from TEXT NOT NULL,
    system_known_until TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES prmr_entities(entity_id)
);

CREATE TABLE IF NOT EXISTS prmr_relationship_candidates (
    relationship_candidate_id TEXT PRIMARY KEY,
    extraction_run_id TEXT,
    source_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    subject_entity_id TEXT,
    object_entity_id TEXT,
    proposed_relationship_type TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    relationship_candidate_fingerprint_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    relationship_candidate_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, relationship_candidate_fingerprint_sha256, relationship_candidate_revision)
);

CREATE TABLE IF NOT EXISTS prmr_relationship_evidence (
    relationship_evidence_id TEXT PRIMARY KEY,
    relationship_candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    evidence_text_hash_sha256 TEXT NOT NULL,
    segment_content_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(relationship_candidate_id) REFERENCES prmr_relationship_candidates(relationship_candidate_id)
);

CREATE TABLE IF NOT EXISTS prmr_relationship_admission_decisions (
    relationship_admission_id TEXT PRIMARY KEY,
    relationship_candidate_id TEXT NOT NULL,
    relationship_id TEXT,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_reference TEXT NOT NULL,
    reason TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_relationships (
    relationship_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    subject_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    object_entity_id TEXT NOT NULL,
    relationship_status TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    originating_relationship_candidate_id TEXT NOT NULL,
    originating_source_id TEXT NOT NULL,
    originating_admission_id TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    system_known_from TEXT NOT NULL,
    system_known_until TEXT,
    relationship_fingerprint_sha256 TEXT NOT NULL,
    evidence_manifest_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_relationship_evolution_records (
    relationship_evolution_id TEXT PRIMARY KEY,
    evolution_type TEXT NOT NULL,
    source_relationship_id TEXT NOT NULL,
    replacement_relationship_id TEXT,
    conflict_id TEXT,
    resolution_relationship_id TEXT,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);

CREATE TABLE IF NOT EXISTS prmr_relationship_conflicts (
    conflict_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    relationship_ids_json TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    conflict_status TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    system_effective_at TEXT NOT NULL,
    resolution_relationship_id TEXT,
    resolved_at TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_entity_relationship_reconstructions (
    reconstruction_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    valid_at TEXT,
    known_at TEXT,
    reconstruction_hash_sha256 TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, reconstruction_hash_sha256)
);

CREATE INDEX IF NOT EXISTS prmr_entity_candidates_scope_idx
    ON prmr_entity_candidates(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_entity_candidates_type_idx
    ON prmr_entity_candidates(proposed_entity_type, candidate_status);
CREATE INDEX IF NOT EXISTS prmr_entity_evidence_candidate_idx
    ON prmr_entity_evidence(entity_candidate_id, sequence_index);
CREATE INDEX IF NOT EXISTS prmr_entities_scope_idx
    ON prmr_entities(client_id, vault_id, namespace, entity_status);
CREATE INDEX IF NOT EXISTS prmr_entities_label_idx
    ON prmr_entities(client_id, vault_id, namespace, canonical_label);
CREATE INDEX IF NOT EXISTS prmr_entities_type_idx
    ON prmr_entities(canonical_entity_type);
CREATE INDEX IF NOT EXISTS prmr_entity_identifiers_digest_idx
    ON prmr_entity_identifiers(client_id, vault_id, namespace, identifier_namespace, identifier_value_digest, identifier_status);
CREATE UNIQUE INDEX IF NOT EXISTS prmr_entity_identifiers_active_unique_idx
    ON prmr_entity_identifiers(client_id, vault_id, namespace, identifier_namespace, identifier_value_digest)
    WHERE identifier_status = 'active' AND valid_until IS NULL AND system_known_until IS NULL;
CREATE INDEX IF NOT EXISTS prmr_entity_mentions_source_idx
    ON prmr_entity_mentions(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_entity_alias_current_idx
    ON prmr_entity_alias_assertions(client_id, vault_id, namespace, alias_normalised, alias_status);
CREATE UNIQUE INDEX IF NOT EXISTS prmr_event_entity_links_active_unique_idx
    ON prmr_event_entity_links(client_id, vault_id, namespace, event_id, entity_id, entity_role)
    WHERE valid_until IS NULL AND system_known_until IS NULL;
CREATE INDEX IF NOT EXISTS prmr_event_entity_links_event_idx
    ON prmr_event_entity_links(client_id, vault_id, namespace, event_id);
CREATE INDEX IF NOT EXISTS prmr_event_entity_links_entity_idx
    ON prmr_event_entity_links(client_id, vault_id, namespace, entity_id);
CREATE INDEX IF NOT EXISTS prmr_relationship_candidates_scope_idx
    ON prmr_relationship_candidates(client_id, vault_id, namespace, source_id);
CREATE INDEX IF NOT EXISTS prmr_relationships_subject_idx
    ON prmr_relationships(client_id, vault_id, namespace, subject_entity_id, relationship_status);
CREATE INDEX IF NOT EXISTS prmr_relationships_object_idx
    ON prmr_relationships(client_id, vault_id, namespace, object_entity_id, relationship_status);
CREATE INDEX IF NOT EXISTS prmr_relationships_type_idx
    ON prmr_relationships(relationship_type, relationship_status);
CREATE INDEX IF NOT EXISTS prmr_relationships_valid_idx
    ON prmr_relationships(valid_from, valid_until);
CREATE INDEX IF NOT EXISTS prmr_relationships_known_idx
    ON prmr_relationships(system_known_from, system_known_until);
