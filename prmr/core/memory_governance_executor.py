"""Authorised, resumable, scope-bound governance cascade execution."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any

from .entity_store import json_value, placeholder, scope_params, table
from .memory_dependency_graph import STORAGE_CATALOG
from .memory_governance_models import (
    GovernanceExecutionResult,
    MEMORY_ERASURE_TOMBSTONE_REVISION,
    MEMORY_GOVERNANCE_EXECUTION_REVISION,
    MemoryErasureTombstone,
    MemoryGovernanceError,
    MemoryGovernanceExecution,
)
from .memory_governance_planner import MemoryGovernancePlanner
from .memory_governance_store import MemoryGovernanceStore
from .memory_governance_verifier import MemoryGovernanceVerifier
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


DELETE_RANK = {
    descriptor.table_name: index for index, descriptor in enumerate(STORAGE_CATALOG)
}
DELETE_RANK.update(
    {
        "prmr_admitted_memory_links": 0,
        "prmr_memory_admission_decisions": 1,
        "prmr_candidate_evidence": 2,
        "prmr_candidate_memories": 3,
        "prmr_candidate_extraction_runs": 4,
        "prmr_source_segments": 5,
        "prmr_sources": 10_000,
    }
)


class MemoryGovernanceExecutor:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.planner = MemoryGovernancePlanner(repository, initialize=False)
        self.verifier = MemoryGovernanceVerifier(repository, initialize=False)
        self.p = placeholder(repository)
        self.backend = str(getattr(repository, "backend_name", "sqlite"))

    def execute(
        self,
        scope: AuthenticatedScope,
        governance_plan_id: str,
        *,
        idempotency_key: str,
        started_at: str | None = None,
        interrupt_after_items: int | None = None,
    ) -> GovernanceExecutionResult:
        plan = self.planner.get_plan(scope, governance_plan_id)
        request = self.planner.get_request(scope, plan.governance_request_id)
        if plan.plan_status not in {"approved", "executed"}:
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_NOT_APPROVED", "Governance plan is not approved."
            )
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "plan": plan.governance_plan_id,
                    "idempotency_key": idempotency_key,
                    "revision": MEMORY_GOVERNANCE_EXECUTION_REVISION,
                }
            )
        )
        running = self._running_execution_for_plan(scope, governance_plan_id)
        if running:
            if idempotency_key != running["execution_idempotency_digest"]:
                raise MemoryGovernanceError(
                    "GOVERNANCE_EXECUTION_CONFLICT",
                    "Governance plan already has an active execution.",
                )
            digest = running["execution_idempotency_digest"]
            execution_id = running["governance_execution_id"]
        else:
            execution_id = f"govexec_{digest[:24]}"
        existing = self.store.get(
            "execution",
            "governance_execution_id",
            execution_id,
            scope.memory_boundary(),
        )
        if existing and existing["execution_status"] in {
            "completed",
            "completed_with_invalidations",
        }:
            execution = self._execution(existing)
            verification = self._verification(scope, execution)
            tombstone = self._tombstone(scope, execution)
            return GovernanceExecutionResult(
                execution, verification, tombstone, replayed=True
            )
        now = started_at or utc_now()
        if existing:
            execution = self._execution(existing)
            execution = replace(
                execution,
                execution_status="recovering",
                phase="lock_scope",
                updated_at=now,
            )
            self._update_execution(execution)
            LOGGER.info(
                "memory_governance_execution_recovered",
                extra={"governance_execution_id": execution_id},
            )
        else:
            current = self.planner.graphs.build(
                scope, request, generated_at=now, persist=False
            )
            if current.dependency_graph_id != plan.dependency_graph_id:
                raise MemoryGovernanceError(
                    "GOVERNANCE_PLAN_STALE",
                    "Memory changed after plan approval.",
                )
            execution = MemoryGovernanceExecution(
                governance_execution_id=execution_id,
                governance_request_id=request.governance_request_id,
                governance_plan_id=plan.governance_plan_id,
                action_type=plan.action_type,
                target_type=plan.target_type,
                scope=scope.memory_boundary(),
                execution_status="running",
                phase="validate_plan",
                manifest_before=current.graph_manifest_hash,
                manifest_after=None,
                erased_counts={},
                detached_counts={},
                recomputed_counts={},
                invalidated_counts={},
                retained_counts={},
                tombstone_count=0,
                verification_id=None,
                started_at=now,
                completed_at=None,
                duration_ms=None,
                error_code=None,
                execution_idempotency_digest=digest,
                memory_governance_execution_revision=MEMORY_GOVERNANCE_EXECUTION_REVISION,
                created_at=now,
                updated_at=now,
            )
            try:
                self._insert_execution(scope, execution)
            except Exception as exc:
                if self._execution_for_plan(scope, governance_plan_id):
                    raise MemoryGovernanceError(
                        "GOVERNANCE_EXECUTION_CONFLICT",
                        "Governance plan already has an execution.",
                    ) from exc
                raise
            LOGGER.info(
                "memory_governance_execution_started",
                extra={
                    "governance_execution_id": execution_id,
                    "action_type": plan.action_type,
                },
            )
        items = self._pending_items(scope, plan.governance_plan_id, execution_id)
        processed = 0
        counters: dict[str, Counter[str]] = {
            "erase": Counter(execution.erased_counts),
            "detach": Counter(execution.detached_counts),
            "recompute": Counter(execution.recomputed_counts),
            "invalidate": Counter(execution.invalidated_counts),
            "retain": Counter(execution.retained_counts),
        }
        for item in items:
            action = item["item_action"]
            node = item["node"]
            changed = 0
            if action in {"erase", "invalidate"}:
                changed = self._erase_node(scope, node)
            elif action == "detach":
                changed = self._detach_node(scope, node, request)
            elif action == "recompute":
                changed = 1
            else:
                changed = 1
            counters[action][node["node_type"]] += changed
            self._mark_item(execution_id, item, "completed", processed)
            processed += 1
            execution = replace(
                execution,
                phase={
                    "erase": "erase_exclusive",
                    "detach": "detach_shared",
                    "recompute": "recompute_survivors",
                    "invalidate": "invalidate_derived",
                    "retain": "invalidate_derived",
                }[action],
                erased_counts=dict(counters["erase"]),
                detached_counts=dict(counters["detach"]),
                recomputed_counts=dict(counters["recompute"]),
                invalidated_counts=dict(counters["invalidate"]),
                retained_counts=dict(counters["retain"]),
                updated_at=utc_now(),
            )
            self._update_execution(execution)
            if interrupt_after_items is not None and processed >= interrupt_after_items:
                return GovernanceExecutionResult(
                    execution,
                    None,
                    None,
                    safe_notices=("execution_interrupted_for_recovery_proof",),
                )
        erased_keys = tuple(
            item["node"]["storage_key"]
            for item in items
            if item["item_action"] in {"erase", "invalidate"}
        )
        execution = replace(execution, phase="verify", updated_at=utc_now())
        self._update_execution(execution)
        verification = self.verifier.verify_erasure(
            scope,
            request,
            execution,
            erased_storage_keys=erased_keys,
            shared_recomputed=not plan.planned_recompute_nodes
            or bool(counters["recompute"]),
        )
        if verification.verification_status != "verified":
            failed = replace(
                execution,
                execution_status="failed",
                error_code="GOVERNANCE_ERASURE_VERIFICATION_FAILED",
                verification_id=verification.governance_verification_id,
                updated_at=utc_now(),
            )
            self._update_execution(failed)
            raise MemoryGovernanceError(
                "GOVERNANCE_ERASURE_VERIFICATION_FAILED",
                "Post-erasure verification failed.",
            )
        completed_at = utc_now()
        elapsed = max(
            0,
            int(
                (
                    datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    - datetime.fromisoformat(
                        execution.started_at.replace("Z", "+00:00")
                    )
                ).total_seconds()
                * 1000
            ),
        )
        after_manifest = self.planner.graphs.scope_manifest(scope)
        completed = replace(
            execution,
            execution_status=(
                "completed_with_invalidations"
                if counters["invalidate"]
                else "completed"
            ),
            phase="complete",
            manifest_after=after_manifest,
            tombstone_count=1,
            verification_id=verification.governance_verification_id,
            completed_at=completed_at,
            duration_ms=elapsed,
            updated_at=completed_at,
        )
        tombstone = self._create_tombstone(
            scope, request, plan, completed, verification
        )
        self._update_execution(completed)
        self._finish_request_and_plan(scope, request, plan, completed)
        self._remove_sensitive_governance_working_state(
            request, plan.dependency_graph_id
        )
        LOGGER.info(
            "memory_governance_execution_completed",
            extra={
                "governance_execution_id": execution_id,
                "object_count": sum(completed.erased_counts.values())
                + sum(completed.invalidated_counts.values()),
                "status": completed.execution_status,
            },
        )
        return GovernanceExecutionResult(completed, verification, tombstone)

    def recover_incomplete_governance_executions(
        self, scope: AuthenticatedScope
    ) -> list[str]:
        table_name = self.store.tables["execution"]
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {table_name} WHERE client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                "AND execution_status IN ('running','recovering') ORDER BY started_at",
                scope_params(scope),
            ).fetchall()
        recovered: list[str] = []
        for row in rows:
            payload = self.store.decode(row["payload_json"])
            self.execute(
                scope,
                payload["governance_plan_id"],
                idempotency_key=payload["execution_idempotency_digest"],
            )
            recovered.append(payload["governance_execution_id"])
        return recovered

    def erase_source_with_dependencies(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_actor_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_entity_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_session_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_workspace_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_application_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def execute_tenant_memory_erasure(self, scope: AuthenticatedScope, approved_plan_id: str, **kwargs: Any) -> GovernanceExecutionResult:
        return self.execute(scope, approved_plan_id, **kwargs)

    def _pending_items(
        self,
        scope: AuthenticatedScope,
        plan_id: str,
        execution_id: str,
    ) -> list[dict[str, Any]]:
        plan_table = self.store.tables["plan_item"]
        execution_table = self.store.tables["execution_item"]
        with self.repository.connect() as connection:
            rows = connection.execute(
                f"SELECT p.plan_item_id,p.item_action,p.node_type,p.storage_table,"
                f"p.storage_key,p.sequence_index,p.payload_json,e.item_status "
                f"FROM {plan_table} p LEFT JOIN {execution_table} e ON "
                f"p.plan_item_id=e.plan_item_id AND e.governance_execution_id={self.p} "
                f"WHERE p.governance_plan_id={self.p} AND p.client_id={self.p} "
                f"AND p.vault_id={self.p} AND p.namespace={self.p} "
                "ORDER BY p.sequence_index",
                (execution_id, plan_id, *scope_params(scope)),
            ).fetchall()
        items = []
        for row in rows:
            if row["item_status"] == "completed":
                continue
            payload = self.store.decode(row["payload_json"])
            items.append(
                {
                    "plan_item_id": row["plan_item_id"],
                    "item_action": row["item_action"],
                    "sequence_index": row["sequence_index"],
                    "node": payload["node"],
                }
            )
        return sorted(
            items,
            key=lambda item: (
                DELETE_RANK.get(item["node"]["storage_table"], 10_000),
                item["sequence_index"],
            ),
        )

    def _running_execution_for_plan(
        self, scope: AuthenticatedScope, plan_id: str
    ) -> dict[str, Any] | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.store.tables['execution']} "
                f"WHERE governance_plan_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                "AND execution_status IN ('running','recovering') "
                "ORDER BY started_at LIMIT 1",
                (plan_id, *scope_params(scope)),
            ).fetchone()
        return self.store.decode(row["payload_json"]) if row else None

    def _execution_for_plan(
        self, scope: AuthenticatedScope, plan_id: str
    ) -> dict[str, Any] | None:
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {self.store.tables['execution']} "
                f"WHERE governance_plan_id={self.p} AND client_id={self.p} "
                f"AND vault_id={self.p} AND namespace={self.p} "
                "ORDER BY started_at LIMIT 1",
                (plan_id, *scope_params(scope)),
            ).fetchone()
        return self.store.decode(row["payload_json"]) if row else None

    def _erase_node(self, scope: AuthenticatedScope, node: dict[str, Any]) -> int:
        descriptor = next(
            (
                item
                for item in STORAGE_CATALOG
                if item.table_name == node["storage_table"]
            ),
            None,
        )
        if not descriptor:
            return 0
        if descriptor.blob_kind == "event_list":
            return self._erase_event_blob(scope, node["storage_key"])
        qualified = table(self.repository, descriptor.table_name)
        with self.repository.connect() as connection:
            columns = self._columns(connection, descriptor.table_name)
            id_column = next(
                (item for item in descriptor.id_candidates if item in columns), None
            )
            if not id_column:
                return 0
            predicates = [f"{id_column}={self.p}"]
            params: list[Any] = [node["storage_key"]]
            if {"client_id", "vault_id", "namespace"}.issubset(columns):
                predicates.extend(
                    [
                        f"client_id={self.p}",
                        f"vault_id={self.p}",
                        f"namespace={self.p}",
                    ]
                )
                params.extend(scope.memory_boundary())
            cursor = connection.execute(
                f"DELETE FROM {qualified} WHERE " + " AND ".join(predicates),
                tuple(params),
            )
            return max(0, int(cursor.rowcount))

    def _erase_event_blob(
        self, scope: AuthenticatedScope, event_id: str
    ) -> int:
        qualified = table(self.repository, "events")
        scope_key = "::".join(scope.memory_boundary())
        with self.repository.connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {qualified} WHERE scope_key={self.p}",
                (scope_key,),
            ).fetchone()
            if not row:
                return 0
            raw_events = row["payload_json"]
            events = (
                json.loads(raw_events)
                if isinstance(raw_events, str)
                else list(raw_events or [])
            )
            retained = [
                item for item in events if str(item.get("event_id")) != event_id
            ]
            if len(retained) == len(events):
                return 0
            connection.execute(
                f"UPDATE {qualified} SET payload_json={self.p} WHERE scope_key={self.p}",
                (canonical_json(retained), scope_key),
            )
            return len(events) - len(retained)

    def _detach_node(
        self,
        scope: AuthenticatedScope,
        node: dict[str, Any],
        request: Any,
    ) -> int:
        descriptor = next(
            (
                item
                for item in STORAGE_CATALOG
                if item.table_name == node["storage_table"]
            ),
            None,
        )
        if not descriptor or descriptor.blob_kind:
            return self._erase_node(scope, node)
        qualified = table(self.repository, descriptor.table_name)
        with self.repository.connect() as connection:
            columns = self._columns(connection, descriptor.table_name)
            id_column = next(
                (item for item in descriptor.id_candidates if item in columns), None
            )
            if not id_column or "payload_json" not in columns:
                return self._erase_node(scope, node)
            row = connection.execute(
                f"SELECT * FROM {qualified} WHERE {id_column}={self.p}",
                (node["storage_key"],),
            ).fetchone()
            if not row:
                return 0
            mapping = dict(row)
            if request.opaque_target_reference in {
                str(mapping.get(column, ""))
                for column in columns
                if column != "payload_json"
            }:
                return self._erase_node(scope, node)
            payload = self.store.decode(mapping["payload_json"])
            scrubbed, changed = self._scrub_reference(
                payload,
                request.opaque_target_reference,
                None,
            )
            if not changed:
                return 0
            scrubbed = self._recompute_surviving_evidence(scrubbed)
            assignments = [f"payload_json={self.p}"]
            params: list[Any] = [json_value(self.repository, scrubbed)]
            if (
                "evidence_manifest_hash" in columns
                and "evidence_manifest_hash" in scrubbed
            ):
                assignments.append(f"evidence_manifest_hash={self.p}")
                params.append(scrubbed["evidence_manifest_hash"])
            params.append(node["storage_key"])
            connection.execute(
                f"UPDATE {qualified} SET {','.join(assignments)} "
                f"WHERE {id_column}={self.p}",
                tuple(params),
            )
            return 1

    @classmethod
    def _scrub_reference(
        cls, value: Any, target: str, marker: str | None
    ) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            result = {}
            for key, item in value.items():
                rewritten, item_changed = cls._scrub_reference(item, target, marker)
                result[key] = rewritten
                changed = changed or item_changed
            return result, changed
        if isinstance(value, list):
            changed = False
            result = []
            for item in value:
                rewritten, item_changed = cls._scrub_reference(item, target, marker)
                if not (item_changed and rewritten is None):
                    result.append(rewritten)
                changed = changed or item_changed
            return result, changed
        if value == target:
            return marker, True
        return value, False

    @staticmethod
    def _recompute_surviving_evidence(payload: dict[str, Any]) -> dict[str, Any]:
        support_keys = (
            "source_ids",
            "event_ids",
            "candidate_ids",
            "evidence_ids",
            "supporting_source_ids",
            "supporting_event_ids",
            "supporting_candidate_ids",
            "supporting_evidence_ids",
        )
        supports = {
            key: sorted(str(item) for item in payload.get(key, []) if item)
            for key in support_keys
            if isinstance(payload.get(key), list)
        }
        if supports:
            payload["evidence_manifest_hash"] = sha256_text(
                canonical_json(supports)
            )
            payload["governance_evidence_status"] = "recomputed_after_detach"
        return payload

    def _mark_item(
        self,
        execution_id: str,
        item: dict[str, Any],
        status: str,
        sequence: int,
    ) -> None:
        material = {"execution": execution_id, "item": item["plan_item_id"]}
        item_id = f"gxitem_{sha256_text(canonical_json(material))[:24]}"
        existing = self.store.get(
            "execution_item", "execution_item_id", item_id
        )
        now = utc_now()
        if existing:
            return
        self.store.insert(
            "execution_item",
            (
                "execution_item_id",
                "governance_execution_id",
                "plan_item_id",
                "item_status",
                "batch_sequence",
                "updated_at",
            ),
            (item_id, execution_id, item["plan_item_id"], status, sequence, now),
            {
                "execution_item_id": item_id,
                "governance_execution_id": execution_id,
                "plan_item_id": item["plan_item_id"],
                "item_status": status,
                "batch_sequence": sequence,
                "updated_at": now,
            },
        )

    def _create_tombstone(
        self, scope: AuthenticatedScope, request: Any, plan: Any, execution: Any, verification: Any
    ) -> MemoryErasureTombstone:
        material = {
            "execution": execution.governance_execution_id,
            "target_digest": request.target_reference_digest,
            "plan": plan.plan_hash_sha256,
            "verification": verification.verification_manifest_hash,
            "revision": MEMORY_ERASURE_TOMBSTONE_REVISION,
        }
        digest = sha256_text(canonical_json(material))
        tombstone = MemoryErasureTombstone(
            erasure_tombstone_id=f"tomb_{digest[:24]}",
            governance_execution_id=execution.governance_execution_id,
            target_type=request.target_type,
            target_reference_digest=request.target_reference_digest,
            scope_fingerprint=sha256_text(canonical_json(scope.memory_boundary()))[:24],
            governance_policy_id=request.governance_policy_id,
            plan_hash_sha256=plan.plan_hash_sha256,
            object_counts_by_type={
                **execution.erased_counts,
                **{
                    f"invalidated_{key}": value
                    for key, value in execution.invalidated_counts.items()
                },
            },
            manifest_before_hash=execution.manifest_before,
            manifest_after_hash=execution.manifest_after or "",
            verification_hash=verification.verification_manifest_hash,
            completed_at=execution.completed_at or utc_now(),
            tombstone_status="verified",
            memory_erasure_tombstone_revision=MEMORY_ERASURE_TOMBSTONE_REVISION,
            created_at=execution.completed_at or utc_now(),
        )
        existing = self.store.get(
            "tombstone",
            "erasure_tombstone_id",
            tombstone.erasure_tombstone_id,
            scope.memory_boundary(),
        )
        if not existing:
            self.store.insert(
                "tombstone",
                (
                    "erasure_tombstone_id",
                    "governance_execution_id",
                    "client_id",
                    "vault_id",
                    "namespace",
                    "target_type",
                    "target_reference_digest",
                    "tombstone_status",
                    "completed_at",
                    "verification_hash",
                    "created_at",
                ),
                (
                    tombstone.erasure_tombstone_id,
                    execution.governance_execution_id,
                    scope.client_id,
                    scope.vault_id,
                    scope.namespace,
                    request.target_type,
                    request.target_reference_digest,
                    "verified",
                    tombstone.completed_at,
                    tombstone.verification_hash,
                    tombstone.created_at,
                ),
                tombstone.to_dict(),
            )
        LOGGER.info(
            "memory_erasure_tombstone_created",
            extra={"governance_execution_id": execution.governance_execution_id},
        )
        return tombstone

    def _finish_request_and_plan(
        self, scope: AuthenticatedScope, request: Any, plan: Any, execution: Any
    ) -> None:
        safe_request = replace(
            request,
            opaque_target_reference=f"erased:{request.target_reference_digest[:24]}",
            request_status="completed",
            completed_execution_id=execution.governance_execution_id,
            updated_at=execution.completed_at,
        )
        self.store.update_payload(
            "request",
            "governance_request_id",
            request.governance_request_id,
            safe_request.to_dict(),
            {
                "request_status": "completed",
                "completed_execution_id": execution.governance_execution_id,
                "updated_at": execution.completed_at,
            },
        )
        updated_plan = replace(plan, plan_status="executed")
        self.store.update_payload(
            "plan",
            "governance_plan_id",
            plan.governance_plan_id,
            updated_plan.to_dict(),
            {"plan_status": "executed"},
        )

    def _remove_sensitive_governance_working_state(
        self, request: Any, graph_id: str
    ) -> None:
        with self.repository.connect() as connection:
            connection.execute(
                f"DELETE FROM {self.store.tables['plan_item']} "
                f"WHERE governance_plan_id={self.p}",
                (request.approved_plan_id,),
            )
            connection.execute(
                f"DELETE FROM {self.store.tables['graph']} "
                f"WHERE dependency_graph_id={self.p}",
                (graph_id,),
            )

    def _insert_execution(
        self, scope: AuthenticatedScope, execution: MemoryGovernanceExecution
    ) -> None:
        self.store.insert(
            "execution",
            (
                "governance_execution_id",
                "governance_request_id",
                "governance_plan_id",
                "client_id",
                "vault_id",
                "namespace",
                "action_type",
                "target_type",
                "execution_status",
                "phase",
                "execution_idempotency_digest",
                "started_at",
                "completed_at",
                "updated_at",
            ),
            (
                execution.governance_execution_id,
                execution.governance_request_id,
                execution.governance_plan_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                execution.action_type,
                execution.target_type,
                execution.execution_status,
                execution.phase,
                execution.execution_idempotency_digest,
                execution.started_at,
                None,
                execution.updated_at,
            ),
            execution.to_dict(),
        )

    def _update_execution(self, execution: MemoryGovernanceExecution) -> None:
        self.store.update_payload(
            "execution",
            "governance_execution_id",
            execution.governance_execution_id,
            execution.to_dict(),
            {
                "execution_status": execution.execution_status,
                "phase": execution.phase,
                "completed_at": execution.completed_at,
                "updated_at": execution.updated_at,
            },
        )

    def _verification(
        self, scope: AuthenticatedScope, execution: MemoryGovernanceExecution
    ) -> Any:
        if not execution.verification_id:
            return None
        return self.store.get(
            "verification",
            "governance_verification_id",
            execution.verification_id,
            scope.memory_boundary(),
        )

    def _tombstone(
        self, scope: AuthenticatedScope, execution: MemoryGovernanceExecution
    ) -> Any:
        rows = self.store.manifest_rows("tombstone", scope.memory_boundary())
        return next(
            (
                item
                for item in rows
                if item["governance_execution_id"]
                == execution.governance_execution_id
            ),
            None,
        )

    @staticmethod
    def _execution(payload: dict[str, Any]) -> MemoryGovernanceExecution:
        payload["scope"] = tuple(payload["scope"])
        return MemoryGovernanceExecution(**payload)

    def _columns(self, connection: Any, name: str) -> list[str]:
        if self.backend == "postgres":
            rows = connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='prmr_self_serve' AND table_name=%s",
                (name,),
            ).fetchall()
            return [str(row["column_name"]) for row in rows]
        return [str(row["name"]) for row in connection.execute(f"PRAGMA table_info({name})")]


def recompute_after_dependency_removal(
    governed_object_id: str, removed_dependency_ids: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "governed_object_digest": sha256_text(governed_object_id),
        "removed_dependency_digests": [
            sha256_text(item) for item in removed_dependency_ids
        ],
        "outcome": "partial" if removed_dependency_ids else "valid",
        "provenance_complete": not removed_dependency_ids,
    }


__all__ = [
    "MemoryGovernanceExecutor",
    "recompute_after_dependency_removal",
]
