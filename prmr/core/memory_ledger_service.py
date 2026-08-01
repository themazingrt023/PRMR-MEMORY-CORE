"""Append-only bitemporal evolution operations over admitted PRMR events."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any

from .admission_models import AdmissionDecisionActor
from .admission_service import MemoryAdmissionService
from .memory_ledger_models import (
    BITEMPORAL_POLICY_REVISION,
    MEMORY_CONFLICT_REVISION,
    MEMORY_EVOLUTION_REVISION,
    MEMORY_LEDGER_SCHEMA_REVISION,
    MemoryConflict,
    MemoryConflictStatus,
    MemoryEvolutionRecord,
    MemoryEvolutionStatus,
    MemoryEvolutionType,
    MemoryLedgerError,
)
from .source_integrity import canonical_json, sha256_text
from .source_ledger import POSTGRES_SCHEMA, utc_now
from .source_models import AuthenticatedScope, MaintenanceContext


LOGGER = logging.getLogger("prmr.core.memory_ledger")
EVOLUTION_TABLE = "prmr_memory_evolution_records"
CONFLICT_TABLE = "prmr_memory_conflicts"
RECONSTRUCTION_TABLE = "prmr_memory_reconstructions"
CONFLICT_TYPES = {
    "state_conflict", "status_conflict", "value_conflict", "identity_conflict",
    "temporal_conflict", "general_contradiction",
}


SQLITE_MEMORY_LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS prmr_memory_ledger_schema_migrations (
    revision TEXT PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_evolution_records (
    evolution_id TEXT PRIMARY KEY,
    evolution_type TEXT NOT NULL,
    evolution_status TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    replacement_event_id TEXT,
    conflict_id TEXT,
    resolution_event_id TEXT,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
    entity_references_json TEXT NOT NULL, session_reference TEXT,
    valid_from TEXT NOT NULL, valid_until TEXT, system_effective_at TEXT NOT NULL,
    evolution_actor_type TEXT NOT NULL, evolution_actor_reference TEXT NOT NULL,
    evolution_reason TEXT NOT NULL, evolution_metadata_json TEXT NOT NULL,
    source_event_hash TEXT NOT NULL, replacement_event_hash TEXT,
    source_admission_id TEXT NOT NULL, replacement_admission_id TEXT,
    memory_ledger_schema_revision TEXT NOT NULL,
    memory_evolution_revision TEXT NOT NULL,
    bitemporal_policy_revision TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL,
    completed_at TEXT NOT NULL, duration_ms REAL NOT NULL, error_code TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_conflicts (
    conflict_id TEXT PRIMARY KEY,
    conflict_status TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
    entity_references_json TEXT NOT NULL, session_reference TEXT,
    conflicting_event_ids_json TEXT NOT NULL, event_set_fingerprint TEXT NOT NULL,
    conflict_key TEXT, conflict_type TEXT NOT NULL, declared_by TEXT NOT NULL,
    declaration_reason TEXT NOT NULL, valid_from TEXT NOT NULL,
    system_effective_at TEXT NOT NULL, resolution_event_id TEXT,
    resolved_at TEXT, resolution_reason TEXT,
    memory_conflict_revision TEXT NOT NULL, memory_ledger_schema_revision TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(client_id, vault_id, namespace, event_set_fingerprint, memory_conflict_revision),
    UNIQUE(client_id, vault_id, namespace, idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_reconstructions (
    reconstruction_id TEXT PRIMARY KEY,
    reconstruction_identity TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    valid_at TEXT, known_at TEXT, reconstruction_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS prmr_evolution_source_idx ON prmr_memory_evolution_records(source_event_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_replacement_idx ON prmr_memory_evolution_records(replacement_event_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_conflict_idx ON prmr_memory_evolution_records(conflict_id);
CREATE INDEX IF NOT EXISTS prmr_evolution_scope_idx ON prmr_memory_evolution_records(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_evolution_type_idx ON prmr_memory_evolution_records(evolution_type);
CREATE INDEX IF NOT EXISTS prmr_evolution_system_idx ON prmr_memory_evolution_records(system_effective_at);
CREATE UNIQUE INDEX IF NOT EXISTS prmr_evolution_terminal_unique_idx
ON prmr_memory_evolution_records(client_id,vault_id,namespace,source_event_id)
WHERE evolution_type IN ('correct','supersede','retract','invalidate')
AND evolution_status='completed';
CREATE UNIQUE INDEX IF NOT EXISTS prmr_evolution_conflict_resolution_unique_idx
ON prmr_memory_evolution_records(client_id,vault_id,namespace,conflict_id)
WHERE evolution_type='resolve_contradiction' AND evolution_status='completed';
CREATE INDEX IF NOT EXISTS prmr_conflict_scope_idx ON prmr_memory_conflicts(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_conflict_status_idx ON prmr_memory_conflicts(conflict_status);
CREATE INDEX IF NOT EXISTS prmr_conflict_system_idx ON prmr_memory_conflicts(system_effective_at);
CREATE INDEX IF NOT EXISTS prmr_conflict_resolution_idx ON prmr_memory_conflicts(resolution_event_id);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_scope_idx ON prmr_memory_reconstructions(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_valid_idx ON prmr_memory_reconstructions(valid_at);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_known_idx ON prmr_memory_reconstructions(known_at);
CREATE INDEX IF NOT EXISTS prmr_reconstruction_hash_idx ON prmr_memory_reconstructions(reconstruction_hash);
"""


