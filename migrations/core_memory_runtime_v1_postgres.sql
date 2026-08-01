CREATE SCHEMA IF NOT EXISTS prmr_self_serve;

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_runtime_schema_migrations (
    migration_id TEXT PRIMARY KEY,
    sprint TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    resulting_schema_state TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_jobs (
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
    safe_payload_json JSONB NOT NULL,
    payload_hash_sha256 TEXT NOT NULL CHECK(length(payload_hash_sha256) = 64),
    idempotency_key_digest TEXT NOT NULL CHECK(length(idempotency_key_digest) = 64),
    job_status TEXT NOT NULL CHECK(job_status IN (
        'queued','leased','running','retry_wait','completed','failed',
        'dead_letter','cancel_requested','cancelled','blocked'
    )),
    priority INTEGER NOT NULL DEFAULT 0,
    scheduled_for TIMESTAMPTZ NOT NULL,
    available_after TIMESTAMPTZ NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    maximum_attempts INTEGER NOT NULL CHECK(maximum_attempts > 0),
    lease_owner TEXT,
    lease_token_digest TEXT,
    lease_acquired_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    last_error_code TEXT,
    result_reference_type TEXT,
    result_reference_id TEXT,
    parent_job_id TEXT REFERENCES prmr_self_serve.prmr_memory_jobs(job_id),
    correlation_id TEXT NOT NULL,
    runtime_schema_revision TEXT NOT NULL,
    job_schema_revision TEXT NOT NULL,
    job_queue_revision TEXT NOT NULL,
    job_lease_revision TEXT NOT NULL,
    job_retry_revision TEXT NOT NULL,
    job_handler_revision TEXT NOT NULL,
    job_recovery_revision TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(
        client_id, vault_id, namespace, job_type, target_object_type,
        target_object_id, idempotency_key_digest
    )
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_job_attempts (
    job_attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_memory_jobs(job_id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    lease_token_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms DOUBLE PRECISION,
    handler_revision TEXT NOT NULL,
    transaction_mode TEXT NOT NULL,
    retryable BOOLEAN,
    error_code TEXT,
    safe_error_details TEXT,
    result_reference_type TEXT,
    result_reference_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE(job_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_job_events (
    job_event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_memory_jobs(job_id) ON DELETE CASCADE,
    job_attempt_id TEXT REFERENCES prmr_self_serve.prmr_memory_job_attempts(job_attempt_id),
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    worker_id TEXT,
    safe_reason TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE(job_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_job_dependencies (
    parent_job_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_memory_jobs(job_id) ON DELETE CASCADE,
    child_job_id TEXT NOT NULL REFERENCES prmr_self_serve.prmr_memory_jobs(job_id) ON DELETE CASCADE,
    dependency_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(parent_job_id, child_job_id)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_job_effects (
    job_id TEXT PRIMARY KEY REFERENCES prmr_self_serve.prmr_memory_jobs(job_id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    result_reference_type TEXT NOT NULL,
    result_reference_id TEXT NOT NULL,
    result_hash_sha256 TEXT NOT NULL CHECK(length(result_hash_sha256) = 64),
    effect_status TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.prmr_memory_job_schedules (
    schedule_id TEXT PRIMARY KEY,
    schedule_type TEXT NOT NULL,
    job_type TEXT NOT NULL,
    client_id TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    safe_payload_json JSONB NOT NULL,
    interval_seconds INTEGER,
    next_run_at TIMESTAMPTZ NOT NULL,
    schedule_status TEXT NOT NULL,
    occurrence_number INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS prmr_job_lease_scan_idx
ON prmr_self_serve.prmr_memory_jobs(
    job_status, available_after, scheduled_for, priority DESC, created_at, job_id
);
CREATE INDEX IF NOT EXISTS prmr_job_scope_idx
ON prmr_self_serve.prmr_memory_jobs(client_id, vault_id, namespace, job_status, created_at);
CREATE INDEX IF NOT EXISTS prmr_job_lease_expiry_idx
ON prmr_self_serve.prmr_memory_jobs(job_status, lease_expires_at);
CREATE INDEX IF NOT EXISTS prmr_job_attempt_idx
ON prmr_self_serve.prmr_memory_job_attempts(job_id, attempt_number);
CREATE INDEX IF NOT EXISTS prmr_job_event_idx
ON prmr_self_serve.prmr_memory_job_events(job_id, sequence_number);
CREATE INDEX IF NOT EXISTS prmr_job_schedule_due_idx
ON prmr_self_serve.prmr_memory_job_schedules(schedule_status, next_run_at);
