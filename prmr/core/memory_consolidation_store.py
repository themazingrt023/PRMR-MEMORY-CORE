"""Durable storage for derived memory-consolidation artifacts."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from .memory_consolidation_models import (
    MEMORY_CONSOLIDATION_SCHEMA_REVISION,
    ConsolidatedMemory,
    ConsolidatedMemoryMember,
    MemoryCheckpoint,
    MemoryCheckpointDelta,
    MemoryConsolidationEquivalenceProof,
    MemoryConsolidationInvalidation,
    MemoryConsolidationPlan,
    MemoryConsolidationRun,
)
from .memory_query_store import (
    POSTGRES_SCHEMA,
    backend_name,
    json_value,
    payload_from_row,
    placeholder,
    table,
)
from .source_models import AuthenticatedScope


ROOT = Path(__file__).resolve().parents[2]
SQLITE_MIGRATION = ROOT / "migrations" / "core_memory_consolidation_v1_sqlite.sql"
POSTGRES_MIGRATION = ROOT / "migrations" / "core_memory_consolidation_v1_postgres.sql"
T = TypeVar("T")


def _from_row(cls: type[T], row: Any) -> T:
    payload = payload_from_row(row)
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in payload.items() if key in allowed})


def initialize_memory_consolidation_schema(repository: Any) -> None:
    with repository.connect() as connection:
        if backend_name(repository) == "postgres":
            connection.execute(POSTGRES_MIGRATION.read_text(encoding="utf-8"))
            connection.execute(
                f"INSERT INTO {POSTGRES_SCHEMA}.prmr_memory_consolidation_schema_migrations"
                "(revision,applied_at) VALUES(%s,TO_CHAR(NOW() AT TIME ZONE 'UTC',"
                "'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')) ON CONFLICT(revision) DO NOTHING",
                (MEMORY_CONSOLIDATION_SCHEMA_REVISION,),
            )
        else:
            connection.executescript(SQLITE_MIGRATION.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT OR IGNORE INTO prmr_memory_consolidation_schema_migrations"
                "(revision,applied_at) VALUES(?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (MEMORY_CONSOLIDATION_SCHEMA_REVISION,),
            )


class MemoryConsolidationStore:
    """Parameterised, scope-aware persistence for immutable derived artifacts."""

    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        if initialize:
            initialize_memory_consolidation_schema(repository)
        self.p = placeholder(repository)
        self.plan_table = table(repository, "prmr_memory_consolidation_plans")
        self.run_table = table(repository, "prmr_memory_consolidation_runs")
        self.memory_table = table(repository, "prmr_consolidated_memories")
        self.member_table = table(repository, "prmr_consolidated_memory_members")
        self.checkpoint_table = table(repository, "prmr_memory_checkpoints")
        self.delta_table = table(repository, "prmr_memory_checkpoint_deltas")
        self.invalidation_table = table(
            repository, "prmr_memory_consolidation_invalidations"
        )
        self.proof_table = table(
            repository, "prmr_memory_consolidation_equivalence_proofs"
        )

    @staticmethod
    def _scope(scope: AuthenticatedScope) -> tuple[str, str, str]:
        return scope.client_id, scope.vault_id, scope.namespace

    def put_plan(
        self, scope: AuthenticatedScope, plan: MemoryConsolidationPlan
    ) -> None:
        sql = (
            f"INSERT INTO {self.plan_table}"
            "(consolidation_plan_id,consolidation_run_identity_hash,client_id,"
            "vault_id,namespace,plan_hash_sha256,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 8)}) ON CONFLICT(consolidation_plan_id) "
            "DO NOTHING"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    plan.consolidation_plan_id,
                    plan.consolidation_run_identity_hash,
                    *self._scope(scope),
                    plan.plan_hash_sha256,
                    plan.created_at,
                    json_value(self.repository, plan),
                ),
            )

    def put_run(self, run: MemoryConsolidationRun) -> None:
        sql = (
            f"INSERT INTO {self.run_table}"
            "(consolidation_run_id,consolidation_plan_id,run_identity_hash,client_id,"
            "vault_id,namespace,entity_id,relationship_id,valid_at,known_at,status,"
            "checkpoint_id,consolidation_manifest_hash,created_at,updated_at,payload_json) "
            f"VALUES({','.join([self.p] * 16)}) ON CONFLICT(consolidation_run_id) "
            "DO UPDATE SET status=excluded.status,checkpoint_id=excluded.checkpoint_id,"
            "consolidation_manifest_hash=excluded.consolidation_manifest_hash,"
            "updated_at=excluded.updated_at,payload_json=excluded.payload_json"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    run.consolidation_run_id,
                    run.consolidation_plan_id,
                    run.consolidation_run_identity_hash
                    if hasattr(run, "consolidation_run_identity_hash")
                    else run.consolidation_run_id.removeprefix("mcrun_"),
                    run.client_id,
                    run.vault_id,
                    run.namespace,
                    run.entity_id,
                    run.relationship_id,
                    run.valid_at,
                    run.known_at,
                    run.status,
                    run.checkpoint_id,
                    run.consolidation_manifest_hash,
                    run.created_at,
                    run.updated_at,
                    json_value(self.repository, run),
                ),
            )

    def put_memory(self, memory: ConsolidatedMemory) -> None:
        sql = (
            f"INSERT INTO {self.memory_table}"
            "(consolidated_memory_id,consolidation_run_id,consolidation_type,"
            "consolidation_key,client_id,vault_id,namespace,entity_id,relationship_id,"
            "signal_key,valid_at,known_at,window_start,window_end,status,"
            "contributor_manifest_hash_sha256,consolidated_memory_hash_sha256,"
            "created_at,updated_at,payload_json) "
            f"VALUES({','.join([self.p] * 20)}) ON CONFLICT(consolidated_memory_id) "
            "DO NOTHING"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    memory.consolidated_memory_id,
                    memory.consolidation_run_id,
                    memory.consolidation_type,
                    memory.consolidation_key,
                    memory.client_id,
                    memory.vault_id,
                    memory.namespace,
                    memory.entity_id,
                    memory.relationship_id,
                    memory.signal_key,
                    memory.valid_at,
                    memory.known_at,
                    memory.window_start,
                    memory.window_end,
                    memory.status,
                    memory.contributor_manifest_hash_sha256,
                    memory.consolidated_memory_hash_sha256,
                    memory.created_at,
                    memory.updated_at,
                    json_value(self.repository, memory),
                ),
            )

    def put_members(
        self,
        scope: AuthenticatedScope,
        run_id: str,
        members: list[ConsolidatedMemoryMember],
    ) -> None:
        sql = (
            f"INSERT INTO {self.member_table}"
            "(consolidated_memory_member_id,consolidated_memory_id,"
            "consolidation_run_id,client_id,vault_id,namespace,member_type,event_id,"
            "source_id,candidate_id,admission_id,evolution_id,conflict_id,entity_id,"
            "relationship_id,sequence_index,member_hash_sha256,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 19)}) "
            "ON CONFLICT(consolidated_memory_member_id) DO NOTHING"
        )
        rows = [
            (
                item.consolidated_memory_member_id,
                item.consolidated_memory_id,
                run_id,
                *self._scope(scope),
                item.member_type,
                item.event_id,
                item.source_id,
                item.candidate_id,
                item.admission_id,
                item.evolution_id,
                item.conflict_id,
                item.entity_id,
                item.relationship_id,
                item.sequence_index,
                item.member_hash_sha256,
                item.created_at,
                json_value(self.repository, item),
            )
            for item in members
        ]
        if not rows:
            return
        with self.repository.connect() as connection:
            connection.cursor().executemany(sql, rows)

    def put_checkpoint(self, checkpoint: MemoryCheckpoint) -> None:
        identity = checkpoint.memory_checkpoint_id.removeprefix("mchk_")
        sql = (
            f"INSERT INTO {self.checkpoint_table}"
            "(memory_checkpoint_id,consolidation_run_id,checkpoint_type,"
            "checkpoint_identity_hash,client_id,vault_id,namespace,entity_id,"
            "relationship_id,valid_at,known_at,window_start,window_end,"
            "checkpoint_status,authoritative_event_manifest_hash,"
            "checkpoint_hash_sha256,previous_checkpoint_id,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 19)}) ON CONFLICT(memory_checkpoint_id) "
            "DO UPDATE SET checkpoint_status=excluded.checkpoint_status,"
            "payload_json=excluded.payload_json"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    checkpoint.memory_checkpoint_id,
                    checkpoint.consolidation_run_id,
                    checkpoint.checkpoint_type,
                    identity,
                    checkpoint.client_id,
                    checkpoint.vault_id,
                    checkpoint.namespace,
                    checkpoint.entity_id,
                    checkpoint.relationship_id,
                    checkpoint.valid_at,
                    checkpoint.known_at,
                    checkpoint.window_start,
                    checkpoint.window_end,
                    checkpoint.checkpoint_status,
                    checkpoint.authoritative_event_manifest_hash,
                    checkpoint.checkpoint_hash_sha256,
                    checkpoint.previous_checkpoint_id,
                    checkpoint.created_at,
                    json_value(self.repository, checkpoint),
                ),
            )

    def put_delta(
        self, scope: AuthenticatedScope, delta: MemoryCheckpointDelta
    ) -> None:
        sql = (
            f"INSERT INTO {self.delta_table}"
            "(checkpoint_delta_id,base_checkpoint_id,target_checkpoint_id,client_id,"
            "vault_id,namespace,delta_manifest_hash_sha256,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 9)}) "
            "ON CONFLICT(checkpoint_delta_id) DO NOTHING"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    delta.checkpoint_delta_id,
                    delta.base_checkpoint_id,
                    delta.target_checkpoint_id,
                    *self._scope(scope),
                    delta.delta_manifest_hash_sha256,
                    delta.created_at,
                    json_value(self.repository, delta),
                ),
            )

    def put_invalidation(
        self, scope: AuthenticatedScope, item: MemoryConsolidationInvalidation
    ) -> None:
        sql = (
            f"INSERT INTO {self.invalidation_table}"
            "(invalidation_id,consolidation_run_id,consolidated_memory_id,"
            "checkpoint_id,client_id,vault_id,namespace,invalidation_type,"
            "triggering_object_id,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 11)}) "
            "ON CONFLICT(invalidation_id) DO NOTHING"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    item.invalidation_id,
                    item.consolidation_run_id,
                    item.consolidated_memory_id,
                    item.checkpoint_id,
                    *self._scope(scope),
                    item.invalidation_type,
                    item.triggering_object_id,
                    item.created_at,
                    json_value(self.repository, item),
                ),
            )

    def put_proof(
        self,
        scope: AuthenticatedScope,
        proof: MemoryConsolidationEquivalenceProof,
    ) -> None:
        sql = (
            f"INSERT INTO {self.proof_table}"
            "(equivalence_proof_id,consolidation_run_id,checkpoint_id,client_id,"
            "vault_id,namespace,proof_type,query_type,equivalent,"
            "canonical_result_hash,accelerated_result_hash,created_at,payload_json) "
            f"VALUES({','.join([self.p] * 13)}) "
            "ON CONFLICT(equivalence_proof_id) DO NOTHING"
        )
        with self.repository.connect() as connection:
            connection.execute(
                sql,
                (
                    proof.equivalence_proof_id,
                    proof.consolidation_run_id,
                    proof.checkpoint_id,
                    *self._scope(scope),
                    proof.proof_type,
                    proof.query_type,
                    proof.equivalent,
                    proof.canonical_result_hash,
                    proof.accelerated_result_hash,
                    proof.created_at,
                    json_value(self.repository, proof),
                ),
            )

    def _one(
        self,
        scope: AuthenticatedScope,
        source_table: str,
        id_column: str,
        value: str,
        cls: type[T],
    ) -> T | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {source_table} WHERE {id_column}={self.p} "
                f"AND client_id={self.p} AND vault_id={self.p} AND namespace={self.p}",
                (value, *self._scope(scope)),
            ).fetchone()
        return _from_row(cls, row) if row else None

    def get_plan(
        self, scope: AuthenticatedScope, plan_id: str
    ) -> MemoryConsolidationPlan | None:
        return self._one(
            scope, self.plan_table, "consolidation_plan_id", plan_id, MemoryConsolidationPlan
        )

    def get_run(
        self, scope: AuthenticatedScope, run_id: str
    ) -> MemoryConsolidationRun | None:
        return self._one(
            scope, self.run_table, "consolidation_run_id", run_id, MemoryConsolidationRun
        )

    def get_memory(
        self, scope: AuthenticatedScope, memory_id: str
    ) -> ConsolidatedMemory | None:
        return self._one(
            scope,
            self.memory_table,
            "consolidated_memory_id",
            memory_id,
            ConsolidatedMemory,
        )

    def get_checkpoint(
        self, scope: AuthenticatedScope, checkpoint_id: str
    ) -> MemoryCheckpoint | None:
        return self._one(
            scope,
            self.checkpoint_table,
            "memory_checkpoint_id",
            checkpoint_id,
            MemoryCheckpoint,
        )

    def list_memories(
        self,
        scope: AuthenticatedScope,
        *,
        run_id: str | None = None,
        consolidation_type: str | None = None,
    ) -> list[ConsolidatedMemory]:
        clauses = [
            f"client_id={self.p}",
            f"vault_id={self.p}",
            f"namespace={self.p}",
        ]
        params: list[Any] = list(self._scope(scope))
        if run_id:
            clauses.append(f"consolidation_run_id={self.p}")
            params.append(run_id)
        if consolidation_type:
            clauses.append(f"consolidation_type={self.p}")
            params.append(consolidation_type)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.memory_table} WHERE "
                + " AND ".join(clauses)
                + " ORDER BY consolidation_type,consolidation_key",
                tuple(params),
            ).fetchall()
        return [_from_row(ConsolidatedMemory, row) for row in rows]

    def list_members(
        self, scope: AuthenticatedScope, memory_id: str
    ) -> list[ConsolidatedMemoryMember]:
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.member_table} "
                f"WHERE consolidated_memory_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                "ORDER BY sequence_index,consolidated_memory_member_id",
                (memory_id, *self._scope(scope)),
            ).fetchall()
        return [_from_row(ConsolidatedMemoryMember, row) for row in rows]

    def list_members_for_scope(
        self, scope: AuthenticatedScope
    ) -> list[ConsolidatedMemoryMember]:
        """Load scoped consolidation membership in one ordered repository read."""

        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.member_table} "
                f"WHERE client_id={self.p} AND vault_id={self.p} "
                f"AND namespace={self.p} "
                "ORDER BY consolidated_memory_id,sequence_index,"
                "consolidated_memory_member_id",
                self._scope(scope),
            ).fetchall()
        return [_from_row(ConsolidatedMemoryMember, row) for row in rows]

    def list_checkpoints(
        self,
        scope: AuthenticatedScope,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[MemoryCheckpoint]:
        clauses = [
            f"client_id={self.p}",
            f"vault_id={self.p}",
            f"namespace={self.p}",
        ]
        params: list[Any] = list(self._scope(scope))
        if statuses:
            clauses.append(
                "checkpoint_status IN (" + ",".join([self.p] * len(statuses)) + ")"
            )
            params.extend(statuses)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.checkpoint_table} WHERE "
                + " AND ".join(clauses)
                + " ORDER BY known_at DESC,valid_at DESC,created_at DESC",
                tuple(params),
            ).fetchall()
        return [_from_row(MemoryCheckpoint, row) for row in rows]

    def list_deltas(
        self, scope: AuthenticatedScope, *, target_checkpoint_id: str | None = None
    ) -> list[MemoryCheckpointDelta]:
        clauses = [
            f"client_id={self.p}",
            f"vault_id={self.p}",
            f"namespace={self.p}",
        ]
        params: list[Any] = list(self._scope(scope))
        if target_checkpoint_id:
            clauses.append(f"target_checkpoint_id={self.p}")
            params.append(target_checkpoint_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.delta_table} WHERE "
                + " AND ".join(clauses)
                + " ORDER BY created_at",
                tuple(params),
            ).fetchall()
        return [_from_row(MemoryCheckpointDelta, row) for row in rows]

    def list_proofs(
        self, scope: AuthenticatedScope, *, checkpoint_id: str | None = None
    ) -> list[MemoryConsolidationEquivalenceProof]:
        clauses = [
            f"client_id={self.p}",
            f"vault_id={self.p}",
            f"namespace={self.p}",
        ]
        params: list[Any] = list(self._scope(scope))
        if checkpoint_id:
            clauses.append(f"checkpoint_id={self.p}")
            params.append(checkpoint_id)
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {self.proof_table} WHERE "
                + " AND ".join(clauses)
                + " ORDER BY created_at,equivalence_proof_id",
                tuple(params),
            ).fetchall()
        return [_from_row(MemoryConsolidationEquivalenceProof, row) for row in rows]

    def update_checkpoint_status(
        self,
        scope: AuthenticatedScope,
        checkpoint: MemoryCheckpoint,
    ) -> None:
        self.put_checkpoint(checkpoint)


__all__ = [
    "MemoryConsolidationStore",
    "POSTGRES_MIGRATION",
    "SQLITE_MIGRATION",
    "initialize_memory_consolidation_schema",
]