def initialize_sqlite_memory_ledger_schema(connection: Any) -> None:
    connection.executescript(SQLITE_MEMORY_LEDGER_SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO prmr_memory_ledger_schema_migrations(revision,applied_at) VALUES(?,?)",
        (MEMORY_LEDGER_SCHEMA_REVISION, utc_now()),
    )


def initialize_postgres_memory_ledger_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
    sql = SQLITE_MEMORY_LEDGER_SCHEMA.replace(
        "CREATE TABLE IF NOT EXISTS ", f"CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}."
    ).replace(
        "CREATE INDEX IF NOT EXISTS prmr_", "CREATE INDEX IF NOT EXISTS prmr_"
    )
    # Index ON targets need schema qualification; use the shipped migration in
    # deployed Postgres environments and keep runtime table creation explicit.
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    for statement in statements:
        if statement.startswith("CREATE INDEX"):
            statement = re.sub(
                r" ON (prmr_[a-z_]+)", rf" ON {POSTGRES_SCHEMA}.\1", statement
            )
        if "payload_json TEXT" in statement:
            statement = statement.replace("payload_json TEXT", "payload_json JSONB")
        if "entity_references_json TEXT" in statement:
            statement = statement.replace("entity_references_json TEXT", "entity_references_json JSONB")
        if "evolution_metadata_json TEXT" in statement:
            statement = statement.replace("evolution_metadata_json TEXT", "evolution_metadata_json JSONB")
        if "conflicting_event_ids_json TEXT" in statement:
            statement = statement.replace("conflicting_event_ids_json TEXT", "conflicting_event_ids_json JSONB")
        cursor.execute(statement)
    cursor.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_memory_ledger_schema_migrations(revision,applied_at) "
        "VALUES(%s,%s) ON CONFLICT(revision) DO NOTHING",
        (MEMORY_LEDGER_SCHEMA_REVISION, utc_now()),
    )


def _log(event: str, **fields: Any) -> None:
    allowed = {
        "evolution_id", "conflict_id", "reconstruction_id", "source_event_id",
        "replacement_event_id", "event_count", "excluded_count", "duration_ms",
        "error_code", "memory_evolution_revision", "memory_conflict_revision",
    }
    LOGGER.info("%s", json.dumps({"event": event, **{k: v for k, v in fields.items() if k in allowed}}, sort_keys=True))


