-- PRMR Memory Core product-readiness index/migration plan.
-- Non-destructive DDL for the current Postgres schema.
-- This does not claim large-scale readiness; benchmark before broad external use.

CREATE TABLE IF NOT EXISTS prmr_self_serve.applications (
  application_reference TEXT NOT NULL,
  client_id TEXT NOT NULL REFERENCES prmr_self_serve.clients(client_id),
  name TEXT NOT NULL,
  environment TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(application_reference, client_id)
);

CREATE TABLE IF NOT EXISTS prmr_self_serve.key_applications (
  key_id TEXT PRIMARY KEY REFERENCES prmr_self_serve.api_keys(key_id),
  application_reference TEXT NOT NULL,
  client_id TEXT NOT NULL,
  FOREIGN KEY(application_reference, client_id)
    REFERENCES prmr_self_serve.applications(application_reference, client_id)
);

CREATE INDEX IF NOT EXISTS applications_client_id_idx
  ON prmr_self_serve.applications(client_id);

CREATE INDEX IF NOT EXISTS applications_environment_idx
  ON prmr_self_serve.applications(environment);

CREATE INDEX IF NOT EXISTS key_applications_client_id_idx
  ON prmr_self_serve.key_applications(client_id);

CREATE INDEX IF NOT EXISTS reports_scope_lookup_idx
  ON prmr_self_serve.reports(client_id, vault_id, namespace, report_id);

CREATE INDEX IF NOT EXISTS api_request_logs_scope_status_idx
  ON prmr_self_serve.api_request_logs(client_id, vault_id, namespace, status);

CREATE INDEX IF NOT EXISTS api_request_logs_timestamp_idx
  ON prmr_self_serve.api_request_logs(timestamp);

-- Recommended next relational migration:
-- create prmr_self_serve.event_records with client_id, vault_id, namespace,
-- application_reference, actor_reference, workspace_reference, entity_reference,
-- session_reference, event_id, event_type, occurred_at, timestamp_index,
-- normalized_payload_json, and UNIQUE(client_id, vault_id, namespace, event_id).
