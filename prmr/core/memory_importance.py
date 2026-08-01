"""Append-only explicit importance annotations for temporal memory."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from .admission_models import AdmissionDecisionActor
from .memory_ledger_service import MemoryLedgerService
from .memory_temporal_models import (
    MEMORY_IMPORTANCE_REVISION,
    MEMORY_TEMPORAL_SCHEMA_REVISION,
    MemoryDynamicsError,
    MemoryImportanceAnnotation,
    MemoryImportanceLevel,
    TemporalMemoryPolicy,
)
from .memory_temporal_policy import quantize8, validate_policy
from .source_integrity import canonical_json, sha256_text
from .source_ledger import POSTGRES_SCHEMA, utc_now
from .source_models import AuthenticatedScope


IMPORTANCE_TABLE = "prmr_memory_importance_annotations"
SNAPSHOT_TABLE = "prmr_memory_dynamics_snapshots"
SIGNAL_DYNAMICS_TABLE = "prmr_memory_signal_dynamics"
TEMPORAL_MIGRATION_TABLE = "prmr_memory_temporal_schema_migrations"
LOGGER = logging.getLogger("prmr.core.memory_importance")


SQLITE_TEMPORAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS prmr_memory_temporal_schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_importance_annotations (
    importance_annotation_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
    entity_references_json TEXT NOT NULL, session_reference TEXT,
    importance_level TEXT, importance_weight REAL NOT NULL,
    annotation_actor_type TEXT NOT NULL, annotation_actor_reference TEXT NOT NULL,
    annotation_reason TEXT NOT NULL, system_effective_at TEXT NOT NULL,
    memory_importance_revision TEXT NOT NULL, idempotency_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id,vault_id,namespace,idempotency_digest)
);
CREATE TABLE IF NOT EXISTS prmr_memory_dynamics_snapshots (
    dynamics_snapshot_id TEXT PRIMARY KEY,
    dynamics_snapshot_identity TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL, vault_id TEXT NOT NULL, namespace TEXT NOT NULL,
    application_reference TEXT, actor_reference TEXT, workspace_reference TEXT,
    entity_reference TEXT, session_reference TEXT,
    valid_at TEXT NOT NULL, known_at TEXT NOT NULL,
    dynamics_mode TEXT NOT NULL, temporal_policy_id TEXT NOT NULL,
    resolved_event_manifest_hash TEXT NOT NULL,
    importance_annotation_manifest_hash TEXT NOT NULL,
    signal_dynamics_manifest_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prmr_memory_signal_dynamics (
    signal_dynamics_id TEXT PRIMARY KEY,
    dynamics_snapshot_id TEXT NOT NULL,
    signal_key TEXT NOT NULL,
    memory_phase TEXT NOT NULL,
    reinforced INTEGER NOT NULL,
    re_emerging INTEGER NOT NULL,
    final_influence REAL NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(dynamics_snapshot_id,signal_key),
    FOREIGN KEY(dynamics_snapshot_id)
      REFERENCES prmr_memory_dynamics_snapshots(dynamics_snapshot_id)
);
CREATE INDEX IF NOT EXISTS prmr_importance_event_idx ON prmr_memory_importance_annotations(event_id);
CREATE INDEX IF NOT EXISTS prmr_importance_scope_idx ON prmr_memory_importance_annotations(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_importance_system_idx ON prmr_memory_importance_annotations(system_effective_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_scope_idx ON prmr_memory_dynamics_snapshots(client_id,vault_id,namespace);
CREATE INDEX IF NOT EXISTS prmr_dynamics_valid_idx ON prmr_memory_dynamics_snapshots(valid_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_known_idx ON prmr_memory_dynamics_snapshots(known_at);
CREATE INDEX IF NOT EXISTS prmr_dynamics_policy_idx ON prmr_memory_dynamics_snapshots(temporal_policy_id);
CREATE INDEX IF NOT EXISTS prmr_dynamics_event_manifest_idx ON prmr_memory_dynamics_snapshots(resolved_event_manifest_hash);
CREATE INDEX IF NOT EXISTS prmr_signal_snapshot_idx ON prmr_memory_signal_dynamics(dynamics_snapshot_id);
CREATE INDEX IF NOT EXISTS prmr_signal_key_idx ON prmr_memory_signal_dynamics(signal_key);
CREATE INDEX IF NOT EXISTS prmr_signal_phase_idx ON prmr_memory_signal_dynamics(memory_phase);
CREATE INDEX IF NOT EXISTS prmr_signal_reinforced_idx ON prmr_memory_signal_dynamics(reinforced);
CREATE INDEX IF NOT EXISTS prmr_signal_reemerging_idx ON prmr_memory_signal_dynamics(re_emerging);
"""


