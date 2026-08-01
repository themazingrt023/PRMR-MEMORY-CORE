"""Deterministic governance request, dependency plan, and approval workflow."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import logging
from typing import Any

from .entity_store import json_value, placeholder, scope_params
from .memory_dependency_graph import MemoryDependencyGraph
from .memory_governance_models import (
    DependencyClassification,
    GovernanceActor,
    MEMORY_GOVERNANCE_PLAN_REVISION,
    MEMORY_GOVERNANCE_POLICY_REVISION,
    MEMORY_GOVERNANCE_SCHEMA_REVISION,
    MemoryDependencyGraphResult,
    MemoryGovernanceError,
    MemoryGovernancePlan,
    MemoryGovernanceRequest,
    MemoryGovernanceTargetType,
)
from .memory_governance_policy import (
    sanitise_governance_text,
    validate_action_policy,
    validate_actor,
)
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryGovernancePlanner:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.graphs = MemoryDependencyGraph(repository, initialize=False)
        self.p = placeholder(repository)

    def create_request(
        self,
        scope: AuthenticatedScope,
        *,
        action_type: str,
        target_type: str,
        target_reference: str,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        governance_policy_id: str = "strict_governance_v1",
        request_metadata: dict[str, Any] | None = None,
        requested_at: str | None = None,
    ) -> MemoryGovernanceRequest:
        validate_action_policy(action_type, governance_policy_id)
        actor = validate_actor(actor)
        if target_type not in {item.value for item in MemoryGovernanceTargetType}:
            raise MemoryGovernanceError(
                "GOVERNANCE_TARGET_INVALID", "Unsupported governance target."
            )
        if not isinstance(target_reference, str) or not target_reference:
            raise MemoryGovernanceError(
                "GOVERNANCE_TARGET_INVALID", "Target reference is required."
            )
        now = requested_at or utc_now()
        target_digest = sha256_text(target_reference)
        digest = sha256_text(
            canonical_json(
                {
                    "scope": scope.memory_boundary(),
                    "action": action_type,
                    "target_type": target_type,
                    "target_digest": target_digest,
                    "idempotency_key": idempotency_key,
                    "policy": governance_policy_id,
                    "revision": MEMORY_GOVERNANCE_SCHEMA_REVISION,
                }
            )
        )
        request_id = f"govreq_{digest[:24]}"
        existing = self.store.get(
            "request",
            "governance_request_id",
            request_id,
            scope.memory_boundary(),
        )
        if existing:
            return MemoryGovernanceRequest(**existing)
        metadata = self._safe_metadata(request_metadata or {})
        request = MemoryGovernanceRequest(
            governance_request_id=request_id,
            action_type=action_type,
            target_type=target_type,
            opaque_target_reference=target_reference,
            target_reference_digest=target_digest,
            client_id=scope.client_id,
            vault_id=scope.vault_id,
            namespace=scope.namespace,
            application_reference=scope.application_reference,
            actor_reference=scope.actor_reference,
            workspace_reference=scope.workspace_reference,
            entity_id=scope.entity_reference,
            session_reference=scope.session_reference,
            requested_by_actor_type=actor.actor_type,
            requested_by_actor_reference=actor.actor_reference,
            request_reason=sanitise_governance_text(reason),
            request_metadata=metadata,
            governance_policy_id=governance_policy_id,
            requested_at=now,
            request_idempotency_digest=digest,
            request_status="pending",
            approved_plan_id=None,
            completed_execution_id=None,
            memory_governance_schema_revision=MEMORY_GOVERNANCE_SCHEMA_REVISION,
            memory_governance_policy_revision=MEMORY_GOVERNANCE_POLICY_REVISION,
            created_at=now,
            updated_at=now,
        )
        self.store.insert(
            "request",
            (
                "governance_request_id",
                "client_id",
                "vault_id",
                "namespace",
                "action_type",
                "target_type",
                "target_reference_digest",
                "request_status",
                "request_idempotency_digest",
                "approved_plan_id",
                "completed_execution_id",
                "created_at",
                "updated_at",
            ),
            (
                request_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                action_type,
                target_type,
                target_digest,
                "pending",
                digest,
                None,
                None,
                now,
                now,
            ),
            request.to_dict(),
        )
        LOGGER.info(
            "memory_governance_request_created",
            extra={
                "governance_request_id": request_id,
                "action_type": action_type,
                "target_type": target_type,
            },
        )
        return request

    def plan(
        self,
        scope: AuthenticatedScope,
        governance_request_id: str,
        *,
        generated_at: str | None = None,
    ) -> MemoryGovernancePlan:
        request = self.get_request(scope, governance_request_id)
        now = generated_at or utc_now()
        graph = self.graphs.build(scope, request, generated_at=now)
        actions = self._actions(request, graph)
        blockers = tuple(graph.blockers)
        status = "blocked" if blockers else "ready"
        manifests = self._category_manifests(graph)
        material = {
            "request": request.governance_request_id,
            "graph": graph.graph_manifest_hash,
            "actions": actions,
            "blockers": blockers,
            "revision": MEMORY_GOVERNANCE_PLAN_REVISION,
        }
        plan_hash = sha256_text(canonical_json(material))
        plan_id = f"govplan_{plan_hash[:24]}"
        existing = self.store.get(
            "plan", "governance_plan_id", plan_id, scope.memory_boundary()
        )
        if existing:
            existing["scope"] = tuple(existing["scope"])
            for key in (
                "planned_erase_nodes",
                "planned_detach_edges",
                "planned_recompute_nodes",
                "planned_invalidate_nodes",
                "planned_retain_nodes",
                "planned_tombstones",
                "blockers",
                "preservation_holds",
            ):
                existing[key] = tuple(existing[key])
            return MemoryGovernancePlan(**existing)
        counts = Counter(node.node_type for node in graph.discovered_nodes)
        plan = MemoryGovernancePlan(
            governance_plan_id=plan_id,
            governance_request_id=request.governance_request_id,
            action_type=request.action_type,
            target_type=request.target_type,
            target_digest=request.target_reference_digest,
            scope=scope.memory_boundary(),
            dependency_graph_id=graph.dependency_graph_id,
            source_manifest_before=manifests["source"],
            event_manifest_before=manifests["event"],
            entity_manifest_before=manifests["entity"],
            relationship_manifest_before=manifests["relationship"],
            canonical_signal_manifest_before=manifests["canonical"],
            planned_erase_nodes=tuple(actions["erase"]),
            planned_detach_edges=tuple(actions["detach"]),
            planned_recompute_nodes=tuple(actions["recompute"]),
            planned_invalidate_nodes=tuple(actions["invalidate"]),
            planned_retain_nodes=tuple(actions["retain"]),
            planned_tombstones=("safe_erasure_tombstone",)
            if request.action_type.startswith("erase_")
            else (),
            blockers=blockers,
            preservation_holds=graph.active_holds,
            estimated_counts_by_type=dict(sorted(counts.items())),
            estimated_storage_bytes=None,
            plan_status=status,
            plan_hash_sha256=plan_hash,
            memory_governance_plan_revision=MEMORY_GOVERNANCE_PLAN_REVISION,
            created_at=now,
        )
        self.store.insert(
            "plan",
            (
                "governance_plan_id",
                "governance_request_id",
                "dependency_graph_id",
                "client_id",
                "vault_id",
                "namespace",
                "action_type",
                "target_type",
                "target_reference_digest",
                "plan_status",
                "plan_hash_sha256",
                "created_at",
                "approved_at",
            ),
            (
                plan_id,
                request.governance_request_id,
                graph.dependency_graph_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                request.action_type,
                request.target_type,
                request.target_reference_digest,
                status,
                plan_hash,
                now,
                None,
            ),
            plan.to_dict(),
        )
        self._persist_plan_items(scope, plan, graph, actions)
        request_status = "blocked" if blockers else "planned"
        self._update_request(request, request_status, now)
        LOGGER.info(
            "memory_governance_plan_blocked"
            if blockers
            else "memory_governance_plan_created",
            extra={
                "governance_plan_id": plan_id,
                "object_count": len(graph.discovered_nodes),
                "status": status,
            },
        )
        return plan

    def plan_erasure(
        self,
        scope: AuthenticatedScope,
        *,
        target_type: str,
        target_reference: str,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        action_type: str | None = None,
        governance_policy_id: str = "strict_governance_v1",
        generated_at: str | None = None,
    ) -> MemoryGovernancePlan:
        action = action_type or {
            "source": "erase_source",
            "actor": "erase_actor",
            "entity": "erase_entity",
            "session": "erase_session",
            "workspace": "erase_workspace",
            "application": "erase_application",
            "tenant_memory_boundary": "erase_tenant_memory",
        }.get(target_type)
        if not action:
            raise MemoryGovernanceError(
                "GOVERNANCE_TARGET_INVALID",
                "Target does not have a typed erasure operation.",
            )
        request = self.create_request(
            scope,
            action_type=action,
            target_type=target_type,
            target_reference=target_reference,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            governance_policy_id=governance_policy_id,
            requested_at=generated_at,
        )
        return self.plan(
            scope, request.governance_request_id, generated_at=generated_at
        )

    def plan_actor_erasure(self, scope: AuthenticatedScope, actor_reference: str, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(scope, target_type="actor", target_reference=actor_reference, **kwargs)

    def plan_entity_erasure(self, scope: AuthenticatedScope, entity_id: str, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(scope, target_type="entity", target_reference=entity_id, **kwargs)

    def plan_session_erasure(self, scope: AuthenticatedScope, session_reference: str, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(scope, target_type="session", target_reference=session_reference, **kwargs)

    def plan_workspace_erasure(self, scope: AuthenticatedScope, workspace_reference: str, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(scope, target_type="workspace", target_reference=workspace_reference, **kwargs)

    def plan_application_erasure(self, scope: AuthenticatedScope, application_reference: str, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(scope, target_type="application", target_reference=application_reference, **kwargs)

    def plan_tenant_memory_erasure(self, scope: AuthenticatedScope, **kwargs: Any) -> MemoryGovernancePlan:
        return self.plan_erasure(
            scope,
            target_type="tenant_memory_boundary",
            target_reference="::".join(scope.memory_boundary()),
            action_type="erase_tenant_memory",
            governance_policy_id="full_tenant_erasure_v1",
            **kwargs,
        )

    def approve_governance_plan(
        self,
        scope: AuthenticatedScope,
        governance_plan_id: str,
        *,
        actor: GovernanceActor,
        reason: str,
        idempotency_key: str,
        approved_at: str | None = None,
    ) -> MemoryGovernancePlan:
        actor = validate_actor(actor)
        sanitise_governance_text(reason)
        plan = self.get_plan(scope, governance_plan_id)
        if plan.plan_status == "approved":
            return plan
        if plan.plan_status == "blocked" or plan.blockers or plan.preservation_holds:
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_BLOCKED", "Governance plan has active blockers."
            )
        if plan.plan_status != "ready":
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_NOT_APPROVED", "Governance plan is not ready."
            )
        request = self.get_request(scope, plan.governance_request_id)
        current = self.graphs.build(
            scope, request, generated_at=approved_at or utc_now(), persist=False
        )
        if current.dependency_graph_id != plan.dependency_graph_id:
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_STALE",
                "Memory or governance controls changed after planning.",
            )
        now = approved_at or utc_now()
        updated = replace(
            plan,
            plan_status="approved",
            approved_at=now,
            approved_by=actor.actor_reference,
        )
        self.store.update_payload(
            "plan",
            "governance_plan_id",
            plan.governance_plan_id,
            updated.to_dict(),
            {"plan_status": "approved", "approved_at": now},
        )
        request = replace(
            request,
            request_status="approved",
            approved_plan_id=plan.governance_plan_id,
            updated_at=now,
        )
        self.store.update_payload(
            "request",
            "governance_request_id",
            request.governance_request_id,
            request.to_dict(),
            {
                "request_status": "approved",
                "approved_plan_id": plan.governance_plan_id,
                "updated_at": now,
            },
        )
        LOGGER.info(
            "memory_governance_plan_approved",
            extra={"governance_plan_id": plan.governance_plan_id},
        )
        return updated

    def get_request(
        self, scope: AuthenticatedScope, governance_request_id: str
    ) -> MemoryGovernanceRequest:
        payload = self.store.get(
            "request",
            "governance_request_id",
            governance_request_id,
            scope.memory_boundary(),
        )
        if not payload:
            raise MemoryGovernanceError(
                "GOVERNANCE_REQUEST_NOT_FOUND",
                "Governance request was not found in scope.",
            )
        return MemoryGovernanceRequest(**payload)

    def get_plan(
        self, scope: AuthenticatedScope, governance_plan_id: str
    ) -> MemoryGovernancePlan:
        payload = self.store.get(
            "plan",
            "governance_plan_id",
            governance_plan_id,
            scope.memory_boundary(),
        )
        if not payload:
            raise MemoryGovernanceError(
                "GOVERNANCE_PLAN_NOT_FOUND",
                "Governance plan was not found in scope.",
            )
        payload["scope"] = tuple(payload["scope"])
        for key in (
            "planned_erase_nodes",
            "planned_detach_edges",
            "planned_recompute_nodes",
            "planned_invalidate_nodes",
            "planned_retain_nodes",
            "planned_tombstones",
            "blockers",
            "preservation_holds",
        ):
            payload[key] = tuple(payload[key])
        return MemoryGovernancePlan(**payload)

    def _actions(
        self,
        request: MemoryGovernanceRequest,
        graph: MemoryDependencyGraphResult,
    ) -> dict[str, list[str]]:
        if request.action_type == "export":
            return {
                "erase": [],
                "detach": [],
                "recompute": [],
                "invalidate": [],
                "retain": [node.node_id for node in graph.discovered_nodes],
            }
        edge_by_node: dict[str, list[str]] = {}
        for edge in graph.discovered_edges:
            edge_by_node.setdefault(edge.from_node_id, []).append(edge.classification)
        actions = {key: [] for key in ("erase", "detach", "recompute", "invalidate", "retain")}
        for node in graph.discovered_nodes:
            classes = edge_by_node.get(node.node_id, [])
            if node.node_type in {"canonical_invalidation"}:
                actions["retain"].append(node.node_id)
            elif DependencyClassification.DERIVED_CACHE.value in classes or node.node_type in {
                "packet",
                "report",
                "query_run",
                "query_result",
                "evidence_bundle",
                "evidence_item",
                "explanation",
                "consolidated_memory",
                "checkpoint",
                "checkpoint_delta",
                "dynamics_snapshot",
                "signal_dynamics",
                "event_signal_projection",
                "canonical_signal_artifact",
                "reconstruction",
                "export_bundle",
                "export_request",
            }:
                actions["invalidate"].append(node.node_id)
            elif DependencyClassification.SHARED_REQUIRED.value in classes:
                actions["detach"].append(node.node_id)
                actions["recompute"].append(node.node_id)
            else:
                actions["erase"].append(node.node_id)
        return {key: sorted(set(value)) for key, value in actions.items()}

    def _persist_plan_items(
        self,
        scope: AuthenticatedScope,
        plan: MemoryGovernancePlan,
        graph: MemoryDependencyGraphResult,
        actions: dict[str, list[str]],
    ) -> None:
        node_by_id = {node.node_id: node for node in graph.discovered_nodes}
        sequence = 0
        rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for action in ("detach", "recompute", "invalidate", "erase", "retain"):
            for node_id in actions[action]:
                node = node_by_id[node_id]
                material = {
                    "plan": plan.governance_plan_id,
                    "action": action,
                    "node": node_id,
                }
                item_id = f"gitem_{sha256_text(canonical_json(material))[:24]}"
                rows.append(
                    (
                        (
                            item_id,
                            plan.governance_plan_id,
                            scope.client_id,
                            scope.vault_id,
                            scope.namespace,
                            action,
                            node.node_type,
                            node.storage_table,
                            node.storage_key,
                            sequence,
                        ),
                        {
                            "plan_item_id": item_id,
                            "governance_plan_id": plan.governance_plan_id,
                            "item_action": action,
                            "node": node.to_dict(),
                            "sequence_index": sequence,
                        },
                    )
                )
                sequence += 1
        self.store.insert_many(
            "plan_item",
            (
                "plan_item_id",
                "governance_plan_id",
                "client_id",
                "vault_id",
                "namespace",
                "item_action",
                "node_type",
                "storage_table",
                "storage_key",
                "sequence_index",
            ),
            rows,
        )

    @staticmethod
    def _category_manifests(
        graph: MemoryDependencyGraphResult,
    ) -> dict[str, str]:
        categories = {
            "source": {"source", "segment", "candidate_memory", "candidate_evidence"},
            "event": {"event", "admission", "admitted_memory_link", "event_evolution"},
            "entity": {item.node_type for item in graph.discovered_nodes if "entity" in item.node_type},
            "relationship": {item.node_type for item in graph.discovered_nodes if "relationship" in item.node_type},
            "canonical": {item.node_type for item in graph.discovered_nodes if "canonical" in item.node_type or item.node_type == "event_signal_projection"},
        }
        return {
            key: sha256_text(
                canonical_json(
                    [
                        node.to_dict()
                        for node in graph.discovered_nodes
                        if node.node_type in types
                    ]
                )
            )
            for key, types in categories.items()
        }

    def _update_request(
        self, request: MemoryGovernanceRequest, status: str, now: str
    ) -> None:
        updated = replace(request, request_status=status, updated_at=now)
        self.store.update_payload(
            "request",
            "governance_request_id",
            request.governance_request_id,
            updated.to_dict(),
            {"request_status": status, "updated_at": now},
        )

    @staticmethod
    def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = sanitise_governance_text(str(key), maximum=80)
            if isinstance(item, (bool, int, float)) or item is None:
                safe[safe_key] = item
            elif isinstance(item, str):
                safe[safe_key] = sanitise_governance_text(item, maximum=200)
        return safe


def approve_governance_plan(
    planner: MemoryGovernancePlanner,
    scope: AuthenticatedScope,
    governance_plan_id: str,
    actor: GovernanceActor,
    reason: str,
    idempotency_key: str,
) -> MemoryGovernancePlan:
    return planner.approve_governance_plan(
        scope,
        governance_plan_id,
        actor=actor,
        reason=reason,
        idempotency_key=idempotency_key,
    )


__all__ = ["MemoryGovernancePlanner", "approve_governance_plan"]
