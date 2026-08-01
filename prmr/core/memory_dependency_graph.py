"""Deterministic scope-bound dependency discovery across Memory Core stores."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import json
import logging
from typing import Any, Iterable

from .entity_store import json_value, placeholder, scope_params, table
from .memory_governance_models import (
    DependencyClassification,
    DependencyEdge,
    DependencyNode,
    MEMORY_DEPENDENCY_GRAPH_REVISION,
    MemoryDependencyGraphResult,
    MemoryGovernanceError,
    MemoryGovernanceRequest,
)
from .memory_governance_store import MemoryGovernanceStore
from .source_integrity import canonical_json, sha256_text
from .source_models import AuthenticatedScope


LOGGER = logging.getLogger("prmr.core.memory_governance")


@dataclass(frozen=True)
class StorageDescriptor:
    table_name: str
    node_type: str
    id_candidates: tuple[str, ...]
    classification: str
    shared_capable: bool = False
    blob_kind: str | None = None


def _d(
    table_name: str,
    node_type: str,
    *ids: str,
    classification: str = DependencyClassification.EXCLUSIVE_REQUIRED.value,
    shared: bool = False,
    blob_kind: str | None = None,
) -> StorageDescriptor:
    return StorageDescriptor(
        table_name, node_type, tuple(ids), classification, shared, blob_kind
    )


STORAGE_CATALOG = (
    _d("prmr_source_segments", "segment", "segment_id"),
    _d("prmr_candidate_evidence", "candidate_evidence", "candidate_evidence_id", "evidence_id"),
    _d("prmr_candidate_memories", "candidate_memory", "candidate_id"),
    _d("prmr_candidate_extraction_runs", "extraction_run", "extraction_run_id"),
    _d("prmr_memory_admission_decisions", "admission", "admission_id"),
    _d("prmr_admitted_memory_links", "admitted_memory_link", "admitted_memory_link_id"),
    _d("prmr_memory_evolution_records", "event_evolution", "evolution_id", "memory_evolution_id"),
    _d("prmr_memory_conflicts", "memory_conflict", "conflict_id"),
    _d("prmr_memory_reconstructions", "reconstruction", "reconstruction_id", classification="derived_cache"),
    _d("prmr_memory_importance_annotations", "importance_annotation", "importance_annotation_id"),
    _d("prmr_memory_signal_dynamics", "signal_dynamics", "signal_dynamics_id", classification="derived_cache"),
    _d("prmr_memory_dynamics_snapshots", "dynamics_snapshot", "dynamics_snapshot_id", classification="derived_cache"),
    _d("prmr_entity_evidence", "entity_evidence", "entity_evidence_id", "evidence_id", shared=True),
    _d("prmr_entity_mentions", "entity_mention", "entity_mention_id", "mention_id"),
    _d("prmr_entity_candidates", "entity_candidate", "entity_candidate_id"),
    _d("prmr_entity_identifiers", "entity_identifier", "entity_identifier_id"),
    _d("prmr_entity_aliases", "entity_alias", "entity_alias_id"),
    _d("prmr_entity_resolutions", "entity_resolution", "entity_resolution_id"),
    _d("prmr_entity_merges", "entity_merge", "entity_merge_id"),
    _d("prmr_entity_distinctness_assertions", "entity_distinctness", "entity_distinctness_id"),
    _d("prmr_event_entity_links", "event_entity_link", "event_entity_link_id"),
    _d("prmr_entities", "entity", "entity_id"),
    _d("prmr_relationship_evidence", "relationship_evidence", "relationship_evidence_id", "evidence_id", shared=True),
    _d("prmr_relationship_candidates", "relationship_candidate", "relationship_candidate_id"),
    _d("prmr_relationship_admissions", "relationship_admission", "relationship_admission_id"),
    _d("prmr_relationship_evolution", "relationship_evolution", "relationship_evolution_id"),
    _d("prmr_relationship_conflicts", "relationship_conflict", "relationship_conflict_id"),
    _d("prmr_relationships", "relationship", "relationship_id", shared=True),
    _d("prmr_memory_query_evidence_items", "evidence_item", "evidence_item_id", classification="derived_cache"),
    _d("prmr_memory_evidence_bundles", "evidence_bundle", "evidence_bundle_id", classification="derived_cache"),
    _d("prmr_memory_explanations", "explanation", "explanation_id", classification="derived_cache"),
    _d("prmr_memory_query_results", "query_result", "query_result_id", classification="derived_cache"),
    _d("prmr_memory_query_runs", "query_run", "query_run_id", classification="derived_cache"),
    _d("prmr_memory_query_result_comparisons", "query_comparison", "comparison_hash_sha256", classification="derived_cache"),
    _d("prmr_consolidated_memory_members", "consolidation_member", "consolidated_memory_member_id", "member_id", classification="derived_cache"),
    _d("prmr_consolidated_memories", "consolidated_memory", "consolidated_memory_id", classification="derived_cache"),
    _d("prmr_memory_consolidation_runs", "consolidation_run", "consolidation_run_id", classification="derived_cache"),
    _d("prmr_memory_consolidation_plans", "consolidation_plan", "consolidation_plan_id", classification="derived_cache"),
    _d("prmr_memory_checkpoint_deltas", "checkpoint_delta", "checkpoint_delta_id", classification="derived_cache"),
    _d("prmr_memory_checkpoints", "checkpoint", "checkpoint_id", classification="derived_cache"),
    _d("prmr_memory_consolidation_invalidations", "consolidation_invalidation", "invalidation_id", classification="derived_cache"),
    _d("prmr_memory_consolidation_equivalence_proofs", "equivalence_proof", "equivalence_proof_id", classification="derived_cache"),
    _d("prmr_interpretation_proposal_links", "interpretation_proposal_link", "proposal_link_id"),
    _d("prmr_interpretation_unknown_results", "interpretation_unknown", "unknown_result_id"),
    _d("prmr_interpretation_validation_failures", "interpretation_validation_failure", "validation_failure_id"),
    _d("prmr_interpretation_response_records", "interpretation_response", "interpretation_response_record_id"),
    _d("prmr_interpretation_attempts", "interpretation_attempt", "interpretation_attempt_id"),
    _d("prmr_interpretation_requests", "interpretation_request", "interpretation_request_id"),
    _d("prmr_event_signal_projections", "event_signal_projection", "event_signal_projection_id", classification="derived_cache"),
    _d("prmr_canonical_signal_alias_assertions", "canonical_signal_alias", "signal_alias_assertion_id"),
    _d("prmr_canonical_signal_decisions", "canonical_signal_decision", "canonical_signal_decision_id"),
    _d("prmr_canonical_signal_proposals", "canonical_signal_proposal", "canonical_signal_proposal_id", shared=True),
    _d("prmr_canonical_signal_definitions", "canonical_signal_definition", "canonical_signal_id", shared=True),
    _d("prmr_canonical_signal_artifacts", "canonical_signal_artifact", "canonical_artifact_id", classification="derived_cache"),
    _d("prmr_canonical_artifact_invalidations", "canonical_invalidation", "invalidation_id", classification="audit_reference"),
    _d("prmr_continuity_packet_state_dimensions_v2", "packet_v2_dimension", "state_dimension_key", classification="derived_cache"),
    _d("prmr_continuity_packet_items_v2", "packet_v2_item", "event_id", classification="derived_cache"),
    _d("prmr_continuity_packet_conflicts_v2", "packet_v2_conflict", "conflict_id", classification="derived_cache"),
    _d("prmr_continuity_packet_entities_v2", "packet_v2_entity", "entity_id", classification="derived_cache"),
    _d("prmr_continuity_packet_relationships_v2", "packet_v2_relationship", "relationship_id", classification="derived_cache"),
    _d("prmr_continuity_packet_comparisons_v2", "packet_v2_comparison", "comparison_hash", classification="derived_cache"),
    _d("prmr_continuity_packets_v2", "packet_v2", "packet_id", classification="derived_cache"),
    _d("packets", "packet", "packet_id", classification="derived_cache"),
    _d("reports", "report", "report_id", classification="derived_cache"),
    _d(
        "prmr_memory_export_bundles",
        "export_bundle",
        "memory_export_bundle_id",
        classification="derived_cache",
    ),
    _d(
        "prmr_memory_export_requests",
        "export_request",
        "memory_export_request_id",
        classification="derived_cache",
    ),
    _d("events", "event", "event_id", blob_kind="event_list"),
    _d("prmr_sources", "source", "source_id"),
)


SUBJECT_FIELDS = {
    "actor": ("actor_reference",),
    "entity": ("entity_id", "entity_reference", "entity_references"),
    "session": ("session_reference",),
    "workspace": ("workspace_reference",),
    "application": ("application_reference",),
}


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(_strings(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.update(_strings(item))
    elif isinstance(value, str):
        found.add(value)
    return found


def _reference_strings(value: Any, key: str | None = None) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.update(_reference_strings(child, str(child_key)))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.update(_reference_strings(item, key))
    elif isinstance(value, str) and key:
        normalized = key.lower()
        blocked = {
            "client_id",
            "vault_id",
            "namespace",
            "content",
            "signal",
            "summary",
            "description",
            "reason",
            "safe_detail",
            "payload",
            "sanitised_payload",
            "evidence_quote",
        }
        reference_key = (
            normalized.endswith("_id")
            or normalized.endswith("_ids")
            or normalized.endswith("_reference")
            or normalized.endswith("_references")
            or normalized
            in {
                "subject",
                "object",
                "members",
                "dependencies",
                "target",
                "_storage_key",
            }
        )
        if normalized not in blocked and reference_key:
            found.add(value)
    return found


def _support_reference_count(payload: dict[str, Any]) -> int:
    """Count explicit evidence supports without treating ordinary IDs as support."""
    support: set[str] = set()
    for key, value in payload.items():
        normalized = str(key).lower()
        if normalized in {
            "source_ids",
            "event_ids",
            "candidate_ids",
            "evidence_ids",
            "supporting_source_ids",
            "supporting_event_ids",
            "supporting_candidate_ids",
            "supporting_evidence_ids",
        }:
            support.update(_strings(value))
    return len(support)


class MemoryDependencyGraph:
    def __init__(self, repository: Any, *, initialize: bool = True) -> None:
        self.repository = repository
        self.store = MemoryGovernanceStore(repository, initialize=initialize)
        self.p = placeholder(repository)
        self.backend = str(getattr(repository, "backend_name", "sqlite"))

    def build(
        self,
        scope: AuthenticatedScope,
        request: MemoryGovernanceRequest,
        *,
        generated_at: str,
        persist: bool = True,
    ) -> MemoryDependencyGraphResult:
        self._assert_scope(scope, request)
        records = self._scope_records(scope)
        if request.action_type == "export":
            records = [
                item
                for item in records
                if item[0].node_type not in {"export_request", "export_bundle"}
            ]
        targets = self._target_records(request, records)
        if not targets and request.target_type != "tenant_memory_boundary":
            raise MemoryGovernanceError(
                "GOVERNANCE_SCOPE_DENIED", "Governance target was not found in scope."
            )
        selected: dict[str, tuple[DependencyNode, dict[str, Any], StorageDescriptor]] = {
            item[0].node_id: item for item in targets
        }
        known_references = {request.opaque_target_reference}
        known_references.update(node.storage_key for node, _, _ in targets)
        queue = deque(known_references)
        while queue:
            queue.popleft()
            changed = False
            for node, payload, descriptor in records:
                if node.node_id in selected:
                    continue
                if _reference_strings(payload).intersection(known_references):
                    selected[node.node_id] = (node, payload, descriptor)
                    new_refs = {node.storage_key}.difference(known_references)
                    known_references.update(new_refs)
                    queue.extend(sorted(new_refs))
                    changed = True
            if not changed and not queue:
                break
        target_ids = {item[0].node_id for item in targets}
        edges: list[DependencyEdge] = []
        selected_keys = {
            item[0].storage_key: item[0].node_id for item in selected.values()
        }
        for node, payload, descriptor in selected.values():
            references = _reference_strings(payload)
            parents = sorted(references.intersection(selected_keys))
            for parent_key in parents:
                parent_id = selected_keys[parent_key]
                if parent_id == node.node_id:
                    continue
                classification = descriptor.classification
                if descriptor.shared_capable and (
                    len(parents) > 1 or _support_reference_count(payload) > 1
                ):
                    classification = DependencyClassification.SHARED_REQUIRED.value
                material = {
                    "from": node.node_id,
                    "to": parent_id,
                    "classification": classification,
                }
                edges.append(
                    DependencyEdge(
                        edge_id=f"medge_{sha256_text(canonical_json(material))[:24]}",
                        from_node_id=node.node_id,
                        to_node_id=parent_id,
                        edge_type=self._edge_type(node.node_type),
                        classification=classification,
                    )
                )
        edges.sort(key=lambda item: item.edge_id)
        nodes = tuple(sorted((item[0] for item in selected.values()), key=lambda x: x.node_id))
        holds = self._active_holds(scope, request)
        manifest_material = {
            "request": request.governance_request_id,
            "targets": sorted(target_ids),
            "nodes": [item.to_dict() for item in nodes],
            "edges": [item.to_dict() for item in edges],
            "holds": holds,
            "revision": MEMORY_DEPENDENCY_GRAPH_REVISION,
        }
        manifest = sha256_text(canonical_json(manifest_material))
        graph_id = f"mdep_{manifest[:24]}"
        counts = Counter(edge.classification for edge in edges)
        result = MemoryDependencyGraphResult(
            dependency_graph_id=graph_id,
            governance_request_id=request.governance_request_id,
            target_nodes=tuple(
                sorted((item[0] for item in targets), key=lambda value: value.node_id)
            ),
            discovered_nodes=nodes,
            discovered_edges=tuple(edges),
            exclusive_dependency_count=counts[
                DependencyClassification.EXCLUSIVE_REQUIRED.value
            ],
            shared_dependency_count=counts[
                DependencyClassification.SHARED_REQUIRED.value
            ],
            cache_dependency_count=counts[
                DependencyClassification.DERIVED_CACHE.value
            ],
            blockers=tuple("active_preservation_hold" for _ in holds),
            active_holds=tuple(holds),
            graph_manifest_hash=manifest,
            graph_revision=MEMORY_DEPENDENCY_GRAPH_REVISION,
            generated_at=generated_at,
        )
        if persist:
            self._persist(scope, result)
        LOGGER.info(
            "memory_dependency_graph_built",
            extra={
                "governance_request_id": request.governance_request_id,
                "object_count": len(nodes),
                "edge_count": len(edges),
            },
        )
        return result

    def scope_manifest(self, scope: AuthenticatedScope) -> str:
        records = self._scope_records(scope)
        material = [
            {
                "node": node.to_dict(),
                "payload_digest": sha256_text(canonical_json(payload)),
            }
            for node, payload, _ in records
            if not node.storage_table.startswith("prmr_memory_governance_")
        ]
        return sha256_text(canonical_json(sorted(material, key=lambda item: item["node"]["node_id"])))

    def _scope_records(
        self, scope: AuthenticatedScope
    ) -> list[tuple[DependencyNode, dict[str, Any], StorageDescriptor]]:
        records: list[tuple[DependencyNode, dict[str, Any], StorageDescriptor]] = []
        unscoped: list[
            tuple[DependencyNode, dict[str, Any], StorageDescriptor]
        ] = []
        with self.repository.connect() as connection:
            if self.backend == "postgres":
                column_rows = connection.execute(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='prmr_self_serve' "
                    "ORDER BY table_name,ordinal_position"
                ).fetchall()
                columns_by_table: dict[str, list[str]] = {}
                for column_row in column_rows:
                    columns_by_table.setdefault(
                        str(column_row["table_name"]), []
                    ).append(str(column_row["column_name"]))

                parts: list[str] = []
                params: list[Any] = []
                descriptors: list[StorageDescriptor] = []
                for descriptor in STORAGE_CATALOG:
                    columns = columns_by_table.get(descriptor.table_name)
                    if not columns:
                        continue
                    qualified = table(self.repository, descriptor.table_name)
                    parts.append(
                        f"SELECT {self.p} AS table_name,to_jsonb(t) AS row_data "
                        f"FROM {qualified} AS t"
                        + (
                            f" WHERE client_id={self.p} AND vault_id={self.p} "
                            f"AND namespace={self.p}"
                            if {"client_id", "vault_id", "namespace"}.issubset(
                                columns
                            )
                            else (
                                f" WHERE scope_key={self.p}"
                                if descriptor.table_name == "events"
                                and "scope_key" in columns
                                else ""
                            )
                        )
                    )
                    params.append(descriptor.table_name)
                    if {"client_id", "vault_id", "namespace"}.issubset(columns):
                        params.extend(scope_params(scope))
                    elif (
                        descriptor.table_name == "events"
                        and "scope_key" in columns
                    ):
                        params.append("::".join(scope.memory_boundary()))
                    descriptors.append(descriptor)
                batched_rows = (
                    connection.execute(
                        " UNION ALL ".join(parts), tuple(params)
                    ).fetchall()
                    if parts
                    else []
                )
                rows_by_table: dict[str, list[dict[str, Any]]] = {}
                for row in batched_rows:
                    rows_by_table.setdefault(str(row["table_name"]), []).append(
                        dict(row["row_data"])
                    )
                table_batches = [
                    (
                        descriptor,
                        columns_by_table[descriptor.table_name],
                        rows_by_table.get(descriptor.table_name, []),
                    )
                    for descriptor in descriptors
                ]
            else:
                table_batches = []
                for descriptor in STORAGE_CATALOG:
                    if not self._table_exists(connection, descriptor.table_name):
                        continue
                    columns = self._columns(connection, descriptor.table_name)
                    table_batches.append(
                        (
                            descriptor,
                            columns,
                            self._rows(
                                connection,
                                descriptor.table_name,
                                columns,
                                scope,
                            ),
                        )
                    )

            for descriptor, columns, rows in table_batches:
                for row in rows:
                    mapping = dict(row)
                    payload = _decode(mapping.get("payload_json", mapping))
                    if not isinstance(payload, dict):
                        payload = {"value": payload}
                    if not self._payload_in_scope(payload, mapping, scope):
                        continue
                    if descriptor.blob_kind == "event_list":
                        event_payload = _decode(mapping.get("payload_json"))
                        events = event_payload if isinstance(event_payload, list) else []
                        for event in events:
                            if isinstance(event, dict):
                                records.append(
                                    self._record_for(
                                        descriptor,
                                        event,
                                        event,
                                        scope,
                                        str(event.get("event_id", "")),
                                    )
                                )
                        continue
                    key = self._row_key(mapping, payload, descriptor, columns)
                    if key:
                        record = self._record_for(
                            descriptor, mapping, payload, scope, key
                        )
                        if {"client_id", "vault_id", "namespace"}.issubset(
                            columns
                        ):
                            records.append(record)
                        else:
                            unscoped.append(record)
        owned_keys = {node.storage_key for node, _, _ in records}
        pending = unscoped
        while pending:
            retained = []
            changed = False
            for item in pending:
                node, payload, _ = item
                if _reference_strings(payload).intersection(owned_keys):
                    records.append(item)
                    owned_keys.add(node.storage_key)
                    changed = True
                else:
                    retained.append(item)
            if not changed:
                break
            pending = retained
        return records

    def _record_for(
        self,
        descriptor: StorageDescriptor,
        row: dict[str, Any],
        payload: dict[str, Any],
        scope: AuthenticatedScope,
        key: str,
    ) -> tuple[DependencyNode, dict[str, Any], StorageDescriptor]:
        combined = {**row, **payload}
        combined.pop("payload_json", None)
        for field_name, value in tuple(combined.items()):
            if field_name.endswith("_json"):
                decoded = _decode(value)
                combined[field_name] = decoded
                combined.setdefault(field_name[:-5], decoded)
        node_material = {
            "table": descriptor.table_name,
            "key": key,
            "scope": scope.memory_boundary(),
        }
        node = DependencyNode(
            node_id=f"mnode_{sha256_text(canonical_json(node_material))[:24]}",
            node_type=descriptor.node_type,
            storage_table=descriptor.table_name,
            storage_key=key,
            scope_fingerprint=sha256_text(
                canonical_json(scope.memory_boundary())
            )[:24],
            content_digest=sha256_text(canonical_json(combined)),
        )
        combined["_storage_key"] = key
        return node, combined, descriptor

    def _target_records(
        self,
        request: MemoryGovernanceRequest,
        records: list[tuple[DependencyNode, dict[str, Any], StorageDescriptor]],
    ) -> list[tuple[DependencyNode, dict[str, Any], StorageDescriptor]]:
        if request.target_type == "tenant_memory_boundary":
            return list(records)
        if request.target_type in SUBJECT_FIELDS:
            fields = SUBJECT_FIELDS[request.target_type]
            targets = []
            for item in records:
                payload = item[1]
                if not any(
                    request.opaque_target_reference in _strings(payload.get(field))
                    for field in fields
                ):
                    continue
                if request.target_type == "entity":
                    entity_references = _strings(payload.get("entity_references"))
                    if (
                        len(entity_references) > 1
                        and item[0].node_type
                        not in {
                            "entity",
                            "entity_alias",
                            "entity_identifier",
                            "entity_mention",
                            "entity_resolution",
                            "event_entity_link",
                            "relationship",
                            "relationship_evidence",
                            "relationship_candidate",
                            "relationship_admission",
                            "relationship_evolution",
                            "relationship_conflict",
                        }
                    ):
                        continue
                targets.append(item)
            return targets
        aliases = {
            "candidate": {"candidate_memory"},
            "admission": {"admission", "admitted_memory_link"},
            "canonical_signal_mapping": {
                "canonical_signal_proposal",
                "canonical_signal_decision",
                "canonical_signal_alias",
            },
        }
        types = aliases.get(request.target_type, {request.target_type})
        return [
            item
            for item in records
            if item[0].node_type in types
            and item[0].storage_key == request.opaque_target_reference
        ]

    def _active_holds(
        self, scope: AuthenticatedScope, request: MemoryGovernanceRequest
    ) -> list[str]:
        holds = self.store.manifest_rows("hold", scope.memory_boundary())
        return sorted(
            item["preservation_hold_id"]
            for item in holds
            if item.get("hold_status") == "active"
            and (
                item.get("target_reference_digest")
                == request.target_reference_digest
                or item.get("target_type") == "tenant_memory_boundary"
            )
        )

    def _persist(
        self, scope: AuthenticatedScope, graph: MemoryDependencyGraphResult
    ) -> None:
        existing = self.store.get(
            "graph",
            "dependency_graph_id",
            graph.dependency_graph_id,
            scope.memory_boundary(),
        )
        if existing:
            return
        self.store.insert(
            "graph",
            (
                "dependency_graph_id",
                "governance_request_id",
                "client_id",
                "vault_id",
                "namespace",
                "graph_manifest_hash",
                "created_at",
            ),
            (
                graph.dependency_graph_id,
                graph.governance_request_id,
                scope.client_id,
                scope.vault_id,
                scope.namespace,
                graph.graph_manifest_hash,
                graph.generated_at,
            ),
            graph.to_dict(),
        )

    def _table_exists(self, connection: Any, name: str) -> bool:
        if self.backend == "postgres":
            row = connection.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='prmr_self_serve' "
                "AND table_name=%s",
                (name,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
        return bool(row)

    def _columns(self, connection: Any, name: str) -> list[str]:
        if self.backend == "postgres":
            rows = connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='prmr_self_serve' AND table_name=%s "
                "ORDER BY ordinal_position",
                (name,),
            ).fetchall()
            return [str(row["column_name"]) for row in rows]
        return [str(row["name"]) for row in connection.execute(f"PRAGMA table_info({name})")]

    def _rows(
        self,
        connection: Any,
        name: str,
        columns: list[str],
        scope: AuthenticatedScope,
    ) -> list[Any]:
        qualified = table(self.repository, name)
        if {"client_id", "vault_id", "namespace"}.issubset(columns):
            return list(
                connection.execute(
                    f"SELECT * FROM {qualified} WHERE client_id={self.p} "
                    f"AND vault_id={self.p} AND namespace={self.p}",
                    scope_params(scope),
                ).fetchall()
            )
        if name == "events" and "scope_key" in columns:
            key = "::".join(scope.memory_boundary())
            return list(
                connection.execute(
                    f"SELECT * FROM {qualified} WHERE scope_key={self.p}", (key,)
                ).fetchall()
            )
        return list(connection.execute(f"SELECT * FROM {qualified}").fetchall())

    @staticmethod
    def _payload_in_scope(
        payload: dict[str, Any], row: dict[str, Any], scope: AuthenticatedScope
    ) -> bool:
        combined = {**row, **payload}
        explicit = tuple(
            str(combined.get(key, ""))
            for key in ("client_id", "vault_id", "namespace")
        )
        if any(explicit):
            return explicit == scope.memory_boundary()
        key = str(combined.get("scope_key", ""))
        return not key or key == "::".join(scope.memory_boundary())

    @staticmethod
    def _row_key(
        row: dict[str, Any],
        payload: dict[str, Any],
        descriptor: StorageDescriptor,
        columns: Iterable[str],
    ) -> str | None:
        for candidate in descriptor.id_candidates:
            value = row.get(candidate, payload.get(candidate))
            if value:
                return str(value)
        for candidate in columns:
            if candidate.endswith("_id") and row.get(candidate):
                return str(row[candidate])
        return None

    @staticmethod
    def _edge_type(node_type: str) -> str:
        if node_type in {"segment", "candidate_evidence", "entity_evidence", "relationship_evidence"}:
            return "supported_by"
        if node_type in {"query_result", "checkpoint", "packet", "consolidated_memory"}:
            return "derived_from"
        if node_type in {"entity_mention", "event_entity_link"}:
            return "linked_to"
        if node_type.startswith("canonical_signal"):
            return "maps_to"
        return "depends_on"

    @staticmethod
    def _assert_scope(
        scope: AuthenticatedScope, request: MemoryGovernanceRequest
    ) -> None:
        if request.client_id != scope.client_id or request.vault_id != scope.vault_id or request.namespace != scope.namespace:
            raise MemoryGovernanceError(
                "GOVERNANCE_SCOPE_DENIED", "Governance request was not found in scope."
            )


__all__ = [
    "MemoryDependencyGraph",
    "STORAGE_CATALOG",
    "StorageDescriptor",
    "_reference_strings",
]