def initialize_sqlite_temporal_schema(connection: Any) -> None:
    connection.executescript(SQLITE_TEMPORAL_SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO prmr_memory_temporal_schema_migrations(revision,applied_at) "
        "VALUES(?,?)",
        (MEMORY_TEMPORAL_SCHEMA_REVISION, utc_now()),
    )


def initialize_postgres_temporal_schema(connection: Any) -> None:
    cursor = connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {POSTGRES_SCHEMA}")
    statements = [
        item.strip() for item in SQLITE_TEMPORAL_SCHEMA.split(";") if item.strip()
    ]
    for statement in statements:
        if statement.startswith("CREATE TABLE"):
            statement = statement.replace(
                "CREATE TABLE IF NOT EXISTS ",
                f"CREATE TABLE IF NOT EXISTS {POSTGRES_SCHEMA}.",
                1,
            )
        elif statement.startswith("CREATE INDEX"):
            marker = " ON prmr_"
            statement = statement.replace(
                marker, f" ON {POSTGRES_SCHEMA}.prmr_", 1
            )
        statement = statement.replace("payload_json TEXT", "payload_json JSONB")
        statement = statement.replace(
            "entity_references_json TEXT", "entity_references_json JSONB"
        )
        statement = statement.replace(
            "REFERENCES prmr_memory_dynamics_snapshots",
            f"REFERENCES {POSTGRES_SCHEMA}.prmr_memory_dynamics_snapshots",
        )
        statement = statement.replace("reinforced INTEGER", "reinforced BOOLEAN")
        statement = statement.replace("re_emerging INTEGER", "re_emerging BOOLEAN")
        cursor.execute(statement)
    cursor.execute(
        f"INSERT INTO {POSTGRES_SCHEMA}.prmr_memory_temporal_schema_migrations"
        "(revision,applied_at) VALUES(%s,%s) ON CONFLICT(revision) DO NOTHING",
        (MEMORY_TEMPORAL_SCHEMA_REVISION, utc_now()),
    )


