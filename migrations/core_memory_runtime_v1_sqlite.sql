CREATE TABLE IF NOT EXISTS prmr_runtime_schema_migrations (
    migration_id TEXT PRIMARY KEY,
    sprint TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    resulting_schema_state TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_memory_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    application_reference TEXT,
    actor_reference TEXT,
    workspace_reference TEXT,
    entity_id TEXT,
    session_reference TEXT,
    target_object_type TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    safe_payload_json TEXT NOT NULL,
    payload_hash_sha256 TEXT NOT NULL,
    idempotency_key_digest TEXT NOT NULL,
    job_status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    scheduled_for TEXT NOT NULL,
    available_after TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    maximum_attempts INTEGER NOT NULL,
    lease_owner TEXT,
    lease_token_digest TEXT,
    lease_acquired_at TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    last_error_code TEXT,
    result_reference_type TEXT,
    result_reference_id TEXT,
    parent_job_id TEXT,
    correlation_id TEXT NOT NULL,
    runtime_schema_revision TEXT NOT NULL,
    job_schema_revision TEXT NOT NULL,
    job_queue_revision TEXT NOT NULL,
    job_lease_revision TEXT NOT NULL,
    job_retry_revision TEXT NOT NULL,
    job_handler_revision TEXT NOT NULL,
    job_recovery_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(
        client_id, vault_id, namespace, job_type, target_object_type,
        target_object_id, idempotency_key_digest
    ),
    FOREIGN KEY(parent_job_id) REFERENCES prmr_memory_jobs(job_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_job_attempts (
    job_attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    lease_token_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    heartbeat_at TEXT,
    completed_at TEXT,
    duration_ms REAL,
    handler_revision TEXT NOT NULL,
    transaction_mode TEXT NOT NULL,
    retryable INTEGER,
    error_code TEXT,
    safe_error_details TEXT,
    result_reference_type TEXT,
    result_reference_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, attempt_number),
    FOREIGN KEY(job_id) REFERENCES prmr_memory_jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_memory_job_events (
    job_event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    job_attempt_id TEXT,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    worker_id TEXT,
    safe_reason TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, sequence_number),
    FOREIGN KEY(job_id) REFERENCES prmr_memory_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(job_attempt_id) REFERENCES prmr_memory_job_attempts(job_attempt_id)
);

CREATE TABLE IF NOT EXISTS prmr_memory_job_dependencies (
    parent_job_id TEXT NOT NULL,
    child_job_id TEXT NOT NULL,
    dependency_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(parent_job_id, child_job_id),
    FOREIGN KEY(parent_job_id) REFERENCES prmr_memory_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(child_job_id) REFERENCES prmr_memory_jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_memory_job_effects (
    job_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    result_reference_type TEXT NOT NULL,
    result_reference_id TEXT NOT NULL,
    result_hash_sha256 TEXT NOT NULL,
    effect_status TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES prmr_memory_jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prmr_memory_job_schedules (
    schedule_id TEXT PRIMARY KEY,
    schedule_type TEXT NOT NULL,
    job_type TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    safe_payload_json TEXT NOT NULL,
    interval_seconds INTEGER,
    next_run_at TEXT NOT NULL,
    schedule_status TEXT NOT NULL,
    occurrence_number INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_job_lease_scan_idx
ON prmr_memory_jobs(job_status, available_after, scheduled_for, priority DESC, created_at, job_id);
CREATE INDEX IF NOT EXISTS prmr_job_scope_idx
ON prmr_memory_jobs(client_id, vault_id, namespace, job_status, created_at);
CREATE INDEX IF NOT EXISTS prmr_job_lease_expiry_idx
ON prmr_memory_jobs(job_status, lease_expires_at);
CREATE INDEX IF NOT EXISTS prmr_job_attempt_idx
ON prmr_memory_job_attempts(job_id, attempt_number);
CREATE INDEX IF NOT EXISTS prmr_job_event_idx
ON prmr_memory_job_events(job_id, sequence_number);
CREATE INDEX IF NOT EXISTS prmr_job_schedule_due_idx
ON prmr_memory_job_schedules(schedule_status, next_run_at);