class MemoryLedgerService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.backend = str(getattr(repository, "backend_name", "sqlite"))
        self.admission = MemoryAdmissionService(repository, initialize=initialize)
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        self.evolution_table = prefix + EVOLUTION_TABLE
        self.conflict_table = prefix + CONFLICT_TABLE
        self.reconstruction_table = prefix + RECONSTRUCTION_TABLE
        if initialize:
            with repository.connect() as connection:
                (initialize_postgres_memory_ledger_schema if self.backend == "postgres" else initialize_sqlite_memory_ledger_schema)(connection)

    def correct_admitted_memory(self, scope: AuthenticatedScope, original_event_id: str, replacement_event_id: str, decision_actor: AdmissionDecisionActor, reason: str, valid_from: str | None = None, system_effective_at: str | None = None, idempotency_key: str | None = None) -> MemoryEvolutionRecord:
        _log("memory_correction_started", source_event_id=original_event_id, replacement_event_id=replacement_event_id)
        record = self._replace(scope, "correct", original_event_id, replacement_event_id, decision_actor, reason, valid_from, system_effective_at, idempotency_key)
        _log("memory_correction_completed", evolution_id=record.evolution_id)
        return record

    def supersede_admitted_memory(self, scope: AuthenticatedScope, original_event_id: str, successor_event_id: str, decision_actor: AdmissionDecisionActor, reason: str, valid_from: str | None = None, system_effective_at: str | None = None, idempotency_key: str | None = None) -> MemoryEvolutionRecord:
        record = self._replace(scope, "supersede", original_event_id, successor_event_id, decision_actor, reason, valid_from, system_effective_at, idempotency_key)
        _log("memory_supersession_completed", evolution_id=record.evolution_id)
        return record

    def retract_admitted_memory(self, scope: AuthenticatedScope, event_id: str, decision_actor: AdmissionDecisionActor, reason: str, system_effective_at: str | None = None, idempotency_key: str | None = None) -> MemoryEvolutionRecord:
        decision_actor.validate()
        event, link, admission = self._admitted(scope, event_id)
        if self._terminal_evolution(scope, event_id):
            existing = self._latest_for_source(scope, event_id, "retract")
            if existing:
                return existing
            raise MemoryLedgerError("MEMORY_RETRACTION_INVALID", "Event is already inactive.")
        system_at = self._time(system_effective_at or utc_now())
        self._require_system_after_admission(system_at, admission)
        digest = self._digest(idempotency_key or f"retract:{event_id}", "retract")
        replay = self._evolution_by_digest(scope, digest)
        if replay:
            return replay
        record = self._record(scope, "retract", event, link, admission, decision_actor, reason, event["timestamp"], system_at, digest)
        self._insert_record(record)
        _log("memory_retraction_completed", evolution_id=record.evolution_id)
        return record

    def declare_memory_contradiction(self, scope: AuthenticatedScope, event_ids: list[str], conflict_type: str, decision_actor: AdmissionDecisionActor, reason: str, valid_from: str | None = None, system_effective_at: str | None = None, idempotency_key: str | None = None) -> MemoryConflict:
        decision_actor.validate()
        ordered = sorted(set(event_ids))
        if len(ordered) != len(event_ids) or len(ordered) < 2 or conflict_type not in CONFLICT_TYPES:
            raise MemoryLedgerError("MEMORY_CONFLICT_INVALID", "Conflict requires two or more unique admitted events and a supported type.")
        admitted = [self._admitted(scope, event_id) for event_id in ordered]
        fingerprint = sha256_text(canonical_json({"events": ordered, "revision": MEMORY_CONFLICT_REVISION}))
        digest = self._digest(idempotency_key or f"conflict:{fingerprint}", "declare_contradiction")
        existing = self._conflict_by_fingerprint(scope, fingerprint)
        if existing:
            return existing
        system_at = self._time(system_effective_at or utc_now())
        for _, _, admission in admitted:
            self._require_system_after_admission(system_at, admission)
        valid = self._time(valid_from or min(item[0]["timestamp"] for item in admitted))
        now = utc_now()
        conflict_id = f"cnfl_{fingerprint[:24]}"
        conflict = MemoryConflict(
            conflict_id, "open", *scope.memory_boundary(), scope.application_reference,
            scope.actor_reference, scope.workspace_reference,
            [scope.entity_reference] if scope.entity_reference else [],
            scope.session_reference, ordered, None, conflict_type,
            decision_actor.actor_reference, self._reason(reason), valid, system_at,
            None, None, None, MEMORY_CONFLICT_REVISION, MEMORY_LEDGER_SCHEMA_REVISION,
            digest, now, now,
        )
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                self._insert_conflict(connection, conflict)
                for event, link, admission in admitted:
                    event_digest = sha256_text(f"{digest}:{event['event_id']}")
                    record = self._record(scope, "declare_contradiction", event, link, admission, decision_actor, reason, valid, system_at, event_digest, conflict_id=conflict_id)
                    self._insert_evolution(connection, record)
        except Exception as exc:
            replay = self._conflict_by_fingerprint(scope, fingerprint)
            if replay:
                return replay
            raise MemoryLedgerError("MEMORY_CONFLICT_INVALID", "Conflict transaction failed.", retryable=True) from exc
        _log("memory_conflict_declared", conflict_id=conflict_id, event_count=len(ordered))
        return conflict

    def resolve_memory_contradiction(self, scope: AuthenticatedScope, conflict_id: str, resolution_event_id: str, decision_actor: AdmissionDecisionActor, reason: str, system_effective_at: str | None = None, idempotency_key: str | None = None) -> MemoryConflict:
        decision_actor.validate()
        conflict = self.get_conflict(scope, conflict_id)
        if conflict.conflict_status == "resolved":
            if conflict.resolution_event_id == resolution_event_id:
                return conflict
            raise MemoryLedgerError("MEMORY_CONFLICT_ALREADY_RESOLVED", "Conflict already has a different resolution.")
        event, link, admission = self._admitted(scope, resolution_event_id)
        digest = self._digest(idempotency_key or f"resolve:{conflict_id}:{resolution_event_id}", "resolve_contradiction")
        system_at = self._time(system_effective_at or utc_now())
        self._require_system_after_admission(system_at, admission)
        if system_at < conflict.system_effective_at:
            raise MemoryLedgerError(
                "MEMORY_CONFLICT_RESOLUTION_INVALID",
                "Conflict resolution cannot precede conflict declaration.",
            )
        record = self._record(scope, "resolve_contradiction", event, link, admission, decision_actor, reason, event["timestamp"], system_at, digest, conflict_id=conflict_id, resolution_event_id=resolution_event_id)
        now = utc_now()
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                self._insert_evolution(connection, record)
                connection.execute(
                    f"UPDATE {self.conflict_table} SET conflict_status={self._p},resolution_event_id={self._p},resolved_at={self._p},resolution_reason={self._p},updated_at={self._p} WHERE conflict_id={self._p} AND conflict_status={self._p}",
                    ("resolved", resolution_event_id, system_at, self._reason(reason), now, conflict_id, "open"),
                )
        except Exception as exc:
            replay = self._evolution_by_digest(scope, digest)
            if replay:
                return self.get_conflict(scope, conflict_id)
            raise MemoryLedgerError("MEMORY_CONFLICT_RESOLUTION_INVALID", "Conflict resolution transaction failed.", retryable=True) from exc
        _log("memory_conflict_resolved", conflict_id=conflict_id, evolution_id=record.evolution_id)
        return self.get_conflict(scope, conflict_id)

    def invalidate_admitted_memory(self, context: MaintenanceContext, event_id: str, reason: str, system_effective_at: str | None = None) -> MemoryEvolutionRecord:
        if not context.privileged or context.scope is None:
            raise MemoryLedgerError("MEMORY_EVENT_SCOPE_DENIED", "Privileged scoped maintenance authority is required.")
        scope = context.scope
        event, link, admission = self._admitted(scope, event_id)
        actor = AdmissionDecisionActor("internal_service", "maintenance")
        digest = self._digest(f"invalidate:{event_id}:{reason}", "invalidate")
        replay = self._evolution_by_digest(scope, digest)
        if replay:
            return replay
        system_at = self._time(system_effective_at or utc_now())
        self._require_system_after_admission(system_at, admission)
        record = self._record(scope, "invalidate", event, link, admission, actor, reason, event["timestamp"], system_at, digest)
        self._insert_record(record)
        _log("memory_event_invalidated", evolution_id=record.evolution_id)
        return record

    def get_conflict(self, scope: AuthenticatedScope, conflict_id: str) -> MemoryConflict:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.conflict_table} WHERE conflict_id={self._p} AND client_id={self._p} AND vault_id={self._p} AND namespace={self._p}",
                (conflict_id, *scope.memory_boundary()),
            ).fetchone()
        if not row:
            raise MemoryLedgerError("MEMORY_CONFLICT_NOT_FOUND", "Conflict was not found in the authenticated scope.")
        return self._conflict_from_row(row)

    def list_evolutions(self, scope: AuthenticatedScope) -> list[MemoryEvolutionRecord]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.evolution_table} WHERE client_id={self._p} AND vault_id={self._p} AND namespace={self._p} ORDER BY system_effective_at,evolution_id",
                scope.memory_boundary(),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def list_conflicts(self, scope: AuthenticatedScope) -> list[MemoryConflict]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.conflict_table} WHERE client_id={self._p} AND vault_id={self._p} AND namespace={self._p} ORDER BY system_effective_at,conflict_id",
                scope.memory_boundary(),
            ).fetchall()
        return [self._conflict_from_row(row) for row in rows]

    def trace_memory_evolution(self, scope: AuthenticatedScope, event_id: str) -> dict[str, Any]:
        event, _, _ = self._admitted(scope, event_id)
        records = self.list_evolutions(scope)
        relevant = [item for item in records if event_id in {item.source_event_id, item.replacement_event_id, item.resolution_event_id}]
        origins = {event_id: self.admission.trace_admitted_memory_origin(scope, event_id)}
        for item in relevant:
            for linked in (item.source_event_id, item.replacement_event_id, item.resolution_event_id):
                if linked and linked not in origins:
                    origins[linked] = self.admission.trace_admitted_memory_origin(scope, linked)
        from .memory_ledger_integrity import MemoryLedgerIntegrityVerifier
        from .memory_state_resolver import MemoryStateResolver

        view = MemoryStateResolver(self.repository).resolve_effective_events(scope)
        projection = next(
            (item for item in view.projections if item.event_id == event_id), None
        )
        predecessors = sorted(
            item.source_event_id
            for item in records
            if item.replacement_event_id == event_id
        )
        successors = sorted(
            item.replacement_event_id
            for item in records
            if item.source_event_id == event_id and item.replacement_event_id
        )
        integrity = MemoryLedgerIntegrityVerifier(
            self.repository
        ).verify_memory_ledger_integrity(scope)
        return {
            "event_id": event["event_id"],
            "original_event": event,
            "evolutions": [item.to_dict() for item in relevant],
            "origins": origins,
            "conflicts": [item.to_dict() for item in self.list_conflicts(scope) if event_id in item.conflicting_event_ids or item.resolution_event_id == event_id],
            "predecessor_event_ids": predecessors,
            "successor_event_ids": successors,
            "current_projection": projection.to_dict() if projection else None,
            "temporal_intervals": [
                {
                    "valid_from": item.valid_from,
                    "valid_until": item.valid_until,
                    "system_effective_at": item.system_effective_at,
                }
                for item in relevant
            ],
            "integrity": {
                "verified": integrity.verified,
                "failures": integrity.failures,
            },
            "history_erased": False,
            "revisions": {"memory_ledger_schema_revision": MEMORY_LEDGER_SCHEMA_REVISION, "memory_evolution_revision": MEMORY_EVOLUTION_REVISION},
        }

    def _replace(self, scope: AuthenticatedScope, kind: str, source_id: str, replacement_id: str, actor: AdmissionDecisionActor, reason: str, valid_from: str | None, system_at: str | None, key: str | None) -> MemoryEvolutionRecord:
        actor.validate()
        if source_id == replacement_id:
            raise MemoryLedgerError("MEMORY_EVOLUTION_CYCLE_DETECTED", "An event cannot replace itself.")
        source_event, source_link, source_admission = self._admitted(scope, source_id)
        replacement_event, replacement_link, replacement_admission = self._admitted(scope, replacement_id)
        if self._terminal_evolution(scope, source_id):
            existing = self._latest_for_source(scope, source_id, kind)
            if existing and existing.replacement_event_id == replacement_id:
                return existing
            raise MemoryLedgerError("MEMORY_EVOLUTION_STATE_INVALID", "Source event is already inactive.")
        if self._would_cycle(scope, source_id, replacement_id):
            _log("memory_evolution_cycle_rejected", source_event_id=source_id, replacement_event_id=replacement_id)
            raise MemoryLedgerError("MEMORY_EVOLUTION_CYCLE_DETECTED", "Evolution would create a cycle.")
        digest = self._digest(key or f"{kind}:{source_id}:{replacement_id}", kind)
        replay = self._evolution_by_digest(scope, digest)
        if replay:
            return replay
        valid = self._time(valid_from or replacement_event["timestamp"])
        system = self._time(system_at or utc_now())
        self._require_system_after_admission(system, source_admission, replacement_admission)
        record = self._record(
            scope, kind, source_event, source_link, source_admission, actor, reason,
            valid, system, digest, replacement_event=replacement_event,
            replacement_link=replacement_link, replacement_admission=replacement_admission,
        )
        self._insert_record(record)
        return record

    def _record(self, scope: AuthenticatedScope, kind: str, source_event: dict[str, Any], source_link: Any, source_admission: Any, actor: AdmissionDecisionActor, reason: str, valid_from: str, system_at: str, digest: str, *, replacement_event: dict[str, Any] | None = None, replacement_link: Any = None, replacement_admission: Any = None, conflict_id: str | None = None, resolution_event_id: str | None = None) -> MemoryEvolutionRecord:
        now = utc_now()
        identity = canonical_json({"scope": scope.memory_boundary(), "kind": kind, "source": source_event["event_id"], "replacement": replacement_event and replacement_event["event_id"], "conflict": conflict_id, "resolution": resolution_event_id, "digest": digest})
        return MemoryEvolutionRecord(
            f"mevo_{sha256_text(identity)[:24]}", kind, "completed", source_event["event_id"],
            replacement_event and replacement_event["event_id"], conflict_id, resolution_event_id,
            *scope.memory_boundary(), source_link.application_reference, source_link.actor_reference,
            source_link.workspace_reference, list(source_link.entity_references), source_link.session_reference,
            self._time(valid_from), None, self._time(system_at), actor.actor_type, actor.actor_reference,
            self._reason(reason), {"history_erased": False, "truth_winner_selected": False},
            sha256_text(canonical_json(source_event)),
            sha256_text(canonical_json(replacement_event)) if replacement_event else None,
            source_admission.admission_id, replacement_admission.admission_id if replacement_admission else None,
            MEMORY_LEDGER_SCHEMA_REVISION, MEMORY_EVOLUTION_REVISION, BITEMPORAL_POLICY_REVISION,
            digest, now, 0.0, None, now, now,
        )

    def _admitted(self, scope: AuthenticatedScope, event_id: str) -> tuple[dict[str, Any], Any, Any]:
        try:
            event = self.admission.get_admitted_event(scope, event_id)
            link = self.admission.get_admitted_memory_link(scope, event_id)
            admission = self.admission.get_admission(scope, link.admission_id)
            integrity = self.admission.verify_admission_integrity(scope, admission.admission_id)
        except Exception as exc:
            raise MemoryLedgerError("MEMORY_EVENT_NOT_FOUND", "Admitted event was not found in the authenticated scope.") from exc
        if not integrity.verified:
            raise MemoryLedgerError("MEMORY_LEDGER_INTEGRITY_FAILED", "Admitted event provenance failed integrity verification.")
        return event, link, admission

    def _terminal_evolution(self, scope: AuthenticatedScope, event_id: str) -> bool:
        return any(item.source_event_id == event_id and item.evolution_type in {"correct", "supersede", "retract", "invalidate"} for item in self.list_evolutions(scope))

    def _latest_for_source(self, scope: AuthenticatedScope, event_id: str, kind: str) -> MemoryEvolutionRecord | None:
        items = [item for item in self.list_evolutions(scope) if item.source_event_id == event_id and item.evolution_type == kind]
        return items[-1] if items else None

    def _would_cycle(self, scope: AuthenticatedScope, source: str, replacement: str) -> bool:
        graph: dict[str, set[str]] = {}
        for item in self.list_evolutions(scope):
            if item.evolution_type in {"correct", "supersede"} and item.replacement_event_id:
                graph.setdefault(item.source_event_id, set()).add(item.replacement_event_id)
        graph.setdefault(source, set()).add(replacement)
        stack = [replacement]
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node == source:
                return True
            if node not in seen:
                seen.add(node)
                stack.extend(graph.get(node, ()))
        return False

    def _insert_record(self, record: MemoryEvolutionRecord) -> None:
        try:
            with self.repository.connect() as connection:
                self._begin(connection)
                self._insert_evolution(connection, record)
        except Exception as exc:
            replay = self._evolution_by_digest(AuthenticatedScope(record.client_id, record.vault_id, record.namespace), record.idempotency_digest)
            if replay:
                return
            raise MemoryLedgerError("MEMORY_EVOLUTION_STATE_INVALID", "Evolution transaction failed.", retryable=True) from exc

    def _insert_evolution(self, connection: Any, record: MemoryEvolutionRecord) -> None:
        data = record.to_dict()
        columns = ["entity_references_json" if k == "entity_references" else "evolution_metadata_json" if k == "evolution_metadata" else k for k in data]
        values = [canonical_json(v) if k in {"entity_references", "evolution_metadata"} else v for k, v in data.items()]
        connection.execute(f"INSERT INTO {self.evolution_table}({','.join(columns)}) VALUES({','.join([self._p]*len(values))})", tuple(values))

    def _insert_conflict(self, connection: Any, conflict: MemoryConflict) -> None:
        data = conflict.to_dict()
        columns = []
        values = []
        for key, value in data.items():
            if key == "entity_references":
                columns.append("entity_references_json"); values.append(canonical_json(value))
            elif key == "conflicting_event_ids":
                columns.append("conflicting_event_ids_json"); values.append(canonical_json(value))
            else:
                columns.append(key); values.append(value)
        columns.insert(11, "event_set_fingerprint")
        values.insert(11, sha256_text(canonical_json({"events": conflict.conflicting_event_ids, "revision": MEMORY_CONFLICT_REVISION})))
        connection.execute(f"INSERT INTO {self.conflict_table}({','.join(columns)}) VALUES({','.join([self._p]*len(values))})", tuple(values))

    def _evolution_by_digest(self, scope: AuthenticatedScope, digest: str) -> MemoryEvolutionRecord | None:
        with self.repository.connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.evolution_table} WHERE client_id={self._p} AND vault_id={self._p} AND namespace={self._p} AND idempotency_digest={self._p}", (*scope.memory_boundary(), digest)).fetchone()
        return self._record_from_row(row) if row else None

    def _conflict_by_fingerprint(self, scope: AuthenticatedScope, fingerprint: str) -> MemoryConflict | None:
        with self.repository.connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.conflict_table} WHERE client_id={self._p} AND vault_id={self._p} AND namespace={self._p} AND event_set_fingerprint={self._p}", (*scope.memory_boundary(), fingerprint)).fetchone()
        return self._conflict_from_row(row) if row else None

    def _record_from_row(self, row: Any) -> MemoryEvolutionRecord:
        return MemoryEvolutionRecord(
            **{key: (self._json(row["entity_references_json"]) if key == "entity_references" else self._json(row["evolution_metadata_json"]) if key == "evolution_metadata" else row[key]) for key in MemoryEvolutionRecord.__dataclass_fields__}
        )

    def _conflict_from_row(self, row: Any) -> MemoryConflict:
        return MemoryConflict(
            **{key: (self._json(row["entity_references_json"]) if key == "entity_references" else self._json(row["conflicting_event_ids_json"]) if key == "conflicting_event_ids" else row[key]) for key in MemoryConflict.__dataclass_fields__}
        )

    @staticmethod
    def _json(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _reason(value: str) -> str:
        cleaned = " ".join(str(value).split())
        if not cleaned or len(cleaned) > 500 or any(token in cleaned.lower() for token in ("authorization:", "bearer ", "api_key", "database_url", "postgresql://")):
            raise MemoryLedgerError("MEMORY_EVOLUTION_STATE_INVALID", "Evolution reason is invalid or contains restricted material.")
        return cleaned

    @staticmethod
    def _digest(key: str, kind: str) -> str:
        if not key or len(key) > 500:
            raise MemoryLedgerError("MEMORY_EVOLUTION_IDEMPOTENCY_CONFLICT", "A valid idempotency key is required.")
        return sha256_text(f"{kind}:{key}")

    @staticmethod
    def _time(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError as exc:
            raise MemoryLedgerError("MEMORY_TEMPORAL_BOUNDARY_INVALID", "Temporal value is invalid.") from exc

    def _begin(self, connection: Any) -> None:
        if self.backend == "sqlite":
            connection.execute("BEGIN IMMEDIATE")

    def _require_system_after_admission(self, system_at: str, *admissions: Any) -> None:
        known_times = [
            self._time(item.completed_at)
            for item in admissions
            if item is not None and item.completed_at
        ]
        if known_times and system_at < max(known_times):
            raise MemoryLedgerError(
                "MEMORY_EVOLUTION_STATE_INVALID",
                "Evolution cannot become effective before its admitted memory was known.",
            )

    @property
    def _p(self) -> str:
        return "%s" if self.backend == "postgres" else "?"


__all__ = [
    "CONFLICT_TABLE", "EVOLUTION_TABLE", "RECONSTRUCTION_TABLE", "MemoryLedgerService",
    "SQLITE_MEMORY_LEDGER_SCHEMA", "initialize_postgres_memory_ledger_schema",
    "initialize_sqlite_memory_ledger_schema",
]