class MemoryImportanceService:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.backend = str(getattr(repository, "backend_name", "sqlite"))
        self.ledger = MemoryLedgerService(repository, initialize=initialize)
        prefix = f"{POSTGRES_SCHEMA}." if self.backend == "postgres" else ""
        self.table = prefix + IMPORTANCE_TABLE
        self.snapshot_table = prefix + SNAPSHOT_TABLE
        self.signal_table = prefix + SIGNAL_DYNAMICS_TABLE
        self.placeholder = "%s" if self.backend == "postgres" else "?"
        if initialize:
            with repository.connect() as connection:
                (
                    initialize_postgres_temporal_schema
                    if self.backend == "postgres"
                    else initialize_sqlite_temporal_schema
                )(connection)

    def annotate_memory_importance(
        self,
        authenticated_scope: AuthenticatedScope,
        event_id: str,
        importance_level_or_weight: str | float | int,
        actor: AdmissionDecisionActor,
        reason: str,
        system_effective_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> MemoryImportanceAnnotation:
        actor.validate()
        try:
            _, link, admission = self.ledger._admitted(
                authenticated_scope, event_id
            )
        except Exception as exc:
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_SCOPE_DENIED",
                "Admitted event was not found in the authenticated scope.",
            ) from exc
        level, weight = self._importance(importance_level_or_weight)
        system_at = self._time(system_effective_at or utc_now())
        if admission.completed_at and system_at < self._time(admission.completed_at):
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_INVALID",
                "Importance cannot become effective before event admission.",
            )
        raw_key = idempotency_key or f"{event_id}:{level}:{weight}:{system_at}"
        if not raw_key or len(raw_key) > 500:
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_IDEMPOTENCY_CONFLICT",
                "Importance idempotency key is invalid.",
            )
        digest = sha256_text(f"importance:{raw_key}")
        cleaned_reason = self._reason(reason)
        replay = self._by_digest(authenticated_scope, digest)
        if replay:
            if not self._same_intent(
                replay,
                event_id=event_id,
                level=level,
                weight=weight,
                actor=actor,
                reason=cleaned_reason,
            ):
                raise MemoryDynamicsError(
                    "MEMORY_IMPORTANCE_IDEMPOTENCY_CONFLICT",
                    "Importance idempotency key was reused with different input.",
                )
            return replay
        created_at = utc_now()
        identity = canonical_json(
            {
                "scope": authenticated_scope.memory_boundary(),
                "event_id": event_id,
                "digest": digest,
                "revision": MEMORY_IMPORTANCE_REVISION,
            }
        )
        annotation = MemoryImportanceAnnotation(
            importance_annotation_id=f"mimp_{sha256_text(identity)[:24]}",
            event_id=event_id,
            client_id=authenticated_scope.client_id,
            vault_id=authenticated_scope.vault_id,
            namespace=authenticated_scope.namespace,
            application_reference=link.application_reference,
            actor_reference=link.actor_reference,
            workspace_reference=link.workspace_reference,
            entity_references=list(link.entity_references),
            session_reference=link.session_reference,
            importance_level=level,
            importance_weight=weight,
            annotation_actor_type=actor.actor_type,
            annotation_actor_reference=actor.actor_reference,
            annotation_reason=cleaned_reason,
            system_effective_at=system_at,
            memory_importance_revision=MEMORY_IMPORTANCE_REVISION,
            idempotency_digest=digest,
            created_at=created_at,
        )
        try:
            with self.repository.connect() as connection:
                if self.backend == "sqlite":
                    connection.execute("BEGIN IMMEDIATE")
                self._insert(connection, annotation)
        except Exception as exc:
            replay = self._by_digest(authenticated_scope, digest)
            if replay and self._same_intent(
                replay,
                event_id=event_id,
                level=level,
                weight=weight,
                actor=actor,
                reason=cleaned_reason,
            ):
                return replay
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_IDEMPOTENCY_CONFLICT",
                "Importance annotation could not be stored.",
                retryable=True,
            ) from exc
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "event": "memory_importance_annotated",
                    "importance_annotation_id": annotation.importance_annotation_id,
                    "event_count": 1,
                    "memory_importance_revision": MEMORY_IMPORTANCE_REVISION,
                    "scope_fingerprint": sha256_text(
                        canonical_json(authenticated_scope.memory_boundary())
                    )[:16],
                },
                sort_keys=True,
            ),
        )
        return annotation

    @staticmethod
    def _same_intent(
        existing: MemoryImportanceAnnotation,
        *,
        event_id: str,
        level: str | None,
        weight: float,
        actor: AdmissionDecisionActor,
        reason: str,
    ) -> bool:
        return (
            existing.event_id == event_id
            and existing.importance_level == level
            and existing.importance_weight == weight
            and existing.annotation_actor_type == actor.actor_type
            and existing.annotation_actor_reference == actor.actor_reference
            and existing.annotation_reason == reason
        )

    def list_importance_annotations(
        self, authenticated_scope: AuthenticatedScope, event_id: str
    ) -> list[MemoryImportanceAnnotation]:
        try:
            self.ledger._admitted(authenticated_scope, event_id)
        except Exception as exc:
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_SCOPE_DENIED",
                "Admitted event was not found in the authenticated scope.",
            ) from exc
        p = self.placeholder
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.table} WHERE event_id={p} "
                f"AND client_id={p} AND vault_id={p} AND namespace={p} "
                "ORDER BY system_effective_at,importance_annotation_id",
                (event_id, *authenticated_scope.memory_boundary()),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def effective_annotations(
        self, authenticated_scope: AuthenticatedScope, known_at: str
    ) -> dict[str, MemoryImportanceAnnotation]:
        p = self.placeholder
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.table} WHERE client_id={p} AND vault_id={p} "
                f"AND namespace={p} AND system_effective_at<={p} "
                "ORDER BY event_id,system_effective_at,importance_annotation_id",
                (*authenticated_scope.memory_boundary(), known_at),
            ).fetchall()
        latest: dict[str, MemoryImportanceAnnotation] = {}
        for row in rows:
            item = self._from_row(row)
            latest[item.event_id] = item
        return latest

    def _insert(self, connection: Any, item: MemoryImportanceAnnotation) -> None:
        data = item.to_dict()
        columns = [
            "entity_references_json" if key == "entity_references" else key
            for key in data
        ]
        values = [
            canonical_json(value) if key == "entity_references" else value
            for key, value in data.items()
        ]
        connection.execute(
            f"INSERT INTO {self.table}({','.join(columns)}) "
            f"VALUES({','.join([self.placeholder] * len(values))})",
            tuple(values),
        )

    def _by_digest(
        self, scope: AuthenticatedScope, digest: str
    ) -> MemoryImportanceAnnotation | None:
        p = self.placeholder
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table} WHERE client_id={p} AND vault_id={p} "
                f"AND namespace={p} AND idempotency_digest={p}",
                (*scope.memory_boundary(), digest),
            ).fetchone()
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: Any) -> MemoryImportanceAnnotation:
        payload = dict(row)
        raw = payload.pop("entity_references_json")
        payload["entity_references"] = json.loads(raw) if isinstance(raw, str) else raw
        return MemoryImportanceAnnotation(**payload)

    @staticmethod
    def _importance(value: str | float | int) -> tuple[str | None, float]:
        policy = validate_policy(TemporalMemoryPolicy())
        weights = policy.configuration()["importance_weights"]
        if isinstance(value, str):
            level = value.strip().lower()
            if level not in {item.value for item in MemoryImportanceLevel}:
                raise MemoryDynamicsError(
                    "MEMORY_IMPORTANCE_INVALID", "Importance level is invalid."
                )
            return level, quantize8(weights[level])
        if isinstance(value, bool):
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_INVALID", "Importance weight is invalid."
            )
        weight = float(value)
        if not policy.numeric_importance_min <= weight <= policy.numeric_importance_max:
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_INVALID",
                "Importance weight is outside the allowed range.",
            )
        return None, quantize8(weight)

    @staticmethod
    def _reason(value: str) -> str:
        cleaned = " ".join(str(value).split())
        restricted = ("authorization:", "bearer ", "api_key", "database_url", "postgresql://")
        if not cleaned or len(cleaned) > 500 or any(
            item in cleaned.lower() for item in restricted
        ):
            raise MemoryDynamicsError(
                "MEMORY_IMPORTANCE_INVALID", "Importance reason is invalid."
            )
        return cleaned

    @staticmethod
    def _time(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MemoryDynamicsError(
                "MEMORY_TEMPORAL_BOUNDARY_INVALID", "Temporal value is invalid."
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "IMPORTANCE_TABLE",
    "SIGNAL_DYNAMICS_TABLE",
    "SNAPSHOT_TABLE",
    "SQLITE_TEMPORAL_SCHEMA",
    "MemoryImportanceService",
    "initialize_postgres_temporal_schema",
    "initialize_sqlite_temporal_schema",
]
