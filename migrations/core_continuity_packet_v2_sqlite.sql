CREATE TABLE IF NOT EXISTS prmr_continuity_packets_v2 (
    packet_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    packet_status TEXT NOT NULL,
    valid_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    entity_id TEXT,
    signal_identity_mode TEXT NOT NULL,
    packet_hash TEXT NOT NULL,
    effective_event_manifest_hash TEXT NOT NULL,
    artifact_status TEXT NOT NULL DEFAULT 'current',
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, packet_hash)
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_state_dimensions_v2 (
    packet_id TEXT NOT NULL,
    state_dimension_key TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    state_dimension_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(packet_id, state_dimension_key),
    FOREIGN KEY(packet_id) REFERENCES prmr_continuity_packets_v2(packet_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_items_v2 (
    packet_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    layer_name TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    temporal_phase TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(packet_id, event_id, layer_name),
    FOREIGN KEY(packet_id) REFERENCES prmr_continuity_packets_v2(packet_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_conflicts_v2 (
    packet_id TEXT NOT NULL,
    conflict_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    conflict_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(packet_id, conflict_id),
    FOREIGN KEY(packet_id) REFERENCES prmr_continuity_packets_v2(packet_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_entities_v2 (
    packet_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    entity_view_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(packet_id, entity_id),
    FOREIGN KEY(packet_id) REFERENCES prmr_continuity_packets_v2(packet_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_relationships_v2 (
    packet_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    layer_name TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    relationship_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(packet_id, relationship_id, layer_name),
    FOREIGN KEY(packet_id) REFERENCES prmr_continuity_packets_v2(packet_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_continuity_packet_comparisons_v2 (
    comparison_hash TEXT PRIMARY KEY,
    first_packet_id TEXT NOT NULL,
    second_packet_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, first_packet_id, second_packet_id)
);

CREATE INDEX IF NOT EXISTS prmr_pktv2_scope_idx ON prmr_continuity_packets_v2(client_id,vault_id,namespace,created_at);
CREATE INDEX IF NOT EXISTS prmr_pktv2_status_idx ON prmr_continuity_packets_v2(packet_status,artifact_status);
CREATE INDEX IF NOT EXISTS prmr_pktv2_boundary_idx ON prmr_continuity_packets_v2(valid_at,known_at);
CREATE INDEX IF NOT EXISTS prmr_pktv2_entity_idx ON prmr_continuity_packets_v2(entity_id);
CREATE INDEX IF NOT EXISTS prmr_pktv2_signal_mode_idx ON prmr_continuity_packets_v2(signal_identity_mode);
CREATE INDEX IF NOT EXISTS prmr_pktv2_hash_idx ON prmr_continuity_packets_v2(packet_hash);
CREATE INDEX IF NOT EXISTS prmr_pktv2_event_manifest_idx ON prmr_continuity_packets_v2(effective_event_manifest_hash);
CREATE INDEX IF NOT EXISTS prmr_pktv2_items_scope_idx ON prmr_continuity_packet_items_v2(client_id,vault_id,namespace,event_id);
CREATE INDEX IF NOT EXISTS prmr_pktv2_entities_scope_idx ON prmr_continuity_packet_entities_v2(client_id,vault_id,namespace,entity_id);
CREATE INDEX IF NOT EXISTS prmr_pktv2_rel_scope_idx ON prmr_continuity_packet_relationships_v2(client_id,vault_id,namespace,relationship_id);
